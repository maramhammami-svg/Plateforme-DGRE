from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import User, Station
from .security import hash_password
from . import constants as C

USERS = [
    ("admin",      "admin123", "Administrateur",   C.ROLE_ADMIN,       "National"),
    ("resp_nord",  "resp123",  "Responsable Nord", C.ROLE_RESPONSABLE, "Nord"),
    ("agent_nord", "agent123", "Agent Nord",       C.ROLE_AGENT,       "Nord"),
    ("agent_sud",  "agent123", "Agent Sud",        C.ROLE_AGENT,       "Sud"),
]

STATIONS = [
    ("ST-001", "Station Bizerte",  "Nord", "Bizerte"),
    ("ST-002", "Station Beja",     "Nord", "Beja"),
    ("ST-003", "Station Gabes",    "Sud",  "Gabes"),
]


def seed():
    db: Session = SessionLocal()
    try:
        for username, pwd, full, role, region in USERS:
            if not db.query(User).filter(User.username == username).first():
                db.add(User(username=username, full_name=full,
                            hashed_password=hash_password(pwd),
                            role=role, region=region))
        for code, name, region, gov in STATIONS:
            if not db.query(Station).filter(Station.code == code).first():
                db.add(Station(code=code, name=name, region=region, governorate=gov))
        db.commit()
    finally:
        db.close()
