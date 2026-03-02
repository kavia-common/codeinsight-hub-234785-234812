from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.settings import get_settings


def _build_sqlalchemy_url() -> str:
    """
    Build SQLAlchemy connection string.

    We use POSTGRES_URL as authoritative (it is provided by DB container env vars).
    """
    settings = get_settings()
    # POSTGRES_URL is expected to be like: postgresql://host:port/dbname
    # SQLAlchemy accepts the same.
    return settings.postgres_url


_ENGINE = create_engine(
    _build_sqlalchemy_url(),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE)


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy Session."""
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager for a managed DB session with rollback-on-error."""
    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
