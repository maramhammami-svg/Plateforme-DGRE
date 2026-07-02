from sqlalchemy.orm import Session
from fastapi import Request
from .models import Event
from . import constants as C


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def log_event(db: Session, *, request: Request | None, user=None,
              action: str, result: str = C.RESULT_SUCCESS,
              resource_type: str | None = None, resource_id=None,
              unite_ressource: str | None = None, volume: int | None = None,
              detail: dict | None = None) -> Event:
    """Ecrit un evenement normalise (le seul canal lu par l'agent)."""
    unite = getattr(user, "unite", None) if user is not None else None
    unite_acteur = unite.nom if unite is not None else None
    ev = Event(
        actor_id=getattr(user, "id", None),
        actor_username=getattr(user, "username", None),
        role=getattr(user, "role", None),
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        unite_acteur=unite_acteur,
        unite_ressource=unite_ressource,
        volume=volume,
        channel_ip=client_ip(request),
        result=result,
        detail=detail,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev
