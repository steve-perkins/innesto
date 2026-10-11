# Innesto: single image serving the API and the built PWA.
# Local:   docker compose build && docker compose up
# Release: make release   (buildx for linux/amd64, pushed to the private registry)
#
# Translation models are not baked in (size); the entrypoint fetches missing
# ones into the /models volume on first start.

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
    INNESTO_ENV=production INNESTO_DATA_DIR=/data INNESTO_MODELS_DIR=/models INNESTO_WEB_DIST=/app/web/dist
WORKDIR /app
COPY api/pyproject.toml api/alembic.ini api/
COPY api/innesto api/innesto
COPY api/scripts api/scripts
COPY schema schema
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN pip install --no-cache-dir ./api \
 && python -m spacy download en_core_web_sm \
 && python -m spacy download it_core_news_sm \
 && python -m spacy download es_core_news_sm
COPY --from=web /src/web/dist web/dist
VOLUME ["/data", "/models"]
EXPOSE 8000
WORKDIR /app/api
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
