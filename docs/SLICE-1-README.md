# Slice 1: Walking Skeleton

## What This Is

The foundational layer of RegAI Copilot: a working FastAPI application with authentication, database, audit logging, and protected routes. No UI yet — just the backbone that all future slices build on.

## What's Included

| Component | What It Does |
|---|---|
| **Config** | Dev defaults, production validation (fails fast if secrets missing) |
| **Database** | Thread-safe SQLite wrapper (WAL mode, foreign keys ON) |
| **Migrations** | Raw SQL runner with checksum enforcement and idempotent reruns |
| **Auth** | WorkOS login/callback, server-side sessions (opaque token + SHA-256 hash in DB) |
| **Sessions** | Create, validate, revoke. Checks expiration, revocation, and `is_active` |
| **Bootstrap** | First login = admin (optionally allowlist-gated). Later logins = analyst |
| **Audit** | Immutable log of all auth events with actor attribution |
| **Guards** | Protected routes redirect unauthenticated requests to `/auth/login` |
| **CSRF** | Double-submit token pattern on POST `/auth/logout` |

## Prerequisites

- Python 3.11+
- No external services needed for testing (WorkOS is mocked)

## Quick Start

```bash
# 1. Create virtual environment and install dependencies
uv sync

# 2. Run all Slice 1 tests
uv run pytest -v
```

Expected output: **18 tests passing** across 6 test files.

> **Note:** `uv sync` reads `pyproject.toml` and `uv.lock` to create a reproducible environment. If you don't have `uv`, install it: `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Manual Verification (Optional)

If you want to run the app locally and test the auth flow:

```bash
# 1. Copy env template
cp .env.example .env

# 2. Set dummy WorkOS credentials (won't be called in manual testing)
echo "WORKOS_CLIENT_ID=dummy" >> .env
echo "WORKOS_API_KEY=dummy" >> .env

# 3. Start the app
uv run uvicorn regai.main:create_app --factory --reload
```

Expected output: **18 tests passing** across 6 test files.

## What Each Test File Covers

| File | Tests | What It Verifies |
|---|---|---|
| `test_health.py` | 1 | `GET /health` returns 200 with `{"status": "ok"}` |
| `test_config.py` | 4 | Dev defaults load, env overrides work, production fails without secrets, short secret key rejected |
| `test_db.py` | 3 | Migrations apply idempotently, checksum tampering detected, WAL + foreign_keys enabled |
| `test_audit.py` | 2 | Audit entries insert correctly with valid JSON metadata, system events allow null actor |
| `test_auth_routes.py` | 5 | Protected route redirects, invalid session denied, expired session denied, logout requires CSRF, CSRF mismatch denied |
| `test_auth_callback.py` | 3 | First login creates admin with US+EU jurisdictions, second login creates analyst with no jurisdictions, allowlist blocks unauthorized |

## Manual Verification (Optional)

If you want to run the app locally and test the auth flow:

```bash
# 1. Copy env template
cp .env.example .env

# 2. Set dummy WorkOS credentials (won't be called in manual testing)
echo "WORKOS_CLIENT_ID=dummy" >> .env
echo "WORKOS_API_KEY=dummy" >> .env

# 3. Start the app
uvicorn regai.main:create_app --factory --reload
```

- Visit `http://localhost:8000/health` → `{"status":"ok"}`
- Visit `http://localhost:8000/app` → redirects to `/auth/login` → redirects to WorkOS
- Visit `http://localhost:8000/auth/login` → redirects to WorkOS authorization URL

## Project Structure (Slice 1 Only)

```
regai-copilot/
├── pyproject.toml
├── .env.example
├── render.yaml
├── migrations/
│   └── 001_initial.sql          # 17 tables, indices, FTS5
├── src/
│   └── regai/
│       ├── __init__.py
│       ├── main.py              # FastAPI app factory
│       ├── config.py            # Settings + production validation
│       ├── db.py                # Database wrapper + migration runner
│       ├── auth/
│       │   ├── __init__.py
│       │   ├── session.py       # Token generation, hashing, CRUD
│       │   └── guards.py        # require_auth() guard
│       ├── routes/
│       │   ├── __init__.py
│       │   └── auth.py          # Login, callback, logout
│       ├── services/
│       │   ├── __init__.py
│       │   └── audit.py         # AuditService
│       ├── templates/
│       │   └── base.html        # Base layout with sidebar
│       └── static/
└── tests/
    ├── test_health.py
    ├── test_config.py
    ├── test_db.py
    ├── test_audit.py
    ├── test_auth_routes.py
    └── test_auth_callback.py
```

## Known Limitations (Intentional for Slice 1)

- No browser UI — just API endpoints and redirects
- WorkOS integration is mocked in tests (no real credentials needed)
- No ingestion, search, or assessment features (those are Slice 2+)
- `render.yaml` has hardcoded `WORKOS_REDIRECT_URI` (acceptable for single prod service)
- `auth/workos.py` not yet extracted (WorkOS logic is inline in `routes/auth.py`)
