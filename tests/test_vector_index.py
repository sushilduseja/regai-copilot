import pytest
from regai.services.vector_index import FakeEmbeddingProvider


def test_fake_embedding_provider_returns_deterministic_vectors():
    provider = FakeEmbeddingProvider(dimensions=4)
    result = provider.embed_texts(["hello world"])
    assert len(result) == 1
    assert len(result[0]) == 4
    assert all(isinstance(v, float) for v in result[0])


def test_fake_embedding_is_deterministic():
    provider = FakeEmbeddingProvider(dimensions=4)
    v1 = provider.embed_texts(["hello world"])
    v2 = provider.embed_texts(["hello world"])
    assert v1 == v2


def test_fake_embedding_differs_for_different_texts():
    provider = FakeEmbeddingProvider(dimensions=4)
    v1 = provider.embed_texts(["hello world"])
    v2 = provider.embed_texts(["goodbye world"])
    assert v1 != v2


def test_fake_vector_index_stores_and_returns_chunks():
    from regai.services.vector_index import FakeVectorIndexService, ChunkVector
    svc = FakeVectorIndexService()
    chunks = [
        ChunkVector(id="c1", values=[1.0, 0.0, 0.0], metadata={"jurisdiction": "US"}),
        ChunkVector(id="c2", values=[0.0, 1.0, 0.0], metadata={"jurisdiction": "EU"}),
    ]
    svc.upsert_chunks(chunks)
    hits = svc.query([1.0, 0.0, 0.0], top_k=5)
    assert len(hits) == 2
    assert hits[0].id == "c1"
    assert hits[0].score > hits[1].score


def test_fake_vector_index_filters():
    from regai.services.vector_index import FakeVectorIndexService, ChunkVector
    svc = FakeVectorIndexService()
    chunks = [
        ChunkVector(id="c1", values=[1.0, 0.0], metadata={"jurisdiction": "US"}),
        ChunkVector(id="c2", values=[0.0, 1.0], metadata={"jurisdiction": "EU"}),
    ]
    svc.upsert_chunks(chunks)
    hits = svc.query([1.0, 0.0], top_k=5, filters={"jurisdiction": "US"})
    assert len(hits) == 1
    assert hits[0].id == "c1"


class _FailingVectorIndexService:
    def upsert_chunks(self, chunks):
        raise RuntimeError("Pinecone connection failed")

    def query(self, vector, top_k, filters=None):
        return []


def test_process_job_calls_vector_index_upsert(tmp_path):
    import hashlib
    from regai.db import Database, run_migrations
    from regai.ingestion.indexer import process_job
    from regai.services.vector_index import FakeVectorIndexService

    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    run_migrations(db)

    data_dir = tmp_path / "data"
    upload_dir = data_dir / "uploads" / "originals"
    upload_dir.mkdir(parents=True)

    content = "This is a test document for vector indexing.\n\nIt has two paragraphs."
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    src_file = upload_dir / f"{content_hash}.txt"
    src_file.write_text(content, encoding="utf-8")

    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        ("vi-admin", "vi-sub", "vi@example.com", "VI"),
    )
    reg_id = "reg-vector-index"
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, document_hash, original_file_path, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', ?, ?, 'ingesting')",
        (reg_id, "Vector Index Test", content_hash, str(src_file)),
    )
    job_id = "job-vector-index"
    db.execute(
        "INSERT INTO ingestion_jobs (id, admin_user_id, filename, file_path, status, regulation_id) VALUES (?, 'vi-admin', 'test.txt', ?, 'pending', ?)",
        (job_id, str(src_file), reg_id),
    )
    db.commit()

    vector_index = FakeVectorIndexService()
    embedding_provider = FakeEmbeddingProvider()
    process_job(db, job_id, str(data_dir), vector_index=vector_index, embedding_provider=embedding_provider)

    reg = dict(db.execute("SELECT * FROM regulations WHERE id = ?", (reg_id,)).fetchone())
    assert reg["index_status"] == "indexed"

    hits = vector_index.query([1.0, 0.0, 0.0], top_k=5)
    assert len(hits) > 0


def test_process_job_vector_index_failure_sets_stale(tmp_path):
    import hashlib
    from regai.db import Database, run_migrations
    from regai.ingestion.indexer import process_job

    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    run_migrations(db)

    data_dir = tmp_path / "data"
    upload_dir = data_dir / "uploads" / "originals"
    upload_dir.mkdir(parents=True)

    content = "FTS succeeds but vector index fails."
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    src_file = upload_dir / f"{content_hash}.txt"
    src_file.write_text(content, encoding="utf-8")

    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        ("vi-admin-2", "vi-sub-2", "vi2@example.com", "VI2"),
    )
    reg_id = "reg-stale"
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, document_hash, original_file_path, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', ?, ?, 'ingesting')",
        (reg_id, "Stale Test", content_hash, str(src_file)),
    )
    job_id = "job-stale"
    db.execute(
        "INSERT INTO ingestion_jobs (id, admin_user_id, filename, file_path, status, regulation_id) VALUES (?, 'vi-admin-2', 'test.txt', ?, 'pending', ?)",
        (job_id, str(src_file), reg_id),
    )
    db.commit()

    vector_index = _FailingVectorIndexService()
    embedding_provider = FakeEmbeddingProvider()
    process_job(db, job_id, str(data_dir), vector_index=vector_index, embedding_provider=embedding_provider)

    reg = dict(db.execute("SELECT * FROM regulations WHERE id = ?", (reg_id,)).fetchone())
    assert reg["index_status"] == "stale"

    job = dict(db.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone())
    assert job["status"] == "indexed"

    audit = db.execute(
        "SELECT action, metadata FROM audit_logs WHERE entity_id = ? ORDER BY rowid DESC LIMIT 1",
        (reg_id,),
    ).fetchone()
    assert audit["action"] == "vector_index.failed"
    assert "Pinecone connection failed" in audit["metadata"]


def test_process_job_vector_index_skip_when_no_index(tmp_path):
    import hashlib
    from regai.db import Database, run_migrations
    from regai.ingestion.indexer import process_job

    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    run_migrations(db)

    data_dir = tmp_path / "data"
    upload_dir = data_dir / "uploads" / "originals"
    upload_dir.mkdir(parents=True)

    content = "No vector index needed."
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    src_file = upload_dir / f"{content_hash}.txt"
    src_file.write_text(content, encoding="utf-8")

    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        ("vi-admin-3", "vi-sub-3", "vi3@example.com", "VI3"),
    )
    reg_id = "reg-no-vi"
    db.execute(
        "INSERT INTO regulations (id, title, jurisdiction, regulator, document_type, document_hash, original_file_path, index_status) VALUES (?, ?, 'US', 'SEC', 'rule', ?, ?, 'ingesting')",
        (reg_id, "No VI Test", content_hash, str(src_file)),
    )
    job_id = "job-no-vi"
    db.execute(
        "INSERT INTO ingestion_jobs (id, admin_user_id, filename, file_path, status, regulation_id) VALUES (?, 'vi-admin-3', 'test.txt', ?, 'pending', ?)",
        (job_id, str(src_file), reg_id),
    )
    db.commit()

    process_job(db, job_id, str(data_dir))

    reg = dict(db.execute("SELECT * FROM regulations WHERE id = ?", (reg_id,)).fetchone())
    assert reg["index_status"] == "indexed"

    job = dict(db.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone())
    assert job["status"] == "indexed"
