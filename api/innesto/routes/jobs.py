from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from ..auth import current_user_id
from ..db import get_session
from ..jobs import enqueue_job
from ..models import Job, User
from .books import get_book

router = APIRouter(tags=["jobs"])


@router.post("/api/books/{book_id}/jobs", status_code=202)
def create_job(book_id: str, response: Response, target_lang: str | None = None,
               session: Session = Depends(get_session)) -> Job:
    book = get_book(book_id, session)
    lang = target_lang or session.get(User, current_user_id()).target_lang
    job, created = enqueue_job(session, book, lang)
    if not created:
        response.status_code = 200
    return job


@router.get("/api/books/{book_id}/jobs")
def list_jobs(book_id: str, session: Session = Depends(get_session)) -> list[Job]:
    book = get_book(book_id, session)
    return list(session.exec(select(Job).where(Job.book_id == book.id).order_by(Job.created_at.desc())))


@router.get("/api/jobs/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    get_book(job.book_id, session)       # ownership check
    return job
