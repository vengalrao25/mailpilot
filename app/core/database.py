"""Lazy SQLAlchemy engine/session factory.

Nothing here runs at import time — `get_sessionmaker()` (cached) is the
only entry point, and it's called from a FastAPI dependency or a script's
`main`, never from module top-level. That keeps importing the app (e.g.
for tests that override the repository dependency) from ever opening a
database connection.
"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings


@lru_cache
def get_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    return create_engine(settings.database_url)


@lru_cache
def get_sessionmaker(settings: Settings | None = None) -> sessionmaker:
    return sessionmaker(bind=get_engine(settings))
