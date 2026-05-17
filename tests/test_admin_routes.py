import uuid
import hashlib
import pytest
from fastapi.testclient import TestClient

def _admin_headers(test_app):
    from tests.conftest import admin_headers
    # Since admin_headers is a fixture, we can't call it easily here.
    # I'll implement the helper using the same logic as the fixture.
    import secrets
    from regai.auth.session import create_session
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, f"admin_{user_id}", f"admin_{user_id}@example.com", "Admin"),
    )
    db.commit()
    session_token = create_session(db, user_id)
    csrf = secrets.token_hex(16)
    db.commit()
    return {"session": session_token, "csrf": csrf, "user_id": user_id}

def _csrf_headers(client):
    csrf = str(client.cookies.get("regai_csrf"))
    return {"X-CSRF-Token": csrf}


def test_non_admin_cannot_access_upload(analyst_client):
    resp = analyst_client.get("/admin/regulations/upload")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/app"


def test_upload_form_loads(admin_client):
    resp = admin_client.get("/admin/regulations/upload")
    assert resp.status_code == 200


def test_upload_rejects_unsupported_extension(admin_client):
    resp = admin_client.post(
        "/admin/regulations/upload",
        headers=_csrf_headers(admin_client),
        data={
            "title": "Test", "regulator": "SEC", "jurisdiction": "US",
            "document_type": "rule", "source_url": "https://example.com",
            "license_note": "public",
        },
        files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
    )
    assert resp.status_code == 400


def test_upload_rejects_regulator_jurisdiction_mismatch(admin_client):
    resp = admin_client.post(
        "/admin/regulations/upload",
        headers=_csrf_headers(admin_client),
        data={
            "title": "Test", "regulator": "SEC", "jurisdiction": "EU",
            "document_type": "rule", "source_url": "https://example.com",
            "license_note": "public",
        },
        files={"file": ("test.txt", b"some content", "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_rejects_duplicate_hash_and_links_existing(admin_client, test_app):
    db = test_app.state.db
    content = b"duplicate content for hashing"
    doc_hash = hashlib.sha256(content).hexdigest()
    existing_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, document_hash, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', ?, 'indexed')",
        (existing_id, "Existing Reg", doc_hash),
    )
    db.commit()

    resp = admin_client.post(
        "/admin/regulations/upload",
        headers=_csrf_headers(admin_client),
        data={
            "title": "Duplicate", "regulator": "SEC", "jurisdiction": "US",
            "document_type": "rule", "source_url": "https://example.com",
            "license_note": "public",
        },
        files={"file": ("dup.txt", content, "text/plain")},
    )
    assert resp.status_code == 303
    assert f"/admin/regulations/{existing_id}" in resp.headers["location"]


def test_upload_creates_regulation_and_job(admin_client, test_app):
    resp = admin_client.post(
        "/admin/regulations/upload",
        headers=_csrf_headers(admin_client),
        data={
            "title": "New Reg", "regulator": "SEC", "jurisdiction": "US",
            "document_type": "rule", "source_url": "https://sec.gov/rule",
            "license_note": "public",
        },
        files={"file": ("new.txt", b"fresh content", "text/plain")},
    )
    assert resp.status_code == 303
    assert "/admin/ingestion-jobs/" in resp.headers["location"]

    db = test_app.state.db
    reg_count = db.execute("SELECT COUNT(*) as c FROM regulations WHERE title = 'New Reg'").fetchone()["c"]
    assert reg_count == 1
    job_count = db.execute("SELECT COUNT(*) as c FROM ingestion_jobs").fetchone()["c"]
    assert job_count == 1

    job = db.execute("SELECT * FROM ingestion_jobs").fetchone()
    assert job["status"] == "pending"
    assert job["regulation_id"] is not None


def test_job_detail_shows_status(admin_client, test_app):
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, "job_user", "job@example.com", "Job User"),
    )
    reg_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', 'indexed')",
        (reg_id, "Job Reg"),
    )
    job_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO ingestion_jobs (id, admin_user_id, filename, file_path, status, regulation_id) VALUES (?, ?, ?, '/tmp/test.txt', 'indexed', ?)",
        (job_id, user_id, "test.txt", reg_id),
    )
    db.commit()

    resp = admin_client.get(f"/admin/ingestion-jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.text.count("indexed") >= 1


def test_regulation_list_shows_regulations(admin_client, test_app):
    db = test_app.state.db
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, index_status) VALUES (?, ?, 'US', 'CFTC', 'guidance', 'indexed')",
        (str(uuid.uuid4()), "List Reg"),
    )
    db.commit()

    resp = admin_client.get("/admin/regulations")
    assert resp.status_code == 200
    assert "List Reg" in resp.text


def test_regulation_detail_shows_chunks(admin_client, test_app):
    db = test_app.state.db
    reg_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', 'indexed')",
        (reg_id, "Detail Reg"),
    )
    chunk_id = "hash:1:0"
    db.execute(
        "INSERT INTO regulation_chunks (id, regulation_id, document_hash, chunk_index, section_id, section_path, heading, text, token_count, char_start, char_end, block_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (chunk_id, reg_id, "hash", 0, "1", "", "", "Chunk text", 10, 0, 10, "paragraph"),
    )
    rowid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute("INSERT INTO chunks_fts(rowid, text, section_path, heading) VALUES (?, ?, ?, ?)", (rowid, "Chunk text", "", ""))
    db.commit()

    resp = admin_client.get(f"/admin/regulations/{reg_id}")
    assert resp.status_code == 200
    assert "Detail Reg" in resp.text
    assert "Chunk text" in resp.text


def test_retry_failed_job(admin_client, test_app):
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, "retry_user", "retry@example.com", "Retry User"),
    )
    reg_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', 'failed')",
        (reg_id, "Retry Reg"),
    )
    job_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO ingestion_jobs (id, admin_user_id, filename, file_path, status, regulation_id) VALUES (?, ?, ?, '/tmp/fail.txt', 'failed', ?)",
        (job_id, user_id, "fail.txt", reg_id),
    )
    db.commit()

    resp = admin_client.post(
        f"/admin/ingestion-jobs/{job_id}/retry",
        headers=_csrf_headers(admin_client),
    )
    assert resp.status_code == 303
    assert f"/admin/ingestion-jobs/{job_id}" in resp.headers["location"]

    job = dict(db.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone())
    assert job["status"] == "pending"

    reg = dict(db.execute("SELECT * FROM regulations WHERE id = ?", (reg_id,)).fetchone())
    assert reg["index_status"] == "ingesting"


def test_retry_non_failed_job_rejected(admin_client, test_app):
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, "done_user", "done@example.com", "Done User"),
    )
    reg_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', 'indexed')",
        (reg_id, "Done Reg"),
    )
    job_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO ingestion_jobs (id, admin_user_id, filename, file_path, status, regulation_id) VALUES (?, ?, ?, '/tmp/done.txt', 'indexed', ?)",
        (job_id, user_id, "done.txt", reg_id),
    )
    db.commit()

    resp = admin_client.post(
        f"/admin/ingestion-jobs/{job_id}/retry",
        headers=_csrf_headers(admin_client),
    )
    assert resp.status_code == 400


def test_require_admin_blocks_analyst(analyst_client):
    for path in ["/admin/regulations/upload", "/admin/regulations"]:
        resp = analyst_client.get(path)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/app"


def test_require_admin_blocks_unauthenticated(test_app):
    client = TestClient(test_app, follow_redirects=False)
    for path in ["/admin/regulations/upload", "/admin/regulations"]:
        resp = client.get(path)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/auth/login"


def test_upload_rejects_missing_csrf(admin_client):
    resp = admin_client.post(
        "/admin/regulations/upload",
        data={
            "title": "Test", "regulator": "SEC", "jurisdiction": "US",
            "document_type": "rule", "source_url": "https://example.com",
            "license_note": "public",
        },
        files={"file": ("test.txt", b"some content", "text/plain")},
    )
    assert resp.status_code == 403


def test_upload_rejects_wrong_csrf(admin_client):
    resp = admin_client.post(
        "/admin/regulations/upload",
        headers={"X-CSRF-Token": "wrong-token"},
        data={
            "title": "Test", "regulator": "SEC", "jurisdiction": "US",
            "document_type": "rule", "source_url": "https://example.com",
            "license_note": "public",
        },
        files={"file": ("test.txt", b"some content", "text/plain")},
    )
    assert resp.status_code == 403


def test_upload_rejects_non_english(admin_client):
    resp = admin_client.post(
        "/admin/regulations/upload",
        headers=_csrf_headers(admin_client),
        data={
            "title": "Test", "regulator": "SEC", "jurisdiction": "US",
            "document_type": "rule", "source_url": "https://example.com",
            "license_note": "public", "language": "fr",
        },
        files={"file": ("test.txt", b"some content", "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_rejects_invalid_regulator(admin_client):
    resp = admin_client.post(
        "/admin/regulations/upload",
        headers=_csrf_headers(admin_client),
        data={
            "title": "Test", "regulator": "FCA", "jurisdiction": "US",
            "document_type": "rule", "source_url": "https://example.com",
            "license_note": "public",
        },
        files={"file": ("test.txt", b"some content", "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_rejects_oversized_file(test_app):
    h = _admin_headers(test_app)
    client = TestClient(test_app, follow_redirects=False)
    client.cookies.set("regai_session", h["session"])
    client.cookies.set("regai_csrf", h["csrf"])

    test_app.state.settings.max_upload_size = 100

    resp = client.post(
        "/admin/regulations/upload",
        headers=_csrf_headers(client),
        data={
            "title": "Test", "regulator": "SEC", "jurisdiction": "US",
            "document_type": "rule", "source_url": "https://example.com",
            "license_note": "public",
        },
        files={"file": ("test.txt", b"x" * 200, "text/plain")},
    )
    assert resp.status_code == 400
    assert "too large" in resp.text.lower()
