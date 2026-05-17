import uuid
import hashlib
import os
import secrets
import tempfile
import shutil
from pathlib import Path
from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from regai.auth.guards import require_admin
from regai.services.audit import AuditService
from regai.services.llm import CompletionService, NVIDIACompletionProvider


router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")

ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown"}
REGULATOR_JURISDICTION = {"SEC": "US", "CFTC": "US", "EUR_LEX": "EU"}
CSRF_COOKIE = "regai_csrf"
CSRF_HEADER = "X-CSRF-Token"
CHUNK_SIZE = 65536


class _RedirectToRegulation(Exception):
    """Internal exception to trigger redirect from inside transaction block."""
    def __init__(self, regulation_id: str):
        self.regulation_id = regulation_id


def _get_upload_dir(data_dir: str) -> Path:
    return Path(data_dir) / "uploads" / "originals"


def _validate_metadata(regulator: str, jurisdiction: str, language: str):
    if regulator not in REGULATOR_JURISDICTION:
        raise HTTPException(400, f"Invalid regulator: {regulator}")
    if jurisdiction not in ("US", "EU"):
        raise HTTPException(400, f"Invalid jurisdiction: {jurisdiction}")
    if REGULATOR_JURISDICTION[regulator] != jurisdiction:
        raise HTTPException(400, f"Regulator {regulator} does not match jurisdiction {jurisdiction}")
    if language != "en":
        raise HTTPException(400, "Only English is supported")


def _check_csrf(request: Request):
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or cookie != header:
        raise HTTPException(403, "CSRF validation failed")


@router.post("/regulations/suggest")
async def suggest_metadata(
    request: Request,
    file: UploadFile = File(...),
):
    guard = require_admin(request)
    if guard:
        return guard
    _check_csrf(request)

    settings = request.app.state.settings

    # Metadata suggestion requires NVIDIA API key (Groq not yet supported)
    if not settings.nvidia_api_key:
        if settings.groq_api_key:
            raise HTTPException(503, "Metadata suggestion unavailable: Groq provider not implemented. Configure NVIDIA_API_KEY instead.")
        raise HTTPException(503, "Metadata suggestion unavailable: NVIDIA API key not configured")

    # Read up to 40KB of the file (enough to capture headers/metadata)
    content = await file.read(40000)
    text = content.decode("utf-8", errors="ignore")

    try:
        provider = NVIDIACompletionProvider(
            api_key=settings.nvidia_api_key,
            model="meta/llama-3.1-8b-instruct"
        )
        svc = CompletionService(provider)

        prompt = f"Extract regulatory metadata from the following regulatory document text. Return ONLY a valid JSON object with these exact keys. Never wrap in markdown:\n- title: The full official title (string, required)\n- regulator: One of ['SEC', 'CFTC', 'EUR_LEX'] (string, required)\n- jurisdiction: One of ['US', 'EU'] (string, required)\n- document_type: Type of document (string, required, e.g. 'rule', 'directive', 'regulation', 'guideline')\n- publication_date: Publication date in YYYY-MM-DD format (string, or empty string if not found)\n- effective_date: Effective date in YYYY-MM-DD format (string, or empty string if not found)\n- source_url: Official URL for this document (string, or empty string if not found)\n- license_note: License or copyright notice (string, or empty string if not found)\n\nLook carefully for dates in headers, footers, or metadata sections. Look for URLs in headers or footnotes.\n\nText:\n{text}"
        system_prompt = "You are a regulatory data extractor. Return only valid JSON."

        suggestion = await svc.complete_async(prompt, system_prompt)

        # Basic cleaning of JSON response (remove markdown blocks if present)
        suggestion = suggestion.strip()
        if suggestion.startswith("```json"):
            suggestion = suggestion[7:].rstrip("```").strip()
        elif suggestion.startswith("```"):
            suggestion = suggestion[3:].rstrip("```").strip()

        import json
        return json.loads(suggestion)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Metadata suggestion temporarily unavailable")


@router.get("/regulations/upload")
def upload_form(request: Request):
    guard = require_admin(request)
    if guard:
        return guard
    csrf_token = request.cookies.get(CSRF_COOKIE) or secrets.token_hex(32)
    response = templates.TemplateResponse(request, "admin/upload.html", {
        "user": request.state.user,
        "csrf_token": csrf_token,
    })
    response.set_cookie(CSRF_COOKIE, csrf_token, httponly=False, samesite="lax")
    return response


@router.post("/regulations/upload")
async def upload_submit(
    request: Request,
    title: str = Form(...),
    regulator: str = Form(...),
    jurisdiction: str = Form(...),
    document_type: str = Form(...),
    source_url: str = Form(...),
    license_note: str = Form(...),
    language: str = Form("en"),
    publication_date: str = Form(None),
    effective_date: str = Form(None),
    file: UploadFile = File(...),
):
    guard = require_admin(request)
    if guard:
        return guard
    _check_csrf(request)

    db = request.app.state.db
    settings = request.app.state.settings
    audit = AuditService(db)
    user_id = request.state.user["user_id"]

    _validate_metadata(regulator, jurisdiction, language)

    ext = Path(file.filename or "file.txt").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Only TXT and MD are accepted.")

    max_size = settings.max_upload_size
    upload_dir = _get_upload_dir(settings.data_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext, dir=str(upload_dir))
    try:
        sha = hashlib.sha256()
        total = 0
        while chunk := await file.read(CHUNK_SIZE):
            if total + len(chunk) > max_size:
                tmp.close()
                os.unlink(tmp.name)
                raise HTTPException(400, f"File too large: {total + len(chunk)} bytes (max {max_size})")
            total += len(chunk)
            sha.update(chunk)
            tmp.write(chunk)
        tmp.close()

        file_hash = sha.hexdigest()
        dest_path = upload_dir / f"{file_hash}{ext}"

        with db.transaction():
            existing = db.execute(
                "SELECT id FROM regulations WHERE document_hash = ?", (file_hash,),
            ).fetchone()
            if existing:
                os.unlink(tmp.name)
                raise _RedirectToRegulation(existing["id"])

            shutil.move(tmp.name, str(dest_path))

            regulation_id = str(uuid.uuid4())
            db.execute(
                """INSERT INTO regulations (
                    id, title, jurisdiction, regulator, document_type,
                    publication_date, effective_date, source_url, license_note,
                    language, document_hash, original_filename, mime_type,
                    file_size_bytes, original_file_path, index_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ingesting')""",
                (
                    regulation_id, title, jurisdiction, regulator, document_type,
                    publication_date, effective_date, source_url, license_note,
                    language, file_hash, file.filename, file.content_type,
                    total, str(dest_path),
                ),
            )

            job_id = str(uuid.uuid4())
            db.execute(
                """INSERT INTO ingestion_jobs (id, admin_user_id, filename,
                    file_path, status, regulation_id)
                   VALUES (?, ?, ?, ?, 'pending', ?)""",
                (job_id, user_id, file.filename, str(dest_path), regulation_id),
            )

            audit.log(
                action="ingestion.started",
                actor_user_id=user_id,
                entity_type="regulation",
                entity_id=regulation_id,
                metadata={"job_id": job_id, "filename": file.filename, "hash": file_hash},
            )
    except _RedirectToRegulation as e:
        return RedirectResponse(f"/admin/regulations/{e.regulation_id}", status_code=303)
    except Exception:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise

    # Worker polls DB for pending jobs automatically, no need to enqueue

    return RedirectResponse(f"/admin/ingestion-jobs/{job_id}", status_code=303)


@router.get("/jobs")
def job_list(request: Request):
    guard = require_admin(request)
    if guard:
        return guard
    db = request.app.state.db
    rows = db.execute(
        """SELECT j.*, r.title AS regulation_title, r.index_status AS regulation_status
           FROM ingestion_jobs j
           LEFT JOIN regulations r ON r.id = j.regulation_id
           ORDER BY j.created_at DESC"""
    ).fetchall()
    return templates.TemplateResponse(request, "admin/jobs.html", {
        "user": request.state.user, "jobs": [dict(r) for r in rows],
    })


@router.get("/ingestion-jobs/{job_id}")
def job_detail(request: Request, job_id: str):
    guard = require_admin(request)
    if guard:
        return guard
    db = request.app.state.db
    job = db.execute(
        "SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,),
    ).fetchone()
    if not job:
        raise HTTPException(404, "Job not found")
    regulation = db.execute(
        "SELECT id, title FROM regulations WHERE id = ?",
        (job["regulation_id"],),
    ).fetchone()
    return templates.TemplateResponse(request, "admin/job_detail.html", {
        "user": request.state.user,
        "job": dict(job),
        "regulation": dict(regulation) if regulation else None,
        "csrf_token": request.cookies.get(CSRF_COOKIE, ""),
    })


@router.post("/ingestion-jobs/{job_id}/retry")
def retry_job(request: Request, job_id: str):
    guard = require_admin(request)
    if guard:
        return guard
    _check_csrf(request)
    db = request.app.state.db
    job = db.execute(
        "SELECT id, regulation_id FROM ingestion_jobs WHERE id = ? AND status = 'failed'",
        (job_id,),
    ).fetchone()
    if not job:
        raise HTTPException(400, "Job not found or not in failed state")
    db.execute(
        "UPDATE ingestion_jobs SET status = 'pending', started_at = NULL, completed_at = NULL, error_message = NULL WHERE id = ?",
        (job_id,),
    )
    db.execute(
        "UPDATE regulations SET index_status = 'ingesting' WHERE id = ?",
        (job["regulation_id"],),
    )
    db.commit()
    # Worker polls DB for pending jobs automatically, no need to enqueue
    return RedirectResponse(f"/admin/ingestion-jobs/{job_id}", status_code=303)


@router.get("/regulations")
def regulation_list(request: Request):
    guard = require_admin(request)
    if guard:
        return guard
    db = request.app.state.db
    rows = db.execute(
        "SELECT id, title, regulator, jurisdiction, document_type, index_status, created_at FROM regulations ORDER BY created_at DESC",
    ).fetchall()
    return templates.TemplateResponse(request, "admin/regulations.html", {
        "user": request.state.user, "regulations": [dict(r) for r in rows],
    })


@router.get("/regulations/{regulation_id}")
def regulation_detail(request: Request, regulation_id: str):
    guard = require_admin(request)
    if guard:
        return guard
    db = request.app.state.db
    row = db.execute(
        "SELECT * FROM regulations WHERE id = ?", (regulation_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Regulation not found")
    regulation = dict(row)
    chunks = [
        dict(r) for r in db.execute(
            "SELECT id, chunk_index, section_id, section_path, heading, text, token_count FROM regulation_chunks WHERE regulation_id = ? ORDER BY chunk_index",
            (regulation_id,),
        ).fetchall()
    ]
    return templates.TemplateResponse(request, "admin/regulation_detail.html", {
        "user": request.state.user, "regulation": regulation, "chunks": chunks,
    })
