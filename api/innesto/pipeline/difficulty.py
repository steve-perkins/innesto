"""Difficulty scoring for candidate spans.

Level 1-5 is what the reader's *Level* slider gates on. It combines the span
kind (what grammatical unit is being swapped) with how rare the vocabulary is,
measured with wordfreq's Zipf scale (7 = extremely common, 3 = rare).
"""

from __future__ import annotations

from functools import lru_cache

from wordfreq import zipf_frequency

KIND_BASE = {"word": 1, "np": 1, "np_mod": 2, "vp": 2, "pp": 3, "clause": 4, "sentence": 5}


@lru_cache(maxsize=200_000)
def zipf(lemma: str, lang: str) -> float:
    return zipf_frequency(lemma, lang)


def frequency_penalty(min_zipf: float) -> int:
    # Calibrated on en_core_web_sm lemmas: book 5.4, cat 4.8, garden 4.8,
    # harvest 4.0, scabbard 2.5.
    if min_zipf >= 4.5:
        return 0
    if min_zipf >= 3.8:
        return 1
    if min_zipf >= 3.0:
        return 2
    return 3


def score(kind: str, modified: bool, lemmas: list[str], lang: str = "en") -> tuple[int, float]:
    """Return (level, difficulty). `difficulty` is a continuous 0..1 value used
    for ordering within a level; `level` is clamped to 1..5."""
    base_kind = "np_mod" if (kind == "np" and modified) else kind
    base = KIND_BASE[base_kind]
    zipfs = [zipf(l, lang) for l in lemmas] or [6.0]
    min_zipf = min(zipfs)
    level = max(1, min(5, base + frequency_penalty(min_zipf)))
    rarity = max(0.0, min(1.0, (7.0 - min_zipf) / 4.5))      # 0 = very common, 1 = very rare
    difficulty = max(0.0, min(1.0, 0.55 * (base - 1) / 4 + 0.45 * rarity))
    return level, round(difficulty, 4)
