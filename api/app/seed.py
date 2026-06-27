from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import User, Station
from .security import hash_password
from . import constants as C

USERS = [
    ("admin",        "admin123",  "Administrateur",      C.ROLE_ADMIN),
    ("directeur1",   "dir123",    "Directeur National",  C.ROLE_DIRECTEUR),
    ("analyste1",    "ana123",    "Analyste Hydrologie", C.ROLE_ANALYSTE),
    ("responsable1", "resp123",   "Responsable Terrain", C.ROLE_RESPONSABLE),
    ("observateur1", "obs123",    "Observateur",         C.ROLE_OBSERVATEUR),
    ("agent1",       "agent123",  "Agent Saisie",        C.ROLE_AGENT),
]

STATIONS = [
    {
        "name": "Bizerte Pluvio Auto",
        "type": C.STATION_TYPE_AUTO,
        "parameter": C.PARAM_PLUVIO,
        "unit": C.UNIT_MM,
        "sampling_interval_min": 15,
        "latitude": 37.27,
        "longitude": 9.87,
        "altitude_m": 12.0,
        "governorate": "Bizerte",
    },
    {
        "name": "Beja Pluvio Auto",
        "type": C.STATION_TYPE_AUTO,
        "parameter": C.PARAM_PLUVIO,
        "unit": C.UNIT_MM,
        "sampling_interval_min": 15,
        "latitude": 36.73,
        "longitude": 9.18,
        "altitude_m": 150.0,
        "governorate": "Beja",
    },
    {
        "name": "Gabes Limni Auto",
        "type": C.STATION_TYPE_AUTO,
        "parameter": C.PARAM_LIMNI,
        "unit": C.UNIT_CM,
        "sampling_interval_min": 60,
        "latitude": 33.88,
        "longitude": 10.10,
        "altitude_m": 5.0,
        "governorate": "Gabes",
    },
    {
        "name": "Jendouba Pluvio Conv",
        "type": C.STATION_TYPE_CONV,
        "parameter": C.PARAM_PLUVIO,
        "unit": C.UNIT_MM,
        "sampling_interval_min": None,
        "latitude": 36.50,
        "longitude": 8.78,
        "altitude_m": 138.0,
        "governorate": "Jendouba",
    },
]


def seed():
    db: Session = SessionLocal()
    try:
        for username, pwd, full, role in USERS:
            if not db.query(User).filter(User.username == username).first():
                db.add(User(username=username, full_name=full,
                            hashed_password=hash_password(pwd),
                            role=role))
        for st_data in STATIONS:
            if not db.query(Station).filter(Station.name == st_data["name"]).first():
                db.add(Station(**st_data))
        db.commit()
    finally:
        db.close()
