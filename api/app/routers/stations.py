from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Station, User
from ..events import log_event
from ..deps import get_current_user
from .. import constants as C
from ..schemas import StationIn, StationUpdate, StationOut, StationCreated
from ..security import generate_station_key, hash_password

router = APIRouter(prefix="/stations", tags=["stations"])

_WRITE_ROLES = {C.ROLE_RESPONSABLE, C.ROLE_ANALYSTE, C.ROLE_DIRECTEUR, C.ROLE_ADMIN}


@router.get("", response_model=list[StationOut])
def list_stations(request: Request, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    stations = db.query(Station).all()
    log_event(db, request=request, user=user, action="list_stations",
              resource_type="station", volume=len(stations))
    return stations


@router.post("", response_model=StationCreated, status_code=201)
def create_station(payload: StationIn, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    if user.role not in _WRITE_ROLES:
        log_event(db, request=request, user=user, action="create_station",
                  result=C.RESULT_DENIED, resource_type="station",
                  detail={"reason": "role insuffisant"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Role insuffisant")
    if payload.type not in C.STATION_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Type station invalide")
    if payload.parameter not in C.PARAMETERS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Parametre invalide")
    if payload.unit not in C.UNITS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unite invalide")
    if db.query(Station).filter(Station.name == payload.name).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Nom de station deja utilise")
    station_key = generate_station_key()
    st = Station(**payload.model_dump(), hashed_station_key=hash_password(station_key))
    db.add(st); db.commit(); db.refresh(st)
    log_event(db, request=request, user=user, action="create_station",
              resource_type="station", resource_id=st.id)
    data = StationOut.model_validate(st).model_dump()
    return StationCreated(**data, station_key=station_key)


@router.patch("/{station_id}", response_model=StationOut)
def update_station(station_id: int, payload: StationUpdate, request: Request,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    st = db.query(Station).filter(Station.id == station_id).first()
    if not st:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station introuvable")
    if user.role not in _WRITE_ROLES:
        log_event(db, request=request, user=user, action="update_station",
                  result=C.RESULT_DENIED, resource_type="station", resource_id=st.id,
                  detail={"reason": "role insuffisant"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Role insuffisant")
    data = payload.model_dump(exclude_unset=True)
    if "type" in data and data["type"] not in C.STATION_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Type station invalide")
    if "parameter" in data and data["parameter"] not in C.PARAMETERS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Parametre invalide")
    if "unit" in data and data["unit"] not in C.UNITS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unite invalide")
    old = {k: getattr(st, k) for k in data}
    for k, v in data.items():
        setattr(st, k, v)
    db.commit(); db.refresh(st)
    log_event(db, request=request, user=user, action="update_station",
              resource_type="station", resource_id=st.id,
              detail={"from": old, "to": data})
    return st
