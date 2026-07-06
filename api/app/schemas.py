from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Literal
from datetime import date, datetime

from . import constants as C


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    role: str
    is_active: int = 1
    locked: int = 0
    unite_id: Optional[int] = None
    superviseur_id: Optional[int] = None

    class Config:
        from_attributes = True


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.\-]+$")
    password: str = Field(min_length=8, max_length=72)  # limite dure bcrypt (72 octets)
    full_name: Optional[str] = Field(default=None, max_length=120)
    role: str
    unite_id: Optional[int] = None
    superviseur_id: Optional[int] = None


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[int] = None
    unite_id: Optional[int] = None
    superviseur_id: Optional[int] = None


class PasswordChange(BaseModel):
    ancien: str = Field(min_length=1, max_length=72)
    nouveau: str = Field(min_length=8, max_length=72)  # limite dure bcrypt (72 octets)


class PasswordResetOut(BaseModel):
    user_id: int
    username: str
    nouveau_mot_de_passe: str   # renvoye une seule fois, jamais restocke


class UniteOut(BaseModel):
    id: int
    nom: str
    type: str
    parent_id: Optional[int] = None

    class Config:
        from_attributes = True


class StationIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=120)
    type: str
    parameter: str
    unit: str
    sampling_interval_min: Optional[int] = Field(default=None, ge=1, le=10_080)
    latitude: float
    longitude: float
    altitude_m: Optional[float] = Field(default=None, ge=-500, le=9000)
    governorate: Optional[str] = Field(default=None, max_length=60)
    unite_id: Optional[int] = None

    @field_validator("latitude")
    @classmethod
    def validate_lat(cls, v):
        if not (30 <= v <= 38):
            raise ValueError("latitude doit etre entre 30 et 38 (Tunisie WGS84)")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_lon(cls, v):
        if not (7 <= v <= 12):
            raise ValueError("longitude doit etre entre 7 et 12 (Tunisie WGS84)")
        return v


class StationUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=30)
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    type: Optional[str] = None
    parameter: Optional[str] = None
    unit: Optional[str] = None
    sampling_interval_min: Optional[int] = Field(default=None, ge=1, le=10_080)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = Field(default=None, ge=-500, le=9000)
    governorate: Optional[str] = Field(default=None, max_length=60)
    status: Optional[str] = None
    unite_id: Optional[int] = None

    @field_validator("latitude")
    @classmethod
    def validate_lat(cls, v):
        if v is not None and not (30 <= v <= 38):
            raise ValueError("latitude doit etre entre 30 et 38 (Tunisie WGS84)")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_lon(cls, v):
        if v is not None and not (7 <= v <= 12):
            raise ValueError("longitude doit etre entre 7 et 12 (Tunisie WGS84)")
        return v


class StationOut(BaseModel):
    id: int
    code: str
    name: str
    type: str
    parameter: str
    unit: str
    sampling_interval_min: Optional[int] = None
    latitude: float
    longitude: float
    altitude_m: Optional[float] = None
    governorate: Optional[str] = None
    status: str
    unite_id: Optional[int] = None

    class Config:
        from_attributes = True


class StationCreated(StationOut):
    station_key: str


def _reject_non_finite(v):
    """Refuse NaN/Infinity : accepte comme float par le JSON mais fausserait
    silencieusement les flags qualite et les agregations (SUM/AVG empoisonnes)."""
    import math
    if v is not None and not math.isfinite(v):
        raise ValueError("valeur doit etre un nombre fini (NaN/Infini refuses)")
    return v


class RawReadingIn(BaseModel):
    station_id: int
    timestamp: Optional[datetime] = None
    valeur: Optional[float] = None
    is_missing: bool = False
    source: str = Field(min_length=1, max_length=40)

    @field_validator("valeur")
    @classmethod
    def validate_valeur(cls, v):
        return _reject_non_finite(v)


class RawReadingOut(BaseModel):
    id: int
    station_id: int
    timestamp: datetime
    valeur: Optional[float] = None
    is_missing: bool
    source: str

    class Config:
        from_attributes = True


class RawPoint(BaseModel):
    timestamp: Optional[datetime] = None
    valeur: Optional[float] = None
    is_missing: bool = False

    @field_validator("valeur")
    @classmethod
    def validate_valeur(cls, v):
        return _reject_non_finite(v)


class RawBatchIn(BaseModel):
    station_id: int
    source: str = Field(min_length=1, max_length=40)
    points: list[RawPoint] = Field(min_length=1, max_length=C.MAX_BATCH_POINTS)


class RawBatchResult(BaseModel):
    inserted: int
    days_aggregated: int


def _validate_iso_date(v: str) -> str:
    try:
        date.fromisoformat(v)
    except (TypeError, ValueError):
        raise ValueError("date invalide (attendu AAAA-MM-JJ)")
    return v


class ReadingIn(BaseModel):
    station_id: int
    date: str
    valeur: float

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        return _validate_iso_date(v)

    @field_validator("valeur")
    @classmethod
    def validate_valeur(cls, v):
        return _reject_non_finite(v)


class ReadingUpdate(BaseModel):
    valeur_recalculee: Optional[float] = None
    raison: Optional[str] = Field(default=None, max_length=500)

    @field_validator("valeur_recalculee")
    @classmethod
    def validate_valeur(cls, v):
        return _reject_non_finite(v)


class ReadingOut(BaseModel):
    id: int
    station_id: int
    date: str
    parameter: str
    valeur_recalculee: Optional[float] = None
    valeur_validee: Optional[float] = None
    status: str
    quality_flag: Optional[str] = None
    source: str

    class Config:
        from_attributes = True


class ReadingVersionOut(BaseModel):
    version_no: int
    ancienne_val: Optional[float] = None
    nouvelle_val: Optional[float] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    post_validation: bool
    auteur: int
    raison: Optional[str] = None

    class Config:
        from_attributes = True


class ValidateIn(BaseModel):
    decision: Literal["validate", "reject"]


class ImportResult(BaseModel):
    inserted: int
    rejected: int
    details: list[Any] = []


class EventOut(BaseModel):
    id: int
    actor_username: Optional[str] = None
    role: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    unite_acteur: Optional[str] = None
    unite_ressource: Optional[str] = None
    volume: Optional[int] = None
    channel_ip: Optional[str] = None
    result: str
    detail: Optional[Any] = None

    class Config:
        from_attributes = True


class ConsolidationOut(BaseModel):
    id: int
    station_id: int
    annee_hydro: int
    sept: Optional[float] = None
    octo: Optional[float] = None
    nove: Optional[float] = None
    dece: Optional[float] = None
    janv: Optional[float] = None
    fevr: Optional[float] = None
    mars: Optional[float] = None
    avri: Optional[float] = None
    mai: Optional[float] = None
    juin: Optional[float] = None
    juil: Optional[float] = None
    aout: Optional[float] = None
    automne: Optional[float] = None
    hiver: Optional[float] = None
    printemps: Optional[float] = None
    ete: Optional[float] = None
    total: Optional[float] = None
    normale: Optional[float] = None
    pourcentage: Optional[float] = None

    class Config:
        from_attributes = True


class ConsolidationIn(BaseModel):
    station_id: int
    annee_hydro: int
    sept: Optional[float] = None
    octo: Optional[float] = None
    nove: Optional[float] = None
    dece: Optional[float] = None
    janv: Optional[float] = None
    fevr: Optional[float] = None
    mars: Optional[float] = None
    avri: Optional[float] = None
    mai: Optional[float] = None
    juin: Optional[float] = None
    juil: Optional[float] = None
    aout: Optional[float] = None
    automne: Optional[float] = None
    hiver: Optional[float] = None
    printemps: Optional[float] = None
    ete: Optional[float] = None
    total: Optional[float] = None
    normale: Optional[float] = None
    pourcentage: Optional[float] = None


class StationCompleteness(BaseModel):
    station_id: int
    code: str
    name: str
    completude_mensuelle: Optional[float] = None
    completude_journaliere: float


class DashboardSummary(BaseModel):
    pending_count: int
    quality_anomalies: int
    stations_active: int
    stations_inactive: int
    completeness: list[StationCompleteness]


class StationMarker(BaseModel):
    id: int
    code: str
    name: str
    latitude: float
    longitude: float
    status: str
    quality: str

    class Config:
        from_attributes = True


class SharedTargetOut(BaseModel):
    type: Literal["unite", "user"]
    id: int
    nom: str


class DocumentOut(BaseModel):
    id: int
    nom: str
    mime_type: Optional[str] = None
    owner_id: int
    unite_id: Optional[int] = None
    taille_ko: int
    created_at: Optional[datetime] = None
    partages: list[SharedTargetOut] = []

    class Config:
        from_attributes = True


class UniteLiteOut(BaseModel):
    id: int
    nom: str

    class Config:
        from_attributes = True


class UserLiteOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    unite_id: Optional[int] = None

    class Config:
        from_attributes = True
