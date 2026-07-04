from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Consolidation
from ..schemas import ConsolidationOut

router = APIRouter(prefix="/consolidations", tags=["consolidations"])


@router.get("", response_model=list[ConsolidationOut])
def list_consolidations(station_id: int | None = Query(None),
                        annee_hydro: int | None = Query(None),
                        db: Session = Depends(get_db),
                        user=Depends(get_current_user)):
    q = db.query(Consolidation)
    if station_id is not None:
        q = q.filter(Consolidation.station_id == station_id)
    if annee_hydro is not None:
        q = q.filter(Consolidation.annee_hydro == annee_hydro)
    return q.order_by(Consolidation.station_id, Consolidation.annee_hydro).all()


@router.get("/{station_id}/{annee_hydro}", response_model=ConsolidationOut)
def get_consolidation(station_id: int, annee_hydro: int,
                      db: Session = Depends(get_db),
                      user=Depends(get_current_user)):
    row = db.query(Consolidation).filter(
        Consolidation.station_id == station_id,
        Consolidation.annee_hydro == annee_hydro,
    ).first()
    if not row:
        raise HTTPException(404, "Consolidation introuvable")
    return row
