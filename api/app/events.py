from sqlalchemy.orm import Session
from fastapi import Request
from .models import Event
from . import constants as C


def client_ip(request: Request | None) -> str | None:
    """IP loggee dans le contrat d'observabilite (signal anti-exfiltration).
    X-Forwarded-For est usurpable par le client (nginx l'ajoute a la suite d'une
    valeur deja presente au lieu de l'ecraser) : on ne s'y fie pas. X-Real-IP est
    ecrase inconditionnellement par la passerelle nginx (`proxy_set_header X-Real-IP
    $remote_addr`), donc non usurpable tant que l'API n'est joignable que via elle."""
    if request is None:
        return None
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
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
