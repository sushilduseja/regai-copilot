import uuid
import secrets
import shutil
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from regai.main import create_app
from regai.db import Database, run_migrations
from regai.auth.session import create_session

@pytest.fixture(scope="session")
def session_tmp_path(tmp_path_factory):
    return tmp_path_factory.mktemp("session_data")

@pytest.fixture(scope="session")
def base_db(session_tmp_path):
    """Create a base database with migrations applied once per session."""
    db_path = session_tmp_path / "base_test.db"
    db = Database(f"sqlite:///{db_path}")
    run_migrations(db)
    db.close()
    return db_path

@pytest.fixture
def test_app(base_db, tmp_path):
    """Provide a fresh app with a clean database for every test by copying the base DB."""
    db_path = tmp_path / "test.db"
    shutil.copy(base_db, db_path)
    
    db = Database(f"sqlite:///{db_path}")
    app = create_app(db=db)
    app.state.settings.data_dir = str(tmp_path / "data")
    yield app
    db.close()

def _user_headers(test_app, role="analyst", jurisdictions=None):
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, ?)",
        (user_id, f"{role}_{user_id}", f"{role}_{user_id}@example.com", f"{role.title()} User", role),
    )
    if jurisdictions:
        for j in jurisdictions:
            db.execute(
                "INSERT INTO user_jurisdictions (user_id, jurisdiction) VALUES (?, ?)",
                (user_id, j),
            )
    db.commit()
    session_token = create_session(db, user_id)
    csrf = secrets.token_hex(16)
    return {"session": session_token, "csrf": csrf, "user_id": user_id}

@pytest.fixture
def admin_client(test_app):
    h = _user_headers(test_app, "admin", jurisdictions=["US", "EU"])
    client = TestClient(test_app, follow_redirects=False)
    client.cookies.set("regai_session", h["session"])
    client.cookies.set("regai_csrf", h["csrf"])
    return client

@pytest.fixture
def analyst_client(test_app):
    h = _user_headers(test_app, "analyst", jurisdictions=["US"])
    client = TestClient(test_app, follow_redirects=False)
    client.cookies.set("regai_session", h["session"])
    client.cookies.set("regai_csrf", h["csrf"])
    return client

@pytest.fixture
def us_client(analyst_client):
    return analyst_client

@pytest.fixture
def no_jurisdiction_client(test_app):
    h = _user_headers(test_app, "analyst", jurisdictions=[])
    client = TestClient(test_app, follow_redirects=False)
    client.cookies.set("regai_session", h["session"])
    client.cookies.set("regai_csrf", h["csrf"])
    return client

@pytest.fixture
def admin_headers(test_app):
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, f"admin_{user_id}", f"admin_{user_id}@example.com", "Admin"),
    )
    db.commit()
    session_token = create_session(db, user_id)
    csrf = secrets.token_hex(16)
    db.commit()
    return {"session": session_token, "csrf": csrf, "user_id": user_id}

@pytest.fixture
def analyst_headers(test_app):
    db = test_app.state.db
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, auth_subject, email, name, role) VALUES (?, ?, ?, ?, 'analyst')",
        (user_id, f"analyst_{user_id}", f"analyst_{user_id}@example.com", "Analyst"),
    )
    db.commit()
    session_token = create_session(db, user_id)
    csrf = secrets.token_hex(16)
    db.commit()
    return {"session": session_token, "csrf": csrf, "user_id": user_id}
