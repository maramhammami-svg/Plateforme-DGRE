from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import UniteOrganisationnelle, User
from ..schemas import UniteLiteOut

router = APIRouter(prefix="/unites", tags=["unites"])


@router.get("", response_model=list[UniteLiteOut])
def list_unites(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Annuaire des unites (id + nom) : utilise pour choisir des destinataires de
    partage de document. Pas de scoping ici, seulement des libelles non sensibles."""
    return db.query(UniteOrganisationnelle).order_by(UniteOrganisationnelle.nom).all()
