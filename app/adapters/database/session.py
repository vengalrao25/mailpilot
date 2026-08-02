from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_sessionmaker


@contextmanager
def session_scope(session_factory: sessionmaker | None = None) -> Iterator[Session]:
    """Open a Session bound to `session_factory` (defaults to the app's
    configured Postgres sessionmaker, resolved lazily on first use)."""
    factory = session_factory or get_sessionmaker()
    with factory() as session:
        yield session
