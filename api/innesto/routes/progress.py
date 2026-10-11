from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from ..auth import current_user_id
from ..db import get_session
from ..models import ReadingPosition, utcnow
from .books import get_book

router = APIRouter(prefix="/api/books/{book_id}/progress", tags=["progress"])


class ProgressIn(BaseModel):
    cfi: str | None = None
    fraction: float = 0.0


@router.get("")
def get_progress(book_id: str, session: Session = Depends(get_session)) -> ReadingPosition:
    book = get_book(book_id, session)
    pos = session.get(ReadingPosition, (current_user_id(), book.id))
    return pos or ReadingPosition(user_id=current_user_id(), book_id=book.id)


@router.put("")
def put_progress(book_id: str, body: ProgressIn, session: Session = Depends(get_session)) -> ReadingPosition:
    book = get_book(book_id, session)
    pos = session.get(ReadingPosition, (current_user_id(), book.id))
    if pos is None:
        pos = ReadingPosition(user_id=current_user_id(), book_id=book.id)
    pos.cfi = body.cfi
    pos.fraction = max(0.0, min(1.0, body.fraction))
    pos.updated_at = utcnow()
    session.add(pos)
    session.commit()
    session.refresh(pos)
    return pos
