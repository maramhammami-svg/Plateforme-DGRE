from pydantic import BaseModel
from typing import Optional, Any


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    role: str
    region: str
    is_active: int = 1

    class Config:
        from_attributes = True


class UserIn(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    role: str
    region: str


class UserUpdate(BaseModel):
    role: Optional[str] = None
    region: Optional[str] = None
    is_active: Optional[int] = None


class StationIn(BaseModel):
    code: str
    name: str
    region: str
    governorate: Optional[str] = None


class StationUpdate(BaseModel):
    name: Optional[str] = None
    governorate: Optional[str] = None
    status: Optional[str] = None


class StationOut(BaseModel):
    id: int
    code: str
    name: str
    region: str
    governorate: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class ReadingIn(BaseModel):
    station_id: int
    date: str
    value_mm: float


class ReadingUpdate(BaseModel):
    value_mm: Optional[float] = None
    reason: Optional[str] = None


class ReadingOut(BaseModel):
    id: int
    station_id: int
    date: str
    value_mm: float
    status: str
    quality_flag: Optional[str] = None

    class Config:
        from_attributes = True


class ReadingVersionOut(BaseModel):
    version_no: int
    old_value_mm: Optional[float] = None
    new_value_mm: Optional[float] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    changed_by: int
    reason: Optional[str] = None

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
    region: Optional[str] = None
    volume: Optional[int] = None
    channel_ip: Optional[str] = None
    result: str
    detail: Optional[Any] = None

    class Config:
        from_attributes = True
