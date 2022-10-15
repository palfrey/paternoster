from email.mime import base
import requests

base_url = "http://paternoster:5000"


def test_root():
    resp = requests.get(base_url)
    assert resp.status_code == 200, resp.content
    assert resp.text.find("Select station") != -1, resp.text


def test_get_stations():
    resp = requests.get(f"{base_url}/getstations?term=Victoria")
    assert resp.status_code == 200, resp.content
    assert resp.json() == [
        {"id": "Manchester Victoria", "label": "Manchester Victoria", "value": "Manchester Victoria"},
        {"id": "Royal Victoria", "label": "Royal Victoria", "value": "Royal Victoria"},
        {"id": "Royal Victoria DLR", "label": "Royal Victoria DLR", "value": "Royal Victoria DLR"},
        {"id": "Victoria", "label": "Victoria", "value": "Victoria"},
    ]


def test_get_lifts():
    resp = requests.get(f"{base_url}/getlifts?station=Victoria")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert sorted([lift["location"] for lift in data]) == ["ISU/Admin Office"]
