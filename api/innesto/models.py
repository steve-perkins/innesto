"""Database models. Everything user-visible is keyed by user_id so that
multi-user hosting (Google SSO, phase 5) is a change of auth, not of schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: str = Field(primary_key=True)          # phase 1: "local"; later: OIDC subject
    email: Optional[str] = None
    display_name: Optional[str] = None
    native_lang: str = "en"
    target_lang: str = "it"
    created_at: datetime = Field(default_factory=utcnow)


class Book(SQLModel, table=True):
    # "sha256:<hex>" of the EPUB bytes. Same id as the sidecar's bookId, so
    # sidecars produced elsewhere can be matched to the book they belong to.
    id: str = Field(primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    title: str
    author: Optional[str] = None
    language: Optional[str] = None
    filename: str
    size: int
    section_count: int = 0
    has_cover: bool = False
    added_at: datetime = Field(default_factory=utcnow)


class Sidecar(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: str = Field(foreign_key="book.id", index=True)
    target_lang: str
    generator_name: str
    generator_version: str
    engine: Optional[str] = None
    path: str                                   # JSON file under SIDECARS_DIR
    active: bool = False                        # one active sidecar per (book, lang)
    candidate_count: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: str = Field(foreign_key="book.id", index=True)
    target_lang: str
    status: str = "queued"                      # queued | running | done | error
    progress: int = 0                           # sections done
    total: int = 0                              # sections total
    error: Optional[str] = None
    sidecar_id: Optional[int] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ReadingPosition(SQLModel, table=True):
    user_id: str = Field(foreign_key="user.id", primary_key=True)
    book_id: str = Field(foreign_key="book.id", primary_key=True)
    cfi: Optional[str] = None
    fraction: float = 0.0
    updated_at: datetime = Field(default_factory=utcnow)


class VocabEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    lang: str                                   # target language of the lemma
    lemma: str
    status: str = "learning"                    # learning | known
    lookups: int = 0
    last_seen: datetime = Field(default_factory=utcnow)


class Translation(SQLModel, table=True):
    """Cross-book cache of engine output, keyed by engine and source text."""
    engine: str = Field(primary_key=True)
    source: str = Field(primary_key=True)
    target: str
