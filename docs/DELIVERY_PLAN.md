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

- [ ] admin upload route (`POST /admin/regulations/upload`)
- [ ] file storage (`data/uploads/originals/`, `extracted/`, `normalized/`)
- [ ] SHA-256 hash dedup
- [ ] admin metadata form (title, regulator, jurisdiction, document_type, dates, source_url)
- [ ] ingestion job table + status page
- [ ] TXT/MD extractor first (defer PDF)
- [ ] normalized JSON output
- [ ] hierarchical chunker (800-1200 target, 1500 max, section-aware, 0 overlap)
- [ ] SQLite chunks + FTS5 index
- [ ] source viewer (document detail page with section anchors)
- [ ] graceful degradation: Pinecone fail → FTS-only banner

**Tests:**
- [ ] upload creates ingestion_job with pending status
- [ ] duplicate hash blocked
- [ ] chunk IDs deterministic from hash + section_id + index
- [ ] FTS returns results for indexed text
- [ ] source viewer shows metadata + text + anchors

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
