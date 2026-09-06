"""Moteur de l'agent : execute toutes les regles, persiste les alertes,
declenche l'auto-reponse quand elle existe, et journalise chaque alerte comme
evenement (action="agent_alert") pour que le contrat d'observabilite reste
complet meme pour l'activite de l'agent lui-meme."""
from sqlalchemy.orm import Session

from .. import constants as C
from ..events import log_event
from ..models import Alert, User
from .rules import RULES


def _apply_auto_response(db: Session, alert: Alert) -> None:
    """Seule l'action de verrouillage est reellement appliquee aujourd'hui : les
    autres valeurs (block_export, force_relogin) sont enregistrees sur l'alerte
    pour traitement manuel, faute de mecanisme d'application (pas de gating export,
    pas de revocation de JWT dans ce systeme sans etat)."""
    if alert.auto_action == C.AUTO_ACTION_LOCK and alert.actor_username:
        user = db.query(User).filter(User.username == alert.actor_username).first()
        if user is not None and not user.locked:
            user.locked = 1
            db.commit()


def scan(db: Session) -> list[Alert]:
    """Execute toutes les regles de l'agent et retourne les alertes creees."""
    created: list[Alert] = []
    for rule in RULES:
        for data in rule.run(db):
            alert = Alert(**data)
            db.add(alert)
            db.commit()
            db.refresh(alert)

            _apply_auto_response(db, alert)

            log_event(
                db, request=None, user=None, action="agent_alert",
                resource_type="alert", resource_id=alert.id,
                detail={
                    "rule_name": alert.rule_name,
                    "severity": alert.severity,
                    "actor_username": alert.actor_username,
                    "source_ip": alert.source_ip,
                    "auto_action": alert.auto_action,
                },
            )
            created.append(alert)
    return created
