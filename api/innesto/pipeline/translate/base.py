"""Translation provider interface.

A provider turns span texts into target-language text. The request carries the
containing sentence so that context-aware engines (an LLM, a future
alignment-based engine) can use it; the phase-1 CTranslate2 engine ignores it.
Swapping engines is a configuration change, and an external tool can bypass
this layer entirely by writing a sidecar directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ... import config


@dataclass(frozen=True)
class SpanRequest:
    text: str
    context: str | None = None


class Provider(Protocol):
    name: str                       # identifier recorded in sidecar.generator.engine
    source_lang: str
    target_lang: str

    def translate_batch(self, requests: list[SpanRequest]) -> list[str]: ...


class NullProvider:
    """Emits null translations: produces a candidates-only sidecar for an
    external tool to fill (`--no-translate`)."""
    name = "none"

    def __init__(self, source_lang: str, target_lang: str):
        self.source_lang, self.target_lang = source_lang, target_lang

    def translate_batch(self, requests: list[SpanRequest]) -> list[str | None]:  # type: ignore[override]
        return [None] * len(requests)


class EchoProvider:
    """Test double: wraps the source text so tests can see it round-trip."""
    name = "echo"

    def __init__(self, source_lang: str = "en", target_lang: str = "xx"):
        self.source_lang, self.target_lang = source_lang, target_lang

    def translate_batch(self, requests: list[SpanRequest]) -> list[str]:
        return [f"[{self.target_lang}:{r.text}]" for r in requests]


def model_dir_for(source_lang: str, target_lang: str) -> Path:
    return config.MODELS_DIR / f"{source_lang}-{target_lang}"


def get_provider(source_lang: str, target_lang: str, engine: str = "ct2") -> Provider:
    if engine == "none":
        return NullProvider(source_lang, target_lang)
    if engine == "echo":
        return EchoProvider(source_lang, target_lang)
    if engine == "ct2":
        from .ct2 import CT2Provider
        return CT2Provider(model_dir_for(source_lang, target_lang), source_lang, target_lang)
    raise ValueError(f"Unknown translation engine: {engine}")


def provider_available(source_lang: str, target_lang: str) -> bool:
    from .ct2 import find_layout
    return find_layout(model_dir_for(source_lang, target_lang)) is not None


_TERMINAL = ".!?…"
_TRAILING = _TERMINAL + ",;:"        # "However" -> "Tuttavia,": the comma is already in the text
_QUOTES = "\"'«»“”‘’"
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_LOOP_RE = re.compile(r"(.{2,}?)\1{2,}", re.S)     # a chunk repeated 3+ times in a row


def degenerate(source: str, target: str | None) -> bool:
    """True when the decoder ran away: a chunk repeated over and over
    ("milamilamila…", "fan di fan di fan di", "######"), or output far longer
    than any rendering of the fragment (a hallucinated sentence for "However").
    Repetition the source itself has ("ha ha ha", "...") does not count."""
    if not target:
        return False
    if len(target) > 3 * len(source) + 20:
        return True
    return bool(_LOOP_RE.search(target)) and not _LOOP_RE.search(source)


def postprocess(source: str, target: str | None) -> str | None:
    """Make fragment translations fit where the fragment came from. MT models
    are trained on sentences and like to add a full stop, capitalise, wrap
    output in quotes, or (for a lone word) repeat themselves. Idempotent, and
    applied to every translation at sidecar-build time, cached or fresh.
    Runaway output is dropped (None): no gloss beats a garbage one."""
    if target is None or degenerate(source, target):
        return None
    t = target.strip()
    if not t:
        return t
    if t[0] in _QUOTES and t[-1] in _QUOTES and source[:1] not in _QUOTES:
        t = t[1:-1].strip()
    if source[-1:] not in _TRAILING:
        while t and t[-1] in _TRAILING:
            t = t[:-1].rstrip()
    # Single-word source, repetitive output ("cena a cena", "felicemente
    # felice"): cut at the first word that repeats an earlier word's stem.
    if len(_WORD_RE.findall(source)) == 1:
        words = t.split()
        stems = []
        for i, w in enumerate(words):
            stem = re.sub(r"\W+", "", w.lower())[:4]
            if len(stem) >= 3 and stem in stems:
                kept = words[:i]
                while len(kept) > 1 and len(re.sub(r"\W+", "", kept[-1])) <= 2:
                    kept.pop()                      # drop a dangling "a", "di"...
                t = " ".join(kept).rstrip(" ,;:")
                break
            stems.append(stem)
    if source[:1].islower() and t[:1].isupper():
        t = t[0].lower() + t[1:]
    elif source[:1].isupper() and t[:1].islower():
        t = t[0].upper() + t[1:]
    return t
