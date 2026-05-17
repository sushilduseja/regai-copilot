import uuid
import pytest
from fastapi.testclient import TestClient

def _seed_regulation(db, reg_id, title, jurisdiction, regulator, chunks, doc_hash="hash"):
    db.execute(
        """INSERT INTO regulations (id, title, jurisdiction, regulator, document_type,
           publication_date, effective_date, source_url, index_status)
           VALUES (?, ?, ?, ?, 'rule', '2025-01-01', '2025-06-01', 'https://example.com/doc', 'indexed')""",
        (reg_id, title, jurisdiction, regulator),
    )
    for i, (section_id, text) in enumerate(chunks):
        chunk_id = f"{doc_hash}:{section_id}:{i}"
        db.execute(
            "INSERT INTO regulation_chunks (id, regulation_id, document_hash, chunk_index, section_id, section_path, heading, text, token_count, char_start, char_end, block_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (chunk_id, reg_id, doc_hash, i, section_id, f"Section {section_id}", f"Section {section_id}", text, len(text) // 4, 0, len(text), "paragraph"),
        )
        rowid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("INSERT INTO chunks_fts(rowid, text, section_path, heading) VALUES (?, ?, ?, ?)", (rowid, text, f"Section {section_id}", f"Section {section_id}"))


def test_search_page_loads(admin_client):
    resp = admin_client.get("/app")
    assert resp.status_code == 200
    assert "Search" in resp.text


def test_search_returns_matching_chunks(admin_client, test_app):
    db = test_app.state.db
    reg_id = str(uuid.uuid4())
    _seed_regulation(db, reg_id, "SEC Rule 10b5-1", "US", "SEC", [
        ("1", "This rule addresses insider trading and material non-public information."),
        ("2", "Trading plans must be established in good faith."),
    ])
    db.commit()

    resp = admin_client.get("/app?q=insider")
    assert resp.status_code == 200
    assert "SEC Rule 10b5-1" in resp.text


def test_search_filters_by_jurisdiction(us_client, test_app):
    db = test_app.state.db
    eu_reg_id = str(uuid.uuid4())
    _seed_regulation(db, eu_reg_id, "EU Market Abuse Regulation", "EU", "EUR_LEX", [
        ("1", "This regulation addresses market abuse and insider dealing."),
    ], doc_hash=eu_reg_id)
    us_reg_id = str(uuid.uuid4())
    _seed_regulation(db, us_reg_id, "SEC Rule 10b5-1", "US", "SEC", [
        ("1", "This rule addresses insider trading and material non-public information."),
    ])
    db.commit()

    resp = us_client.get("/app?q=insider")
    assert resp.status_code == 200
    assert "SEC Rule 10b5-1" in resp.text
    assert "EU Market Abuse Regulation" not in resp.text


def test_no_jurisdiction_returns_no_results(no_jurisdiction_client, test_app):
    db = test_app.state.db
    reg_id = str(uuid.uuid4())
    _seed_regulation(db, reg_id, "SEC Rule 10b5-1", "US", "SEC", [
        ("1", "This rule addresses insider trading."),
    ])
    db.commit()

    resp = no_jurisdiction_client.get("/app?q=insider")
    assert resp.status_code == 200
    assert "SEC Rule 10b5-1" not in resp.text


def test_special_characters_in_query_do_not_crash(admin_client, test_app):
    db = test_app.state.db
    reg_id = str(uuid.uuid4())
    _seed_regulation(db, reg_id, "SEC Rule 10b5-1", "US", "SEC", [
        ("1", "This rule addresses insider trading."),
    ])
    db.commit()

    resp = admin_client.get('/app?q=insider"')
    assert resp.status_code == 200


def test_malformed_fts_query_shows_banner(admin_client):
    resp = admin_client.get("/app?q=" + "*" * 1000)
    assert resp.status_code == 200


def test_search_service_structured_result(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    reg_id = str(uuid.uuid4())
    _seed_regulation(db, reg_id, "SEC Rule 10b5-1", "US", "SEC", [
        ("1", "This rule addresses insider trading."),
    ])
    db.commit()

    svc = SearchService(db)
    result = svc.search(user_id, "insider")
    assert result["error"] is None
    assert result["count"] == 1
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "SEC Rule 10b5-1"
    assert "insider" in result["results"][0]["snippet"]


def test_search_service_empty_query(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    result = SearchService(db).search("any_user", "")
    assert result["error"] is None
    assert result["count"] == 0
    assert result["results"] == []


def test_search_service_no_jurisdictions(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    result = SearchService(db).search("any_user", "insider")
    assert result["error"] is None
    assert result["count"] == 0
    assert result["results"] == []


def test_search_service_sanitized_query_escapes_html_in_snippet(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    reg_id = str(uuid.uuid4())
    _seed_regulation(db, reg_id, "SEC Rule", "US", "SEC", [
        ("1", "This rule mentions <script>alert('xss')</script> and insider trading."),
    ])
    db.commit()

    svc = SearchService(db)
    result = svc.search(user_id, "rule")
    assert result["count"] == 1
    snippet = result["results"][0]["snippet"]
    assert "<script>" not in snippet
    assert "&lt;script&gt;" in snippet
    assert "<mark>" in snippet


# --- Filter tests ---

def _seed_multi_regulations(db):
    regs = [
        ("SEC Rule 10b5-1", "US", "SEC", "rule", "2024-01-15", "2024-06-01", "insider trading disclosure requirements"),
        ("EU Market Abuse Reg", "EU", "EUR_LEX", "regulation", "2023-06-01", "2024-01-01", "market abuse insider dealing provisions"),
        ("CFTC Swaps Rule", "US", "CFTC", "rule", "2025-03-01", "2025-09-01", "swap execution clearing reporting"),
    ]
    ids = []
    for title, jur, reg, dtype, pub, eff, search_text in regs:
        rid = str(uuid.uuid4())
        db.execute(
            """INSERT INTO regulations (id, title, jurisdiction, regulator, document_type,
               publication_date, effective_date, source_url, index_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'https://example.com/doc', 'indexed')""",
            (rid, title, jur, reg, dtype, pub, eff),
        )
        chunk_id = f"{rid}:0:0"
        text = f"{title} {search_text}"
        db.execute(
            "INSERT INTO regulation_chunks (id, regulation_id, document_hash, chunk_index, section_id, section_path, heading, text, token_count, char_start, char_end, block_type) VALUES (?, ?, ?, 0, '1', 'Section 1', 'Section 1', ?, 10, 0, 50, 'paragraph')",
            (chunk_id, rid, rid, text),
        )
        rowid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("INSERT INTO chunks_fts(rowid, text, section_path, heading) VALUES (?, ?, 'Section 1', 'Section 1')", (rowid, text))
        ids.append(rid)
    return ids


def test_filter_by_regulator(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'EU')", (user_id,))
    _seed_multi_regulations(db)
    db.commit()

    svc = SearchService(db)
    result = svc.search(user_id, "insider", filters={"regulator": "SEC"})
    assert result["error"] is None
    assert result["count"] == 1
    assert result["results"][0]["regulator"] == "SEC"


def test_filter_by_document_type(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'EU')", (user_id,))
    _seed_multi_regulations(db)
    db.commit()

    svc = SearchService(db)
    result = svc.search(user_id, "market", filters={"document_type": "regulation"})
    assert result["error"] is None
    assert result["count"] == 1
    assert result["results"][0]["document_type"] == "regulation"
    assert result["results"][0]["regulator"] == "EUR_LEX"


def test_filter_by_date_range(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'EU')", (user_id,))
    _seed_multi_regulations(db)
    db.commit()

    svc = SearchService(db)
    result = svc.search(user_id, "swap", filters={"date_from": "2025-01-01"})
    assert result["error"] is None
    assert result["count"] == 1
    assert result["results"][0]["regulator"] == "CFTC"


def test_filter_by_jurisdictions(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'EU')", (user_id,))
    _seed_multi_regulations(db)
    db.commit()

    svc = SearchService(db)
    result = svc.search(user_id, "market", filters={"jurisdictions": ["EU"]})
    assert result["error"] is None
    assert result["count"] == 1
    assert result["results"][0]["jurisdiction"] == "EU"
    assert result["results"][0]["regulator"] == "EUR_LEX"


def test_filter_mixed(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'EU')", (user_id,))
    _seed_multi_regulations(db)
    db.commit()

    svc = SearchService(db)
    result = svc.search(user_id, "swap", filters={
        "regulator": "CFTC",
        "date_from": "2025-01-01",
    })
    assert result["error"] is None
    assert result["count"] == 1
    assert result["results"][0]["regulator"] == "CFTC"


def test_filter_no_match_returns_empty(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    _seed_multi_regulations(db)
    db.commit()

    svc = SearchService(db)
    result = svc.search(user_id, "insider", filters={"regulator": "NONEXISTENT"})
    assert result["error"] is None
    assert result["count"] == 0
    assert result["results"] == []


def test_filter_via_http_route(admin_client, test_app):
    db = test_app.state.db
    _seed_multi_regulations(db)
    db.commit()

    resp = admin_client.get("/app?q=insider&j=US&reg=SEC")
    assert resp.status_code == 200
    assert "SEC Rule 10b5-1" in resp.text
    assert "EU Market Abuse Reg" not in resp.text
    assert "CFTC Swaps Rule" not in resp.text


def test_filter_via_http_route_date_range(admin_client, test_app):
    db = test_app.state.db
    _seed_multi_regulations(db)
    db.commit()

    resp = admin_client.get("/app?q=swap&date_from=2025-01-01")
    assert resp.status_code == 200
    assert "CFTC Swaps Rule" in resp.text
    assert "SEC Rule 10b5-1" not in resp.text
    assert "EU Market Abuse Reg" not in resp.text


def test_jurisdiction_intersection_bypass(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'analyst')",
        (user_id, user_id, f"{user_id}@example.com", "Analyst"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    _seed_multi_regulations(db)
    db.commit()

    svc = SearchService(db)
    result = svc.search(user_id, "market", filters={"jurisdictions": ["EU"]})
    assert result["error"] is None
    assert result["count"] == 0
    assert result["results"] == []


def test_empty_string_filter_values_treated_as_noop(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'EU')", (user_id,))
    _seed_multi_regulations(db)
    db.commit()

    svc = SearchService(db)
    result = svc.search(user_id, "disclosure", filters={"regulator": "", "document_type": ""})
    assert result["error"] is None
    assert result["count"] == 1
    assert result["results"][0]["regulator"] == "SEC"


def test_date_to_before_date_from_returns_empty(test_app):
    from regai.services.search import SearchService
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'EU')", (user_id,))
    _seed_multi_regulations(db)
    db.commit()

    svc = SearchService(db)
    result = svc.search(user_id, "insider", filters={"date_from": "2025-01-01", "date_to": "2024-01-01"})
    assert result["error"] is None
    assert result["count"] == 0


# --- Deep link tests ---

def test_document_route_shows_regulation(admin_client, test_app):
    db = test_app.state.db
    reg_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, source_url, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', 'https://example.com/doc', 'indexed')",
        (reg_id, "SEC Rule 10b5-1"),
    )
    db.execute(
        "INSERT INTO regulation_chunks (id, regulation_id, document_hash, chunk_index, section_id, section_path, heading, text, token_count, char_start, char_end, block_type) VALUES (?, ?, 'hash', 0, '1', 'Section 1', 'Heading 1', 'This is the chunk text.', 10, 0, 20, 'paragraph')",
        (f"hash:1:0", reg_id),
    )
    db.commit()

    resp = admin_client.get(f"/app/documents/{reg_id}")
    assert resp.status_code == 200
    assert "SEC Rule 10b5-1" in resp.text
    assert "US" in resp.text


def test_document_route_requires_auth(test_app):
    db = test_app.state.db
    reg_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', 'indexed')",
        (reg_id, "SEC Rule 10b5-1"),
    )
    db.commit()
    client = TestClient(test_app, follow_redirects=False)

    resp = client.get(f"/app/documents/{reg_id}")
    assert resp.status_code == 303
    assert "/auth/login" in resp.headers.get("location", "")


def test_document_route_404(admin_client):
    resp = admin_client.get(f"/app/documents/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_document_route_jurisdiction_restricted(us_client, test_app):
    db = test_app.state.db
    reg_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, index_status) VALUES (?, ?, 'EU', 'EUR_LEX', 'regulation', 'indexed')",
        (reg_id, "EU Market Abuse Reg"),
    )
    db.commit()

    resp = us_client.get(f"/app/documents/{reg_id}")
    assert resp.status_code == 403


def test_search_result_links_to_document(admin_client, test_app):
    db = test_app.state.db
    reg_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, source_url, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', 'https://example.com/doc', 'indexed')",
        (reg_id, "SEC Rule 10b5-1"),
    )
    db.execute(
        "INSERT INTO regulation_chunks (id, regulation_id, document_hash, chunk_index, section_id, section_path, heading, text, token_count, char_start, char_end, block_type) VALUES (?, ?, 'hash', 0, '1', 'Section 1', 'Section 1', 'This rule addresses insider trading.', 10, 0, 35, 'paragraph')",
        (f"hash:1:0", reg_id),
    )
    rowid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute("INSERT INTO chunks_fts(rowid, text, section_path, heading) VALUES (?, ?, 'Section 1', 'Section 1')", (rowid, "This rule addresses insider trading."))
    db.commit()

    resp = admin_client.get("/app?q=insider")
    assert resp.status_code == 200
    assert f"/app/documents/{reg_id}#chunk-hash:1:0" in resp.text


# --- Semantic search tests ---

def test_semantic_search_returns_chunk_metadata_from_sqlite(test_app):
    from regai.services.search import SearchService
    from regai.services.vector_index import FakeVectorIndexService, ChunkVector

    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    reg_id = str(uuid.uuid4())
    _seed_regulation(db, reg_id, "SEC Rule 10b5-1", "US", "SEC", [
        ("1", "This rule addresses insider trading and material non-public information."),
    ])
    db.commit()

    chunks = db.execute(
        "SELECT id FROM regulation_chunks WHERE regulation_id = ?", (reg_id,)
    ).fetchall()
    chunk_id = chunks[0]["id"]

    vector_index = FakeVectorIndexService()
    vector_index.upsert_chunks([
        ChunkVector(id=chunk_id, values=[1.0, 0.0, 0.0], metadata={}),
    ])

    svc = SearchService(db)
    result = svc.semantic_search(user_id, vector=[1.0, 0.0, 0.0], vector_index=vector_index)

    assert result["error"] is None
    assert result["count"] == 1
    r = result["results"][0]
    assert r["chunk_id"] == chunk_id
    assert r["regulation_id"] == reg_id
    assert r["title"] == "SEC Rule 10b5-1"
    assert r["jurisdiction"] == "US"
    assert r["regulator"] == "SEC"
    assert r["snippet"] is not None


def test_semantic_search_respects_jurisdiction(test_app):
    from regai.services.search import SearchService
    from regai.services.vector_index import FakeVectorIndexService, ChunkVector

    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'analyst')",
        (user_id, user_id, f"{user_id}@example.com", "Analyst"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))

    eu_reg_id = str(uuid.uuid4())
    _seed_regulation(db, eu_reg_id, "EU Market Abuse Reg", "EU", "EUR_LEX", [
        ("1", "market abuse insider dealing provisions"),
    ], doc_hash=eu_reg_id)

    eu_chunks = db.execute(
        "SELECT id FROM regulation_chunks WHERE regulation_id = ?", (eu_reg_id,)
    ).fetchall()
    db.commit()

    vector_index = FakeVectorIndexService()
    vector_index.upsert_chunks([
        ChunkVector(id=eu_chunks[0]["id"], values=[1.0, 0.0, 0.0], metadata={}),
    ])

    svc = SearchService(db)
    result = svc.semantic_search(user_id, vector=[1.0, 0.0, 0.0], vector_index=vector_index)

    assert result["error"] is None
    assert result["count"] == 0
    assert result["results"] == []


def test_semantic_search_handles_vector_index_failure(test_app):
    from regai.services.search import SearchService

    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    db.commit()

    class _BrokenVectorIndex:
        def query(self, vector, top_k=10, filters=None):
            raise RuntimeError("Pinecone down")

    svc = SearchService(db)
    result = svc.semantic_search(user_id, vector=[1.0, 0.0, 0.0], vector_index=_BrokenVectorIndex())

    assert result["error"] == "vector_unavailable"
    assert result["count"] == 0
    assert result["results"] == []


def test_semantic_search_filters_by_date_range(test_app):
    from regai.services.search import SearchService
    from regai.services.vector_index import FakeVectorIndexService, ChunkVector

    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))

    reg_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, publication_date, effective_date, source_url, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', '2024-01-15', '2024-06-01', 'https://example.com/doc', 'indexed')",
        (reg_id, "SEC Rule 10b5-1"),
    )
    chunk_id = f"date-test:1:0"
    db.execute(
        "INSERT INTO regulation_chunks (id, regulation_id, document_hash, chunk_index, section_id, section_path, heading, text, token_count, char_start, char_end, block_type) VALUES (?, ?, 'date-test', 0, '1', 'Section 1', 'Section 1', 'insider trading disclosure requirements', 10, 0, 50, 'paragraph')",
        (chunk_id, reg_id),
    )
    db.commit()

    vector_index = FakeVectorIndexService()
    vector_index.upsert_chunks([
        ChunkVector(id=chunk_id, values=[1.0, 0.0, 0.0], metadata={"publication_date": "2024-01-15"}),
    ])

    svc = SearchService(db)
    result = svc.semantic_search(user_id, vector=[1.0, 0.0, 0.0], vector_index=vector_index,
                                 filters={"date_from": "2024-01-01", "date_to": "2024-02-01"})

    assert result["error"] is None
    assert result["count"] == 1

    result = svc.semantic_search(user_id, vector=[1.0, 0.0, 0.0], vector_index=vector_index,
                                 filters={"date_from": "2025-01-01"})
    assert result["count"] == 0


def test_rrf_fusion_merges_fts_and_semantic_results(test_app):
    from regai.services.search import SearchService
    from regai.services.vector_index import FakeVectorIndexService, ChunkVector

    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))

    both_id = "reg-both"
    _seed_regulation(db, both_id, "Both Match Reg", "US", "SEC", [
        ("1", "insider trading disclosure requirements"),
    ], doc_hash=both_id)
    fts_id = "reg-fts"
    _seed_regulation(db, fts_id, "FTS Only Reg", "US", "SEC", [
        ("1", "insider trading material non-public information"),
    ], doc_hash=fts_id)
    sem_id = "reg-sem"
    _seed_regulation(db, sem_id, "Semantic Only Reg", "US", "SEC", [
        ("1", "market abuse insider dealing provisions"),
    ], doc_hash=sem_id)
    db.commit()

    chunks = db.execute(
        "SELECT id, regulation_id FROM regulation_chunks"
    ).fetchall()
    chunk_by_reg = {r["regulation_id"]: r["id"] for r in chunks}

    vector_index = FakeVectorIndexService()
    vector_index.upsert_chunks([
        ChunkVector(id=chunk_by_reg[both_id], values=[0.9, 0.1, 0.0], metadata={}),
        ChunkVector(id=chunk_by_reg[sem_id], values=[0.8, 0.2, 0.0], metadata={}),
    ])

    svc = SearchService(db)
    result = svc.hybrid_search(
        user_id,
        query="insider",
        vector=[0.9, 0.1, 0.0],
        vector_index=vector_index,
    )

    assert result["error"] is None
    chunk_ids = [r["chunk_id"] for r in result["results"]]

    both_chunk = chunk_by_reg[both_id]
    fts_chunk = chunk_by_reg[fts_id]
    sem_chunk = chunk_by_reg[sem_id]

    assert both_chunk in chunk_ids
    assert fts_chunk in chunk_ids
    assert sem_chunk in chunk_ids

    both_idx = chunk_ids.index(both_chunk)
    fts_idx = chunk_ids.index(fts_chunk)
    sem_idx = chunk_ids.index(sem_chunk)
    assert both_idx < fts_idx, "RRF should rank FTS+semantic match above FTS-only"
    assert both_idx < sem_idx, "RRF should rank FTS+semantic match above semantic-only"


def test_hybrid_search_shows_fts_results_when_vector_fails(test_app):
    from regai.services.search import SearchService

    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    reg_id = str(uuid.uuid4())
    _seed_regulation(db, reg_id, "SEC Rule", "US", "SEC", [
        ("1", "insider trading disclosure"),
    ])
    db.commit()

    class _BrokenVector:
        def query(self, vector, top_k=10, filters=None):
            raise RuntimeError("Pinecone down")

    svc = SearchService(db)
    result = svc.hybrid_search(user_id, "insider", [1.0, 0.0, 0.0], _BrokenVector())

    assert result["error"] == "vector_unavailable"
    assert result["count"] == 1
    assert result["results"][0]["regulation_id"] == reg_id


def test_hybrid_search_shows_semantic_results_when_fts_returns_none(test_app):
    from regai.services.search import SearchService
    from regai.services.vector_index import FakeVectorIndexService, ChunkVector

    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    reg_id = str(uuid.uuid4())
    _seed_regulation(db, reg_id, "SEC Rule", "US", "SEC", [
        ("1", "insider trading disclosure"),
    ])
    db.commit()

    chunk_id = db.execute("SELECT id FROM regulation_chunks").fetchone()[0]
    vector_index = FakeVectorIndexService()
    vector_index.upsert_chunks([ChunkVector(id=chunk_id, values=[1.0, 0.0, 0.0], metadata={})])

    svc = SearchService(db)
    result = svc.hybrid_search(user_id, "zzz_nonexistent_zzz", [1.0, 0.0, 0.0], vector_index)

    assert result["error"] is None
    assert result["count"] == 1
    assert result["results"][0]["regulation_id"] == reg_id


def test_hybrid_search_returns_error_when_both_fail(test_app):
    from regai.services.search import SearchService

    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, user_id, f"{user_id}@example.com", "Admin"),
    )
    db.execute("INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, 'US')", (user_id,))
    db.execute("DROP TABLE IF EXISTS chunks_fts")
    db.commit()

    class _BrokenVector:
        def query(self, vector, top_k=10, filters=None):
            raise RuntimeError("Pinecone down")

    svc = SearchService(db)
    result = svc.hybrid_search(user_id, "insider", [1.0, 0.0, 0.0], _BrokenVector())

    assert result["error"] == "search_unavailable"
    assert result["count"] == 0


def test_document_route_logs_viewed_audit(admin_client, test_app):
    db = test_app.state.db
    reg_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', 'indexed')",
        (reg_id, "SEC Rule 10b5-1"),
    )
    db.commit()

    admin_client.get(f"/app/documents/{reg_id}")

    audit_rows = db.execute(
        "SELECT action, entity_type, entity_id, actor_user_id FROM audit_logs WHERE action = 'regulation.viewed'",
    ).fetchall()
    assert len(audit_rows) >= 1
    found = any(
        r["entity_id"] == reg_id and r["action"] == "regulation.viewed"
        for r in audit_rows
    )
    assert found
