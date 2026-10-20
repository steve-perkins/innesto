from __future__ import annotations

import hashlib
import mimetypes
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import config
from ..auth import current_user_id
from ..db import get_session
from ..epub.container import Epub
from ..models import Book, Job, ReadingPosition, Sidecar, User
from ..pipeline.translate.base import provider_available

router = APIRouter(prefix="/api/books", tags=["books"])

COVER_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
             "image/webp": ".webp", "image/svg+xml": ".svg"}


def book_path(book_id: str) -> Path:
    return config.BOOKS_DIR / f"{book_id.split(':', 1)[1]}.epub"


def cover_path(book_id: str) -> Path | None:
    stem = book_id.split(":", 1)[1]
    for ext in COVER_EXT.values():
        p = config.COVERS_DIR / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def get_book(book_id: str, session: Session) -> Book:
    book = session.get(Book, book_id)
    if not book or book.user_id != current_user_id():
        raise HTTPException(404, "Book not found")
    return book


class BookOut(BaseModel):
    """Book plus a processing summary for the library view."""
    id: str
    user_id: str
    title: str
    author: str | None
    language: str | None
    filename: str
    size: int
    section_count: int
    has_cover: bool
    added_at: datetime
    sidecar_langs: list[str] = []
    job: Job | None = None


def _summarize(session: Session, book: Book) -> BookOut:
    langs = sorted({s.target_lang for s in session.exec(
        select(Sidecar).where(Sidecar.book_id == book.id, Sidecar.active == True))})  # noqa: E712
    job = session.exec(select(Job).where(Job.book_id == book.id)
                       .order_by(Job.created_at.desc())).first()
    return BookOut(**book.model_dump(), sidecar_langs=langs, job=job)


def maybe_enqueue(session: Session, book: Book, target_lang: str | None = None) -> None:
    """Queue processing for the requested (or the user's default) target
    language when the configured engine can run (echo/none always can; ct2
    needs the model on disk)."""
    from .. import jobs
    if not target_lang:
        user = session.get(User, current_user_id())
        target_lang = user.target_lang if user else config.DEFAULT_TARGET
    if config.TRANSLATION_ENGINE != "ct2" or provider_available(book.source_lang, target_lang):
        jobs.enqueue_job(session, book, target_lang)


@router.get("")
def list_books(session: Session = Depends(get_session)) -> list[BookOut]:
    stmt = select(Book).where(Book.user_id == current_user_id()).order_by(Book.added_at.desc())
    return [_summarize(session, b) for b in session.exec(stmt)]


@router.post("", status_code=201)
async def upload_book(file: UploadFile, target_lang: str | None = None,
                      session: Session = Depends(get_session)) -> Book:
    config.ensure_dirs()
    sha = hashlib.sha256()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub", dir=config.DATA_DIR) as tmp:
        while chunk := await file.read(1 << 20):
            sha.update(chunk)
            tmp.write(chunk)
        tmp_path = Path(tmp.name)
    book_id = f"sha256:{sha.hexdigest()}"

    existing = session.get(Book, book_id)
    if existing:
        tmp_path.unlink(missing_ok=True)
        if existing.user_id != current_user_id():
            raise HTTPException(409, "This book exists under another account")
        return existing

    try:
        with Epub(tmp_path) as epub:
            info = epub.info()
            cover_bytes = epub.read(info.cover_href) if info.cover_href and epub.has(info.cover_href) else None
            section_count = len(epub.text_sections())
    except Exception as exc:  # zipfile.BadZipFile, KeyError, etree errors...
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(400, f"Not a readable EPUB: {exc}") from exc

    dest = book_path(book_id)
    shutil.move(tmp_path, dest)
    has_cover = False
    if cover_bytes and info.cover_media_type in COVER_EXT:
        (config.COVERS_DIR / f"{sha.hexdigest()}{COVER_EXT[info.cover_media_type]}").write_bytes(cover_bytes)
        has_cover = True

    book = Book(id=book_id, user_id=current_user_id(), title=info.title, author=info.author,
                language=info.language, filename=file.filename or "book.epub",
                size=dest.stat().st_size, section_count=section_count, has_cover=has_cover)
    session.add(book)
    session.commit()
    maybe_enqueue(session, book, target_lang)
    session.refresh(book)
    return book


@router.get("/{book_id}")
def read_book(book_id: str, session: Session = Depends(get_session)) -> BookOut:
    return _summarize(session, get_book(book_id, session))


@router.get("/{book_id}/file")
def book_file(book_id: str, session: Session = Depends(get_session)):
    book = get_book(book_id, session)
    return FileResponse(book_path(book.id), media_type="application/epub+zip", filename=book.filename)


@router.get("/{book_id}/cover")
def book_cover(book_id: str, session: Session = Depends(get_session)):
    book = get_book(book_id, session)
    path = cover_path(book.id)
    if not path:
        raise HTTPException(404, "No cover")
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "image/jpeg")


@router.get("/{book_id}/toc")
def book_toc(book_id: str, session: Session = Depends(get_session)) -> list[dict]:
    book = get_book(book_id, session)
    with Epub(book_path(book.id)) as epub:
        return [t.to_dict() for t in epub.toc()]


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: str, session: Session = Depends(get_session)) -> None:
    book = get_book(book_id, session)
    for sc in session.exec(select(Sidecar).where(Sidecar.book_id == book.id)):
        Path(sc.path).unlink(missing_ok=True)
        session.delete(sc)
    for job in session.exec(select(Job).where(Job.book_id == book.id)):
        session.delete(job)
    for pos in session.exec(select(ReadingPosition).where(ReadingPosition.book_id == book.id)):
        session.delete(pos)
    session.delete(book)
    session.commit()
    book_path(book.id).unlink(missing_ok=True)
    if (cp := cover_path(book.id)):
        cp.unlink(missing_ok=True)
    sidecar_dir = config.SIDECARS_DIR / book.id.split(":", 1)[1]
    if sidecar_dir.exists():
        shutil.rmtree(sidecar_dir, ignore_errors=True)
