import math

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .database import Base, engine
from .seed import seed
from .routers import (auth, stations, raw_readings, readings, events, admin,
                      consolidations, documents, dashboard)

app = FastAPI(
    title="Plateforme DGRE - Banc d'essai pluviometrie / limnimetrie",
    description="PoC instrumente : chaque action emet un evenement normalise (contrat d'observabilite).",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def _json_safe(value):
    """Remplace NaN/Infinity (valides en Python, invalides en JSON strict) par une
    representation textuelle, pour eviter que la reponse d'erreur elle-meme ne
    plante en recopiant l'entree invalide fournie par le client."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for e in exc.errors():
        e = dict(e)
        e.pop("ctx", None)   # peut contenir l'exception Python brute levee par un validator
        errors.append(e)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": _json_safe(jsonable_encoder(errors))},
    )


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    seed()


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(stations.router)
app.include_router(raw_readings.router)
app.include_router(readings.router)
app.include_router(events.router)
app.include_router(admin.router)
app.include_router(consolidations.router)
app.include_router(documents.router)
app.include_router(dashboard.router)
