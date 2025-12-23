"""
Audit Service - Persistent audit trail for compliance.

Logs all admin actions, permission changes, and optionally data access events.

Version: 1.0.0
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
import json

from psycopg2.extras import RealDictCursor
from auth.auth_service import get_db_connection

logger = logging.getLogger(__name__)

SCHEMA = "enterprise"

# Singleton instance
_audit_service = None


@dataclass
class AuditEntry:
    """Single audit log entry."""
    id: str
    action: str
    actor_email: Optional[str]
    target_email: Optional[str]
    department_slug: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    reason: Optional[str]
    ip_address: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "action": self.action,
            "actor_email": self.actor_email,
            "target_email": self.target_email,
            "department_slug": self.department_slug,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "ip_address": self.ip_address,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class AuditService:
    """
    Service for logging and querying audit events.

    Thread-safe, uses connection pooling via get_db_connection().
    """

    # Valid action types (for validation)
    VALID_ACTIONS = {
        # Authentication
        "login", "logout", "token_refresh", "auth_failure",
        # Authorization
        "department_access_grant", "department_access_revoke",
        "dept_head_promote", "dept_head_revoke",
        "super_user_promote", "super_user_revoke",
        "access_denied",
        # User management
        "user_created", "user_updated", "user_deactivated",
        "user_reactivated", "batch_import",
        # Data access (optional, high volume)
        "user_query", "document_retrieval", "dept_switch"
    }

    def log_event(
        self,
        action: str,
        actor_email: Optional[str] = None,
        target_email: Optional[str] = None,
        department_slug: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Log an audit event.

        Returns the UUID of the created entry, or None on failure.
        """
        if action not in self.VALID_ACTIONS:
            logger.warning(f"[Audit] Unknown action type: {action}")
            # Still log it, but warn

        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                    INSERT INTO {SCHEMA}.audit_log
                        (action, actor_email, target_email, department_slug,
                         old_value, new_value, reason, ip_address, user_agent, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    action,
                    actor_email.lower() if actor_email else None,
                    target_email.lower() if target_email else None,
                    department_slug,
                    old_value,
                    new_value,
                    reason,
                    ip_address,
                    user_agent,
                    json.dumps(metadata or {})
                ))
                result = cur.fetchone()
                conn.commit()

                entry_id = str(result[0]) if result else None
                logger.debug(f"[Audit] Logged {action} by {actor_email} -> {entry_id}")
                return entry_id

        except Exception as e:
            logger.error(f"[Audit] Failed to log event: {e}")
            return None

    def query_log(
        self,
        action: Optional[str] = None,
        actor_email: Optional[str] = None,
        target_email: Optional[str] = None,
        department: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query audit log with filters.

        Returns list of audit entry dicts, ordered by created_at DESC.
        """
        conditions = []
        params = []

        if action:
            conditions.append("action = %s")
            params.append(action)

        if actor_email:
            conditions.append("LOWER(actor_email) = %s")
            params.append(actor_email.lower())

        if target_email:
            conditions.append("LOWER(target_email) = %s")
            params.append(target_email.lower())

        if department:
            conditions.append("department_slug = %s")
            params.append(department)

        if start_date:
            conditions.append("created_at >= %s")
            params.append(start_date)

        if end_date:
            conditions.append("created_at <= %s")
            params.append(end_date)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        params.extend([limit, offset])

        try:
            with get_db_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute(f"""
                    SELECT id, action, actor_email, target_email, department_slug,
                           old_value, new_value, reason,
                           ip_address::text as ip_address, metadata, created_at
                    FROM {SCHEMA}.audit_log
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, params)

                rows = cur.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"[Audit] Query failed: {e}")
            return []

    def count_log(
        self,
        action: Optional[str] = None,
        actor_email: Optional[str] = None,
        target_email: Optional[str] = None,
        department: Optional[str] = None
    ) -> int:
        """Count audit entries matching filters (for pagination)."""
        conditions = []
        params = []

        if action:
            conditions.append("action = %s")
            params.append(action)

        if actor_email:
            conditions.append("LOWER(actor_email) = %s")
            params.append(actor_email.lower())

        if target_email:
            conditions.append("LOWER(target_email) = %s")
            params.append(target_email.lower())

        if department:
            conditions.append("department_slug = %s")
            params.append(department)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                    SELECT COUNT(*) FROM {SCHEMA}.audit_log
                    WHERE {where_clause}
                """, params)
                return cur.fetchone()[0]

        except Exception as e:
            logger.error(f"[Audit] Count failed: {e}")
            return 0


def get_audit_service() -> AuditService:
    """Get singleton AuditService instance."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
