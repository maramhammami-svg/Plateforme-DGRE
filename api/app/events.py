import hashlib
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import Request
from .models import Event
from . import constants as C

GENESIS_HASH = "GENESIS"


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


def chain_payload(prev_hash: str, action: str, actor_username: str | None,
                  result: str, timestamp: datetime) -> str:
    """Formule du chainage (identique a l'insertion et a la re-verification) :
    depend du hash precedent, donc toute alteration ou suppression d'un evenement
    passe casse tous les hash suivants."""
    return f"{prev_hash}|{action}|{actor_username}|{result}|{timestamp.isoformat()}"


def log_event(db: Session, *, request: Request | None, user=None,
              action: str, result: str = C.RESULT_SUCCESS,
              resource_type: str | None = None, resource_id=None,
              unite_ressource: str | None = None, volume: int | None = None,
              detail: dict | None = None) -> Event:
    """Ecrit un evenement normalise (le seul canal lu par l'agent), chaine par hash
    (chain_hash = sha256(prev_hash|...|timestamp)) pour detecter toute alteration
    ulterieure de la table. Le timestamp est genere ici en Python (pas via
    server_default) car le hash doit etre calcule AVANT l'insertion."""
    unite = getattr(user, "unite", None) if user is not None else None
    unite_acteur = unite.nom if unite is not None else None
    actor_username = getattr(user, "username", None)

    timestamp = datetime.now(timezone.utc)
    last = db.query(Event).order_by(Event.id.desc()).first()
    prev_hash = last.chain_hash if last is not None else GENESIS_HASH
    payload = chain_payload(prev_hash, action, actor_username, result, timestamp)
    chain_hash = hashlib.sha256(payload.encode()).hexdigest()

    ev = Event(
        timestamp=timestamp,
        actor_id=getattr(user, "id", None),
        actor_username=actor_username,
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
        chain_hash=chain_hash,
        prev_hash=prev_hash,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev
