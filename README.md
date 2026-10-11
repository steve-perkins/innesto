# Innesto

**Innesto** (Italian for *graft*) is an ebook reader for language learners. You read books you
already own, in a language you already know, and Innesto grafts words and phrases from the language
you are learning into the text:

> John is reading **un libro**.

Swapped phrases are shown in a distinct color; tap one to see the original text. Two controls decide
how much of the page is swapped: **Level** (from common single words up to rare vocabulary and whole
clauses) and **Density** (how many swaps per page).

The approach is the **diglot weave** technique: reading native-language text in which a growing share
of the words and phrases has been replaced with the target language, so that vocabulary and grammar
are absorbed in context. Italian and Spanish are supported so far; the design is language-neutral.

## How it works

1. You upload an EPUB. It is stored and shown in your library.
2. A background pipeline produces a **sidecar** for the book and target language: every candidate
   phrase that *could* be swapped, with its translation and a difficulty level. Candidate selection
   and difficulty use spaCy and word-frequency data; translation uses self-hosted Opus-MT models via
   CTranslate2. Nothing leaves your machine and there is no per-use cost.
3. The reader applies your Level and Density to the sidecar on the fly. Changing them is instant and
   works offline.

The sidecar is a plain JSON file with a published schema (`schema/sidecar.schema.json`). Sidecars can
be produced by the built-in pipeline or by any external tool (for example a Claude Code skill that
reviews or improves translations) and imported into the app.

## Repository layout

```
api/        FastAPI backend + processing pipeline (Python 3.12)
web/        React + TypeScript PWA (Vite); web/vendor/foliate-js renders the books
schema/     Sidecar JSON Schema, the contract between pipeline, external tools and reader
data/       Runtime data in local dev: books, covers, sidecars, SQLite (git-ignored)
```

## Local development

Requirements: Python 3.12, Node 20+.

```bash
# one-time setup
cd api && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/python -m spacy download en_core_web_sm && cd ..
cd web && npm install && cd ..

# run API (http://localhost:8000) and web app (http://localhost:5173) together
make dev

# tests
make test
```

The web dev server proxies `/api` to the API. Open http://localhost:5173, add an EPUB, read.

### Translation model

Processing needs a CTranslate2 model for the language pair under `api/models/<src>-<tgt>/`.
The simplest source is an Argos Translate package (CT2 model + sentencepiece, no PyTorch):

```bash
cd api && .venv/bin/python -m scripts.fetch_model en it   # Italian
cd api && .venv/bin/python -m scripts.fetch_model en es   # Spanish
```

Supported target languages are listed in `api/innesto/config.py` (`SUPPORTED_TARGETS`); adding one
means adding it there, fetching its model, and installing the matching spaCy model
(`python -m spacy download xx_core_news_sm`) for target-lemma extraction.

Until a model is present, uploads are not processed automatically; the library shows
"Not processed" and the **Process** button reports the missing model. `INNESTO_TRANSLATION_ENGINE=echo`
runs the pipeline with a stub engine for development.

### Working with sidecars from outside the app

```bash
# candidates only (translation: null), for an external tool to fill
.venv/bin/python -m innesto.pipeline book.epub --target it --no-translate -o book.it.json
# check a (hand-edited or externally generated) sidecar against the book
.venv/bin/python -m innesto.pipeline --verify book.it.json book.epub
```

Import the result from the library card menu ("Import sidecar…") or `POST /api/books/{id}/sidecars`.
The imported sidecar becomes the active one; earlier ones are kept and can be re-activated.

## Licenses and attributions

Innesto avoids copyleft dependencies. Notable third-party components:

- [foliate-js](https://github.com/johnfactotum/foliate-js) — MIT (vendored in `web/vendor/foliate-js`, see `VENDOR.md` there)
- [spaCy](https://spacy.io) and `en_core_web_sm` — MIT
- [wordfreq](https://github.com/rspeer/wordfreq) — code Apache-2.0; data CC BY-SA 4.0 (used at runtime, not redistributed)
- [CTranslate2](https://github.com/OpenNMT/CTranslate2) — MIT; [sentencepiece](https://github.com/google/sentencepiece) — Apache-2.0
- [Helsinki-NLP Opus-MT](https://huggingface.co/Helsinki-NLP) translation models — CC BY 4.0
- FastAPI, SQLModel, lxml, React, Vite, Dexie, zustand — MIT / BSD / Apache-2.0
