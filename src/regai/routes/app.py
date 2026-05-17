import logging
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from regai.auth.guards import require_auth
from regai.services.audit import AuditService
from regai.services.search import SearchService

router = APIRouter(prefix="/app", tags=["app"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("")
def app_search(request: Request, q: str = ""):
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
            actor_user_id=user_id,
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
