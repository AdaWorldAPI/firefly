#!/bin/sh
set -e

# Detect environment
if [ -n "$RAILWAY_ENVIRONMENT" ] || [ -n "$RAILWAY_SERVICE_ID" ]; then
    # Railway: bind to 0.0.0.0, PORT is injected (default 8080)
    HOST="0.0.0.0"
    PORT="${PORT:-8080}"
    echo "=== Firefly [Railway] ==="
    echo "  Bind: ${HOST}:${PORT}"
    echo "  Data: ${FIREFLY_DATA_DIR:-/data}"
else
    # Local / Claude backend: bind to loopback only
    HOST="127.0.0.1"
    PORT="${PORT:-8000}"
    echo "=== Firefly [local] ==="
    echo "  Bind: ${HOST}:${PORT}"
    echo "  Data: ${FIREFLY_DATA_DIR:-./firefly_data}"
fi

exec python -m uvicorn server:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level info
