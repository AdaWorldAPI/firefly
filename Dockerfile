FROM python:3.11-slim

# Railway sets PORT (default 8080). Local/Claude backend uses 8000.
# Detection: RAILWAY_ENVIRONMENT or RAILWAY_SERVICE_ID → 0.0.0.0:$PORT
#            Otherwise                                  → 127.0.0.1:8000

WORKDIR /app

# System deps for native extensions (duckdb, kuzu, lancedb)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent storage on Railway via mounted volume at /data
# Local runs use ./firefly_data (bind-mount or ephemeral)
ENV FIREFLY_DATA_DIR=/data

# Railway injects PORT=8080; local callers can override
ENV PORT=8080

# Entrypoint script handles the Railway vs local split
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

CMD ["/entrypoint.sh"]
