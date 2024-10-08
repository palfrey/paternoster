from datetime import datetime, timedelta
import os
from pathlib import Path
import threading
import traceback
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade
import atexit
import sys

try:
    import uwsgi
except ImportError:
    uwsgi = None
    dataLock = threading.Lock()
try:
    import apis
except ImportError:
    from . import apis

yourTimer = None

POOL_TIME = 30


def create_app():
    app = Flask(__name__)
    default_db_path = Path(__file__).parent.joinpath("app.db")
    db_url = os.getenv("DATABASE_URL", f"sqlite:///{default_db_path.as_posix()}")
    db_url = db_url.replace(  # because of https://stackoverflow.com/questions/62688256/sqlalchemy-exc-nosuchmoduleerror-cant-load-plugin-sqlalchemy-dialectspostgre
        "postgres://", "postgresql://"
    )
    print(db_url)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    db = SQLAlchemy(app)
    Migrate(app, db)

    with app.app_context():
        upgrade()

    class Station(db.Model):
        id = db.Column(db.String(128), primary_key=True)
        name = db.Column(db.String(128))
        source = db.Column(db.String(128))

        def to_json(self):
            return apis.hashdict({"id": self.id, "name": self.name, "source": self.source})

    class Lift(db.Model):
        id = db.Column(db.String(128), primary_key=True)
        location = db.Column(db.String(128))
        message = db.Column(db.Text)
        station_id = db.Column(db.String, db.ForeignKey("station.id"), nullable=False)
        station = db.relationship("Station", backref=db.backref("lifts", lazy=True))
        source = db.Column(db.String(128))

    class Updates(db.Model):
        id = db.Column(db.String(128), primary_key=True)
        last_updated = db.Column(db.DateTime, nullable=True)

    def interrupt():
        global yourTimer
        if yourTimer is not None:
            yourTimer.cancel()
            yourTimer = None

    def update_stations(kind: str, stations: dict[str, str]) -> None:
        old_stations = set([st.name for st in Station.query.filter_by(source=kind).all()])
        missing_stations = old_stations - set(stations.values())
        print("missing stations", missing_stations)
        for station in missing_stations:
            id = Station.query.filter_by(source=kind, name=station).all()[0].id
            Lift.query.filter_by(station_id=id).delete()
            Station.query.filter_by(id=id).delete()
        new_stations = set(stations.values()) - old_stations
        print("new stations", new_stations)
        for station_id, station in stations.items():
            if station not in new_stations:
                continue
            obj = Station(id=station_id, name=station, source=kind)
            db.session.add(obj)

    def update_nr_stations():
        nr_stations = apis.nr_stations_and_lifts()
        update_stations("nr", nr_stations["stations"])
        Lift.query.filter_by(source="nr").delete()
        for lift_id, lift in nr_stations["lifts"].items():
            station = Station.query.get(lift["station_id"])
            obj = Lift(
                id=lift_id, message=lift["status"], location=lift["location"], source="nr", station_id=station.id
            )
            db.session.add(obj)

        print("updated nr stations")

    def update_tfl_stations():
        tfl_stations = apis.tfl_stations()
        update_stations("tfl", tfl_stations)
        print("updated tfl stations")

    def closest_station(station_source: str, name: str):
        stations = Station.query.filter_by(source=station_source).filter(Station.name.startswith(name)).all()
        if len(stations) == 1:
            return stations[0]
        elif len(stations) == 0:
            raise Exception((station_source, name))
        else:
            for poss in stations:
                if poss.name == name:
                    return poss
            raise Exception([st.__dict__ for st in stations], name)

    def tflapi_lift_issues():
        lifts = apis.tflapi_lift_issues()
        Lift.query.filter_by(source="tflapi").delete()
        for lift in lifts:
            station = closest_station("tfl", lift["station"])
            obj = Lift(
                id=lift["id"], message=lift["status"], location=lift["location"], source="tflapi", station_id=station.id
            )
            db.session.add(obj)

    updaters = {
        "nr_stations_update": {
            "func": update_nr_stations,
            "limit": timedelta(minutes=5),
        },
        "update_tfl_stations": {
            "func": update_tfl_stations,
            "limit": timedelta(days=1),
        },
        "tflapi_lift_issues": {"func": tflapi_lift_issues, "limit": timedelta(minutes=5)},
    }

    def doStuff():
        global yourTimer
        yourTimer = None
        if uwsgi is not None:
            uwsgi.lock()
        else:
            dataLock.acquire()
        print("update")
        for key, value in updaters.items():
            update = Updates.query.get(key)
            if update is not None:
                age = datetime.now() - update.last_updated
                if age > value["limit"]:
                    print(f"{key}: out of date")
                    try:
                        value["func"]()
                        update.last_updated = datetime.now()
                        db.session.commit()
                        print(f"{key}: updated")
                    except Exception as e:
                        print("Issue during update cycle", e)
                        print(traceback.format_exc())
                else:
                    print(f"{key}: ok {age}")
            else:
                value["func"]()
                update = Updates(id=key, last_updated=datetime.now())
                db.session.add(update)
                db.session.commit()

        if uwsgi is not None:
            uwsgi.unlock()
        else:
            dataLock.release()

        if os.environ.get("FLASK_RUN_FROM_CLI") != "true":
            yourTimer = threading.Timer(POOL_TIME, doStuff, ())
            yourTimer.start()

    if "db" not in sys.argv:
        with app.app_context():
            doStuff()
    atexit.register(interrupt)
    return {"app": app, "Updates": Updates, "Station": Station, "Lift": Lift}


data = create_app()
print("booted")
app = data["app"]
Lift = data["Lift"]
Station = data["Station"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/getstations")
def getstations():
    term = request.args.get("term")
    stations = sorted(
        set([station.name for station in Station.query.filter(Station.name.ilike(f"%{term}%")).limit(10).all()])
    )
    return jsonify([{"id": station, "label": station, "value": station} for station in stations])


@app.route("/getlifts")
def getlifts():
    station = request.args.get("station")
    stations = Station.query.filter(Station.name.startswith(station)).all()

    # Sometimes we've got exact matches, and sometimes not.
    # This lets us deal with both the "TfL and NR don't agree on whether Station goes at the end of a station name" case
    # and the "Cambridge vs. Cambridge North" case
    exact_matches = [st for st in stations if st.name == station]
    if len(exact_matches) > 0:
        # We prefer exact matches
        stations = exact_matches
    # but will take non-exact but "begins with"

    if len(stations) > 1:
        # If we have more than one, there's sometimes issues where one API thinks one thing and the other something else
        # First see if only one has lifts, and use that

        lift_counts = [(st, Lift.query.filter(Lift.station == st).count()) for st in stations]
        non_zero_lifts = [item[0] for item in lift_counts if item[1] != 0]
        if len(non_zero_lifts) == 1:
            stations = non_zero_lifts

    if len(stations) > 1:
        # Next try if there's both TfL and NR entries, skip the NR entry as those appear to be wrong more often (e.g. Canonbury)
        nr_stations = [st for st in stations if st.source == "nr"]
        tfl_stations = [st for st in stations if st.source == "tfl"]
        if len(tfl_stations) > 0 and len(nr_stations) > 0:
            stations = tfl_stations
    lifts = Lift.query.filter(Lift.station_id.in_([st.id for st in stations]))
    station_map = dict([(st.id, st) for st in stations])
    return jsonify(
        list(
            set(
                [
                    apis.hashdict(
                        {
                            "location": lift.location,
                            "message": lift.message,
                            "station": station_map[lift.station_id].to_json(),
                        }
                    )
                    for lift in lifts
                    if lift.location != ""
                ]
            )
        )
    )


if os.environ.get("UWSGI_RELOADS") is None and not sys.argv[0].endswith("flask"):
    if yourTimer is not None:
        yourTimer.cancel()
    # Running as test, not uwsgi block or flask
    sys.exit()
