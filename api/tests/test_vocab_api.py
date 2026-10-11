def test_vocab_roundtrip(app_env):
    c = app_env
    r = c.post("/api/vocab", json={"lang": "it", "lemma": "Libro", "lookup": True})
    assert r.status_code == 200 and r.json()["status"] == "learning" and r.json()["lookups"] == 1
    c.post("/api/vocab", json={"lang": "it", "lemma": "libro", "lookup": True})
    c.post("/api/vocab", json={"lang": "it", "lemma": "casa", "status": "known"})
    s = c.get("/api/vocab/summary", params={"lang": "it"}).json()
    assert s["known"] == ["casa"] and s["learning"] == ["libro"]
    rows = c.get("/api/vocab", params={"lang": "it"}).json()
    assert {r["lemma"]: r["lookups"] for r in rows} == {"libro": 2, "casa": 0}
    csv_text = c.get("/api/vocab/export.csv", params={"lang": "it"}).text
    assert csv_text.startswith("lemma,status,lookups,last_seen") and "libro,learning,2" in csv_text
    assert c.delete("/api/vocab/it/libro").status_code == 204
    assert c.get("/api/vocab/summary", params={"lang": "it"}).json()["learning"] == []
    assert c.post("/api/vocab", json={"lang": "it", "lemma": "x", "status": "bogus"}).status_code == 400
