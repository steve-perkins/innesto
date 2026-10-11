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
cp api/.env.example api/.env     # then fill in INNESTO_GOOGLE_CLIENT_ID (see "Sign-in" below)

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

## Sign-in and access

Innesto uses Google sign-in (Google Identity Services) and admits only the accounts listed in
`INNESTO_ALLOWED_EMAILS`. The browser gets a Google ID token, exchanges it at `POST /api/auth/google`
for a 7-day bearer token, and sends that on every API call. There is no other login.

One-time setup in the Google Cloud console (APIs & Services → Credentials):

1. Configure the OAuth consent screen (External, app name "Innesto", your support email).
2. Create an **OAuth client ID** of type **Web application**. Authorized JavaScript origins:
   `https://innesto.steveperkins.com` and `http://localhost:5173` (for local dev). No redirect
   URIs are needed (the popup flow is used).
3. Put the client id in `api/.env` locally (`INNESTO_GOOGLE_CLIENT_ID=…`, see `api/.env.example`) and
   in the server's env file (below).

Local dev: `make dev`, open http://localhost:5173, sign in. The first account to sign in inherits any
library created before sign-in existed (the old implicit "local" user).

To invite someone, add their Google email to `INNESTO_ALLOWED_EMAILS` and restart the container.
Removing an email locks that person out at their next request.

## Deploying to the VM

The production image bundles the API and the built web app; data (SQLite db, books, sidecars) lives
in the `innestodata` volume and translation models in `innestomodels` (fetched automatically on
first start). The VM side lives in the separate `docker` repo (`innesto` service, Traefik labels for
`innesto.steveperkins.com`, backup entries).

First time:

1. DNS: an A record for `innesto.steveperkins.com` pointing at the VM (Let's Encrypt HTTP-01 needs it).
2. On the VM, `docker/innesto/innesto.env` from `innesto.env.example` with the client id, a secret
   from `openssl rand -hex 32`, and the allowlist.
3. From this repo: `docker login registry.steveperkins.com` then `make release` (builds for
   linux/amd64 with buildx and pushes `:latest` and `:<git sha>`).
4. On the VM: `cd ~/docker && docker compose pull innesto && docker compose up -d innesto`, then
   `docker compose logs -f innesto` while it fetches the models and runs migrations.
5. Rebuild and push the backup image once (`innestodata` was added to its volume list).

Updates: `make release`, then step 4. Roll back by pinning `image: …/innesto:<previous sha>`.

### Database upgrades, backups and restore

- Schema changes are Alembic migrations in `api/innesto/migrations/versions`; the app applies
  pending ones at startup, so an image upgrade never needs manual steps. Databases from before
  Alembic are stamped at the baseline and upgraded in place.
- Every day at 06:30 UTC (before the VM's 07:00 backup) the app writes a consistent snapshot to
  `/data/backups/innesto-YYYYMMDD.db` (7 kept) and `innesto-latest.db` using SQLite's online backup
  API, so the volume tarball always contains a clean copy even if the live file is mid-write.
- Restore: `docker compose stop innesto`, extract the volume tarball (see the docker repo's
  `restore.py`) or copy a snapshot in, then
  `docker compose run --rm innesto python -m innesto.maintenance restore /data/backups/innesto-latest.db`
  and `docker compose up -d innesto`.

## Licenses and attributions

Innesto avoids copyleft dependencies. Notable third-party components:

- [foliate-js](https://github.com/johnfactotum/foliate-js) — MIT (vendored in `web/vendor/foliate-js`, see `VENDOR.md` there)
- [spaCy](https://spacy.io) and `en_core_web_sm` — MIT
- [wordfreq](https://github.com/rspeer/wordfreq) — code Apache-2.0; data CC BY-SA 4.0 (used at runtime, not redistributed)
- [CTranslate2](https://github.com/OpenNMT/CTranslate2) — MIT; [sentencepiece](https://github.com/google/sentencepiece) — Apache-2.0
- [Helsinki-NLP Opus-MT](https://huggingface.co/Helsinki-NLP) translation models — CC BY 4.0
- [Noto Serif and Noto Sans](https://fonts.google.com/noto) — SIL Open Font License 1.1, bundled in `web/public/fonts` (refresh with `python3 web/scripts/fetch_fonts.py`)
- FastAPI, SQLModel, lxml, React, Vite, Dexie, zustand — MIT / BSD / Apache-2.0
