from pydantic import BaseModel, field_validator
from typing import Optional, Any
from datetime import datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    role: str
    is_active: int = 1
    unite_id: Optional[int] = None
    superviseur_id: Optional[int] = None

    class Config:
        from_attributes = True


class UserIn(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    role: str
    unite_id: Optional[int] = None
    superviseur_id: Optional[int] = None


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[int] = None
    unite_id: Optional[int] = None
    superviseur_id: Optional[int] = None


class UniteOut(BaseModel):
    id: int
    nom: str
    type: str
    parent_id: Optional[int] = None

    class Config:
        from_attributes = True


class StationIn(BaseModel):
    name: str
    type: str
    parameter: str
    unit: str
    sampling_interval_min: Optional[int] = None
    latitude: float
    longitude: float
    altitude_m: Optional[float] = None
    governorate: Optional[str] = None
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
    name: Optional[str] = None
    type: Optional[str] = None
    parameter: Optional[str] = None
    unit: Optional[str] = None
    sampling_interval_min: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None
    governorate: Optional[str] = None
    status: Optional[str] = None
    unite_id: Optional[int] = None


class StationOut(BaseModel):
    id: int
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


class RawReadingIn(BaseModel):
    station_id: int
    timestamp: Optional[datetime] = None
    valeur: Optional[float] = None
    is_missing: bool = False
    source: str


class RawReadingOut(BaseModel):
    id: int
    station_id: int
    timestamp: datetime
    valeur: Optional[float] = None
    is_missing: bool
    source: str

    class Config:
        from_attributes = True


class ReadingIn(BaseModel):
    station_id: int
    date: str
    valeur: float


class ReadingUpdate(BaseModel):
    valeur_recalculee: Optional[float] = None
    raison: Optional[str] = None


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
    decision: str


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
