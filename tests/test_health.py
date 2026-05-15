import pytest
from fastapi.testclient import TestClient
from regai.main import create_app
from regai.db import Database, run_migrations


@pytest.fixture
def test_app(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    run_migrations(db)
    app = create_app(db=db)
    yield app
    db.close()


def test_health_returns_200(test_app):
    client = TestClient(test_app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
