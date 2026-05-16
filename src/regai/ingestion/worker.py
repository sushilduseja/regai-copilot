import time
import threading
from regai.db import Database
from regai.ingestion.indexer import process_job
from regai.services.vector_index import (
    PineconeVectorIndexService,
    NVIDIAEmbeddingProvider,
)


POLL_INTERVAL = 1.0


class IngestionWorker:
    def __init__(self, settings):
        self._settings = settings
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._vector_index = None
        self._embedding_provider = None
        self._setup_services()

    def _setup_services(self):
        if self._settings.pinecone_api_key:
            self._vector_index = PineconeVectorIndexService(
                api_key=self._settings.pinecone_api_key,
                index_name=self._settings.pinecone_index_name,
            )
            if self._settings.nvidia_api_key:
                self._embedding_provider = NVIDIAEmbeddingProvider(
                    api_key=self._settings.nvidia_api_key,
                    model=self._settings.nvidia_embedding_model,
                )

    def start(self):
        self._recover_stuck_jobs()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _get_db(self):
        return Database(self._settings.database_url)

    def _recover_stuck_jobs(self):
        db = self._get_db()
        db.execute(
            "UPDATE ingestion_jobs SET status = 'failed', error_message = 'Server restarted', completed_at = datetime('now') WHERE status = 'processing'",
        )
        db.execute(
            "UPDATE regulations SET index_status = 'failed' WHERE index_status = 'ingesting'",
        )
        db.commit()
        db.close()

    def _run(self):
        while not self._stop_event.is_set():
            db = self._get_db()
            row = db.execute(
                "SELECT id FROM ingestion_jobs WHERE status = 'pending' ORDER BY created_at LIMIT 1",
            ).fetchone()
            if row:
                job_id = row["id"]
                db.close()
                worker_db = self._get_db()
                try:
                    process_job(
                        worker_db, job_id, self._settings.data_dir,
                        vector_index=self._vector_index,
                        embedding_provider=self._embedding_provider,
                    )
                finally:
                    worker_db.close()
            else:
                db.close()
                time.sleep(POLL_INTERVAL)
