#!/bin/sh
# Innesto container entrypoint.
# 1. Fetch any missing translation models into the models volume (one-time,
#    ~90 MB per language pair) unless INNESTO_AUTO_FETCH_MODELS=0.
# 2. Start the API; schema migrations run during application startup.
set -eu

cd /app/api

if [ "${INNESTO_AUTO_FETCH_MODELS:-1}" != "0" ]; then
  python - <<'PY'
import subprocess, sys
from innesto import config
src = "en"
for code in config.SUPPORTED_TARGETS:
    if not (config.MODELS_DIR / f"{src}-{code}" / "model" / "model.bin").exists():
        print(f"[entrypoint] fetching translation model {src}->{code} ...", flush=True)
        rc = subprocess.call([sys.executable, "-m", "scripts.fetch_model", src, code])
        if rc != 0:
            print(f"[entrypoint] WARNING: could not fetch {src}->{code}; books in that language will not be processed", flush=True)
PY
fi

exec uvicorn innesto.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips='*' "$@"
