import json

import jsonschema
import pytest

from innesto.pipeline import __main__ as cli
from innesto.pipeline.sidecar import build_sidecar, validate, verify_against_book
from innesto.pipeline.translate.base import EchoProvider, NullProvider


@pytest.fixture(scope="module")
def sidecar(sample_epub):
    return build_sidecar(sample_epub, EchoProvider("en", "xx"))


def test_sidecar_is_valid_and_consistent(sidecar, sample_epub):
    validate(sidecar)
    assert sidecar["generator"]["engine"] == "echo" and sidecar["targetLang"] == "xx"
    assert [s["index"] for s in sidecar["sections"]] == [0, 1, 2]
    ch1 = sidecar["sections"][1]
    texts = {c["text"] for c in ch1["candidates"]}
    assert {"a book", "John is reading", "very", "slowly"} <= texts
    for c in ch1["candidates"]:
        assert c["translation"] == f"[xx:{c['text']}]"
        assert c["targetLemmas"]
    assert verify_against_book(sidecar, sample_epub) == []


def test_candidates_only_sidecar(sample_epub):
    sc = build_sidecar(sample_epub, NullProvider("en", "it"))
    validate(sc)
    assert all(c["translation"] is None for s in sc["sections"] for c in s["candidates"])


def test_verify_detects_tampering(sidecar, sample_epub):
    bad = json.loads(json.dumps(sidecar))
    bad["sections"][1]["candidates"][0]["text"] = "nope"
    assert any("do not match" in p for p in verify_against_book(bad, sample_epub))
    bad["sections"][1]["textHash"] = "sha256:" + "0" * 64
    assert any("textHash" in p for p in verify_against_book(bad, sample_epub))
    bad["bookId"] = "sha256:" + "1" * 64
    assert any("bookId" in p for p in verify_against_book(bad, sample_epub))


def test_schema_rejects_garbage(sidecar):
    bad = json.loads(json.dumps(sidecar))
    bad["sections"][0]["candidates"].append({"id": "x"})
    with pytest.raises(jsonschema.ValidationError):
        validate(bad)


def test_cli_roundtrip(sample_epub, tmp_path):
    out = tmp_path / "s.json"
    assert cli.main([str(sample_epub), "--engine", "echo", "--target", "xx", "-o", str(out)]) == 0
    assert cli.main(["--verify", str(out), str(sample_epub)]) == 0
