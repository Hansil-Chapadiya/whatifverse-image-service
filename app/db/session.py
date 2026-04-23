from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base


engine = None
SessionLocal = None

if settings.database_url:
    engine = create_engine(settings.database_url, echo=settings.db_echo, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def is_db_enabled() -> bool:
    return SessionLocal is not None


def init_db() -> None:
    if engine is None:
        return
    # Ensure model metadata is imported before create_all.
    from app.db.models import asset_model  # noqa: F401

    Base.metadata.create_all(bind=engine)


def check_db_connection() -> None:
    if engine is None:
        return
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
