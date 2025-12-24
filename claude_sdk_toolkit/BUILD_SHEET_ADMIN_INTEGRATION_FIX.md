# BUILD SHEET: Admin Integration Fix (Option B)

## Overview
**Priority:** P0 - Critical  
**Estimated Time:** 4-6 hours  
**Based On:** ADMIN_INTEGRATION_BATTLE_PLAN.md recon findings

### What This Fixes
- 14 broken observability endpoints (traces, logs, alerts)
- 2 legacy 501 stubs causing console errors (departments, stats)
- Route path duplication issue (/traces/traces → /traces)
- Unlocks 3 blocked admin pages (Traces, Logs, Alerts)

---

## TASK 1: Verify core/database.py Exists

**Check if previous deployment worked:**

```bash
# SSH into Railway or check logs
cat core/database.py
```

If file exists, skip to Task 2. If not, create it:

**File:** `core/database.py`

```python
"""
Database Pool Manager
Centralized connection pooling for observability routes.
"""

import asyncpg
import os
from typing import Optional
from contextlib import asynccontextmanager

_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> asyncpg.Pool:
    """Initialize the database connection pool."""
    global _pool
    if _pool is None:
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            _pool = await asyncpg.create_pool(
                database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
        else:
            # Fallback to individual params
            _pool = await asyncpg.create_pool(
                host=os.environ.get("DB_HOST", "localhost"),
                port=int(os.environ.get("DB_PORT", 5432)),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", ""),
                database=os.environ.get("DB_NAME", "enterprise_bot"),
                min_size=2,
                max_size=10,
                command_timeout=60
            )
    return _pool


async def get_db_pool() -> asyncpg.Pool:
    """Get the database connection pool, initializing if needed."""
    global _pool
    if _pool is None:
        await init_db_pool()
    return _pool


async def close_db_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection():
    """Context manager for database connections."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        yield conn
```

---

## TASK 2: Fix Route Path Duplication

The routes have doubled paths like `/api/admin/traces/traces`. Fix by removing the duplicate path segment in the route decorators.

### File: `auth/tracing_routes.py`

**Find all route decorators and remove the duplicate:**

```python
# BEFORE (wrong):
@router.get("/traces")
@router.get("/traces/{trace_id}")
@router.get("/traces/stats/summary")

# AFTER (correct):
@router.get("/")
@router.get("/{trace_id}")
@router.get("/stats/summary")
```

**Full file edit - replace route decorators:**

```python
# Line ~20: Change from
@router.get("/traces")
async def list_traces(...):

# To:
@router.get("/")
async def list_traces(...):


# Line ~45: Change from  
@router.get("/traces/{trace_id}")
async def get_trace(...):

# To:
@router.get("/{trace_id}")
async def get_trace(...):


# Line ~70: Change from
@router.get("/traces/stats/summary")
async def get_trace_stats(...):

# To:
@router.get("/stats/summary")
async def get_trace_stats(...):
```

### File: `auth/logging_routes.py`

**Same pattern - remove duplicate path segment:**

```python
# Change from:
@router.get("/logs")
@router.get("/logs/{log_id}")
@router.get("/logs/stats/levels")
@router.websocket("/logs/stream")

# To:
@router.get("/")
@router.get("/{log_id}")
@router.get("/stats/levels")
@router.websocket("/stream")
```

### File: `auth/alerting_routes.py`

**Same pattern:**

```python
# Change from:
@router.get("/rules")
@router.post("/rules")
@router.get("/rules/{rule_id}")
@router.put("/rules/{rule_id}")
@router.delete("/rules/{rule_id}")
@router.get("/alerts")
@router.post("/alerts/{alert_id}/acknowledge")

# These should already be correct (no /alerts prefix in decorator)
# But verify the paths match what frontend expects
```

---

## TASK 3: Fix 501 Stub Endpoints

These two endpoints cause console spam. Replace stubs with working implementations.

### File: `auth/admin_routes.py`

**Find and replace the `/departments` endpoint:**

```python
# FIND (around line 850-860):
@router.get("/departments")
async def list_departments():
    """List all departments."""
    return JSONResponse(
        status_code=501,
        content={"error": "Not implemented - departments table removed in migration"}
    )

# REPLACE WITH:
@router.get("/departments")
async def list_departments():
    """List all departments (static list post-migration)."""
    # Static departments after 2-table schema migration
    STATIC_DEPARTMENTS = [
        {"slug": "credit", "name": "Credit Department", "description": "Credit and collections"},
        {"slug": "sales", "name": "Sales Department", "description": "Sales operations"},
        {"slug": "warehouse", "name": "Warehouse", "description": "Warehouse operations"},
        {"slug": "accounting", "name": "Accounting", "description": "Financial operations"},
        {"slug": "hr", "name": "Human Resources", "description": "HR operations"},
        {"slug": "it", "name": "IT Department", "description": "Technology operations"},
    ]
    return {"departments": STATIC_DEPARTMENTS}
```

**Find and replace the `/stats` endpoint:**

```python
# FIND (around line 870-880):
@router.get("/stats")
async def get_admin_stats():
    """Get admin dashboard statistics."""
    return JSONResponse(
        status_code=501,
        content={"error": "Not implemented - stats query needs update for new schema"}
    )

# REPLACE WITH:
@router.get("/stats")
async def get_admin_stats(user: dict = Depends(require_admin)):
    """Get admin dashboard statistics."""
    from core.database import get_db_pool
    
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # User counts
            total_users = await conn.fetchval("SELECT COUNT(*) FROM enterprise.users")
            active_users = await conn.fetchval("SELECT COUNT(*) FROM enterprise.users WHERE is_active = true")
            super_users = await conn.fetchval("SELECT COUNT(*) FROM enterprise.users WHERE is_super_user = true")
            
            # Recent activity (last 24h)
            recent_logins = await conn.fetchval("""
                SELECT COUNT(*) FROM enterprise.users 
                WHERE last_login_at > NOW() - INTERVAL '24 hours'
            """)
            
            # Audit events today
            audit_today = await conn.fetchval("""
                SELECT COUNT(*) FROM enterprise.audit_log 
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            
            return {
                "users": {
                    "total": total_users,
                    "active": active_users,
                    "super_users": super_users,
                    "recent_logins_24h": recent_logins
                },
                "audit": {
                    "events_24h": audit_today
                },
                "departments": {
                    "count": 6  # Static post-migration
                }
            }
    except Exception as e:
        return {"error": str(e), "users": {"total": 0}, "audit": {"events_24h": 0}}
```

---

## TASK 4: Fix Alert Engine Table References

The alert routes may reference wrong table names. Verify and fix.

### File: `auth/alerting_routes.py`

**Check table references - should be:**
- `enterprise.alert_rules` (not `alerts.rules`)
- `enterprise.alerts` (not `alerts.instances`)
- `enterprise.alert_instances` (this also exists - pick one or merge)

**If queries fail, update them to match actual schema:**

```python
# Correct table references:
SELECT * FROM enterprise.alert_rules ...
SELECT * FROM enterprise.alerts ...

# NOT:
SELECT * FROM alerts.rules ...  # Wrong schema
SELECT * FROM alert_rules ...   # Missing schema prefix
```

---

## TASK 5: Verify Observability Route Imports

Each route file should import from `core.database`:

### File: `auth/tracing_routes.py` (top of file)
```python
from core.database import get_db_pool
```

### File: `auth/logging_routes.py` (top of file)
```python
from core.database import get_db_pool
```

### File: `auth/alerting_routes.py` (top of file)
```python
from core.database import get_db_pool
```

**If they import from somewhere else, update to `core.database`.**

---

## TASK 6: Test All Endpoints

After deployment, run these tests:

```bash
BASE="https://lucky-love-production.up.railway.app"

# 1. Health check (should already work)
curl $BASE/health/deep | jq

# 2. Fixed 501 stubs (should return data now)
curl $BASE/api/admin/departments | jq
curl $BASE/api/admin/stats -H "Authorization: Bearer $TOKEN" | jq

# 3. Traces (should return [] not 500)
curl $BASE/api/admin/traces | jq

# 4. Logs (should return [] not 500)  
curl $BASE/api/admin/logs | jq

# 5. Alerts (should return data structure not 500)
curl $BASE/api/admin/alerts | jq
curl $BASE/api/admin/alerts/rules | jq
```

**Expected Results:**
- `/api/admin/departments` → `{"departments": [...]}`
- `/api/admin/stats` → `{"users": {...}, "audit": {...}}`
- `/api/admin/traces` → `[]` or `{"traces": []}`
- `/api/admin/logs` → `[]` or `{"logs": []}`
- `/api/admin/alerts` → `{"alerts": [], "rules": []}` or similar

---

## COMPLETION CHECKLIST

- [ ] `core/database.py` exists and exports `get_db_pool`
- [ ] `auth/tracing_routes.py` - route paths fixed (no /traces/traces)
- [ ] `auth/logging_routes.py` - route paths fixed (no /logs/logs)
- [ ] `auth/alerting_routes.py` - route paths verified
- [ ] `auth/admin_routes.py` - /departments returns static list
- [ ] `auth/admin_routes.py` - /stats returns real data
- [ ] All observability routes import from `core.database`
- [ ] No 501 errors in browser console
- [ ] No 500 errors on observability endpoints
- [ ] Traces page loads (even if empty)
- [ ] Logs page loads (even if empty)
- [ ] Alerts page loads (even if empty)

---

## FILES CHANGED

| File | Action | Lines |
|------|--------|-------|
| `core/database.py` | VERIFY/CREATE | ~50 |
| `auth/tracing_routes.py` | EDIT routes | ~10 |
| `auth/logging_routes.py` | EDIT routes | ~10 |
| `auth/alerting_routes.py` | VERIFY | ~5 |
| `auth/admin_routes.py` | EDIT 2 endpoints | ~50 |

---

## ROLLBACK

If anything breaks:
```bash
git checkout HEAD~1 -- auth/admin_routes.py
git checkout HEAD~1 -- auth/tracing_routes.py
git checkout HEAD~1 -- auth/logging_routes.py
git checkout HEAD~1 -- auth/alerting_routes.py
```

---

## SUCCESS CRITERIA

After this build:
1. ✅ Zero 501 errors in browser console
2. ✅ Zero 500 errors on admin pages
3. ✅ All 8 admin pages load without errors
4. ✅ Traces/Logs/Alerts pages show empty state (not error state)
5. ✅ System health continues working
6. ✅ Nerve center displays stats from /api/admin/stats

---

**END OF BUILD SHEET**
