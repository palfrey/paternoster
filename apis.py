from datetime import datetime, time, timedelta
import os
from typing import Dict, Generator, List
import uuid
from typing_extensions import TypedDict
import requests

try:
    from hashdict import hashdict
except ImportError:
    from .hashdict import hashdict
from defusedxml.ElementTree import fromstring

NRW_API_KEY = os.environ["NRW_API_KEY"]


def reduce_name(name: str) -> str:
    return (
        name.replace(" Station", "")
        .replace(" Stn", "")
        .replace(" Rail", "")
        .replace(" Underground", "")
        .replace(" (London)", "")
    )


class LiftInfo(TypedDict):
    location: str
    status: str
    station_id: str


class NRStationsAndLifts(TypedDict):
    stations: dict[str, str]
    lifts: dict[str, LiftInfo]


def nr_stations_and_lifts() -> NRStationsAndLifts:
    res = requests.get(
        "https://api1.raildata.org.uk/1033-stations-experience-api---lifts-and-escalatorsv1_0/stations/all/lifts-and-escalators",
        headers={"x-apikey": NRW_API_KEY, "User-Agent": "paternoster/1.0"},
    )
    if res.status_code != 200:
        print("Issue with NR API (lifts)", res.status_code, res.text)
        return {"stations": {}, "lifts": {}}

    stations: dict[str, str] = {}
    lifts: dict[str, LiftInfo] = {}

    for lift in res.json()["data"]["resultSet"]:
        if lift.get("type") != "Lift":
            continue
        station = lift["station"]
        if station["id"] not in stations:
            stations[station["id"]] = reduce_name(station["name"])

        try:
            lift_id = lift.get("uprn", lift.get("blockId"))
            location = lift.get("alternateName", lift.get("blockTitle"))
            status = lift.get("status", lift.get("operationalStatus"))
            liftinfo: LiftInfo = {"location": location, "station_id": station["id"], "status": status}
        except KeyError:
            print("Bad lift", lift)
            raise
        assert lift_id is not None, lift
        lifts[lift_id] = liftinfo

    return {"stations": stations, "lifts": lifts}


def tflapi_lift_issues():
    res = requests.get(
        "https://api.tfl.gov.uk/StopPoint/Mode/tube,dlr,national-rail,overground,elizabeth-line/Disruption"
    )
    if res.status_code != 200:
        print("Issue with TfL API (lifts)", res.status_code, res.text)
        return
    for issue in res.json():
        if issue["description"].lower().find("lift") != -1:
            yield hashdict(
                {
                    "id": str(uuid.uuid4()),
                    "status": issue["description"].strip(),
                    "location": None,
                    "station": reduce_name(issue["commonName"]),
                }
            )


def tflapi_lift_disruptions():
    res = requests.get("https://api.tfl.gov.uk/Disruptions/Lifts/")
    if res.status_code != 200:
        print("Issue with TfL API (lift disruptions)", res.status_code, res.text)
        return
    for issue in res.json():
        yield hashdict(
            {
                "status": issue["message"].strip(),
                "location": None,
                "station": reduce_name(issue["stopPointName"]),
            }
        )


def tfl_stations():
    page = 1
    stations = []
    while True:
        print(f"page {page}")
        res = requests.get(
            f"https://api.tfl.gov.uk/StopPoint/Mode/tube%2Cdlr%2Coverground%2Celizabeth-line?page={page}"
        )
        if res.status_code != 200:
            print("Issue with TfL API (stations)", res.status_code, res.text)
            break
        data = res.json()
        stations += [(stopPoint["id"], reduce_name(stopPoint["commonName"])) for stopPoint in data["stopPoints"]]
        if len(stations) == data["total"]:
            break
        page += 1
    return dict(stations)


def trackernet_issues():
    res = requests.get("http://cloud.tfl.gov.uk/TrackerNet/StationStatus/IncidentsOnly")
    if res.status_code != 200:
        print("Issue with TfL API (trackernet)", res.status_code, res.text)
        return
    res.encoding = "utf-8-sig"
    data = fromstring(res.text)
    for stationstatus in data.iter(tag="{http://webservices.lul.co.uk/}StationStatus"):
        status_element = stationstatus.find("{http://webservices.lul.co.uk/}Status")
        status = status_element.get("Description")
        if status in ["Closed", "Part Closed"]:
            continue
        station_element = stationstatus.find("{http://webservices.lul.co.uk/}Station")
        yield {
            "station": reduce_name(station_element.get("Name")),
            "status": status,
            "location": None,
        }
