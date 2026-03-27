FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.8.0

COPY pyproject.toml poetry.lock ./

RUN poetry export --only main --without-hashes -o requirements.txt \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /install/bin /usr/local/bin

COPY app/ /app/app/

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8083

HEALTHCHECK --interval=5m --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8083/api/v1/scraper/health || exit 1

CMD ["python", "-m", "app"]
