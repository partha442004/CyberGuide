# 🚂 InternTrack on Railway.app

Deploy the full API + Postgres on Railway's free trial — **no credit card
required** (unlike Oracle Cloud, which asks for a card at signup).

> ✅ **Verified live (2026-08-02):** the API runs at
> **https://cyberguide-api-production.up.railway.app** with v1.20.0 and a
> healthy Postgres connection (`GET /health` → `{"status":"healthy","version":"1.20.0","database":"ok"}`).

Railway deploys from the repo root; the service builds with the **Dockerfile**
(`RAILWAY_DOCKERFILE_PATH=Dockerfile` on the service) and overrides the
container CMD with `railway.toml`'s `startCommand`. No Docker Hub push or SSH
server needed.

---

## How the service is configured (verified working)

| Setting | Value | Notes |
|---------|-------|-------|
| Build | `Dockerfile` | `RAILWAY_DOCKERFILE_PATH=Dockerfile` (service variable) |
| Start command | `uvicorn interntrack.main:app --host 0.0.0.0 --port 8000` | Railway runs it **literally** — no shell expansion |
| Port | `8000` | Dockerfile `EXPOSE 8000`; public domain pinned to `8000` |
| Healthcheck | *(omitted)* | Railway's internal probe couldn't reach `/health` on Dockerfile deploys; without it, SUCCESS = container running |
| Schema | `init_db()` → `create_all` at startup | No `alembic upgrade head` at deploy time (see lessons) |
| `PYTHONPATH` | `/app/src` | matches the Docker image layout |
| `DATABASE_URL` | Postgres plugin (service variable) | asyncpg → internal `*.railway.internal:5432` |
| `SECRET_KEY` | random 64-hex (service variable) | set in the dashboard |
| `DEBUG` | `false` | production mode; `/docs` disabled |

Service variables on `cyberguide-api`: `DATABASE_URL`, `SECRET_KEY`,
`PYTHONPATH=/app/src`, `APP_NAME`, `DEBUG=false`.

---

## Quick start (5 minutes)

### 1. Sign up
1. Go to [railway.app](https://railway.app) → **Start a New Project**
2. Sign in with **GitHub** (or email) — free trial credit included

### 2. Deploy from this repo
1. **Deploy from GitHub repo** → select **CyberGuide**
   (partha442004/CyberGuide)
2. Railway builds with the Dockerfile (auto-detected)

### 3. Add PostgreSQL + variables on the API service
1. **New → Database → Add PostgreSQL**; copy the `DATABASE_URL` into the API
   service → **Variables** (or reference it as a service variable)
2. Add `PYTHONPATH=/app/src`, `DEBUG=false`
3. Set a real `SECRET_KEY`:
   `python -c "import secrets; print(secrets.token_hex(32))"`

### 4. Add a public domain (pinned to port 8000)
1. Service → **Settings → Networking → Generate Domain** (or CLI:
   `railway domain -s <service> -p 8000`)
2. **Update → Port → 8000** so the proxy targets the app port
3. Open `https://<your-domain>` → `GET /health` → healthy

---

## Lessons learned (2026-08-02) — read before changing config

1. **`railway.toml` `[deploy].startCommand` OVERRIDES the Dockerfile CMD** for
   Dockerfile services and is executed **without shell expansion**:
   - `--port $PORT` and `--port ${PORT:-8000}` both fail with
     `'$PORT' is not a valid integer` — the command must be fully literal.
   - No `PORT` env var is even injected for this service (verified via
     `railway run printenv`), so bind the EXPOSE port explicitly.
2. **Do not run `alembic upgrade head` in the start command**: the app
   self-initializes the schema with `init_db()` (`Base.metadata.create_all`),
   and the Railway Postgres already has tables — `alembic upgrade head` fails
   with `DuplicateTableError: relation "jobs" already exists`. It also fails
   with `No 'script_location' key` if `alembic.ini` isn't in the image.
3. **`healthcheckPath: /health` causes Dockerfile deploys to FAIL**: the
   container starts fine but Railway's internal probe marks the deployment
   FAILED and stops the container ("Stopping Container"). Removing the
   healthcheck makes SUCCESS = container running, and the app's own `/health`
   is reachable via the pinned public domain.
4. **Pin the domain port**: `railway domain update <id> --port 8000` fixed the
   public 502 ("Application failed to respond") while the service was online.
5. **Deploying from CLI**: `railway up -s <service> -y -d` uploads the local
   directory (`.railwayignore` excludes `.env`, `data/`, caches) and deploys —
   handy when Railway's GitHub auto-deploy hasn't picked up `master` pushes.

---

## Environment variables (all optional except DATABASE_URL)

| Variable | Needed for |
|----------|-----------|
| `DATABASE_URL` | ✅ Postgres plugin (required) |
| `SECRET_KEY` | Recommended — random value; placeholder logs a warning |
| `REDIS_URL` | Shared rate limiting + cache (optional, in-memory fallback) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram notifications |
| `DISCORD_WEBHOOK_URL` | Discord notifications |
| `SLACK_WEBHOOK_URL` | Slack notifications |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | Email notifications |
| `GEMINI_API_KEY` | AI classification / learning recommendations |

---

## Redis (wired 2026-08-02)

The project's **Redis** service is connected to the API via
`REDIS_URL=redis://default:<password>@redis.railway.internal:6379` on the
`cyberguide-api` service — shared rate limiting (`RedisRateLimitStore`) and
Redis-backed cache. The app falls back to in-memory stores if Redis is ever
unreachable (never fails closed). To re-wire after a Redis password rotation,
copy the new `REDIS_URL` from the Redis service's variables
(`railway variable list -s Redis -k`) onto the API service and redeploy.

## GitHub auto-deploy (dashboard)

The repo is connected to the Railway project, but pushes to `master` do **not**
auto-deploy (the last GitHub-triggered deploy predates the current setup).
To enable it in the dashboard: **Project → Settings → GitHub App / Connected
Repo → set the deploy branch to `master`**. Until then, deploy explicitly with
`railway up -s cyberguide-api -y -d` (respects `.railwayignore`).

## How updates flow

- **`railway up`** (CLI) or a **redeploy from the dashboard** deploys the
  latest code; `init_db()` re-creates any missing tables automatically.
- **Push to master** → GitHub Actions CI validates + tests the commit.
- **Tag `v*`** → GitHub CD publishes the `kira2004/cybershield` Docker image
  on Docker Hub (release artifact; not required for Railway).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Invalid value for '--port': '$PORT'` | Start command must be fully literal — use `--port 8000` |
| `DuplicateTableError: relation ... already exists` | Remove `alembic upgrade head` from the start command |
| Deployment FAILED but app starts fine in logs | Likely the healthcheck — remove `healthcheckPath` |
| Public URL returns 502 "Application failed to respond" | Pin the domain port to 8000: `railway domain update <id> --port 8000` |
| `/health` returns 503 degraded | Postgres not linked — set `DATABASE_URL` on the API service and redeploy |
