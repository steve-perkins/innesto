"""Assemble, validate, read and verify sidecars."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import jsonschema

from .. import __version__, config
from ..epub.container import Epub
from ..epub.textstream import extract
from .candidates import Candidate, Extractor
from .translate.base import Provider, SpanRequest

GENERATOR_NAME = "innesto-pipeline"

ProgressFn = Callable[[int, int], None]


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(config.SCHEMA_PATH.read_text())


def validate(sidecar: dict) -> None:
    """Raise jsonschema.ValidationError if the document is not a valid sidecar."""
    jsonschema.validate(sidecar, schema(), format_checker=jsonschema.FormatChecker())
    for sec in sidecar["sections"]:
        for c in sec["candidates"]:
            if c["end"] <= c["start"]:
                raise jsonschema.ValidationError(
                    f"candidate {c['id']} in section {sec['index']} has end <= start")


def book_id_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def section_streams(epub: Epub) -> list[tuple[int, str, "TextStream"]]:  # noqa: F821
    out = []
    for item in epub.text_sections():
        out.append((item.index, item.href, extract(epub.read(item.href))))
    return out


def verify_against_book(sidecar: dict, epub_path: Path) -> list[str]:
    """Check an (imported) sidecar against the EPUB it claims to describe.
    Returns a list of problems; empty means it is consistent."""
    problems: list[str] = []
    expected = book_id_of(epub_path)
    if sidecar["bookId"] != expected:
        problems.append(f"bookId {sidecar['bookId']} does not match the EPUB ({expected})")
        return problems
    with Epub(epub_path) as epub:
        streams = {idx: (href, ts) for idx, href, ts in section_streams(epub)}
    for sec in sidecar["sections"]:
        got = streams.get(sec["index"])
        if got is None:
            problems.append(f"section {sec['index']} is not a text section of this book")
            continue
        href, ts = got
        if sec["textHash"] != ts.hash:
            problems.append(f"section {sec['index']} ({href}): textHash mismatch")
            continue
        bad = [c["id"] for c in sec["candidates"] if ts.text[c["start"]:c["end"]] != c["text"]]
        if bad:
            problems.append(f"section {sec['index']}: {len(bad)} candidate(s) do not match the text, e.g. {bad[:3]}")
    return problems


def _target_lemmatizer(lang: str):
    """Best effort lemmatiser for the target language (spaCy model if installed)."""
    models = {"it": "it_core_news_sm", "es": "es_core_news_sm", "fr": "fr_core_news_sm",
              "de": "de_core_news_sm", "pt": "pt_core_news_sm", "nl": "nl_core_news_sm"}
    name = models.get(lang)
    if not name:
        return None
    try:
        import spacy
        return spacy.load(name, exclude=["ner", "parser", "textcat"])
    except Exception:
        return None


def build_sidecar(epub_path: Path, provider: Provider, *, source_lang: str = "en",
                  extractor: Extractor | None = None, progress: ProgressFn | None = None,
                  translation_cache: dict[str, str] | None = None) -> dict:
    """Run the whole pipeline for one book and return the sidecar document."""
    extractor = extractor or Extractor(lang=source_lang)
    cache = translation_cache if translation_cache is not None else {}
    lemmatizer = _target_lemmatizer(provider.target_lang)
    book_id = book_id_of(epub_path)

    with Epub(epub_path) as epub:
        streams = section_streams(epub)
    total = len(streams)
    sections = []
    for done, (index, href, ts) in enumerate(streams):
        cands: list[Candidate] = extractor.extract_stream(ts.text, ts.blocks)

        todo = sorted({c.text for c in cands if c.text not in cache})
        if todo:
            # Context: the sentence of the first candidate with this text.
            ctx = {}
            for c in cands:
                ctx.setdefault(c.text, ts.text[c.sentence[0]:c.sentence[1]])
            results = provider.translate_batch([SpanRequest(t, ctx.get(t)) for t in todo])
            for t, r in zip(todo, results):
                cache[t] = r

        out_cands = []
        for n, c in enumerate(cands):
            translation = cache.get(c.text)
            entry = {
                "id": f"s{index}-c{n:04d}", "start": c.start, "end": c.end, "text": c.text,
                "translation": translation, "kind": c.kind, "level": c.level,
                "difficulty": c.difficulty, "lemmas": c.lemmas,
                "sentence": {"start": c.sentence[0], "end": c.sentence[1]},
            }
            if translation:
                entry["targetLemmas"] = target_lemmas(translation, lemmatizer)
            out_cands.append(entry)

        sections.append({"index": index, "href": href, "textHash": ts.hash,
                         "wordCount": ts.word_count, "candidates": out_cands})
        if progress:
            progress(done + 1, total)

    sidecar = {
        "schemaVersion": 1,
        "bookId": book_id,
        "sourceLang": source_lang,
        "targetLang": provider.target_lang,
        "generator": {
            "name": GENERATOR_NAME, "version": __version__, "engine": provider.name,
            "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "sections": sections,
    }
    validate(sidecar)
    return sidecar


def target_lemmas(translation: str, lemmatizer) -> list[str]:
    if lemmatizer is None:
        words = [w.strip(".,;:!?\"'«»()").lower() for w in translation.split()]
        return [w for w in words if w and any(ch.isalpha() for ch in w)]
    out: list[str] = []
    for t in lemmatizer(translation):
        if t.is_alpha and t.pos_ in ("NOUN", "VERB", "ADJ", "ADV", "AUX", "NUM", "INTJ"):
            lemma = t.lemma_.lower()
            if lemma not in out:
                out.append(lemma)
    return out


def write_sidecar(sidecar: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=None, separators=(",", ":")))


def read_sidecar(path: Path) -> dict:
    return json.loads(path.read_text())
