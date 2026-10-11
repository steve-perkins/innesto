import json
import time

import pytest


@pytest.fixture
def echo_env(app_env, monkeypatch):
    from innesto import config
    monkeypatch.setattr(config, "TRANSLATION_ENGINE", "echo")
    return app_env


def upload(client, path):
    with open(path, "rb") as f:
        r = client.post("/api/books", files={"file": ("sample.epub", f, "application/epub+zip")})
    assert r.status_code == 201, r.text
    return r.json()


def wait_for_job(client, job_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_upload_triggers_job_and_sidecar(echo_env, sample_epub):
    client = echo_env
    book = upload(client, sample_epub)
    jobs = client.get(f"/api/books/{book['id']}/jobs").json()
    assert len(jobs) == 1 and jobs[0]["target_lang"] == "it"
    job = wait_for_job(client, jobs[0]["id"])
    assert job["status"] == "done", job
    assert job["progress"] == job["total"] == 3

    listed = client.get("/api/books").json()[0]
    assert listed["sidecar_langs"] == ["it"] and listed["job"]["status"] == "done"

    r = client.get(f"/api/books/{book['id']}/sidecars/active", params={"lang": "it"})
    assert r.status_code == 200
    sidecar = r.json()
    assert sidecar["bookId"] == book["id"] and sidecar["generator"]["engine"] == "echo"
    assert any(c["text"] == "a book" and c["translation"] == "[it:a book]"
               for c in sidecar["sections"][1]["candidates"])

    # Re-requesting a job while one is done creates a new one; while pending returns the same.
    r1 = client.post(f"/api/books/{book['id']}/jobs")
    assert r1.status_code == 202
    r2 = client.post(f"/api/books/{book['id']}/jobs")
    assert r2.status_code == 200 and r2.json()["id"] == r1.json()["id"]
    wait_for_job(client, r1.json()["id"])


def test_import_external_sidecar(echo_env, sample_epub):
    client = echo_env
    book = upload(client, sample_epub)
    job = wait_for_job(client, client.get(f"/api/books/{book['id']}/jobs").json()[0]["id"])
    sidecar = client.get(f"/api/sidecars/{job['sidecar_id']}").json()

    # An external tool revises translations and re-imports under its own name.
    sidecar["generator"] = {"name": "claude-skill", "version": "0.1", "engine": "claude",
                            "createdAt": "2026-10-10T00:00:00Z"}
    for c in sidecar["sections"][1]["candidates"]:
        if c["text"] == "a book":
            c["translation"] = "un libro"
    r = client.post(f"/api/books/{book['id']}/sidecars",
                    files={"file": ("reviewed.json", json.dumps(sidecar), "application/json")})
    assert r.status_code == 201, r.text
    imported = r.json()
    assert imported["active"] is True and imported["generator_name"] == "claude-skill"
    rows = client.get(f"/api/books/{book['id']}/sidecars").json()
    assert sum(1 for s in rows if s["active"]) == 1
    active = client.get(f"/api/books/{book['id']}/sidecars/active", params={"lang": "it"}).json()
    assert any(c["translation"] == "un libro" for c in active["sections"][1]["candidates"])

    # Switching back to the pipeline's sidecar.
    pipeline_row = next(s for s in rows if s["generator_name"] == "innesto-pipeline")
    assert client.post(f"/api/sidecars/{pipeline_row['id']}/activate").json()["active"] is True

    # Tampered sidecars are rejected.
    sidecar["sections"][1]["candidates"][0]["text"] = "garbage"
    r = client.post(f"/api/books/{book['id']}/sidecars",
                    files={"file": ("bad.json", json.dumps(sidecar), "application/json")})
    assert r.status_code == 422
    r = client.post(f"/api/books/{book['id']}/sidecars",
                    files={"file": ("bad.json", "{}", "application/json")})
    assert r.status_code == 422
