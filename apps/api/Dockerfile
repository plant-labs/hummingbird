# Hummingbird API — build from repository root:
#   docker build -f apps/api/Dockerfile -t hummingbird-api .

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY packages/schemas /packages/schemas
RUN pip install --no-cache-dir /packages/schemas

COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/api/app /app/app
COPY pipelines /pipelines
COPY infra/postgres /infra/postgres
COPY scripts /scripts

ENV PYTHONPATH=/packages/schemas:/pipelines/ingest:/pipelines/extract:/pipelines/cluster:/pipelines/sync
ENV USE_DEMO_STORE=false
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["sh", "-c", "python /scripts/migrate.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
