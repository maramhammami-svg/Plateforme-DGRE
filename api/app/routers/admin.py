from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..security import hash_password, generate_password
from ..events import log_event
from ..deps import get_current_user, require_role
from .. import constants as C
from ..schemas import UserIn, UserUpdate, UserOut, PasswordResetOut, UserLiteOut

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(db, request, user, action):
    if user.role != C.ROLE_ADMIN:
        log_event(db, request=request, user=user, action=action,
                  result=C.RESULT_DENIED, resource_type="account",
                  detail={"reason": "reserve a l'administrateur"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Reserve a l'administrateur")


@router.get("/users", response_model=list[UserOut])
def list_users(request: Request, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    _require_admin(db, request, user, "list_users")
    return db.query(User).order_by(User.id).all()


@router.get("/users/directory", response_model=list[UserLiteOut])
def users_directory(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Annuaire des comptes actifs (id/username/nom/unite) : utilise pour choisir
    des destinataires de partage de document. Ouvert a tout utilisateur authentifie,
    contrairement a /admin/users (reserve admin) : rien ici n'est sensible."""
    return (db.query(User).filter(User.is_active == 1)
            .order_by(User.username).all())


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserIn, request: Request, db: Session = Depends(get_db),
                user: User = Depends(require_role(
                    C.ROLE_ADMIN, action="create_account", resource_type="account"))):
    if payload.role not in C.ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Role inconnu")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Identifiant deja pris")
    u = User(username=payload.username, full_name=payload.full_name,
             hashed_password=hash_password(payload.password),
             role=payload.role)
    db.add(u); db.commit(); db.refresh(u)
    log_event(db, request=request, user=user, action="create_account",
              resource_type="account", resource_id=u.id,
              detail={"username": u.username, "role": u.role})
    return u


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, request: Request,
                db: Session = Depends(get_db),
                user: User = Depends(require_role(
                    C.ROLE_ADMIN, action="update_account", resource_type="account"))):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compte introuvable")
    data = payload.model_dump(exclude_unset=True)
    if "role" in data and data["role"] not in C.ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Role inconnu")
    old = {k: getattr(target, k) for k in data}
    for k, v in data.items():
        setattr(target, k, v)
    db.commit(); db.refresh(target)
    log_event(db, request=request, user=user, action="update_account",
              resource_type="account", resource_id=target.id,
              detail={"from": old, "to": data})
    return target


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetOut)
def reset_password(user_id: int, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(require_role(
                       C.ROLE_ADMIN, action="password_reset", resource_type="account"))):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compte introuvable")
    nouveau = generate_password()
    target.hashed_password = hash_password(nouveau)
    db.commit()
    log_event(db, request=request, user=user, action="password_reset",
              result=C.RESULT_SUCCESS, resource_type="account", resource_id=target.id)
    return PasswordResetOut(user_id=target.id, username=target.username,
                            nouveau_mot_de_passe=nouveau)


@router.post("/users/{user_id}/unlock", response_model=UserOut)
def unlock_user(user_id: int, request: Request, db: Session = Depends(get_db),
                user: User = Depends(require_role(
                    C.ROLE_ADMIN, action="account_unlock", resource_type="account"))):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compte introuvable")
    target.locked = 0
    target.failed_attempts = 0
    db.commit()
    log_event(db, request=request, user=user, action="account_unlock",
              result=C.RESULT_SUCCESS, resource_type="account", resource_id=target.id)
    return target
