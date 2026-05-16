from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from regai.auth.guards import require_auth
from regai.services.audit import AuditService

router = APIRouter(prefix="/app", tags=["app"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/documents/{regulation_id}")
def document_detail(request: Request, regulation_id: str):
    guard = require_auth(request)
    if guard:
        return guard

    db = request.app.state.db
    user_id = request.state.user["user_id"]
    row = db.execute(
        "SELECT id, title, jurisdiction, regulator, document_type, publication_date, effective_date, source_url FROM regulations WHERE id = ?",
        (regulation_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Regulation not found")

    regulation = dict(row)

    user_jurisdictions = db.execute(
        "SELECT jurisdiction FROM user_jurisdictions WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    allowed = {r["jurisdiction"] for r in user_jurisdictions}
    if regulation["jurisdiction"] not in allowed:
        raise HTTPException(403, "Access denied")

    chunks = [
        dict(r) for r in db.execute(
            "SELECT id, chunk_index, section_id, section_path, heading, text, token_count FROM regulation_chunks WHERE regulation_id = ? ORDER BY chunk_index",
            (regulation_id,),
        ).fetchall()
    ]

    audit = AuditService(db)
    audit.log(
        action="regulation.viewed",
        actor_user_id=user_id,
        entity_type="regulation",
        entity_id=regulation_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return templates.TemplateResponse(request, "document.html", {
        "user": request.state.user, "regulation": regulation, "chunks": chunks,
    })
