import json
import hashlib
from pathlib import Path
import pytest
from regai.ingestion.extractors import extract_text
from regai.ingestion.normalizer import normalize
from regai.ingestion.chunker import chunk_document, estimate_tokens
from regai.ingestion.indexer import process_job
from regai.ingestion.worker import IngestionWorker
from regai.db import Database, run_migrations


SAMPLE_TXT = "This is paragraph one.\n\nThis is paragraph two.\n\nThis is paragraph three."
SAMPLE_MD = "# Title\n\n## Section 1\n\nSection one content.\n\n## Section 2\n\nSection two content."
REGULATION_ID = "reg-123"
DOC_HASH = "a" * 64


def test_extract_txt(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text(SAMPLE_TXT, encoding="utf-8")
    text = extract_text(str(f))
    assert text == SAMPLE_TXT


def test_normalize_paragraphs():
    doc = normalize(SAMPLE_TXT, title="Test Doc")
    assert doc.title == "Test Doc"
    assert len(doc.blocks) == 3
    assert doc.blocks[0].text == "This is paragraph one."
    assert doc.blocks[1].text == "This is paragraph two."


def test_normalize_md_headings():
    doc = normalize(SAMPLE_MD, title="MD Doc")
    assert len(doc.blocks) == 2
    assert doc.blocks[0].section_id == "0"
    assert doc.blocks[0].heading == "Section 1"
    assert doc.blocks[1].section_id == "0"
    assert doc.blocks[1].heading == "Section 2"


def test_normalize_empty():
    doc = normalize("", title="Empty")
    assert len(doc.blocks) == 1
    assert doc.blocks[0].text == ""


def test_chunk_id_format():
    doc = normalize("Paragraph one.\n\nParagraph two.", title="Test")
    chunks = chunk_document(doc, DOC_HASH, REGULATION_ID)
    for c in chunks:
        parts = c.id.split(":")
        assert len(parts) == 3
        assert parts[0] == DOC_HASH
        assert c.regulation_id == REGULATION_ID


def test_chunk_id_deterministic():
    doc = normalize("Hello world.\n\nGoodbye world.", title="Test")
    c1 = chunk_document(doc, DOC_HASH, REGULATION_ID)
    c2 = chunk_document(doc, DOC_HASH, REGULATION_ID)
    assert [c.id for c in c1] == [c.id for c in c2]
    assert [c.text for c in c1] == [c.text for c in c2]
    for c in c1:
        assert c.id == f"{DOC_HASH}:{c.section_id}:{c.chunk_index}"


def test_chunk_respects_target():
    para = " ".join(["word"] * 300)
    text = "\n\n".join(para for _ in range(20))
    doc = normalize(text, title="Big")
    chunks = chunk_document(doc, DOC_HASH, REGULATION_ID)
    for c in chunks:
        assert c.token_count <= 1500, f"Chunk {c.id} has {c.token_count} tokens (max 1500)"


def test_chunk_respects_hard_max():
    big_block = "hello " * 3000
    text = f"Small intro.\n\n{big_block}\n\nSmall outro."
    doc = normalize(text, title="HardMax")
    chunks = chunk_document(doc, DOC_HASH, REGULATION_ID)
    for c in chunks:
        assert c.token_count <= 1500, f"Chunk {c.id} has {c.token_count} tokens (max 1500)"


def test_index_and_fts(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    run_migrations(db)
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', 'ingesting')",
        (REGULATION_ID, "Test Reg"),
    )
    db.commit()

    doc = normalize("This is a unique searchable phrase for FTS testing.", title="SearchTest")
    chunks = chunk_document(doc, DOC_HASH, REGULATION_ID)
    from regai.ingestion.indexer import index_chunks
    with db.transaction():
        index_chunks(db, REGULATION_ID, chunks)

    row = db.execute(
        "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?", ("searchable",),
    ).fetchone()
    assert row is not None
    db.close()


def test_full_pipeline(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    run_migrations(db)

    data_dir = tmp_path / "data"
    upload_dir = data_dir / "uploads" / "originals"
    upload_dir.mkdir(parents=True)

    content = "This is the full pipeline test document.\n\nIt has two paragraphs."
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    src_file = upload_dir / f"{content_hash}.txt"
    src_file.write_text(content, encoding="utf-8")

    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        ("pipeline-admin", "pipeline-sub", "pipeline@example.com", "Pipeline"),
    )
    reg_id = "reg-pipeline"
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, document_hash, original_file_path, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', ?, ?, 'ingesting')",
        (reg_id, "Pipeline Test", content_hash, str(src_file)),
    )
    job_id = "job-pipeline"
    db.execute(
        "INSERT INTO ingestion_jobs (id, admin_user_id, filename, file_path, status, regulation_id) VALUES (?, 'pipeline-admin', ?, ?, 'pending', ?)",
        (job_id, "test.txt", str(src_file), reg_id),
    )
    db.commit()

    process_job(db, job_id, str(data_dir))

    reg = dict(db.execute("SELECT * FROM regulations WHERE id = ?", (reg_id,)).fetchone())
    assert reg["index_status"] == "indexed"

    job = dict(db.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone())
    assert job["status"] == "indexed"

    chunk_rows = db.execute("SELECT id FROM regulation_chunks WHERE regulation_id = ?", (reg_id,)).fetchall()
    assert len(chunk_rows) > 0

    fts_row = db.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?", ("pipeline",)).fetchone()
    assert fts_row is not None

    assert Path(str(reg["extracted_text_path"])).exists()
    assert Path(str(reg["normalized_json_path"])).exists()

    extracted = Path(str(reg["extracted_text_path"])).read_text(encoding="utf-8")
    assert "full pipeline" in extracted
    db.close()


def test_pipeline_failure_marks_failed(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    run_migrations(db)

    data_dir = tmp_path / "data"
    upload_dir = data_dir / "uploads" / "originals"
    upload_dir.mkdir(parents=True)

    content = "Some content"
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    src_file = upload_dir / f"{content_hash}.txt"
    src_file.write_text(content, encoding="utf-8")

    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        ("fail-admin", "fail-sub", "fail@example.com", "Fail"),
    )
    reg_id = "reg-fail"
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, document_hash, original_file_path, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', ?, ?, 'ingesting')",
        (reg_id, "Fail Test", content_hash, str(src_file)),
    )
    job_id = "job-fail"
    db.execute(
        "INSERT INTO ingestion_jobs (id, admin_user_id, filename, file_path, status, regulation_id) VALUES (?, 'fail-admin', 'test.txt', '/nonexistent/path.txt', 'pending', ?)",
        (job_id, reg_id),
    )
    db.commit()

    process_job(db, job_id, str(data_dir))

    reg = dict(db.execute("SELECT * FROM regulations WHERE id = ?", (reg_id,)).fetchone())
    assert reg["index_status"] == "failed"

    job = dict(db.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone())
    assert job["status"] == "failed"
    assert job["error_message"] is not None
    db.close()


def test_worker_recovery(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    run_migrations(db)

    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        ("stuck-admin", "stuck-sub", "stuck@example.com", "Stuck"),
    )
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, document_hash, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', ?, 'ingesting')",
        ("reg-stuck", "Stuck", "hash-stuck"),
    )
    db.execute(
        "INSERT INTO ingestion_jobs (id, admin_user_id, filename, file_path, status, regulation_id) VALUES (?, 'stuck-admin', 'stuck.txt', '/stuck.txt', 'processing', ?)",
        ("job-stuck", "reg-stuck"),
    )
    db.commit()

    from regai.config import Settings
    settings = Settings(_env_file=None)
    settings.database_url = f"sqlite:///{db_path}"
    settings.data_dir = str(tmp_path / "data")

    worker = IngestionWorker(settings)
    worker._recover_stuck_jobs()

    job = dict(db.execute("SELECT * FROM ingestion_jobs WHERE id = ?", ("job-stuck",)).fetchone())
    assert job["status"] == "failed"

    reg = dict(db.execute("SELECT * FROM regulations WHERE id = ?", ("reg-stuck",)).fetchone())
    assert reg["index_status"] == "failed"
    db.close()
