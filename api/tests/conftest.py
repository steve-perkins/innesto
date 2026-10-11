from __future__ import annotations

import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES))


@pytest.fixture(scope="session")
def sample_epub(tmp_path_factory) -> Path:
    from make_fixture import build
    return build(tmp_path_factory.mktemp("fixture") / "sample.epub")


TEST_USER = {"id": "google-sub-1", "email": "reader@example.com"}


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    """Point the app at a temporary data directory and return a TestClient
    that is signed in as TEST_USER (bearer token minted with the test secret)."""
    from innesto import config, db
    data = tmp_path / "data"
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "BOOKS_DIR", data / "books")
    monkeypatch.setattr(config, "COVERS_DIR", data / "covers")
    monkeypatch.setattr(config, "SIDECARS_DIR", data / "sidecars")
    monkeypatch.setattr(config, "DB_PATH", data / "test.db")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(config, "ALLOWED_EMAILS", frozenset({TEST_USER["email"], "friend@example.com"}))
    monkeypatch.setenv("INNESTO_JWT_SECRET", "test-secret")
    monkeypatch.setattr(config, "DISABLE_MAINTENANCE", True)
    db.reset_for_tests()
    from fastapi.testclient import TestClient
    from sqlmodel import Session
    from innesto.auth import mint_token
    from innesto.main import app
    from innesto.models import User
    with TestClient(app) as client:
        with Session(db.engine()) as session:
            user = User(**TEST_USER)
            session.add(user)
            session.commit()
            session.refresh(user)
            token = mint_token(user)
        client.headers["Authorization"] = f"Bearer {token}"
        yield client
    db.reset_for_tests()
