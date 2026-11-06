# VibeFinderAI

VibeFinderAI is an AI-powered, vibe-first music discovery platform.
Instead of searching by artist or genre only, users describe a feeling or scene in natural language and get a playable recommendation set with controls for artist similarity, nicheness, BPM, language, and service integrations.

Production frontend: https://vibefinderai.netlify.app/
Production backend: https://vibefinderai.onrender.com/

## Latest Project Status (March 2026)

- Monorepo with React + Vite frontend and FastAPI backend
- Supabase PostgreSQL via Prisma Python client
- Multi-service integrations: Spotify, YouTube, Last.fm, Deezer, SoundCloud, Apple
- Built-in analytics dashboard with token-gated metrics endpoints
- Semantic ranking fallback system tuned for low-memory Render deployment
- Persistent YouTube search caching backed by DB thin-pool cache

## Repository Layout

- `frontend/` - React UI (Vite + Tailwind v4)
- `backend/` - FastAPI API server, recommendation engine, analytics routes, service OAuth routes
- `backend/core/` - core vibe engine and ranking logic
- `backend/routes/` - auth, analytics, playlist, Spotify, services, Apple, metrics auth
- `backend/analyzers/` - semantic + sentiment analyzers and reporting utilities
- `backend/data/` - configs and enrichment scripts
- `analysis_reports/` - test and batch analysis artifacts
- `run_archives/` - archived run logs
- `tobeanalysed/` - input/result scratch and checkpoint files for batch workflows

See `filesystem.md` for a broader structural reference.

## Tech Stack

### Frontend

- React 19
- Vite 7
- Tailwind CSS 4
- ESLint 9

### Backend

- Python 3.12
- FastAPI + Uvicorn
- Prisma (Python)
- JWT auth (`PyJWT` + `python-jose` for metrics auth)
- `httpx` and `aiohttp` for external API access
- `slowapi` rate limiting (when available)

### Data and Infrastructure

- Supabase PostgreSQL
- Render deployment for backend
- Netlify deployment for frontend

## Core Capabilities

- Natural-language vibe analysis and recommendation generation
- Optional Gemini enhancement path when configured (`GEMINI_API_KEY`)
- Language-aware vibe tagging
- Track feedback loop (thumbs up/down)
- Playlist and social-style persistence flows
- OAuth flows for connected services
- Real-time analytics snapshots and live metrics

## Analytics System

Analytics is integrated and active in the backend.

Key endpoints:

- `POST /api/metrics/auth` - exchange passphrase for 7-day metrics token
- `GET /api/analytics/dashboard` - aggregate dashboard snapshot
- `GET /api/analytics/live` - lightweight live stats
- `GET /api/analytics/vibes` - vibe distribution
- `GET /api/analytics/export` - CSV export

See:

- `ANALYTICS.md`
- `ANALYTICS_OVERVIEW.md`
- `ANALYTICS_INTEGRATION.md`
- `ANALYTICS_ARCHITECTURE.txt`

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.12+
- pip
- Prisma CLI available through backend setup scripts
- Supabase/PostgreSQL connection strings

### 1) Install dependencies

From repo root:

```bash
npm install
cd frontend && npm install
cd ../backend && pip install -r requirements.txt
```

Or use root helper script:

```bash
npm run install:all
```

### 2) Configure environment variables

### Frontend

`frontend/.env.local`

```env
VITE_API_URL=http://localhost:8000
```

`frontend/.env.production`

```env
VITE_API_URL=https://vibefinderai.onrender.com
```

### Backend

Create `backend/.env` with at least:

```env
DATABASE_URL=postgresql://...
DIRECT_URL=postgresql://...
SECRET_KEY=replace_me
FRONTEND_URL_PROD=http://localhost:5173
FRONTEND_URL=https://vibefinderai.netlify.app
BACKEND_URL=https://vibefinderai.onrender.com

LASTFM_API_KEY=
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
YOUTUBE_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

METRICS_PASSPHRASE=
METRICS_SECRET=

GEMINI_API_KEY=
```

Note: some integrations require additional service-specific secrets (for example Last.fm shared secret, Deezer and SoundCloud OAuth credentials, Apple credentials).

Replace `SECRET_KEY` with a private random value of at least 32 bytes before starting
the backend. Missing, blank, short and the former built-in default keys are rejected.
For example, generate a value locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`
and store it in the backend secret environment, never in frontend settings or Git.
Use the same user signing key on every backend replica.

The metrics dashboard also requires `METRICS_PASSPHRASE` and a separate random
`METRICS_SECRET` of at least 32 bytes. It cannot reuse `SECRET_KEY`; an absent or
invalid metrics key disables metrics access. Existing metrics sessions need a new
login because metrics tokens now require an explicit purpose claim. Existing user
tokens remain valid until expiry when they contain a nonblank user ID and use the
configured signing key. Rotate any formerly public/default key and sign users in
again before deploying; changing this source does not rotate deployed secrets.

### 3) Run in development

From repo root (both frontend + backend):

```bash
npm run dev
```

Or separately:

```bash
# frontend
cd frontend
npm run dev

# backend
cd backend
uvicorn main:app --reload --port 8000
```

### 4) Health check

```bash
curl http://localhost:8000/health
```

Expected response includes status and database connectivity.

## API Overview

Common backend routes currently include:

- `GET /` - service metadata
- `GET /health` - health probe
- `POST /auth/register`, `POST /auth/token` - auth flows
- `POST /api/vibe/analyze` - core vibe analysis request
- `GET /api/playlist/*` - playlist operations
- `GET /api/services/*` - multi-service OAuth and actions
- `GET /api/spotify/*` - Spotify integration endpoints
- `GET /api/analytics/*` - analytics data endpoints

For full route-level details, refer to files under `backend/routes/` and `backend/main.py`.

## Deployment

Backend deployment configuration is in `render.yaml` and uses `backend/start.sh`.

`backend/start.sh` includes:

- schema hash check for Prisma generation caching
- lazy Prisma client generation when schema changes
- low-memory-friendly startup choices for Render

Frontend is deployed on Netlify and should be built with the correct `VITE_API_URL` for target environment.

See `DEPLOYMENT_GUIDE.md` for deployment steps.

## Documentation Index

- `architecture.md` - architecture overview
- `features.md` - feature tracking
- `phases.md` - project roadmap and phases
- `analysis.md` - analysis and QA notes
- `ANALYTICS.md` - analytics design and usage
- `DEPLOYMENT_GUIDE.md` - deployment setup
- `monetisation.md` - cost and monetization notes

## Notes for Contributors

Backend regression tests run from `backend` after installing `requirements-test.txt`:

```bash
python -m pytest tests -q
```

The real-app integration suite is opt-in. Create a disposable local PostgreSQL
database named `vfai_security` (or another name beginning with `vfai_security`).
Set `VFAI_TEST_DATABASE_URL`, `DATABASE_URL` and `DIRECT_URL` to that same loopback
connection, then run `python -m prisma generate --schema schema.prisma` and
`python -m prisma db push --schema schema.prisma --skip-generate` before pytest.
Use a separate test cluster; these tests create and remove fixture records. They
exercise startup/shutdown, sign-in, ownership, sharing, analytics and cache reads.
Provider calls are mocked in the focused suite; production provider behavior and
deployment settings still require separate validation.

YouTube track lookups now derive their provider query from the same normalized
title/artist pair used for caching. Caller-supplied `q` is used only for uncached
free-text searches. The `yt:v2:` namespace intentionally ignores older cache rows,
so the first lookup for each track may consume provider quota after deployment.

- Keep backend route wiring centralized in `backend/main.py`
- Prefer lightweight dependencies for Render free-tier compatibility
- Avoid introducing torch-heavy packages unless deployment capacity is upgraded
- Keep analytics read endpoints token-gated when exposed publicly

## License

No explicit license file is currently present in this repository. Add one before public redistribution.
