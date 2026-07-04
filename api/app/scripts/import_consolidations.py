"""Import du resume annuel (yasra.xlsx) dans la table consolidations.

Usage :
    python -m app.scripts.import_consolidations /tmp/yasra.xlsx --annee 2024

L'annee hydro N'EST PAS dans le fichier : elle est passee en argument.
Une execution = une annee. Idempotent : une ligne (station, annee) existante
est ignoree. Valeurs reprises telles quelles (aucun recalcul)."""
import argparse
import sys

import openpyxl
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Station, Consolidation
from ..events import log_event

COL_CODE = 0
COL_MONTHS = list(range(4, 16))     # SEPT..AOUT
COL_SEASONS = list(range(16, 20))   # AUTO, HIVER, PRINT, ETE
COL_TOTAL, COL_MOY, COL_PCT = 20, 21, 22

MONTH_FIELDS = ["sept", "octo", "nove", "dece", "janv", "fevr",
                "mars", "avri", "mai", "juin", "juil", "aout"]
SEASON_FIELDS = ["automne", "hiver", "printemps", "ete"]


def _num(v):
    """Cellule -> float ou None. 0 reste 0.0 ; vide/None -> None."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _code(v):
    """CODE (int dans le fichier) -> str, pour matcher Station.code."""
    if v is None:
        return None
    if isinstance(v, float):
        v = int(v)
    return str(v).strip()


def run(path: str, annee: int):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Feuil1"]

    db: Session = SessionLocal()
    inserted = rejected = ignored = 0
    rejets = []
    try:
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                continue  # en-tete
            code = _code(row[COL_CODE])
            if not code:
                continue  # ligne vide

            station = db.query(Station).filter(Station.code == code).first()
            if station is None:
                rejected += 1
                rejets.append(code)
                continue

            exists = db.query(Consolidation).filter(
                Consolidation.station_id == station.id,
                Consolidation.annee_hydro == annee,
            ).first()
            if exists:
                ignored += 1
                continue

            data = {"station_id": station.id, "annee_hydro": annee}
            for field, col in zip(MONTH_FIELDS, COL_MONTHS):
                data[field] = _num(row[col])
            for field, col in zip(SEASON_FIELDS, COL_SEASONS):
                data[field] = _num(row[col])
            data["total"] = _num(row[COL_TOTAL])
            data["normale"] = _num(row[COL_MOY])
            data["pourcentage"] = _num(row[COL_PCT])

            db.add(Consolidation(**data))
            inserted += 1

        db.commit()
        log_event(
            db, request=None, user=None,
            action="import_consolidations", result="success",
            resource_type="consolidation", volume=inserted,
            detail={"annee_hydro": annee, "ignorees": ignored,
                    "rejetees": rejected, "codes_rejetes": rejets},
        )
        print(f"Import termine : {inserted} inserees, {ignored} ignorees, "
              f"{rejected} rejetees (annee {annee}).")
        if rejets:
            print("Codes sans station en base :", ", ".join(rejets))
    finally:
        db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Import consolidations yasra.xlsx")
    p.add_argument("path", help="Chemin du .xlsx dans le conteneur")
    p.add_argument("--annee", type=int, required=True,
                   help="Annee hydro de debut (ex. 2024 = sept 2024 -> aout 2025)")
    args = p.parse_args()
    if not (2000 <= args.annee <= 2100):
        sys.exit(f"Annee invraisemblable : {args.annee}")
    run(args.path, args.annee)
