"""Vocabulary: what the reader knows or is learning, in the target language.

Entries are keyed by (user, lang, lemma). The reader sends lookups when a
swap is tapped and explicit marks from the popover; the selection algorithm
uses the known/learning sets to choose what to swap.
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from ..auth import current_user_id
from ..db import get_session
from ..models import VocabEntry, utcnow

router = APIRouter(prefix="/api/vocab", tags=["vocab"])


class VocabIn(BaseModel):
    lang: str
    lemma: str
    status: str | None = None          # "known" | "learning" | None (keep)
    lookup: bool = False               # record one lookup


class VocabSummary(BaseModel):
    lang: str
    known: list[str]
    learning: list[str]


def _get(session: Session, lang: str, lemma: str) -> VocabEntry | None:
    return session.exec(select(VocabEntry).where(
        VocabEntry.user_id == current_user_id(), VocabEntry.lang == lang,
        VocabEntry.lemma == lemma)).first()


@router.get("")
def list_vocab(lang: str, status: str | None = None,
               session: Session = Depends(get_session)) -> list[VocabEntry]:
    stmt = select(VocabEntry).where(VocabEntry.user_id == current_user_id(), VocabEntry.lang == lang)
    if status:
        stmt = stmt.where(VocabEntry.status == status)
    return list(session.exec(stmt.order_by(VocabEntry.last_seen.desc())))


@router.get("/summary")
def summary(lang: str, session: Session = Depends(get_session)) -> VocabSummary:
    rows = list_vocab(lang, None, session)
    return VocabSummary(lang=lang,
                        known=[r.lemma for r in rows if r.status == "known"],
                        learning=[r.lemma for r in rows if r.status == "learning"])


@router.post("")
def upsert(body: VocabIn, session: Session = Depends(get_session)) -> VocabEntry:
    lemma = body.lemma.strip().lower()
    if not lemma:
        raise HTTPException(400, "empty lemma")
    if body.status not in (None, "known", "learning"):
        raise HTTPException(400, "status must be known or learning")
    row = _get(session, body.lang, lemma)
    if row is None:
        row = VocabEntry(user_id=current_user_id(), lang=body.lang, lemma=lemma,
                         status=body.status or "learning")
    if body.status:
        row.status = body.status
    if body.lookup:
        row.lookups += 1
    row.last_seen = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/{lang}/{lemma}", status_code=204)
def delete(lang: str, lemma: str, session: Session = Depends(get_session)) -> None:
    row = _get(session, lang, lemma.lower())
    if row:
        session.delete(row)
        session.commit()


@router.get("/export.csv")
def export_csv(lang: str, session: Session = Depends(get_session)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["lemma", "status", "lookups", "last_seen"])
    for r in list_vocab(lang, None, session):
        w.writerow([r.lemma, r.status, r.lookups, r.last_seen.isoformat()])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="innesto-vocab-{lang}.csv"'})
