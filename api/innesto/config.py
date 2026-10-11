"""Runtime configuration, read from environment variables with local-dev defaults."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Where uploaded books, covers, sidecars and the SQLite database live.
DATA_DIR = Path(os.environ.get("INNESTO_DATA_DIR", REPO_ROOT / "data")).resolve()
BOOKS_DIR = DATA_DIR / "books"
COVERS_DIR = DATA_DIR / "covers"
SIDECARS_DIR = DATA_DIR / "sidecars"
DB_PATH = DATA_DIR / "innesto.db"

# Translation models (CTranslate2 directories), one per language pair.
MODELS_DIR = Path(os.environ.get("INNESTO_MODELS_DIR", REPO_ROOT / "api" / "models")).resolve()

# Translation engine used by background jobs: ct2 (self-hosted models), echo
# (test double) or none (candidates only, for external translation tools).
TRANSLATION_ENGINE = os.environ.get("INNESTO_TRANSLATION_ENGINE", "ct2")

# Built web app, served as static files when present (production container).
WEB_DIST = Path(os.environ.get("INNESTO_WEB_DIST", REPO_ROOT / "web" / "dist")).resolve()

SCHEMA_PATH = REPO_ROOT / "schema" / "sidecar.schema.json"

# Phase 1 runs single-user; this is the implicit local account.
LOCAL_USER_ID = "local"


def ensure_dirs() -> None:
    for d in (DATA_DIR, BOOKS_DIR, COVERS_DIR, SIDECARS_DIR):
        d.mkdir(parents=True, exist_ok=True)
