# RegAI Copilot MVP PRD

## 1. Objective

Build a lightweight, production-grade MVP that lets compliance analysts create defensible first-pass regulatory impact assessments from trusted, cited regulatory sources.

Success target: reduce initial impact assessment from 3-5 days to under 2 hours for covered SEC, CFTC, and EU regulatory documents.

## 2. MVP Scope

### Included

- Curated corpus from SEC, CFTC, and EUR-Lex only.
- Manual/admin-assisted document ingestion.
- Hybrid regulatory search: keyword + semantic.
- Source-grounded Q&A over selected documents.
- Citation-first source viewer.
- Structured impact assessment drafting.
- Manager review workflow.
- Basic RBAC: Analyst, Manager, Admin.
- Audit log for source access, search, AI answers, assessment edits, and review actions.

### Excluded

- Postgres.
- Automated regulator scraping.
- FCA, MAS, or other restricted/licensed sources.
- Email alerts.
- Calendar integrations.
- Jira/ServiceNow integrations.
- Advanced version diff.
- Multi-tenant billing.
- Large-scale obligation extraction.
- Auto-generated implementation tickets.

## 3. Corpus

### Sources

- US SEC: rules, proposed rules, final rules, releases, forms, staff guidance.
- US CFTC: rulemakings, regulations, releases, guidance, advisories.
- EU EUR-Lex: regulations, directives, delegated acts, implementing acts, official legal text.

### Corpus Size

- Phase 1 seed: 100-300 documents.
- Jurisdictions: US and EU.
- Topics: capital markets, broker-dealer, investment adviser, derivatives, market abuse, reporting, operational resilience.

### Source Rules

- Store source URL, publisher, license/reuse basis, retrieval date, document hash, and original file.
- Preserve original document text and structure where practical.
- Every quote/snippet must show attribution.
- Generated analysis must cite source passages.
- No claim without citation.
- No restricted sources unless user uploads licensed/customer-owned content later.

## 4. Users

### Analyst

Creates searches, asks cited questions, reviews source text, drafts assessments, submits for review.

### Manager

Reviews submitted assessments, verifies citations, comments, approves, or requests revisions.

### Admin

Uploads documents, manages corpus metadata, users, roles, jurisdiction access, and reindex jobs.

## 5. Core Workflow

1. Admin uploads/regenerates curated corpus.
2. System extracts text, chunks documents, indexes chunks.
3. Analyst searches by concept or keyword.
4. Analyst opens result, verifies source text, asks cited questions.
5. Analyst creates impact assessment from cited source material.
6. Manager reviews assessment and citations.
7. Manager approves or requests revisions.
8. System records full audit trail.

## 6. Functional Requirements

### Document Ingestion

- Upload PDF, HTML, TXT, or Markdown source files.
- Capture title, regulator, jurisdiction, document type, publication date, effective date, source URL, license note.
- Extract text into searchable chunks.
- Store immutable original file.
- Compute document hash.
- Track index status: pending, indexed, failed, stale.
- Allow admin reindex.

### Search

- Search across SEC, CFTC, and EUR-Lex corpus.
- Support keyword search via SQLite FTS5.
- Support semantic search via Pinecone.
- Merge and rerank keyword + vector results in app.
- Filters: jurisdiction, regulator, document type, publication date, effective date.
- Result cards show title, regulator, jurisdiction, date, document type, relevance, cited snippet.
- Target latency: under 3 seconds for MVP corpus.

### Source Viewer

- Show document metadata.
- Show extracted text with section/page/chunk anchors.
- Show source URL and original file link.
- Allow copy quote + citation.
- Citation format: `[Title, regulator, section/page/chunk, source URL]`.

### Cited Q&A

- Analyst selects one or more documents or search results.
- System answers only from retrieved passages.
- Every material statement includes citation.
- If retrieved context is insufficient, system says answer is not supported by available sources.
- Store prompt, retrieved chunk IDs, model, answer, citations, timestamp.
- Support Groq and Nvidia model adapters behind one interface.

### Impact Assessment

- Create assessment linked to one or more documents.
- Fields:
  - title
  - summary
  - applicability
  - key obligations
  - affected business lines
  - affected systems/processes
  - effective/deadline date
  - risk rating
  - implementation effort
  - citations
  - status
- Statuses: draft, submitted, revisions_requested, approved.
- Analyst can save draft and submit.
- Submitted assessments become read-only except revision flow.

### Manager Review

- Queue of submitted assessments.
- Side-by-side assessment and cited source passages.
- Manager can comment, request revisions, or approve.
- Store decision, comments, actor, timestamp.

### RBAC

- Analyst: search, Q&A, create/edit own drafts, submit.
- Manager: analyst permissions plus review/approve.
- Admin: all permissions plus corpus/user management.
- Jurisdiction access filter applies to search, docs, and assessments.

### Audit

Log:

- login/logout
- document view
- search query
- Q&A request/response metadata
- assessment create/edit/submit
- review comment/status change
- admin ingestion/reindex

Audit entries must include actor, action, entity, timestamp, IP/session ID where available.

## 7. Non-Functional Requirements

### Performance

- Search p95 under 3 seconds for 300 docs.
- Q&A p95 under 20 seconds.
- Page load under 2 seconds for common views.
- Support 25 concurrent MVP users.

### Reliability

- SQLite WAL enabled.
- Short transactions only.
- Background reindex retries for Pinecone failures.
- If Pinecone unavailable, keyword search remains usable.
- If model API unavailable, search/source viewer remains usable.

### Security

- Password auth or enterprise SSO-ready abstraction.
- HTTPS in deployed env.
- Encrypted secrets.
- Least-privilege role checks server-side.
- No source text sent to model except retrieved passages needed for answer.
- No training-data opt-in unless explicitly configured.

### Data Integrity

- SQLite is source of truth.
- Pinecone stores vector IDs and metadata only.
- Chunk IDs deterministic from document hash + chunk position.
- Reindex can rebuild Pinecone from SQLite/files.
- Backups cover SQLite DB and original files.

## 8. Architecture

### Storage

- SQLite: users, roles, docs, chunks, citations, assessments, reviews, audit logs, ingestion jobs.
- SQLite FTS5: keyword index over chunks.
- Pinecone: vector index over chunk embeddings.
- Local/object file storage: original docs and extracted text artifacts.

### AI

- Embedding model: configurable; store model and dimension per index.
- LLM provider: Groq and Nvidia through provider adapter.
- RAG policy: cite-only, conservative, source-bounded.

### App Services

- Ingestion service.
- Search service.
- RAG answer service.
- Assessment service.
- Review service.
- Audit service.
- Admin service.

## 9. MVP Acceptance Criteria

- Admin can load 100+ SEC/CFTC/EUR-Lex docs.
- Analyst can search and filter corpus.
- Analyst can open source text and copy citation.
- Analyst can ask cited question and receive answer with source links.
- Unsupported answer returns explicit "not supported by available sources."
- Analyst can create and submit impact assessment.
- Manager can review, comment, approve, or request revisions.
- Audit log captures critical user and AI actions.
- Pinecone outage does not break keyword search.
- SQLite backup/reindex procedure documented and tested.

## 10. Success Metrics

- Median first-pass assessment time: under 2 hours.
- Search p95 latency: under 3 seconds.
- Q&A citation coverage: 100% of material claims.
- Manual citation spot-check accuracy: 98%+.
- Manager review time: under 30 minutes.
- Revision rate after manager review: under 15% for pilot.

## 11. Delivery Phases

### Phase 1A: Foundation

- SQLite schema.
- Auth/RBAC.
- Admin upload.
- Text extraction/chunking.
- SQLite FTS5.
- Pinecone indexing.
- Basic search UI/API.

### Phase 1B: Citation Product

- Source viewer.
- Copy quote/citation.
- Cited Q&A.
- Provider adapters for Groq/Nvidia.
- Audit logging.

### Phase 1C: Assessment Workflow

- Impact assessment CRUD.
- Submit/review/approve flow.
- Side-by-side citation verification.
- Backup/reindex runbook.
- Pilot eval set.

## 12. Decisive MVP Build Choices

- Use SQLite, not Postgres.
- Use Pinecone only for vectors.
- Keep SQLite canonical for all business data.
- Use manual/admin ingestion, not scraping.
- Use SEC, CFTC, and EUR-Lex only.
- Make citations mandatory.
- Build review workflow before advanced extraction.
- Prefer source viewer + cited answer over autonomous obligation extraction.
- Ship fewer features with audit-grade traceability.
