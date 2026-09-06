"""Regles de detection de l'agent de surveillance.

Chaque regle interroge la table `events` (le seul contrat d'observabilite lu par
l'agent, cf. app/events.py) avec des filtres/aggregations SQL — jamais de boucle
Python sur les lignes brutes. Une regle retourne une liste de dicts consommables
directement par `Alert(**data)`. Le sujet d'une alerte (pour la deduplication
"pas de doublon tant qu'une alerte est ouverte") est toujours `actor_username`
et/ou `source_ip`, les deux seuls champs d'identite portes par le modele `Alert`.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import constants as C
from ..models import Alert, Event

_LOGIN = "login"
_UPDATE_READING = "update_reading"


def _now():
    return datetime.now(timezone.utc)


def _has_open_alert(db: Session, rule_name: str, *,
                    actor_username: str | None = None,
                    source_ip: str | None = None) -> bool:
    """Vrai si une alerte non close existe deja pour ce (rule_name, sujet)."""
    q = db.query(Alert.id).filter(Alert.rule_name == rule_name, Alert.status == C.ALERT_OPEN)
    if actor_username is not None:
        q = q.filter(Alert.actor_username == actor_username)
    if source_ip is not None:
        q = q.filter(Alert.source_ip == source_ip)
    return db.query(q.exists()).scalar()


class BruteForceRule:
    """R1 — plusieurs echecs de connexion sur le MEME compte en peu de temps."""
    name = "brute_force"
    severity = C.SEVERITY_CRITICAL
    auto_action = C.AUTO_ACTION_LOCK

    def run(self, db: Session) -> list[dict]:
        since = _now() - timedelta(seconds=C.BRUTE_FORCE_WINDOW_SEC)
        rows = (
            db.query(
                Event.actor_username,
                func.count(Event.id).label("cnt"),
                func.max(Event.channel_ip).label("ip"),
                func.max(Event.timestamp).label("last_ts"),
            )
            .filter(
                Event.action == _LOGIN,
                Event.result == C.RESULT_FAILURE,
                Event.actor_username.isnot(None),
                Event.timestamp >= since,
            )
            .group_by(Event.actor_username)
            .having(func.count(Event.id) >= C.BRUTE_FORCE_THRESHOLD)
            .all()
        )
        alerts = []
        for username, cnt, ip, last_ts in rows:
            if _has_open_alert(db, self.name, actor_username=username):
                continue
            alerts.append({
                "rule_name": self.name,
                "severity": self.severity,
                "actor_username": username,
                "source_ip": ip,
                "description": (
                    f"{cnt} echecs de connexion sur le compte '{username}' "
                    f"en moins de {C.BRUTE_FORCE_WINDOW_SEC}s"
                ),
                "evidence": {
                    "failed_attempts": cnt,
                    "window_sec": C.BRUTE_FORCE_WINDOW_SEC,
                    "last_attempt": last_ts.isoformat() if last_ts else None,
                },
                "auto_action": self.auto_action,
            })
        return alerts


class AccountScanRule:
    """R2 — echecs de connexion sur de NOMBREUX comptes distincts depuis la meme IP
    (enumeration/scan de comptes, pas de cible unique a verrouiller)."""
    name = "account_scan"
    severity = C.SEVERITY_HIGH
    auto_action = None

    def run(self, db: Session) -> list[dict]:
        since = _now() - timedelta(seconds=C.SCAN_WINDOW_SEC)
        attempted = Event.detail["username"].as_string()
        rows = (
            db.query(
                Event.channel_ip,
                func.count(func.distinct(attempted)).label("cnt"),
            )
            .filter(
                Event.action == _LOGIN,
                Event.result == C.RESULT_FAILURE,
                Event.channel_ip.isnot(None),
                Event.timestamp >= since,
            )
            .group_by(Event.channel_ip)
            .having(func.count(func.distinct(attempted)) >= C.SCAN_THRESHOLD)
            .all()
        )
        alerts = []
        for ip, cnt in rows:
            if _has_open_alert(db, self.name, source_ip=ip):
                continue
            alerts.append({
                "rule_name": self.name,
                "severity": self.severity,
                "actor_username": None,
                "source_ip": ip,
                "description": (
                    f"{cnt} comptes distincts tentes depuis {ip} "
                    f"en moins de {C.SCAN_WINDOW_SEC}s"
                ),
                "evidence": {"distinct_accounts": cnt, "window_sec": C.SCAN_WINDOW_SEC},
                "auto_action": self.auto_action,
            })
        return alerts


class EscalationRule:
    """R3 — accumulation d'acces refuses (403) pour le meme acteur : tentative
    repetee d'agir hors de son role/perimetre."""
    name = "escalation"
    severity = C.SEVERITY_HIGH
    auto_action = None

    def run(self, db: Session) -> list[dict]:
        since = _now() - timedelta(seconds=C.ESCALATION_WINDOW_SEC)
        rows = (
            db.query(
                Event.actor_username,
                func.count(Event.id).label("cnt"),
                func.max(Event.channel_ip).label("ip"),
            )
            .filter(
                Event.result == C.RESULT_DENIED,
                Event.actor_username.isnot(None),
                Event.timestamp >= since,
            )
            .group_by(Event.actor_username)
            .having(func.count(Event.id) >= C.ESCALATION_THRESHOLD)
            .all()
        )
        alerts = []
        for username, cnt, ip in rows:
            if _has_open_alert(db, self.name, actor_username=username):
                continue
            alerts.append({
                "rule_name": self.name,
                "severity": self.severity,
                "actor_username": username,
                "source_ip": ip,
                "description": (
                    f"{cnt} acces refuses pour '{username}' "
                    f"en moins de {C.ESCALATION_WINDOW_SEC}s"
                ),
                "evidence": {"denied_count": cnt, "window_sec": C.ESCALATION_WINDOW_SEC},
                "auto_action": self.auto_action,
            })
        return alerts


class ConcurrentSessionRule:
    """R4 — connexions reussies du meme compte depuis des IP differentes en peu de
    temps (session concurrente / vol d'identifiants). Pas de seuil dedie dans
    constants.py : reutilise BRUTE_FORCE_WINDOW_SEC comme fenetre de simultaneite."""
    name = "concurrent_session"
    severity = C.SEVERITY_MEDIUM
    auto_action = C.AUTO_ACTION_FORCE_RELOGIN

    def run(self, db: Session) -> list[dict]:
        since = _now() - timedelta(seconds=C.BRUTE_FORCE_WINDOW_SEC)
        rows = (
            db.query(
                Event.actor_username,
                func.count(func.distinct(Event.channel_ip)).label("cnt"),
            )
            .filter(
                Event.action == _LOGIN,
                Event.result == C.RESULT_SUCCESS,
                Event.actor_username.isnot(None),
                Event.channel_ip.isnot(None),
                Event.timestamp >= since,
            )
            .group_by(Event.actor_username)
            .having(func.count(func.distinct(Event.channel_ip)) >= 2)
            .all()
        )
        alerts = []
        for username, cnt in rows:
            if _has_open_alert(db, self.name, actor_username=username):
                continue
            ips = [
                row[0] for row in db.query(func.distinct(Event.channel_ip)).filter(
                    Event.action == _LOGIN, Event.result == C.RESULT_SUCCESS,
                    Event.actor_username == username, Event.timestamp >= since,
                ).all()
            ]
            alerts.append({
                "rule_name": self.name,
                "severity": self.severity,
                "actor_username": username,
                "source_ip": ips[0] if ips else None,
                "description": (
                    f"Compte '{username}' connecte depuis {cnt} IP differentes "
                    f"en moins de {C.BRUTE_FORCE_WINDOW_SEC}s"
                ),
                "evidence": {"distinct_ips": ips, "window_sec": C.BRUTE_FORCE_WINDOW_SEC},
                "auto_action": self.auto_action,
            })
        return alerts


class ExfiltrationRule:
    """R5 — volume exporte/telecharge en un seul evenement au-dela du seuil
    (export CSV, telechargement de document). Seuil par evenement, pas de fenetre
    dediee : reutilise ESCALATION_WINDOW_SEC comme horizon de detection."""
    name = "exfiltration"
    severity = C.SEVERITY_CRITICAL
    auto_action = C.AUTO_ACTION_BLOCK_EXPORT

    def run(self, db: Session) -> list[dict]:
        since = _now() - timedelta(seconds=C.ESCALATION_WINDOW_SEC)
        rows = (
            db.query(Event)
            .filter(
                Event.action.in_(["export_readings", "document_download"]),
                Event.result == C.RESULT_SUCCESS,
                Event.volume.isnot(None),
                Event.volume >= C.EXFILTRATION_VOLUME,
                Event.timestamp >= since,
            )
            .all()
        )
        alerts = []
        for ev in rows:
            if _has_open_alert(db, self.name, actor_username=ev.actor_username):
                continue
            alerts.append({
                "rule_name": self.name,
                "severity": self.severity,
                "actor_username": ev.actor_username,
                "source_ip": ev.channel_ip,
                "description": (
                    f"Volume {ev.volume} exporte par '{ev.actor_username}' "
                    f"via '{ev.action}' (seuil {C.EXFILTRATION_VOLUME})"
                ),
                "evidence": {"event_id": ev.id, "volume": ev.volume, "action": ev.action},
                "auto_action": self.auto_action,
            })
        return alerts


class FalsificationRule:
    """R6 — modification d'un releve deja valide (post_validation=True dans le
    detail de l'evenement `update_reading`). Pas de seuil : toute occurrence est un
    signal d'integrite. Pas d'auto-reponse (alerte seule)."""
    name = "falsification"
    severity = C.SEVERITY_HIGH
    auto_action = None

    def run(self, db: Session) -> list[dict]:
        since = _now() - timedelta(seconds=C.ESCALATION_WINDOW_SEC)
        post_validation = Event.detail["post_validation"].as_boolean()
        rows = (
            db.query(
                Event.actor_username,
                func.count(Event.id).label("cnt"),
                func.max(Event.channel_ip).label("ip"),
            )
            .filter(
                Event.action == _UPDATE_READING,
                Event.result == C.RESULT_SUCCESS,
                post_validation.is_(True),
                Event.timestamp >= since,
            )
            .group_by(Event.actor_username)
            .all()
        )
        alerts = []
        for username, cnt, ip in rows:
            if _has_open_alert(db, self.name, actor_username=username):
                continue
            alerts.append({
                "rule_name": self.name,
                "severity": self.severity,
                "actor_username": username,
                "source_ip": ip,
                "description": (
                    f"{cnt} modification(s) d'un releve deja valide par '{username}'"
                ),
                "evidence": {"count": cnt},
                "auto_action": self.auto_action,
            })
        return alerts


class NightAccessRule:
    """R7 — connexion reussie hors plage horaire normale
    ([NIGHT_END_HOUR, NIGHT_START_HOUR[). Alerte seule."""
    name = "night_access"
    severity = C.SEVERITY_MEDIUM
    auto_action = None

    def run(self, db: Session) -> list[dict]:
        since = _now() - timedelta(seconds=C.ESCALATION_WINDOW_SEC)
        hour = func.extract("hour", Event.timestamp)
        rows = (
            db.query(
                Event.actor_username,
                func.count(Event.id).label("cnt"),
                func.max(Event.channel_ip).label("ip"),
            )
            .filter(
                Event.action == _LOGIN,
                Event.result == C.RESULT_SUCCESS,
                Event.actor_username.isnot(None),
                Event.timestamp >= since,
                (hour >= C.NIGHT_START_HOUR) | (hour < C.NIGHT_END_HOUR),
            )
            .group_by(Event.actor_username)
            .all()
        )
        alerts = []
        for username, cnt, ip in rows:
            if _has_open_alert(db, self.name, actor_username=username):
                continue
            alerts.append({
                "rule_name": self.name,
                "severity": self.severity,
                "actor_username": username,
                "source_ip": ip,
                "description": (
                    f"Connexion de '{username}' hors plage horaire normale "
                    f"({C.NIGHT_START_HOUR}h-{C.NIGHT_END_HOUR}h)"
                ),
                "evidence": {"count": cnt},
                "auto_action": self.auto_action,
            })
        return alerts


class ActivitySpikeRule:
    """R8 — volume d'activite recent d'un acteur >= ACTIVITY_SPIKE_MULTIPLIER fois sa
    moyenne habituelle (baseline = 24h precedentes). Deux aggregations SQL groupees
    par acteur ; seule leur combinaison (petit nombre de groupes, pas d'evenements
    bruts) se fait en Python. Alerte seule."""
    name = "activity_spike"
    severity = C.SEVERITY_MEDIUM
    auto_action = None
    _BASELINE_HOURS = 24

    def run(self, db: Session) -> list[dict]:
        now = _now()
        recent_since = now - timedelta(seconds=C.SCAN_WINDOW_SEC)
        baseline_since = recent_since - timedelta(hours=self._BASELINE_HOURS)
        baseline_windows = (self._BASELINE_HOURS * 3600) / C.SCAN_WINDOW_SEC

        recent = dict(
            db.query(Event.actor_username, func.count(Event.id))
            .filter(Event.actor_username.isnot(None), Event.timestamp >= recent_since)
            .group_by(Event.actor_username)
            .all()
        )
        baseline = dict(
            db.query(Event.actor_username, func.count(Event.id))
            .filter(
                Event.actor_username.isnot(None),
                Event.timestamp >= baseline_since,
                Event.timestamp < recent_since,
            )
            .group_by(Event.actor_username)
            .all()
        )

        alerts = []
        for username, recent_cnt in recent.items():
            baseline_cnt = baseline.get(username, 0)
            if baseline_cnt <= 0:
                continue
            baseline_avg = baseline_cnt / baseline_windows
            if recent_cnt < baseline_avg * C.ACTIVITY_SPIKE_MULTIPLIER:
                continue
            if _has_open_alert(db, self.name, actor_username=username):
                continue
            alerts.append({
                "rule_name": self.name,
                "severity": self.severity,
                "actor_username": username,
                "source_ip": None,
                "description": (
                    f"Activite de '{username}' x{round(recent_cnt / baseline_avg, 1)} "
                    f"par rapport a sa moyenne habituelle"
                ),
                "evidence": {
                    "recent_count": recent_cnt,
                    "baseline_avg": round(baseline_avg, 3),
                    "window_sec": C.SCAN_WINDOW_SEC,
                },
                "auto_action": self.auto_action,
            })
        return alerts


RULES = [
    BruteForceRule(),
    AccountScanRule(),
    EscalationRule(),
    ConcurrentSessionRule(),
    ExfiltrationRule(),
    FalsificationRule(),
    NightAccessRule(),
    ActivitySpikeRule(),
]
