import pytest
from fastapi.testclient import TestClient

def test_protected_route_redirects_to_login(test_app):
    client = TestClient(test_app, follow_redirects=False)
    response = client.get("/app")
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


def test_invalid_session_denied(test_app):
    client = TestClient(test_app, follow_redirects=False)
    client.cookies.set("regai_session", "nonexistent_session_id")
    response = client.get("/app")
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


def test_expired_session_denied(test_app):
    import hashlib
    db = test_app.state.db
    # Create expired session
    db.execute(
        "INSERT INTO users (id, auth_subject, email) VALUES (?, ?, ?)",
        ("user_expired", "workos_expired", "expired@example.com"),
    )
    token_hash = hashlib.sha256("expired_session".encode()).hexdigest()
    db.execute(
        "INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)",
        (token_hash, "user_expired", "2020-01-01T00:00:00"),
    )
    db.commit()

    client = TestClient(test_app, follow_redirects=False)
    client.cookies.set("regai_session", "expired_session")
    response = client.get("/app")
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


def test_logout_requires_csrf(test_app):
    client = TestClient(test_app, follow_redirects=False)
    # Set a session cookie but no CSRF
    client.cookies.set("regai_session", "any_session")
    response = client.post("/auth/logout")
    assert response.status_code == 403


def test_logout_csrf_mismatch_denied(test_app):
    client = TestClient(test_app, follow_redirects=False)
    client.cookies.set("regai_session", "any_session")
    client.cookies.set("regai_csrf", "cookie_token")
    response = client.post("/auth/logout", headers={"X-CSRF-Token": "wrong_token"})
    assert response.status_code == 403
