"""Tests HTTP du router alerts (routers/alerts.py) : scan sans donnee suspecte,
listing/stats vides, et controle d'acces par role. Complementaire de
tests/test_agent.py qui couvre le moteur (rules.py + engine.py) directement."""
import os
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.models import Event

# Heure de jour fixe (UTC) : hors de la fenetre nocturne de NightAccessRule
# ([NIGHT_START_HOUR=22, NIGHT_END_HOUR=6[), pour que le scan sur une base "propre"
# soit deterministe quelle que soit l'heure reelle d'execution des tests.
_NOON_UTC = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


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


def _freeze_last_login_at_noon():
    """Le login passe par le vrai endpoint HTTP : Event.timestamp est pose par
    server_default=func.now() (horloge reelle du moteur SQL), donc insensible a un
    monkeypatch de app.agent.rules._now. On corrige donc directement la valeur
    enregistree, sans toucher a NightAccessRule."""
    db = database.SessionLocal()
    try:
        ev = (db.query(Event).filter(Event.action == "login")
              .order_by(Event.id.desc()).first())
        ev.timestamp = _NOON_UTC
        db.commit()
    finally:
        db.close()


def test_scan_then_list_and_stats_empty(client, monkeypatch):
    monkeypatch.setattr("app.agent.rules._now", lambda: _NOON_UTC)
    headers = _auth_headers(_login(client, "admin", "admin123"))
    _freeze_last_login_at_noon()

    resp = client.post("/agent/scan", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"new_alerts": 0}

    resp = client.get("/alerts", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == []

    resp = client.get("/alerts/stats", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"by_severity": {}, "by_status": {}}


def test_list_alerts_forbidden_for_observateur(client):
    headers = _auth_headers(_login(client, "obs_jendouba", "obs_jendouba123"))
    resp = client.get("/alerts", headers=headers)
    assert resp.status_code == 403
