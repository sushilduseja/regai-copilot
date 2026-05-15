import uuid
import secrets
from urllib.parse import urlencode
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from regai.auth.session import (
    SESSION_COOKIE,
    SESSION_DURATION_DAYS,
    create_session,
    revoke_session,
    token_hash,
)
from regai.services.audit import AuditService

router = APIRouter(prefix="/auth", tags=["auth"])

STATE_COOKIE = "regai_auth_state"
CSRF_COOKIE = "regai_csrf"
CSRF_HEADER = "X-CSRF-Token"


def _get_workos_client(settings):
    from workos import WorkOSClient
    return WorkOSClient(api_key=settings.workos_api_key, client_id=settings.workos_client_id)


def _verify_workos_user(code: str, settings) -> dict:
    """Exchange WorkOS code for user profile. Mockable for tests."""
    client = _get_workos_client(settings)
    profile = client.user_management.authenticate_with_code(code=code)
    return {
        "id": profile["user"]["id"],
        "email": profile["user"]["email"],
        "name": profile["user"].get("first_name", "") + " " + profile["user"].get("last_name", ""),
    }


@router.get("/login")
def login(request: Request):
    settings = request.app.state.settings
    state = secrets.token_hex(16)
    is_prod = settings.environment == "production"

    client = _get_workos_client(settings)
    url = client.user_management.get_authorization_url(
        provider="authkit",
        redirect_uri=settings.workos_redirect_uri,
        state=state,
    )

    response = RedirectResponse(url, status_code=303)
    response.set_cookie(
        STATE_COOKIE, state, httponly=True, samesite="lax",
        max_age=600, secure=is_prod,
    )
    return response


@router.get("/callback")
def callback(request: Request, code: str = None, state: str = None):
    settings = request.app.state.settings
    db = request.app.state.db
    audit = AuditService(db)
    is_prod = settings.environment == "production"

    # Verify state
    cookie_state = request.cookies.get(STATE_COOKIE)
    if not state or not cookie_state or state != cookie_state:
        audit.log(action="auth.login_failed", entity_type="user", metadata={"reason": "state_mismatch"})
        response = RedirectResponse("/auth/login", status_code=303)
        response.delete_cookie(STATE_COOKIE)
        return response

    # Verify WorkOS code
    try:
        profile = _verify_workos_user(code, settings)
    except Exception as e:
        audit.log(
            action="auth.login_failed", entity_type="user",
            metadata={"reason": "workos_error", "error": str(e)},
        )
        response = RedirectResponse("/auth/login", status_code=303)
        response.delete_cookie(STATE_COOKIE)
        return response

    # Upsert user
    existing = db.execute(
        "SELECT id, role FROM users WHERE auth_subject = ?",
        (profile["id"],),
    ).fetchone()

    is_new = existing is None
    if existing:
        user_id = existing["id"]
        role = existing["role"]
    else:
        user_id = str(uuid.uuid4())
        user_count = db.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
        bootstrap_emails = settings.bootstrap_admin_emails

        if bootstrap_emails:
            allowed = [e.strip() for e in bootstrap_emails.split(",")]
            if profile["email"] not in allowed:
                audit.log(
                    action="auth.login_failed", entity_type="user",
                    metadata={"reason": "bootstrap_blocked", "email": profile["email"]},
                )
                response = RedirectResponse("/auth/login", status_code=303)
                response.delete_cookie(STATE_COOKIE)
                return response
            role = "admin"
        else:
            role = "admin" if user_count == 0 else "analyst"

        db.execute(
            "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, ?)",
            (user_id, profile["id"], profile["email"], profile["name"], role),
        )

        if role == "admin":
            for j in ("US", "EU"):
                db.execute(
                    "INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, ?)",
                    (user_id, j),
                )

        db.commit()

        if role == "admin" and user_count == 0:
            audit.log(
                action="auth.bootstrap_admin_created",
                actor_user_id=user_id,
                entity_type="user", entity_id=user_id,
                metadata={"email": profile["email"]},
            )

        audit.log(
            action="user.created",
            actor_user_id=user_id,
            entity_type="user", entity_id=user_id,
            metadata={"role": role, "email": profile["email"]},
        )

    # Create session
    session_token = create_session(db, user_id)
    csrf_token = secrets.token_hex(16)

    audit.log(
        action="auth.login_succeeded",
        actor_user_id=user_id,
        entity_type="user", entity_id=user_id,
        metadata={"is_new": is_new},
    )

    response = RedirectResponse("/app", status_code=303)
    response.set_cookie(
        SESSION_COOKIE, session_token,
        httponly=True, samesite="lax",
        secure=is_prod,
        max_age=SESSION_DURATION_DAYS * 86400,
    )
    response.set_cookie(
        CSRF_COOKIE, csrf_token,
        httponly=False, samesite="lax",
        secure=is_prod,
        max_age=SESSION_DURATION_DAYS * 86400,
    )
    response.delete_cookie(STATE_COOKIE)
    return response


@router.post("/logout")
def logout(request: Request):
    # CSRF validation
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    csrf_header = request.headers.get(CSRF_HEADER)
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(status_code=403, detail="CSRF validation failed")

    db = request.app.state.db
    audit = AuditService(db)
    session_token = request.cookies.get(SESSION_COOKIE)
    if session_token:
        tok_hash = token_hash(session_token)
        user = db.execute(
            "SELECT u.id FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.id = ?",
            (tok_hash,),
        ).fetchone()
        if user:
            audit.log(
                action="auth.logout",
                actor_user_id=user["id"],
                entity_type="user", entity_id=user["id"],
            )
        revoke_session(db, session_token)
    response = RedirectResponse("/auth/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    return response
