"""Command-line pipeline.

    python -m innesto.pipeline BOOK.epub --target it -o sidecar.json
    python -m innesto.pipeline BOOK.epub --target it --no-translate -o candidates.json
    python -m innesto.pipeline --verify sidecar.json BOOK.epub

The CLI produces exactly the file the app's background job produces, so an
external tool (e.g. a Claude Code skill) can start from a candidates-only
sidecar, fill or revise `translation` fields, and import the result.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .sidecar import build_sidecar, read_sidecar, validate, verify_against_book, write_sidecar
from .translate.base import get_provider


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="innesto.pipeline", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("epub", type=Path, help="EPUB file")
    ap.add_argument("-o", "--output", type=Path, help="sidecar path (default: <epub>.<lang>.sidecar.json)")
    ap.add_argument("--source", default="en", help="source language (default: en)")
    ap.add_argument("--target", default="it", help="target language (default: it)")
    ap.add_argument("--engine", default="ct2", choices=["ct2", "echo", "none"])
    ap.add_argument("--no-translate", action="store_true", help="emit candidates with translation: null")
    ap.add_argument("--verify", type=Path, metavar="SIDECAR", help="verify an existing sidecar against the EPUB and exit")
    args = ap.parse_args(argv)

    if args.verify:
        sidecar = read_sidecar(args.verify)
        validate(sidecar)
        problems = verify_against_book(sidecar, args.epub)
        for p in problems:
            print("PROBLEM:", p, file=sys.stderr)
        print("OK" if not problems else f"{len(problems)} problem(s)")
        return 0 if not problems else 1

    engine = "none" if args.no_translate else args.engine
    provider = get_provider(args.source, args.target, engine)

    def progress(done: int, total: int) -> None:
        print(f"\rsection {done}/{total}", end="", file=sys.stderr, flush=True)

    sidecar = build_sidecar(args.epub, provider, source_lang=args.source, progress=progress)
    print(file=sys.stderr)
    out = args.output or args.epub.with_suffix(f".{args.target}.sidecar.json")
    write_sidecar(sidecar, out)
    n = sum(len(s["candidates"]) for s in sidecar["sections"])
    print(f"wrote {out} ({len(sidecar['sections'])} sections, {n} candidates, engine={provider.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
