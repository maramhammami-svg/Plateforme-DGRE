from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, Station, UniteOrganisationnelle
from .security import decode_token
from .events import log_event
from . import constants as C

oauth2 = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalide")
    user = db.query(User).filter(User.username == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utilisateur inconnu ou inactif")
    return user


# Roles qui voient toutes les donnees (aucun branch-scoping)
_ROLES_GLOBAUX = {C.ROLE_ADMIN, C.ROLE_ANALYSTE, C.ROLE_DIRECTEUR}


def require_role(*roles: str, action: str, resource_type: str | None = None):
    """Dependance-usine : autorise seulement `roles`. En cas de refus,
    journalise result=denied puis leve 403. Retourne le user si autorise."""
    def dep(request: Request,
            db: Session = Depends(get_db),
            user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            log_event(db, request=request, user=user,
                      action=action, result=C.RESULT_DENIED,
                      resource_type=resource_type)
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Action non autorisee pour votre role")
        return user
    return dep


def _descendant_unite_ids(db: Session, root_id: int | None) -> set[int]:
    """root_id + tous ses descendants dans l'arbre des unites."""
    if root_id is None:
        return set()
    enfants: dict[int | None, list[int]] = {}
    for u in db.query(UniteOrganisationnelle).all():
        enfants.setdefault(u.parent_id, []).append(u.id)
    ids = {root_id}
    pile = [root_id]
    while pile:
        cur = pile.pop()
        for c in enfants.get(cur, []):
            if c not in ids:
                ids.add(c)
                pile.append(c)
    return ids


def scoped_station_ids(db: Session, user: User) -> list[int] | None:
    """station_id visibles par user. None = aucune restriction (voit tout)."""
    if user.role in _ROLES_GLOBAUX:
        return None
    unite_ids = _descendant_unite_ids(db, user.unite_id)
    q = db.query(Station.id).filter(Station.unite_id.in_(unite_ids))
    if user.role == C.ROLE_OBSERVATEUR:
        q = q.filter(Station.type == C.STATION_TYPE_CONV)
    return [row[0] for row in q.all()]


def scoped_unite_ids(db: Session, user: User) -> set[int] | None:
    """unite_id visibles par user. None = aucune restriction (voit tout)."""
    if user.role in _ROLES_GLOBAUX:
        return None
    return _descendant_unite_ids(db, user.unite_id)
