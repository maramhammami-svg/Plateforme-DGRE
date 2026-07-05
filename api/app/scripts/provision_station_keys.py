"""Provisionne les cles d'authentification station (acte unique, lance a la main).

Usage (depuis la racine du repo) :
    docker compose exec api python -m app.scripts.provision_station_keys
    docker compose exec api python -m app.scripts.provision_station_keys --all   # rotation

Par defaut, ne traite que les stations sans cle (hashed_station_key is None) :
idempotent, relancable sans risque. `--all` regenere la cle de toutes les
stations (rotation), y compris celles qui en ont deja une.

Ecrit station_keys.json (cle = code station, valeur = cle en clair) a la
racine du process (ex. /app/station_keys.json dans le conteneur). Ce fichier
contient des secrets en clair : jamais committe (voir .gitignore).
"""
import argparse
import json

from ..database import SessionLocal
from ..models import Station
from ..security import generate_station_key, hash_password
from ..events import log_event
from .. import constants as C

OUTPUT_PATH = "station_keys.json"


def provision_station_keys(all_stations: bool = False) -> None:
    db = SessionLocal()
    try:
        q = db.query(Station)
        if not all_stations:
            q = q.filter(Station.hashed_station_key.is_(None))
        stations = q.all()

        keys_clair: dict[str, str] = {}
        for st in stations:
            cle = generate_station_key()
            st.hashed_station_key = hash_password(cle)
            keys_clair[st.code] = cle

        db.commit()

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(keys_clair, f, indent=2, ensure_ascii=False)

        log_event(db, request=None, user=None,
                  action="provision_station_keys", result=C.RESULT_SUCCESS,
                  resource_type="station", volume=len(stations),
                  detail={"all": all_stations, "provisioned": len(stations)})

        print(f"Provisioning termine : {len(stations)} station(s) traitee(s).")
        print(f"Cles en clair ecrites dans {OUTPUT_PATH}")
    finally:
        db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Provisionne les cles station")
    p.add_argument("--all", action="store_true",
                   help="regenerer la cle de toutes les stations (rotation)")
    args = p.parse_args()
    provision_station_keys(all_stations=args.all)
