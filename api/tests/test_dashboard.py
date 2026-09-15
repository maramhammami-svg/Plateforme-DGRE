"""Test HTTP du router dashboard (routers/dashboard.py) : GET /dashboard/map
doit retomber sur l'annee hydro deduite des Reading existants quand la table
Consolidation est vide, plutot que sur 2024 en dur -- sinon la fenetre de
dates par defaut ne contient aucun releve reel et toutes les stations
affichent quality="inconnu" meme quand des relevés valides existent.
Meme pattern TestClient que tests/test_alerts_api.py."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.models import Reading
from app import constants as C


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


def test_map_uses_latest_reading_date_when_no_consolidation(client):
    headers = _auth_headers(_login(client, "aymen", "aymen123"))
    resp = client.get("/stations", headers=headers, params={"code": "PLV-003"})
    assert resp.status_code == 200, resp.text
    stations = [s for s in resp.json() if s["code"] == "PLV-003"]
    assert stations, resp.text
    station_id = stations[0]["id"]

    # aucune Consolidation en base : le releve du 2026-09-01 doit determiner
    # l'annee hydro par defaut (2026), pas 2024 en dur.
    db = database.SessionLocal()
    try:
        db.add(Reading(
            station_id=station_id, date="2026-09-01",
            parameter=C.PARAM_PLUVIO, valeur_recalculee=5.0,
            status=C.STATUS_VALIDATED, quality_flag=C.FLAG_OK,
            source=C.SOURCE_MANUAL,
        ))
        db.commit()
    finally:
        db.close()

    resp = client.get("/dashboard/map", headers=headers)
    assert resp.status_code == 200, resp.text
    marker = next(m for m in resp.json() if m["id"] == station_id)
    assert marker["quality"] == "ok"
