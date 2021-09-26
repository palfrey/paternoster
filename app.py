from datetime import datetime, timedelta
import os
import threading
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade
import atexit
import sys
import apis

dataLock = threading.Lock()
yourTimer = None

POOL_TIME = 5


def create_app():
    app = Flask(__name__)
    db_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
    db_url = db_url.replace(  # because of https://stackoverflow.com/questions/62688256/sqlalchemy-exc-nosuchmoduleerror-cant-load-plugin-sqlalchemy-dialectspostgre
        "postgres://", "postgresql://"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db = SQLAlchemy(app)
    Migrate(app, db)

    with app.app_context():
        upgrade()

    class Station(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(128))
        source = db.Column(db.String(128))

    class Lift(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        location = db.Column(db.String(128))
        message = db.Column(db.Text)
        station_id = db.Column(db.Integer, db.ForeignKey("station.id"), nullable=False)
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

    def update_nr_stations():
        nr_stations = apis.nr_stations()
        Station.query.filter_by(source="nr").delete()
        for station in nr_stations:
            obj = Station(name=station, source="nr")
            db.session.add(obj)
        print("updated nr stations")

    def update_tfl_stations():
        tfl_stations = apis.tfl_stations()
        Station.query.filter_by(source="tfl").delete()
        for station in tfl_stations:
            obj = Station(name=station, source="tfl")
            db.session.add(obj)
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

    def nr_non_working_lifts():
        lifts = apis.nr_non_working_lifts()
        Lift.query.filter_by(source="nr").delete()
        for lift in lifts:
            station = closest_station("nr", lift["station"])
            obj = Lift(message=lift["status"], location=lift["location"], source="nr", station_id=station.id)
            db.session.add(obj)

    def tflapi_lift_issues():
        lifts = apis.tflapi_lift_issues()
        Lift.query.filter_by(source="tflapi").delete()
        for lift in lifts:
            station = closest_station("tfl", lift["station"])
            obj = Lift(message=lift["status"], location=lift["location"], source="tflapi", station_id=station.id)
            db.session.add(obj)

    updaters = {
        "nr_stations_update": {
            "func": update_nr_stations,
            "limit": timedelta(days=1),
        },
        "update_tfl_stations": {
            "func": update_tfl_stations,
            "limit": timedelta(days=1),
        },
        "nr_non_working_lifts": {"func": nr_non_working_lifts, "limit": timedelta(minutes=5)},
        "tflapi_lift_issues": {"func": tflapi_lift_issues, "limit": timedelta(minutes=5)},
    }

    def doStuff():
        global yourTimer
        yourTimer = None
        with dataLock:
            print("update")
            for key, value in updaters.items():
                update = Updates.query.get(key)
                if update is not None:
                    age = datetime.now() - update.last_updated
                    if age > value["limit"]:
                        print(f"{key}: out of date")
                        value["func"]()
                        update.last_updated = datetime.now()
                        db.session.commit()
                    else:
                        print(f"{key}: ok {age}")
                else:
                    value["func"]()
                    update = Updates(id=key, last_updated=datetime.now())
                    db.session.add(update)
                    db.session.commit()

        if os.environ.get("FLASK_RUN_FROM_CLI") != "true":
            yourTimer = threading.Timer(POOL_TIME, doStuff, ())
            yourTimer.start()

    if "db" not in sys.argv:
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
        set([station.name for station in Station.query.filter(Station.name.contains(term)).limit(10).all()])
    )
    return jsonify([{"id": station, "label": station, "value": station} for station in stations])


@app.route("/getlifts")
def getlifts():
    station = request.args.get("station")
    stations = [st.id for st in Station.query.filter(Station.name.startswith(station)).all()]
    lifts = Lift.query.filter(Lift.station_id.in_(stations))
    return jsonify([{"location": lift.location, "message": lift.message} for lift in lifts])
