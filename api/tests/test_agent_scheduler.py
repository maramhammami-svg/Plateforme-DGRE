"""Tests du scan automatique (agent/scheduler.py) et de GET /agent/status."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.agent import scheduler


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
    database.Base.metadata.drop_all(bind=database.engine)


def _headers(client, username, password):
    resp = client.post("/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_scheduler_not_started_in_tests(client):
    assert scheduler.get_state()["running"] is False


def test_run_once_updates_state(client):
    before = scheduler.get_state()["scan_count"]
    n = scheduler.run_once()
    state = scheduler.get_state()
    assert isinstance(n, int)
    assert state["scan_count"] == before + 1
    assert state["last_scan_at"] is not None
    assert state["last_error"] is None


def test_start_is_idempotent_and_stop(client):
    scheduler.start(interval=3600)
    scheduler.start(interval=3600)
    assert scheduler.get_state()["running"] is True
    scheduler.stop()
    assert scheduler.get_state()["running"] is False


def test_status_visible_to_responsable_not_observateur(client):
    resp = client.get("/agent/status", headers=_headers(client, "najla", "najla123"))
    assert resp.status_code == 200, resp.text
    assert {"running", "interval_sec", "last_scan_at", "scan_count",
            "open_alerts"} <= resp.json().keys()
    resp = client.get("/agent/status",
                      headers=_headers(client, "obs_jendouba", "obs_jendouba123"))
    assert resp.status_code == 403
