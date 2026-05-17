from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from regai.config import Settings
from regai.db import Database, run_migrations
from regai.routes import auth
from regai.routes import admin as admin_routes
from regai.routes import app as app_routes
from regai.ingestion.worker import IngestionWorker
from regai.services.search import SearchService
from regai.services.audit import AuditService
from regai.services.vector_index import (
    PineconeVectorIndexService,
    FakeEmbeddingProvider,
    NVIDIAEmbeddingProvider,
)


def create_app(db=None) -> FastAPI:
    settings = Settings()

    start_worker = db is None
    if db is None:
        db = Database(settings.database_url)
    run_migrations(db)

    vector_index = None
    embedding_provider = None
    if settings.pinecone_api_key:
        vector_index = PineconeVectorIndexService(
            api_key=settings.pinecone_api_key,
            index_name=settings.pinecone_index_name,
        )
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

    templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")

    app.include_router(auth.router)
    app.include_router(admin_routes.router)
    app.include_router(app_routes.router)

    @app.get("/app")
    def app_search(request: Request, q: str = ""):
        from regai.auth.guards import require_auth
        import logging
        guard = require_auth(request)
        if guard:
            return guard

        filters = {}
        reg = request.query_params.get("reg")
        dt = request.query_params.get("dt")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        j_params = request.query_params.getlist("j")
        if j_params:
            filters["jurisdictions"] = j_params
        if reg:
            filters["regulator"] = reg
        if dt:
            filters["document_type"] = dt
        if date_from:
            filters["date_from"] = date_from
        if date_to:
            filters["date_to"] = date_to

        result = {"results": [], "error": None, "count": 0}
        user_id = request.state.user["user_id"]
        if q:
            try:
                svc = SearchService(request.app.state.db)
                vi = request.app.state.vector_index
                ep = request.app.state.embedding_provider
                if vi is not None and ep is not None:
                    vector = ep.embed_texts([q])[0]
                    result = svc.hybrid_search(
                        request.state.user["user_id"], q, vector, vi, filters=filters,
                    )
                else:
                    result = svc.search(request.state.user["user_id"], q, filters=filters)
            except Exception:
                logging.getLogger("regai").exception("Search failed")
                result = {"results": [], "error": "search_unavailable", "count": 0}
        elif filters:
            try:
                svc = SearchService(request.app.state.db)
                result = svc.browse(request.state.user["user_id"], filters=filters)
            except Exception:
                logging.getLogger("regai").exception("Browse failed")
                result = {"results": [], "error": "search_unavailable", "count": 0}

        try:
            audit = AuditService(request.app.state.db)
            audit.log(
                action="search.executed",
                actor_user_id=request.state.user["user_id"],
                entity_type="search",
                metadata={
                    "query": q,
                    "result_count": result["count"],
                    "error": result["error"],
                    "filters": filters,
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        except Exception:
            logging.getLogger("regai").exception("Search audit failed")

        return templates.TemplateResponse(request, "search.html", {
            "user": request.state.user,
            "result": result,
            "q": q,
            "filters": filters,
        })

    return app
