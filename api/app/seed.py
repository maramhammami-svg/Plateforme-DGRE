from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import User, Station, UniteOrganisationnelle
from .security import hash_password
from . import constants as C


def _get_or_create_unite(db: Session, nom: str, type_: str, parent_id=None):
    u = db.query(UniteOrganisationnelle).filter_by(nom=nom).first()
    if not u:
        u = UniteOrganisationnelle(nom=nom, type=type_, parent_id=parent_id)
        db.add(u)
        db.flush()
    return u


def _get_or_create_user(db: Session, username: str, full_name: str, role: str,
                        unite_id=None, superviseur_id=None):
    u = db.query(User).filter_by(username=username).first()
    if not u:
        u = User(
            username=username,
            full_name=full_name,
            hashed_password=hash_password(username + "123"),
            role=role,
            unite_id=unite_id,
            superviseur_id=superviseur_id,
        )
        db.add(u)
        db.flush()
    return u


def seed():
    db: Session = SessionLocal()
    try:
        # ── ÉTAPE 1 : Organigramme ──────────────────────────────────────────

        # 1a – Direction
        dir_gen = _get_or_create_unite(db, "Direction Générale", C.UNITE_DIRECTION)

        # 1b – Départements (parent = Direction Générale)
        dept_surface = _get_or_create_unite(db, "Eaux de Surface",            C.UNITE_DEPARTEMENT, dir_gen.id)
        dept_soutr   = _get_or_create_unite(db, "Eaux Souterraines",          C.UNITE_DEPARTEMENT, dir_gen.id)
        dept_nconv   = _get_or_create_unite(db, "Eaux Non-Conventionnelles",  C.UNITE_DEPARTEMENT, dir_gen.id)

        # 1c – Services (parent = Eaux de Surface)
        svc_reseaux = _get_or_create_unite(db, "Service Réseaux de mesure",             C.UNITE_SERVICE, dept_surface.id)
        svc_etudes  = _get_or_create_unite(db, "Service Études",                         C.UNITE_SERVICE, dept_surface.id)
        svc_crues   = _get_or_create_unite(db, "Service Alerte crues",                   C.UNITE_SERVICE, dept_surface.id)
        svc_hydro   = _get_or_create_unite(db, "Service Hydrologie analytique et bases", C.UNITE_SERVICE, dept_surface.id)

        # ── ÉTAPE 2 : Utilisateurs ──────────────────────────────────────────

        # 2a – Admin (sans unité) + DG
        _get_or_create_user(db, "admin", "Administrateur", C.ROLE_ADMIN)
        dg = _get_or_create_user(db, "dg", "Aissa Halimi", C.ROLE_DIRECTEUR,
                                 unite_id=dir_gen.id)

        # 2b – Directeurs de département (superviseur = dg)
        dir_surface = _get_or_create_user(db, "dir_surface", "Alaeddine Jallassi", C.ROLE_RESPONSABLE,
                                          unite_id=dept_surface.id, superviseur_id=dg.id)
        dir_soutr   = _get_or_create_user(db, "dir_soutr",   "Faouzi Ammari",      C.ROLE_RESPONSABLE,
                                          unite_id=dept_soutr.id,   superviseur_id=dg.id)
        dir_nconv   = _get_or_create_user(db, "dir_nconv",   "Tayba Haki",         C.ROLE_RESPONSABLE,
                                          unite_id=dept_nconv.id,   superviseur_id=dg.id)

        # 2c – Subordonnés
        for username, full_name, role, unite_id, sup_id in [
            # Eaux de Surface
            ("najla",        "Najla Khalfoun",       C.ROLE_RESPONSABLE,  svc_hydro.id,   dir_surface.id),
            ("walid",        "Walid Ben Khalifa",    C.ROLE_RESPONSABLE,  svc_etudes.id,  dir_surface.id),
            ("yosra",        "Yosra Khmira",         C.ROLE_RESPONSABLE,  svc_etudes.id,  dir_surface.id),
            ("zohair",       "Zohair Gharbi",        C.ROLE_RESPONSABLE,  svc_crues.id,   dir_surface.id),
            ("aymen",        "Aymen Nafzi",          C.ROLE_AGENT,        svc_reseaux.id, dir_surface.id),
            ("jilani",       "Jilani Dhifli",        C.ROLE_AGENT,        svc_reseaux.id, dir_surface.id),
            ("ammar",        "Ammar Mannai",         C.ROLE_AGENT,        svc_reseaux.id, dir_surface.id),
            ("hanen",        "Hanen Friji",          C.ROLE_AGENT,        svc_reseaux.id, dir_surface.id),
            ("obs_jendouba", "Observateur Jendouba", C.ROLE_OBSERVATEUR,  svc_reseaux.id, dir_surface.id),
            # Eaux Souterraines
            ("khoula",       "Khoula Ben Slim",      C.ROLE_RESPONSABLE,  dept_soutr.id,  dir_soutr.id),
            ("rim",          "Rim Matoussi",         C.ROLE_RESPONSABLE,  dept_soutr.id,  dir_soutr.id),
            ("abir",         "Abir Blali",           C.ROLE_RESPONSABLE,  dept_soutr.id,  dir_soutr.id),
            # Eaux Non-Conventionnelles
            ("hedia",        "Hedia Fadhili",        C.ROLE_RESPONSABLE,  dept_nconv.id,  dir_nconv.id),
            ("nadia",        "Nadia Mastouri",       C.ROLE_ANALYSTE,     dept_nconv.id,  dir_nconv.id),
        ]:
            _get_or_create_user(db, username, full_name, role,
                                unite_id=unite_id, superviseur_id=sup_id)

        # ── ÉTAPE 3 : Stations pluviométriques existantes (rattrapage) ──────
        # Si ST-001/ST-002/ST-003 existent deja en base (anciennes versions
        # du seed), on complete leur gouvernorat sans les recreer.
        for code, governorate in [("ST-001", "Bizerte"), ("ST-002", "Béja"), ("ST-003", "Jendouba")]:
            st = db.query(Station).filter_by(code=code).first()
            if st and not st.governorate:
                st.governorate = governorate

        # ── ÉTAPE 4 : Stations pluviométriques réelles ──────────────────────
        for st_data in [
            {"code": "PLV-001", "name": "Tunis Carthage",       "governorate": "Tunis",
             "latitude": 36.8500, "longitude": 10.2333, "altitude_m": 4.0,
             "type": C.STATION_TYPE_AUTO, "sampling_interval_min": 15,
             "sensor_status": "operational", "battery_level": 0.92, "last_transmission_hours_ago": 1.5},
            {"code": "PLV-002", "name": "Bizerte Ville",         "governorate": "Bizerte",
             "latitude": 37.2744, "longitude": 9.8739, "altitude_m": 5.0,
             "type": C.STATION_TYPE_AUTO, "sampling_interval_min": 15,
             "sensor_status": "operational", "battery_level": 0.85, "last_transmission_hours_ago": 2.0},
            {"code": "PLV-003", "name": "Béja Nord",             "governorate": "Béja",
             "latitude": 36.7256, "longitude": 9.1817, "altitude_m": 168.0,
             "type": C.STATION_TYPE_CONV, "sampling_interval_min": None},
            {"code": "PLV-004", "name": "Jendouba Centre",       "governorate": "Jendouba",
             "latitude": 36.5011, "longitude": 8.7803, "altitude_m": 143.0,
             "type": C.STATION_TYPE_CONV, "sampling_interval_min": None},
            {"code": "PLV-005", "name": "Le Kef Ville",          "governorate": "Le Kef",
             "latitude": 36.1742, "longitude": 8.7048, "altitude_m": 516.0,
             "type": C.STATION_TYPE_CONV, "sampling_interval_min": None},
            {"code": "PLV-006", "name": "Siliana Barrage",       "governorate": "Siliana",
             "latitude": 36.0844, "longitude": 9.3708, "altitude_m": 380.0,
             "type": C.STATION_TYPE_AUTO, "sampling_interval_min": 30,
             "sensor_status": "degraded", "battery_level": 0.15, "last_transmission_hours_ago": 36.0},
            {"code": "PLV-007", "name": "Nabeul Ville",          "governorate": "Nabeul",
             "latitude": 36.4561, "longitude": 10.7376, "altitude_m": 5.0,
             "type": C.STATION_TYPE_AUTO, "sampling_interval_min": 15,
             "sensor_status": "operational", "battery_level": 0.78, "last_transmission_hours_ago": 0.5},
            {"code": "PLV-008", "name": "Zaghouan Centre",       "governorate": "Zaghouan",
             "latitude": 36.4028, "longitude": 10.1425, "altitude_m": 225.0,
             "type": C.STATION_TYPE_CONV, "sampling_interval_min": None},
            {"code": "PLV-009", "name": "Sousse Ville",          "governorate": "Sousse",
             "latitude": 35.8256, "longitude": 10.6369, "altitude_m": 11.0,
             "type": C.STATION_TYPE_AUTO, "sampling_interval_min": 15,
             "sensor_status": "operational", "battery_level": 0.88, "last_transmission_hours_ago": 3.0},
            {"code": "PLV-010", "name": "Kairouan Centre",       "governorate": "Kairouan",
             "latitude": 35.6781, "longitude": 10.0963, "altitude_m": 65.0,
             "type": C.STATION_TYPE_AUTO, "sampling_interval_min": 30,
             "sensor_status": "degraded", "battery_level": 0.22, "last_transmission_hours_ago": 48.0},
            {"code": "PLV-011", "name": "Sfax Ville",            "governorate": "Sfax",
             "latitude": 34.7398, "longitude": 10.7600, "altitude_m": 3.0,
             "type": C.STATION_TYPE_AUTO, "sampling_interval_min": 15,
             "sensor_status": "operational", "battery_level": 0.95, "last_transmission_hours_ago": 4.0},
            {"code": "PLV-012", "name": "Kasserine Centre",      "governorate": "Kasserine",
             "latitude": 35.1676, "longitude": 8.8365, "altitude_m": 683.0,
             "type": C.STATION_TYPE_CONV, "sampling_interval_min": None},
            {"code": "PLV-013", "name": "Gabès Ville",           "governorate": "Gabès",
             "latitude": 33.8815, "longitude": 10.0982, "altitude_m": 7.0,
             "type": C.STATION_TYPE_AUTO, "sampling_interval_min": 15,
             "sensor_status": "offline", "battery_level": 0.0},
            {"code": "PLV-014", "name": "Médenine Centre",       "governorate": "Médenine",
             "latitude": 33.3549, "longitude": 10.5055, "altitude_m": 108.0,
             "type": C.STATION_TYPE_CONV, "sampling_interval_min": None},
            {"code": "PLV-015", "name": "Tozeur Oasis",          "governorate": "Tozeur",
             "latitude": 33.9197, "longitude": 8.1335, "altitude_m": 43.0,
             "type": C.STATION_TYPE_AUTO, "sampling_interval_min": 30,
             "sensor_status": "operational", "battery_level": 0.65, "last_transmission_hours_ago": 6.0},
            {"code": "PLV-016", "name": "Menzel Bourguiba",      "governorate": "Bizerte",
             "latitude": 37.1553, "longitude": 9.7883, "altitude_m": 4.0,
             "type": C.STATION_TYPE_CONV, "sampling_interval_min": None},
            {"code": "PLV-017", "name": "Testour",               "governorate": "Béja",
             "latitude": 36.5497, "longitude": 9.4433, "altitude_m": 105.0,
             "type": C.STATION_TYPE_CONV, "sampling_interval_min": None},
            {"code": "PLV-018", "name": "Fernana",               "governorate": "Jendouba",
             "latitude": 36.6647, "longitude": 8.6947, "altitude_m": 260.0,
             "type": C.STATION_TYPE_CONV, "sampling_interval_min": None},
        ]:
            hours_ago = st_data.get("last_transmission_hours_ago")
            last_transmission = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)
                                  if hours_ago is not None else None)
            st = db.query(Station).filter_by(code=st_data["code"]).first()
            if not st:
                st = Station(
                    code=st_data["code"], name=st_data["name"],
                    type=st_data["type"], parameter=C.PARAM_PLUVIO, unit=C.UNIT_MM,
                    sampling_interval_min=st_data["sampling_interval_min"],
                    latitude=st_data["latitude"], longitude=st_data["longitude"],
                    altitude_m=st_data["altitude_m"], governorate=st_data["governorate"],
                    unite_id=svc_reseaux.id,
                    sensor_status=st_data.get("sensor_status", "unknown"),
                    battery_level=st_data.get("battery_level"),
                    last_transmission=last_transmission,
                )
                db.add(st)
            else:
                if not st.governorate:
                    st.governorate = st_data["governorate"]
                if st.sensor_status in (None, "unknown") and "sensor_status" in st_data:
                    st.sensor_status = st_data["sensor_status"]
                    st.battery_level = st_data["battery_level"]

        db.commit()
    finally:
        db.close()
