"""Runtime configuration, read from environment variables with local-dev defaults."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Local development reads api/.env (git-ignored) so the Google client id,
# allowlist and secret need not be exported by hand. Production passes real
# environment variables (docker env_file); those always win.
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / "api" / ".env", override=False)
except ImportError:  # pragma: no cover
    pass

ENV = os.environ.get("INNESTO_ENV", "development").lower()
IS_PRODUCTION = ENV == "production"

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

# Target languages the UI offers. A language is usable once its translation
# model is installed (scripts/fetch_model.py); the API reports availability.
SUPPORTED_TARGETS = {"it": "Italian", "es": "Spanish"}
DEFAULT_TARGET = "it"

# --- Identity --------------------------------------------------------------
# Google Identity Services client id (public). The frontend fetches it from
# /api/auth/config so one image serves every environment.
GOOGLE_CLIENT_ID = os.environ.get("INNESTO_GOOGLE_CLIENT_ID", "")
# Comma-separated emails allowed to sign in. Empty means nobody can.
ALLOWED_EMAILS = frozenset(
    e.strip().lower() for e in os.environ.get("INNESTO_ALLOWED_EMAILS", "").split(",") if e.strip())
# Tests and one-off CLI runs set this to skip the nightly snapshot thread.
DISABLE_MAINTENANCE = os.environ.get("INNESTO_DISABLE_MAINTENANCE", "") == "1"
TOKEN_TTL_DAYS = int(os.environ.get("INNESTO_TOKEN_TTL_DAYS", "7"))
# Legacy single-user account from phase 1; its data is adopted by the first
# real user to sign in (see auth.adopt_legacy_local_user).
LEGACY_LOCAL_USER_ID = "local"


def jwt_secret() -> str:
    """Signing key for access tokens. Required in production; in development
    one is generated once and kept in DATA_DIR so sessions survive restarts."""
    value = os.environ.get("INNESTO_JWT_SECRET", "")
    if value:
        return value
    if IS_PRODUCTION:
        raise RuntimeError("INNESTO_JWT_SECRET must be set in production")
    path = DATA_DIR / "jwt-secret"
    if not path.exists():
        ensure_dirs()
        path.write_text(secrets.token_hex(32))
        path.chmod(0o600)
    return path.read_text().strip()


def ensure_dirs() -> None:
    for d in (DATA_DIR, BOOKS_DIR, COVERS_DIR, SIDECARS_DIR):
        d.mkdir(parents=True, exist_ok=True)
