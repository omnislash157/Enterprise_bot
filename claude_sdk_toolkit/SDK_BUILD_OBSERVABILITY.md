# SDK AGENT BUILD: Observability Infrastructure Fix

## CONTEXT
Database tables are being created by user in Azure CLI. This build focuses on backend code changes only.

**Problem:** Observability dashboards show zero data
**Root Causes:** Missing `core/database.py`, wrong route prefixes, no tracing instrumentation

---

## TASK 1: Create core/database.py (NEW FILE)

**Action:** Create new file `core/database.py`

```python
"""
Database Pool Manager
Provides centralized database connection pooling for observability routes.

Version: 1.0.0
"""

import asyncpg
from typing import Optional
from contextlib import asynccontextmanager
from core.config_loader import get_config

_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> asyncpg.Pool:
    """Initialize the database connection pool."""
    global _pool
    if _pool is None:
        config = get_config()
        db_config = config.get("database", {})
        
        _pool = await asyncpg.create_pool(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 5432),
            user=db_config.get("user", "postgres"),
            password=db_config.get("password", ""),
            database=db_config.get("database", "enterprise_bot"),
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

## TASK 2: Fix Route Prefixes (3 files)

### File: auth/tracing_routes.py
**Find:**
```python
router = APIRouter(prefix="/api/observability/traces", tags=["tracing"])
```
**Replace with:**
```python
router = APIRouter(prefix="/api/admin/traces", tags=["tracing"])
```

### File: auth/logging_routes.py
**Find:**
```python
router = APIRouter(prefix="/api/observability/logs", tags=["logging"])
```
**Replace with:**
```python
router = APIRouter(prefix="/api/admin/logs", tags=["logging"])
```

### File: auth/alerting_routes.py
**Find:**
```python
router = APIRouter(prefix="/api/observability/alerts", tags=["alerting"])
```
**Replace with:**
```python
router = APIRouter(prefix="/api/admin/alerts", tags=["alerting"])
```

---

## TASK 3: Add /health/deep Endpoint

**File:** `core/main.py`

**Action:** Add this endpoint near the existing `/health` endpoint (around line 515):

```python
@app.get("/health/deep")
async def deep_health_check():
    """Comprehensive health check including observability stack."""
    from datetime import datetime
    
    checks = {}
    overall_status = "healthy"
    
    # Database check
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = {"status": "healthy"}
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)}
        overall_status = "unhealthy"
    
    # Redis check
    try:
        from core.cache import get_redis
        redis = await get_redis()
        if redis:
            await redis.ping()
            checks["redis"] = {"status": "healthy"}
        else:
            checks["redis"] = {"status": "warning", "message": "Redis not configured"}
    except Exception as e:
        checks["redis"] = {"status": "error", "message": str(e)}
        if overall_status == "healthy":
            overall_status = "degraded"
    
    # Observability tables check
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'enterprise' 
                AND table_name IN ('traces', 'trace_spans', 'structured_logs', 'alert_rules', 'alerts')
            """)
            table_names = [r['table_name'] for r in tables]
            expected = {'traces', 'trace_spans', 'structured_logs', 'alert_rules', 'alerts'}
            missing = expected - set(table_names)
            if missing:
                checks["observability_tables"] = {"status": "error", "missing": list(missing)}
                overall_status = "unhealthy"
            else:
                checks["observability_tables"] = {"status": "healthy", "count": len(table_names)}
    except Exception as e:
        checks["observability_tables"] = {"status": "error", "message": str(e)}
        overall_status = "unhealthy"
    
    # Metrics collector check
    try:
        if 'metrics_collector' in dir():
            checks["metrics"] = {"status": "healthy"}
        else:
            checks["metrics"] = {"status": "warning", "message": "Metrics collector not in scope"}
    except Exception as e:
        checks["metrics"] = {"status": "error", "message": str(e)}
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }
```

---

## TASK 4: Update Shutdown Handler

**File:** `core/main.py`

**Find:** The `@app.on_event("shutdown")` handler

**Add** at the beginning of the shutdown function:

```python
# Close database pool
try:
    from core.database import close_db_pool
    await close_db_pool()
    logger.info("[SHUTDOWN] Database pool closed")
except Exception as e:
    logger.error(f"[SHUTDOWN] Database cleanup error: {e}")
```

---

## TASK 5: Add Tracing Import to main.py

**File:** `core/main.py`

**Find:** Import section at top of file

**Add:**
```python
from core.tracing import start_trace, create_span
```

**Note:** If this import fails, check that `core/tracing.py` exports these functions. The tracing integration into WebSocket/Twin/RAG is Phase 2 - skip if time constrained. The critical path is Tasks 1-4.

---

## VERIFICATION

After completing tasks, run these checks:

```bash
# 1. Check for import errors on startup
# Watch Railway logs for ModuleNotFoundError

# 2. Test deep health
curl https://cogtwin.up.railway.app/health/deep

# Expected: {"status": "healthy", "checks": {...}}

# 3. Test traces endpoint (should return empty array, not error)
curl https://cogtwin.up.railway.app/api/admin/traces

# Expected: [] (empty array, not 500 error)

# 4. Test logs endpoint
curl https://cogtwin.up.railway.app/api/admin/logs

# Expected: [] (empty array, not 500 error)

# 5. Test alerts endpoint  
curl https://cogtwin.up.railway.app/api/admin/alerts

# Expected: [] or {"rules": [], "alerts": []}
```

---

## COMPLETION CRITERIA

- [ ] `core/database.py` exists and exports `get_db_pool`, `close_db_pool`
- [ ] Route prefixes changed in all 3 files
- [ ] `/health/deep` endpoint returns status
- [ ] Shutdown handler closes DB pool
- [ ] No import errors in Railway logs
- [ ] Observability endpoints return 200 (even if empty data)

---

## PRIORITY ORDER

If time-constrained, complete in this order:
1. **CRITICAL:** Task 1 (database.py) - unblocks all routes
2. **CRITICAL:** Task 2 (route prefixes) - frontend can't find endpoints
3. **HIGH:** Task 3 (health/deep) - validates the fix
4. **MEDIUM:** Task 4 (shutdown) - prevents connection leaks
5. **LOW:** Task 5 (tracing import) - prep for Phase 2

---

## FILES CHANGED

| File | Action |
|------|--------|
| `core/database.py` | CREATE |
| `auth/tracing_routes.py` | EDIT (prefix) |
| `auth/logging_routes.py` | EDIT (prefix) |
| `auth/alerting_routes.py` | EDIT (prefix) |
| `core/main.py` | EDIT (add endpoint + shutdown) |

---

**END OF BUILD**
