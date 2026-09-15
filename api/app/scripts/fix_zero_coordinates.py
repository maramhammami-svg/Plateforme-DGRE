"""Repare les stations automatiques creees a (0,0) par un import_mis.py
execute avant l'ajout de GOVERNORATE_CENTROIDS ou a cause d'un gouvernorat
non reconnu (accents/casse). Idempotent : ne touche que lat=0 ET lon=0.
Usage : python -m app.scripts.fix_zero_coordinates
"""
from ..database import SessionLocal
from ..models import Station
from .import_mis import _CENTROIDS_NORMALIZED, _normalize


def run():
    db = SessionLocal()
    try:
        broken = db.query(Station).filter(
            Station.latitude == 0, Station.longitude == 0
        ).all()
        fixed, still_unknown = 0, []
        for st in broken:
            coords = _CENTROIDS_NORMALIZED.get(_normalize(st.governorate or ""))
            if coords:
                st.latitude, st.longitude = coords
                fixed += 1
            else:
                still_unknown.append((st.code, st.governorate))
        db.commit()
        print(f"{fixed} stations corrigees sur {len(broken)} trouvees a (0,0).")
        if still_unknown:
            print("Toujours non reconnues (a corriger manuellement) :")
            for code, gov in still_unknown:
                print(f"  - {code} : gouvernorat={gov!r}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
