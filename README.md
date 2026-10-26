# Groupor Backend — FastAPI & PostgreSQL Community Service

[![Live Site](https://img.shields.io/badge/Live%20Platform-groupor.link-17D292?style=flat-square)](https://www.groupor.link/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

Groupor Backend is an asynchronous, high-throughput REST API and data service powering community indexing, invite link resolution, spam screening, rate limiting, and reporting for [Groupor](https://www.groupor.link).

Built with **FastAPI**, **SQLAlchemy (asyncpg)**, and **PostgreSQL**, deployed with Docker on **Railway**.

---

## Architecture & Technology Stack

| Layer | Component | Description |
|:---|:---|:---|
| **API Framework** | FastAPI (ASGI / Uvicorn) | Asynchronous REST API with automatic OpenAPI validation |
| **Database** | PostgreSQL | Relational storage for groups, reports, rate limits, and audit logs |
| **ORM / Query Engine** | SQLAlchemy 2.0 (asyncio) | High-performance non-blocking query execution |
| **Moderation Engine** | Automated Trust & Safety | Keyword regex filters, phone spam detection, and quarantine pipelines |
| **Link Scraping** | Open Graph WhatsApp Scraper | Automated WhatsApp group title and avatar extraction |
| **Deployment** | Docker & Railway | Containerized deployment with automated health checks (`/healthz`) |

---

## Core API Endpoints

Interactive Swagger documentation is available locally at `/api/docs`.

### Public Directory Endpoints
- `GET /healthz` — Service healthcheck, PostgreSQL connectivity status, and memory cache diagnostics.
- `GET /api/groups` — Paginated directory listings with category, country, language, and search query filters.
- `GET /api/groups/{slug}` — Retrieve group metadata, OG tags, canonical URLs, and JSON-LD structured data.
- `GET /api/reports` — Fetch list of confirmed reported invite codes to synchronize frontend removal cache.

### Submission & Moderation Endpoints
- `POST /api/preview` — Scrapes and verifies public WhatsApp invite link metadata (title and thumbnail).
- `POST /api/groups` — Submits a single WhatsApp group link (enforces 5 submissions / 24hr IP rate-limit and Trust & Safety spam filters).
- `POST /api/groups/bulk` — Batch ingestion of up to 50 links per request (requires `X-API-Key`).
- `POST /api/reports` — Submits a user report against malicious, inactive, or abusive group invite codes.

---

## Quickstart & Local Setup

### Prerequisites
- Python 3.11+
- PostgreSQL database instance
- Docker (optional)

### Option A: Local Python Environment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mrankushsingh/groupor-backend.git
   cd groupor-backend
   ```

2. **Create and activate a virtual environment:**
   For Windows:
   ```powershell
   .venv\Scripts\activate
   ```
   For Linux/macOS:
   ```bash
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to configure your PostgreSQL credentials:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/groupor
   SITE_URL=https://www.groupor.link
   SITE_NAME=Groupor
   BULK_API_KEY=your-secure-random-key
   ```

5. **Start the API server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   Access the API at [http://localhost:8000](http://localhost:8000) and API docs at [http://localhost:8000/api/docs](http://localhost:8000/api/docs).

### Option B: Docker Compose

```bash
docker compose up --build
```

---

## Bulk Import Workflow

To seed or backfill verified WhatsApp communities:
```bash
python scripts/bulk_import_groups.py \
  --api https://your-backend.up.railway.app \
  --key YOUR_BULK_API_KEY \
  --file links.txt \
  --country India \
  --category social-friendship-community
```

---

## Contributing

Please review [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before submitting pull requests.

---

## License

This project is licensed under the [MIT License](LICENSE).
