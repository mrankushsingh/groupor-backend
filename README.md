# FastAPI + PostgreSQL SSR (production architecture)

Dynamic server-rendered Groupor pages. Group HTML is generated from PostgreSQL on request — no static HTML file per group.

## Stack

| Layer | Choice |
| --- | --- |
| Backend | FastAPI |
| Database | PostgreSQL |
| Pages | Jinja2 SSR |
| Cache | In-process TTL + `Cache-Control` headers (Redis-ready seam) |

## URLs

- `/` — home listing (paginated)
- `/group/find` — filtered search (paginated)
- `/group/{slug}` — group detail with SEO title/description/canonical/OG/JSON-LD
- `/group/addgroup` — submit form
- `/sitemap.xml` — indexable active groups
- `/robots.txt`
- `/healthz`

## Quick start

```bash
# from repo root
docker compose up --build
```

App: http://localhost:8000

### Local without Docker (API only)

1. Start Postgres and set `DATABASE_URL`.
2. From `backend/`:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Copy `backend/.env.example` to `backend/.env` and adjust.

## Environment

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://...` |
| `SITE_URL` | Canonical origin, e.g. `https://groupor.link` |
| `SITE_NAME` | Brand in titles |
| `SESSION_SECRET` | Future signed cookies / CSRF |
| `REDIS_URL` | Optional — leave empty for now |

## SEO

Each `/group/{slug}` response includes:

- HTML body with name, description, category, country, language, tags
- `<title>`, meta description, canonical
- Open Graph tags
- `application/ld+json` WebPage + BreadcrumbList
- `Cache-Control: public, max-age=120, stale-while-revalidate=600`

Sitemap lists active group URLs dynamically from Postgres.

## Redis later

`app/cache.py` exposes `build_cache(redis_url)`. Call sites use `request.app.state.cache`. When traffic needs it, implement `RedisCache` behind the same protocol — no page rewrite required.

## Deploy (Vercel + Railway)

See **[DEPLOY.md](../DEPLOY.md)** at the repo root.

- **Frontend** → Vercel (`vercel.json`, Nitro preset `vercel`)
- **Backend + Postgres** → Railway (`backend/Dockerfile`, `backend/railway.toml`)
- Set `VITE_API_URL` on Vercel to the Railway public URL
- Set `CORS_ORIGINS` on Railway to the Vercel domain
