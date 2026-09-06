from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from .config import settings

# SQLite (tests uniquement, cf. tests/) : sans StaticPool, chaque thread du pool
# FastAPI verrait sa propre base ":memory:" vide (SingletonThreadPool par defaut).
# Sans effet sur Postgres en production (settings.database_url y commence toujours
# par "postgresql+psycopg2://").
_is_sqlite = settings.database_url.startswith("sqlite")
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    poolclass=StaticPool if _is_sqlite else None,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
