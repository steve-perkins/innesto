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
def _env(name: str, default: str = "") -> str:
    """Environment value with surrounding quotes/whitespace removed: docker
    env_file passes `X="a"` through verbatim, quotes included."""
    return os.environ.get(name, default).strip().strip("\"'").strip()


def parse_allowlist(value: str) -> frozenset[str]:
    """Comma-, semicolon- or whitespace-separated emails, case-insensitive."""
    parts = value.strip().strip("\"'").replace(";", ",").replace(" ", ",").split(",")
    return frozenset(p.strip().strip("\"'").lower() for p in parts if p.strip().strip("\"'"))


GOOGLE_CLIENT_ID = _env("INNESTO_GOOGLE_CLIENT_ID")
# Emails allowed to sign in. Empty means nobody can.
ALLOWED_EMAILS = parse_allowlist(os.environ.get("INNESTO_ALLOWED_EMAILS", ""))
# Tests and one-off CLI runs set this to skip the nightly snapshot thread.
DISABLE_MAINTENANCE = os.environ.get("INNESTO_DISABLE_MAINTENANCE", "") == "1"
TOKEN_TTL_DAYS = int(os.environ.get("INNESTO_TOKEN_TTL_DAYS", "7"))
# Legacy single-user account from phase 1; its data is adopted by the first
# real user to sign in (see auth.adopt_legacy_local_user).
LEGACY_LOCAL_USER_ID = "local"


def validate_settings() -> list[str]:
    """Problems that make sign-in impossible. In production the app refuses
    to start on any of them (a 500 at sign-in time is much harder to spot)."""
    problems: list[str] = []
    if not GOOGLE_CLIENT_ID:
        problems.append("INNESTO_GOOGLE_CLIENT_ID is not set (no one can sign in)")
    if IS_PRODUCTION and not os.environ.get("INNESTO_JWT_SECRET", "").strip().strip("\"'"):
        problems.append("INNESTO_JWT_SECRET is not set (generate one with: openssl rand -hex 32)")
    if not ALLOWED_EMAILS:
        problems.append("INNESTO_ALLOWED_EMAILS is empty (no one can sign in)")
    return problems


def jwt_secret() -> str:
    """Signing key for access tokens. Required in production; in development
    one is generated once and kept in DATA_DIR so sessions survive restarts."""
    value = _env("INNESTO_JWT_SECRET")
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
