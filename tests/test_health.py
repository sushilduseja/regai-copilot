import pytest
from fastapi.testclient import TestClient

def test_health_returns_200(test_app):
    client = TestClient(test_app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
