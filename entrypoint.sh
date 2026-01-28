#!/bin/sh
set -e

# Railway: always use port 8080 (hardcoded to match healthcheck)
HOST="0.0.0.0"
PORT="8080"

echo "=== Firefly [Railway] ==="
echo "  Bind: ${HOST}:${PORT}"
echo "  Data: ${FIREFLY_DATA_DIR:-/data}"

exec python -m uvicorn server:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level info
