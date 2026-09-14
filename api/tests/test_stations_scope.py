"""Tests HTTP du controle de perimetre par unite sur POST /stations et
PATCH /stations/{id} (routers/stations.py) : un responsable ne doit pouvoir
ni creer une station sous une unite hors de son perimetre, ni modifier une
station hors de son perimetre, ni deplacer une station qu'il possede vers une
unite hors de son perimetre. Meme pattern TestClient que
tests/test_readings_scope.py."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
    database.Base.metadata.drop_all(bind=database.engine)


def _login(client, username, password):
    resp = client.post("/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _unite_id(client, headers, nom):
    resp = client.get("/unites", headers=headers)
    assert resp.status_code == 200, resp.text
    matches = [u for u in resp.json() if u["nom"] == nom]
    assert matches, resp.text
    return matches[0]["id"]


def _station_id(client, headers, code):
    resp = client.get("/stations", headers=headers, params={"code": code})
    assert resp.status_code == 200, resp.text
    stations = [s for s in resp.json() if s["code"] == code]
    assert stations, resp.text
    return stations[0]


def _station_payload(unite_id, name, code):
    return {
        "name": name, "code": code, "type": "conventionnelle",
        "parameter": "pluviometrie", "unit": "mm", "unite_id": unite_id,
        "latitude": 36.8, "longitude": 10.2,
    }


def test_create_station_rejects_unite_outside_scope(client):
    walid_headers = _auth_headers(_login(client, "walid", "walid123"))
    reseaux_unite_id = _unite_id(client, walid_headers, "Service Réseaux de mesure")

    resp = client.post("/stations", headers=walid_headers,
                       json=_station_payload(reseaux_unite_id, "Station Test 1", "TST-001"))
    assert resp.status_code == 403, resp.text


def test_create_station_allows_own_unite(client):
    walid_headers = _auth_headers(_login(client, "walid", "walid123"))
    etudes_unite_id = _unite_id(client, walid_headers, "Service Études")

    resp = client.post("/stations", headers=walid_headers,
                       json=_station_payload(etudes_unite_id, "Station Test 2", "TST-002"))
    assert resp.status_code == 201, resp.text


def test_update_station_rejects_outside_scope(client):
    dir_headers = _auth_headers(_login(client, "dir_surface", "dir_surface123"))
    station = _station_id(client, dir_headers, "PLV-003")

    walid_headers = _auth_headers(_login(client, "walid", "walid123"))
    resp = client.patch(f"/stations/{station['id']}", headers=walid_headers,
                        json={"governorate": "Ariana"})
    assert resp.status_code == 403, resp.text

    reread = _station_id(client, dir_headers, "PLV-003")
    assert reread["governorate"] == station["governorate"]


def test_update_station_allows_own_scope(client):
    dir_headers = _auth_headers(_login(client, "dir_surface", "dir_surface123"))
    station = _station_id(client, dir_headers, "PLV-003")

    resp = client.patch(f"/stations/{station['id']}", headers=dir_headers,
                        json={"governorate": "Ariana"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["governorate"] == "Ariana"


def test_update_station_rejects_moving_outside_scope(client):
    walid_headers = _auth_headers(_login(client, "walid", "walid123"))
    etudes_unite_id = _unite_id(client, walid_headers, "Service Études")
    reseaux_unite_id = _unite_id(client, walid_headers, "Service Réseaux de mesure")

    resp = client.post("/stations", headers=walid_headers,
                       json=_station_payload(etudes_unite_id, "Station Test 3", "TST-003"))
    assert resp.status_code == 201, resp.text
    station_id = resp.json()["id"]

    resp = client.patch(f"/stations/{station_id}", headers=walid_headers,
                        json={"unite_id": reseaux_unite_id})
    assert resp.status_code == 403, resp.text

    resp = client.get("/stations", headers=walid_headers, params={"code": "TST-003"})
    assert resp.status_code == 200, resp.text
    reread = next(s for s in resp.json() if s["code"] == "TST-003")
    assert reread["unite_id"] == etudes_unite_id
