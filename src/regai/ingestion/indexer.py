import json
import traceback
from pathlib import Path
from typing import Optional
from regai.ingestion.extractors import extract_text
from regai.ingestion.normalizer import normalize
from regai.ingestion.chunker import chunk_document
from regai.ingestion.models import Chunk
from regai.services.vector_index import (
    VectorIndexService,
    EmbeddingProvider,
    ChunkVector,
)
from regai.services.audit import AuditService


_TRACE_LIMIT = 2000


def _truncated_trace() -> str:
    tb = traceback.format_exc()
    if len(tb) > _TRACE_LIMIT:
        tb = tb[:_TRACE_LIMIT] + "..."
    return tb


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


def process_job(
    db,
    job_id: str,
    data_dir: str,
    vector_index: Optional[VectorIndexService] = None,
    embedding_provider: Optional[EmbeddingProvider] = None,
):
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
    audit = AuditService(db)

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
            "SELECT title, jurisdiction, regulator, document_type, publication_date, effective_date FROM regulations WHERE id = ?",
            (regulation_id,),
        ).fetchone()
        reg_title = reg_row["title"] if reg_row else ""
        reg_meta = dict(reg_row) if reg_row else {}

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
            audit.log(
                action="ingestion.completed",
                actor_user_id=admin_user_id,
                entity_type="regulation",
                entity_id=regulation_id,
                metadata={"job_id": job_id, "chunk_count": len(chunks)},
            )

        db.commit()

        if vector_index is not None and embedding_provider is not None:
            try:
                texts = [c.text for c in chunks]
                embeddings = embedding_provider.embed_texts(texts)
                vector_chunks = []
                for i, chunk in enumerate(chunks):
                    vector_chunks.append(ChunkVector(
                        id=chunk.id,
                        values=embeddings[i],
                        metadata={
                            "chunk_id": chunk.id,
                            "regulation_id": regulation_id,
                            "jurisdiction": reg_meta.get("jurisdiction", ""),
                            "regulator": reg_meta.get("regulator", ""),
                            "document_type": reg_meta.get("document_type", ""),
                            "publication_date": reg_meta.get("publication_date", "") or "",
                            "effective_date": reg_meta.get("effective_date", "") or "",
                        },
                    ))
                vector_index.upsert_chunks(vector_chunks)
                db.execute(
                    "UPDATE regulations SET index_status = 'indexed' WHERE id = ?",
                    (regulation_id,),
                )
                audit.log(
                    action="vector_index.completed",
                    actor_user_id=admin_user_id,
                    entity_type="regulation",
                    entity_id=regulation_id,
                    metadata={"job_id": job_id, "chunk_count": len(chunks)},
                )
                db.commit()
            except Exception:
                db.execute(
                    "UPDATE regulations SET index_status = 'stale' WHERE id = ? AND index_status = 'indexed'",
                    (regulation_id,),
                )
                audit.log(
                    action="vector_index.failed",
                    actor_user_id=admin_user_id,
                    entity_type="regulation",
                    entity_id=regulation_id,
                    metadata={"job_id": job_id, "error": _truncated_trace()},
                )
                db.commit()
    except Exception:
        try:
            db.execute(
                "UPDATE regulations SET index_status = 'failed' WHERE id = ?",
                (regulation_id,),
            )
            db.execute(
                "UPDATE ingestion_jobs SET status = 'failed', completed_at = datetime('now'), error_message = ? WHERE id = ?",
                (_truncated_trace(), job_id),
            )
            audit.log(
                action="ingestion.failed",
                actor_user_id=admin_user_id,
                entity_type="regulation",
                entity_id=regulation_id,
                metadata={"job_id": job_id, "error": _truncated_trace()},
            )
            db.commit()
        except Exception:
            db.execute("ROLLBACK")
