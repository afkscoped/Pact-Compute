# Build from the repo root:  docker build -t pact-compute .
# Single container: API (serves built frontend) + research worker. GPU runner is NOT in this image.
FROM node:24-slim AS web
WORKDIR /web
COPY pact-compute/frontend/package.json pact-compute/frontend/package-lock.json ./
RUN npm ci
COPY pact-compute/frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/pact-compute/backend PACT_STATE_DIR=/data \
    PACT_SOURCE_DIR=/app/PACT-Compute-data-preflight
WORKDIR /app/pact-compute
COPY pact-compute/requirements-runtime-py312.lock.txt ./
RUN python -m pip install --no-cache-dir pip==26.3 && python -m pip install --no-cache-dir -r requirements-runtime-py312.lock.txt
COPY pact-compute/backend ./backend
COPY pact-compute/alembic.ini ./
COPY --from=web /web/dist ./frontend/dist
# Only the small files the importer needs (not the large legal corpora).
COPY PACT-Compute-data-preflight/download-manifest.json PACT-Compute-data-preflight/openb_*.csv PACT-Compute-data-preflight/neso_*.json /app/PACT-Compute-data-preflight/
COPY deploy/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh && mkdir -p /data
VOLUME /data
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:%s/api/health'%os.getenv('PORT','8765'),timeout=4)"
CMD ["/entrypoint.sh"]
