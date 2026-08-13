"""SQLAlchemy engine/session setup.

Defaults to a local SQLite file (zero-setup) but honours ``DATABASE_URL`` so the
same code runs against Postgres/PostGIS in production. The engine is created
lazily and cached so importing this module never opens a connection.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=4)
def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, future=True, connect_args=connect_args)
    return engine


def init_db(database_url: str | None = None) -> Engine:
    """Create all tables. Import models first so they register on ``Base``."""
    from app.db import models  # noqa: F401  (ensures models are registered)

    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    return engine


def get_session(database_url: str | None = None) -> Session:
    factory = sessionmaker(bind=get_engine(database_url), expire_on_commit=False, future=True)
    return factory()
