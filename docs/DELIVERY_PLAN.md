# RegAI Copilot — Delivery Plan

## Tech Stack

- **Backend/UI:** FastAPI + Jinja2 + HTMX
- **DB:** SQLite with WAL, stored on Render persistent disk
- **Keyword search:** SQLite FTS5
- **Vector search:** Pinecone
- **LLM:** Groq (primary) + Nvidia (fallback) behind provider adapter
- **Auth:** WorkOS AuthKit (authn) + local SQLite authz
- **Files:** Render persistent disk for MVP; object storage later
- **Jobs:** in-app admin-triggered ingestion/reindex first; background worker later
- **Deploy:** Render paid web service + persistent disk
- **Migrations:** Raw SQL, forward-only, checksum-tracked
- **Testing:** pytest + httpx TestClient, mock providers, fake Pinecone

## Project Structure

```
regai-copilot/
├── docs/
├── src/
│   └── regai/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── db.py
│       ├── auth/
│       │   ├── workos.py
│       │   ├── session.py
│       │   └── guards.py
│       ├── models/
│       ├── routes/
│       │   ├── auth.py
│       │   ├── search.py
│       │   ├── documents.py
│       │   ├── assessments.py
│       │   ├── review.py
│       │   └── admin.py
│       ├── services/
│       │   ├── audit.py
│       │   ├── search.py
│       │   ├── rag.py
│       │   ├── assessment.py
│       │   ├── review.py
│       │   └── providers.py
│       ├── ingestion/
│       │   ├── extractors.py
│       │   ├── chunker.py
│       │   └── indexer.py
│       ├── templates/
│       │   ├── base.html
│       │   ├── auth/
│       │   ├── search/
│       │   ├── documents/
│       │   ├── assessments/
│       │   ├── review/
│       │   └── admin/
│       └── static/
├── migrations/
├── tests/
├── data/
├── pyproject.toml
├── .env.example
└── render.yaml
```

## Slice 1: Walking Skeleton

- [x] project structure
- [x] config (dev defaults, production validation)
- [x] migration runner (raw SQL, checksum-tracked, idempotent)
- [x] `001_initial.sql` — all 14 tables, indices, FTS5
- [x] SQLite engine (WAL, foreign_keys=ON)
- [x] FastAPI app
- [x] health check endpoint
- [x] audit service skeleton
- [x] WorkOS login/callback
- [x] server-side sessions in SQLite
- [x] first-admin bootstrap (allowlist-gated)
- [x] protected route guard (redirects to `/auth/login`)
- [x] session validation (invalid/expired/revoked denied)

**Tests:** 18 passing

## Slice 2: Admin Ingestion, FTS-Only

### Design

Admin uploads a TXT/MD regulation file through a `GET + POST` form. On POST:
1. Require admin role.
2. Validate extension/MIME/size (TXT/MD only, max 50MB).
3. Stream to temp file, compute SHA-256.
4. If duplicate hash exists: delete temp, redirect to existing regulation.
5. Move to `data/uploads/originals/{hash}.{ext}`.
6. Create `regulations` row with `index_status=ingesting`.
7. Create `ingestion_jobs` row with `status=pending`.
8. Enqueue job ID for single in-process worker.
9. Redirect to `/admin/ingestion-jobs/{job_id}`.

Single worker processes the queue (started at app startup):
```
pending → processing
  extract TXT/MD → write extracted/{hash}.txt
  normalize blocks → write normalized/{hash}.json
  chunk (800-1200 target, 1500 max, section-aware, 0 overlap)
  insert chunks + chunks_fts rows
  regulation.index_status = indexed
  job.status = indexed
failure → job.status=failed, regulation.index_status=failed
```

All multi-write steps use `db.transaction()`. No partial ingestion state.

### Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/regulations/upload` | Metadata + file form |
| POST | `/admin/regulations/upload` | Accept upload, create job |
| GET | `/admin/ingestion-jobs/{id}` | Job status detail |
| POST | `/admin/ingestion-jobs/{id}/retry` | Retry failed job |
| GET | `/admin/regulations` | Regulation list |
| GET | `/admin/regulations/{id}` | Source viewer with metadata + chunk anchors |

### Metadata

**Required:** `title`, `regulator` (SEC|CFTC|EUR_LEX), `jurisdiction` (US|EU), `document_type`, `source_url`, `license_note`, `language=en`, `file`.

**Optional:** `publication_date`, `effective_date`.

**Validation:**
- `SEC`/`CFTC` → `US`, `EUR_LEX` → `EU`.
- TXT/MD only (Slice 2).
- Max 50MB.
- English only.

### Checksum / Deterministic IDs

- SHA-256 hash computed from original file bytes during streaming upload.
- Dedup: if hash exists, reject before creating regulation/job (no short-lived rejected job).
- Chunk ID: `{document_hash}:{section_id}:{chunk_index}`.

### Not In Slice 2

PDF/HTML extraction, Pinecone, hybrid search/RRF, analyst search UI, Q&A, assessments, batch upload.

- [ ] `require_admin` guard in `src/regai/auth/guards.py`
- [ ] `src/regai/ingestion/` package (extractors, normalizer, chunker, indexer, worker)
- [ ] `src/regai/routes/admin.py` — all 6 routes
- [ ] templates: `admin/upload.html`, `admin/job_detail.html`, `admin/regulations.html`, `admin/regulation_detail.html`
- [ ] register admin router + worker startup in `main.py`
- [ ] No new migration needed — `001_initial.sql` already has `regulations`, `regulation_chunks`, `chunks_fts`, `ingestion_jobs`

**Tests:**
- [ ] Non-admin cannot access upload.
- [ ] Upload form loads for admin.
- [ ] Upload rejects unsupported extension.
- [ ] Upload rejects regulator/jurisdiction mismatch.
- [ ] Upload rejects duplicate SHA-256 and links existing regulation.
- [ ] Upload creates `regulations` + `ingestion_jobs`.
- [ ] Worker extracts TXT/MD and writes extracted + normalized files.
- [ ] Chunk IDs deterministic: `{hash}:{section_id}:{index}`.
- [ ] Chunk target/hard max respected for normal text.
- [ ] FTS returns expected chunk for indexed term.
- [ ] Failed extraction marks job/regulation failed.
- [ ] Source viewer shows metadata + chunk anchors.
- [ ] Retry failed job works.

## Slice 3: Search Quality

- [ ] search UI with filters (jurisdiction, regulator, document_type, date range)
- [ ] FTS search results display
- [ ] Pinecone indexing integration
- [ ] Pinecone vector search
- [ ] RRF fusion (chunk-level, k=60)
- [ ] metadata boosts (exact title/rule match +20%, same regulator +10%)
- [ ] graceful degradation banners (Pinecone fail, FTS fail, both fail)
- [ ] document/source deep links from results

**Tests:**
- [ ] RRF ranks chunk-level results correctly
- [ ] Pinecone failure falls back to FTS with banner
- [ ] jurisdiction filter blocks inaccessible docs
- [ ] metadata boosts applied after RRF

## Slice 4: Cited Q&A

- [ ] provider adapter interface
- [ ] mock provider for tests
- [ ] Groq provider (OpenAI-compatible)
- [ ] Nvidia provider (after Groq works)
- [ ] RAG prompt builder (source-bounded, cite-only)
- [ ] citation validator (rejects unsupported claims)
- [ ] `qa_interactions` table
- [ ] fail-closed uncited answer handling
- [ ] Q&A UI with source citations

**Tests:**
- [ ] retrieval returns expected chunks
- [ ] prompt builder includes only allowed chunks
- [ ] citation validator rejects unsupported claims
- [ ] unsupported answer returns explicit message
- [ ] Pinecone failure → FTS-only Q&A still works

## Slice 5: Assessments

- [ ] assessment CRUD (create, read, update, delete)
- [ ] primary regulation link
- [ ] secondary regulation references (`assessment_regulations`)
- [ ] citation picker (select chunks from search/source)
- [ ] `assessment_citations` table
- [ ] state machine: draft → submitted → approved | revisions_requested
- [ ] submission snapshots (`assessment_versions`)
- [ ] submitted assessments locked (no edits until manager acts)
- [ ] approved assessments terminal (read-only)

**Tests:**
- [ ] analyst can create and edit draft
- [ ] submitted assessment locked for analyst
- [ ] manager can approve/request revisions
- [ ] revision_requested re-opens for analyst
- [ ] approved assessment cannot be reopened
- [ ] assessment version created on each submit

## Slice 6: Review, Ops, Hardening

- [ ] manager review queue (submitted assessments, sorted by deadline)
- [ ] side-by-side citation verification
- [ ] approve/request revisions with required comment
- [ ] backup endpoint (SQLite `.backup` to disk/object storage)
- [ ] ingestion retry/recovery (failed jobs, stale regulations)
- [ ] disk quota checks (block uploads at 80%)
- [ ] audit log UI (filterable by action, entity, date)
- [ ] ingestion job recovery on app restart
- [ ] error-path tests (SQLite lock timeout, model timeout, missing citations)

**Tests:**
- [ ] review queue shows only submitted assessments
- [ ] manager cannot approve inaccessible jurisdiction
- [ ] backup creates valid SQLite backup
- [ ] disk full blocks upload with clear error
- [ ] audit log captures all critical actions
