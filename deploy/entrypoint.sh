#!/bin/sh
set -e
# Migrations are idempotent; set PACT_RUN_MIGRATIONS=0 to skip (e.g. extra replicas).
if [ "${PACT_RUN_MIGRATIONS:-1}" = "1" ]; then python -m alembic upgrade head; fi
python -m pact.cli init
[ "${PACT_RUN_IMPORT:-1}" = "1" ] && { python -m pact.cli import || echo "dataset import failed; research snapshots unavailable"; }
if [ "${PACT_RUN_WORKER:-1}" = "1" ]; then python -m pact.worker & fi
exec python -m uvicorn pact.api:app --host 0.0.0.0 --port "${PORT:-8765}" --proxy-headers --forwarded-allow-ips='*'
