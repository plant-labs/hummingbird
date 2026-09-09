# Hummingbird

Open-source security intelligence for Nigeria. Tracks kidnappings, robberies, terrorism,
protests, and scams with a verification-first pipeline and a live heat-bubble map.

**Core rule:** reported and verified are different states of the same record. No source, no field.

## Architecture

- **Databricks lakehouse** — bronze (raw) → silver (extract/cluster) → gold (candidates)
- **Postgres + PostGIS** — publish store, map bubbles, review queue, LISTEN/NOTIFY
- **FastAPI** — bubbles, incidents, sources, SSE, moderation
- **Next.js + MapLibre** — heat bubbles → incident list → source drill-down
- **Hosting (default):** Vercel (web) · Railway (API) · Neon (PostGIS)

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for the codebook and [docs/DEPLOY.md](docs/DEPLOY.md) for production deploy.

## Quick start (local)

### 1. Schemas + API

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e packages/schemas
pip install -r apps/api/requirements.txt
pip install -r pipelines/requirements.txt

# API uses in-memory demo store if Postgres is unreachable
cd apps/api && uvicorn app.main:app --reload --port 8000
```

### 2. Optional Postgres

```bash
cd infra && docker compose up -d
# then set DATABASE_URL=postgresql://hummingbird:hummingbird@localhost:5432/hummingbird
```

### 3. Web map

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000 — click a heat bubble → incident list → sources.

Report a tip: http://localhost:3000/report  
About: http://localhost:3000/about  
Moderation UI: http://localhost:3000/moderation  
Auth header token default: `dev-moderator-token`

### 4. News → bronze pipeline (demo)

```bash
source .venv/bin/activate
PYTHONPATH=packages/schemas:pipelines/ingest:pipelines/extract:pipelines/cluster:pipelines/sync \
  python pipelines/run_local_pipeline.py
```

Live scrape (network):

```bash
PYTHONPATH=packages/schemas python pipelines/ingest/news_scraper.py --limit 3
```

## Repo layout

```
apps/web          Next.js map + moderation
apps/api          FastAPI + SSE
packages/schemas  Shared Pydantic models
pipelines/        ingest · extract · cluster · verify · postgres sync · Databricks stubs
infra/postgres    DDL + seed
docs/             Methodology codebook
```

## Ethics

Victim names/photos are not published unless officially released. Unconfirmed incidents stay
off the default map. Casualty figures always require human review.
