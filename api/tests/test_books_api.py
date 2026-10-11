def test_upload_list_progress_delete(app_env, sample_epub):
    client = app_env
    with open(sample_epub, "rb") as f:
        r = client.post("/api/books", files={"file": ("sample.epub", f, "application/epub+zip")})
    assert r.status_code == 201, r.text
    book = r.json()
    assert book["title"] == "A Small Sample" and book["has_cover"] is True
    assert book["id"].startswith("sha256:") and book["section_count"] == 3

    # Re-uploading the same bytes is idempotent.
    with open(sample_epub, "rb") as f:
        r2 = client.post("/api/books", files={"file": ("again.epub", f, "application/epub+zip")})
    assert r2.status_code == 201 and r2.json()["id"] == book["id"]
    assert len(client.get("/api/books").json()) == 1

    assert client.get(f"/api/books/{book['id']}/file").status_code == 200
    assert client.get(f"/api/books/{book['id']}/cover").headers["content-type"].startswith("image/png")
    toc = client.get(f"/api/books/{book['id']}/toc").json()
    assert toc[0]["label"] == "Chapter One"

    r = client.put(f"/api/books/{book['id']}/progress", json={"cfi": "epubcfi(/6/4!/4/2/1:0)", "fraction": 0.25})
    assert r.status_code == 200 and r.json()["fraction"] == 0.25
    assert client.get(f"/api/books/{book['id']}/progress").json()["cfi"] == "epubcfi(/6/4!/4/2/1:0)"

    assert client.delete(f"/api/books/{book['id']}").status_code == 204
    assert client.get("/api/books").json() == []
    assert client.get(f"/api/books/{book['id']}").status_code == 404


def test_rejects_non_epub(app_env):
    r = app_env.post("/api/books", files={"file": ("x.epub", b"not a zip", "application/epub+zip")})
    assert r.status_code == 400
