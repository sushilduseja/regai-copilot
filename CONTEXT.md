# Context

## Glossary

**Regulation** — A legal document from a regulatory body (SEC, CFTC, EUR-Lex). Has metadata: title, regulator, jurisdiction, document type, publication date, effective date, source URL.

**Chunk** — A passage extracted from a regulation document. Target 800–1200 tokens, hard max 1500. Deterministic ID: `{document_hash}:{section_id}:{chunk_index}`.

**Impact Assessment** — A structured analysis document created by an Analyst, linked to one or more regulations. States: draft → submitted → approved | revisions_requested.

**Analyst** — User role. Creates searches, asks cited questions, drafts assessments, submits for review.

**Manager** — User role. Reviews submitted assessments, verifies citations, approves or requests revisions.

**Admin** — User role. Uploads documents, manages corpus, users, roles, jurisdiction access, and reindex jobs. First authenticated WorkOS user becomes Admin if `users` table is empty (optionally gated by `BOOTSTRAP_ADMIN_EMAILS`). All later users default to Analyst.

**Jurisdiction** — Geographic/regulatory scope. Flat enum: `US`, `EU`. Users have jurisdiction-based access filtering on search, documents, and assessments. Mapping: US → SEC, CFTC; EU → EUR-Lex.

**Regulator** — The publishing body. Enum: `SEC`, `CFTC`, `EUR_LEX`. Tied to jurisdiction at the app level (SEC/CFTC require US, EUR_LEX requires EU).

**Citation** — A reference to a specific chunk with section/page attribution. Format: `[Regulator, Rule/Section, page/chunk, source URL]`. Mandatory for all material claims.

**Review** — A Manager's action on a submitted assessment. Either approves or requests revisions (with required comment).

**Corpus** — The curated collection of regulatory documents. MVP scope: SEC, CFTC, EUR-Lex. English only.

**Assessment Version** — Snapshot of assessment content at submission time. Stored in `assessment_versions` for audit integrity.

**Ingestion Job** — Background task to process an uploaded regulatory document. Statuses: pending → processing → indexed | failed. Tracked in `ingestion_jobs` table.

**QA Interaction** — A single Q&A exchange: user query, retrieved chunks, AI answer, citations. Stored in `qa_interactions` for full reconstruction. Audit log references it.

**Audit Log** — Immutable record of all user and system actions. Actor is always the human who triggered the action (nullable for system events). AI details stored in metadata.

**Normalized Document** — Intermediate representation between raw file extraction and chunking. Contains metadata and ordered blocks with section IDs, section paths, page numbers, and block types. Stored as JSON for reindexing without re-parsing.

**File Storage** — Uploaded originals stored immutably by SHA-256 hash under `data/uploads/`. Three tiers: `originals/{hash}.{ext}`, `extracted/{hash}.txt`, `normalized/{hash}.json`. Max upload 50MB.
