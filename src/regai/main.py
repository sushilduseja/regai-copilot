from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from regai.config import Settings
from regai.db import Database, run_migrations
from regai.routes import auth


def create_app(db=None) -> FastAPI:
    settings = Settings()
    app = FastAPI(title="RegAI Copilot")
    app.state.settings = settings

    # Initialize DB and run migrations on startup
    if db is None:
        db = Database(settings.database_url)
    run_migrations(db)
    app.state.db = db

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Include routes
    app.include_router(auth.router)

    @app.get("/app")
    def app_dashboard(request: Request):
        from regai.auth.guards import require_auth
        guard = require_auth(request)
        if guard:
            return guard
        return {"message": "Dashboard", "user": request.state.user["email"]}

    return app
