"""Import des fichiers MIS (telemetrie HYDRACCESS) dans raw_readings.

Usage :
    python -m app.scripts.import_mis /tmp/mis_data.zip

Entree : un .zip contenant un dossier par gouvernorat, chacun rempli de
fichiers .MIS (un fichier peut contenir plusieurs blocs capteur) :

    <STATION>1487902313</STATION><SENSOR>0006</SENSOR><DATEFORMAT>YYYYMMDD</DATEFORMAT>
    20260830;230500;0.00
    20260830;231000;0.00

Cree automatiquement les stations inconnues (type automatique/pluviometrie,
coordonnees placeholder 0.0/0.0 - A CORRIGER MANUELLEMENT, le format MIS ne
transporte aucune coordonnee). Pas d'idempotence ligne par ligne (trop lent
sur ~100K+ lignes) : une reexecution duplique les mesures deja importees."""
import argparse
import math
import os
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone

from ..database import SessionLocal
from ..models import Station, RawReading, UniteOrganisationnelle
from ..events import log_event
from .. import constants as C

UNITE_RATTACHEMENT = "Service Réseaux de mesure"
BATCH_SIZE = 5000
PROGRESS_EVERY = 500

HEADER_RE = re.compile(r"<STATION>(\d+)</STATION><SENSOR>(\d+)</SENSOR>")

GOVERNORATE_CENTROIDS = {
    "Tunis": (36.8065, 10.1815),
    "Ariana": (36.8625, 10.1956),
    "Ben_Arous": (36.7533, 10.2282),
    "Manouba": (36.8081, 10.0972),
    "Nabeul": (36.4561, 10.7376),
    "Zaghouan": (36.4028, 10.1425),
    "Bizerte": (37.2744, 9.8739),
    "Beja": (36.7256, 9.1817),
    "Jendouba": (36.5011, 8.7803),
    "Kef": (36.1826, 8.7148),
    "Siliana": (36.0836, 9.3708),
    "Kairouan": (35.6781, 10.0963),
    "Kasserine": (35.1676, 8.8365),
    "Sidi_Bouzid": (35.0381, 9.4858),
    "Sousse": (35.8256, 10.6369),
    "Monastir": (35.7643, 10.8113),
    "Mahdia": (35.5047, 11.0622),
    "Sfax": (34.7406, 10.7603),
    "Gafsa": (34.4250, 8.7842),
    "Tozeur": (33.9197, 8.1335),
    "Kebili": (33.7044, 8.9690),
    "Gabes": (33.8815, 10.0982),
    "Medenine": (33.3549, 10.5055),
    "Tataouine": (32.9297, 10.4518),
}


def _parse_value(raw: str):
    """'0.00' -> 0.0 ; vide/non-numerique -> None (is_missing)."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        v = float(raw)
    except ValueError:
        return None
    if not math.isfinite(v):
        return None
    return v


def _parse_mis_file(path: str):
    """Genere (station_code, sensor_code, timestamp, valeur) pour un fichier .MIS."""
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        content = f.read()
    lines = content.replace("\r\n", "\n").split("\n")

    station_code = sensor_code = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = HEADER_RE.search(line)
        if m:
            station_code, sensor_code = m.group(1), m.group(2)
            continue
        if station_code is None:
            continue  # donnees avant tout en-tete : ignorees
        parts = line.split(";")
        if len(parts) != 3:
            continue
        date_str, time_str, val_str = parts
        try:
            ts = datetime.strptime(date_str + time_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        yield station_code, sensor_code, ts, _parse_value(val_str)


def run(zip_path: str):
    tmpdir = tempfile.mkdtemp(prefix="import_mis_")
    db = SessionLocal()
    stations_created = files_done = readings_count = errors = 0
    station_cache: dict[str, int] = {}
    batch: list[RawReading] = []
    unknown_governorates: list[str] = []

    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmpdir)

        unite = db.query(UniteOrganisationnelle).filter(
            UniteOrganisationnelle.nom == UNITE_RATTACHEMENT
        ).first()
        unite_id = unite.id if unite is not None else None

        for code, id_ in db.query(Station.code, Station.id).all():
            station_cache[code] = id_

        mis_files = []
        for governorate in sorted(os.listdir(tmpdir)):
            gdir = os.path.join(tmpdir, governorate)
            if not os.path.isdir(gdir):
                continue
            for fname in sorted(os.listdir(gdir)):
                if fname.upper().endswith(".MIS"):
                    mis_files.append((governorate, os.path.join(gdir, fname)))

        total = len(mis_files)

        def flush():
            nonlocal batch
            if batch:
                db.add_all(batch)
                db.commit()
                batch = []

        for governorate, fpath in mis_files:
            try:
                for station_code, sensor_code, ts, valeur in _parse_mis_file(fpath):
                    station_id = station_cache.get(station_code)
                    if station_id is None:
                        lat, lon = GOVERNORATE_CENTROIDS.get(governorate, (0.0, 0.0))
                        if governorate not in GOVERNORATE_CENTROIDS and governorate not in unknown_governorates:
                            unknown_governorates.append(governorate)
                        st = Station(
                            code=station_code,
                            name=f"Station {station_code}",
                            type=C.STATION_TYPE_AUTO,
                            parameter=C.PARAM_PLUVIO,
                            unit=C.UNIT_MM,
                            governorate=governorate,
                            sampling_interval_min=5,
                            latitude=lat,
                            longitude=lon,
                            unite_id=unite_id,
                        )
                        db.add(st)
                        db.commit()
                        db.refresh(st)
                        station_id = st.id
                        station_cache[station_code] = station_id
                        stations_created += 1

                    batch.append(RawReading(
                        station_id=station_id,
                        timestamp=ts,
                        valeur=valeur,
                        is_missing=valeur is None,
                        source=C.SOURCE_IMPORT,
                    ))
                    readings_count += 1
                    if len(batch) >= BATCH_SIZE:
                        flush()
            except Exception as e:
                errors += 1
                print(f"Erreur sur {fpath} : {e}", file=sys.stderr)

            files_done += 1
            if files_done % PROGRESS_EVERY == 0:
                print(f"... {files_done}/{total} fichiers traites, {readings_count} mesures")

        flush()

        log_event(
            db, request=None, user=None,
            action="import_mis", result=C.RESULT_SUCCESS,
            resource_type="raw_reading", volume=readings_count,
            detail={"fichiers": files_done, "stations_creees": stations_created,
                    "erreurs": errors},
        )
        print(f"Import termine : {stations_created} stations creees, "
              f"{files_done} fichiers traites, {readings_count} mesures importees, "
              f"{errors} erreurs ignorees.")
        if unknown_governorates:
            print(f"⚠️ Gouvernorats non reconnus, coordonnées (0,0) — "
                  f"à corriger manuellement : {', '.join(unknown_governorates)}")
    finally:
        db.close()
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Import fichiers MIS (telemetrie HYDRACCESS)")
    p.add_argument("zip_path", help="Chemin du .zip contenant les dossiers gouvernorat")
    args = p.parse_args()
    run(args.zip_path)
