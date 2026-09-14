"""Tests HTTP du controle d'acces (scoped_station_ids) sur
GET /readings/{id}/versions (routers/readings.py) : un responsable d'un autre
service ne doit pas pouvoir consulter l'historique d'un releve hors de son
perimetre en devinant son id, alors que le responsable du bon departement le
peut. Meme pattern TestClient que tests/test_alerts_api.py."""
import os
from datetime import date

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


def test_correct_reading_rejects_implausible_value(client):
    # aymen (agent, Service Reseaux de mesure) cree un releve valide sur une
    # station conventionnelle de son perimetre.
    aymen_headers = _auth_headers(_login(client, "aymen", "aymen123"))
    resp = client.get("/stations", headers=aymen_headers, params={"code": "PLV-003"})
    assert resp.status_code == 200, resp.text
    stations = [s for s in resp.json() if s["code"] == "PLV-003"]
    assert stations, resp.text
    station_id = stations[0]["id"]

    resp = client.post("/readings", headers=aymen_headers,
                       json={"station_id": station_id, "date": date.today().isoformat(),
                             "valeur": 5.0})
    assert resp.status_code == 201, resp.text
    reading_id = resp.json()["id"]

    # correction avec une valeur au-dela de PLAUSIBLE_MAX_MM : doit etre
    # rejetee (422) et ne rien modifier en base.
    resp = client.patch(f"/readings/{reading_id}", headers=aymen_headers,
                        json={"valeur_recalculee": 351.0})
    assert resp.status_code == 422, resp.text

    resp = client.get("/readings", headers=aymen_headers, params={"station_id": station_id})
    assert resp.status_code == 200, resp.text
    reading = next(r for r in resp.json() if r["id"] == reading_id)
    assert reading["valeur_recalculee"] == 5.0
    assert reading["status"] == "pending"


def test_reading_versions_scoped_to_own_perimeter(client):
    # aymen (agent, Service Reseaux de mesure) cree un releve sur une station
    # conventionnelle de son perimetre.
    aymen_headers = _auth_headers(_login(client, "aymen", "aymen123"))
    resp = client.get("/stations", headers=aymen_headers, params={"code": "PLV-003"})
    assert resp.status_code == 200, resp.text
    stations = [s for s in resp.json() if s["code"] == "PLV-003"]
    assert stations, resp.text
    station_id = stations[0]["id"]

    resp = client.post("/readings", headers=aymen_headers,
                       json={"station_id": station_id, "date": date.today().isoformat(),
                             "valeur": 5.0})
    assert resp.status_code == 201, resp.text
    reading_id = resp.json()["id"]

    # walid (responsable, Service Etudes -- meme departement, autre service) : hors
    # perimetre, doit etre rejete.
    walid_headers = _auth_headers(_login(client, "walid", "walid123"))
    resp = client.get(f"/readings/{reading_id}/versions", headers=walid_headers)
    assert resp.status_code == 403, resp.text

    # dir_surface (responsable du departement Eaux de Surface, parent des deux
    # services) : dans son perimetre, doit passer.
    dir_headers = _auth_headers(_login(client, "dir_surface", "dir_surface123"))
    resp = client.get(f"/readings/{reading_id}/versions", headers=dir_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
