# Prodaxis WhatsApp Platform

Production-grade FastAPI service for sending and receiving WhatsApp messages
through the **Meta WhatsApp Cloud API**. Built for **Prodaxis** as a multi-tenant
Tech-Provider-ready backend that scales from a single client to a thousand without
architectural rewrites.

- Send single text and template messages
- Bulk campaigns with CSV upload, queued delivery, retries, and per-recipient tracking
- Webhook receiver with HMAC-SHA256 signature verification and async processing
- Postgres audit log of every message, status update, and webhook
- Multi-tenant data model from day one (single-tenant mode by default)
- Celery-backed background workers, Redis-backed rate limiting
- Loguru structured JSON logs, Sentry error monitoring, slowapi API rate limiting
- Containerized with Docker; deploys to Render + Supabase + Upstash on the free tier

---

## Architecture

```
                  ┌─────────────────────────────┐
                  │       Meta WhatsApp         │
                  │       Cloud API (v22)       │
                  └──────────┬──────────────────┘
                             │  HTTPS + webhooks
                             ▼
┌──────────────┐    ┌────────────────────────┐    ┌────────────────┐
│   Clients    │───▶│  FastAPI app (uvicorn) │───▶│ PostgreSQL 16   │
│ (web/admin)  │    │   - REST API           │    │  (Supabase)     │
└──────────────┘    │   - Webhook receiver   │    └────────────────┘
                    │   - Pydantic models    │            ▲
                    └─────────┬──────────────┘            │
                              │ Celery dispatch           │
                              ▼                           │
                    ┌────────────────────────┐            │
                    │  Redis (Upstash)        │           │
                    │  - Rate-limit buckets  │            │
                    │  - Celery broker       │            │
                    └─────────┬──────────────┘            │
                              │                           │
                              ▼                           │
                    ┌────────────────────────┐            │
                    │  Celery worker(s)      │────────────┘
                    │  - send_message        │
                    │  - process_campaign    │
                    │  - process_webhook     │
                    └────────────────────────┘
```

---

## Tech Stack

| Layer            | Choice                                              |
|------------------|-----------------------------------------------------|
| Language         | Python 3.11+                                        |
| Web framework    | FastAPI                                             |
| ASGI             | Uvicorn (dev) · Gunicorn + UvicornWorker (prod)     |
| ORM              | SQLAlchemy 2.0 (async)                              |
| Migrations       | Alembic                                             |
| Database         | PostgreSQL 16 (Supabase free tier)                  |
| Cache + queue    | Redis 7 (Upstash free tier)                         |
| Background jobs  | Celery 5                                            |
| HTTP client      | httpx (async, retried)                              |
| Validation       | Pydantic v2 + pydantic-settings                     |
| Logging          | Loguru (JSON in prod) + Sentry                      |
| Tests            | pytest + pytest-asyncio                             |
| Lint / format    | Ruff + Black + mypy                                 |
| Container        | Docker (multi-stage) + docker-compose               |

---

## Prerequisites

- Python 3.11 or newer
- Docker Desktop (for the local stack)
- Git
- A Meta developer account with a WhatsApp Business app + permanent system-user token
- (For deploy) Free accounts on **Supabase**, **Upstash**, **Render**, **Sentry**

---

## Quick start (local, with Docker)

```bash
git clone https://github.com/<you>/prodaxis-platform.git
cd prodaxis-platform
cp .env.example .env
# fill in META_*, DATABASE_URL leave default for compose, etc.

docker compose up --build
# wait for "Application startup complete"

# in another terminal — confirm a real send works:
docker compose exec app python -m scripts.send_test_message +919876543210
```

Browse:

- API docs: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- pgAdmin (optional): `docker compose --profile tools up -d pgadmin` → <http://localhost:5050>

---

## Quick start (local, no Docker)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                # fill it in

# Postgres + Redis must be reachable from DATABASE_URL / REDIS_URL.
alembic upgrade head
python -m scripts.seed_data

# api:
uvicorn src.main:app --reload --port 8000

# worker (separate terminal):
celery -A src.celery_app worker --loglevel=info

# beat (only if you add scheduled tasks):
celery -A src.celery_app beat --loglevel=info
```

---

## Environment variables

All config lives in `.env`. See [.env.example](.env.example) for the full list with
inline comments. Required values:

| Variable | What it is |
|---|---|
| `SECRET_KEY` | 32+ char random string. Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `DATABASE_URL` | Async Postgres URL, e.g. `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | `redis://...` or `rediss://...` (Upstash) |
| `META_APP_SECRET` | App secret from <https://developers.facebook.com> → App settings → Basic |
| `META_WABA_ID` | WhatsApp Business Account id |
| `META_PHONE_NUMBER_ID` | Production phone number id |
| `META_ACCESS_TOKEN` | Permanent system-user token |
| `META_WEBHOOK_VERIFY_TOKEN` | Any random string — must match what you paste into Meta's webhook config |
| `API_KEY` | Optional — when set, all `/messages|/templates|/campaigns|/tenants` endpoints require `X-API-Key` |
| `ENCRYPTION_KEY` | Fernet key. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `SENTRY_DSN` | Optional. When set, errors are reported. |

---

## Database migrations

```bash
alembic upgrade head            # apply all migrations
alembic revision --autogenerate -m "add foo"
alembic downgrade -1            # revert last
```

The first migration ([`alembic/versions/20260507_0001_initial.py`](alembic/versions/20260507_0001_initial.py))
creates every table, enum, and index used by the platform.

---

## Running the test suite

```bash
pip install -r requirements-dev.txt
pytest                          # all tests
pytest tests/test_health.py -v  # one file
pytest -m unit                  # unit-only
ruff check .
black --check .
mypy src
```

The default test config uses an in-memory SQLite DB and mocks every Meta call,
so tests run with **no external dependencies** (Postgres, Redis, or Meta).

---

## API reference

Once the server is running, the full interactive reference is at `/docs`. Highlights:

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/messages/send/text` | Free-form text (24h customer service window only) |
| `POST /api/v1/messages/send/template` | Approved template message (works any time) |
| `GET  /api/v1/messages` | Paginated message log with filters |
| `GET  /api/v1/messages/{id}` | One message |
| `GET  /api/v1/messages/{wa_id}/status` | Latest status by Meta wamid |
| `GET  /api/v1/templates` | List templates |
| `POST /api/v1/templates/sync` | Force a sync from Meta |
| `POST /api/v1/campaigns` | Create draft campaign |
| `POST /api/v1/campaigns/{id}/recipients/upload` | Upload CSV |
| `POST /api/v1/campaigns/{id}/start` | Start sending |
| `POST /api/v1/campaigns/{id}/pause|resume|cancel` | Lifecycle |
| `GET  /api/v1/campaigns/{id}/recipients` | Per-recipient progress |
| `GET  /api/v1/webhooks/whatsapp` | Meta verification handshake |
| `POST /api/v1/webhooks/whatsapp` | Meta event receiver |
| `GET  /api/v1/health` | Aggregate health |
| `GET  /api/v1/health/ready` | Readiness probe |
| `GET  /api/v1/health/live` | Liveness probe |
| `GET  /api/v1/tenants*` | Tenant CRUD (gated by `ENABLE_MULTI_TENANT`) |

---

## Project layout

```
prodaxis-platform/
├── alembic/                migrations
├── scripts/                init_db, seed_data, send_test_message
├── tests/                  pytest test suite
└── src/
    ├── api/v1/             FastAPI routers
    ├── services/           business logic + Meta HTTP client
    ├── models/             SQLAlchemy ORM
    ├── schemas/            Pydantic request/response
    ├── tasks/              Celery tasks
    ├── utils/              phone normalization, retry, pagination
    ├── config.py           settings (pydantic-settings)
    ├── database.py         async engine + sessionmaker
    ├── redis_client.py     async Redis pool
    ├── celery_app.py       Celery factory
    ├── logger.py           Loguru config
    ├── exceptions.py       domain errors
    ├── dependencies.py     FastAPI deps
    └── main.py             FastAPI app factory
```

---

## Deploying to Render (free tier)

1. Push the repo to GitHub.
2. Create a **PostgreSQL** project in Supabase. Copy the *Connection Pooler* URI (port 6543).
   Convert the prefix to `postgresql+asyncpg://`.
3. Create a **Redis** database in Upstash (Mumbai region). Copy the `rediss://` URL.
4. (Optional) Create a Sentry project; copy the DSN.
5. On Render → **New Web Service** → connect the GitHub repo.
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn src.main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
   - Environment: copy each variable from `.env` (set `APP_ENV=production`, `LOG_FORMAT=json`).
6. Add a **Background Worker** service for Celery:
   - Start: `celery -A src.celery_app worker --loglevel=info --concurrency=4`
7. (Optional) Add a **Background Worker** for Celery beat if you add scheduled tasks:
   - Start: `celery -A src.celery_app beat --loglevel=info`
8. After the first deploy, exec into the web service shell and run:
   ```
   alembic upgrade head
   python -m scripts.seed_data
   ```
9. Update Meta → **Configuration → Webhook**:
   - Callback URL: `https://<your-service>.onrender.com/api/v1/webhooks/whatsapp`
   - Verify token: same as `META_WEBHOOK_VERIFY_TOKEN`
   - Subscribe to: `messages`, `message_template_status_update`

You're live.

---

## Operational notes

### Rate limiting

Meta enforces per-phone-number-id and per-recipient limits. We mirror them in
[`src/services/rate_limiter.py`](src/services/rate_limiter.py) with Redis counters:

- **80 messages/sec** per phone number id (configurable via `META_MAX_MESSAGES_PER_SECOND`)
- **45 messages burst** per recipient inside a 6-second window, then back-pressure

When the limiter rejects a send, Celery retries with exponential backoff
(see [`src/tasks/send_message_task.py`](src/tasks/send_message_task.py)).

### Webhook latency

Meta requires a 200 OK within 5 seconds. The platform persists the raw event
inside the request handler, returns 200 immediately, and dispatches the
processing logic to Celery (`process_webhook_task`). If dispatch itself fails
we still return 200, log the error, and rely on a future re-delivery.

### Logging

Loguru is configured in [`src/logger.py`](src/logger.py). In production
(`APP_ENV=production` and `LOG_FORMAT=json`) every log line is a single JSON
object suitable for stdout-based log shipping. Sensitive substrings
(`access_token`, `Bearer ...`, `EAA...`, `password`, `secret`) are auto-masked
before serialization.

### Sentry

Set `SENTRY_DSN` and Sentry will receive WARNING+ events with FastAPI/Starlette
integrations enabled. PII is intentionally **not** forwarded.

### Multi-tenant mode

Every table already has `tenant_id`. To onboard a real client:

1. Set `ENABLE_MULTI_TENANT=True`.
2. `POST /api/v1/tenants` with their WABA id, phone number id, and access token.
   Tokens are encrypted at rest with the `ENCRYPTION_KEY` Fernet key.
3. Client requests pass `tenant_id` on each call (or omit it to default to the
   platform tenant).

---

## Contributing

```bash
ruff check . --fix
black .
mypy src
pytest
```

Pre-commit hooks (optional):

```bash
pip install pre-commit
pre-commit install
```

Open a PR. Branch name: `feat/<short>` or `fix/<short>`.

---

## License

MIT © Prodaxis
