import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(p: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def generate_station_key() -> str:
    return secrets.token_urlsafe(24)


def generate_password(n: int = 12) -> str:
    """Mot de passe aleatoire url-safe, pour reset admin (montre une seule fois)."""
    return secrets.token_urlsafe(n)


def create_access_token(sub: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": sub, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str):
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
