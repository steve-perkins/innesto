"""Background processing of books into sidecars.

A single worker thread drains an in-process queue; job state lives in the Job
table so it survives restarts (pending jobs are re-queued at startup). This is
deliberately simple: one user, one VM, no Redis. The pipeline itself is in
`innesto.pipeline` and knows nothing about jobs or the database.
"""

from __future__ import annotations

import logging
import queue
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from . import config
from .db import engine
from .models import Book, Job, Sidecar, Translation, utcnow
from .pipeline.candidates import Extractor
from .pipeline.sidecar import build_sidecar, write_sidecar
from .pipeline.translate.base import get_provider

log = logging.getLogger("innesto.jobs")


def sidecar_dir(book_id: str, lang: str) -> Path:
    return config.SIDECARS_DIR / book_id.split(":", 1)[1] / lang


def register_sidecar(session: Session, book: Book, lang: str, sidecar: dict, *,
                     activate: bool = True) -> Sidecar:
    """Write a sidecar document to disk and record it (optionally as the active
    one for its book/language). Used by jobs and by the import endpoint."""
    gen = sidecar["generator"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    safe_engine = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (gen.get("engine") or gen["name"]))
    path = sidecar_dir(book.id, lang) / f"{stamp}-{safe_engine}.json"
    write_sidecar(sidecar, path)
    row = Sidecar(book_id=book.id, target_lang=lang, generator_name=gen["name"],
                  generator_version=gen["version"], engine=gen.get("engine"), path=str(path),
                  active=False, candidate_count=sum(len(s["candidates"]) for s in sidecar["sections"]))
    session.add(row)
    session.commit()
    session.refresh(row)
    if activate:
        set_active(session, row)
    return row


def set_active(session: Session, row: Sidecar) -> None:
    others = session.exec(select(Sidecar).where(Sidecar.book_id == row.book_id,
                                                Sidecar.target_lang == row.target_lang))
    for o in others:
        o.active = (o.id == row.id)
        session.add(o)
    session.commit()
    session.refresh(row)


class Worker:
    def __init__(self) -> None:
        self.q: queue.Queue[int] = queue.Queue()
        self.thread: threading.Thread | None = None
        self._extractors: dict[str, Extractor] = {}

    def start(self) -> None:
        with Session(engine()) as session:
            pending = session.exec(select(Job).where(Job.status.in_(["queued", "running"]))  # type: ignore[attr-defined]
                                   .order_by(Job.created_at)).all()
            for job in pending:
                job.status = "queued"
                session.add(job)
                self.q.put(job.id)  # type: ignore[arg-type]
            session.commit()
        self.thread = threading.Thread(target=self._loop, name="innesto-worker", daemon=True)
        self.thread.start()

    def enqueue(self, job_id: int) -> None:
        self.q.put(job_id)

    def _loop(self) -> None:
        while True:
            job_id = self.q.get()
            try:
                self._process(job_id)
            except Exception:  # pragma: no cover - last-resort guard
                log.exception("job %s crashed", job_id)
            finally:
                self.q.task_done()

    def _extractor(self, lang: str) -> Extractor:
        if lang not in self._extractors:
            self._extractors[lang] = Extractor(lang=lang)
        return self._extractors[lang]

    def _process(self, job_id: int) -> None:
        with Session(engine()) as session:
            job = session.get(Job, job_id)
            if job is None or job.status not in ("queued", "running"):
                return
            book = session.get(Book, job.book_id)
            if book is None:
                job.status, job.error = "error", "book no longer exists"
                session.add(job); session.commit()
                return
            job.status, job.updated_at = "running", utcnow()
            session.add(job); session.commit()
            source_lang = (book.language or "en").split("-")[0].lower()
            target_lang = job.target_lang
            book_id = book.id

        def progress(done: int, total: int) -> None:
            with Session(engine()) as s:
                j = s.get(Job, job_id)
                if j:
                    j.progress, j.total, j.updated_at = done, total, utcnow()
                    s.add(j); s.commit()

        try:
            provider = get_provider(source_lang, target_lang, config.TRANSLATION_ENGINE)
            with Session(engine()) as s:
                cache = {t.source: t.target for t in s.exec(
                    select(Translation).where(Translation.engine == provider.name))}
            known = set(cache)
            from .routes.books import book_path
            sidecar = build_sidecar(book_path(book_id), provider, source_lang=source_lang,
                                    extractor=self._extractor(source_lang), progress=progress,
                                    translation_cache=cache)
            with Session(engine()) as s:
                for src, tgt in cache.items():
                    if src not in known and tgt is not None:
                        s.merge(Translation(engine=provider.name, source=src, target=tgt))
                s.commit()
                book = s.get(Book, book_id)
                row = register_sidecar(s, book, target_lang, sidecar)
                j = s.get(Job, job_id)
                j.status, j.sidecar_id, j.updated_at = "done", row.id, utcnow()
                j.progress = j.total = len(sidecar["sections"])
                s.add(j); s.commit()
                count = row.candidate_count
            log.info("job %s done: %s candidates", job_id, count)
        except Exception as exc:
            log.error("job %s failed: %s\n%s", job_id, exc, traceback.format_exc())
            with Session(engine()) as s:
                j = s.get(Job, job_id)
                if j:
                    j.status, j.error, j.updated_at = "error", f"{type(exc).__name__}: {exc}"[:1000], utcnow()
                    s.add(j); s.commit()


worker = Worker()


def enqueue_job(session: Session, book: Book, target_lang: str) -> tuple[Job, bool]:
    """Create (or return the existing pending) job for a book/language.
    Returns (job, created)."""
    existing = session.exec(select(Job).where(
        Job.book_id == book.id, Job.target_lang == target_lang,
        Job.status.in_(["queued", "running"]))).first()  # type: ignore[attr-defined]
    if existing:
        return existing, False
    job = Job(book_id=book.id, target_lang=target_lang, total=book.section_count)
    session.add(job)
    session.commit()
    session.refresh(job)
    worker.enqueue(job.id)  # type: ignore[arg-type]
    return job, True
