"""Generateur de trafic HTTP pour Plateforme-DGRE.

Tourne depuis l'hote, en HTTP via la passerelle nginx (:8080) -- PAS dans le
conteneur API. Sert a peupler un baseline de 28 jours de releves realistes puis a
declencher chacune des 6 regles de l'agent de surveillance (api/app/agent/rules.py)
avec un scenario d'attaque dedie, pour verifier que le pipeline detection -> alerte
fonctionne de bout en bout sur des donnees produites via l'API (pas des fixtures
injectees directement en base).

Usage :
    python scripts/generate_traffic.py baseline
    python scripts/generate_traffic.py attack brute-force|account-scan|escalation|
        exfiltration|falsification|all
    python scripts/generate_traffic.py scan
    python scripts/generate_traffic.py full
"""
import argparse
import csv
import io
import os
import random
import sys
import time
from datetime import date, timedelta

import requests

BASE_URL = os.environ.get("TRAFFIC_BASE_URL", "http://localhost:8080")

ADMIN = ("admin", "admin123")
AGENTS = [("aymen", "aymen123"), ("jilani", "jilani123"),
          ("ammar", "ammar123"), ("hanen", "hanen123")]
RESPONSABLE = ("dir_surface", "dir_surface123")

CONV_STATION_CODES = ["PLV-003", "PLV-004", "PLV-005", "PLV-008", "PLV-012",
                       "PLV-014", "PLV-016", "PLV-017", "PLV-018"]
BASELINE_DAYS = 28
VALIDATE_RATE = 0.8


# ---------- HTTP helpers ----------

def api_request(method: str, path: str, token: str | None = None, **kwargs) -> requests.Response:
    """Requete API avec retry sur 429 (rate-limit nginx) : le baseline envoie des
    centaines de requetes d'affilee, plus vite que les zones limit_req ne les laissent
    passer en regime permanent."""
    url = f"{BASE_URL}{path}"
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # zone "login" (5r/m) met ~12s a rendre un jeton ; zone "api" (15r/s) beaucoup
    # moins -- pas de Retry-After renvoye par nginx, donc on choisit le fallback
    # selon la route plutot qu'une constante unique.
    fallback_sleep = 12.0 if path == "/auth/login" else 1.0
    for _ in range(8):
        resp = requests.request(method, url, headers=headers, timeout=15, **kwargs)
        if resp.status_code == 429:
            time.sleep(float(resp.headers.get("Retry-After", fallback_sleep)))
            continue
        return resp
    return resp


def raw_login(username: str, password: str) -> requests.Response:
    return api_request("POST", "/auth/login", data={"username": username, "password": password})


def login(username: str, password: str) -> str:
    resp = raw_login(username, password)
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_station_map(admin_token: str) -> dict[str, int]:
    resp = api_request("GET", "/stations", token=admin_token)
    resp.raise_for_status()
    by_code = {s["code"]: s["id"] for s in resp.json()}
    missing = [c for c in CONV_STATION_CODES if c not in by_code]
    if missing:
        print(f"  ATTENTION : stations introuvables en base : {missing}")
    return {c: by_code[c] for c in CONV_STATION_CODES if c in by_code}


def _unlock_agents_if_needed(admin_token: str):
    """L'attaque brute-force verrouille reellement le compte cible (auto-reponse de la
    regle brute_force). Deverrouille les 4 agents avant le baseline pour que le script
    reste rejouable apres un `attack brute-force` sans intervention manuelle."""
    resp = api_request("GET", "/admin/users", token=admin_token)
    resp.raise_for_status()
    by_username = {u["username"]: u for u in resp.json()}
    for username, _ in AGENTS:
        u = by_username.get(username)
        if u and u["locked"]:
            api_request("POST", f"/admin/users/{u['id']}/unlock", token=admin_token)
            print(f"  (compte '{username}' etait verrouille, deverrouille)")


# ---------- baseline ----------

def generate_baseline():
    print(f"== Baseline ({BASELINE_DAYS} jours x {len(CONV_STATION_CODES)} stations) ==")
    admin_token = login(*ADMIN)
    station_ids = list(get_station_map(admin_token).values())
    if not station_ids:
        print("Aucune station conventionnelle trouvee, abandon du baseline.")
        return

    _unlock_agents_if_needed(admin_token)
    agent_tokens = [login(u, p) for u, p in AGENTS]
    created_ids: list[int] = []
    created_count = 0
    skipped_count = 0

    today = date.today()
    for day_idx in range(BASELINE_DAYS):
        the_date = (today - timedelta(days=BASELINE_DAYS - day_idx)).isoformat()
        day_created = 0
        for st_idx, station_id in enumerate(station_ids):
            token = agent_tokens[(day_idx * len(station_ids) + st_idx) % len(agent_tokens)]
            valeur = round(random.uniform(0.0, 15.0), 1)
            resp = api_request("POST", "/readings", token=token,
                               json={"station_id": station_id, "date": the_date, "valeur": valeur})
            if resp.status_code == 201:
                created_ids.append(resp.json()["id"])
                created_count += 1
                day_created += 1
            elif resp.status_code == 409:
                skipped_count += 1
            else:
                print(f"  ! echec creation station={station_id} date={the_date} -> "
                      f"{resp.status_code} {resp.text[:200]}")
        print(f"Jour {day_idx + 1}/{BASELINE_DAYS} ({the_date}) : {day_created} releves crees")

    print(f"Total releves crees : {created_count} (ignores car deja existants : {skipped_count})")

    resp_token = login(*RESPONSABLE)
    to_validate = [rid for rid in created_ids if random.random() < VALIDATE_RATE]
    validated_ids: list[int] = []
    for rid in to_validate:
        resp = api_request("POST", f"/readings/{rid}/validate", token=resp_token,
                           json={"decision": "validate"})
        if resp.status_code == 200:
            validated_ids.append(rid)
    print(f"Releves valides par {RESPONSABLE[0]} : {len(validated_ids)}/{len(created_ids)} "
          f"(cible ~{int(VALIDATE_RATE * 100)}%)")
    if validated_ids:
        print(f"  (ex. releve valide garde de cote : id={validated_ids[0]})")

    export_station_id = station_ids[0]
    resp = api_request("GET", "/readings/export", token=resp_token,
                       params={"station_id": export_station_id})
    lines = resp.text.strip().splitlines()
    print(f"Export normal (station_id={export_station_id}) par {RESPONSABLE[0]} : "
          f"{max(len(lines) - 1, 0)} lignes de donnees")
    print("== Baseline terminee ==\n")


# ---------- attaques ----------

def attack_brute_force():
    print("== Attaque : brute force (comptes reels) ==")
    target, _real_password = AGENTS[3]  # hanen
    wrong_password = "mot-de-passe-invalide-000"
    n_attempts = 6
    for i in range(1, n_attempts + 1):
        resp = raw_login(target, wrong_password)
        print(f"  Tentative {i}/{n_attempts} sur '{target}' -> {resp.status_code}")
        if i < n_attempts:
            time.sleep(5)
    print("== Fin brute force (attendu : 401 x3 puis 403 verrouille x3) ==\n")


def attack_account_scan():
    print("== Attaque : scan de comptes (usernames fictifs) ==")
    fake_users = [f"scan_ghost_{i:02d}" for i in range(1, 11)]
    for i, username in enumerate(fake_users, start=1):
        resp = raw_login(username, "peu-importe-123")
        print(f"  Tentative {i}/{len(fake_users)} (compte fictif '{username}') -> {resp.status_code}")
        if i < len(fake_users):
            time.sleep(15)
    print("== Fin scan de comptes ==\n")


def attack_escalation():
    print("== Attaque : escalade de privileges (agent -> route admin) ==")
    token = login("jilani", "jilani123")
    for i in range(1, 4):
        resp = api_request("GET", "/admin/users", token=token)
        print(f"  Appel {i}/3 GET /admin/users (jilani, role agent) -> {resp.status_code}")
    print("== Fin escalade ==\n")


def attack_exfiltration():
    print("== Attaque : exfiltration (export complet) ==")
    token = login(*ADMIN)
    resp = api_request("GET", "/readings/export", token=token)
    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    n_data_rows = max(len(rows) - 1, 0)
    print(f"  Export complet (admin, sans station_id) -> {resp.status_code}, "
          f"{n_data_rows} lignes de donnees")
    print("== Fin exfiltration ==\n")


def attack_falsification():
    print("== Attaque : falsification post-validation ==")
    token = login(*RESPONSABLE)
    resp = api_request("GET", "/readings", token=token, params={"status": "validated"})
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        print("  Aucun releve valide trouve -- lancez d'abord le baseline. Abandon.")
        return
    reading_id = rows[0]["id"]
    new_valeur = round(random.uniform(0.0, 15.0), 1)
    resp = api_request("PATCH", f"/readings/{reading_id}", token=token,
                       json={"valeur_recalculee": new_valeur, "raison": "correction test"})
    print(f"  PATCH /readings/{reading_id} (deja valide) par {RESPONSABLE[0]} -> {resp.status_code}")
    print("== Fin falsification ==\n")


_ATTACKS = {
    "brute-force": attack_brute_force,
    "account-scan": attack_account_scan,
    "escalation": attack_escalation,
    "exfiltration": attack_exfiltration,
    "falsification": attack_falsification,
}

# Ordre d'execution pour "all"/"full" : les attaques instantanees (escalation,
# exfiltration, falsification, dont les regles reutilisent la fenetre large de 600s)
# passent en premier ; account-scan (fenetre 300s, ~135s de duree) puis brute-force
# (fenetre 120s, ~25s de duree) passent en dernier, brute-force juste avant le scan,
# pour que chaque regle voie encore ses evenements dans sa fenetre au moment du scan.
_ATTACK_ORDER = ["escalation", "exfiltration", "falsification", "account-scan", "brute-force"]


def run_all_attacks():
    for name in _ATTACK_ORDER:
        _ATTACKS[name]()


# ---------- scan / rapport ----------

def trigger_scan_and_report():
    print("== Scan de l'agent + rapport ==")
    token = login(*ADMIN)
    resp = api_request("POST", "/agent/scan", token=token)
    resp.raise_for_status()
    print(f"POST /agent/scan -> new_alerts = {resp.json()['new_alerts']}")

    resp = api_request("GET", "/alerts/stats", token=token)
    resp.raise_for_status()
    stats = resp.json()
    print(f"Stats par severite (ouvertes) : {stats['by_severity']}")
    print(f"Stats par statut : {stats['by_status']}")

    resp = api_request("GET", "/alerts", token=token, params={"per_page": 200})
    resp.raise_for_status()
    alerts = resp.json()
    print(f"Alertes ({len(alerts)}) :")
    for a in alerts:
        print(f"  [{a['severity']:8s}] {a['rule_name']:22s} {a['description']}")
    print("== Fin scan ==\n")


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(description="Generateur de trafic Plateforme-DGRE")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("baseline", help="genere 28 jours de releves realistes")
    sub.add_parser("scan", help="declenche le scan de l'agent et affiche le rapport")
    sub.add_parser("full", help="baseline + toutes les attaques + scan")

    p_attack = sub.add_parser("attack", help="joue un scenario d'attaque")
    p_attack.add_argument("target", choices=list(_ATTACKS.keys()) + ["all"])

    args = parser.parse_args()

    if args.command == "baseline":
        generate_baseline()
    elif args.command == "scan":
        trigger_scan_and_report()
    elif args.command == "attack":
        if args.target == "all":
            run_all_attacks()
        else:
            _ATTACKS[args.target]()
    elif args.command == "full":
        generate_baseline()
        run_all_attacks()
        trigger_scan_and_report()


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError as exc:
        print(f"Impossible de joindre {BASE_URL} : {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.HTTPError as exc:
        print(f"Erreur HTTP inattendue : {exc}", file=sys.stderr)
        sys.exit(1)
