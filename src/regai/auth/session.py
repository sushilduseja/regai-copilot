import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional


SESSION_COOKIE = "regai_session"
SESSION_DURATION_DAYS = 7


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_hash(token: str) -> str:
    """Public alias for _hash_token."""
    return _hash_token(token)


def create_session(db, user_id: str) -> str:
    """Returns opaque session token. Stores SHA-256 hash in DB."""
    token = secrets.token_hex(32)
    token_hash = _hash_token(token)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS)).isoformat()
    db.execute(
        "INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)",
        (token_hash, user_id, expires_at),
    )
    db.commit()
    return token


def get_session(db, token: str) -> Optional[dict]:
    token_hash = _hash_token(token)
    row = db.execute(
        """SELECT s.id, s.user_id, s.expires_at, u.id as uid, u.role, u.email, u.name
           FROM sessions s
           JOIN users u ON u.id = s.user_id
           WHERE s.id = ? AND s.revoked_at IS NULL AND s.expires_at > ? AND u.is_active = 1""",
        (token_hash, datetime.now(timezone.utc).isoformat()),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def revoke_session(db, token: str):
    token_hash = _hash_token(token)
    db.execute(
        "UPDATE sessions SET revoked_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), token_hash),
    )
    db.commit()
