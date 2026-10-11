"""Innesto API entry point.

Innesto is a diglot-weave ebook reader: it renders the reader's own EPUBs with
words and phrases swapped for the language they are learning. This FastAPI app
stores the library, serves book files, runs the processing pipeline that
produces per-book "sidecars" of translation candidates, and serves the built
web app in production.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, config
from .db import init_db
from .routes import books, progress


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    init_db()
    yield


app = FastAPI(title="Innesto", version=__version__, lifespan=lifespan)

# Dev convenience: the Vite dev server proxies /api, but allow direct calls too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(books.router)
app.include_router(progress.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


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
