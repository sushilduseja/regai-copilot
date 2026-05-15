import sqlite3
import hashlib
import threading
from contextlib import contextmanager
from pathlib import Path


class Database:
    """Thread-safe SQLite access via reentrant lock."""

    def __init__(self, database_url: str):
        path = database_url.replace("sqlite:///", "")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    @contextmanager
    def transaction(self):
        """Hold lock through full operation (execute + commit)."""
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def execute(self, sql, params=()):
        with self._lock:
            return self._conn.execute(sql, params)

    def executescript(self, sql):
        with self._lock:
            return self._conn.executescript(sql)

    def commit(self):
        with self._lock:
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()


def _resolve_migrations_dir(migrations_dir: str) -> Path:
    """Resolve migrations directory relative to project root (pyproject.toml)."""
    p = Path(migrations_dir)
    if p.is_absolute():
        return p
    # Walk up from this file to find project root (pyproject.toml)
    project_root = Path(__file__).resolve().parent.parent.parent
    resolved = project_root / migrations_dir
    if resolved.exists():
        return resolved
    # Fallback: try relative to CWD
    return Path.cwd() / migrations_dir


def run_migrations(db: Database, migrations_dir: str = "migrations"):
    db.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    db.commit()

    applied = {}
    for row in db.execute("SELECT version, checksum FROM schema_migrations"):
        applied[row["version"]] = row["checksum"]

    migration_path = _resolve_migrations_dir(migrations_dir)
    if not migration_path.exists():
        raise FileNotFoundError(
            f"Migrations directory not found: {migration_path}. "
            f"Expected at project root or CWD."
        )

    sql_files = sorted(migration_path.glob("*.sql"))
    if not sql_files:
        raise RuntimeError(f"No .sql files found in {migration_path}")

    for sql_file in sql_files:
        version = sql_file.stem
        content = sql_file.read_text()
        checksum = hashlib.sha256(content.encode()).hexdigest()

        if version in applied:
            if applied[version] != checksum:
                raise RuntimeError(
                    f"Migration {version} checksum mismatch. "
                    f"Expected {applied[version]}, got {checksum}"
                )
            continue

        db.executescript(content)
        db.execute(
            "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
            (version, checksum),
        )
        db.commit()
