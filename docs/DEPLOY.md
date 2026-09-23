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

- `DATABASE_URL` = Neon URL **without quotes**  
  Example shape: `postgresql://USER:PASSWORD@ep-….neon.tech/neondb?sslmode=require`  
  Do **not** paste `DATABASE_URL=` or surrounding `"..."`.

This powers the daily workflow in `.github/workflows/daily-pipeline.yml` (06:00 UTC, also manual “Run workflow”).

### 3. Railway API

```bash
npm i -g @railway/cli
railway login
railway init   # link plant-labs/hummingbird
railway variables set DATABASE_URL="postgresql://..."
railway variables set USE_DEMO_STORE=false
railway variables set MODERATOR_TOKEN="..."
railway variables set REQUIRE_HUMAN_APPROVAL=true
railway variables set RESEND_API_KEY="..."
railway variables set MODERATOR_NOTIFY_EMAIL="you@example.com"
railway variables set NOTIFY_FROM_EMAIL="Hummingbird <onboarding@resend.dev>"
railway variables set PUBLIC_WEB_URL="https://YOUR_VERCEL_DOMAIN"
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

**Human approval (default):** new pipeline incidents and crowd tips go to `/moderation` as `pending` and are **not** published to the map until you approve. Set `REQUIRE_HUMAN_APPROVAL=false` only if you intentionally want auto-publish again.

You get an email (Resend) and/or webhook when something new enters the queue.

## Env reference

| Service | Variable | Notes |
|---------|----------|--------|
| Railway | `DATABASE_URL` | Neon |
| Railway | `USE_DEMO_STORE` | `false` |
| Railway | `CORS_ORIGINS` | Vercel origin(s) |
| Railway | `MODERATOR_TOKEN` | shared secret |
| Railway | `REQUIRE_HUMAN_APPROVAL` | default `true` — hold all new incidents for `/moderation` |
| Railway | `RESEND_API_KEY` | Resend API key for review emails |
| Railway | `MODERATOR_NOTIFY_EMAIL` | your inbox for review alerts |
| Railway | `NOTIFY_FROM_EMAIL` | e.g. `Hummingbird <onboarding@resend.dev>` (or verified domain) |
| Railway | `PUBLIC_WEB_URL` | Vercel origin for email deep links (no trailing slash) |
| Railway | `REPORT_NOTIFY_WEBHOOK` | optional Slack/Discord URL for every pending item (tips + pipeline) |
| Railway | `REVIEW_NOTIFY_WEBHOOK` | alias for `REPORT_NOTIFY_WEBHOOK` |
| Vercel | `NEXT_PUBLIC_API_URL` | Railway origin |
| Vercel | `NEXT_PUBLIC_MODERATOR_TOKEN` | same secret (Phase-1) |
| GitHub Actions | `DATABASE_URL` | Neon |
| GitHub Actions | `RESEND_API_KEY` / `MODERATOR_NOTIFY_EMAIL` / `NOTIFY_FROM_EMAIL` / `PUBLIC_WEB_URL` | same as Railway (pipeline sends email on enqueue) |
| GitHub Actions | `REPORT_NOTIFY_WEBHOOK` | optional |
| Pipeline | `AUTO_PUBLISH_MIN_SOURCES` | only matters when `REQUIRE_HUMAN_APPROVAL=false` |
| Pipeline | `REQUIRE_HUMAN_APPROVAL` | default `true` |

