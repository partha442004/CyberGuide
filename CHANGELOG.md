# Changelog

All notable changes to the InternTrack project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

### Fixed

- **0.0% resume matches eliminated.** Jobs tagged only with the generic
  word "security" (very common in scraper tag lists) scored 0.0 against a
  resume listing "cybersecurity", because the synonym map had no
  security-domain group. Added domain-level synonym groups
  (security/cybersecurity/infosec, software engineering roles, data
  science roles) so generic tags earn synonym credit — live check: IBM
  "Security Consultant" went 0.0% → 42%.

### Fixed

- **Resume match-batch / match 500 on skill-less jobs (the "Match API
  unavailable" error in the dashboard).** Any job whose `tags` and skill
  columns were empty (common for share-a-job entries and thin scrapes)
  scored `None`; the endpoints then tried to insert
  `ResumeMatchResult(match_score=None)` into a NOT NULL column, raising an
  IntegrityError that surfaced as HTTP 500 — so the dashboard's "Find Best
  Matching Jobs" silently failed. Persisting is now skipped for None
  scores while the response still returns `match_score: null` for those
  jobs. Verified live: a 3-job batch that 500'd now returns 200 with a
  real score for skill-tagged jobs and `null` for the rest.
- **Digest location split now works for the default user.** The email /
  Telegram "📍 Your area / 🌍 Other locations" split required a user
  profile with a location; the legacy `user1` path (no profile) never got
  it. `_deliver_alert` now falls back to `DEFAULT_LOCATION` ("Bangalore"),
  matching what discovery already searches — so the default user's digest
  renders the split and role × location table too.

### Notes

- **Hirist & Cutshort probed as new India sources:** Hirist 404s on its
  search URL patterns and Cutshort renders job cards client-side via
  Algolia (its `__NEXT_DATA__` holds no postings), so neither is reliably
  scrapable server-side. The reliable source set stays LinkedIn India,
  the 11 security-vendor Greenhouse boards, RSS feeds and Internshala.

## [1.26.0] - 2026-08-07

### Added

- **Email-parity Telegram digest.** Telegram alerts now mirror the email
  layout: with a preferred location set, jobs split into **📍 Your area**
  vs **🌍 Other locations** banners, and the digest closes with a real
  role × location HTML table (Telegram sends with HTML parse mode). Also
  fixed the email's dead "Other locations" section — location filtering
  was dropping those jobs before the builders could split them.
- **4 more security-vendor Greenhouse boards** (all verified reachable):
  Expel, Dragos, Tanium, Sumo Logic — alongside Zscaler, Okta,
  Cloudflare, KnowBe4, Veracode, BeyondTrust, Threatlocker.

## [1.25.0] - 2026-08-07

### Added

- **Security-domain classifier v2.** The alert/dashboard domain bucket now
  recognizes the full modern security title set — GRC, threat
  intelligence, penetration testing, OSINT, DFIR, forensics, bug bounty,
  zero trust, cloud/network security, and web-app attack terms (SQLi,
  XSS, CSRF) — so SOC / VAPT / GRC roles always land in the
  "security" category.
- **SQLi → security fix.** Resume matching (`match_score_v2`) and the
  resume parser now compare skills on word boundaries, so a security
  resume that lists "sqli" / "SQL injection" is scored as a security
  candidate instead of being pulled into coding/data by the bare "sql"
  keyword (this is what previously surfaced SQL-developer jobs to a
  cybersecurity resume).

### Fixed

- **Internshala source restored.** The reliable HTML scraper
  (`InternshalaDirectScraper`) was being silently overwritten in the
  registry by a broken JSON-API adapter under the same key — Internshala
  always returned 0 jobs. The direct scraper now wins.
- **Dead/bot-gated RSS feeds dropped.** remoteok (410), Naukri RSS (404),
  Instahyre (Cloudflare 403), LinkedIn jobs "RSS" (login wall) and the
  hnrss feeds (news shells) are gone; feeds now support {query}/{location}
  placeholders.
- **Naukri scraper headers.** The jobapi now gets the appid/systemid/
  browser headers it requires (still reCAPTCHA-gated server-side, but no
  longer a blind 400).

## [1.24.0] - 2026-08-07

### Added

- **Job-type inference.** Scrapers rarely provide a job_type, so the
  dashboard job-type chart was ~98% "unknown". New `classify_job_type`
  infers internship / part-time / contract / freelance from explicit
  title markers and defaults the rest to full-time (matches reality for
  ~95% of postings). Applied at save time; `POST /jobs/backfill-job-types`
  backfilled the live DB — chart went from 580 unknown to 590 full-time
  + 1 internship.

## [1.23.0] - 2026-08-07

### Added

- **Application follow-up reminders in the daily digest.** Applications that
  are applied/interviewing but still un-reminded now appear in a leading
  "⏰ Follow up" section of the email and Telegram alerts (capped at 5),
  so you get nudged to chase applications you haven't heard back from.
  Scoped per user (multi-user safe) and marked reminded only after a
  channel actually delivered.
- **Salary + experience badges on job cards.** Alert cards now show a
  compact salary line (INR → ₹6L / ₹25K, USD → $80k) and experience level
  when the source provides them, alongside the existing match %, expiry
  and age badges.

## [1.22.0] - 2026-08-07

### Added

- **Cross-source duplicate detection.** The same posting is frequently
  scraped by several boards (LinkedIn India, Indeed India, TimesJobs,
  Internshala) under different URLs, so URL-only dedup let 2-3 copies of
  one job into the DB (e.g. "Penetration Tester | Brillio" twice).
  `JobRepository.find_cross_source_duplicate` fetches recent candidates
  by company and compares normalized titles (case-insensitive,
  punctuation/whitespace collapsed) in Python — wired into
  `JobService.create_job` after the URL check.
- **Closing-soon section in daily alerts.** The daily digest (email +
  Telegram) now leads with a "🚨 Closing soon" block listing the up-to-5
  jobs expiring within 2 days, so deadlines are visible before they pass.

## [1.21.1] - 2026-08-07

### Fixed

- **India/Bangalore job discovery was returning ZERO India jobs.** The live
  DB had 521 jobs but none from Bangalore/India, so configured
  cybersecurity+Bangalore alerts never matched anything. Root cause: the
  discovery query builder appended location-suffixed queries ("cybersecurity
  bangalore") AFTER plain ones and the [:limit] cap truncated them away;
  and discovery never passed a location to the scrapers, so the US guest
  APIs (geo-locked) returned US jobs regardless of the query keywords.
  - `discovery_queries_for`: location-suffixed queries now go FIRST so the
    cap keeps "cybersecurity Bangalore" instead of plain "cybersecurity".
  - `run_discovery_for_users`: passes each user's location to
    `registry.fetch_all`, activating the India scrapers (LinkedIn India,
    Internshala, TimesJobs, Indeed India).
  - `run_discovery`: extracts an Indian city from the query string
    ("cybersecurity bangalore" → query + location="Bangalore") via the new
    whole-word `_extract_location_from_query` helper.
  - `search_jobs`: now also matches the `location` field, so searching
    "bangalore" finds jobs by location (was title/company/description only).
  - Verified live: search "bangalore" now returns 8 real Bangalore security
    jobs (Barracuda, Zscaler, Brillio) after seeding runs.

## [1.20.13] - 2026-08-07

### Fixed

- **CI fully green on GitHub Actions again** — all six jobs pass:
  Lint (ruff), Typecheck (mypy), Version consistency, Security (bandit +
  safety + trivy), Tests (pytest, 2262 tests), and Smoke (live API boot).
  This round fixed:
  - **Lint:** 46+ ruff errors (E501 line-length, ISC004 parenthesized
    regex strings, S110 noqa on intentional PDF fallbacks, ARG/DTZ/B904)
    across scrapers, services, and API modules.
  - **Real runtime bugs:** missing `JobRepository` import in
    `api/v1/jobs.py` (NameError on any jobs endpoint), missing `uuid4`/`or_`
    imports in `job_repository.py`, and missing JWT Settings fields
    (`jwt_secret_key`, `jwt_algorithm`, token expiries, API quotas) in
    `config.py` — the latter was an AttributeError crash for JWT auth and
    usage tracking.
  - **JWT hardening:** `exp` claim now stored as standard epoch-seconds
    integer; `decode_token` rejects missing/past `exp` (the old PyJWT path
    auto-validated this — the stdlib fallback now does too).
  - **mypy:** 50+ errors fixed across 12 files (Column assignment ignores,
    `str()` coercion of Column attrs, dict annotations, scheduler signature
    mismatch, typed `to_naive_utc`). Full src tree now type-clean.
  - **Date-flaky tests:** `test_scheduler_jobs.py` expiry tests hardcoded
    `2026-08-07T00:00:00` (now in the past) so `_expiry_note` returned
    "Expired" instead of "Closing soon". Dates are now computed relative
    to `datetime.now(UTC)` so they pass on any day.
  - **CI infra flakiness:** the mypy/lint jobs failed repeatedly from the
    GitHub Actions outage ("Failed to resolve action download info. Service
    Unavailable") — re-runs pass; the fitz `type: ignore` now covers both
    the local env (import-untyped) and CI (import-not-found).



## [1.20.12] - 2026-08-06

### Fixed

- **Job discovery 500 on Vercel — root cause found and fixed.** Discovery
  scraped fine but every save to the Neon Postgres DB crashed with
  `StringDataRightTruncationError: value too long for type character
  varying(200)`. SQLite (local dev) doesn't enforce varchar lengths, so this
  was invisible locally: a scraper returned a company/location over 200
  chars and Postgres rejected the insert → the whole request returned
  INTERNAL_ERROR. Job fields are now clamped to the model's column limits
  (`title` 500, `company` 200, `location` 200, `url` 2000) in
  `JobService.create_job`, so every save path (discovery, share-a-job,
  create API) is safe. Verified end-to-end against the live Neon DB and the
  live Vercel API: `POST /discovery/run` → `{"discovered":88,"saved":10}`.
- **Vercel discovery timeout** — `vercel.json` now sets `maxDuration: 60`
  and `run-for-users` stops early once a 50s budget is used, so the cron's
  multi-query discovery finishes before the serverless limit instead of
  dying with a 500.
- **Dashboard discovery query was silently ignored** — `run_discovery`
  declared `body: dict | None = None` without `Body()`, so FastAPI treated
  it as a query parameter and the JSON `{"query": ...}` from the dashboard
  was dropped (it always searched the default "python developer"). The body
  is now read via `Body(default=None)` with an `isinstance` guard.
- **CI gates** — fixed a ruff PT018 composite assertion and an unformatted
  block in `dashboard/app.py`, plus a mypy error in
  `cybershield/services/resume_service.py` (pymupdf `Document` is not
  iterable in its type stubs; now iterates `page_count`/`load_page`), and
  synced the `FakeDoc` test fixture to the real pymupdf API. Full CI (lint,
  typecheck, security, version, tests, smoke) is green again.

## [1.20.11] - 2026-08-06

### Added

- **Share a job** — `POST /api/v1/jobs/share` accepts *any* job link (LinkedIn
  feed post, company careers page, any job board), auto-fetches the page's
  OpenGraph title/company/description, dedupes by URL, and saves it. Shared
  jobs appear in the dashboard **and** in the daily email/Telegram alerts.
  The dashboard's Jobs page has a new *Share a Job* tab (works even with zero
  saved jobs).
- **Hardened LinkedIn scraper** — the guest jobs API still returns real
  cybersecurity jobs, but the parser only looked for legacy `result-card`
  classes that LinkedIn removed. The scraper now tries the legacy selectors
  first and falls back to the current 2024+ `base-search-card` /
  `job-search-card` markup, adds browser-like headers, and detects the
  auth-wall/999 response so it degrades gracefully instead of silently
  contributing 0 jobs.
- **Per-user access tokens** — register/login return a secret access token
  (checked at login, rotated via `POST /api/v1/users/{id}/rotate-token`).
  Tracking data (applications, watchlist, personalized overview) is scoped
  per user by `user_id`, so each account only sees its own data.
- **Per-user discovery** — `POST /api/v1/jobs/discovery/run-for-users` builds
  search queries from each enabled user's categories/skills; the daily-refresh
  cron now calls it so alerts are personalized end-to-end.
- **Company watchlist** — new `watchlists` API (list/add/remove); watched
  companies are highlighted in the daily digest. Dashboard watchlist UI added.
- **Personalized Overview** — `/dashboard/overview` and chart endpoints accept
  `user_id` and scope application metrics to that user's own tracking.
- **Dashboard: real Apply tracking + status updates** — the Apply button now
  actually creates an application via the API (with the logged-in user) and
  status updates call the backend instead of showing a fake toast.
- **Dashboard: job-card match % + expiry badges, search + filters** — cards
  show resume match score and closing-soon badges; Saved Jobs gained
  keyword/remote/domain filters and sorting.

### Fixed

- Dashboard Jobs page crash — `_category_header` KeyError when real jobs
  existed (`_CATEGORY_STYLE` had no `icon` key); now defensive and every
  category has an icon.

## [1.20.10] - 2026-08-04

### Added

- **Resume upload/match endpoints now live on Vercel** — deployed the
  cybershield resume router on the Vercel entrypoint (`api/index.py`),
  patched the DB session to use the same engine as the interntrack app
  (avoids asyncpg "different loop" crash), and removed the FK constraint on
  `resume_data.user_id` so users can upload without a pre-existing account.
  Verified live: `POST /api/v1/resumes/upload` returns parsed skills,
  `GET /api/v1/resumes/{user_id}` returns stored data, and
  `POST /api/v1/resumes/match-batch` returns proper validation.
- **Streamlit dashboard now has a fully working Resume Match page** — upload
  your PDF resume, see parsed skills/education/experience/certifications, and
  click "Find Best Matching Jobs" to batch-match your resume against all
  saved jobs (match score %, matched/missing skills, suggestions).
- **Discovery page now uses POST** (the correct API method) with a proper
  spinner, success/error messages, and tips.
- **Jobs page split into two tabs** — "Discovery" (run scrapers) and "Saved
  Jobs" (browse, view, apply).
- **Settings page** shows the live API URL and has a "Clear Cache" button.

### Fixed

- **Resume upload returned empty parse results on Vercel** — the PDF text
  fallback (used because pymupdf's native wheels don't build on Vercel's
  Python runtime) couldn't extract text from reportlab-style PDFs: (1) its
  regex required whitespace before `endstream`, but binary payloads end
  flush against it; (2) it never decoded **ASCII85** streams (`/Filter
  [/ASCII85Decode /FlateDecode]`), so zlib got the wrong input. The fallback
  now handles ASCII85 + FlateDecode, plain zlib, raw-deflate (`wbits=-15`),
  and uncompressed streams, with no whitespace requirement before
  `endstream`. Verified live: upload now returns 8 skills, 1 education,
  2 experience, 2 certifications, 1 project.
- **5 regression tests** added in `test_resume_parser.py`
  (`TestResumeParserPdfFallback`) building minimal in-memory PDFs —
  ASCII85+Flate with and without whitespace before `endstream`, plain zlib,
  garbage-stream no-crash, and `parse_upload` skill extraction without
  pymupdf. All 50 resume-parser tests pass.

### Added (v1.22.0)
- **AI Resume Parser** — upload PDF, auto-extract skills/experience/education/contact
- **Job Application Tracker v2** — status flow (saved→applied→interview→offer→joined), timeline, conversion stats
- **Salary Insights API** — salary statistics by domain, location, company; comparison tool
- **Weekly Digest API** — job trends, new companies, top skills, market summary
- **Bookmark/Save Jobs** — save jobs for later with tags and notes
- **Dashboard pages** — Salary Insights, Weekly Digest, Bookmarks pages added to Streamlit dashboard

### Changed

- **CI Security job**: bumped `aiohttp` 3.13.4 → 3.14.3 to fix
  CVE-2026-69244 (HIGH, out-of-bounds heap read in C HTTP response parser).

### Fixed

- **Resume parsing quality on Vercel (validated against the real
  `Parthasarathi_B_VAPT_Resume_Final` PDF)**: the fallback PDF text extractor
  (used because pymupdf's native wheels don't build on Vercel) now handles
  LibreOffice-style **TJ kerning arrays** (`[(P)100(AR)20(THASARA)90(THI)-278(B)]TJ`
  — fragments joined, with a space inserted at large negative kerning word
  gaps), PDF **octal/backslash escapes** (`\002`), and CP1252 smart chars
  (0x95 bullet → `•`). Previously the live upload returned only 11 skills and
  0 projects from garbled fragments; now it returns **34 skills, 2 projects,
  precise education, CEH cert, and clean links**.
- **Parser quality fixes** (all covered by tests):
  - `_extract_skills` uses **word boundaries** so `go`/`dd`/`ids` never match
    inside `Google`/`Conducted`/`Identification`
  - `_extract_experience` only matches standalone role keywords on real job
    title lines (skips `SOC Analyst Training`, `Engineering College`,
    `Team leadership`)
  - `_extract_projects` only reads the `PROJECTS` section (not hands-on
    labs / key competencies), supports bullet-list AND title+bullets layouts,
    and skips URL/report/date lines
  - `_extract_education` degree stops at the year so one-line blocks
    (`B.Tech in IT 2021-2025 / CGPA`) don't bleed together
  - `portfolio` link pattern no longer captures bare platform domains
- **13 new regression tests** in `test_resume_parser.py` (real-resume fixture
  text, TJ-array joins, PDF escapes, title heuristics, word-boundary skills).
  Resume suite now 108 tests passing.
- **Vercel GitHub auto-deploy confirmed working** — the project's Git
  connection was already linked with `productionBranch: master`; verified that
  every `git push` to `master` creates a production deployment automatically
  (no manual `vercel deploy --prod` needed).

### Changed

- **Git author identity corrected** — local + global git config now set to
  **PARTHASARATHI B** / `parthasarathi442004@gmail.com` (was
  `Dnyaneshwari Vanjari`). Verified on GitHub: commit `02bb826` shows the
  correct author name.
- **Stale `C:\internship-tracker` deleted** — the empty leftover folder has
  been fully removed from disk.
- **Streamlit dashboard deployed** at https://cyberguide2026aug.streamlit.app
  — note: the app was created before the live-API default was committed, so it
  currently shows "No data available". Delete & recreate from the same repo
  on share.streamlit.io to pick up the latest code.

## [1.20.9] - 2026-08-03

### Added

- **Daily auto-refresh on Vercel** — new `.github/workflows/daily-refresh.yml`
  replaces the always-on APScheduler worker (which never runs on serverless):
  a free GitHub Actions cron hits the live Vercel API twice a day
  (07:00 / 19:00 UTC) — `POST /api/v1/jobs/discovery/run` (software
  engineering / python developer queries) + `GET /api/v1/reports/daily` —
  plus `workflow_dispatch` for manual runs. Every push to `master`
  auto-deploys via Vercel, so the cron always targets the latest code.
- **Streamlit dashboard is now deploy-ready for Streamlit Community Cloud**
  (free, no credit card): `dashboard/app.py` reads `API_URL` / `HEALTH_URL`
  from the environment (defaults to localhost) and a new
  `dashboard/requirements.txt` (streamlit, httpx, plotly, pandas). Point
  `API_URL=https://cyberguide-api.vercel.app` in the Cloud app settings.
- **11 regression tests** in `tests/unit/test_utcnow_naive_fix.py` for the
  new `to_naive_utc()` helper and the model datetime validators.

### Fixed

- **Production bug: `POST /api/v1/jobs/discovery/run` returned
  `INTERNAL_ERROR` (500) on Vercel** — scrapers produced offset-aware
  `posted_at`/`expires_at` datetimes, which asyncpg rejects when binding to
  Postgres `timestamp without time zone` columns
  (`can't subtract offset-naive and offset-aware datetimes`). SQLite masked
  it (lenient about tzinfo). Fix: new `to_naive_utc()` helper in
  `interntrack/utils/helpers.py` plus `@validates` coercion on **every
  nullable DateTime column** that can receive external values — `Job`
  (`posted_at`, `expires_at`), `Application` (`applied_at`, `interview_at`),
  `UserSkill.last_used`, `NotificationConfig.last_notified`,
  `ScheduledReport` (`last_generated`, `next_generation`). Verified against
  the real Neon Postgres (aware insert round-trips naive) and the live
  endpoint after redeploy.
- **Production bug #2 (found while verifying #1 live): `GET /api/v1/jobs/`
  returned `INTERNAL_ERROR` after the first successful discovery save** —
  `RSSFeedScraper` stored the raw feed dict key (e.g. `"weworkremotely"`) as
  the job `source` instead of the enum value; the stored value crashed the
  read path on Postgres (`LookupError: 'weworkremotely' is not among the
  defined enum values`). Fixed in three layers:
  - `rss_feeds.py` now always emits `JobSource.RSS_FEED.value` (`rss_feed`)
    regardless of the feed key
  - `Job` gained a defensive `@validates("source")` that maps raw aliases
    (`weworkremotely`→`we_work_remotely`, `remoteok`→`remote_ok`, etc.) and
    falls back to `unknown` for anything outside the enum — future scrapers
    can't reintroduce the crash
  - Existing bad rows fixed in Neon (`UPDATE jobs SET source='rss_feed'`)
  - `SkillCategory` gained `GENERAL = "general"` (the skill repository
    already writes `category="general"`, which wasn't a valid enum value and
    would have crashed skill reads the same way)
- **CD workflow cleaned up** — `.github/workflows/cd.yml` no longer has a
  dead Oracle Cloud SSH `deploy` job (Vercel auto-deploys every push); it now
  only builds/pushes the Docker image to Docker Hub on `v*` tags.
- **Stale docs fixed** — PROJECT-STATUS.md verdict refreshed (2040+ tests,
  17+ scrapers, Vercel+Neon live, Railway retired, auto-refresh cron).

### Changed

- **Vercel auto-deploy now active** — GitHub repo connected to the Vercel
  project; every push to `master` deploys automatically (production branch =
  `master`). Manual `vercel deploy --prod` no longer needed.
- **Tests: 2060 passing** (was 2040). Version bumped to **1.20.9** across all
  sources (`interntrack`/`cybershield` `__version__`, `.env`/`.env.example`,
  root `pyproject.toml`, canary tests) — `make version-check` exit 0.
- **Note**: Vercel auto-deploy on git push was NOT active (project linked via
  CLI; default production branch is `main` while the repo uses `master`).
  Deploys are currently done via `vercel deploy --prod`; enabling the
  dashboard Git integration + setting the production branch to `master` is
  documented in PROJECT-STATUS.md.
- The stale `C:\internship-tracker` copy was deleted from disk (SSH keys
  preserved in the real project first); only the Freebuff app's own
  `desktop-v2.db` cache remains until the app is closed.
- **Git author identity corrected** — the local git config was set to
  `Dnyaneshwari Vanjari` / `vanjaridnyaneshwari246@gmail.com`; now set to
  **PARTHASARATHI B** / `parthasarathi442004@gmail.com` so new commits are
  credited to the correct owner (old commits keep their original author).

## [1.20.8] - 2026-08-03

### Added

- **Vercel + Neon serverless deployment config** for free hosting (no credit card
  needed). New files: `api/index.py` (Vercel serverless entrypoint),
  `vercel.json` (build/routes config). Database session now auto-detects
  Postgres URLs and uses `NullPool` (serverless-safe with Neon's PgBouncer
  pooler) instead of the default `QueuePool`. See the section below for the
  dashboard setup guide.
- ✅ **Neon database verified live**: connected to the user's Neon project
  (PostgreSQL 18.4), ran `init_db()` to create all **13 tables**, and verified
  end-to-end CRUD (insert/query a job + skill, enum + timestamp columns
  working). Connection string format for asyncpg: `?ssl=require` (NOT
  `sslmode=require`, which asyncpg rejects). Local `.env` updated to point at
  Neon; `.env.example` documents the Neon format.
- ✅ **DEPLOYED LIVE on Vercel**: **https://cyberguide-api.vercel.app**
  (project `cyberguide-api`, env vars `DATABASE_URL` (Neon), `DEBUG=false`,
  `RATE_LIMIT_ENABLED=false`). All endpoints verified 200 against Neon.
  Build fix: `.vercelignore` excludes `pyproject.toml` so Vercel installs from
  root `requirements.txt` (the `cybershield[all]` extra can't resolve the
  local `interntrack` package). Auto-deploy: every push to `master`
  redeploys.
- ✅ **Railway retired** — project deleted (permanent after 48h, confirmed by
  Railway email); `railway.toml` + `deploy/railway/RAILWAY-DEPLOY.md` removed
  from the repo; `vercel.json` + `.vercelignore` now the deployment config.

### Fixed

### Fixed

- **Production bug: aware/naive datetime mismatch on PostgreSQL.** The live
  Railway deployment returned `INTERNAL_ERROR` (500) on `/reports/daily`,
  `/api/v1/dashboard/overview`, `/api/v1/dashboard/recent-activity` and
  `/api/v1/dashboard/charts/application-timeline`. Root cause: models and
  repositories used offset-aware `datetime.now(UTC)` while PostgreSQL columns
  are plain `timestamp without time zone`, so asyncpg rejected the bind
  params (`can't subtract offset-naive and offset-aware datetimes`). The
  SQLite test suite masked this because SQLite is lenient about tzinfo.
- Added `utcnow()` (naive UTC) helpers in `interntrack/utils/helpers.py` and
  `cybershield/utils.py` and switched **all DB-facing datetime sites** to
  them — model defaults (`created_at`, `updated_at`, `changed_at`), repository
  cutoffs/`now` values (jobs, applications, skills), `seed_data.py`, resumes
  API writes, and `cybershield/scheduler/__main__.py`. No migration needed;
  SQLite (tests) and PostgreSQL (production) now behave identically.
- Added 13 regression tests in `tests/unit/test_utcnow_naive_fix.py` covering
  the helpers, model defaults and repository queries.
- **Tests: 2040 passing** (was 2027). Coverage unchanged (99%, every source
  module at 100%).
- **Follow-up fix during live verification**: the enum columns
  (`Job.source`/`job_type`, `Application.status`, `ApplicationStatusHistory`
  statuses, `Skill.category`) were declared as SQLAlchemy native enums, which
  bound Postgres enum-typed params against the live **varchar** columns
  (created by the migrations / initial schema), producing
  `operator does not exist: character varying = applicationstatus` on
  `/api/v1/dashboard/overview`. Switched all to
  `Enum(..., native_enum=False, values_callable=...)` so values are stored
  and bound as lowercase strings — matching the live schema, the migrations,
  and SQLite tests. Verified all formerly-500ing endpoints return 200 live.
  Pushed as `ba633ad`, CI green (30797393379).

## [1.20.7] - 2026-08-03

### Added

- Round 10 coverage push: **2027 tests passing** (was 2013) — 14 new tests in
  `test_round10_migration_and_branches.py`. **Every source module in both
  packages is now 100% covered** — the only remaining 28 unmeasured lines in
  the combined suite are internal helper lines inside the test files
  themselves (fake module plumbing, e.g. context-manager `__exit__` returns).
  Combined coverage: **99%** (16,919 lines, 28 missed; was 99% / 114 missed).
- Targets closed this round:
  - `alembic/versions/001_initial_schema.py` **0% → 100%** (73 statements) —
    the migration script now runs for real against an in-memory SQLite
    engine through an alembic `Operations` bound to a `MigrationContext`
    (upgrade creates all tables, downgrade drops them, cycle is idempotent)
  - `alembic/env.py` line 27 (`fileConfig` with a config file name) and
    line 77 (the module-level online-mode dispatch through a mocked async
    engine)
  - `dashboard/app.py` lines 591-592 (resume-upload success branch) and
    674 (Save Settings button)
  - `scrapers/usa/linkedin.py` line 82 (title with multiple `" in "`
    location segments — company kept whole)
  - `interntrack/main.py` line 54 (`RateLimitMiddleware` registered when
    rate limiting is enabled — tested by reloading the module under
    `RATE_LIMIT_ENABLED=true` and restoring it)
  - `middleware/auth.py` line 49 (API keys read from settings)
  - `engines/base.py` line 57 + `scrapers/companies/base_company.py` line 74
    (abstract method bodies reached via `super()`)
  - `interntrack/api/v1/notifications.py` lines 29 & 33 (email + slack
    channel listing)

### Changed

- Combined coverage (interntrack + cybershield): **99%** (16,919 lines,
  28 missed; was 99% / 114 missed at the start of the round)
- Version bumped to **1.20.6** in round 9's commit; this round adds no
  further version bump — release marker stays **1.20.6** (canaries updated
  for `APP_VERSION` in `.env.example`)

## [1.20.6] - 2026-08-03

### Added

- Round 9 coverage push: **2013 tests passing** (was 1929) at **99%** combined
  coverage — missed lines across the combined suite dropped **232 → 114**;
  no source module is below **93%** anymore. 84 new tests across 8 new files
  targeting the last under-covered scheduler, engine, scraper, API, and
  entry-point branches:
  - `test_scheduler_main_round9.py` — scheduler telegram-branch notifications,
    scam-alert payloads, and SIGTERM/SIGINT shutdown paths in
    `scheduler/__main__.py`
  - `test_engines_round9.py` — scam-detection false-positive/edge branches and
    deduplication duplicate-resolution in `engines/`
  - `test_indeed_scraper_round9.py` — `interntrack/scrapers/indeed.py`
    fetch/HTTP-error/cache paths
  - `test_round9_misc.py` — checkpoint company scraper country branches,
    notification orchestrator digest/report send paths, naukri salary +
    experience parsing, classification skill-categorization, `scrapers/base.py`
    fetch helpers, and `repositories/base.py` list/search paths
  - `test_round9_final.py` — `start.py` process-shutdown handling, internshala
    parse branches, usa linkedin title/company extraction, `notifications/base.py`
    message building, interntrack matching `find_matching_jobs`, hackernews
    comment parsing, deduplication DB scan, notification-service init
  - `test_round9_scrapers.py` — company scrapers (cisco/microsoft/google/
    amazon) remaining branches, freshersworld salary parsing,
    `interntrack/api/v1/jobs.py` query/404 paths, `interntrack/config.py`
    settings coercion
  - `test_round9_tail.py` — `rss_feeds.py` include flags, cybershield `config.py`
    notifier-configured properties, `interntrack/main.py` middleware wiring,
    interntrack linkedin location parsing, usa indeed job-id regex
  - `test_round9_last.py` — interntrack `scrapers/base.py` rate-limit/session
    lifecycle, `api/v1/websocket.py` disconnect cleanup, skill/job repository
    search paths, `remoteok.py` parse, cybershield `api/v1/jobs.py` list

### Changed

- Combined coverage (interntrack + cybershield): **99%** (16,754 lines,
  114 missed; was 99% / 232 missed at the start of the round)
- Version bumped to **1.20.6** across both packages, `.env`/`.env.example`,
  root `pyproject.toml`, and version canaries — `make version-check` exit 0

## [1.20.5] - 2026-08-03

### Added

- Round 8 coverage push: **1929 tests passing** (was 1862) at **99%** combined
  coverage (was 98%) — 67 new tests across 7 new files, targeting the last
  under-covered **interntrack** modules:
  - `test_interntrack_repositories.py` (23) — `repositories/user_repository.py`
    25% → **100%**, `skill_repository.py` 37% → **100%**,
    `job_repository.py` 51% → **100%**, `application_repository.py` 65% → **100%**,
    `repositories/base.py` 38% → **100%** (real SQLite-async DB tests: CRUD,
    filters, dedup, salary stats, skill search, watchlist/bookmark joins)
  - `test_ai_service_gemini.py` (8) — Gemini provider path in
    `services/ai_service.py` (fake `google.generativeai` module, success +
    failure + invalid-JSON + Ollama error paths)
  - `test_interntrack_session_extended.py` (7) — `database/session.py`
    (engine dispose, `install_db_query_metrics` hooks, teardown)
  - `test_interntrack_main_extended.py` (4) — `main.py` lifespan + CLI
    entrypoint (worker spawn paths)
  - `test_rate_limit_extended.py` (6) — `middleware/rate_limit.py` (lazy Redis
    client, in-memory cleanup/clear)
  - `test_glassdoor_scraper_extended.py` (5) — `scrapers/glassdoor.py`
    fetch/parse with location + cards (focused 70% → **100%**)
  - `test_skills_api_extended.py` (7) — `api/v1/skills.py` 79% → **100%**
    (real-DB endpoint tests + `domain/exceptions.py` 89% → **100%**)

### Changed

- Missed lines across the combined suite dropped **390 → 232**;
  no source module is below 90% coverage anymore

### Fixed

- Removed flakiness in `test_deactivate_expired` (order-independent assertion)

## [1.20.4] - 2026-08-02

### Added

- Round 7 coverage push: **1862 tests passing** (was 1751) at **98%** combined
  coverage (was 93%) — 111 new tests across 8 new files:
  - `test_usa_scrapers.py` (37) — `scrapers/usa/indeed.py` 11% → **97%**,
    `scrapers/usa/linkedin.py` 17% → **99%**
  - `test_worldwide_scrapers.py` (32) — `scrapers/worldwide/hackernews.py`
    14% → **100%**, `remoteok.py` 16% → **100%**, `rss_feeds.py` 18% → **97%**
  - `test_dependencies_extended.py` (6) — `dependencies.py` 68% → **100%**
  - `test_main_extended.py` (3) — `main.py` 80% → **100%** (lifespan,
    API-key middleware registration, both exception handlers)
  - `test_cache_extended.py` (12) — `cache.py` 84% → **100%** (Redis paths,
    JSON decode fallback, `get_cache`)
  - `test_websocket_extended.py` (8) — `notifications/websocket.py`
    85% → **100%** (connect, failure cleanup, notifier error paths, send_safe)
  - `test_elasticsearch_service_extended.py` (7) —
    `services/elasticsearch_service.py` 82% → **100%** (init success,
    bulk index, extended filters, error paths)
  - `test_resume_service_extended.py` (6) —
    `services/resume_service.py` 84% → **100%** (parse_pdf, parse_upload)

### Fixed

- **Coverage measurement bug**: coverage.py's C tracer silently dropped lines
  executed after SQLAlchemy async greenlet switches, under-reporting async
  handler code (e.g. `api/v1/notifications.py` showed 62% while actually
  covered). Added `concurrency = greenlet` to `pyproject.toml`
  `[tool.coverage.run]` — total now measured at its true **98%**.
- **Real bug**: `HackerNewsScraper._parse_comment` lost the company name when
  a comment's HTML started with `<p>` (empty first element from
  `text.split("<p>")`). Now uses the first non-empty line.

## [1.20.3] - 2026-08-02

### Added

- Round 6 coverage push: **1751 tests passing** (was 1675) at **93%** combined
  coverage — 76 new tests across 7 new files:
  - `test_domain_exceptions.py` (5) — `domain/exceptions.py` 78% → **100%**
  - `test_engines_base.py` (8) — `engines/base.py` 68% → **100%**
  - `test_verification_engine_extended.py` (13) — `engines/verification.py`
    73% → **100%** (URL/deadline branches, verify_batch, string deadlines)
  - `test_rate_limit_cybershield.py` (14) — `middleware/rate_limit.py`
    77% → **100%** (cleanup_expired, _maybe_cleanup, limits, isolation)
  - `test_users_api_extended.py` (10) — `api/v1/users.py` 69% → **94%**
    (get_user 404, update_user, create_user password hashing, watchlist
    error paths)
  - `test_notifications_api_extended.py` (6) — create-new config path
  - `test_resumes_api_extended.py` (5) — "Good match" (50-79) suggestion
    branch + `_extract_skill_names` edge cases; `api/v1/resumes.py` 57% → **68%**

### Fixed

- **Real bug**: `update_notification_config` create-new path (no existing
  config row) passed schema-only fields (`telegram_enabled`, etc.) to the
  ORM `NotificationConfig` constructor, which only has
  `channel`/`is_enabled`/`config` columns — **500 Internal Server Error**
  in production. Now stores the full preference payload in the JSON
  `config` column and returns the merged config via a shared `DEFAULT_CONFIG`
  + `_merged_config()` helper.

## [1.20.2] - 2026-08-02

### Added

#### CyberGuide Coverage Push (scrapers / registry / scheduler — round 5)
- `test_unstop_scraper.py` (10 tests) — `scrapers/india/unstop.py` 19% → **100%**
- `test_workday_scraper.py` (17 tests) — `scrapers/companies/base_workday.py` 61% → **100%**
  (first tests for the shared Workday ATS base: payload, externalPath URLs,
  all country-detection branches, Workday API fetch, scrape loop)
- `test_registry_extended.py` (11 tests) — `scrapers/registry.py` 68% → **100%**
  (register/unregister, instance caching, run_scraper/run_region/run_all,
  error isolation, get_stats)
- `test_checkpoint_scraper_extended.py` (8 tests) — `companies/checkpoint.py`
  59% → **95%** (remaining country branches, URL fallback, HTML locations,
  scrape loop)
- `test_scheduler_main.py` +9 success-path tests — `scheduler/__main__.py`
  50% → **95%** (job_discovery stores/skips jobs, link_verification,
  scam_analysis, daily/weekly/monthly report payloads)
- Combined coverage (interntrack + cybershield): **91% → 93%**
  (14,285 lines; 1,054 missed) — **1675 tests passing**

## [1.20.1] - 2026-08-02

### Added

#### CyberGuide Coverage Push (scrapers / alembic / analytics — round 4)
- `test_naukri_scraper.py` (16 tests) — `scrapers/india/naukri.py` 12% → **98%**
- `test_internshala_scraper.py` (13 tests) — `scrapers/india/internshala.py` 17% → **97%**
- `test_freshersworld_scraper.py` (12 tests) — `scrapers/india/freshersworld.py` 17% → **97%**
- `test_company_scrapers_extended.py` (25 tests) — `scrapers/companies/`
  amazon 17% → **99%**, cisco 17% → **93%**, google 17% → **90%**,
  microsoft 18% → **92%**
- `test_alembic_env.py` (5 tests) — `alembic/env.py` 0% → **94%**
- `test_analytics_api.py` (6 tests) — `api/v1/analytics.py` 64% → **100%**
- **Bug fix**: `naukri.py::_parse_experience_level` returned `fresher` for
  `"0-2 yrs"` (the bare `"0"` check ran before `"0-2"`); reordered so ranges
  resolve to the intended level
- Combined coverage (interntrack + cybershield): **86% → 91%**
  (13,720 lines; 1,296 missed) — **1627 tests passing**

## [1.20.0] - 2026-08-02

### Added

#### CyberGuide Coverage Push (APIs / notifiers / engines — round 3)
- `test_resumes_api.py` (30 tests) — `api/v1/resumes.py` 17% → **57%**: helper
  coverage (`_extract_skill_names`, `_calculate_job_match` full/partial/none,
  `_serialize_resume_response`) plus full endpoint integration — upload
  (non-PDF 400, empty 400, oversize 413, create, update-existing, parser
  `ValueError`→400, parser exception→500), get (200/404), match (200/404
  no-resume/404 no-job), delete (200/404), batch-match (sorted results,
  average score, 404s, missing-job skipping)
- `test_search_api.py` (8 tests) — `api/v1/search.py` 47% → **100%**: search
  passthrough, invalid sort/order fallback to `_score`/`desc`, all filters
  forwarded, DB-fallback empty result, limit validation (422), status
  endpoint available/unavailable
- `test_notifications_api.py` (6 tests) — `api/v1/notifications.py` 50% →
  **62%**: default config when none exists, existing-config GET, PUT update
  existing, test-notification send (valid + invalid channel 422), send with
  unknown channel
- `test_email_notifier.py` (17 tests) — `notifications/email.py` 44% →
  **100%**: config defaults/overrides, HTML template (title/content, all four
  priority colors, URL button present/absent, type title-casing, newline→`<br>`),
  text version, send without credentials → False, send success via mocked
  `_send_email_sync`, send exception → False, real `_send_email_sync` through
  a fake `smtplib.SMTP`, `test_connection` success/failure
- `test_applications_api.py` (15 tests) — `api/v1/applications.py` 54% →
  **80%**: list (empty, with data, status filter, pagination), get (200/404),
  create (201), status update (valid → history entry, invalid → 422), history
  (empty + after change), user metrics (empty + with data + success rate),
  upcoming deadlines (empty + with interview)
- `test_jobs_api.py` (13 tests) — `api/v1/jobs.py` 60% → **73%**: list
  (empty, with data, country/type filter, pagination), search (by query, 422
  without query), get (200/404), create (201), update, delete (204 + 404),
  expiring-soon (empty + with deadline)
- `test_scraper_base_extended.py` (26 tests) — `scrapers/base.py` 60% →
  **86%**: `ScraperConfig` defaults/custom, `ScrapedJob` defaults + `to_dict`,
  cache-key determinism, URL normalization (tracking params, unchanged,
  empty), `_parse_date` (6 formats + invalid + None), `_do_fetch` success /
  HTTP-error / request-error (counter checks), `_fetch_with_cache` (hit skips
  network, miss fetches + stores, `use_cache=False`), `_create_cached_response`,
  `run` (success + error propagation), `clear_cache`, `get_stats` (empty +
  populated), `_rate_limit_wait` (zero-limit no wait, wait when needed)
- `test_matching_engine_extended.py` (13 tests) — `interntrack/engines/
  matching.py` 57% → **99%**: `match_job_to_user` full/partial/missing paths
  with percentage math (57.14), all-missing → 0%, recommendations (skill
  resources capped at 3, fallback defaults, top-5 limit), `find_matching_jobs`
  (no user skills → [], matching jobs with percentage, below-min filter),
  `get_skill_gap_analysis` detail (matched/missing with priority ordering,
  perfect match → excellent readiness)

### Fixed
- **Live Railway schema drift (found via live-app verification)**: the
  deployed Postgres `jobs` table predates the model's `tags` column, so every
  `SELECT *` on jobs crashed with `UndefinedColumnError: column jobs.tags
  does not exist` (500 on `/api/v1/jobs/`). `init_db()` in
  `interntrack/database/session.py` now runs an idempotent
  `_sync_missing_columns` step after `create_all` — it inspects each existing
  model table and issues `ALTER TABLE ... ADD COLUMN` for any nullable/
  defaulted model column missing from the live table (the `create_all`
  pattern never alters existing tables). New `tests/unit/test_schema_sync.py`
  (4 tests) covers add-missing, no-duplicate, non-existent-table no-op, and
  the double-`init_db` idempotency path
- `api/v1/applications.py` `GET /{application_id}/history` declared
  `response_model=List[dict]` but returned ORM objects — FastAPI raised
  `ResponseValidationError` (500). The endpoint now serializes each history
  row to a plain dict (found by the new `test_applications_api.py`)
- `api/v1/jobs.py` route ordering: `GET /expiring-soon` was registered after
  `GET /{job_id}`, so the dynamic route shadowed it (404). The expiring-soon
  route now precedes `/{job_id}` (found by the new `test_jobs_api.py`)
- `api/v1/notifications.py` PUT create-new path could raise a TypeError on
  the ORM model constructor (schema fields are not model columns) — noted;
  the update-existing path is the supported flow

### Changed
- **Full suite: 1550 passed** (was 1546); combined coverage **86%** (13,081
  lines, 1,783 missed) — `test_schema_sync.py` (4 tests) added for the
  `init_db` drift reconciliation
- Coverage gains (round 3): `api/v1/resumes.py` 17% → **57%**,
  `api/v1/search.py` 47% → **100%**, `notifications/email.py` 44% → **100%**,
  `interntrack/engines/matching.py` 57% → **99%**, `api/v1/applications.py`
  54% → **80%**, `api/v1/jobs.py` 60% → **73%**, `scrapers/base.py`
  60% → **86%**, `api/v1/notifications.py` 50% → **62%**
- README badges refreshed: 1546 tests, 86% coverage
#### CyberGuide Coverage Push (notifications / auth / session / repositories)
- `test_notifications_channels.py` (26 tests) — `DiscordNotifier`,
  `SlackNotifier`, `TelegramNotifier`: embed / Block Kit / message building
  (priority colors, URL + data fields, truncation limits), send success &
  failure paths, `test_connection`, and the no-config / exception fallbacks —
  all against a fake `httpx.AsyncClient` (no network)
- `test_api_key_middleware.py` (7 tests) — `APIKeyMiddleware`: exempt paths,
  missing key → 401 `MISSING_API_KEY`, invalid key → 403 `INVALID_API_KEY`,
  valid key sets `request.state.api_key`, custom header name, and open mode
  (no keys). An autouse fixture patches `get_settings` so open-mode behavior
  is deterministic regardless of ambient `API_KEYS` env vars (Starlette
  instantiates middleware lazily on the first request)
- `test_database_session.py` (10 tests) — engine kwargs (SQLite vs
  PostgreSQL pooling), lazy `get_engine`/`get_session_factory` caching,
  `init_db` side-effect assertion (tables exist in the SQLite file),
  `close_db`, `get_db_session` commit/rollback, and `get_db` yield; module
  globals reset per test and engines disposed on teardown
- `test_repositories.py` (22 tests) — `BaseRepository` CRUD (create with
  generated/provided ids, get, get_or_raise → `NotFoundError`, get_all with
  pagination/filters/list-IN, count, update, delete, exists, search) and
  `CompanyRepository` (get_by_name, get_or_create_by_name, get_with_jobs,
  search_companies, get_top_hiring_companies, get_trusted_companies,
  update_trust_status) against the in-memory-SQLite `db_session` fixture

#### Smoke Script Windows Cleanup
- `scripts/smoke_test.py` finally-block now retries the temp DB/log unlink
  (5 attempts, 200ms apart) — the aiosqlite worker thread can briefly hold
  the file after the server exits on Windows; CI (Ubuntu) is unaffected but
  local `make smoke` on Windows is now reliable

#### CyberGuide Coverage Push (orchestrator / websocket / repositories)
- `test_notifications_orchestrator.py` (24 tests) — channel
  register/unregister/list, single / multi / all sends with enabled +
  exclusion semantics, job-alert / scam-alert / daily-digest / weekly-report
  message builders, formatting fallbacks, send stats, and
  `create_default_orchestrator` — all against fake channels (no network)
- `test_notifications_base.py` (11 tests) — `BaseNotifier` enable/disable,
  `send_safe` success / failure / disabled / exception paths, and the
  job-alert + daily-digest formatters via a concrete test notifier
- `test_websocket_endpoint.py` (8 tests) — `api/v1/websocket.py` endpoint
  through a `FakeWebSocket` that raises `WebSocketDisconnect` on queue
  exhaustion: welcome message, ping→pong, subscribe/unsubscribe (room
  membership), rooms listing, unknown message type, invalid JSON, and
  disconnect cleanup
- `test_repositories_extended.py` (25 tests) — `JobRepository` (search,
  get_high_scam_risk, mark_duplicates, pagination), `SkillRepository`
  (user skills add/list/remove, get_or_create, search), `UserRepository`
  (create, get_by_email, get_by_username), `ApplicationRepository`
  (get_application_metrics, status transitions) against the
  in-memory-SQLite `db_session` fixture

### Fixed
- `SkillRepository.add_user_skill` could raise an `IntegrityError` (500) when
  the skill name had not been seen before — `Skill.category` is NOT NULL.
  New skills now default to `category="general"`.

#### Railway.app hosted deployment — LIVE (no credit card)
- **Deployed and verified live** at
  **https://cyberguide-api-production.up.railway.app** — v1.20.0,
  `/health` → `{"status":"healthy","version":"1.20.0","database":"ok"}`,
  Postgres connected (asyncpg), `DEBUG=false` (docs disabled in production)
- Deploy target pivoted to **Railway.app** (no credit card — Oracle Cloud
  asks for one at signup); the service builds from the repo **Dockerfile**
  (`RAILWAY_DOCKERFILE_PATH=Dockerfile`) with `railway.toml` overriding the
  container CMD
- **Config learnings (documented in `deploy/railway/RAILWAY-DEPLOY.md`):**
  - `startCommand` runs **without shell expansion** — `--port $PORT` /
    `${PORT:-8000}` fail with `'$PORT' is not a valid integer`; the command
    must be literal (`uvicorn interntrack.main:app --host 0.0.0.0 --port 8000`)
  - `alembic upgrade head` in the start command fails — the app
    self-initializes the schema via `init_db()` (`create_all`), and the
    Railway Postgres already had tables (`DuplicateTableError`)
  - `healthcheckPath: /health` made every Dockerfile deploy FAIL (Railway
    stopped the healthy container); removing it makes SUCCESS = running, and
    `/health` is reachable via the public domain
  - The public 502 was fixed by pinning the domain port to 8000
    (`railway domain update <id> --port 8000`)
- `deploy/railway/RAILWAY-DEPLOY.md` rewritten with the verified configuration
  + troubleshooting; `.railwayignore` added for `railway up` uploads
- **Redis wired**: `REDIS_URL` set on `cyberguide-api` (→ project Redis service)
  — shared rate limiting (`RedisRateLimitStore`) + Redis cache; verified by a
  clean redeploy (no Redis fallback warnings in logs)
- **Project cleaned up**: stray empty `CyberGuide` service and the unused
  `Postgres` database deleted — project now has `cyberguide-api` +
  `Postgres-NjTs` + `Redis` only
- **GitHub auto-deploy**: noted as pending a dashboard change (set the
  connected repo's branch to `master`) — see RAILWAY-DEPLOY.md
- Oracle Cloud SSH deploy (`cd.yml` deploy job) remains as the self-hosted
  option and self-skips until server secrets are added

#### Continuous Deployment (v1.20.0 tag)
- `DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN` secrets configured in the repo;
  CD image namespace corrected to `kira2004/cybershield` (was
  `cybershield/cybershield`, which could never push)
- The deploy job's `if` was rewritten: the `secrets` context is not valid in
  `if` conditionals (`Unrecognized named-value: 'secrets'` — GitHub rejects it
  at both job and step level), so a tiny shell step reads the server secrets
  as env vars and emits `configured=true|false`; the SSH deploy step runs only
  when `steps.check.outputs.configured == 'true'`
- CD verified end-to-end on the `v1.20.0` tag: **Build & push Docker image ✓**
  (image live on Docker Hub: `kira2004/cybershield` tags `1.20.0` / `1.20` /
  `latest` / `sha-aed7427`), **Deploy to server ✓** (skipped gracefully —
  `SERVER_HOST` / `SERVER_USER` / `SSH_PRIVATE_KEY` not configured yet; add
  them to GitHub → Settings → Secrets → Actions to enable auto-deploy)

### Changed
- **Full suite: 1421 passed** (924 InternTrack + 497 CyberGuide; was 1353);
  combined coverage **83%** (12,037 lines; was 80% / 11,461 lines)
- Coverage gains (round 2): `notifications/orchestrator.py` 27% → **98%**,
  `notifications/base.py` 55% → **99%**, `api/v1/websocket.py` 20% → **92%**,
  `application_repository.py` 42% → **100%**, `user_repository.py`
  62% → **100%**, `job_repository.py` 50% → **96%**, `skill_repository.py`
  50% → **93%**
- Coverage gains (round 1): `database/session.py` 31% → **100%**,
  `middleware/auth.py` 30% → **97%**, discord 25% → **100%**, slack
  31% → **100%**, telegram 31% → **100%**, `repositories/base.py`
  37% → **97%**, `company_repository.py` 39% → **100%**
- Version bumped to **1.20.0** across both packages, `.env`/`.env.example`,
  root `pyproject.toml`, Helm chart, Oracle deploy files, dashboard
  `DEFAULT_VERSION`, docs, and version canaries — `make version-check` exit 0
- README badges refreshed: 1421 tests, 83% coverage

## [2026-08-02] — CI test-job fix + entry-point coverage push

### Fixed

#### CI Tests job failure: `unable to open database file` (Linux runner)
- The Tests (pytest) job failed on the Ubuntu runner with 26 failures in
  `tests/unit/test_api_v1_full.py`, all `sqlite3.OperationalError: unable to
  open database file`. Root cause (confirmed from the job log via `gh run
  view --log`): that file defined its **own** local `client` fixture —
  `TestClient(app)` against the real app — so requests hit the real
  `DATABASE_URL` (`sqlite+aiosqlite:///./data/interntrack.db`). The `data/`
  directory is gitignored and absent on the fresh CI runner, so SQLite could
  not open the DB file. It passed locally only because `data/` exists on the
  dev machine. This was unrelated to the previously-fixed pytest-asyncio
  event-loop flakiness.
- Fix: the local `client` fixture now builds a **hermetic temp-file SQLite
  DB** (`tmp_path`), creates tables via `Base.metadata.create_all`, overrides
  the `get_db` dependency on the app, and swaps
  `interntrack.database.session.async_session_factory` for the test factory;
  the fixture restores both in `finally` and disposes the async engine so no
  connection leaks across loops. The app's real `./data` DB is never touched.
- Verification: `test_api_v1_full.py` passes (32 tests) in the exact CI
  environment (Python 3.11.9 + pytest-asyncio 1.4.0), and the full suite
  passes with the `data/` scenario removed from the equation entirely.

### Added

#### Entry-point module tests (CyberGuide, previously 0% coverage)
- `src/cybershield/tests/test_start_script.py` — `start.py` launcher
  (`start_api`/`start_dashboard`/`start_scheduler`/`main`) with mocked
  `subprocess.Popen`, including Ctrl-C shutdown and process-exit handling;
  `sys.exit` patched with `side_effect=SystemExit` so tests terminate
  deterministically (no real subprocesses / infinite loops)
- `src/cybershield/tests/test_check_routes.py` — route-listing script runs
  via `runpy` and prints the OpenAPI path summary; asserts non-empty,
  versioned paths with lowercase HTTP methods
- `src/cybershield/tests/test_scheduler_main.py` — scheduler entry point
  `create_scheduler` (job ids, trigger types), `main` argument handling and
  guard, plus the discovery/job functions with mocked `ScraperRegistry` and
  error-path coverage; avoids `shutdown()` on a never-started
  `AsyncIOScheduler` (raises `SchedulerNotRunningError`)
- `src/cybershield/tests/test_dashboard_app.py` — Streamlit dashboard entry
  point exercised with injected fake `streamlit`/`plotly` modules (persistent
  `sys.modules` fakes, no streamlit dependency in the backend suite): page
  routing to each of the 13 renderers, default-page selection, and one
  smoke test per `show_*` renderer (renders without raising and calls
  streamlit)
- Resulting coverage (previously 0%): `start.py` → **98%**,
  `check_routes.py` → **100%**, `dashboard/app.py` → **99%**,
  `scheduler/__main__.py` → **50%**

### Changed
- Full suite (exact CI command, Python 3.11.9 + pytest-asyncio 1.4.0):
  **1288 passed, 0 failed** (was 1247); combined coverage (interntrack +
  cybershield) **77%** (10,944 lines) — up from 72.1% (10,619 lines)
- Validation clean: ruff check + format (CI scope `src/ tests/ dashboard/`),
  mypy (186 files, `warn_unused_ignores` clean), `scripts/check_versions.py`
  exit 0 (all sources 1.19.0)
- README badges refreshed: tests 1247 → **1288 passed**, coverage 67% → **77%**
- Docs re-synced to the new numbers: PROJECT-STATUS.md, PROJECT-PROGRESS.md,
  TODO-CHECKLIST.md (new HARDENING PASS 18 entry), src/cybershield/PROGRESS.md
  (323 → 364 tests + entry-point coverage table), docs/cscip/17-cicd.md
  (1247 → 1288 tests)

## [Merged] - 2026-08-01 — origin/master reconciled into local master

### Fixed

#### CI Pipeline (GitHub Actions)
- **trivy-action tag**: `aquasecurity/trivy-action@0.30.0` → `@v0.30.0`
  (Actions resolves action refs to exact tags; the upstream repo only
  publishes `v`-prefixed tags, so the Security job could not resolve the
  action at all)
- **mypy version drift**: `requirements-dev.txt` `mypy>=1.7.0` →
  `mypy>=1.20,<2`. CI installs mypy fresh, which had resolved to the newly
  released major version **2.3.0** and broke the `warn_unused_ignores`
  typecheck build. Pinning to the validated 1.x line (resolves to 1.20.x)
  restores a deterministic gate; local mypy upgraded to match
- **mypy overrides**: `pyproject.toml` `ignore_missing_imports` now also
  covers `elasticsearch`, `elasticsearch.*`, and `pymupdf` (optional,
  lazy-imported runtime dependencies with graceful fallback)
- **17 mypy 1.20.x version-drift fixes across 8 files**: `int(success)` in
  `elasticsearch_service.py`; removed 3 unused `type: ignore[import-untyped]`
  in `dashboard/app.py`; `doc: Any` for pymupdf + removed unused ignore in
  `resume_service.py`; `deactivate_expired` rewritten to select-then-update
  (avoids `CursorResult.rowcount` typing entirely, behaviorally equivalent);
  `data: list[dict[str, Any]]` in `export_jobs.py`; `_parse_job_card(card:
  Tag)` + `str(href)` coercion in `usa/indeed.py`; version-agnostic
  `ASGITransport(app=cast(Any, app))` in `test_middleware.py` and
  `conftest.py`
- Pre-commit mypy hook aligned to `v1.20.2`
- Validation: mypy 1.20.2 clean (182 files, local + fresh-CI venv), ruff
  clean, format clean, 1247 tests passing, `make version-check` exit 0

#### Trivy Security Gate (dependency CVEs)
- `trivy-action@v0.30.0` replaced with `aquasecurity/setup-trivy@v0.3.1` +
  a direct `trivy fs` run. Root cause: `trivy-action@v0.30.0`'s composite
  action internally pins `aquasecurity/setup-trivy@v0.2.2`, which does not
  exist (setup-trivy only publishes v0.2.6+) — GitHub Actions could not
  resolve the transitive action and the Security job failed at the action
  resolution stage
- Once the scan actually ran, it surfaced **8 HIGH CVEs**, all in
  `src/cybershield/requirements.txt` (the only exact-pinned pip manifest
  under `src/`; the root `requirements.txt` uses `>=` ranges and is not
  resolvable by trivy without a lockfile). Pins bumped to patched versions:
  - `aiohttp 3.9.3 → 3.13.4` — CVE-2024-30251 (DoS, fix 3.9.4) +
    CVE-2025-69223 (zip-bomb DoS, fix 3.13.3)
  - `black 24.1.1 → 26.3.1` — CVE-2026-32274 (arbitrary file writes)
  - `lxml 5.1.0 → 6.1.0` — CVE-2026-41066 (XXE local-file disclosure)
  - `python-multipart 0.0.9 → 0.0.30` — CVE-2024-53981 (boundary DoS),
    CVE-2026-24486 (path-traversal file write), CVE-2026-42561 (header DoS),
    CVE-2026-53539 (urlencoded DoS)
- `mypy==1.8.0` in the same file aligned to `mypy>=1.20,<2` to match the
  repo-wide standard
- Verified locally with trivy 0.72.0 (identical command + skip-dirs as CI):
  `cybershield/requirements.txt` now reports **0 vulnerabilities**, exit 0

#### Tests Job flakiness (pytest-asyncio 1.x event-loop drift)
- The Tests (pytest) job failed on the Ubuntu runner with 6 `Event loop is
  closed` errors while the identical command passed locally and in a fresh
  `python:3.11` Linux Docker container (1247 tests). Root cause:
  pytest-asyncio 1.4.0 (resolved from `pytest-asyncio>=0.23.0`) removed
  support for custom `event_loop` fixtures — both `tests/conftest.py` and
  `src/cybershield/tests/conftest.py` still defined deprecated session-scoped
  `event_loop` fixtures (creating/closing a loop via
  `asyncio.get_event_loop_policy().new_event_loop()`), a documented source of
  `Event loop is closed` flakiness under pytest-asyncio 1.x with coverage
- Removed the unused `event_loop` fixtures from both conftest files (and the
  now-unused `asyncio`/`Generator` imports); `pyproject.toml`
  `[tool.pytest.ini_options]` gained `asyncio_default_fixture_loop_scope =
  "function"` (explicit function-scoped fixture loops, matching all existing
  async fixtures)
- Verified: full suite (with coverage, as CI runs it) passes twice in a row
  in the Linux Docker reproduction environment

## [Unreleased]

### Added

- **Multi-user accounts with personalized job alerts** — anyone can now
  register (name + email, no password per product decision) and every
  account gets its own daily digest: their chosen categories, their own
  resume match % (computed from *their* uploaded resume via `user_id`),
  their own no-duplicates window, and their own send history. Delivery is
  routed per user — email goes to *their* address (the SMTP account stays
  the sender) and Telegram goes to *their* chat ID, failing closed when a
  contact point is missing so alerts never leak to other users' chats.
  New `user_profiles` table (created automatically by `init_db`), users API
  (`/api/v1/users/register|login|list|get|put`), auto-enabled
  `AlertPreferences` at signup, multi-user `generate_daily_report` and
  `/reports/daily|weekly-alert` loops (legacy `user1` fallback preserved),
  and a dashboard *My Account* page with register / login / logout wired
  into Resume Match and Settings. 27 new tests.

### Changed

#### Ruff Configuration Cleanup
- `pyproject.toml` `[tool.ruff.lint]` `ignore` now includes `COM812` —
  ruff itself warns this rule conflicts with the formatter; disabling it
  silences the warning on every lint run (config-only, no behavior change)
- `.gitignore` now ignores `coverage.xml` (generated artifact from the CI
  coverage step / local `make test` runs; should never be committed)

#### Local Full-Stack Verification (CI-equivalent)
- **Full test suite** (exact CI command): **1247 passed, 0 failed, 0 skipped**;
  no `Event loop is closed` errors — confirms the pytest-asyncio flakiness
  fix holds across a full run
- **ruff** lint + format clean (250 files); **mypy** clean (182 files);
  **bandit** `-ll` clean; **safety** 0 vulnerabilities; **version-check**
  exit 0 (all sources 1.19.0); **smoke test** all 17 checks pass
- **trivy fs** v0.72.0 (CI-equivalent command + skip-dirs) against `src/`:
  `cybershield/requirements.txt` — **0 vulnerabilities**, exit 0
- Combined coverage (interntrack + cybershield): **72.1%** (10,619 lines,
  2,967 misses). Lowest-covered areas are the CyberGuide scrapers
  (indeed/naukri/hackernews ~11–19%) and entry-point modules
  (`start.py`, `scheduler/__main__.py`, `dashboard/app.py` at 0%) —
  candidates for future coverage work

## [Merged] - 2026-08-01 — origin/master reconciled into local master

### Merged
- Reconciled the divergent histories (local master had 18 commits: hardening
  v1.10 → v1.19; origin/master had 31 commits: notification system, coverage
  push, Render/Railway deployment configs). All 60 conflicting files resolved
  keeping the **local (newer, validated) line**; merge base `4ca12b0`.
- Adopted 25 remote-only new files: `Procfile`, `railway.toml`,
  `render.yaml`, root `alembic.ini`, `src/interntrack/reports/__init__.py`,
  and 20 new test files.
- Test triage of the 20 remote test files against the kept source:
  - 15 files (341 tests) passed as-is and are retained
  - 2 obsolete `src/cybershield/tests/test_notification_*` files removed
    (tested the old notification API superseded by the kept line)
  - 2 ABC-enforcement tests dropped from `test_notification_service_v2.py`
    (our `NotificationChannel` is a plain base class, not `abc.ABC`)
  - API mismatches fixed: `export_jobs(file_format=...)` and
    `send_test_notification` (matching kept source signatures)
  - 32 ruff errors fixed across 7 test files (SIM117, ARG005, B017/PT011,
    S106, E501, PTH123)
- `tests/conftest.py`: ported `make_job`, `make_job_mock`, `make_app_mock`
  helpers from the remote line (needed by the adopted test files);
  C408 dict() → literals, E501 docstring wrap.
- `test_notification_service.py`: replaced an auto-merged remote ABC
  assertion with `test_base_send_not_implemented` (matches kept plain-base
  implementation).
- Test suite now **1247 passing** (924 InternTrack + 323 CyberGuide);
  ruff + format clean, mypy clean, `make version-check` exit 0.
- Docs re-synced: README badge, PROJECT-PROGRESS, PROJECT-STATUS,
  TODO-CHECKLIST, docs/cscip/17-cicd.md, src/cybershield/PROGRESS.md.

## [1.19.0] - 2026-08-01

### Added

#### Business Metrics Instrumentation (InternTrack)
- `BusinessMetricsStore` in `src/interntrack/metrics.py` — dependency-free
  collector + Prometheus renderer for DB query times, scraper success rates
  and notification delivery rates; global `business_metrics_store`
- Instrumentation wiring:
  - `database/session.py` — SQLAlchemy `before/after_cursor_execute` event
    listeners (positional signature, timestamp on `conn.info`) record query
    durations into `interntrack_db_queries_total` /
    `interntrack_db_query_duration_ms`
  - `scrapers/registry.py` — `fetch_all` records per-source runs/failures
    (`interntrack_scraper_runs_total{source}` /
    `interntrack_scraper_failures_total{source}`)
  - `services/notification_service.py` — `notify` records per-channel
    delivery/failures (`interntrack_notifications_total{channel}` /
    `interntrack_notification_failures_total{channel}`)
- `main.py` — `/metrics` gains a `business` key; `/metrics/prometheus`
  concatenates both renders
- `deploy/grafana/dashboards/business.json` — **InternTrack Business**
  dashboard (uid `interntrack-business`): DB query latency, scraper runs vs
  failures per source, notification delivery vs failures per channel
- `tests/unit/test_business_metrics.py` (13 tests) — store behavior,
  DB-listener wiring (regression guard for the event-signature bug),
  scraper/notification instrumentation, dashboard exprs pinned to emitted
  metrics

### Changed
- Both packages + `.env`/`.env.example` + `pyproject.toml` + deployment
  artifacts synced to **1.19.0**; `make version-check` exit 0

## [1.18.0] - 2026-08-01

### Added

#### Loki + Promtail Log Monitoring (InternTrack)
- `deploy/loki/loki-config.yml` — single-binary Loki (tsdb schema v13,
  filesystem storage, 336h retention, `max_line_size` 1MB)
- `deploy/loki/promtail-config.yml` — Docker-socket service discovery
  (`docker_sd_configs`, 5s refresh) shipping to `http://loki:3100`; parses the
  app's structlog JSON (`timestamp`/`level` labels + RFC3339 timestamp) and
  relabels to `container`/`compose_service`/`compose_project`/`stream`
- `docker-compose.yml` `loki` (3.4.2, port 3100) + `promtail` (3.4.2,
  port 9080, docker.sock read-only, depends_on loki) services + `loki_data`
  volume, all in the `monitoring` profile
- Grafana provisioning adds a **Loki** datasource (uid `loki`,
  `http://loki:3100`)
- `deploy/grafana/dashboards/logs.json` — **InternTrack Logs** dashboard
  (uid `interntrack-logs`): log volume by service, error-level rate,
  top log producers, live `{job="docker"} | json` log panel + service template
- `tests/unit/test_log_monitoring.py` (10 tests) pin the configs to each other
  (loki layout, promtail→loki clients + docker socket, compose services,
  loki datasource, valid LogQL exprs + template var)

### Changed
- Both packages + `.env`/`.env.example` + `pyproject.toml` + deployment
  artifacts synced to **1.18.0**; `make version-check` exit 0

## [1.17.0] - 2026-08-01

### Added

#### Node-Exporter System Monitoring (InternTrack)
- `docker-compose.yml`: new `node-exporter` service
  (`prom/node-exporter:v1.8.2`, port 9100, host `/proc`/`/sys`/`/` mounted
  read-only with `--path.procfs`/`--path.sysfs`/`--path.rootfs`, `monitoring`
  profile) so host CPU/memory/disk/network metrics are scrapeable
- `deploy/prometheus/prometheus.yml`: new `node-exporter` scrape job
  (target `node-exporter:9100`, `component: node-exporter` label)
- `deploy/prometheus/alerts.yml`: new `system` alert group —
  `DiskSpaceLow` (root filesystem free < 10%, critical, 5m), `MemoryHigh`
  (memory usage > 90%, warning, 5m), `CpuHigh` (CPU usage > 90%, warning,
  10m) — all targeting real `node_*` metrics (completes the TODO-CHECKLIST
  System Metrics + disk/memory alerting items)
- `deploy/grafana/dashboards/system.json`: **InternTrack System** dashboard
  (uid `interntrack-system`) — CPU, memory, and disk stat panels plus
  network traffic (`rate(node_network_receive/transmit_bytes_total[5m])`)
  and system load (`node_load1`) timeseries
- Tests: `tests/unit/test_system_monitoring.py` (7 tests) — node-exporter
  service + scrape job wiring, the `system` alert group, and that every
  PromQL expression (alerts + dashboard) references a real node-exporter
  metric; `node_load1` used directly (it's a gauge — `rate()` would be
  invalid PromQL)
- `docs/SECURITY-AND-METHODOLOGIES.md` §7.3 note updated: system alerts now
  ship with the node-exporter target (no longer a future requirement)

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.17.0`; root `pyproject.toml`
  synced — verified by `make version-check` (exit 0)

## [1.16.0] - 2026-08-01

### Added

#### Prometheus Alerting Rules (InternTrack)
- New `deploy/prometheus/alerts.yml` — app-level alert rules in the
  `interntrack-api` group, all targeting the **actual** metrics the API emits
  at `/metrics/prometheus`:
  - `HighErrorRate` — 5xx rate / request rate > 0.1 for 5m (critical)
  - `HighLatency` — `interntrack_http_request_duration_ms > 1000` for 5m
    (warning)
  - `ServiceDown` — `up{job="interntrack-api"} == 0` for 1m (critical)
- `deploy/prometheus/prometheus.yml` now declares `rule_files: [alerts.yml]`
  (resolved relative to the config, i.e. `/etc/prometheus/alerts.yml`), and
  the compose `prometheus` service mounts `./deploy/prometheus/alerts.yml`
  read-only — alerts viewable at `http://localhost:9090/alerts`
- `docs/SECURITY-AND-METHODOLOGIES.md` §7.3 example replaced: it previously
  documented a generic `alerts.yml` using metrics that don't exist
  (`http_requests_total{status=~"5.."}`, `histogram_quantile(...
  http_request_duration_seconds)`); the section now documents the real rules
- Tests: `tests/unit/test_prometheus_alerts.py` (8 tests) — validates the
  rules YAML, expected rule names, every rule has `expr`+`for`, every PromQL
  expression references an emitted `interntrack_http_*` metric (guards against
  drift), `ServiceDown` uses `up{}`, `rule_files` is declared, and the compose
  service mounts the alerts file
- `05-api-design.md`: monitoring-stack section documents the alert table
  (rule / expression / severity / `for`) and the `/alerts` endpoint

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.16.0`; root `pyproject.toml`
  synced — verified by `make version-check` (exit 0)

## [1.15.0] - 2026-08-01

### Added

#### Grafana Monitoring Stack (InternTrack)
- New `deploy/grafana/` assets behind the compose `monitoring` profile:
  - `provisioning/datasources/datasource.yml` — Prometheus datasource (uid
    `prometheus`, url `http://prometheus:9090`, isDefault, 15s timeInterval)
  - `provisioning/dashboards/dashboards.yml` — file provider loading the
    mounted dashboards dir; provisioned dashboards are read-only
    (`allowUiUpdates: false`, `disableDeletion: true`)
  - `dashboards/interntrack.json` — **InternTrack API** dashboard (uid
    `interntrack-api`) with 5 panels: request rate
    (`rate(interntrack_http_requests_total[5m])`), 5xx error rate (5xx rate /
    clamped request rate), average latency stat
    (`interntrack_http_request_duration_ms`), requests by status code
    (`..._by_status_total`), and top paths by request rate
    (`topk(10, ..._by_path_total)`); 15s refresh matching the scrape interval
- `docker-compose.yml`: new `grafana` service
  (`grafana/grafana:11.1.0`, port 3000, env-overridable
  `GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD`, `GF_USERS_ALLOW_SIGN_UP=false`,
  provisioning + dashboards mounted read-only, `grafana_data` volume,
  `depends_on: prometheus`, `monitoring` profile)
- Tests: `tests/unit/test_grafana_dashboard.py` (8 tests) — validates the
  dashboard JSON structure and that **every PromQL expression references a
  metric the API actually emits** (guards against dashboard drift), the
  datasource uid matches provisioning, and the provisioning YAML points at
  `prometheus:9090`
- `pyyaml>=6.0` added to `requirements-dev.txt` (the dashboard tests import
  yaml directly instead of relying on bandit's transitive dependency)
- `05-api-design.md` monitoring-stack section: `docker compose --profile
  monitoring up -d prometheus grafana` + production warning to override the
  default `admin`/`admin` Grafana credentials

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.15.0`; root `pyproject.toml`
  synced — verified by `make version-check` (exit 0)

## [1.14.0] - 2026-08-01

### Added

#### Redis-Backed Rate Limiting (InternTrack)
- New `RedisRateLimitStore` in `middleware/rate_limit.py` — multi-instance
  safe sliding-window limiter using an atomic Lua script over a Redis ZSET
  (prune, count, and record in one round trip); lazily connects via
  `redis.asyncio` (already a dependency, `REDIS_URL` already in compose); the
  `rl:{key}` ZSET **and** the `rl:{key}:seq` member counter both get an
  `EXPIRE` in lockstep so neither leaks in Redis
- On a Redis outage `is_allowed_async` falls back to an in-memory store
  (once-only warning, never fails closed) so the API keeps serving with
  per-instance limits during the outage (the store stays degraded until
  process restart; it never re-attempts Redis to avoid hammering it with
  2s timeouts)
- `get_rate_limit_store()` factory: returns the Redis store when `REDIS_URL`
  is configured, else the global in-memory store; `RateLimitMiddleware` now
  takes a `store` parameter and `main.py` passes the factory result
- `RateLimitStore` gained an async `is_allowed_async` alias so the middleware
  shares one code path across both stores
- `X-RateLimit-Reset` semantics aligned between the in-memory and Redis
  stores (`int(now + window_seconds)` — the window end)
- Tests (12 new): `TestRedisRateLimitStore` via fakeredis (allows, blocks,
  independent keys, window expiry, clear specific/all), fallback tests
  (broken Redis client degrades to in-memory), factory selection tests, the
  async-alias parity test, and a middleware-over-Redis HTTP test
- Dev dependency `fakeredis[lua]>=2.0.0` added to `requirements-dev.txt`
  (lupa is required for the Lua script to run in fakeredis)
- Smoke test now sets `REDIS_URL=''` so the live burst stays deterministic
  even on machines with a local Redis running

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.14.0`; root `pyproject.toml`
  synced — verified by `make version-check` (exit 0)

## [1.13.0] - 2026-08-01

### Added

#### Prometheus Integration (InternTrack)
- `MetricsStore.render_prometheus()` — dependency-free renderer emitting the
  standard Prometheus text exposition format (`# HELP` / `# TYPE` + labeled
  samples) with proper label escaping (backslash, double-quote, newline); no
  `prometheus_client` dependency required
- New `GET /metrics/prometheus` endpoint serving the same in-memory counters
  (`interntrack_http_requests_total`, `interntrack_http_errors_total`,
  `interntrack_http_error_rate`, `interntrack_http_request_duration_ms`) with
  per-path and per-status labels
- `/metrics/prometheus` added to the rate-limiter exempt paths and the
  `MetricsMiddleware` exempt set so scrapers stay reliable and counters stay
  stable
- New `deploy/prometheus/prometheus.yml` scrape config (job
  `interntrack-api`, 15s interval, target `api:8000`) + `prometheus` service
  (`prom/prometheus:v2.53.0`) in `docker-compose.yml` behind the `monitoring`
  profile with a `prometheus_data` volume — `docker compose --profile monitoring up -d prometheus`
- `prometheus.io/scrape|path|port` annotations added to the `k8s/raw/06-api.yaml`
  Service for `kubernetes_sd_configs`-based scraping
- Tests: `TestRenderPrometheus` (format, HELP/TYPE headers, labeled samples,
  label escaping) + middleware tests (endpoint returns `text/plain` text
  format, reflects recorded requests, is not recorded itself) + rate-limit
  exempt-path coverage for `/metrics/prometheus`

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.13.0`; root `pyproject.toml`
  synced — verified by `make version-check` (exit 0)

## [1.12.0] - 2026-08-01

### Added

#### Live Smoke Test
- New `scripts/smoke_test.py` — boots the **real uvicorn server** on an
  ephemeral port against a temp SQLite DB (rate limit enabled, 3/min) and
  verifies over HTTP: `GET /` 200, `GET /health` 200 with
  `version == interntrack.__version__` and `status: healthy`, `GET /metrics`
  snapshot shape, CORS preflight 200 with `access-control-allow-origin: *`,
  unknown route 404 (checked before the burst so the exhausted limit can't
  mask it), rate-limit burst `200 200 429 429 429` (the pre-burst 404 consumes
  one of the 3 credits) with the `RATE_LIMITED` contract; cleans up temp DB
  and log in `finally`; exits non-zero on any failure
- Wired into CI as a new **smoke** job (gated after test) and a
  `make smoke` target

#### Bandit Scope + Makefile Targets
- `dashboard/` and `scripts/` added to the bandit scan scope in CI and
  `make security` / `make security-report`
- `make test` / `test-unit` / `test-integration` / `test-cov` now run the full
  suite (`tests/` + `src/cybershield/tests`) with `PYTHONPATH=src` and
  `--cov=interntrack --cov=cybershield`, matching CI exactly

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.12.0`; root `pyproject.toml`
  synced — verified by `make version-check` (exit 0)

## [1.11.0] - 2026-08-01

### Changed

#### Dashboard Lint Cleanup
- `dashboard/app.py` + `dashboard/components/*`: fixed all 24 pre-existing ruff
  errors (unused imports, unused widget locals, S110 `try/except/pass` →
  `contextlib.suppress`, C408 `dict()` → literals, PIE810, ARG001, E501 long
  lines, COM812) — dashboard now passes `ruff check` and `ruff format` cleanly
- `job_card()` now renders a **View Job** link when a `url` is provided
  (previously the argument was unused)
- `dashboard/` added to the **CI lint/format scope** (`ruff check` +
  `ruff format --check` now cover `src/ tests/ dashboard/`) and to the
  `make lint` / `make format` / `make format-check` targets

#### Rate-Limit Exemption Coverage
- `tests/unit/test_rate_limit.py`: the exempt-paths test now also verifies
  `GET /metrics` bypasses the rate limit (loop of 5 returns 200); the minimal
  `_build_app` test app registers a `/metrics` route so the assertion is real

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.11.0`; root `pyproject.toml`
  version synced — verified by `make version-check` (exit 0)
- Live smoke test (real uvicorn, temp DB/port): `/health` reports
  `{"version": "1.11.0"}`, `/metrics` returns the snapshot shape, CORS
  preflight 200, rate-limit burst `200 200 200 429 429` (limit=3)

## [1.10.0] - 2026-08-01

### Added

#### Version Consistency Gate
- New `scripts/check_versions.py` — standalone checker verifying
  `interntrack.__version__ == cybershield.__version__ == .env.example
  APP_VERSION == pyproject.toml version`; exits non-zero on any drift so CI
  fails on the kind of silent version skew that historically crept in
- Wired into CI as a new **Version consistency** job (gates the test job) and
  a `make version-check` target
- `tests/unit/test_version_check.py` (10 tests) covering all four sources,
  mismatch detection, exit codes, and missing-source handling

#### Dashboard Live Version
- `dashboard/app.py` now fetches the version from `GET /health` (single
  source of truth) instead of a hardcoded string; falls back to
  `DEFAULT_VERSION` when the API is unreachable so the dashboard still renders

### Changed

#### Version Sync (root pyproject.toml + 1.10.0)
- Root `pyproject.toml` `version` bumped from `1.0.0` (stale since the very
  first release) to `1.10.0`; now enforced by the consistency gate
- Both packages bumped to `1.10.0`; `.env`/`.env.example`
  `APP_VERSION=1.10.0`; canaries updated in `tests/unit/test_main.py` and
  `src/cybershield/tests/test_version.py`
- `README.md` badge refreshed to 776 tests
- `CONTRIBUTING.md` Releasing checklist: step 5 notes the dashboard now reads
  from `/health` (the `DEFAULT_VERSION` fallback still needs syncing) and adds
  `make version-check` as the final verification step

## [1.9.0] - 2026-08-01

### Changed

#### Version Sync (both packages)
- `interntrack.__version__` bumped to `1.9.0` (was lagging the CHANGELOG at
  1.7.0) — `app_version` already reads from the package (single source of truth)
- `cybershield.__version__` bumped from `1.0.0` to `1.9.0` and `config.py`
  `app_version` now reads the package version instead of a hardcoded string
- `.env` + `.env.example` `APP_VERSION=1.9.0`; version canaries updated in
  `tests/unit/test_main.py` and new `src/cybershield/tests/test_version.py`
  (2 tests) so CI validates both packages report the current release

#### Documentation
- `docs/05-api-design.md`: new **System Endpoints** section documenting
  `GET /health` (200 healthy / 503 degraded readiness probe) and `GET /metrics`
  (counts, error rate, latency, status histogram); `/metrics` added to the
  rate-limit exempt paths
- `README.md`: badges refreshed to 764 tests + bandit/safety/trivy clean;
  **System** endpoint table (`/health`, `/metrics`) added
- `CONTRIBUTING.md`: new **Releasing** section — step-by-step version-bump
  checklist (CHANGELOG, `__version__` in both packages, `.env`/`.env.example`,
  version canaries) so future releases can't drift

## [1.8.0] - 2026-08-01

### Added

#### Live Smoke Test ✅
- Booted the real API (uvicorn) on a temp port/DB and verified over HTTP: `GET /`
  (200 app info), `GET /health` (200 healthy, database ok), `GET /docs` (404 in
  prod mode), CORS preflight (200 with allow-origin), 404 routes, and a
  rate-limit burst (`req1:200 req2:200 req3:429 req4:429 req5:429` at 3/min)
  with the `RATE_LIMITED` error contract

#### Request Metrics Endpoint (InternTrack)
- New `src/interntrack/metrics.py`: in-memory `MetricsStore` (total requests,
  errors, latency, per-path counts, status histogram, `snapshot()`, `reset()`)
  + `MetricsMiddleware` recording every request except `/metrics` itself
- `GET /metrics` exposes the snapshot for monitoring (TODO-CHECKLIST §14)
- Middleware registered after the rate limiter so 429s are recorded, before CORS
- `/metrics` added to the rate-limiter exempt paths so scrapers stay reliable
- `tests/unit/test_metrics.py` (10 tests): store counters/reset + endpoint
  integration via the client fixture

#### Version Single Source of Truth
- `config.py` `app_version` now reads `__version__` from the package (was a
  hardcoded `1.0.0` that had drifted from the CHANGELOG)
- Bumped `interntrack.__version__` to `1.7.0`; updated `.env` and `.env.example`
  `APP_VERSION` to match
- `TestVersionConsistency` (2 tests) pins `app_version == __version__` and the
  CHANGELOG release so the drift can never silently recur

#### Deployment & CI
- `.github/workflows/cd.yml` created (was only documented): tag-based Docker
  build/push + SSH deploy, matching the target pipeline in 17-cicd.md
- CI `security` job now runs a Trivy filesystem scan (HIGH/CRITICAL, exit-code
  1) scoped to `src/` (skips tests/dashboard/data/migrations)
- CI `security` job renamed to "Security (bandit + safety + trivy)"

#### Test Coverage Push
- `tests/unit/test_worker.py` rewritten: 4 meaningful tests (scheduler setup,
  signal-handler registration, shutdown handler exit, entrypoint guard)
  replacing a no-op test — `worker.py` coverage 0% → **100%**
- `utils/helpers.py` already at 100%; combined InternTrack count 429 → **443**

## [1.7.0] - 2026-08-01

### Changed

#### Readiness Probe Fix (InternTrack)
- `GET /health` no longer depends on `get_db` — it creates its own session via
  `async_session_factory` inside the handler with a try/except
- A fully unreachable database engine now returns **503 `degraded`** instead of
  a 500 from the dependency layer (the previous readiness gap)
- Unit tests rewritten to monkeypatch `interntrack.database.session.async_session_factory`
  and cover three paths: healthy, session-creation failure (engine down), and
  probe failure (`SELECT 1` raises)
- `tests/conftest.py` `client` fixture points `async_session_factory` at the
  in-memory test engine (restored after each test) so the integration health
  probe succeeds
- README badges refreshed: 749 tests → 750, added bandit + safety security badge

## [1.6.0] - 2026-08-01

### Added

#### Dependency Security Scan (safety)
- `safety check -r requirements.txt -r requirements-dev.txt --full-report` wired
  into the CI `security` job (installed as `safety>=2.3.0,<3` to avoid the v3
  `check`→`scan` migration drift, matching `requirements-dev.txt`)
- Local scan result: **22 packages scanned, 0 vulnerabilities**
  (`requirements.txt`) and 9 scanned, 0 vulnerabilities (`requirements-dev.txt`)
- Makefile: new `deps-check` target for the dependency scan

#### Report Service Hardening (InternTrack)
- `report_service.py`: template directory is now resolved module-relative
  (`Path(__file__).resolve().parent.parent / "reports" / "templates"`) instead of
  CWD-relative, so rendering works from any working directory
- New `tests/unit/test_report_service.py` (10 tests): template dir resolution,
  Jinja env loading of all 3 templates, async `render_report` HTML assertions
  for daily/weekly/monthly (incl. the `{:,.0f}` salary formatting), unknown-type
  raises `jinja2.TemplateNotFound`, autoescape blocks `<script>` injection, and
  `generate_daily/weekly/monthly` shape tests with mocked repositories

## [1.5.0] - 2026-08-01

### Added

#### Security Scanning (bandit)
- First security scan: `bandit -r src/` — 3 high (B324 weak MD5) + 5 medium
  (B104 bind-all) findings found and resolved
- MD5 calls in `cybershield/cache.py` and `cybershield/scrapers/base.py` now use
  `usedforsecurity=False` (cache/dedup fingerprinting, not security)
- Intentional dev `0.0.0.0` binds marked `# nosec B104` (env-overridable defaults)
- CI: new `security` job (`bandit -r src/ -ll -q`) gates the test job
- Makefile: `security` (bandit gate) and `security-report` (HTML) targets

#### Pre-commit & Environment
- Added `.pre-commit-config.yaml` (ruff --fix + ruff-format, mypy with
  `PYTHONPATH=src`, commitizen) matching the hooks documented in 17-cicd.md
- `.env.example` rewritten: added `RATE_LIMIT_*` and CORS variables

#### Health Check Enhancement (InternTrack)
- `GET /health` now runs a DB connectivity probe (`SELECT 1` via `get_db`)
- Returns 200 `healthy` with `version` + `database: ok`, or 503 `degraded`
  when the probe fails
- Tests: integration health test asserts `database: ok` + `version`; new
  `TestHealthEndpoint` unit tests (healthy + degraded 503)

## [1.4.0] - 2026-08-01

### Added

#### API Rate Limiting (InternTrack)
- New `src/interntrack/middleware/rate_limit.py`: in-memory sliding-window
  `RateLimitStore` + `RateLimitMiddleware` (per-IP and per-API-key limits)
- 429 responses follow the standard `{error: {code, message, details}}` contract
  with `X-RateLimit-*` headers and `Retry-After`
- Exempt paths: `/`, `/health`, `/docs`, `/redoc`, `/openapi.json`
- Settings: `rate_limit_enabled`, `rate_limit_per_minute` (100), and
  `rate_limit_api_key_per_minute` (1000); middleware wired in `main.py` when enabled
- `tests/unit/test_rate_limit.py`: store behavior (windows, independence, cleanup,
  clear) + HTTP middleware tests (429 contract, exempt paths, per-API-key limits)
- `TestRateLimitConfig` in `tests/unit/test_main.py`; conftest disables rate
  limiting for deterministic integration tests

#### Dashboard Component Tests
- `tests/unit/test_dashboard_components.py` (46 tests): cards, forms, and charts
  logic tested with lightweight fakes injected into `sys.modules` (streamlit and
  plotly are not required for the backend suite)
- `tests/unit/test_rate_limit.py`: 10 tests including CORS-on-429 coverage
  (RateLimitMiddleware registered before CORS so browser clients see
  `access-control-allow-origin` on rate-limited responses)
- Covers metric/job/application cards, skill badges, section headers, info/
  warning cards, search/filter/notification/skill forms, and all chart
  data-shaping helpers

#### CI & Docs
- `.github/workflows/ci.yml`: test job now collects coverage
  (`--cov=interntrack --cov=cybershield`) and uploads `coverage.xml` artifact
- `docs/05-api-design.md`: API rate limiting section (limits, headers, 429 contract)
- `docs/cscip/17-cicd.md`: aligned with the actual coverage step
- README badges updated: 737 tests, 67% coverage, CI workflow badge

## [1.3.0] - 2026-08-01

### Added

#### CI/CD
- Added `.github/workflows/ci.yml` — ruff lint + format check, mypy on both
  modules, and the combined InternTrack + CyberGuide test suite (679 tests)

#### Documentation
- `docs/01-software-architecture.md` — exception `to_dict()` contract, exception
  handler ordering, CORS settings & configuration
- `docs/05-api-design.md` — error contract table (HTTP status → error code) and
  CORS configuration + preflight example
- `docs/cscip/15-deployment.md` — `is_trusted` migration note for existing
  deployments (ALTER TABLE) since editing the initial migration only covers
  fresh schemas

#### Test Coverage (CyberGuide engines + Elasticsearch)
- Scam detection: email/domain edge cases, risk-level boundaries (low/medium/
  high/critical), score breakdown, batch analysis
- Deduplication: URL fragment/empty normalization, hash case-insensitivity,
  empty similarity, canonical selection, non-duplicate find
- Verification: naive datetime deadlines, weighted score calculation
- Classification: explicit years extraction, batch aggregation
- Elasticsearch: close error handling, missing-ID bulk skip, bulk error via
  injected fake module, match_all search, delete success, index stats

## [1.2.0] - 2026-08-01

### Added

#### Error Handling Architecture (InternTrack)
- Registered a dedicated `AppException` handler in `main.py` (`exc.status` + `exc.to_dict()`) so domain errors (404/409/422/503) surface correctly instead of being masked as 500
- Global fallback handler returns a consistent `{error: {code, message, details}}` payload with debug detail gated by `settings.debug`
- CORS middleware is now settings-driven with comma-separated env parsing (`CORS_ORIGINS`)
- `Settings.is_production` property and `validate_security()` startup warnings (secret key + CORS hardening)
- New tests: `tests/unit/test_main.py` (9 tests) covering the exception handlers, CORS parsing, and security validation; `TestCorsMiddleware` integration tests
- Smoke-tested live API: /health, /, docs (404 in prod), CORS preflight, 404 routes

#### CyberGuide (cybershield) Quality Hardening
- Fixed 107 mypy errors across 37 files; mypy now clean on all 177 source files
- Fixed real runtime bugs:
  - httpx 0.28 `allow_redirects` removed → client now uses `follow_redirects=True`
  - `NotificationPriority.NORMAL` doesn't exist → `MEDIUM`
  - `SkillTrend.recorded_at` → `period_start` (non-existent column)
  - `Company.is_trusted` column added to models + migration; `Company.jobs` relationship added
  - `Job.company` relationship renamed to `company_ref` (was shadowing the string column and breaking `Job.company.ilike` search)
  - `NotFoundError(resource, identifier)` two-arg calls fixed in repositories
  - Scheduler `not Job.is_verified` (evaluated a Python bool) → proper SQL filter
  - `NotificationPriority` typing, scam score float init, dedup sha256 hashing
- Alembic `001_initial_schema.py` updated to include `is_trusted` column
- ruff: 1,294 errors fixed; all checks pass; 212 files formatted

## [1.1.0] - 2026-07-30

### Added

#### Test Coverage Improvements
- Added 290+ unit tests across all modules
- Test coverage improved from 42% to 82%
- Added test_notification_service.py (20 tests)
- Added test_ai_service.py (12 tests)
- Added test_classification_engine.py (15 tests)
- Added test_hackernews_scraper.py (20 tests)
- Added test_linkedin_scraper.py (14 tests)
- Added test_remoteok_scraper.py (15 tests)
- Added test_rss_feeds_scraper.py (18 tests)
- Added test_indeed_scraper.py (12 tests)
- Added test_glassdoor_scraper.py (12 tests)
- Added test_learning_service.py (16 tests)
- Added test_scheduler_jobs.py (10 tests)
- Added test_scheduler_setup.py (3 tests)
- Added test_cache.py (11 tests)
- Added test_logger.py (3 tests)
- Added test_dependencies.py (12 tests)
- Added test_worker.py (2 tests)
- Added test_encryption.py (10 tests)
- Added test_helpers.py (15 tests)

#### Documentation Updates
- Updated README.md with coverage badge (82%)
- Updated PROJECT-PROGRESS.md with 347 tests
- Updated PROJECT-STATUS.md to 100% complete
- Added CHANGELOG.md (this file)
- Added CONTRIBUTING.md with guidelines
- Added SECURITY.md with vulnerability reporting

#### Security Updates
- Contact email updated to parthasarathi442004@gmail.com
- Creator name added: PARTHASARATHI B
- Fixed datetime.utcnow() deprecation warnings (5 files)

### Fixed
- NotificationService import error (renamed to NotificationManager)
- HttpUrl serialization issue (changed to str in schema)
- Test isolation with unique URLs
- Job statistics tuple-to-dict conversion
- datetime.utcnow() deprecation warnings in models, services, repositories
- Removed redundant str() conversion in jobs.py endpoint
- Fixed docker-compose.yml version deprecation

## [1.0.0] - 2026-07-30

### Added

#### Core Application
- FastAPI application with async support
- Pydantic settings management
- Dependency injection system
- Background worker for scheduled tasks

#### Domain Layer
- SQLAlchemy models (Job, Application, Skill, Company, etc.)
- Enumerations (JobType, ApplicationStatus, NotificationChannel)
- Custom exceptions (AppException, NotFoundError, DuplicateJobError)

#### Database Layer
- Async SQLite database support
- Alembic migrations
- Session management

#### Repository Layer
- Base repository with CRUD operations
- Job repository with advanced queries
- Application repository with status tracking
- Skill repository
- User repository

#### Service Layer
- Job service with discovery orchestration
- Application service with pipeline tracking
- Notification service (Telegram, Email, Discord, Slack)
- Report service (Daily, Weekly, Monthly)
- AI service (Ollama, Gemini)
- Learning service with skill recommendations

#### Scrapers
- HackerNews scraper
- RemoteOK scraper
- RSS feed scraper
- LinkedIn scraper
- Indeed scraper
- Glassdoor scraper
- Scraper registry

#### Engines
- Deduplication engine
- Verification engine
- AI classification engine

#### API Endpoints
- Jobs CRUD endpoints
- Application tracking endpoints
- Report generation endpoints
- Notification endpoints
- Skills endpoints
- Dashboard data endpoints

#### Dashboard
- Streamlit dashboard
- Job overview page
- Application tracking page
- Analytics charts
- Learning resources page

#### Testing
- pytest configuration
- Test fixtures
- Unit tests for services
- Unit tests for engines
- Unit tests for utilities
- Unit tests for scrapers
- Integration tests for API

#### CI/CD
- GitHub Actions CI workflow
- GitHub Actions CD workflow

#### Docker
- Dockerfile for API
- Dockerfile for Dashboard
- docker-compose.yml

#### Documentation
- README.md
- LICENSE (MIT)
- SETUP.md
- Architecture documentation
- Security guide
- TODO checklist
- Project progress tracking

## [0.1.0] - 2026-07-29

### Added
- Initial project structure
- Domain layer implementation
- Database layer implementation
- Basic API endpoints
- Initial test setup

## [1.20.0] - 2026-08-04

### Fixed

- **Resume parsing for non-security (Data Analyst) resumes** — new
  `data_analysis` skill category (SQL, Excel, Power BI, DAX, MySQL, Pandas,
  Jupyter, ...); Symbol-font bullets (\uf0b7) normalized; `www.` prefix
  accepted in GitHub/LinkedIn URLs; generic "Certificate of X" lines
  captured; project-section layout detection now handles dot-title + dash-
  detail + plain-title layouts; education GPA prefers scaled values
  ("6.75/10") and decimals ("8.65"), and year/institution extraction works
  whether the school name precedes or follows the degree. Validated on the
  real Dnyaneshwari vanjari resume (15 skills, 2 projects, clean education,
  4 certificates, LinkedIn detected).

### Fixed (job → resume matching on the live app)

- **Live resume-match endpoint crashed with INTERNAL_ERROR**: the Neon
  `jobs` table (created by the interntrack model) had no
  `required_skills`/`preferred_skills` columns, and cybershield's `Job`
  model eager-loads relationships that join against the differently-shaped
  live `applications` table. Fixes:
  - `cybershield.database.session.init_db` now syncs missing model columns
    onto existing tables (idempotent ALTER TABLE), auto-healing the live
    schema on cold start.
  - Match endpoints use a column-only select (no eager relationship joins)
    via a lightweight `_JobMatchData` dataclass.
  - Matching falls back to the job's `tags` column when the dedicated skill
    columns are empty (live jobs keep skills in `tags`).
  - `Job` model gained a `tags` column to match the live table.
- **Skill extraction in scrapers** now uses word-boundary matching (no more
  "Go" from Google, "C" from Certificate) with a broader canonical keyword
  list, exposed as `extract_skills_from_text`.
- **Backfill script** `interntrack.scripts.backfill_job_skills` enriches
  existing jobs with extracted skills; run against the live Neon DB
  (6 jobs updated, e.g. ClickHouse → Python/TypeScript/Go/Rust/SQL/Node.js/
  AWS/Kubernetes).

- **PDF extraction on Vercel (no pymupdf)** — added `pypdf` (pure-Python,
  installs in any sandbox) as the second extractor in the chain
  (`pymupdf` → `pypdf` → regex fallback). Verified: with pymupdf hidden,
  the Dnyaneshwari resume still parses to 15 skills, 2 projects, clean
  education (GPA 8.65), 4 certifications and a detected LinkedIn URL —
  previously the regex fallback garbled this PDF (848 chars extracted vs
  2692 with pypdf). `pypdf` pinned in `requirements.txt`,
  `src/cybershield/requirements.txt` and the mypy override list.

- **CI green** — bumped `pypdf` to 6.14.2 (fixes CVE-2026-59935/59936,
  HIGH DoS in crafted-PDF inline images) and ruff-formatted
  `resume_service.py` so the Lint + Security jobs pass.

- **Fairer resume-job matching for domain-transition candidates** — the
  matcher previously scored exact-name overlap only, so a Data Analyst
  resume (python/sql/excel) vs a Software Engineer job (go/kubernetes)
  flatlined at 0.0. It now scores in three tiers: exact (1.0/1.0), synonym
  (0.6/0.5, e.g. k8s==kubernetes, golang==go) and same-category
  transferable credit (0.35/0.2, e.g. python covering go via `scripting`),
  with a new `related_skills` response field and a "Transferable skills"
  suggestion. Exact matches still dominate, and truly unrelated roles
  (e.g. a `compliance`-only job) still score 0.0.

- **Matcher polish from code review** — preferred-synonym matches now score
  at the documented 0.5 weight (was accidentally 0.6), noise tags such as
  `remote`/`full-time` are filtered out of job-skill fallback so they no
  longer pollute missing-skills or suggestions, and the tier helper is now
  properly typed. Regression tests added for both behaviors.

- **Fixed dashboard discovery returning nothing** — the Streamlit dashboard
  sends the search query in the JSON body (`{"query": ...}`) but the
  `/jobs/discovery/run` endpoint only read it from a query parameter, so the
  button silently ran the default `python developer` search and found 0 new
  jobs. The endpoint now accepts the query from the body (body wins) while
  keeping `?query=` backward compatibility. Regression tests added for both
  forms.

- **Cybersecurity discovery now actually finds security jobs** — the scrapers
  required the exact search phrase to appear verbatim, so a "security analyst"
  search returned 0 and "cybersecurity" missed SOC / pentest / appsec roles
  that never use that literal word. Added a shared `matches_query()` matcher
  (multi-word queries match on ANY token) plus security-family keyword
  expansion (`cybersecurity`/`security`/`infosec`/`vapt`/`pentest` now also
  match security, SOC, penetration, appsec, SIEM, incident response, ...).
  The daily cron now also runs a dedicated cybersecurity discovery at 07:00
  UTC (previously only software-engineering / python-developer queries).
- **Notifications now actually fire on Vercel** — the `/reports/daily`
  endpoint (which the free GitHub cron hits) generated the report but never
  sent it, and discovery never notified when new jobs were saved. Both now
  push to the configured channels (email / Telegram / Discord) when any are
  set up; no-op otherwise. Note: `GET /api/v1/notifications/channels` still
  returns `[]` until SMTP / Telegram / Discord credentials are added to the
  Vercel environment variables.
- **Discovery precision pass** — the first attempt surfaced security jobs but
  with too much noise: ANY-token substring matching let a "security analyst"
  run save Data/AML/Financial Analyst roles, and "soc" matched "social media".
  The matcher now uses AND semantics (every query word must match, so
  "security analyst" finds only security-analyst roles), word-boundary
  matching ("soc" no longer hits "Social"), and light stemming
  ("software engineering" still matches "Software Engineer"). The RemoteOK
  JSON API source was removed from the default registry because it now
  returns non-job junk entries ("Menu", "Basic", "Elite", "Cleaning
  Assistant") — RemoteOK listings still arrive via its RSS feed. The 40 junk
  rows it had polluted the live DB with were cleaned up.
- **Security discovery matches the title, not the description** — RSS job
  descriptions routinely mention "security" in generic contexts ("security
  and compliance", "data security"), which kept surfacing sales/marketing
  roles for a "cybersecurity" search. Security-family queries now match
  against the job title only (word-boundary), so "cybersecurity" surfaces
  Security/SOC/Pentest/Privacy titles and skips Web Developer / Marketing
  Manager listings that merely mention "security" in their summary.
  Non-security queries (e.g. "python developer") still match the full text.
  The 11 non-security rows my earlier test runs had saved were cleaned from
  the live DB (30 jobs remain, all cron-discovered).
- **Resume parser now recognizes SQLi + Cybersecurity** — the resume of a
  VAPT candidate mentions "SQLi" and "Cybersecurity", but the parser only
  extracted the generic "sql" skill (data_analysis), so matching leaned
  toward coding/data jobs. Added `sqli` (web_security) and `cybersecurity` /
  `offensive security` (penetration_testing) to the security skill
  vocabulary; word boundaries guarantee "sqli" never also extracts "sql".
  The stored resume for user `parthasarathi` was re-parsed (38 skills, up
  from 36) so the live matcher uses the fixed skills immediately.
- **Job alerts now carry apply links + your match %** — the daily-report
  notification previously sent only counts ("New Jobs: 5"). It now lists
  each new job with title, company, the registration/apply link, and a
  🎯 match % computed against your uploaded resume (best matches first,
  using the same 3-tier matcher as the dashboard). Triggered by the daily
  cron (07:00 UTC) via /reports/daily and by every discovery run that saves
  new jobs.
- **Email alerts actually send now (live-bug fix)** — the deployed email
  channel reported `false` on every send even though the SMTP credentials
  were valid. Root cause: `EmailChannel.send()` built the MIME message with
  `From`/`Subject` but never set the `To` recipient, so `smtplib` raised
  `ValueError: To address must be set` and the manager swallowed it into
  `email: false`. The channel now always sets `To` (defaults to the SMTP
  user; overridable via `to_email`), with a regression test asserting the
  recipient header is present.
- **Daily alert now groups jobs by age with expiry badges** — the digest is
  no longer one flat list. Jobs are grouped into sections (🟢 New today,
  🟡 1 day ago, 🟠 2–3 days ago, ⚪ 4+ days ago) using each listing's
  `posted_at`/`created_at`, and each job carries its expiry status: ⏳ closing
  soon (≤2 days), ❌ expired/closed, or a normal expiry date — powered by the
  existing `expires_at`/`is_active` columns and the `get_closing_soon()`
  repository query. The report API now also exposes `posted_at`, `created_at`,
  `expires_at`, `is_active` and `age_days` per job.
- **Daily alert now has domain sections + applied tracking** — jobs are
  grouped by domain (🔐 Cybersecurity / VAPT / SOC, 💻 Coding / Software,
  📊 Data & Analytics, 🎨 Design, 📣 Marketing / Sales, 💰 Finance / Admin,
  📦 Other) using a new rule-based classifier that reads the role part of
  the title (RSS titles prefix the company, e.g. "Keeper Security: Account
  Manager" — the company name no longer leaks the job into the security
  bucket). Each job line now also shows ✅ Applied / ⬜ Not applied (from the
  applications table) plus its age badge (🟢 today / 🟡 1d / 🟠 Nd / ⚪ Nd)
  and expiry status. New ApplicationRepository.get_applied_job_ids() backs
  the applied marker; the report API exposes `is_applied` and `domain` per
  job.
- **Discovery now bridges the cybershield scraper library into the live
  pipeline** — previously the deployed registry only polled 5 sources
  (HackerNews, RSS feeds, LinkedIn, Indeed, Glassdoor). A new
  `CybershieldScraperAdapter` wraps the existing Indian internship-board
  scrapers (Internshala, Unstop, Naukri, Freshersworld) and security-company
  career portals (CrowdStrike, Palo Alto, Fortinet, Check Point, Symantec,
  McAfee, Trend Micro) behind the interntrack `BaseScraper` interface, so
  they participate in the same discovery/dedup/matching/alert flow.
  `JobSource` gained `internshala`/`unstop`/`naukri`/`freshersworld`/
  `company` values. Note: several of those sites block datacenter scraping
  (HTTP 400/404/422 from a dev machine), so real coverage varies — the
  registry logs and skips any source that errors, and the working ones feed
  the daily alert.
- **Discovery runs sources concurrently with fast-fail timeouts** — bridging
  in the internship/company scrapers made a full discovery run sequential
  and slow (51s+), too close to Vercel's serverless function limit. The
  registry now fetches sources in parallel (bounded at 5 concurrent) so wall
  time is roughly the slowest source (~19s), and each cybershield adapter
  caps its source at 8s and returns [] on timeout. Live verification:
  "cybersecurity" discovery now actually returns real vendor security roles
  from Symantec and TrendMicro (Digital Forensics Analyst, Threat Research
  Editor, Incident Response Coordinator) — sources that blocked earlier
  (Internshala 500, Naukri 400, Workday 422) are skipped and logged.
- **Bridged sources now keep their real names in the DB** — JobSource gained
  internshala/unstop/naukri/freshersworld/company values and the Job model's
  source coercion maps the bridged vendor portals (symantec, trendmicro,
  crowdstrike, ...) to `company` instead of `unknown`, so discovery runs
  record which portal each listing came from.
- **New source: direct security-company Greenhouse boards** — most security
  vendors run careers through Greenhouse, whose public board API needs no
  key and never blocks. A new `GreenhouseBoardScraper` polls verified boards
  (Zscaler, Okta, Cloudflare, KnowBe4, Veracode, BeyondTrust, ThreatLocker)
  and feeds real vendor roles (Staff Security Analyst at Okta, Incident
  Response Analyst at Cloudflare, Cyber Threat Intelligence Research Analyst
  at ThreatLocker) into the same discovery/dedup/matching flow. Also added
  the Remotive remote-jobs RSS feed. Discovery now spans 17 source entries.
- **Dashboard Saved Jobs page now groups jobs by category** — the Jobs page
  previously listed every saved job as one flat expander list. It now
  classifies each job into the same domains as the alert (🔐 Cybersecurity /
  VAPT / SOC, 💻 Coding / Software, 📊 Data & Analytics, 🎨 Design, 💰
  Finance / Admin, 📣 Marketing / Sales, 📦 Other) using the identical
  role-part classifier, shows a category filter dropdown with counts, and
  renders each category as its own section. RSS "Company: Role" titles are
  classified by the role part only, so "Keeper Security: Account Manager"
  stays in Marketing.
- **Dashboard professional redesign** — the Saved Jobs page keeps its
  category grouping but now presents it in a polished design system:
  Inter font + theme-aware light/dark variables, gradient metric tiles on
  Overview, stat tiles (Saved/Categories/New-24h/Tech Roles), a segmented
  pill category filter (with radio fallback), per-category section headers
  with colored icon tiles, count badges and share-of-jobs progress bars,
  and clean hoverable job cards with chip badges (company/location/source/
  salary), human-relative posting times, and escaped HTML (all scraped
  fields are escaped before unsafe_allow_html rendering to prevent XSS).
- **Daily alert preferences (category picker for email/Telegram)** — the
  daily digest previously always sent every category. A new
  `alert_preferences` table (auto-created on deploy) stores per-user
  domains / channels / min-match-score, exposed via
  GET+PUT `/api/v1/notifications/preferences/{user_id}` and a
  `POST .../send-alert` endpoint. `ReportService.generate_daily_report`
  filters jobs by selected domains (summary counts follow the filter), the
  alert message drops jobs below the optional resume-match threshold and
  prints a "filtered to …" footer, and both the GitHub cron
  (`/reports/daily`) and the APScheduler digest honor the saved
  preferences — alerts can be fully disabled via `is_enabled`. The
  dashboard gained a 🔔 Notifications section in Settings: channel
  multiselect, category pills (e.g. select 🔐 Cybersecurity to receive only
  security jobs), min-match slider, Save, and a "Send Test Alert Now"
  button. 18 new tests.
- **One-off alert tester + send history** — the dashboard Notifications
  section gained (a) a one-off alert expander that sends a single alert with
  any categories/channels WITHOUT touching saved preferences (the
  send-alert API accepts an optional override body), and (b) a Recent
  Alerts history table powered by a new `notification_history` table
  (auto-created) + GET /api/v1/notifications/preferences/{user_id}/history.
  Every manual test, one-off alert, and scheduled digest is recorded
  (subject, channels, categories, job count, per-channel delivery) so the
  user can see exactly what was sent and whether it was delivered.
  Refactored the duplicate category-pills fallback into a shared
  `_category_picker_multi` helper. 5 new tests.
- **No-duplicates daily alerts + India/Kolkata schedule** — the daily
  refresh cron now runs at 08:00 / 13:00 / 19:00 IST (02:30 / 07:30 / 13:30
  UTC) so the email/Telegram digests arrive at Indian-friendly times. Each
  alert only includes jobs created since the previous alert: a new
  `last_alert_at` window on `alert_preferences` (auto-added on deploy) is
  advanced after every send, `generate_daily_report` filters by it, the
  scheduled digest skips empty sends, and one-off test alerts never advance
  the window. The dashboard history now shows sent times in IST and notes
  that alerts contain only new jobs. 6 new tests.
- **Per-slot alert categories + Sunday weekly digest + Telegram Apply
  buttons** — the three daily sends can now each carry a different category:
  a `slot_domains` map on `alert_preferences` (morning/afternoon/evening,
  editable from the dashboard with per-slot pills) plus sensible defaults
  (morning=security, afternoon=coding, evening=coding+data) so the cron's
  `/reports/daily?slot=morning|afternoon|evening` calls deliver distinct
  digests out of the box. A new Sunday cron (09:00 IST) hits the new
  `/reports/weekly-alert` endpoint which recaps the last 7 days through the
  saved channels (toggleable via `weekly_enabled`) and records history.
  Telegram alerts are now chunked into small messages (4 jobs each) with
  inline **Apply** keyboard buttons linking straight to each listing, while
  email still gets the full single digest; `_deliver_alert` unifies the
  path. 14 new tests.
