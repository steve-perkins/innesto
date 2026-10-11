"""Sidecars: list, fetch, import, activate, delete.

The import endpoint is the extension point for externally produced sidecars
(e.g. from a Claude Code skill): any JSON that validates against
schema/sidecar.schema.json and matches the book's text is accepted.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ..db import get_session
from ..jobs import register_sidecar, set_active
from ..models import Sidecar
from ..pipeline.sidecar import validate, verify_against_book
from .books import book_path, get_book

router = APIRouter(tags=["sidecars"])


def _get_sidecar(sidecar_id: int, session: Session) -> Sidecar:
    row = session.get(Sidecar, sidecar_id)
    if not row:
        raise HTTPException(404, "Sidecar not found")
    get_book(row.book_id, session)
    return row


@router.get("/api/books/{book_id}/sidecars")
def list_sidecars(book_id: str, session: Session = Depends(get_session)) -> list[Sidecar]:
    book = get_book(book_id, session)
    return list(session.exec(select(Sidecar).where(Sidecar.book_id == book.id).order_by(Sidecar.created_at.desc())))


@router.get("/api/books/{book_id}/sidecars/active")
def active_sidecar(book_id: str, lang: str, session: Session = Depends(get_session)):
    book = get_book(book_id, session)
    row = session.exec(select(Sidecar).where(Sidecar.book_id == book.id, Sidecar.target_lang == lang,
                                              Sidecar.active == True)).first()  # noqa: E712
    if not row:
        raise HTTPException(404, f"No sidecar for {lang}")
    return FileResponse(row.path, media_type="application/json",
                        headers={"X-Sidecar-Id": str(row.id), "Cache-Control": "no-cache"})


@router.post("/api/books/{book_id}/sidecars", status_code=201)
async def import_sidecar(book_id: str, file: UploadFile, activate: bool = True,
                         session: Session = Depends(get_session)) -> Sidecar:
    book = get_book(book_id, session)
    try:
        sidecar = json.loads(await file.read())
        validate(sidecar)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Not JSON: {exc}") from exc
    except jsonschema.ValidationError as exc:
        raise HTTPException(422, f"Invalid sidecar: {exc.message}") from exc
    problems = verify_against_book(sidecar, book_path(book.id))
    if problems:
        raise HTTPException(422, "Sidecar does not match this book: " + "; ".join(problems))
    return register_sidecar(session, book, sidecar["targetLang"], sidecar, activate=activate)


@router.get("/api/sidecars/{sidecar_id}")
def get_sidecar(sidecar_id: int, session: Session = Depends(get_session)):
    row = _get_sidecar(sidecar_id, session)
    return FileResponse(row.path, media_type="application/json")


@router.post("/api/sidecars/{sidecar_id}/activate")
def activate_sidecar(sidecar_id: int, session: Session = Depends(get_session)) -> Sidecar:
    row = _get_sidecar(sidecar_id, session)
    set_active(session, row)
    return row


@router.delete("/api/sidecars/{sidecar_id}", status_code=204)
def delete_sidecar(sidecar_id: int, session: Session = Depends(get_session)) -> None:
    row = _get_sidecar(sidecar_id, session)
    Path(row.path).unlink(missing_ok=True)
    session.delete(row)
    session.commit()
