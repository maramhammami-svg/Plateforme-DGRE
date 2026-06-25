from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Event, User
from ..events import log_event
from ..deps import get_current_user
from .. import constants as C
from ..schemas import EventOut

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventOut])
def list_events(request: Request, limit: int = 100,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Le journal global est reserve a l'Administrateur (futur tableau de l'agent).
    if user.role != C.ROLE_ADMIN:
        log_event(db, request=request, user=user, action="list_events",
                  result=C.RESULT_DENIED, resource_type="event",
                  detail={"reason": "role insuffisant"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Reserve a l'administrateur")
    rows = db.query(Event).order_by(Event.id.desc()).limit(min(limit, 500)).all()
    return rows
