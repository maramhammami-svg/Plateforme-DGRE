import hashlib
from datetime import timezone
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Event, User
from ..deps import require_role
from ..events import GENESIS_HASH, chain_payload
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


@router.get("/verify-integrity")
def verify_integrity(db: Session = Depends(get_db),
                     user: User = Depends(require_role(
                         C.ROLE_ADMIN, action="verify_integrity", resource_type="event"))):
    """Rejoue le chainage de hash sur toute la table `events` et compare au chain_hash
    stocke a chaque etape. Toute alteration d'un champ (ou d'un timestamp) apres coup,
    ou toute suppression d'un evenement, decale le hash calcule et est detectee des le
    premier evenement touche."""
    rows = db.query(Event).order_by(Event.id.asc()).all()
    total = len(rows)
    prev_hash = GENESIS_HASH
    checked = 0
    for ev in rows:
        ts = ev.timestamp
        if ts.tzinfo is None:
            # SQLite ne conserve pas le fuseau horaire au retour de lecture (contrairement
            # a Postgres/timestamptz) : on rehydrate en UTC, seul fuseau jamais ecrit ici,
            # pour que isoformat() reproduise exactement la chaine hachee a l'insertion.
            ts = ts.replace(tzinfo=timezone.utc)
        payload = chain_payload(prev_hash, ev.action, ev.actor_username, ev.result, ts)
        expected_hash = hashlib.sha256(payload.encode()).hexdigest()
        checked += 1
        if expected_hash != ev.chain_hash:
            return {"valid": False, "broken_at": ev.id, "total": total, "checked": checked}
        prev_hash = ev.chain_hash
    return {"valid": True, "total": total, "checked": checked}
