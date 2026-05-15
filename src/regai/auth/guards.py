from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from regai.auth.session import SESSION_COOKIE, get_session


def require_auth(request: Request) -> Response | None:
    session_token = request.cookies.get(SESSION_COOKIE)
    if not session_token:
        return RedirectResponse("/auth/login", status_code=303)

    session = get_session(request.app.state.db, session_token)
    if session is None:
        return RedirectResponse("/auth/login", status_code=303)

    request.state.user = session
    return None
