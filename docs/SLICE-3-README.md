# Slice 3: Search Quality

## What This Is

The search layer for RegAI Copilot: keyword (FTS5), semantic (Pinecone), and hybrid (RRF fusion) search across the regulatory corpus. Analysts can search, filter, and navigate to source documents with chunk-level anchors. Built on Slice 1's auth and Slice 2's ingestion pipeline.

## What's Included

| Component | What It Does |
|---|---|
| **FTS Search** | `SearchService.search()` — SQLite FTS5 keyword search with jurisdiction enforcement, regulator/doc-type/date filters, `<mark>`-highlighted snippets |
| **Search UI** | `GET /app` — server-rendered search page with collapsible filter form, result cards, result count, clear-all button |
| **Search Audit** | `search.executed` events logged with query, result count, error, filters, IP, user-agent |
| **Deep Links** | `GET /app/documents/{regulation_id}` — analyst-safe document viewer with chunk anchors (`#chunk-{id}`). Search result titles link to `{doc_url}#chunk-{chunk_id}`. 403/404/audit on view |
| **Pinecone Indexing** | `PineconeVectorIndexService` + `FakeVectorIndexService` — batch upsert (100 vectors/batch), connectivity check on init. Failure → regulation `stale`, FTS stays searchable |
| **Semantic Search** | `SearchService.semantic_search()` — vector index query → SQLite metadata fetch. Jurisdiction enforced in SQLite. `vector_unavailable` error on failure |
| **RRF Fusion** | `SearchService.hybrid_search()` — FTS top 50 + semantic top 50 merged at chunk level with `k=60`. Chunks in both lists rank above singles. Metadata re-fetched from SQLite after fusion |
| **Graceful Degradation** | 3 paths: vector down → FTS + `vector_unavailable` banner; FTS down → semantic + `fts_unavailable` banner; both down → `search_unavailable` error |
| **Embedding** | `FakeEmbeddingProvider` (SHA-256 seeded LCG, deterministic, unit-norm) for dev. `NVIDIAEmbeddingProvider` (NIM API) for production |
| **Route Wiring** | `GET /app` falls back to FTS-only if no vector index configured; uses `hybrid_search` when Pinecone + embedding provider are available |

## Prerequisites

- Slice 1 + 2 complete (auth, ingestion working)
- Python 3.11+
- Optional: Pinecone index for semantic search (`PINECONE_API_KEY`, `PINECONE_INDEX_NAME`)
- Optional: NVIDIA API key for real embeddings (`NVIDIA_API_KEY`)
- No Pinecone/NVIDIA keys needed for tests (fake implementations used)

## Quick Start

```bash
# 1. Install dependencies (with optional extras)
pip install -e ".[pinecone]"

# 2. Run all tests
python -m pytest tests/ -v
```

Expected output: **96 tests passing** across 10 test files.

## What Each Test File Covers

| File | Tests | What It Verifies |
|---|---|---|---|
| `test_health.py` | 1 | `GET /health` returns 200 |
| `test_config.py` | 4 | Dev defaults, env overrides, prod validation, short secret key |
| `test_db.py` | 3 | Migration idempotency, checksum enforcement, WAL + fk pragmas |
| `test_audit.py` | 2 | Audit inserts with valid JSON metadata, system events allow null actor |
| `test_auth_routes.py` | 5 | Protected route redirect, invalid/expired session denied, CSRF on logout |
| `test_auth_callback.py` | 3 | First login = admin, second = analyst, allowlist blocks unauthorized |
| `test_admin_routes.py` | 18 | Upload CSRF rejection, extension validation, jurisdiction check, dedup, job creation, retry, regulation list/detail, oversized file rejection, analyst/unauthenticated blocking |
| `test_ingestion.py` | 12 | TXT extraction, normalization, chunking, FTS indexing, pipeline failure, worker crash recovery |
| **`test_search.py`** | **36** | Search page loads, FTS matching, jurisdiction filtering, malformed-query safety, XSS in snippets, empty query, filter by regulator/doc-type/date/jurisdiction, mixed filters, no-match, HTTP filter routes, jurisdiction intersection bypass, empty-string filters, date-range inversion, deep-link document route (auth/404/jurisdiction/chunk anchor), document-view audit, semantic search (metadata fetch, jurisdiction enforcement, vector failure, date filter), RRF fusion ranking, hybrid degradation (vector failure, FTS empty, both fail) |
| **`test_vector_index.py`** | **8** | Fake embedding determinism & uniqueness, fake index store/query/filters, process_job vector upsert, vector failure marks stale, no-vector-index skip |

## Manual Verification (Optional)

```bash
# 1. Copy env template
cp .env.example .env

# 2. Set dummy WorkOS and optional Pinecone/NVIDIA credentials
echo "WORKOS_CLIENT_ID=dummy" >> .env
echo "WORKOS_API_KEY=dummy" >> .env
# echo "PINECONE_API_KEY=..." >> .env   # optional
# echo "PINECONE_INDEX_NAME=..." >> .env
# echo "NVIDIA_API_KEY=..." >> .env     # optional

# 3. Start the app (worker starts automatically)
uvicorn regai.main:create_app --factory --reload
```

With the app running:

- `GET /app` — search page (redirects to login if unauthenticated)
- `GET /app?q=insider` — keyword search with result cards
- `GET /app?q=insider&j=US&reg=SEC` — filtered search
- `GET /app/documents/{id}` — document viewer with chunk anchors
- Click a result title — navigates to `#chunk-{id}` in document viewer

To test with hybrid search (requires Pinecone + NVIDIA):
1. Set `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `NVIDIA_API_KEY` in `.env`
2. Restart the app
3. Ingest a document through `/admin/regulations/upload`
4. Search at `/app?q=keyword` — results use RRF fusion

## Project Structure (Slice 3 Additions)

```
src/regai/
├── main.py                         # Route wiring: FTS-only or hybrid_search
├── routes/
│   └── app.py                      # GET /app/documents/{regulation_id} (deep links)
├── services/
│   ├── search.py                   # SearchService: search(), semantic_search(), hybrid_search()
│   └── vector_index.py             # EmbeddingProvider ABC, FakeEmbeddingProvider, NVIDIAEmbeddingProvider
│                                  # VectorIndexService ABC, FakeVectorIndexService, NoopVectorIndexService, PineconeVectorIndexService
├── ingestion/
│   ├── indexer.py                  # process_job() expanded: vector upsert hook after FTS5
│   └── worker.py                   # IngestionWorker: wires PineconeVectorIndexService + embedding provider
├── templates/
│   └── search.html                 # Search page: collapsible filters, result cards, degradation banners
│   └── document.html               # Regulation detail with chunk anchors
└── config.py                       # Settings: pinecone_api_key, pinecone_index_name, nvidia_api_key, nvidia_embedding_model
tests/
├── test_search.py                  # 38 search tests (FTS + semantic + hybrid + degradation)
└── test_vector_index.py            # 8 vector index tests (embedding + fake + process_job hook + failure)
```

## Key Design Decisions

- **Jurisdiction enforced in SQLite, not Pinecone** — The vector index stores all chunks regardless of jurisdiction. Access control happens in the SQLite `WHERE` clause during metadata fetch. This ensures that even if Pinecone metadata is wrong, no data leaks.
- **Embedding decoupled from search** — `semantic_search()` and `hybrid_search()` take pre-embedded vectors. The route handles embedding via the configured `EmbeddingProvider`. This keeps search testable without real embedding calls.
- **RRF metadata re-fetch** — After merging FTS and semantic results, `hybrid_search()` does a third SQLite query to re-fetch metadata for the RRF-reordered chunk IDs. This ensures jurisdiction is re-enforced and snippets are consistent. Three round-trips is acceptable at MVP scale (300 regs, 25 users).
- **Deterministic fake embeddings** — `FakeEmbeddingProvider` uses SHA-256 seeded LCG. Same text always produces the same vector. Different texts produce different vectors. This makes tests reproducible without external dependencies.

## Known Limitations (Intentional for Slice 3)

- **FTS snippets lost in hybrid mode** — FTS returns `<mark>`-highlighted snippets. Hybrid search discards these and re-escapes raw text. Users lose highlighting when using hybrid search. Could be fixed in RRF by preserving the FTS snippet when available (nice-to-have).
- **`FakeEmbeddingProvider` used in dev** — When `PINECONE_API_KEY` is set without `NVIDIA_API_KEY`, hash-based noise vectors are used for embedding. Semantic search quality is meaningless in this mode. Works for integration testing only.
- **No FTS/Pinecone count estimates** — Hybrid search returns `count: len(results)`, not total result count. Pagination deferred.
- **RRF parameters fixed at `k=60`** — Not configurable at runtime. Hardcoded in `hybrid_search()` per PRD §7.3.
- **No search result highlighting in semantic-only mode** — FTS5 `snippet()` function is not available for semantic-only results. Raw text preview used instead.
