"""Import des stations reelles depuis yasra.xlsx (acte unique, lance a la main).

Usage (depuis la racine du repo) :
    docker compose cp yasra.xlsx api:/tmp/yasra.xlsx
    docker compose exec api python -m app.scripts.import_stations /tmp/yasra.xlsx

Convertit les coordonnees UTM 32N (EPSG:32632) -> WGS84 (EPSG:4326).
Rattache toutes les stations au "Service Reseaux de mesure".
Idempotent : une station dont le code existe deja est ignoree (relançable).
"""
import sys
import argparse
import openpyxl
from pyproj import Transformer

from ..database import SessionLocal
from ..models import Station, UniteOrganisationnelle
from ..events import log_event
from .. import constants as C

UNITE_RATTACHEMENT = "Service Réseaux de mesure"
DEFAULT_XLSX = "/tmp/yasra.xlsx"

_transformer = Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)


def utm_to_wgs84(x: float, y: float) -> tuple[float, float]:
    lon, lat = _transformer.transform(x, y)
    return round(lat, 6), round(lon, 6)


def import_stations(path: str) -> None:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Feuil1"]

    db = SessionLocal()
    try:
        unite = db.query(UniteOrganisationnelle).filter(
            UniteOrganisationnelle.nom == UNITE_RATTACHEMENT
        ).first()
        if unite is None:
            sys.exit(f"ARRET : unite '{UNITE_RATTACHEMENT}' introuvable. "
                     "Verifie le seed avant l'import.")

        existing = {c for (c,) in db.query(Station.code).all()}
        inserted, skipped, rejected = 0, 0, []

        for row in ws.iter_rows(min_row=2, values_only=True):
            code, name, x, y = row[0], row[1], row[2], row[3]
            if code is None and name is None:
                continue
            code, name = str(code).strip(), str(name).strip()

            if code in existing:
                skipped += 1
                continue
            try:
                lat, lon = utm_to_wgs84(x, y)
            except Exception as e:
                rejected.append({"code": code, "raison": f"conversion: {e}"})
                continue
            if not (30 <= lat <= 38 and 7 <= lon <= 12):
                rejected.append({"code": code,
                                 "raison": f"hors boite lat={lat} lon={lon}"})
                continue

            db.add(Station(
                code=code, name=name,
                type=C.STATION_TYPE_CONV,
                parameter=C.PARAM_PLUVIO,
                unit=C.UNIT_MM,
                sampling_interval_min=None,
                latitude=lat, longitude=lon,
                altitude_m=None, governorate=None,
                unite_id=unite.id,
                hashed_station_key=None,
            ))
            existing.add(code)
            inserted += 1

        db.commit()

        log_event(db, request=None, user=None,
                  action="import_stations", result=C.RESULT_SUCCESS,
                  resource_type="station", volume=inserted,
                  detail={"source": "yasra.xlsx", "inserted": inserted,
                          "skipped": skipped, "rejected": len(rejected)})

        print(f"Import termine : {inserted} inserees, {skipped} ignorees, "
              f"{len(rejected)} rejetees.")
        for r in rejected:
            print("  rejet:", r)
    finally:
        db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Import stations yasra.xlsx")
    p.add_argument("xlsx", nargs="?", default=DEFAULT_XLSX,
                   help=f"chemin du xlsx (defaut {DEFAULT_XLSX})")
    import_stations(p.parse_args().xlsx)
