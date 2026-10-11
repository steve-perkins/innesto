from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from . import config

_engine = None


def engine():
    global _engine
    if _engine is None:
        config.ensure_dirs()
        _engine = create_engine(
            f"sqlite:///{config.DB_PATH}",
            connect_args={"check_same_thread": False, "timeout": 5},
        )

        @event.listens_for(_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            # WAL: readers never block the job worker's writes, and the file
            # stays consistent for the nightly snapshot. busy_timeout: wait
            # instead of failing when the worker holds the write lock.
            # (Foreign keys stay unenforced, as before: deletes are explicit.)
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()
    return _engine


def init_db() -> None:
    """Bring the schema to the current revision (see innesto/migrations)."""
    from .migrations.runner import upgrade
    upgrade(engine())


def get_session() -> Iterator[Session]:
    with Session(engine()) as session:
        yield session


def reset_for_tests() -> None:
    """Drop the cached engine so tests can point config at a temp directory."""
    global _engine
    _engine = None
