# Feature Build Sheet: Audit Logging

**Priority:** P1  
**Estimated Effort:** 8-10 hours  
**Dependencies:** None

---

## 1. OVERVIEW

### User Story
> As an admin, I want to see who accessed what department data and what permission changes were made so that I can maintain compliance and investigate issues.

### Acceptance Criteria
- [ ] `enterprise.audit_log` table exists with proper indexes
- [ ] AuditService class provides `log_event()` and `query_log()` methods
- [ ] All admin actions (grant, revoke, promote) write to audit log
- [ ] GET `/api/admin/audit` returns paginated, filterable audit entries
- [ ] Frontend audit page displays real data (not 501 error)

---

## 2. DATABASE CHANGES

### Migration File: `db/migrations/004_audit_log.sql`

```sql
-- Migration 004: Create audit_log table
-- Recreates deleted access_audit_log with enhanced schema

CREATE TABLE IF NOT EXISTS enterprise.audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action VARCHAR(100) NOT NULL,
    actor_email VARCHAR(255),
    actor_user_id UUID REFERENCES enterprise.users(id),
    target_email VARCHAR(255),
    target_user_id UUID REFERENCES enterprise.users(id),
    department_slug VARCHAR(50),
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    ip_address INET,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX idx_audit_action ON enterprise.audit_log(action);
CREATE INDEX idx_audit_actor ON enterprise.audit_log(actor_email);
CREATE INDEX idx_audit_target ON enterprise.audit_log(target_email);
CREATE INDEX idx_audit_department ON enterprise.audit_log(department_slug);
CREATE INDEX idx_audit_created ON enterprise.audit_log(created_at DESC);

-- Composite index for filtered + paginated queries
CREATE INDEX idx_audit_filter_combo ON enterprise.audit_log(action, department_slug, created_at DESC);

-- Comment for documentation
COMMENT ON TABLE enterprise.audit_log IS 'Audit trail for admin actions and data access - created 2024-12-23';
```

---

## 3. BACKEND CHANGES

### New File: `auth/audit_service.py`

```python
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
from auth_service import get_db_connection

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
```

---

### File: `admin_routes.py` - Modifications

#### Add Import (near top, around line 25)
```python
from auth.audit_service import get_audit_service
```

#### Replace Audit Endpoint (Lines 639-660)
```python
@admin_router.get("/audit", response_model=APIResponse)
async def get_audit_log(
    x_user_email: str = Header(None, alias="X-User-Email"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    target_email: Optional[str] = Query(None, description="Filter by target user email"),
    department: Optional[str] = Query(None, description="Filter by department slug"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    View audit log entries.
    
    Permissions:
    - Super users: See all entries
    - Dept heads: See entries for their departments only
    """
    if not x_user_email:
        raise HTTPException(401, "X-User-Email header required")
    
    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)
    
    if not requester:
        raise HTTPException(401, "User not found")
    
    # Require admin access
    if not requester.is_super_user and not requester.dept_head_for:
        raise HTTPException(403, "Admin access required")
    
    # Non-super users can only see their departments
    if not requester.is_super_user and department:
        if department not in (requester.dept_head_for or []):
            raise HTTPException(403, f"No access to {department} audit log")
    
    # If non-super user with no department filter, limit to their departments
    effective_department = department
    if not requester.is_super_user and not department:
        # They can only see their own departments - take first one
        if requester.dept_head_for:
            effective_department = requester.dept_head_for[0]
        else:
            raise HTTPException(403, "No departments to view")
    
    audit = get_audit_service()
    entries = audit.query_log(
        action=action,
        target_email=target_email,
        department=effective_department,
        limit=limit,
        offset=offset
    )
    total = audit.count_log(
        action=action,
        target_email=target_email,
        department=effective_department
    )
    
    return APIResponse(
        success=True,
        data={
            "entries": entries,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    )
```

#### Add Audit Calls to Admin Actions

After each `logger.info()` call in admin actions, add an audit log call:

**Line ~387 (after access grant logger.info):**
```python
        logger.info(f"[Admin] {requester.email} {action} for {target_email} to {request.department_slug}")
        
        # Audit log
        audit = get_audit_service()
        audit.log_event(
            action="department_access_grant" if action == "granted access" else "dept_head_promote",
            actor_email=requester.email,
            target_email=target_email,
            department_slug=request.department_slug,
            reason=request.reason
        )
```

**Line ~434 (after access revoke logger.info):**
```python
        logger.info(f"[Admin] {requester.email} revoked {request.department_slug} access from {target_email}")
        
        # Audit log
        audit = get_audit_service()
        audit.log_event(
            action="department_access_revoke",
            actor_email=requester.email,
            target_email=target_email,
            department_slug=request.department_slug,
            reason=request.reason
        )
```

**Line ~494 (after dept head promote logger.info):**
```python
        logger.info(f"[Admin] {requester.email} promoted {request.target_email} to dept_head for {request.department}")
        
        # Audit log
        audit = get_audit_service()
        audit.log_event(
            action="dept_head_promote",
            actor_email=requester.email,
            target_email=request.target_email,
            department_slug=request.department,
            reason=request.reason
        )
```

**Line ~537 (after dept head revoke logger.info):**
```python
        logger.info(f"[Admin] {requester.email} revoked dept_head from {request.target_email} for {request.department}")
        
        # Audit log
        audit = get_audit_service()
        audit.log_event(
            action="dept_head_revoke",
            actor_email=requester.email,
            target_email=request.target_email,
            department_slug=request.department,
            reason=request.reason
        )
```

**Line ~586 (after super user promote logger.info):**
```python
        logger.info(f"[Admin] {requester.email} promoted {request.target_email} to super_user")
        
        # Audit log
        audit = get_audit_service()
        audit.log_event(
            action="super_user_promote",
            actor_email=requester.email,
            target_email=request.target_email,
            reason=request.reason
        )
```

**Line ~623 (after super user revoke logger.info):**
```python
        logger.info(f"[Admin] {requester.email} revoked super_user from {request.target_email}")
        
        # Audit log
        audit = get_audit_service()
        audit.log_event(
            action="super_user_revoke",
            actor_email=requester.email,
            target_email=request.target_email,
            reason=request.reason
        )
```

---

## 4. FRONTEND CHANGES

**None required.** Frontend audit page is complete and expects this API shape.

Verify at: `frontend/src/routes/admin/audit/+page.svelte`

---

## 5. INTEGRATION CHECKLIST

### Database
- [ ] Create migration file `db/migrations/004_audit_log.sql`
- [ ] Run migration against Azure PostgreSQL
- [ ] Verify table exists: `SELECT * FROM enterprise.audit_log LIMIT 1;`

### Backend
- [ ] Create `auth/audit_service.py`
- [ ] Add import to `admin_routes.py`
- [ ] Replace audit endpoint (L639-660)
- [ ] Add audit calls after each logger.info (6 locations)
- [ ] Test endpoint returns data

### Frontend
- [ ] Verify `/admin/audit` page loads without 501 error
- [ ] Test filters work
- [ ] Test pagination works

---

## 6. TESTING COMMANDS

```bash
# Run migration
psql $DATABASE_URL -f db/migrations/004_audit_log.sql

# Test audit endpoint (empty at first)
curl -X GET "http://localhost:8000/api/admin/audit?limit=10" \
  -H "X-User-Email: admin@driscollfoods.com"

# Trigger an auditable action (grant access)
curl -X POST "http://localhost:8000/api/admin/access/grant" \
  -H "Content-Type: application/json" \
  -H "X-User-Email: admin@driscollfoods.com" \
  -d '{"target_email": "test@driscollfoods.com", "department_slug": "warehouse"}'

# Verify audit entry created
curl -X GET "http://localhost:8000/api/admin/audit?limit=10" \
  -H "X-User-Email: admin@driscollfoods.com"

# Expected response:
{
  "success": true,
  "data": {
    "entries": [
      {
        "id": "uuid",
        "action": "department_access_grant",
        "actor_email": "admin@driscollfoods.com",
        "target_email": "test@driscollfoods.com",
        "department_slug": "warehouse",
        "created_at": "2024-12-23T..."
      }
    ],
    "total": 1,
    "limit": 10,
    "offset": 0
  }
}

# Database verification
psql -c "SELECT action, actor_email, target_email, department_slug, created_at FROM enterprise.audit_log ORDER BY created_at DESC LIMIT 5;"
```

---

## 7. AGENT EXECUTION BLOCK

```
FEATURE BUILD: Audit Logging

TASK 1 - Database:
- Create file: db/migrations/004_audit_log.sql [paste SQL from Section 2]
- Run: psql $DATABASE_URL -f db/migrations/004_audit_log.sql
- Verify: SELECT * FROM enterprise.audit_log LIMIT 1;

TASK 2 - Audit Service:
- Create file: auth/audit_service.py [paste code from Section 3]
- Verify syntax: python -c "from auth.audit_service import get_audit_service"

TASK 3 - Admin Routes:
- Edit admin_routes.py:
  - Add import near top: from auth.audit_service import get_audit_service
  - Replace lines 639-660 with new endpoint
  - Add audit calls after lines: 387, 434, 494, 537, 586, 623

TASK 4 - Verification:
- Start server: uvicorn main:app --reload
- Test GET /api/admin/audit (should return empty entries list)
- Perform an admin action (grant access)
- Verify audit entry appears in GET /api/admin/audit
- Check frontend /admin/audit page loads

COMPLETION CRITERIA:
- No 501 error on /api/admin/audit
- Audit entries persist in database
- Frontend displays audit log
- All 6 admin actions write audit entries
```

---

## 8. ROLLBACK PLAN

```sql
-- Database rollback
DROP TABLE IF EXISTS enterprise.audit_log;
```

```bash
# Git rollback
git checkout HEAD -- admin_routes.py
rm auth/audit_service.py
rm db/migrations/004_audit_log.sql
```
