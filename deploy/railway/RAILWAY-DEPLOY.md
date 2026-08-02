# 🚂 InternTrack on Railway.app

Deploy the full API + Postgres on Railway's free trial — **no credit card
required** (unlike Oracle Cloud, which asks for a card at signup).

Railway reads `railway.toml` at the repo root and auto-deploys on every push
to the connected branch. No Docker Hub push or SSH server needed.

---

## Quick start (5 minutes)

### 1. Sign up
1. Go to [railway.app](https://railway.app) and click **Start a New Project**
2. Sign in with **GitHub** (or email) — free trial credit is included

### 2. Deploy from this repo
1. Click **Deploy from GitHub repo**
2. Select the **CyberGuide** repository (partha442004/CyberGuide)
3. Railway detects `railway.toml` automatically and starts building
   (Nixpacks: `pip install -r requirements.txt`)

> If Railway asks for a repo or deploys an empty project, click **New → GitHub
> Repo** and pick CyberGuide.

### 3. Add PostgreSQL
1. In your project, click **New → Database → Add PostgreSQL**
2. Railway injects `DATABASE_URL` automatically — no config needed
3. The deploy `startCommand` already runs `alembic upgrade head` before
   starting the API, so migrations apply automatically on every deploy

### 4. Set the SECRET_KEY (important)
1. Generate one: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Open the API service → **Variables** → **New Variable**
3. Name: `SECRET_KEY`, Value: the generated key (overrides the committed
   `change-me-in-production` placeholder)

### 5. (Optional) Add Redis for shared rate limiting / cache
1. **New → Database → Redis**
2. Copy the Redis URL and add a variable `REDIS_URL` on the API service
   (the app falls back to in-memory stores when this is unset, so it is
   optional on the free tier)

### 6. Open the app
- Railway shows a **Deploy URL** on the service (e.g. `https://cyberguide-xxxx.up.railway.app`)
- Health check: `GET {url}/health` → `{"status":"healthy","version":"1.20.0","debug":false}`
- API docs: `{url}/api/docs` (when not in production mode) or `{url}/docs`

---

## Environment variables (all optional except DATABASE_URL)

| Variable | Needed for |
|----------|-----------|
| `DATABASE_URL` | ✅ auto-injected by the Postgres plugin (required) |
| `SECRET_KEY` | Recommended — random value; placeholder logs a warning |
| `REDIS_URL` | Shared rate limiting + cache (optional, in-memory fallback) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram notifications |
| `DISCORD_WEBHOOK_URL` | Discord notifications |
| `SLACK_WEBHOOK_URL` | Slack notifications |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | Email notifications |
| `GEMINI_API_KEY` | AI classification / learning recommendations |

---

## How updates flow

- **Push to master** → CI (GitHub Actions) validates + tests, and Railway
  auto-deploys the new commit (migrations run automatically).
- **Tag `v*`** → GitHub CD publishes the `kira2004/cybershield` Docker image
  on Docker Hub (release artifact; not required for Railway).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Build fails on `pip install` | Check the deploy logs; Nixpacks uses the root `requirements.txt` |
| `/health` returns 503 | Postgres not linked yet — add the PostgreSQL plugin and redeploy |
| Migrations not applied | They run via `alembic upgrade head` in `startCommand`; check deploy logs for `alembic` errors |
| Restarts in a loop | Inspect `railway logs` (Deployments tab) — most common cause is `DATABASE_URL` missing |
