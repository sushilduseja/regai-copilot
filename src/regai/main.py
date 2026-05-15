from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from regai.config import Settings
from regai.db import Database, run_migrations
from regai.routes import auth
from regai.routes import admin as admin_routes
from regai.ingestion.worker import IngestionWorker


def create_app(db=None) -> FastAPI:
    settings = Settings()

    start_worker = db is None
    if db is None:
        db = Database(settings.database_url)
    run_migrations(db)

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

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(admin_routes.router)

    @app.get("/app")
    def app_dashboard(request: Request):
        from regai.auth.guards import require_auth
        guard = require_auth(request)
        if guard:
            return guard
        return {"message": "Dashboard", "user": request.state.user["email"]}

    return app
