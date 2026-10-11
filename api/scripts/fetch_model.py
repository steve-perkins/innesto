"""Download and unpack a translation model into MODELS_DIR/<src>-<tgt>/.

    python -m scripts.fetch_model en it

Uses the Argos Translate package index (MIT/CC0 project; models are CTranslate2
directories plus a sentencepiece model, so no Argos runtime is needed). The
.argosmodel file is a zip; we extract it and keep only what CT2Provider reads.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from innesto import config

INDEX_URL = "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"


def main(src: str, tgt: str) -> int:
    dest = config.MODELS_DIR / f"{src}-{tgt}"
    if (dest / "model" / "model.bin").exists():
        print(f"already present: {dest}")
        return 0
    with urllib.request.urlopen(INDEX_URL, timeout=60) as r:
        index = json.load(r)
    entry = next((p for p in index if p.get("from_code") == src and p.get("to_code") == tgt), None)
    if not entry:
        print(f"no Argos package for {src}->{tgt}", file=sys.stderr)
        return 1
    url = next(l for l in entry["links"] if l.startswith("http"))
    print(f"downloading {url}")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "model.argosmodel"
        with urllib.request.urlopen(url, timeout=600) as r, open(archive, "wb") as f:
            shutil.copyfileobj(r, f)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(Path(tmp) / "x")
        # The archive contains a single top-level directory.
        root = next(p for p in (Path(tmp) / "x").iterdir() if p.is_dir())
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(root / "model", dest / "model", dirs_exist_ok=True)
        shutil.copy(root / "sentencepiece.model", dest / "sentencepiece.model")
        for name in ("metadata.json", "README.md", "LICENSE"):
            if (root / name).exists():
                shutil.copy(root / name, dest / name)
    print(f"installed {dest}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
