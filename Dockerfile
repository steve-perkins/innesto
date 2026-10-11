# Innesto: single image serving the API and the built PWA.
# Build:  docker compose build     Run:  docker compose up
#
# Translation models are NOT baked in (licensing/size); mount or fetch them
# into /models at first run:  docker compose run --rm api python -m scripts.fetch_model en it

# ---- web build -------------------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- api runtime -----------------------------------------------------------
FROM python:3.12-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    INNESTO_DATA_DIR=/data INNESTO_MODELS_DIR=/models INNESTO_WEB_DIST=/app/web/dist
WORKDIR /app
COPY api/pyproject.toml api/
COPY api/innesto api/innesto
COPY api/scripts api/scripts
COPY schema schema
RUN pip install --no-cache-dir ./api \
 && python -m spacy download en_core_web_sm \
 && python -m spacy download it_core_news_sm \
 && python -m spacy download es_core_news_sm
COPY --from=web /src/web/dist web/dist
VOLUME ["/data", "/models"]
EXPOSE 8000
WORKDIR /app/api
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1
CMD ["uvicorn", "innesto.main:app", "--host", "0.0.0.0", "--port", "8000"]
