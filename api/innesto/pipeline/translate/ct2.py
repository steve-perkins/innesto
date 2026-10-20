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


def find_layout(model_dir: Path) -> dict | None:
    if (model_dir / "model" / "model.bin").exists() and (model_dir / "sentencepiece.model").exists():
        return {"kind": "argos", "ct2": model_dir / "model",
                "src_spm": model_dir / "sentencepiece.model", "tgt_spm": model_dir / "sentencepiece.model"}
    if (model_dir / "model.bin").exists() and (model_dir / "source.spm").exists():
        return {"kind": "marian", "ct2": model_dir,
                "src_spm": model_dir / "source.spm", "tgt_spm": model_dir / "target.spm"}
    return None


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
        self.name = f"{layout['kind']}-{source_lang}_{target_lang}-{version}".rstrip("-")
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

    def _retry(self, sources: list[str]) -> list[str | None]:
        """Second attempt for sources whose first decode ran away. Lone words are
        the usual victims ("thousand" -> "millemilamila…"), and the same word with
        its first letter's case flipped is a different token sequence the model
        usually handles ("Thousand" -> "Migliaia"); postprocess restores the case.
        Penalise repetition harder and take the first sane hypothesis."""
        opts = dict(num_hypotheses=4, repetition_penalty=1.3, no_repeat_ngram_size=3)
        flipped = [s[:1].swapcase() + s[1:] for s in sources]
        out: list[str | None] = [None] * len(sources)
        for variant in (flipped, sources):
            todo = [i for i, o in enumerate(out) if o is None]
            if not todo:
                continue
            for i, hyps in zip(todo, self._decode([variant[i] for i in todo], **opts)):
                out[i] = next((h for h in hyps if not degenerate(sources[i], h)), None)
        return out

    def translate_batch(self, requests: list[SpanRequest]) -> list[str | None]:
        out: list[str | None] = []
        for i in range(0, len(requests), BATCH):
            chunk = [r.text for r in requests[i:i + BATCH]]
            first = [hyps[0] if hyps else "" for hyps in self._decode(chunk, repetition_penalty=1.1)]
            bad = [j for j, (s, t) in enumerate(zip(chunk, first)) if degenerate(s, t)]
            if bad:
                for j, t in zip(bad, self._retry([chunk[j] for j in bad])):
                    first[j] = t
            out.extend(postprocess(s, t) for s, t in zip(chunk, first))
        return out
