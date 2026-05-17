import pytest
from fastapi.testclient import TestClient
from regai.main import create_app
from regai.db import Database, run_migrations

class _MockWorkOSClient:
    def __init__(self, **kwargs):
        pass

    @property
    def user_management(self):
        return self

    def get_authorization_url(self, **kwargs):
        return "https://mock.workos.com/authorize?state=" + kwargs.get("state", "")

    def authenticate_with_code(self, **kwargs):
        return self


def _callback_flow(client, monkeypatch, workos_id, email, name):
    """Helper: set mocks, get state cookie, call login then callback."""
    monkeypatch.setattr("regai.routes.auth._get_workos_client", lambda settings: _MockWorkOSClient())
    monkeypatch.setattr("regai.routes.auth._verify_workos_user", lambda code, settings: {
        "id": workos_id,
        "email": email,
        "name": name,
    })
    login_resp = client.get("/auth/login", follow_redirects=False)
    state_cookie = None
    for cookie in client.cookies.jar:
        if cookie.name == "regai_auth_state":
            state_cookie = cookie.value
            break
    assert state_cookie is not None

    return client.get(
        f"/auth/callback?code=test_{workos_id}&state={state_cookie}",
        follow_redirects=False,
    )


def test_first_login_creates_admin(test_app, monkeypatch):
    client = TestClient(test_app, follow_redirects=False)
    response = _callback_flow(client, monkeypatch, "workos_user_001", "admin@example.com", "First Admin")

    assert response.status_code == 303
    assert response.headers["location"] == "/app"

    session_cookie = response.cookies.get("regai_session")
    assert session_cookie is not None

    db = test_app.state.db
    user = db.execute(
        "SELECT id, role FROM users WHERE auth_subject = ?", ("workos_user_001",)
    ).fetchone()
    assert user is not None
    assert user["role"] == "admin"

    jurisdictions = db.execute(
        "SELECT jurisdiction FROM user_jurisdictions WHERE user_id = ?",
        (user["id"],),
    ).fetchall()
    jurs = [r["jurisdiction"] for r in jurisdictions]
    assert "US" in jurs
    assert "EU" in jurs


def test_second_login_creates_analyst(test_app, monkeypatch):
    client = TestClient(test_app, follow_redirects=False)
    _callback_flow(client, monkeypatch, "workos_user_001", "admin@example.com", "First Admin")

    response = _callback_flow(client, monkeypatch, "workos_user_002", "analyst@example.com", "Second User")
    assert response.status_code == 303

    db = test_app.state.db
    user = db.execute(
        "SELECT id, role FROM users WHERE auth_subject = ?", ("workos_user_002",)
    ).fetchone()
    assert user is not None
    assert user["role"] == "analyst"

    jurs = db.execute(
        "SELECT jurisdiction FROM user_jurisdictions WHERE user_id = ?",
        (user["id"],),
    ).fetchall()
    assert len(jurs) == 0


def test_bootstrap_allowlist_rejects_unauthorized(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAILS", "allowed@example.com")
    monkeypatch.setenv("ENVIRONMENT", "development")

    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    run_migrations(db)
    test_app = create_app(db=db)

    client = TestClient(test_app, follow_redirects=False)
    response = _callback_flow(client, monkeypatch, "workos_user_003", "unauthorized@example.com", "Unauthorized User")

    # Should redirect back to /auth/login (rejected)
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"

    # User should NOT have been created
    user = db.execute(
        "SELECT COUNT(*) as cnt FROM users WHERE auth_subject = ?", ("workos_user_003",)
    ).fetchone()
    assert user["cnt"] == 0
    db.close()
