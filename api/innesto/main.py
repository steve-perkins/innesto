"""Innesto API entry point.

Innesto is a diglot-weave ebook reader: it renders the reader's own EPUBs with
words and phrases swapped for the language they are learning. This FastAPI app
stores the library, serves book files, runs the processing pipeline that
produces per-book "sidecars" of translation candidates, and serves the built
web app in production.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, config
from .db import init_db
from .jobs import worker
from .maintenance import start_scheduler
from .auth import require_user
from .routes import auth, books, jobs, progress, sidecars, vocab


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    init_db()
    worker.start()
    if not config.DISABLE_MAINTENANCE:
        start_scheduler()
    yield


app = FastAPI(title="Innesto", version=__version__, lifespan=lifespan)

# Dev convenience: the Vite dev server proxies /api, but allow direct calls too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

# Public: health, sign-in. Everything else requires a bearer token.
app.include_router(auth.router)
protected = [Depends(require_user)]
for r in (books.router, progress.router, jobs.router, sidecars.router, vocab.router):
    app.include_router(r, dependencies=protected)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    if config.IS_PRODUCTION:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        response.headers.setdefault("Content-Security-Policy", CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


# Book sections render in blob: documents that inherit this policy, so no
# script from an EPUB can run; Google Identity Services needs its origin.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://accounts.google.com",
    "style-src 'self' 'unsafe-inline' blob: https://accounts.google.com",
    "img-src 'self' blob: data: https://*.googleusercontent.com",
    "font-src 'self' blob: data:",
    "connect-src 'self' blob: data: https://accounts.google.com",
    "frame-src 'self' blob: https://accounts.google.com",
    "worker-src 'self' blob:",
    "media-src 'self' blob:",
    "base-uri 'self'",
    "frame-ancestors 'none'",
])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/api/languages", dependencies=[Depends(require_user)])
def languages() -> list[dict]:
    """Target languages the UI can offer, with translation-model availability."""
    from .pipeline.translate.base import provider_available
    engine_ready = config.TRANSLATION_ENGINE != "ct2"
    return [{"code": code, "name": name,
             "available": engine_ready or provider_available("en", code)}
            for code, name in config.SUPPORTED_TARGETS.items()]


# Production: serve the built PWA. Anything that is not /api falls back to
# index.html so client-side routes deep-link correctly.
if config.WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=config.WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = config.WEB_DIST / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(config.WEB_DIST / "index.html")
