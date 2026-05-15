import json
import uuid
from typing import Optional


class AuditService:
    def __init__(self, conn):
        self._conn = conn

    def log(
        self,
        action: str,
        entity_type: str,
        actor_user_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        self._conn.execute(
            """INSERT INTO audit_logs (
                id, actor_user_id, action, entity_type, entity_id,
                metadata, ip_address, user_agent, request_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                actor_user_id,
                action,
                entity_type,
                entity_id,
                json.dumps(metadata or {}),
                ip_address,
                user_agent,
                request_id,
            ),
        )
        self._conn.commit()
