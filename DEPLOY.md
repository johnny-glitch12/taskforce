# Task Force AI — Production Deployment Guide

This document walks through deploying Task Force AI to **Railway** (recommended) and
references the alternative paths.

> **Note for Emergent's "Save to GitHub"**: Emergent's own deploy pipeline expects
> `.env` files committed to the repo (it auto-injects production values at deploy
> time). For Railway / Fly / Render / Heroku / etc., env vars live in the platform's
> dashboard. The repo's `.gitignore` keeps `.env` out of git by default — safest for
> non-Emergent deploys. If you switch to Emergent deploy, remove `.env` from
> `.gitignore` first (or commit a scrubbed template).

## Architecture

A single Docker container runs:
- **FastAPI / Uvicorn** on `$PORT` (Railway injects)
- Serves the React SPA from `backend/spa/` at every non-API path
- Serves the API at `/api/*`
- Optionally launches a Celery worker in the background (see `ENABLE_INLINE_CELERY`)

For high-volume production, split the worker into a separate Railway service
using `Dockerfile.worker`.

## Files in this repo for deploy

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage build (Node → Python). Default for Railway. |
| `Dockerfile.worker` | Dedicated Celery worker image. |
| `.dockerignore` | Excludes git, tests, memory, env files. |
| `railway.toml` | Railway config (Dockerfile builder + healthcheck). |
| `Procfile` | Heroku-style fallback declaration. |
| `runtime.txt` | Pins Python 3.11. |
| `nixpacks.toml` | Alternative to Dockerfile (Railway Nixpacks). |
| `scripts/start.sh` | Container entrypoint — Celery (BG) + Uvicorn (FG). |
| `.env.production.example` | Template for the env vars to set in Railway. |

## Step-by-step Railway setup

### 1. Push to GitHub

```bash
git add Dockerfile* railway.toml Procfile runtime.txt nixpacks.toml \
        scripts/start.sh .dockerignore .env.production.example DEPLOY.md
git commit -m "Add Railway deployment config"
git push
```

### 2. Create the Railway project

1. Go to https://railway.app/dashboard → **New Project** → **Deploy from GitHub repo**
2. Pick your repo
3. Railway detects the `Dockerfile` and starts the first build (will fail until env vars are set — that's expected)

### 3. Provision Redis

1. In your project canvas, click **+ New** → **Database** → **Redis**
2. Railway provisions Redis automatically and exposes `REDIS_URL`

### 4. Provision MongoDB

**Recommended: MongoDB Atlas free tier** (better than Railway's managed Mongo —
managed, backed up, 512 MB free forever):

1. Go to https://www.mongodb.com/cloud/atlas → create free M0 cluster
2. Database Access → Create user (strong password)
3. Network Access → Add IP `0.0.0.0/0` (Railway egress is dynamic)
4. Connect → Drivers → copy the connection string

### 5. Set environment variables

In your Railway web service → **Variables** tab, add (using values from
`.env.production.example` as a template):

```env
# Network
PLATFORM_URL=https://taskforce.run
CORS_ORIGINS=https://taskforce.run,https://www.taskforce.run

# MongoDB Atlas
MONGO_URL=mongodb+srv://USER:PASSWORD@cluster.xxx.mongodb.net/?retryWrites=true&w=majority
DB_NAME=taskforce

# Redis (reference Railway's plugin via the magic variable syntax)
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}

# Auth (generate with: python -c "import secrets; print(secrets.token_urlsafe(48))")
JWT_SECRET=<64-char-random-string>
JWT_EXPIRY_HOURS=24

# Stripe
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PUBLISHABLE_KEY=pk_live_...

# Resend (email)
RESEND_API_KEY=re_...
EMAIL_FROM=Task Force AI <noreply@taskforce.run>

# LLM keys (one of these — Emergent universal works for all 3)
EMERGENT_LLM_KEY=...
# OR
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...

# BYOK
# Generate Fernet keys with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
BYOK_FERNET_KEY=<base64-fernet-key>
BYOK_MASTER_KEY=<base64-fernet-key>
BYOK_KMS_PROVIDER=local

# Optional tuning
ENABLE_INLINE_CELERY=true
CELERY_CONCURRENCY=2
UVICORN_WORKERS=1
```

### 6. Trigger deploy

Push any commit (or click **Deploy** in Railway). The Dockerfile build will:

1. **Stage 1 (Node)**: `yarn install` → `yarn build` with `PUBLIC_URL=/spa` → output to `frontend/build/`
2. **Stage 2 (Python)**: install `requirements.txt`, copy `backend/`, copy frontend build into `backend/spa/`
3. **Run**: `bash scripts/start.sh` → Celery worker (BG) + Uvicorn on `$PORT`

### 7. Wire your custom domain

1. Railway → web service → **Settings** → **Networking** → **Custom Domain** → add `taskforce.run`
2. Railway shows a CNAME target (e.g. `your-service.up.railway.app`)
3. At your DNS provider (Cloudflare / GoDaddy / Namecheap), add a CNAME `@` → that target
4. Wait 1-5 min, then `taskforce.run` resolves to your container

### 8. Update Stripe webhook URL

After domain is live:
- Stripe Dashboard → Developers → Webhooks → edit your endpoint to `https://taskforce.run/api/webhook/stripe`
- Make sure the **Webhook secret** matches `STRIPE_WEBHOOK_SECRET` in Railway env

### 9. Verify Resend DNS (if not yet done)

If transactional emails should land in inboxes (not spam folder):
- Resend Dashboard → Domains → `taskforce.run` → copy the SPF, DKIM, DMARC records
- Add them at your DNS provider (Cloudflare: **turn off proxy** for these records)
- Click **Verify DNS Records** in Resend — green checkmarks within 1-60 min

## Health check

Railway hits `GET /api/health` every few seconds. The endpoint returns:

```json
{
  "status": "healthy",
  "timestamp": "2026-02-04T12:00:00+00:00",
  "services": {
    "mongodb": "connected",
    "redis": "connected"
  }
}
```

When any dep is down, `status` flips to `degraded` (HTTP 200 — Railway is still
happy, we just lose the failing feature surface).

## Splitting the worker into a separate Railway service (optional, for production scale)

By default the web container runs Celery inline via `scripts/start.sh`. For
production scale, split it:

1. In Railway → **+ New** → **GitHub Repo** → same repo
2. Settings → Build → **Dockerfile path**: `Dockerfile.worker`
3. Copy the same env vars (esp. `MONGO_URL`, `REDIS_URL`, `BYOK_*`, all LLM keys)
4. On the original web service, set `ENABLE_INLINE_CELERY=false` to disable the inline worker

## Local smoke test (BEFORE pushing)

```bash
# 1. Build the React SPA
cd frontend
CI=false GENERATE_SOURCEMAP=false REACT_APP_BACKEND_URL="" PUBLIC_URL=/spa npm run build
cd ..

# 2. Copy build into backend/spa
rm -rf backend/spa && cp -r frontend/build backend/spa

# 3. Start the backend (it'll auto-detect backend/spa and mount the SPA)
cd backend && uvicorn server:app --host 0.0.0.0 --port 8000

# 4. Visit http://localhost:8000  — should show the React app
# 5. Hit http://localhost:8000/api/health — should return JSON
# 6. Hit http://localhost:8000/pricing — should serve the React app (SPA route)
```

## Common gotchas

- **`emergentintegrations` PyPI mirror** — this package lives on Emergent's
  CloudFront mirror (`https://d33sy5i8bnduwe.cloudfront.net/simple/`), not on
  public PyPI. Both Dockerfiles already pass `--extra-index-url` to pip so the
  Railway build resolves it transparently. If you ever swap out pip for `uv`
  or another resolver, mirror the same extra-index flag.
- **`/static/*` collision** — the codebase already uses `/static/exchange/*` for
  marketplace listing media. The CRA build is configured with `PUBLIC_URL=/spa`
  so its bundle paths live under `/spa/static/*` and don't collide.
- **Frontend env in browser** — `process.env.REACT_APP_*` values are baked into
  the build at compile time. In production single-container mode,
  `REACT_APP_BACKEND_URL=""` means every fetch is relative (same-origin) — good.
- **Don't `console.log` secrets** — Railway logs are visible to anyone with
  project access.
- **Cold-start tax** — the first request after a Railway deploy may take ~5s
  while the container warms.
- **MongoDB IP allowlist** — Atlas must be set to `0.0.0.0/0` because Railway
  egress IPs are not stable.
- **HTTPS forward** — Railway terminates TLS at its proxy; the container
  always speaks HTTP. The `--proxy-headers --forwarded-allow-ips='*'` flags
  in `start.sh` make FastAPI trust `X-Forwarded-*` headers so `request.url`
  resolves correctly under HTTPS.

## Rollback

Railway → web service → **Deployments** → pick a previous successful build →
**Redeploy**. No code changes needed.
