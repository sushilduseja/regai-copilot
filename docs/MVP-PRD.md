# RegAI Copilot MVP PRD

## 1. Objective

Build a lightweight, production-grade regulatory copilot that helps compliance analysts create defensible first-pass impact assessments from trusted, cited regulatory sources.

Success target: reduce initial impact assessment from 3-5 days to under 2 hours for covered SEC, CFTC, and EU regulatory documents.

## 2. Decisive MVP Scope

### Included

- Curated English-language corpus from SEC, CFTC, and EUR-Lex only.
- Admin-confirmed, one-file-at-a-time ingestion.
- SQLite source of truth with FTS5 keyword search.
- Pinecone vector search.
- Hybrid retrieval with Reciprocal Rank Fusion (RRF).
- Source viewer with section/page/chunk citations.
- Source-grounded Q&A with mandatory citation validation.
- Structured impact assessments with submission snapshots.
- Manager review workflow.
- WorkOS AuthKit for authentication.
- Local SQLite authorization for roles and jurisdiction access.
- Audit log and QA interaction records.

### Excluded

- Postgres.
- Password auth.
- Automated regulator scraping.
- FCA, MAS, UK, APAC, or restricted/licensed sources.
- Batch upload.
- Celery, Redis, or separate queue infrastructure.
- Email alerts.
- Calendar, Jira, ServiceNow, or document-management integrations.
- Advanced version diff.
- Multi-tenant billing.
- Large-scale obligation extraction.
- Externalized domain authorization.

## 3. Users and Access

### Roles

- Analyst: search, view regulations, ask cited questions, create/edit own draft or revision-requested assessments, submit for review.
- Manager: analyst permissions plus review submitted assessments in accessible jurisdictions.
- Admin: all permissions plus upload corpus, manage users, manage ingestion jobs, manage audit log.

### Authentication

- WorkOS AuthKit handles authentication, email verification, MFA, and future SSO path.
- App creates local user row on first successful login.
- First authenticated user becomes Admin only if no users exist; if `BOOTSTRAP_ADMIN_EMAILS` is set, first admin must match allowlist.
- Later first-seen users default to Analyst.
- App uses opaque server-side sessions stored in SQLite.

### Authorization

- Local SQLite authorization owns role, jurisdiction access, regulation access, assessment ownership, review permission.
- Jurisdiction enum: `US`, `EU`.
- Regulator enum: `SEC`, `CFTC`, `EUR_LEX`.
- Mapping: `US -> SEC, CFTC`; `EU -> EUR-Lex`.
- Search, regulations, assessments, secondary references, and review queues are filtered by user jurisdiction.

## 4. Corpus

### Sources

- SEC: rules, proposed rules, final rules, releases, forms, staff guidance.
- CFTC: rulemakings, regulations, releases, guidance, advisories.
- EUR-Lex: EU regulations, directives, delegated acts, implementing acts, official legal text.

### Size and Topics

- Seed corpus: 100-300 regulations.
- Jurisdictions: US and EU.
- Topics: capital markets, broker-dealer, investment adviser, derivatives, market abuse, reporting, operational resilience.

### Source Rules

- Store publisher, source URL, license/reuse basis, retrieval date, document hash, original filename, file size, MIME type, and immutable original file.
- Preserve extracted text, normalized JSON, structure, page/section mapping where practical.
- Generated analysis must cite source passages.
- Every quote/snippet must show attribution.
- No claim without citation.
- No restricted sources unless user uploads licensed/customer-owned content later.

## 5. Product Navigation

Top-level navigation:

- Search
- Documents
- Assessments
- Review Queue: Manager/Admin only
- Admin: Admin only

Admin section:

- Upload Document
- Manage Corpus
- Ingestion Jobs
- Manage Users
- Audit Log

Layout: server-rendered FastAPI + Jinja2 templates with HTMX partial updates. Sidebar plus content area. Routes enforce guards server-side; hidden nav items are convenience only.

## 6. Core Workflow

1. Admin logs in through WorkOS.
2. Admin uploads one regulation file and confirms metadata.
3. Background worker extracts text, normalizes blocks, chunks text, writes SQLite/FTS5, upserts Pinecone vectors.
4. Analyst searches by concept or keyword.
5. Analyst opens source viewer and copies cited source text.
6. Analyst asks source-grounded Q&A over selected retrieved chunks/regulations.
7. Analyst creates assessment for one primary regulation and optional secondary references.
8. Analyst submits assessment; system creates immutable submission snapshot.
9. Manager reviews submitted snapshot and cited source passages.
10. Manager approves or requests revisions.
11. Audit log records user/system actions.

## 7. Functional Requirements

### 7.1 Ingestion

- Admin uploads PDF, HTML, TXT, or Markdown.
- MVP implementation should support TXT/Markdown first; PDF/HTML can follow inside same pipeline.
- Max upload size: 50MB.
- Enforce upload size via `Content-Length` when available and while streaming.
- Compute SHA-256 hash from original file bytes while streaming.
- Store files by hash:
  - `data/uploads/originals/{sha256}.{ext}`
  - `data/uploads/extracted/{sha256}.txt`
  - `data/uploads/normalized/{sha256}.json`
- Block duplicate hash by default and show existing regulation.
- Admin confirms title, regulator, jurisdiction, document type, publication date, effective date, source URL, license note, language.
- Language is English only for MVP.
- Create `ingestion_jobs` row and process through a single-worker queue.
- Statuses: `pending`, `processing`, `indexed`, `failed`.
- Regulation index statuses: `ingesting`, `indexed`, `failed`, `stale`.
- App startup recovers interrupted `processing` jobs by resetting or failing them with retry path.
- Admin can retry failed/stale indexing.

### 7.2 Normalization and Chunking

- Extractors convert raw files into `NormalizedDocument` with ordered blocks.
- Chunker consumes normalized blocks only, not raw PDF/HTML.
- Chunk boundaries:
  1. article/rule/section
  2. subsection
  3. paragraph
  4. sentence fallback only if too large
- Target chunk size: 800-1200 tokens.
- Hard max: 1500 tokens.
- Overlap: 0 for MVP.
- Chunk ID: `{document_hash}:{section_id}:{chunk_index}`.
- Required chunk metadata: regulation ID, document hash, chunk index, section ID, section path, heading, text, token count, character range, page range, source URL, regulator, jurisdiction, document type, publication date, effective date.
- Tables are kept as table blocks; large tables split by row groups.

### 7.3 Search

- Search across SEC, CFTC, and EUR-Lex corpus within user jurisdictions.
- Keyword search uses SQLite FTS5.
- Semantic search uses Pinecone.
- Retrieve top 50 chunks from FTS5 and top 50 chunks from Pinecone.
- Merge with RRF at chunk level using `k=60`.
- Fetch canonical metadata from SQLite after fusion.
- UI may group top chunks by regulation, but ranking and RAG context remain chunk-level.
- Filters: jurisdiction, regulator, document type, publication date, effective date.
- Result cards show title, regulator, jurisdiction, date, document type, section path, snippet, source link.
- Search p95 target: under 3 seconds for 300 regulations.

### 7.4 Source Viewer

- Show regulation metadata.
- Show extracted source text with section/page/chunk anchors.
- Show source URL and original file link.
- Allow copy quote plus citation.
- Citation format: `[Regulator, Rule/Section, page/chunk, source URL]`.
- Deep links must address regulation and chunk/section.

### 7.5 Cited Q&A

- Analyst selects one or more search results or regulations.
- System answers only from retrieved passages.
- Every material statement requires citation to stored chunk.
- If context is insufficient, system says answer is not supported by available sources.
- If citation validation fails, discard answer and show verification failure.
- Never show uncited AI answer.
- Store full QA interaction: user query, answer, provider, model, retrieved chunk IDs, citations, timestamps.
- Support Groq first, Nvidia second, behind provider adapter. Tests use mock provider.

### 7.6 Impact Assessments

- Each assessment has one `primary_regulation_id`.
- Secondary references use `assessment_regulations`.
- Citations use `assessment_citations`.
- Fields:
  - title: varchar(500), required
  - summary: text
  - applicability: text
  - key obligations: text
  - affected business lines: JSON array of strings
  - affected systems: JSON array of strings
  - effective date: date
  - deadline date: date
  - risk rating: low, medium, high, critical
  - implementation effort: low, medium, high
  - status: draft, submitted, revisions_requested, approved
- Status machine:
  - `draft -> submitted`
  - `submitted -> approved`
  - `submitted -> revisions_requested`
  - `revisions_requested -> submitted`
- Submitted assessments are locked for analyst edits.
- Approved assessments are terminal and read-only.
- No reassignment in MVP.
- No reject status in MVP.
- Regulation change after approval creates new assessment.
- Create immutable `assessment_versions` snapshot on every submit.

### 7.7 Manager Review

- Review Queue shows submitted assessments in manager-accessible jurisdictions.
- Sort by deadline urgency, then submitted date.
- Show primary regulation, analyst, risk, deadline, citation count.
- Manager reviews submitted snapshot side-by-side with cited source passages.
- Manager can approve or request revisions.
- Revision request requires comment.

### 7.8 Audit

- Audit log is first-class product surface.
- Actor is human user who triggered action; nullable only for system events.
- AI details go in metadata and QA interaction records.
- Action naming: `resource.verb`, past tense for completed facts.
- Required actions:
  - `auth.login_succeeded`
  - `auth.login_failed`
  - `auth.logout`
  - `user.created`
  - `user.role_changed`
  - `search.executed`
  - `regulation.viewed`
  - `qa.requested`
  - `qa.answered`
  - `assessment.created`
  - `assessment.updated`
  - `assessment.submitted`
  - `assessment.revision_requested`
  - `assessment.approved`
  - `ingestion.started`
  - `ingestion.completed`
  - `ingestion.failed`
- Audit fields: actor user, action, entity type, entity ID, metadata JSON, IP address, user agent, request ID, created timestamp.

## 8. Non-Functional Requirements

### Performance

- Search p95 under 3 seconds for 300 regulations.
- Q&A p95 under 20 seconds.
- Page load under 2 seconds for common views.
- Support 25 concurrent MVP users.

### Reliability and Degradation

- SQLite WAL enabled.
- SQLite foreign keys enabled on every connection.
- Short transactions only.
- SQLite locked retry: 50ms, 100ms, 200ms with jitter; return 503 if still locked.
- Pinecone unavailable: show FTS5 results with banner.
- FTS5 unavailable: show Pinecone results with banner.
- Both search paths unavailable: return search unavailable error.
- LLM unavailable: disable Q&A; search/source viewer remains usable.
- Citation validation failure: discard AI answer.
- Pinecone upsert failure during ingestion: mark regulation `stale`; keep FTS searchable; allow admin retry.
- Uploads blocked at 80% disk usage.

### Security

- WorkOS AuthKit for authentication.
- Server-side sessions in SQLite with opaque random session IDs.
- Cookie flags: HttpOnly, Secure in production, SameSite=Lax.
- Least-privilege role checks server-side.
- Jurisdiction checks server-side.
- HTTPS in deployed environment.
- Encrypted secrets through environment.
- No source text sent to model except retrieved passages needed for answer.
- No training-data opt-in unless explicitly configured.

### Data Integrity

- SQLite is canonical source of truth.
- Pinecone stores vectors and minimal metadata only.
- Chunk IDs deterministic.
- Reindex can rebuild Pinecone from SQLite and stored files.
- Backups cover SQLite DB and `data/uploads`.
- Forward-only SQL migrations with checksum tracking.

## 9. Architecture and Stack

### App Stack

- FastAPI
- Jinja2 templates
- HTMX
- SQLite + FTS5
- Pinecone
- WorkOS AuthKit
- Groq and Nvidia model providers
- Render deployment with persistent disk

### Project Structure

```text
src/regai/
  main.py
  config.py
  db.py
  auth/
  models/
  routes/
  services/
  ingestion/
  templates/
  static/
migrations/
tests/
data/
```

### Storage

- SQLite: users, sessions, jurisdiction grants, regulations, chunks, assessments, citations, reviews, QA interactions, audit logs, ingestion jobs, migrations.
- SQLite FTS5: chunk keyword index.
- Pinecone: chunk embeddings.
- Render persistent disk or local `data/`: original files, extracted text, normalized JSON.

### Config

Required or environment-specific variables:

- `ENVIRONMENT`
- `APP_BASE_URL`
- `DATA_DIR`
- `DATABASE_URL`
- `SECRET_KEY`
- `WORKOS_CLIENT_ID`
- `WORKOS_API_KEY`
- `WORKOS_REDIRECT_URI`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`
- at least one of `GROQ_API_KEY`, `NVIDIA_API_KEY`
- `DEFAULT_LLM_PROVIDER`

Optional:

- `BOOTSTRAP_ADMIN_EMAILS`
- `LOG_LEVEL`
- `MAX_UPLOAD_SIZE`
- `UPLOAD_WARN_DISK_USAGE_PERCENT`

Deploy config owns paths. Production must explicitly set persistent disk path, usually `DATA_DIR=/data` and `DATABASE_URL=sqlite:////data/regai.db`.

## 10. Migrations and Testing

### Migrations

- Raw numbered SQL migrations, e.g. `001_initial.sql`.
- Applied on startup and via explicit command.
- Track in `schema_migrations`.
- Store filename/version, checksum, applied timestamp.
- Forward-only. Rollback through DB/file restore, not down migrations.

### Testing

- `pytest` for unit and integration tests.
- Mock provider for RAG tests.
- Fake Pinecone client for search/indexing tests.
- External API tests marked optional.
- Critical tests:
  - deterministic chunk IDs
  - hash duplicate block
  - RRF chunk-level ranking
  - jurisdiction filtering
  - submitted assessment lock
  - manager jurisdiction guard
  - citation validation fail-closed
  - Pinecone failure fallback to FTS5
  - ingestion restart recovery

## 11. Delivery Order

### Slice 1: Walking Skeleton

- Project structure.
- Config.
- Migration runner.
- `001_initial.sql`.
- SQLite engine.
- FastAPI app.
- Base layout/nav.
- Health check.
- Audit service skeleton.
- WorkOS login/callback.
- Server-side sessions.
- First-admin bootstrap.

### Slice 2: Admin Ingestion, FTS-Only

- Admin upload.
- File storage.
- Hash dedup.
- Metadata form.
- Ingestion jobs/status.
- TXT/Markdown extractor first.
- Normalized JSON.
- Chunker.
- SQLite chunks + FTS5.
- Source viewer.

### Slice 3: Search Quality

- Search UI and filters.
- FTS results.
- Pinecone indexing/search.
- RRF fusion.
- Graceful degradation banners.
- Document/source deep links.

### Slice 4: Cited Q&A

- Provider adapter.
- Mock provider.
- Groq provider.
- RAG prompt builder.
- Citation validator.
- QA interactions.
- Fail-closed uncited answer handling.

### Slice 5: Assessments

- Assessment CRUD.
- Primary regulation link.
- Secondary regulation references.
- Citation picker.
- Assessment citations.
- State machine.
- Submission snapshots.

### Slice 6: Review and Ops

- Review queue.
- Side-by-side citation verification.
- Approve/request revisions.
- Backup/restore command or endpoint.
- Ingestion retry/recovery.
- Disk quota checks.
- Audit log UI.
- Error-path tests.

## 12. MVP Acceptance Criteria

- First WorkOS-authenticated allowed user can bootstrap Admin.
- Admin can ingest 100+ SEC/CFTC/EUR-Lex regulations from supported files.
- Duplicate original files are detected by SHA-256.
- Analyst can search and filter accessible corpus.
- Search continues with warning if either FTS5 or Pinecone fails.
- Analyst can open source text and copy citation.
- Analyst can ask cited question and receive only validated cited answer.
- Unsupported or unvalidated AI answer is not shown.
- Analyst can create assessment for one primary regulation.
- Analyst can attach secondary regulation references and chunk citations.
- Submitted assessment is locked and versioned.
- Manager can review submitted snapshot with source citations.
- Manager can approve or request revisions with comment.
- Approved assessment is terminal.
- Audit log can show actions leading to approval, including source views, QA interactions, submission, and review.
- SQLite/file backup and Pinecone reindex procedure documented and tested.

## 13. Success Metrics

- Median first-pass assessment time: under 2 hours.
- Search p95 latency: under 3 seconds.
- Q&A p95 latency: under 20 seconds.
- Q&A citation coverage: 100% of material claims.
- Manual citation spot-check accuracy: 98%+.
- Manager review time: under 30 minutes.
- Revision rate after manager review: under 15% for pilot.
