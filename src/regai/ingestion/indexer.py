import json
import uuid
import traceback
from pathlib import Path
from regai.ingestion.extractors import extract_text
from regai.ingestion.normalizer import normalize
from regai.ingestion.chunker import chunk_document
from regai.ingestion.models import Chunk


def _log_audit(db, action, actor_user_id, entity_type, entity_id, metadata):
    db.execute(
        "INSERT INTO audit_logs (id, actor_user_id, action, entity_type, entity_id, metadata) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), actor_user_id, action, entity_type, entity_id, json.dumps(metadata or {})),
    )


def index_chunks(db, regulation_id: str, chunks: list[Chunk]):
    for chunk in chunks:
        db.execute(
            """INSERT INTO regulation_chunks (
                id, regulation_id, document_hash, chunk_index,
                section_id, section_path, heading, text,
                token_count, char_start, char_end, block_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                chunk.id, chunk.regulation_id, chunk.document_hash, chunk.chunk_index,
                chunk.section_id, chunk.section_path, chunk.heading, chunk.text,
                chunk.token_count, chunk.char_start, chunk.char_end, chunk.block_type,
            ),
        )
        rowid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO chunks_fts(rowid, text, section_path, heading) VALUES (?, ?, ?, ?)",
            (rowid, chunk.text, chunk.section_path, chunk.heading),
        )


def process_job(db, job_id: str, data_dir: str):
    job_row = db.execute(
        "SELECT * FROM ingestion_jobs WHERE id = ? AND status = 'pending'",
        (job_id,),
    ).fetchone()
    if not job_row:
        return
    job = dict(job_row)
    regulation_id = job["regulation_id"]
    file_path = job["file_path"]
    admin_user_id = job["admin_user_id"]
    document_hash = Path(file_path).stem

    db.execute(
        "UPDATE ingestion_jobs SET status = 'processing', started_at = datetime('now') WHERE id = ?",
        (job_id,),
    )
    db.commit()

    data_root = Path(data_dir)
    extracted_dir = data_root / "uploads" / "extracted"
    normalized_dir = data_root / "uploads" / "normalized"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    try:
        reg_row = db.execute(
            "SELECT title FROM regulations WHERE id = ?", (regulation_id,),
        ).fetchone()
        reg_title = reg_row["title"] if reg_row else ""

        raw_text = extract_text(file_path)
        extracted_path = extracted_dir / f"{document_hash}.txt"
        extracted_path.write_text(raw_text, encoding="utf-8")

        doc = normalize(raw_text, title=reg_title)
        normalized_path = normalized_dir / f"{document_hash}.json"
        normalized_path.write_text(json.dumps({
            "title": doc.title,
            "blocks": [
                {
                    "section_id": b.section_id,
                    "section_path": b.section_path,
                    "heading": b.heading,
                    "text": b.text,
                    "block_type": b.block_type,
                    "char_start": b.char_start,
                    "char_end": b.char_end,
                }
                for b in doc.blocks
            ],
        }, indent=2), encoding="utf-8")

        chunks = chunk_document(doc, document_hash, regulation_id)

        with db.transaction():
            db.execute(
                "UPDATE regulations SET extracted_text_path = ?, normalized_json_path = ? WHERE id = ?",
                (str(extracted_path), str(normalized_path), regulation_id),
            )
            old_rows = [
                r[0] for r in db.execute(
                    "SELECT rowid FROM regulation_chunks WHERE regulation_id = ?",
                    (regulation_id,),
                ).fetchall()
            ]
            for rowid in old_rows:
                db.execute("DELETE FROM chunks_fts WHERE rowid = ?", (rowid,))
            db.execute(
                "DELETE FROM regulation_chunks WHERE regulation_id = ?",
                (regulation_id,),
            )
            index_chunks(db, regulation_id, chunks)
            db.execute(
                "UPDATE regulations SET index_status = 'indexed' WHERE id = ?",
                (regulation_id,),
            )
            db.execute(
                "UPDATE ingestion_jobs SET status = 'indexed', completed_at = datetime('now') WHERE id = ?",
                (job_id,),
            )
            _log_audit(
                db, action="ingestion.completed",
                actor_user_id=admin_user_id,
                entity_type="regulation",
                entity_id=regulation_id,
                metadata={"job_id": job_id, "chunk_count": len(chunks)},
            )
    except Exception:
        try:
            db.execute(
                "UPDATE regulations SET index_status = 'failed' WHERE id = ?",
                (regulation_id,),
            )
            db.execute(
                "UPDATE ingestion_jobs SET status = 'failed', completed_at = datetime('now'), error_message = ? WHERE id = ?",
                (traceback.format_exc(), job_id),
            )
            _log_audit(
                db, action="ingestion.failed",
                actor_user_id=admin_user_id,
                entity_type="regulation",
                entity_id=regulation_id,
                metadata={"job_id": job_id, "error": traceback.format_exc()},
            )
            db.commit()
        except Exception:
            db.execute("ROLLBACK")
