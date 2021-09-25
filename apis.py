from typing import Dict, List
import requests
from .hashdict import hashdict
from defusedxml.ElementTree import fromstring


def nr_non_working_lifts() -> List[Dict]:
    ALL_STATIONS = """query {
portfolio(where: {status: {status: {_neq: "Available"}}, type: {_eq: "Lift"}}) {
   status {
     status
     engineerOnSite
     independant
     isolated
   }
   type
   location
   station
 }
}"""

    res = requests.post(
        "https://nr-lift-and-escalator.azure-api.net/gateway/v1/",
        json={"query": ALL_STATIONS},
    )
    res.raise_for_status()
    print(len(res.json()["data"]["portfolio"]))
    for lift in res.json()["data"]["portfolio"]:
        yield {
            "status": lift["status"]["status"],
            "location": lift["location"],
            "station": lift["station"],
        }


def nr_stations() -> List[str]:
    ALL_STATIONS = """query {
 status(distinct_on: [station]) {
   station
 }
}"""
    res = requests.post(
        "https://nr-lift-and-escalator.azure-api.net/gateway/v1/",
        json={"query": ALL_STATIONS},
    )
    res.raise_for_status()
    return [station["station"] for station in res.json()["data"]["status"] if station["station"] not in ["#N/A", None]]


def tflapi_lift_issues():
    res = requests.get("https://api.tfl.gov.uk/StopPoint/Mode/tube,dlr,national-rail,overground,tflrail/Disruption")
    res.raise_for_status()
    for issue in res.json():
        if issue["description"].lower().find("lift") != -1:
            yield hashdict(
                {
                    "status": issue["description"].strip(),
                    "location": None,
                    "station": issue["commonName"].replace(" Station", ""),
                }
            )


def tflapi_lift_disruptions():
    res = requests.get("https://api.tfl.gov.uk/Disruptions/Lifts/")
    res.raise_for_status()
    for issue in res.json():
        yield hashdict(
            {
                "status": issue["message"].strip(),
                "location": None,
                "station": issue["stopPointName"].replace(" Station", ""),
            }
        )


def tfl_stations():
    page = 1
    stations = []
    while True:
        print(f"page {page}")
        resp = requests.get(f"https://api.tfl.gov.uk/StopPoint/Mode/tube%2Cdlr%2Coverground%2Ctflrail?page={page}")
        resp.raise_for_status()
        data = resp.json()
        stations += [stopPoint["commonName"].replace(" Station", "") for stopPoint in data["stopPoints"]]
        if len(stations) == data["total"]:
            break
        page += 1
    return set(stations)


def trackernet_issues():
    resp = requests.get("http://cloud.tfl.gov.uk/TrackerNet/StationStatus/IncidentsOnly")
    resp.raise_for_status()
    resp.encoding = "utf-8-sig"
    data = fromstring(resp.text)
    for stationstatus in data.iter(tag="{http://webservices.lul.co.uk/}StationStatus"):
        status_element = stationstatus.find("{http://webservices.lul.co.uk/}Status")
        status = status_element.get("Description")
        if status in ["Closed", "Part Closed"]:
            continue
        station_element = stationstatus.find("{http://webservices.lul.co.uk/}Station")
        yield {
            "station": station_element.get("Name"),
            "status": status,
            "location": None,
        }
