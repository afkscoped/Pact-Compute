#!/bin/sh
set -e
# Migrations are idempotent; set PACT_RUN_MIGRATIONS=0 to skip (e.g. extra replicas).
if [ "${PACT_RUN_MIGRATIONS:-1}" = "1" ]; then python -m alembic upgrade head; fi
python -m pact.cli init
if [ "${PACT_RUN_IMPORT:-1}" = "1" ]; then
  # A failed import must not stop the API, but it must never be silent: research snapshots are missing until it succeeds.
  if python -m pact.cli import; then echo "dataset import ok";
  else code=$?; echo "ERROR: dataset import failed (exit $code); research snapshots are UNAVAILABLE until this is fixed" >&2; fi
fi
# Exit the container if either required process fails; forward termination to both.
exec python -m pact.service
