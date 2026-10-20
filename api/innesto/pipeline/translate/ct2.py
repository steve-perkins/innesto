"""Self-hosted neural MT with CTranslate2 + sentencepiece (both permissive,
CPU-only, no PyTorch at runtime).

Two on-disk layouts are recognised under MODELS_DIR/<src>-<tgt>/:

  Argos layout   (unzipped .argosmodel; see scripts/fetch_model.py)
      model/            CTranslate2 model directory
      sentencepiece.model
      metadata.json

  Marian layout  (ct2-transformers-converter output for Helsinki-NLP/opus-mt-*)
      model.bin + config.json ...
      source.spm, target.spm
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import SpanRequest, degenerate, postprocess

BATCH = 32
# Part of the engine name, which keys the translation cache: bump it when
# decoding changes enough that cached output should be regenerated.
DECODING = 2
# Minimum per-token log-prob a target gains from seeing its source rather than
# a blank one. Memorised corpus lines the model emits whatever the input
# ("Have you not" -> "Non lo so.", "take up another matter…" -> "Presidente. —
# L'ordine del giorno reca…") score below 1; translations, even short stock
# replies ("I don't know." -> "Non lo so."), score above it. A retry, already
# suspect, must clear a higher bar ("the vote": "Discussioni del Parlamento
# europeo" 1.6, "La votazione" 6.9).
GROUNDED = 1.0
RETRY_GROUNDED = 3.0


def find_layout(model_dir: Path) -> dict | None:
    if (model_dir / "model" / "model.bin").exists() and (model_dir / "sentencepiece.model").exists():
        return {"kind": "argos", "ct2": model_dir / "model",
                "src_spm": model_dir / "sentencepiece.model", "tgt_spm": model_dir / "sentencepiece.model"}
    if (model_dir / "model.bin").exists() and (model_dir / "source.spm").exists():
        return {"kind": "marian", "ct2": model_dir,
                "src_spm": model_dir / "source.spm", "tgt_spm": model_dir / "target.spm"}
    return None


def _letters(text: str) -> str:
    return "".join(ch for ch in text.casefold() if ch.isalnum())


class CT2Provider:
    def __init__(self, model_dir: Path, source_lang: str, target_lang: str,
                 device: str = "cpu", compute_type: str = "auto"):
        import ctranslate2
        import sentencepiece as spm

        layout = find_layout(model_dir)
        if layout is None:
            raise FileNotFoundError(
                f"No translation model for {source_lang}->{target_lang} in {model_dir}. "
                f"Run: python -m scripts.fetch_model {source_lang} {target_lang}")
        self.source_lang, self.target_lang = source_lang, target_lang
        self.layout = layout
        meta = {}
        if (model_dir / "metadata.json").exists():
            meta = json.loads((model_dir / "metadata.json").read_text())
        version = meta.get("package_version") or meta.get("version") or ""
        self.name = f"{layout['kind']}-{source_lang}_{target_lang}-{version}".rstrip("-") + f"-d{DECODING}"
        self.translator = ctranslate2.Translator(str(layout["ct2"]), device=device,
                                                 compute_type=compute_type, inter_threads=1)
        self.sp_src = spm.SentencePieceProcessor(model_file=str(layout["src_spm"]))
        self.sp_tgt = spm.SentencePieceProcessor(model_file=str(layout["tgt_spm"]))

    def _decode(self, texts: list[str], **opts) -> list[list[str]]:
        """All hypotheses for each text, best first."""
        tokens = [self.sp_src.encode(t, out_type=str) for t in texts]
        # Bounded by the input so a looping hypothesis can't hold the whole batch
        # for 256 steps; generous enough never to clip a real translation.
        limit = min(256, 3 * max(len(t) for t in tokens) + 16)
        results = self.translator.translate_batch(
            tokens, beam_size=4, max_decoding_length=limit, max_batch_size=BATCH, **opts)
        return [[self.sp_tgt.decode(h) for h in res.hypotheses] for res in results]

    def _grounding(self, sources: list[str], targets: list[str]) -> list[float]:
        """How much likelier each target is given its source than given "."
        (mean log-prob per target token)."""
        if not targets:
            return []
        src = [self.sp_src.encode(s, out_type=str) for s in sources]
        tgt = [self.sp_tgt.encode(t, out_type=str) or ["."] for t in targets]
        real = self.translator.score_batch(src, tgt, max_batch_size=BATCH)
        blank = self.translator.score_batch([["."]] * len(tgt), tgt, max_batch_size=BATCH)
        return [(sum(r.log_probs) - sum(b.log_probs)) / len(t) for r, b, t in zip(real, blank, tgt)]

    def _unusable(self, sources: list[str], targets: list[str]) -> list[bool]:
        bad = [degenerate(s, t) for s, t in zip(sources, targets)]
        todo = [i for i, b in enumerate(bad) if not b and targets[i]]
        if todo:
            for i, g in zip(todo, self._grounding([sources[i] for i in todo], [targets[i] for i in todo])):
                bad[i] = g < GROUNDED
        return bad

    def _retry(self, sources: list[str]) -> list[str | None]:
        """Second attempt for sources whose first decode ran away or ignored the
        source. Lone words and fragments are the usual victims ("thousand" ->
        "millemilamila…", "grimly" -> "- Oh, no."), and the same text with its
        first letter's case flipped is a different token sequence the model
        usually handles ("Thousand" -> "Migliaia"); postprocess restores the
        case. Penalise repetition harder and take the first hypothesis that is
        clearly tied to the source and not a copy of it: no gloss beats junk or
        an echo of the English."""
        opts = dict(num_hypotheses=4, repetition_penalty=1.3, no_repeat_ngram_size=3)
        flipped = [s[:1].swapcase() + s[1:] for s in sources]
        out: list[str | None] = [None] * len(sources)
        for variant in (flipped, sources):
            todo = [i for i, o in enumerate(out) if o is None]
            if not todo:
                continue
            pairs = [(i, h) for i, hyps in zip(todo, self._decode([variant[i] for i in todo], **opts))
                     for h in hyps if _letters(h) != _letters(sources[i])
                     and not degenerate(sources[i], h)]
            for (i, h), g in zip(pairs, self._grounding([sources[i] for i, _ in pairs], [h for _, h in pairs])):
                if out[i] is None and g >= RETRY_GROUNDED:
                    out[i] = h
        return out

    def translate_batch(self, requests: list[SpanRequest]) -> list[str | None]:
        out: list[str | None] = []
        for i in range(0, len(requests), BATCH):
            chunk = [r.text for r in requests[i:i + BATCH]]
            first = [hyps[0] if hyps else "" for hyps in self._decode(chunk, repetition_penalty=1.1)]
            bad = [j for j, b in enumerate(self._unusable(chunk, first)) if b]
            if bad:
                for j, t in zip(bad, self._retry([chunk[j] for j in bad])):
                    first[j] = t
            out.extend(postprocess(s, t) for s, t in zip(chunk, first))
        return out
