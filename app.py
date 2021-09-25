from datetime import datetime, timedelta
import threading
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import atexit
import sys
from . import apis

dataLock = threading.Lock()
yourTimer = None

POOL_TIME = 5

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'

    db = SQLAlchemy(app)
    migrate = Migrate(app, db)

    class Station(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(128))
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

    updaters = {"nr_stations_update": {"func": update_nr_stations, "limit": timedelta(days=1)},
    "update_tfl_stations": {"func": update_tfl_stations, "limit": timedelta(days=1)}}

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
            

        yourTimer = threading.Timer(POOL_TIME, doStuff, ())
        yourTimer.start()   

    if "db" not in sys.argv:
        doStuff()
    atexit.register(interrupt)
    return {"app": app, "Updates": Updates, "Station": Station}

data = create_app()
app = data["app"]
for k in data:
    locals()[k] = data[k]

@app.route("/")
def hello_world():
    return "<p>Helo, Worl!</p>"
