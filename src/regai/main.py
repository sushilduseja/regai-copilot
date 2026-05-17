from contextlib import asynccontextmanager

from fastapi import FastAPI
from regai.config import Settings
from regai.db import Database, run_migrations
from regai.routes import auth
from regai.routes import admin as admin_routes
from regai.routes import app as app_routes
from regai.ingestion.worker import IngestionWorker
from regai.services.vector_index import (
    PineconeVectorIndexService,
    FakeVectorIndexService,
    FakeEmbeddingProvider,
    NVIDIAEmbeddingProvider,
)


def create_app(db=None, vector_index=None, embedding_provider=None) -> FastAPI:
    settings = Settings()

    start_worker = db is None
    if db is None:
        db = Database(settings.database_url)
    run_migrations(db)

    if vector_index is None:
        if settings.pinecone_api_key:
            try:
                import pinecone
                vector_index = PineconeVectorIndexService(
                    api_key=settings.pinecone_api_key,
                    index_name=settings.pinecone_index_name,
                )
            except ImportError:
                vector_index = FakeVectorIndexService()
            except Exception as e:
                import logging
                logging.getLogger("regai").warning(
                    f"Pinecone unavailable: {type(e).__name__}: {e}. Falling back to FTS-only."
                )
                vector_index = None
        else:
            vector_index = FakeVectorIndexService()

    if embedding_provider is None:
        if settings.nvidia_api_key:
            embedding_provider = NVIDIAEmbeddingProvider(
                api_key=settings.nvidia_api_key,
                model=settings.nvidia_embedding_model,
            )
        else:
            embedding_provider = FakeEmbeddingProvider()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if start_worker:
            worker = IngestionWorker(settings)
            worker.start()
            app.state.worker = worker
        yield
        worker = getattr(app.state, "worker", None)
        if worker:
            worker.stop()

    app = FastAPI(title="RegAI Copilot", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db
    app.state.vector_index = vector_index
    app.state.embedding_provider = embedding_provider

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(admin_routes.router)
    app.include_router(app_routes.router)

    return app
