# Deploy Hummingbird

Production stack: **Neon (PostGIS)** + **Railway (API)** + **Vercel (web)** + **GitHub Actions (daily pipeline)**.

## What you need to provide

1. **Neon** — create a project, enable PostGIS, copy the connection string (`DATABASE_URL`).
2. **Railway** — log in when prompted; we deploy the API from this repo.
3. **Vercel** — log in when prompted; root directory `apps/web`.
4. A strong **`MODERATOR_TOKEN`** (optional for public browse; needed for `/moderation`).

## One-time setup checklist

### 1. Neon database

1. https://console.neon.tech → New Project
2. Enable extension: `CREATE EXTENSION IF NOT EXISTS postgis;`
3. Copy connection string (prefer pooled for API).

### 2. GitHub secret

In https://github.com/plant-labs/hummingbird → Settings → Secrets:

- `DATABASE_URL` = Neon URL

This powers the daily workflow in `.github/workflows/daily-pipeline.yml` (06:00 UTC, also manual “Run workflow”).

### 3. Railway API

```bash
npm i -g @railway/cli
railway login
railway init   # link plant-labs/hummingbird
railway variables set DATABASE_URL="postgresql://..."
railway variables set USE_DEMO_STORE=false
railway variables set MODERATOR_TOKEN="..."
railway variables set CORS_ORIGINS="https://YOUR_VERCEL_DOMAIN"
railway up
```

Health: `https://YOUR_RAILWAY_URL/api/health` → `store: postgres`

### 4. Vercel web

```bash
npm i -g vercel
cd apps/web
vercel login
vercel link
vercel env add NEXT_PUBLIC_API_URL   # https://YOUR_RAILWAY_URL  (no trailing slash)
vercel env add NEXT_PUBLIC_MODERATOR_TOKEN
vercel --prod
```

### 5. First data load

Trigger **Actions → Daily incident pipeline → Run workflow**, or locally:

```bash
export DATABASE_URL="..."
python scripts/migrate.py
python pipelines/run_daily.py --limit 8
# force specific articles onto the map:
python pipelines/run_daily.py --urls-only --urls \
  'https://www.bbc.com/news/articles/c4g4gpgm1m4o' \
  'https://www.tvcnews.tv/immigration-arrests-two-kidnap-suspects-recovers-n34m-in-adamawa/'
# offline test:
python pipelines/run_daily.py --demo
```

Outlets include Punch (`/tags/kidnap/`), Premium Times, Vanguard, Daily Trust, BBC, TVC, Sahara Reporters, and Arise TV.

Auto-publish writes map-ready incidents (casualty/headcount still go to `/moderation`).

## Env reference

| Service | Variable | Notes |
|---------|----------|--------|
| Railway | `DATABASE_URL` | Neon |
| Railway | `USE_DEMO_STORE` | `false` |
| Railway | `CORS_ORIGINS` | Vercel origin(s) |
| Railway | `MODERATOR_TOKEN` | shared secret |
| Vercel | `NEXT_PUBLIC_API_URL` | Railway origin |
| Vercel | `NEXT_PUBLIC_MODERATOR_TOKEN` | same secret (Phase-1) |
| GitHub Actions | `DATABASE_URL` | Neon |
| Pipeline | `AUTO_PUBLISH_MIN_SOURCES` | default `1`; set `2` for stricter bar |
