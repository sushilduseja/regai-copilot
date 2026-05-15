import shutil
import hashlib
import pytest
from pathlib import Path
from regai.db import Database, run_migrations


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    yield db
    db.close()


def test_migrations_apply_and_rerun_idempotent(temp_db):
    run_migrations(temp_db)

    cursor = temp_db.execute("SELECT COUNT(*) FROM schema_migrations")
    count = cursor.fetchone()[0]
    assert count >= 1

    run_migrations(temp_db)

    cursor = temp_db.execute("SELECT COUNT(*) FROM schema_migrations")
    assert cursor.fetchone()[0] == count


def test_migration_checksum_enforced(tmp_path):
    # Copy migrations to temp dir so we never mutate real files
    tmp_migrations = tmp_path / "migrations"
    shutil.copytree(Path(__file__).parent.parent / "migrations", tmp_migrations)
    real_sql = tmp_migrations / "001_initial.sql"

    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    run_migrations(db, str(tmp_migrations))

    # Tamper with the temp copy
    original = real_sql.read_text()
    real_sql.write_text(original + "\n-- tampered")

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        run_migrations(db, str(tmp_migrations))

    db.close()


def test_sqlite_pragmas_enabled(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    try:
        cursor = db.execute("PRAGMA journal_mode")
        assert cursor.fetchone()[0] == "wal"

        cursor = db.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1
    finally:
        db.close()
