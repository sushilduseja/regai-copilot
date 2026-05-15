import json
import pytest
from regai.services.audit import AuditService
from regai.db import Database, run_migrations


@pytest.fixture
def audit_service(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    run_migrations(db)
    service = AuditService(db)
    yield service
    db.close()


def test_audit_log_inserts_valid_entry(audit_service):
    # Create user first (FK constraint)
    audit_service._conn.execute(
        "INSERT INTO users (id, auth_subject, email) VALUES (?, ?, ?)",
        ("user_123", "workos_sub_123", "test@example.com"),
    )
    audit_service._conn.commit()

    audit_service.log(
        actor_user_id="user_123",
        action="auth.login_succeeded",
        entity_type="user",
        entity_id="user_123",
        metadata={"ip": "127.0.0.1"},
        request_id="req_abc",
    )

    rows = audit_service._conn.execute(
        "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 1"
    ).fetchone()

    assert rows is not None
    assert rows["actor_user_id"] == "user_123"
    assert rows["action"] == "auth.login_succeeded"
    assert rows["entity_type"] == "user"
    assert rows["entity_id"] == "user_123"
    assert rows["request_id"] == "req_abc"
    # Verify metadata is valid JSON
    metadata = json.loads(rows["metadata"])
    assert metadata["ip"] == "127.0.0.1"


def test_audit_log_system_event_no_actor(audit_service):
    audit_service.log(
        actor_user_id=None,
        action="db.migration_applied",
        entity_type="schema",
        entity_id=None,
        metadata={"version": "001_initial"},
    )

    rows = audit_service._conn.execute(
        "SELECT * FROM audit_logs WHERE action = 'db.migration_applied'"
    ).fetchone()

    assert rows is not None
    assert rows["actor_user_id"] is None
