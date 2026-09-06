from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert, User
from ..deps import require_role
from ..events import log_event
from ..agent.engine import scan
from .. import constants as C
from ..schemas import AlertOut, AlertStats

router = APIRouter(prefix="/alerts", tags=["alerts"])
agent_router = APIRouter(prefix="/agent", tags=["alerts"])

_ALERT_ROLES = (C.ROLE_ADMIN, C.ROLE_RESPONSABLE)


@router.get("", response_model=list[AlertOut])
def list_alerts(severity: Optional[str] = Query(default=None),
                status_: Optional[str] = Query(default=None, alias="status"),
                rule_name: Optional[str] = Query(default=None),
                page: int = Query(default=1, ge=1),
                per_page: int = Query(default=50, ge=1, le=200),
                db: Session = Depends(get_db),
                user: User = Depends(require_role(
                    *_ALERT_ROLES, action="list_alerts", resource_type="alert"))):
    q = db.query(Alert)
    if severity is not None:
        q = q.filter(Alert.severity == severity)
    if status_ is not None:
        q = q.filter(Alert.status == status_)
    if rule_name is not None:
        q = q.filter(Alert.rule_name == rule_name)
    q = q.order_by(Alert.created_at.desc())
    return q.offset((page - 1) * per_page).limit(per_page).all()


@router.get("/stats", response_model=AlertStats)
def alert_stats(db: Session = Depends(get_db),
                user: User = Depends(require_role(
                    *_ALERT_ROLES, action="alert_stats", resource_type="alert"))):
    by_severity = dict(
        db.query(Alert.severity, func.count(Alert.id))
        .filter(Alert.status == C.ALERT_OPEN)
        .group_by(Alert.severity)
        .all()
    )
    by_status = dict(
        db.query(Alert.status, func.count(Alert.id))
        .group_by(Alert.status)
        .all()
    )
    return AlertStats(by_severity=by_severity, by_status=by_status)


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db),
             user: User = Depends(require_role(
                 *_ALERT_ROLES, action="get_alert", resource_type="alert"))):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerte introuvable")
    return alert


def _set_status(alert_id: int, new_status: str, action: str, request: Request,
                db: Session, user: User, extra: dict | None = None) -> Alert:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerte introuvable")
    old_status = alert.status
    alert.status = new_status
    if extra:
        for k, v in extra.items():
            setattr(alert, k, v)
    db.commit()
    db.refresh(alert)
    log_event(db, request=request, user=user, action=action,
              resource_type="alert", resource_id=alert.id,
              detail={"from": old_status, "to": alert.status})
    return alert


@router.patch("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: int, request: Request, db: Session = Depends(get_db),
                      user: User = Depends(require_role(
                          *_ALERT_ROLES, action="acknowledge_alert", resource_type="alert"))):
    return _set_status(alert_id, C.ALERT_ACKNOWLEDGED, "acknowledge_alert", request, db, user)


@router.patch("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: int, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(require_role(
                      *_ALERT_ROLES, action="resolve_alert", resource_type="alert"))):
    return _set_status(alert_id, C.ALERT_RESOLVED, "resolve_alert", request, db, user,
                       extra={"resolved_at": datetime.now(timezone.utc), "resolved_by": user.id})


@router.patch("/{alert_id}/false-positive", response_model=AlertOut)
def false_positive_alert(alert_id: int, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(require_role(
                             *_ALERT_ROLES, action="mark_false_positive_alert",
                             resource_type="alert"))):
    return _set_status(alert_id, C.ALERT_FALSE_POSITIVE, "mark_false_positive_alert",
                       request, db, user)


@agent_router.post("/scan")
def trigger_scan(request: Request, db: Session = Depends(get_db),
                 user: User = Depends(require_role(
                     C.ROLE_ADMIN, action="trigger_scan", resource_type="alert"))):
    created = scan(db)
    log_event(db, request=request, user=user, action="trigger_scan",
              resource_type="alert", detail={"new_alerts": len(created)})
    return {"new_alerts": len(created)}
