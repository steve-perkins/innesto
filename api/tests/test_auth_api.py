import sqlite3

import jwt
from sqlmodel import Session, SQLModel

from innesto import auth, db
from innesto.models import Book, User
from tests.conftest import TEST_USER


def google_claims(email, sub="google-sub-2", **extra):
    return {"iss": "https://accounts.google.com", "sub": sub, "email": email, "email_verified": True,
            "name": "Test Person", "picture": "https://example.com/p.png", **extra}


def test_requires_token(app_env):
    anon = app_env
    saved = anon.headers.pop("Authorization")
    assert anon.get("/api/books").status_code == 401
    assert anon.get("/api/languages").status_code == 401
    assert anon.get("/api/health").status_code == 200
    assert anon.get("/api/auth/config").json() == {"clientId": "test-client-id", "configured": True, "allowlistSize": 2}
    anon.headers["Authorization"] = "Bearer not-a-token"
    assert anon.get("/api/books").status_code == 401
    expired = jwt.encode({"sub": TEST_USER["id"], "exp": 1}, "test-secret", algorithm="HS256")
    anon.headers["Authorization"] = f"Bearer {expired}"
    r = anon.get("/api/books")
    assert r.status_code == 401 and "expired" in r.json()["detail"]
    anon.headers["Authorization"] = saved
    assert anon.get("/api/auth/me").json()["email"] == TEST_USER["email"]


def test_google_sign_in_allowlist(app_env, monkeypatch):
    client = app_env
    monkeypatch.setattr(auth, "verify_google_id_token", lambda t: google_claims("stranger@example.com"))
    r = client.post("/api/auth/google", json={"idToken": "x"})
    assert r.status_code == 403 and "guest list" in r.json()["detail"]

    monkeypatch.setattr(auth, "verify_google_id_token", lambda t: google_claims("friend@example.com"))
    r = client.post("/api/auth/google", json={"idToken": "x"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == "friend@example.com" and body["user"]["displayName"] == "Test Person"
    claims = jwt.decode(body["accessToken"], "test-secret", algorithms=["HS256"])
    assert claims["sub"] == "google-sub-2"
    client.headers["Authorization"] = f"Bearer {body['accessToken']}"
    assert client.get("/api/books").status_code == 200

    def bad(_):
        raise ValueError("Token expired")
    monkeypatch.setattr(auth, "verify_google_id_token", bad)
    assert client.post("/api/auth/google", json={"idToken": "x"}).status_code == 401


def test_legacy_local_data_is_adopted(app_env, monkeypatch):
    client = app_env
    # Simulate a phase-4 database: a 'local' user owning a book, nobody else.
    with Session(db.engine()) as s:
        s.delete(s.get(User, TEST_USER["id"]))
        s.add(User(id="local", display_name="Local user", target_lang="es"))
        s.add(Book(id="sha256:" + "a" * 64, user_id="local", title="Old book", filename="x.epub", size=1))
        s.commit()
    monkeypatch.setattr(auth, "verify_google_id_token", lambda t: google_claims("friend@example.com"))
    r = client.post("/api/auth/google", json={"idToken": "x"})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["targetLang"] == "es"       # preference carried over
    client.headers["Authorization"] = f"Bearer {r.json()['accessToken']}"
    assert [b["title"] for b in client.get("/api/books").json()] == ["Old book"]
    with Session(db.engine()) as s:
        assert s.get(User, "local") is None


def test_pre_alembic_database_is_stamped_and_upgraded(tmp_path):
    """A database created by phase 1-4 (create_all, no alembic_version) must
    upgrade in place with its rows intact."""
    from sqlalchemy import create_engine, inspect
    from innesto.migrations.runner import upgrade
    path = tmp_path / "old.db"
    old = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(old)
    with sqlite3.connect(path) as c:                   # strip the phase-5 additions
        for col in ("picture_url", "last_login"):
            c.execute(f"ALTER TABLE user DROP COLUMN {col}")
        c.execute("DROP INDEX IF EXISTS ix_user_email")
        c.execute("INSERT INTO user (id, native_lang, target_lang, created_at) VALUES ('local','en','it','2026-01-01')")
        c.execute("INSERT INTO book (id, user_id, title, filename, size, section_count, has_cover, added_at) "
                  "VALUES ('sha256:abc','local','T','f.epub',1,0,0,'2026-01-01')")
    upgrade(old)
    insp = inspect(old)
    assert "alembic_version" in insp.get_table_names()
    assert {"picture_url", "last_login"} <= {c["name"] for c in insp.get_columns("user")}
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"
        assert c.execute("SELECT title FROM book").fetchone()[0] == "T"
    upgrade(old)   # idempotent


def test_allowlist_parsing_and_validation(monkeypatch):
    from innesto import config
    assert config.parse_allowlist('"Steve@Example.com", friend@example.com ;other@example.com') == \
        {"steve@example.com", "friend@example.com", "other@example.com"}
    assert config.parse_allowlist("") == frozenset()
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(config, "ALLOWED_EMAILS", frozenset())
    monkeypatch.delenv("INNESTO_JWT_SECRET", raising=False)
    problems = config.validate_settings()
    assert len(problems) == 3 and any("JWT_SECRET" in p for p in problems)
    monkeypatch.setenv("INNESTO_JWT_SECRET", '"abc"')
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "x")
    monkeypatch.setattr(config, "ALLOWED_EMAILS", frozenset({"a@b.c"}))
    assert config.validate_settings() == []
    assert config.jwt_secret() == "abc"            # quotes from an env file are tolerated
