from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine, select

from . import config
from .models import User

_engine = None


def engine():
    global _engine
    if _engine is None:
        config.ensure_dirs()
        _engine = create_engine(
            f"sqlite:///{config.DB_PATH}",
            connect_args={"check_same_thread": False},
        )
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(engine())
    with Session(engine()) as session:
        if not session.get(User, config.LOCAL_USER_ID):
            session.add(User(id=config.LOCAL_USER_ID, display_name="Local user"))
            session.commit()


def get_session() -> Iterator[Session]:
    with Session(engine()) as session:
        yield session


def reset_for_tests() -> None:
    """Drop the cached engine so tests can point config at a temp directory."""
    global _engine
    _engine = None
