from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..security import verify_password, create_access_token
from ..events import log_event
from ..deps import get_current_user
from .. import constants as C
from ..schemas import Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        # Echec journalise : c'est ce qui permettra de detecter le brute-force.
        log_event(db, request=request, user=user, action="login",
                  result=C.RESULT_FAILURE,
                  detail={"username": form.username})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants invalides")
    log_event(db, request=request, user=user, action="login", result=C.RESULT_SUCCESS)
    return Token(access_token=create_access_token(user.username))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
