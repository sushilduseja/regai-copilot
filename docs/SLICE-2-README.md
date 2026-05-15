# Slice 2: Admin Ingestion & FTS

## What This Is

The ingestion pipeline for RegAI Copilot: admin uploads TXT/MD regulation files, the system extracts/normalizes/chunks/FTS-indexes them, and the admin can view sources with chunk anchors. Built on Slice 1's auth, session, and audit foundation.

## What's Included

| Component | What It Does |
|---|---|
| **Upload Flow** | Metadata form + streaming file upload with SHA-256 dedup, extension + size validation |
| **Extractors** | Simple text extraction from `.txt` and `.md`/`.markdown` files |
| **Normalizer** | Heading-aware paragraph normalization (preserves section paths) |
| **Chunker** | 800-1200 target token size, 1500 hard max, deterministic IDs `{hash}:{section}:{index}` |
| **FTS Indexer** | SQLite FTS5 external content table, atomic chunk replacement on retry |
| **Worker** | Single-thread polling loop, crash recovery (stuck jobs → failed on startup) |
| **Admin Routes** | 6 endpoints: upload form/submit, job detail, retry, regulation list, regulation detail with chunk anchors |
| **CSRF** | Server-generated token set as cookie + `X-CSRF-Token` header validation on all POST routes |
| **Audit** | `ingestion.started`, `ingestion.completed`, `ingestion.failed` events with full metadata |
| **Auth Guards** | `require_admin()` on all admin routes (analysts and unauthenticated users blocked) |

## Prerequisites

- Python 3.11+
- No external services (WorkOS is mocked, no Pinecone/AI yet)

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Run all tests
uv run pytest -v
```

Expected output: **48 tests passing** across 8 test files.

## What Each Test File Covers

| File | Tests | What It Verifies |
|---|---|---|
| `test_health.py` | 1 | `GET /health` returns 200 |
| `test_config.py` | 4 | Dev defaults, env overrides, prod validation, short secret key |
| `test_db.py` | 3 | Migration idempotency, checksum enforcement, WAL + fk pragmas |
| `test_audit.py` | 2 | Audit inserts with valid JSON metadata, system events allow null actor |
| `test_auth_routes.py` | 5 | Protected route redirect, invalid/expired session denied, CSRF on logout |
| `test_auth_callback.py` | 3 | First login = admin, second = analyst, allowlist blocks unauthorized |
| **`test_admin_routes.py`** | **18** | Upload CSRF rejection, extension validation, jurisdiction check, dedup, job creation, retry, regulation list/detail, oversized file rejection, non-English rejection, analyst/unauthenticated blocking |
| **`test_ingestion.py`** | **12** | TXT extraction, paragraph normalization, heading normalization, empty doc handling, chunk ID format & determinism, target & hard max enforcement, FTS index & search, full pipeline (file→FTS), pipeline failure marking, worker crash recovery |

## Manual Verification (Optional)

```bash
# 1. Copy env template
cp .env.example .env

# 2. Set dummy WorkOS credentials
echo "WORKOS_CLIENT_ID=dummy" >> .env
echo "WORKOS_API_KEY=dummy" >> .env

# 3. Start the app (worker starts automatically)
uv run uvicorn regai.main:create_app --factory --reload
```

With the app running:

- `GET /admin/regulations/upload` — upload form (redirects to login if unauthenticated)
- `POST /admin/regulations/upload` — submit a `.txt` or `.md` file with metadata
- `GET /admin/ingestion-jobs/{id}` — job progress/result
- `POST /admin/ingestion-jobs/{id}/retry` — retry a failed job
- `GET /admin/regulations` — list all uploaded regulations
- `GET /admin/regulations/{id}` — regulation detail with chunk anchors

To test the ingestion pipeline end-to-end:
1. Navigate to `http://localhost:8000/admin/regulations/upload`
2. Fill in metadata (SEC/US/rule, any title, any URL)
3. Upload a `.txt` or `.md` file
4. You'll be redirected to the job detail page — it shows `pending` → `processing` → `indexed`
5. Visit the regulation list to see the indexed document

## Project Structure (Slice 2 Additions)

```
src/regai/
├── routes/
│   └── admin.py                  # 6 admin routes with CSRF, streaming upload
├── ingestion/
│   ├── __init__.py
│   ├── extractors.py             # TXT/MD text extraction
│   ├── normalizer.py             # Heading-aware paragraph normalization
│   ├── chunker.py                # Section-aware chunking (800-1200 target)
│   ├── indexer.py                # FTS index + audit events
│   ├── worker.py                 # Single-thread polling worker + crash recovery
│   └── models.py                 # Block, NormalizedDocument, Chunk dataclasses
├── templates/
│   ├── base.html                 # (Slice 1) Base layout with sidebar nav
│   └── admin/
│       ├── upload.html           # Upload form with JS CSRF + fetch
│       ├── job_detail.html       # Job status with retry button
│       ├── regulations.html      # Regulation list table
│       └── regulation_detail.html # Source viewer with chunk anchors
└── auth/
    └── guards.py                 # require_admin() guard added
tests/
├── test_admin_routes.py          # 18 admin route tests (Upload→CSRF→size→dedup→retry→list→detail)
└── test_ingestion.py             # 12 ingestion pipeline tests (extract→normalize→chunk→index→FTS)
```

## Known Limitations (Intentional for Slice 2)

- Only `.txt`, `.md`, `.markdown` files accepted — PDF/HTML parsing deferred to future slices
- No Pinecone vector search, no hybrid search (RRF) — FTS-only search via `chunks_fts`
- No analyst-facing search UI — that's Slice 3+
- Single-threaded polling worker (1s interval) — no Celery/Redis, fine for MVP volumes
- Character offsets in chunks are approximate (calculated during normalization, not byte-accurate)
- Token estimation is crude (`len(text) // 4`) — sufficient for chunk sizing, not for token counting
- Recovers ALL stuck jobs as failed on startup (may mark jobs that were briefly `processing`)
- `db.transaction()` uses `threading.RLock` — reentrant, safe for nested calls
