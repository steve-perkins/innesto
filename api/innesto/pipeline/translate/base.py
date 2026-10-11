"""Translation provider interface.

A provider turns span texts into target-language text. The request carries the
containing sentence so that context-aware engines (an LLM, a future
alignment-based engine) can use it; the phase-1 CTranslate2 engine ignores it.
Swapping engines is a configuration change, and an external tool can bypass
this layer entirely by writing a sidecar directly.
"""

from __future__ import annotations

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
