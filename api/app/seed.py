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

        db.commit()
    finally:
        db.close()
