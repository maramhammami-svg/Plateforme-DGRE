from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Station, User
from ..events import log_event
from ..deps import get_current_user
from .. import constants as C
from ..schemas import StationIn, StationUpdate, StationOut

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("", response_model=list[StationOut])
def list_stations(request: Request, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    q = db.query(Station)
    if user.role != C.ROLE_ADMIN:
        q = q.filter(Station.region == user.region)
    stations = q.all()
    log_event(db, request=request, user=user, action="list_stations",
              resource_type="station", volume=len(stations))
    return stations


@router.post("", response_model=StationOut, status_code=201)
def create_station(payload: StationIn, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    if user.role == C.ROLE_AGENT:
        log_event(db, request=request, user=user, action="create_station",
                  result=C.RESULT_DENIED, resource_type="station",
                  detail={"reason": "role insuffisant"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Role insuffisant")
    if user.role != C.ROLE_ADMIN and payload.region != user.region:
        log_event(db, request=request, user=user, action="create_station",
                  result=C.RESULT_DENIED, resource_type="station", region=payload.region,
                  detail={"reason": "hors region"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Hors de votre region")
    if db.query(Station).filter(Station.code == payload.code).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Code station deja utilise")
    st = Station(**payload.model_dump())
    db.add(st); db.commit(); db.refresh(st)
    log_event(db, request=request, user=user, action="create_station",
              resource_type="station", resource_id=st.id, region=st.region)
    return st


@router.patch("/{station_id}", response_model=StationOut)
def update_station(station_id: int, payload: StationUpdate, request: Request,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    st = db.query(Station).filter(Station.id == station_id).first()
    if not st:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station introuvable")
    if user.role == C.ROLE_AGENT:
        log_event(db, request=request, user=user, action="update_station",
                  result=C.RESULT_DENIED, resource_type="station", resource_id=st.id,
                  detail={"reason": "role insuffisant"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Role insuffisant")
    if user.role != C.ROLE_ADMIN and st.region != user.region:
        log_event(db, request=request, user=user, action="update_station",
                  result=C.RESULT_DENIED, resource_type="station", resource_id=st.id,
                  region=st.region, detail={"reason": "hors region"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Hors de votre region")
    data = payload.model_dump(exclude_unset=True)
    old = {k: getattr(st, k) for k in data}
    for k, v in data.items():
        setattr(st, k, v)
    db.commit(); db.refresh(st)
    log_event(db, request=request, user=user, action="update_station",
              resource_type="station", resource_id=st.id, region=st.region,
              detail={"from": old, "to": data})
    return st
