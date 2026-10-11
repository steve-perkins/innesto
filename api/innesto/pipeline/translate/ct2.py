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

from .base import SpanRequest

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

    def translate_batch(self, requests: list[SpanRequest]) -> list[str]:
        out: list[str] = []
        for i in range(0, len(requests), BATCH):
            chunk = requests[i:i + BATCH]
            tokens = [self.sp_src.encode(r.text, out_type=str) for r in chunk]
            results = self.translator.translate_batch(
                tokens, beam_size=4, max_decoding_length=256, repetition_penalty=1.1,
                max_batch_size=BATCH)
            for res in results:
                hyp = res.hypotheses[0] if res.hypotheses else []
                out.append(self.sp_tgt.decode(hyp).strip())
        return out
