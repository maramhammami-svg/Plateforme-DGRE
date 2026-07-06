from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Event, User
from ..deps import require_role
from .. import constants as C
from ..schemas import EventOut

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventOut])
def list_events(request: Request, limit: int = Query(default=100, ge=1, le=500),
                db: Session = Depends(get_db),
                user: User = Depends(require_role(
                    C.ROLE_DIRECTEUR, C.ROLE_ADMIN,
                    action="list_events", resource_type="event"))):
    rows = db.query(Event).order_by(Event.id.desc()).limit(limit).all()
    return rows
