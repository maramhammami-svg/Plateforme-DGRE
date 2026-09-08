"""Tests du chainage de hash sur la table `events` (events.py::log_event +
GET /events/verify-integrity) : une chaine intacte doit se verifier valide, et toute
alteration directe d'un champ (hors log_event, donc hors chainage) doit etre detectee
des le premier evenement touche."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.events import log_event
from app.models import Event


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


def test_verify_integrity_valid_chain(client):
    db = database.SessionLocal()
    try:
        for i in range(5):
            log_event(db, request=None, user=None, action=f"test_action_{i}", result="success")
    finally:
        db.close()

    headers = _auth_headers(_login(client, "admin", "admin123"))
    resp = client.get("/events/verify-integrity", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # 5 evenements semes + l'evenement "login" emis par _login ci-dessus
    assert body == {"valid": True, "total": 6, "checked": 6}


def test_verify_integrity_detects_tampering(client):
    db = database.SessionLocal()
    try:
        for i in range(3):
            log_event(db, request=None, user=None, action=f"test_action_{i}", result="success")
    finally:
        db.close()

    headers = _auth_headers(_login(client, "admin", "admin123"))

    db = database.SessionLocal()
    try:
        target = db.query(Event).filter(Event.action == "test_action_1").first()
        broken_id = target.id
        # Alteration directe (hors log_event) : le chain_hash stocke ne correspond
        # plus au contenu, sans passer par la generation du hash.
        target.action = "test_action_tampered"
        db.commit()
    finally:
        db.close()

    resp = client.get("/events/verify-integrity", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is False
    assert body["broken_at"] == broken_id
    assert body["total"] == 4  # 3 semes + le login
    assert body["checked"] == broken_id  # arret a la premiere divergence


def test_verify_integrity_forbidden_for_non_admin(client):
    headers = _auth_headers(_login(client, "dir_surface", "dir_surface123"))
    resp = client.get("/events/verify-integrity", headers=headers)
    assert resp.status_code == 403
