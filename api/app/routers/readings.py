import csv
import io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Reading, ReadingVersion, Station, User
from ..events import log_event
from ..deps import get_current_user, require_role, scoped_station_ids
from .. import constants as C
from ..schemas import (ReadingIn, ReadingUpdate, ReadingOut, ReadingVersionOut,
                       ValidateIn)

router = APIRouter(prefix="/readings", tags=["readings"])


def _station_or_404(db, station_id):
    st = db.query(Station).filter(Station.id == station_id).first()
    if not st:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station introuvable")
    return st


def _quality_flag(value: float | None) -> str:
    if value is None:
        return C.FLAG_MANQUANT
    if value > C.PLAUSIBLE_MAX_MM:
        return C.FLAG_ABERRANT
    if value > C.SUSPECT_MAX_MM:
        return C.FLAG_SUSPECT
    return C.FLAG_OK


# ---------- export CSV ----------

@router.get("/export")
def export_readings(request: Request, station_id: int | None = None,
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Export CSV des releves journaliers.
    Le volume exporte est journalise : un export massif devient un signal d'exfiltration."""
    ids = scoped_station_ids(db, user)
    q = db.query(Reading).join(Station)
    if ids is not None:
        q = q.filter(Reading.station_id.in_(ids))
    if station_id is not None:
        q = q.filter(Reading.station_id == station_id)
    rows = q.all()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "station_name", "date", "parameter", "valeur_recalculee",
                "valeur_validee", "status", "quality_flag", "source"])
    for r in rows:
        w.writerow([r.id, r.station.name, r.date, r.parameter,
                    r.valeur_recalculee, r.valeur_validee,
                    r.status, r.quality_flag or "", r.source])
    log_event(db, request=request, user=user, action="export_readings",
              resource_type="reading", volume=len(rows))
    return Response(content=out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=readings.csv"})


# ---------- CRUD journalier ----------

@router.get("", response_model=list[ReadingOut])
def list_readings(request: Request, station_id: int | None = None,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ids = scoped_station_ids(db, user)
    q = db.query(Reading)
    if ids is not None:
        q = q.filter(Reading.station_id.in_(ids))
    if station_id is not None:
        q = q.filter(Reading.station_id == station_id)
    rows = q.order_by(Reading.id.desc()).all()
    log_event(db, request=request, user=user, action="list_readings",
              resource_type="reading", volume=len(rows))
    return rows


@router.post("", response_model=ReadingOut, status_code=201)
def create_reading(payload: ReadingIn, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(require_role(
                       C.ROLE_AGENT, C.ROLE_RESPONSABLE, C.ROLE_ADMIN,
                       action="create_reading", resource_type="reading"))):
    """Saisie manuelle d'un releve journalier — stations conventionnelles uniquement."""
    st = _station_or_404(db, payload.station_id)
    ids = scoped_station_ids(db, user)
    if ids is not None and st.id not in ids:
        log_event(db, request=request, user=user, action="create_reading",
                  result=C.RESULT_DENIED, resource_type="reading", resource_id=st.id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Station hors de votre perimetre")
    if st.type != C.STATION_TYPE_CONV:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "La saisie manuelle est reservee aux stations conventionnelles")
    if payload.valeur < 0 or payload.valeur > C.PLAUSIBLE_MAX_MM:
        log_event(db, request=request, user=user, action="create_reading",
                  result=C.RESULT_FAILURE, resource_type="reading",
                  detail={"reason": "valeur aberrante", "valeur": payload.valeur})
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Valeur implausible (rejetee)")
    if db.query(Reading).filter(Reading.station_id == st.id,
                                Reading.date == payload.date).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Un releve existe deja pour cette date")
    flag = _quality_flag(payload.valeur)
    r = Reading(station_id=st.id, date=payload.date,
                parameter=st.parameter,
                valeur_recalculee=payload.valeur, valeur_validee=None,
                status=C.STATUS_PENDING, quality_flag=flag,
                source=C.SOURCE_MANUAL, created_by=user.id)
    db.add(r); db.commit(); db.refresh(r)
    log_event(db, request=request, user=user, action="create_reading",
              resource_type="reading", resource_id=r.id, volume=1,
              detail={"valeur": payload.valeur, "quality_flag": flag})
    return r


@router.patch("/{reading_id}", response_model=ReadingOut)
def correct_reading(reading_id: int, payload: ReadingUpdate, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(require_role(
                        C.ROLE_AGENT, C.ROLE_RESPONSABLE, C.ROLE_ADMIN,
                        action="update_reading", resource_type="reading"))):
    """Correction versionnee d'un releve.
    post_validation=True si le releve etait deja valide au moment de la correction."""
    r = db.query(Reading).filter(Reading.id == reading_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Releve introuvable")

    ids = scoped_station_ids(db, user)
    if ids is not None and r.station_id not in ids:
        log_event(db, request=request, user=user, action="update_reading",
                  result=C.RESULT_DENIED, resource_type="reading", resource_id=r.id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Releve hors de votre perimetre")

    was_validated = r.status == C.STATUS_VALIDATED
    if was_validated and user.role == C.ROLE_AGENT:
        log_event(db, request=request, user=user, action="update_reading",
                  result=C.RESULT_DENIED, resource_type="reading", resource_id=r.id,
                  detail={"reason": "modification d'un releve valide"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Releve valide : modification interdite")

    new_val = payload.valeur_recalculee if payload.valeur_recalculee is not None else r.valeur_recalculee
    vno = db.query(ReadingVersion).filter(ReadingVersion.reading_id == r.id).count() + 1
    new_status = r.status if was_validated else C.STATUS_PENDING
    db.add(ReadingVersion(
        reading_id=r.id, version_no=vno,
        ancienne_val=r.valeur_recalculee, nouvelle_val=new_val,
        old_status=r.status, new_status=new_status,
        post_validation=was_validated,
        auteur=user.id, raison=payload.raison,
    ))
    old_val, old_status = r.valeur_recalculee, r.status
    r.valeur_recalculee = new_val
    r.quality_flag = _quality_flag(new_val)
    if not was_validated:
        # repasse en attente si pas encore valide
        r.status = C.STATUS_PENDING
        r.validated_by = None
        r.validated_at = None
    # si valide : valeur_validee reste figee, seule valeur_recalculee change
    db.commit(); db.refresh(r)
    log_event(db, request=request, user=user, action="update_reading",
              resource_type="reading", resource_id=r.id, volume=1,
              detail={"from": {"valeur_recalculee": old_val, "status": old_status},
                      "to": {"valeur_recalculee": new_val, "status": r.status},
                      "post_validation": was_validated, "raison": payload.raison})
    return r


@router.delete("/{reading_id}", status_code=204)
def delete_reading(reading_id: int, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(require_role(
                       C.ROLE_RESPONSABLE, C.ROLE_ADMIN,
                       action="delete_reading", resource_type="reading"))):
    r = db.query(Reading).filter(Reading.id == reading_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Releve introuvable")
    ids = scoped_station_ids(db, user)
    if ids is not None and r.station_id not in ids:
        log_event(db, request=request, user=user, action="delete_reading",
                  result=C.RESULT_DENIED, resource_type="reading", resource_id=r.id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Releve hors de votre perimetre")
    log_event(db, request=request, user=user, action="delete_reading",
              resource_type="reading", resource_id=r.id, volume=1,
              detail={"valeur_recalculee": r.valeur_recalculee, "status": r.status})
    db.query(ReadingVersion).filter(ReadingVersion.reading_id == r.id).delete()
    db.delete(r); db.commit()
    return Response(status_code=204)


@router.get("/{reading_id}/versions", response_model=list[ReadingVersionOut])
def reading_versions(reading_id: int, request: Request, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    r = db.query(Reading).filter(Reading.id == reading_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Releve introuvable")
    return (db.query(ReadingVersion).filter(ReadingVersion.reading_id == r.id)
            .order_by(ReadingVersion.version_no).all())


@router.post("/{reading_id}/validate", response_model=ReadingOut)
def validate_reading(reading_id: int, payload: ValidateIn, request: Request,
                     db: Session = Depends(get_db),
                     user: User = Depends(require_role(
                         C.ROLE_RESPONSABLE, C.ROLE_ADMIN,
                         action="validate_reading", resource_type="reading"))):
    r = db.query(Reading).filter(Reading.id == reading_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Releve introuvable")
    ids = scoped_station_ids(db, user)
    if ids is not None and r.station_id not in ids:
        log_event(db, request=request, user=user, action="validate_reading",
                  result=C.RESULT_DENIED, resource_type="reading", resource_id=r.id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Releve hors de votre perimetre")
    new_status = C.STATUS_VALIDATED if payload.decision == "validate" else C.STATUS_REJECTED
    old_status = r.status
    r.status = new_status
    r.validated_by = user.id
    r.validated_at = datetime.now(timezone.utc)
    if new_status == C.STATUS_VALIDATED:
        r.valeur_validee = r.valeur_recalculee   # gel : copie une seule fois
    db.commit(); db.refresh(r)
    log_event(db, request=request, user=user, action="validate_reading",
              resource_type="reading", resource_id=r.id,
              detail={"from": old_status, "to": new_status,
                      "valeur_validee": r.valeur_validee})
    return r
