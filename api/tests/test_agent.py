"""Test rapide de l'agent (rules.py + engine.py) sur une base SQLite en memoire.
Ne couvre que le cas brute-force (creation d'alerte + verrouillage automatique du
compte) : suffisant pour valider le cablage bout-en-bout, pas une suite complete."""
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest

from app import constants as C
from app import database
from app.agent.engine import scan
from app.models import Alert, Event, User


@pytest.fixture()
def db():
    database.Base.metadata.create_all(bind=database.engine)
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        database.Base.metadata.drop_all(bind=database.engine)


def test_brute_force_creates_alert_and_locks_account(db):
    user = User(username="agent1", hashed_password="x", role=C.ROLE_AGENT)
    db.add(user)
    db.commit()

    now = datetime.now(timezone.utc)
    for i in range(C.BRUTE_FORCE_THRESHOLD):
        db.add(Event(
            timestamp=now - timedelta(seconds=i),
            actor_id=user.id, actor_username=user.username, role=user.role,
            action="login", result=C.RESULT_FAILURE,
            channel_ip="10.0.0.1",
            detail={"username": user.username},
        ))
    db.commit()

    alerts = scan(db)

    brute = [a for a in alerts if a.rule_name == "brute_force"]
    assert len(brute) == 1, alerts
    assert brute[0].actor_username == user.username
    assert brute[0].severity == C.SEVERITY_CRITICAL
    assert brute[0].auto_action == C.AUTO_ACTION_LOCK
    assert brute[0].status == C.ALERT_OPEN

    db.refresh(user)
    assert user.locked == 1

    assert db.query(Alert).filter(Alert.rule_name == "brute_force").count() == 1

    agent_events = db.query(Event).filter(Event.action == "agent_alert").count()
    assert agent_events == 1

    # un second scan ne doit pas redoubler l'alerte (deja ouverte pour ce sujet)
    scan(db)
    assert db.query(Alert).filter(Alert.rule_name == "brute_force").count() == 1


def test_brute_force_counts_denied_after_native_lockout(db):
    """Scenario reel : le verrouillage natif (MAX_FAILED_ATTEMPTS=3) verrouille le
    compte avant que BRUTE_FORCE_THRESHOLD (5) ne soit atteint en pur RESULT_FAILURE.
    Les tentatives suivantes, faites une fois le compte verrouille, sont journalisees
    en RESULT_DENIED (auth.py verifie le verrouillage avant le mot de passe) et
    doivent quand meme compter pour R1."""
    user = User(username="agent2", hashed_password="x", role=C.ROLE_AGENT)
    db.add(user)
    db.commit()

    now = datetime.now(timezone.utc)
    offset = 0

    for _ in range(C.MAX_FAILED_ATTEMPTS):
        db.add(Event(
            timestamp=now - timedelta(seconds=offset),
            actor_id=user.id, actor_username=user.username, role=user.role,
            action="login", result=C.RESULT_FAILURE,
            channel_ip="10.0.0.2",
            detail={"username": user.username},
        ))
        offset += 1
    user.locked = 1
    db.commit()

    for _ in range(2):
        db.add(Event(
            timestamp=now - timedelta(seconds=offset),
            actor_id=user.id, actor_username=user.username, role=user.role,
            action="login", result=C.RESULT_DENIED,
            channel_ip="10.0.0.2",
            resource_type="account", resource_id=user.id,
        ))
        offset += 1
    db.commit()

    alerts = scan(db)

    brute = [a for a in alerts if a.rule_name == "brute_force"]
    assert len(brute) == 1, alerts
    assert brute[0].actor_username == user.username
