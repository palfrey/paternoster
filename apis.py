from datetime import datetime, time, timedelta
import os
from typing import Dict, Generator, List
import requests

try:
    from hashdict import hashdict
except ImportError:
    from .hashdict import hashdict
from defusedxml.ElementTree import fromstring

PRIMARY_KEY = os.environ["PRIMARY_KEY"]


def reduce_name(name: str) -> str:
    return name.replace(" Station", "").replace(" Rail", "").replace(" Underground", "")


_expiry_time = None
_nr_token = None


def nr_get_token():
    global _expiry_time, _nr_token
    if _expiry_time is None or _expiry_time < datetime.now():
        res = requests.post(
            "https://nr-lift-and-escalator.azure-api.net/auth/token/", headers={"x-lne-api-key": PRIMARY_KEY}
        )
        res.raise_for_status()
        _nr_token = res.json()["access_token"]
        _expiry_time = timedelta(seconds=res.json()["expires_in"] / 2) + datetime.now()
    return _nr_token


def nr_non_working_lifts() -> Generator[Dict, None, None]:
    ALL_STATIONS = """query {
assets(where: {status: {status: {_neq: "Available"}}, type: {_eq: "Lift"}}) {
   status {
     status
     engineerOnSite
     independent
     isolated
   }
   type
   location
   id
 }
}"""

    token = nr_get_token()
    res = requests.post(
        "https://nr-lift-and-escalator.azure-api.net/gateway/v2/",
        headers={"x-lne-api-key": PRIMARY_KEY, "Authorization": f"Bearer {token}"},
        json={"query": ALL_STATIONS},
    )
    if res.status_code != 200:
        print("Issue with NR API (stations)", res.status_code, res.text)
        return
    for lift in res.json()["data"]["assets"]:
        yield {
            "status": lift["status"]["status"],
            "location": lift["location"],
            "id": int(lift["id"]),
        }


def nr_stations() -> dict[str, List[int]]:
    ALL_STATIONS = """query {
 stations {
   name
   assets {
       id
   }
 }
}"""
    token = nr_get_token()
    res = requests.post(
        "https://nr-lift-and-escalator.azure-api.net/graphql/v2/",
        headers={"x-lne-api-key": PRIMARY_KEY, "Authorization": f"Bearer {token}"},
        json={"query": ALL_STATIONS},
    )
    if res.status_code != 200:
        print("Issue with NR API (lifts)", res.status_code, res.text)
        return
    return dict(
        [
            (reduce_name(station["name"]), [int(asset["id"]) for asset in station["assets"]])
            for station in res.json()["data"]["stations"]
            if station["name"] not in ["#N/A", None]
        ]
    )


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
        stations += [reduce_name(stopPoint["commonName"]) for stopPoint in data["stopPoints"]]
        if len(stations) == data["total"]:
            break
        page += 1
    return set(stations)


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
