from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Consolidation, Reading, Station, User
from ..events import log_event
from ..deps import get_current_user, scoped_station_ids, parse_iso_date_qs
from .. import constants as C
from ..schemas import DashboardSummary, StationCompleteness, StationMarker

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

MONTH_FIELDS = ["sept", "octo", "nove", "dece", "janv", "fevr",
                "mars", "avri", "mai", "juin", "juil", "aout"]

# Severite pour le pire flag qualite d'une station sur la fenetre (carte)
_SEVERITY = {C.FLAG_ABERRANT: 3, C.FLAG_SUSPECT: 2, C.FLAG_MANQUANT: 1, C.FLAG_OK: 0}


def _default_annee_hydro(db: Session) -> int:
    """Annee hydro la plus recente presente en consolidation, sinon 2024."""
    latest = db.query(func.max(Consolidation.annee_hydro)).scalar()
    return latest if latest is not None else 2024


def _hydro_window(annee_hydro: int) -> tuple[str, str]:
    return f"{annee_hydro}-09-01", f"{annee_hydro + 1}-08-31"


def _scoped_stations(db: Session, ids: list[int] | None, station_id: int | None):
    q = db.query(Station)
    if ids is not None:
        q = q.filter(Station.id.in_(ids))
    if station_id is not None:
        q = q.filter(Station.id == station_id)
    return q.order_by(Station.code).all()


def _completeness(db: Session, stations: list[Station], annee_hydro: int,
                   date_from: str, date_to: str) -> list[StationCompleteness]:
    if not stations:
        return []
    station_ids = [s.id for s in stations]

    cons_by_station = {
        c.station_id: c
        for c in db.query(Consolidation).filter(
            Consolidation.station_id.in_(station_ids),
            Consolidation.annee_hydro == annee_hydro,
        ).all()
    }

    dates_by_station: dict[int, set[str]] = {}
    for sid, d in (db.query(Reading.station_id, Reading.date)
                   .filter(Reading.station_id.in_(station_ids),
                           Reading.date >= date_from, Reading.date <= date_to)
                   .distinct().all()):
        dates_by_station.setdefault(sid, set()).add(d)

    window_days = (date.fromisoformat(date_to) - date.fromisoformat(date_from)).days + 1

    result = []
    for s in stations:
        cons = cons_by_station.get(s.id)
        completude_mensuelle = None
        if cons is not None:
            non_nuls = sum(1 for m in MONTH_FIELDS if getattr(cons, m) is not None)
            completude_mensuelle = non_nuls / 12
        nb_jours = len(dates_by_station.get(s.id, ()))
        completude_journaliere = nb_jours / window_days if window_days > 0 else 0.0
        result.append(StationCompleteness(
            station_id=s.id, code=s.code, name=s.name,
            completude_mensuelle=completude_mensuelle,
            completude_journaliere=completude_journaliere,
        ))
    return result


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(request: Request,
                      annee_hydro: int | None = None,
                      date_from: str | None = None,
                      date_to: str | None = None,
                      station_id: int | None = None,
                      status: str | None = None,
                      quality_flag: str | None = None,
                      db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    date_from = parse_iso_date_qs(date_from, "date_from")
    date_to = parse_iso_date_qs(date_to, "date_to")
    if status is not None and status not in C.STATUSES:
        raise HTTPException(422, "status invalide")
    if quality_flag is not None and quality_flag not in C.QUALITY_FLAGS:
        raise HTTPException(422, "quality_flag invalide")
    ids = scoped_station_ids(db, user)
    annee = annee_hydro if annee_hydro is not None else _default_annee_hydro(db)
    default_from, default_to = _hydro_window(annee)
    d_from = date_from or default_from
    d_to = date_to or default_to

    def _reading_query():
        q = db.query(Reading)
        if ids is not None:
            q = q.filter(Reading.station_id.in_(ids))
        if station_id is not None:
            q = q.filter(Reading.station_id == station_id)
        if status is not None:
            q = q.filter(Reading.status == status)
        if quality_flag is not None:
            q = q.filter(Reading.quality_flag == quality_flag)
        return q.filter(Reading.date >= d_from, Reading.date <= d_to)

    pending_count = _reading_query().filter(Reading.status == C.STATUS_PENDING).count()
    quality_anomalies = _reading_query().filter(
        Reading.quality_flag.in_([C.FLAG_SUSPECT, C.FLAG_ABERRANT, C.FLAG_MANQUANT])
    ).count()

    stations = _scoped_stations(db, ids, station_id)
    stations_active = sum(1 for s in stations if s.status == "active")
    stations_inactive = len(stations) - stations_active

    completeness = _completeness(db, stations, annee, d_from, d_to)

    log_event(db, request=request, user=user, action="view_dashboard",
              resource_type="dashboard")
    return DashboardSummary(
        pending_count=pending_count,
        quality_anomalies=quality_anomalies,
        stations_active=stations_active,
        stations_inactive=stations_inactive,
        completeness=completeness,
    )


@router.get("/map", response_model=list[StationMarker])
def dashboard_map(request: Request,
                  date_from: str | None = None,
                  date_to: str | None = None,
                  station_id: int | None = None,
                  db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    date_from = parse_iso_date_qs(date_from, "date_from")
    date_to = parse_iso_date_qs(date_to, "date_to")
    ids = scoped_station_ids(db, user)
    if date_from is None or date_to is None:
        default_from, default_to = _hydro_window(_default_annee_hydro(db))
        date_from = date_from or default_from
        date_to = date_to or default_to

    stations = _scoped_stations(db, ids, station_id)
    station_ids = [s.id for s in stations]

    flags_by_station: dict[int, set[str]] = {}
    if station_ids:
        for sid, flag in (db.query(Reading.station_id, Reading.quality_flag)
                          .filter(Reading.station_id.in_(station_ids),
                                  Reading.date >= date_from, Reading.date <= date_to,
                                  Reading.quality_flag.isnot(None))
                          .distinct().all()):
            flags_by_station.setdefault(sid, set()).add(flag)

    markers = []
    for s in stations:
        if s.status != "active":
            quality = "inactive"
        else:
            flags = flags_by_station.get(s.id)
            quality = max(flags, key=lambda f: _SEVERITY.get(f, -1)) if flags else "inconnu"
        markers.append(StationMarker(
            id=s.id, code=s.code, name=s.name,
            latitude=s.latitude, longitude=s.longitude,
            status=s.status, quality=quality,
        ))

    log_event(db, request=request, user=user, action="view_dashboard",
              resource_type="map")
    return markers
