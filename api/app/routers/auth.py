from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..security import verify_password, create_access_token, hash_password
from ..events import log_event
from ..deps import get_current_user
from .. import constants as C
from ..schemas import Token, UserOut, PasswordChange

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user:
        log_event(db, request=request, user=None, action="login",
                  result=C.RESULT_FAILURE, detail={"username": form.username})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants invalides")

    if user.locked or not user.is_active:
        log_event(db, request=request, user=user, action="login",
                  result=C.RESULT_DENIED, resource_type="account", resource_id=user.id)
        message = ("Compte verrouille, contactez un administrateur" if user.locked
                   else "Compte desactive")
        raise HTTPException(status.HTTP_403_FORBIDDEN, message)

    if not verify_password(form.password, user.hashed_password):
        user.failed_attempts += 1
        just_locked = user.failed_attempts >= C.MAX_FAILED_ATTEMPTS
        if just_locked:
            user.locked = 1
        db.commit()
        if just_locked:
            log_event(db, request=request, user=user, action="account_locked",
                      result=C.RESULT_SUCCESS, resource_type="account", resource_id=user.id,
                      detail={"failed_attempts": user.failed_attempts})
        log_event(db, request=request, user=user, action="login",
                  result=C.RESULT_FAILURE, detail={"username": form.username})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants invalides")

    user.failed_attempts = 0
    db.commit()
    log_event(db, request=request, user=user, action="login", result=C.RESULT_SUCCESS)
    return Token(access_token=create_access_token(user.username))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.put("/password")
def change_password(payload: PasswordChange, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    if not verify_password(payload.ancien, user.hashed_password):
        log_event(db, request=request, user=user, action="password_change",
                  result=C.RESULT_FAILURE, resource_type="account", resource_id=user.id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ancien mot de passe incorrect")
    user.hashed_password = hash_password(payload.nouveau)
    db.commit()
    log_event(db, request=request, user=user, action="password_change",
              result=C.RESULT_SUCCESS, resource_type="account", resource_id=user.id)
    return {"status": "ok"}
