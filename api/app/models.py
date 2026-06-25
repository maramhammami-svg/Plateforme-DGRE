from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, JSON, func
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    region = Column(String, nullable=False)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Station(Base):
    __tablename__ = "stations"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    region = Column(String, nullable=False, index=True)
    governorate = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    readings = relationship("Reading", back_populates="station")


class Reading(Base):
    __tablename__ = "readings"
    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False, index=True)
    date = Column(String, nullable=False)
    value_mm = Column(Float, nullable=False)
    status = Column(String, default="pending")
    quality_flag = Column(String, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    validated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    station = relationship("Station", back_populates="readings")


class ReadingVersion(Base):
    """Historique de chaque modification d'un releve : la trace fine
    qui permettra de detecter et d'auditer les falsifications."""
    __tablename__ = "reading_versions"
    id = Column(Integer, primary_key=True)
    reading_id = Column(Integer, ForeignKey("readings.id"), nullable=False, index=True)
    version_no = Column(Integer, nullable=False)
    old_value_mm = Column(Float, nullable=True)
    new_value_mm = Column(Float, nullable=True)
    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=True)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    reason = Column(String, nullable=True)


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
    region = Column(String, nullable=True)
    volume = Column(Integer, nullable=True)
    channel_ip = Column(String, nullable=True)
    result = Column(String, nullable=False)
    detail = Column(JSON, nullable=True)
