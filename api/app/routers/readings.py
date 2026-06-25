import csv
import io
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Reading, ReadingVersion, Station, User
from ..events import log_event
from ..deps import get_current_user
from .. import constants as C
from ..schemas import (ReadingIn, ReadingUpdate, ReadingOut, ReadingVersionOut,
                       ValidateIn, ImportResult)

router = APIRouter(prefix="/readings", tags=["readings"])


def _station_or_404(db, station_id):
    st = db.query(Station).filter(Station.id == station_id).first()
    if not st:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station introuvable")
    return st


def _quality_flag(value: float) -> str | None:
    return "suspect" if value > C.SUSPECT_MAX_MM else None


# ---------- routes litterales d'abord (import / export) ----------

@router.post("/import", response_model=ImportResult)
async def import_readings(request: Request, file: UploadFile = File(...),
                          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Import CSV : colonnes attendues 'station_code,date,value_mm'."""
    raw = await file.read()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    inserted, rejected, details = 0, 0, []
    for row in reader:
        code = (row.get("station_code") or "").strip()
        date = (row.get("date") or "").strip()
        st = db.query(Station).filter(Station.code == code).first()
        if not st:
            rejected += 1; details.append({"code": code, "raison": "station inconnue"}); continue
        if user.role != C.ROLE_ADMIN and st.region != user.region:
            rejected += 1; details.append({"code": code, "raison": "hors region"}); continue
        try:
            v = float(row.get("value_mm"))
        except (TypeError, ValueError):
            rejected += 1; details.append({"code": code, "raison": "valeur illisible"}); continue
        if v < 0 or v > C.PLAUSIBLE_MAX_MM:
            rejected += 1; details.append({"code": code, "raison": "valeur aberrante"}); continue
        db.add(Reading(station_id=st.id, date=date, value_mm=v,
                       status=C.STATUS_PENDING, quality_flag=_quality_flag(v),
                       created_by=user.id))
        inserted += 1
    db.commit()
    log_event(db, request=request, user=user, action="import_readings",
              resource_type="reading", volume=inserted,
              detail={"inserted": inserted, "rejected": rejected})
    return ImportResult(inserted=inserted, rejected=rejected, details=details[:20])


@router.get("/export")
def export_readings(request: Request, station_id: int | None = None,
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Export CSV (cloisonne par region). Le volume exporte est journalise :
    un export massif devient un signal d'exfiltration pour l'agent."""
    q = db.query(Reading).join(Station)
    if user.role != C.ROLE_ADMIN:
        q = q.filter(Station.region == user.region)
    if station_id is not None:
        q = q.filter(Reading.station_id == station_id)
    rows = q.all()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "station_code", "date", "value_mm", "status", "quality_flag"])
    for r in rows:
        w.writerow([r.id, r.station.code, r.date, r.value_mm, r.status, r.quality_flag or ""])
    log_event(db, request=request, user=user, action="export_readings",
              resource_type="reading", volume=len(rows))
    return Response(content=out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=readings.csv"})


# ---------- routes generiques ----------

@router.get("", response_model=list[ReadingOut])
def list_readings(request: Request, station_id: int | None = None,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Reading).join(Station)
    if user.role != C.ROLE_ADMIN:
        q = q.filter(Station.region == user.region)
    if station_id is not None:
        q = q.filter(Reading.station_id == station_id)
    rows = q.order_by(Reading.id.desc()).all()
    log_event(db, request=request, user=user, action="list_readings",
              resource_type="reading", volume=len(rows))
    return rows


@router.post("", response_model=ReadingOut, status_code=201)
def create_reading(payload: ReadingIn, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    st = _station_or_404(db, payload.station_id)
    if user.role != C.ROLE_ADMIN and st.region != user.region:
        log_event(db, request=request, user=user, action="create_reading",
                  result=C.RESULT_DENIED, resource_type="reading", region=st.region,
                  detail={"reason": "hors region", "station": st.code})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Station hors de votre region")
    if payload.value_mm < 0 or payload.value_mm > C.PLAUSIBLE_MAX_MM:
        log_event(db, request=request, user=user, action="create_reading",
                  result=C.RESULT_FAILURE, resource_type="reading", region=st.region,
                  detail={"reason": "valeur aberrante", "value_mm": payload.value_mm})
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Valeur implausible (rejetee)")
    flag = _quality_flag(payload.value_mm)
    r = Reading(station_id=st.id, date=payload.date, value_mm=payload.value_mm,
                status=C.STATUS_PENDING, quality_flag=flag, created_by=user.id)
    db.add(r); db.commit(); db.refresh(r)
    log_event(db, request=request, user=user, action="create_reading",
              resource_type="reading", resource_id=r.id, region=st.region, volume=1,
              detail={"value_mm": r.value_mm, "quality_flag": flag})
    if flag:
        log_event(db, request=request, user=user, action="quality_flag",
                  resource_type="reading", resource_id=r.id, region=st.region,
                  detail={"flag": flag, "value_mm": r.value_mm})
    return r


@router.patch("/{reading_id}", response_model=ReadingOut)
def correct_reading(reading_id: int, payload: ReadingUpdate, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Correction d'un releve : versionnee et journalisee (ancienne -> nouvelle)."""
    r = db.query(Reading).filter(Reading.id == reading_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Releve introuvable")
    st = db.query(Station).filter(Station.id == r.station_id).first()
    if user.role != C.ROLE_ADMIN and st.region != user.region:
        log_event(db, request=request, user=user, action="update_reading",
                  result=C.RESULT_DENIED, resource_type="reading", resource_id=r.id,
                  region=st.region, detail={"reason": "hors region"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Releve hors de votre region")
    # Un agent ne peut pas alterer un releve deja valide -> tentative de falsification.
    if r.status == C.STATUS_VALIDATED and user.role == C.ROLE_AGENT:
        log_event(db, request=request, user=user, action="update_reading",
                  result=C.RESULT_DENIED, resource_type="reading", resource_id=r.id,
                  region=st.region, detail={"reason": "modification d'un releve valide"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Releve valide : modification interdite")

    new_val = payload.value_mm if payload.value_mm is not None else r.value_mm
    if new_val < 0 or new_val > C.PLAUSIBLE_MAX_MM:
        log_event(db, request=request, user=user, action="update_reading",
                  result=C.RESULT_FAILURE, resource_type="reading", resource_id=r.id,
                  region=st.region, detail={"reason": "valeur aberrante", "value_mm": new_val})
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Valeur implausible (rejetee)")

    vno = db.query(ReadingVersion).filter(ReadingVersion.reading_id == r.id).count() + 1
    db.add(ReadingVersion(reading_id=r.id, version_no=vno,
                          old_value_mm=r.value_mm, new_value_mm=new_val,
                          old_status=r.status, new_status=C.STATUS_PENDING,
                          changed_by=user.id, reason=payload.reason))
    old_val, old_status = r.value_mm, r.status
    r.value_mm = new_val
    r.status = C.STATUS_PENDING        # une correction repasse en attente de validation
    r.validated_by = None
    r.quality_flag = _quality_flag(new_val)
    db.commit(); db.refresh(r)
    log_event(db, request=request, user=user, action="update_reading",
              resource_type="reading", resource_id=r.id, region=st.region, volume=1,
              detail={"from": {"value_mm": old_val, "status": old_status},
                      "to": {"value_mm": new_val, "status": r.status},
                      "reason": payload.reason})
    return r


@router.delete("/{reading_id}", status_code=204)
def delete_reading(reading_id: int, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    r = db.query(Reading).filter(Reading.id == reading_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Releve introuvable")
    st = db.query(Station).filter(Station.id == r.station_id).first()
    if user.role == C.ROLE_AGENT:
        log_event(db, request=request, user=user, action="delete_reading",
                  result=C.RESULT_DENIED, resource_type="reading", resource_id=r.id,
                  region=st.region, detail={"reason": "role insuffisant"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Suppression reservee au responsable")
    if user.role != C.ROLE_ADMIN and st.region != user.region:
        log_event(db, request=request, user=user, action="delete_reading",
                  result=C.RESULT_DENIED, resource_type="reading", resource_id=r.id,
                  region=st.region, detail={"reason": "hors region"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Releve hors de votre region")
    log_event(db, request=request, user=user, action="delete_reading",
              resource_type="reading", resource_id=r.id, region=st.region, volume=1,
              detail={"value_mm": r.value_mm, "status": r.status})
    db.query(ReadingVersion).filter(ReadingVersion.reading_id == r.id).delete()
    db.delete(r); db.commit()
    return Response(status_code=204)


@router.get("/{reading_id}/versions", response_model=list[ReadingVersionOut])
def reading_versions(reading_id: int, request: Request, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    r = db.query(Reading).filter(Reading.id == reading_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Releve introuvable")
    st = db.query(Station).filter(Station.id == r.station_id).first()
    if user.role != C.ROLE_ADMIN and st.region != user.region:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Releve hors de votre region")
    return (db.query(ReadingVersion).filter(ReadingVersion.reading_id == r.id)
            .order_by(ReadingVersion.version_no).all())


@router.post("/{reading_id}/validate", response_model=ReadingOut)
def validate_reading(reading_id: int, payload: ValidateIn, request: Request,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.query(Reading).filter(Reading.id == reading_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Releve introuvable")
    st = db.query(Station).filter(Station.id == r.station_id).first()
    if user.role == C.ROLE_AGENT:
        log_event(db, request=request, user=user, action="validate_reading",
                  result=C.RESULT_DENIED, resource_type="reading", resource_id=r.id,
                  region=st.region, detail={"reason": "abus de privilege"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Validation reservee au responsable")
    if user.role != C.ROLE_ADMIN and st.region != user.region:
        log_event(db, request=request, user=user, action="validate_reading",
                  result=C.RESULT_DENIED, resource_type="reading", resource_id=r.id,
                  region=st.region, detail={"reason": "hors region"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Releve hors de votre region")
    new_status = C.STATUS_VALIDATED if payload.decision == "validate" else C.STATUS_REJECTED
    old_status = r.status
    r.status = new_status
    r.validated_by = user.id
    db.commit(); db.refresh(r)
    log_event(db, request=request, user=user, action="validate_reading",
              resource_type="reading", resource_id=r.id, region=st.region,
              detail={"from": old_status, "to": new_status})
    return r
