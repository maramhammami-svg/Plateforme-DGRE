from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean,
    ForeignKey, JSON, UniqueConstraint, func
)
from sqlalchemy.orm import relationship
from .database import Base


class UniteOrganisationnelle(Base):
    __tablename__ = "unites"
    id = Column(Integer, primary_key=True)
    nom = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("unites.id"), nullable=True, index=True)

    parent = relationship(
        "UniteOrganisationnelle",
        back_populates="enfants",
        remote_side=[id],
        foreign_keys=[parent_id],
    )
    enfants = relationship(
        "UniteOrganisationnelle",
        back_populates="parent",
        foreign_keys=[parent_id],
    )


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    unite_id = Column(Integer, ForeignKey("unites.id"), nullable=True, index=True)
    superviseur_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    unite = relationship("UniteOrganisationnelle", foreign_keys=[unite_id])
    superviseur = relationship(
        "User",
        back_populates="subordonnes",
        remote_side=[id],
        foreign_keys=[superviseur_id],
    )
    subordonnes = relationship(
        "User",
        back_populates="superviseur",
        foreign_keys=[superviseur_id],
    )


class Station(Base):
    __tablename__ = "stations"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    type = Column(String, nullable=False)            # automatique | conventionnelle
    parameter = Column(String, nullable=False)       # pluviometrie | limnimetrie
    unit = Column(String, nullable=False)            # mm | cm
    sampling_interval_min = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude_m = Column(Float, nullable=True)
    governorate = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    unite_id = Column(Integer, ForeignKey("unites.id"), nullable=True, index=True)
    hashed_station_key = Column(String, nullable=True)

    unite = relationship("UniteOrganisationnelle", foreign_keys=[unite_id])
    raw_readings = relationship("RawReading", back_populates="station")
    readings = relationship("Reading", back_populates="station")
    consolidations = relationship("Consolidation", back_populates="station")


class RawReading(Base):
    """Mesure brute emise par une station automatique."""
    __tablename__ = "raw_readings"
    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    valeur = Column(Float, nullable=True)
    is_missing = Column(Boolean, default=False, nullable=False)
    source = Column(String, nullable=False)

    station = relationship("Station", back_populates="raw_readings")


class Reading(Base):
    """Releve journalier (valeur agregee ou saisie manuelle)."""
    __tablename__ = "readings"
    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False, index=True)
    date = Column(String, nullable=False)            # YYYY-MM-DD
    parameter = Column(String, nullable=False)       # pluviometrie | limnimetrie
    valeur_recalculee = Column(Float, nullable=True)
    valeur_validee = Column(Float, nullable=True)    # figee a la validation
    status = Column(String, default="pending")
    quality_flag = Column(String, nullable=True)
    source = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    validated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    station = relationship("Station", back_populates="readings")

    __table_args__ = (
        UniqueConstraint("station_id", "date", name="uq_reading_station_date"),
    )


class ReadingVersion(Base):
    """Historique de chaque modification d'un releve : trace fine pour detecter les falsifications."""
    __tablename__ = "reading_versions"
    id = Column(Integer, primary_key=True)
    reading_id = Column(Integer, ForeignKey("readings.id"), nullable=False, index=True)
    version_no = Column(Integer, nullable=False)
    ancienne_val = Column(Float, nullable=True)
    nouvelle_val = Column(Float, nullable=True)
    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=True)
    post_validation = Column(Boolean, default=False, nullable=False)
    auteur = Column(Integer, ForeignKey("users.id"), nullable=False)
    date_modif = Column(DateTime(timezone=True), server_default=func.now())
    raison = Column(String, nullable=True)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_id = Column(Integer, nullable=True)
    actor_username = Column(String, nullable=True, index=True)
    role = Column(String, nullable=True)
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    unite_acteur = Column(String, nullable=True)
    unite_ressource = Column(String, nullable=True)
    volume = Column(Integer, nullable=True)
    channel_ip = Column(String, nullable=True)
    result = Column(String, nullable=False)
    detail = Column(JSON, nullable=True)


class Consolidation(Base):
    """Resume annuel (annee hydrologique sept->aout) importe de yasra.xlsx.
    Une ligne par station et par annee hydro. Valeurs reprises telles quelles
    de la source (aucun recalcul) : les incoherences sont un signal pour l'agent."""
    __tablename__ = "consolidations"
    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False, index=True)
    annee_hydro = Column(Integer, nullable=False, index=True)  # annee de debut (2024 = sept 2024 -> aout 2025)

    # 12 mois, ordre hydrologique
    sept = Column(Float, nullable=True)
    octo = Column(Float, nullable=True)
    nove = Column(Float, nullable=True)
    dece = Column(Float, nullable=True)
    janv = Column(Float, nullable=True)
    fevr = Column(Float, nullable=True)
    mars = Column(Float, nullable=True)
    avri = Column(Float, nullable=True)
    mai = Column(Float, nullable=True)
    juin = Column(Float, nullable=True)
    juil = Column(Float, nullable=True)
    aout = Column(Float, nullable=True)

    # 4 saisons
    automne = Column(Float, nullable=True)
    hiver = Column(Float, nullable=True)
    printemps = Column(Float, nullable=True)
    ete = Column(Float, nullable=True)

    # synthese
    total = Column(Float, nullable=True)
    normale = Column(Float, nullable=True)      # MOY : reference pluriannuelle
    pourcentage = Column(Float, nullable=True)  # total / normale * 100

    station = relationship("Station", back_populates="consolidations")

    __table_args__ = (
        UniqueConstraint("station_id", "annee_hydro", name="uq_consolidation_station_annee"),
    )


class Document(Base):
    """Metadonnees d'un document interne (aucun binaire stocke).
    L'unite du document = celle de son owner. Upload/download journalises :
    un acces ou unite_acteur != unite_ressource est un signal hors-perimetre."""
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    nom = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    unite_id = Column(Integer, ForeignKey("unites.id"), nullable=True, index=True)
    taille_ko = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", foreign_keys=[owner_id])
    unite = relationship("UniteOrganisationnelle", foreign_keys=[unite_id])
