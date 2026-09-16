"""Scan automatique de l'agent en tache de fond.

Thread daemon unique (demo mono-worker uvicorn) qui appelle scan() toutes les
AGENT_SCAN_INTERVAL_SEC secondes, avec sa propre session (fermee apres chaque
scan). Une exception ne tue jamais le thread. Le scan automatique n'emet PAS
d'evenement propre (sinon ~1440 evenements/jour qui fausseraient
ActivitySpikeRule) : seules les alertes creees sont journalisees par le moteur
(action="agent_alert"). La boucle attend d'abord l'intervalle, puis scanne :
pas de scan concurrent du seed au demarrage."""
import threading
from datetime import datetime, timezone

from .. import constants as C
from ..database import SessionLocal
from .engine import scan

_lock = threading.Lock()
_stop = threading.Event()
_thread = None
_state = {
    "running": False,
    "interval_sec": C.AGENT_SCAN_INTERVAL_SEC,
    "last_scan_at": None,
    "last_scan_new_alerts": None,
    "last_error": None,
    "scan_count": 0,
}


def get_state() -> dict:
    with _lock:
        return dict(_state)


def run_once():
    """Un scan complet ; met a jour l'etat. Retourne le nb d'alertes creees, ou None si echec."""
    db = SessionLocal()
    try:
        created = scan(db)
        with _lock:
            _state["last_scan_at"] = datetime.now(timezone.utc).isoformat()
            _state["last_scan_new_alerts"] = len(created)
            _state["last_error"] = None
            _state["scan_count"] += 1
        return len(created)
    except Exception as exc:  # un scan en echec ne doit jamais tuer le thread
        db.rollback()
        with _lock:
            _state["last_error"] = f"{type(exc).__name__}: {exc}"
        print(f"[agent-scheduler] scan en echec : {exc!r}", flush=True)
        return None
    finally:
        db.close()


def _loop(interval: int) -> None:
    while not _stop.wait(interval):
        run_once()


def start(interval: int = C.AGENT_SCAN_INTERVAL_SEC) -> None:
    """Idempotent : ne lance pas de second thread si un thread tourne deja."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _stop.clear()
        _thread = threading.Thread(target=_loop, args=(interval,),
                                   name="agent-scheduler", daemon=True)
        _state["running"] = True
        _state["interval_sec"] = interval
        _thread.start()


def stop(timeout: float = 5.0) -> None:
    global _thread
    _stop.set()
    t = _thread
    if t is not None:
        t.join(timeout)
    with _lock:
        _thread = None
        _state["running"] = False
