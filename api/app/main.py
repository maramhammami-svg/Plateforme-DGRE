from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
