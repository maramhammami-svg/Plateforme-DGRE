import csv
import io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Header
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import RawReading, Reading, Station, User
from ..events import log_event
from ..deps import get_current_user, scoped_station_ids
from ..security import verify_password
from .. import constants as C
from ..schemas import RawReadingIn, RawReadingOut, ImportResult

router = APIRouter(prefix="/raw-readings", tags=["raw-readings"])


def _aggregate_day(db: Session, station: Station, date_str: str) -> float | None:
    """Calcule valeur_recalculee pour un jour donne selon le parametre de la station."""
    day_start = datetime.fromisoformat(f"{date_str}T00:00:00")
    day_end = datetime.fromisoformat(f"{date_str}T23:59:59")
    rows = (db.query(RawReading)
            .filter(RawReading.station_id == station.id,
                    RawReading.timestamp >= day_start,
                    RawReading.timestamp <= day_end,
                    RawReading.is_missing == False)  # noqa: E712
            .all())
    valeurs = [r.valeur for r in rows if r.valeur is not None]
    if not valeurs:
        return None
    if station.parameter == C.PARAM_PLUVIO:
        return sum(valeurs)
    return sum(valeurs) / len(valeurs)  # limnimetrie -> moyenne


def _upsert_daily_reading(db: Session, station: Station, date_str: str, actor_id: int | None):
    """Cree ou met a jour le releve journalier correspondant a un jour de brut.
    Ne touche pas a valeur_validee si le releve est deja valide (gel)."""
    r = (db.query(Reading)
         .filter(Reading.station_id == station.id, Reading.date == date_str)
         .first())
    agg = _aggregate_day(db, station, date_str)
    if r is None:
        r = Reading(
            station_id=station.id, date=date_str,
            parameter=station.parameter,
            valeur_recalculee=agg, valeur_validee=None,
            status=C.STATUS_PENDING, source=C.SOURCE_AUTO,
            created_by=actor_id,
        )
        db.add(r)
    elif r.status != C.STATUS_VALIDATED:
        r.valeur_recalculee = agg
    db.commit()


@router.post("", response_model=RawReadingOut, status_code=201)
def create_raw_reading(payload: RawReadingIn, request: Request,
                       db: Session = Depends(get_db),
                       x_station_key: str | None = Header(default=None, alias="X-Station-Key")):
    st = db.query(Station).filter(Station.id == payload.station_id).first()
    if not st:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station introuvable")
    if (not x_station_key or not st.hashed_station_key
            or not verify_password(x_station_key, st.hashed_station_key)):
        log_event(db, request=request, user=None, action="ingest_raw",
                  result=C.RESULT_DENIED, resource_type="station", resource_id=st.id,
                  detail={"reason": "cle station invalide"})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Cle station invalide")
    if st.type != C.STATION_TYPE_AUTO:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Releves bruts reserves aux stations automatiques")
    ts = payload.timestamp or datetime.now(timezone.utc)
    rr = RawReading(station_id=st.id, timestamp=ts, valeur=payload.valeur,
                    is_missing=payload.is_missing, source=payload.source)
    db.add(rr); db.commit(); db.refresh(rr)
    _upsert_daily_reading(db, st, ts.strftime("%Y-%m-%d"), None)
    log_event(db, request=request, user=None, action="ingest_raw",
              resource_type="station", resource_id=st.id, volume=1)
    return rr


@router.get("", response_model=list[RawReadingOut])
def list_raw_readings(request: Request, station_id: int | None = None,
                      date: str | None = None,
                      db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    ids = scoped_station_ids(db, user)
    q = db.query(RawReading)
    if ids is not None:
        q = q.filter(RawReading.station_id.in_(ids))
    if station_id is not None:
        q = q.filter(RawReading.station_id == station_id)
    if date is not None:
        day_start = datetime.fromisoformat(f"{date}T00:00:00")
        day_end = datetime.fromisoformat(f"{date}T23:59:59")
        q = q.filter(RawReading.timestamp >= day_start,
                     RawReading.timestamp <= day_end)
    rows = q.order_by(RawReading.timestamp.desc()).all()
    log_event(db, request=request, user=user, action="list_raw_readings",
              resource_type="raw_reading", volume=len(rows))
    return rows


@router.post("/import", response_model=ImportResult)
async def import_raw_readings(request: Request, file: UploadFile = File(...),
                               db: Session = Depends(get_db),
                               user: User = Depends(get_current_user)):
    """Import CSV brut : colonnes 'station_name,timestamp,valeur'.
    Une valeur commencant par '[' ou vide = donnee manquante (is_missing=True, valeur=null)."""
    raw = await file.read()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    inserted, rejected, details = 0, 0, []
    affected: dict[tuple, int] = {}   # (station_id, date_str) -> actor_id

    for row in reader:
        name = (row.get("station_name") or "").strip()
        ts_str = (row.get("timestamp") or "").strip()
        val_raw = (row.get("valeur") or "").strip()

        st = db.query(Station).filter(Station.name == name).first()
        if not st:
            rejected += 1
            details.append({"station": name, "raison": "station inconnue"})
            continue
        if st.type != C.STATION_TYPE_AUTO:
            rejected += 1
            details.append({"station": name, "raison": "station non automatique"})
            continue
        try:
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            rejected += 1
            details.append({"station": name, "raison": "timestamp invalide"})
            continue

        is_missing = val_raw.startswith("[") or val_raw == ""
        valeur = None
        if not is_missing:
            try:
                valeur = float(val_raw)
            except ValueError:
                rejected += 1
                details.append({"station": name, "raison": "valeur illisible"})
                continue

        db.add(RawReading(station_id=st.id, timestamp=ts, valeur=valeur,
                          is_missing=is_missing, source=C.SOURCE_IMPORT))
        affected[(st.id, ts.strftime("%Y-%m-%d"))] = user.id
        inserted += 1

    db.commit()

    for (sid, date_str), actor_id in affected.items():
        st = db.query(Station).filter(Station.id == sid).first()
        _upsert_daily_reading(db, st, date_str, actor_id)

    log_event(db, request=request, user=user, action="import_raw_readings",
              resource_type="raw_reading", volume=inserted,
              detail={"inserted": inserted, "rejected": rejected})
    return ImportResult(inserted=inserted, rejected=rejected, details=details[:20])
