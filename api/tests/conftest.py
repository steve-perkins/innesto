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


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    """Point the app at a temporary data directory and return a TestClient."""
    from innesto import config, db
    data = tmp_path / "data"
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "BOOKS_DIR", data / "books")
    monkeypatch.setattr(config, "COVERS_DIR", data / "covers")
    monkeypatch.setattr(config, "SIDECARS_DIR", data / "sidecars")
    monkeypatch.setattr(config, "DB_PATH", data / "test.db")
    db.reset_for_tests()
    from fastapi.testclient import TestClient
    from innesto.main import app
    with TestClient(app) as client:
        yield client
    db.reset_for_tests()
