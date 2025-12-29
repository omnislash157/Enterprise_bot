# OBSERVABILITY GAP ANALYSIS REPORT
**Mission:** Identify why observability dashboards show zero data
**Date:** 2024-12-23
**Status:** ✅ COMPLETE

---

## EXECUTIVE SUMMARY

The observability suite is **architecturally sound but broken at multiple layers**. Root causes identified:

### 🔴 CRITICAL GAPS
1. **Database tables missing** - Migrations for `traces`, `structured_logs`, `alerts` were deleted before deployment
2. **Missing database module** - All observability routes import non-existent `core/database.py`
3. **Zero instrumentation** - Tracing infrastructure exists but is never called in request flow
4. **Silent failures** - Observability init errors are logged but system continues, causing data loss

### 🟡 SECONDARY ISSUES
1. **Metrics are ephemeral** - In-memory only, lost on restart
2. **Auth events not audited** - Login/logout not logged
3. **Path mismatches** - Frontend expects `/api/admin/*`, backend serves `/api/observability/*`
4. **No deep health check** - Basic `/health` doesn't validate observability stack

### ✅ WHAT'S WORKING
1. **Metrics collector** - Fully instrumented and operational (in-memory)
2. **Analytics service** - Complete, working, with data
3. **Audit logging** - Works for admin actions
4. **Frontend** - Well-built, waiting for backend data

---

## GAP SUMMARY TABLE

| Layer | Component | Status | Root Cause | Impact |
|-------|-----------|--------|------------|--------|
| **Database** | Observability tables | 🔴 Missing | Migrations deleted | All persistence fails |
| **Database** | `core/database.py` module | 🔴 Missing | Never created | Endpoints crash on call |
| **Middleware** | Tracing middleware | 🔴 Not registered | Never integrated | Zero trace data |
| **Middleware** | Metrics middleware | 🟢 Working | Manual timing | Partial data only |
| **Instrumentation** | Trace spans | 🔴 Never called | Not integrated | Zero span data |
| **Instrumentation** | Structured logging | 🟡 Ready but silent | Tables missing | Logs buffer, never flush |
| **Instrumentation** | Audit logging | 🟢 Partial | Auth events missing | Admin only, not auth |
| **Instrumentation** | Metrics collector | 🟢 Working | In-memory only | Ephemeral data |
| **API Endpoints** | Analytics | 🟢 Working | None | Functional |
| **API Endpoints** | Metrics | 🟢 Working | None | Functional |
| **API Endpoints** | Traces | 🔴 Broken | Missing db module | Import error |
| **API Endpoints** | Logs | 🔴 Broken | Missing db module | Import error |
| **API Endpoints** | Alerts | 🔴 Broken | Missing db module | Import error |
| **Frontend** | Contract alignment | 🟢 Good | None | Ready for data |
| **Lifecycle** | Startup graceful degradation | 🟡 Too graceful | Silent failures | Masks issues |

---

## DETAILED FINDINGS

## 1. DATABASE STATE

### Missing Tables

**The following tables do NOT exist in the database:**

```sql
-- Deleted migration: 008_tracing_tables.sql
enterprise.traces (trace_id, entry_point, endpoint, user_email, start_time, end_time, duration_ms, status, ...)
enterprise.trace_spans (span_id, trace_id, parent_span_id, operation_name, start_time, end_time, duration_ms, ...)

-- Deleted migration: 009_structured_logs.sql
enterprise.structured_logs (id, timestamp, level, logger_name, message, trace_id, span_id, user_email, ...)

-- Deleted migration: 010_alert_tables.sql
enterprise.alerts (id, rule_id, severity, message, triggered_at, status, ...)
enterprise.alert_rules (id, name, metric_type, condition, threshold, enabled, ...)
```

**Evidence:** Git status shows these migrations were created but deleted:
```
D claude_sdk_toolkit/migrations/008_tracing_tables.sql
D claude_sdk_toolkit/migrations/009_structured_logs.sql
D claude_sdk_toolkit/migrations/010_alert_tables.sql
```

**Existing Table:**
```sql
-- Migration 004: EXISTS
enterprise.audit_log (id, action, actor_email, target_email, department_slug, created_at, ...)
```

**Impact:**
- Trace collector flushes to missing table → silent failure
- Structured logging flushes to missing table → silent failure
- Alert engine queries missing tables → endpoint crashes
- Frontend receives empty arrays (if endpoints work) or errors

**File Citations:**
- Expected schema: `core/tracing.py:256-285`, `core/structured_logging.py:159-170`
- Existing migration: `db/migrations/004_audit_log.sql`

---

### Missing Database Module

**All observability route handlers import:**
```python
from core.database import get_db_pool
```

**But this file does NOT exist:**
- ❌ `C:\Users\mthar\projects\enterprise_bot\core\database.py` - File not found

**Files affected (14 import statements):**
- `auth/tracing_routes.py:8` - 3 endpoints crash
- `auth/logging_routes.py:8` - 4 endpoints crash
- `auth/alerting_routes.py:8` - 7 endpoints crash

**Impact:**
- When frontend calls `/api/observability/traces` → ModuleNotFoundError
- When frontend calls `/api/observability/logs` → ModuleNotFoundError
- When frontend calls `/api/observability/alerts/rules` → ModuleNotFoundError

**The correct pattern exists** in `core/enterprise_rag.py`:
```python
from core.enterprise_rag import EnterpriseRAGRetriever
config = get_config()
rag = EnterpriseRAGRetriever(config)
db_pool = await rag._get_pool()
```

This pattern is used in `main.py:466-469` for observability initialization, but route handlers use a different (non-existent) import.

**File Citations:**
- Import errors: `auth/tracing_routes.py:8`, `auth/logging_routes.py:8`, `auth/alerting_routes.py:8`
- Correct pattern: `core/main.py:466-469`, `core/enterprise_rag.py:142-157`

---

## 2. MIDDLEWARE & INSTRUMENTATION

### Metrics Middleware
**Status:** 🟢 WORKING (partial)

**Location:** `core/main.py:342-355`

**Implementation:**
```python
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"

    endpoint = request.url.path
    is_error = response.status_code >= 400
    metrics_collector.record_request(endpoint, elapsed_ms, error=is_error)

    return response
```

**What it does:**
- ✅ Records request count per endpoint
- ✅ Records latency per endpoint
- ✅ Tracks error rate
- ❌ Does NOT create trace spans
- ❌ Does NOT set trace context

**Gap:** Manual timing only. Should use dedicated MetricsMiddleware class with trace integration.

---

### Tracing Middleware
**Status:** 🔴 MISSING

**Expected:** Dedicated TracingMiddleware that:
1. Creates trace context at request entry: `async with start_trace(entry_point='http', endpoint=path, method=method, user_email=email)`
2. Propagates trace_id via context vars
3. Automatically creates root span for request

**Actual:** NO tracing middleware registered

**File Citations:**
- Expected location: `core/main.py:329-341` (middleware registration block)
- Tracing infrastructure exists: `core/tracing.py:330-370` (start_trace function)

---

### Span Instrumentation
**Status:** 🔴 ZERO USAGE

**Tracing infrastructure is complete** (core/tracing.py):
- ✅ `start_trace()` - async context manager
- ✅ `create_span()` - async context manager
- ✅ TraceCollector - singleton with flush loop
- ✅ Database INSERT queries prepared

**But it's NEVER CALLED anywhere in the codebase.**

**Critical missing instrumentation points:**

#### WebSocket Handler (core/main.py:806-1277)
**Expected:**
```python
async with start_trace(
    entry_point='websocket',
    user_email=user_email,
    session_id=session_id,
    department=department
):
    # ... entire handler ...
```

**Actual:** No tracing

---

#### EnterpriseTwin.think_streaming() (core/enterprise_twin.py:509-598)
**Expected:**
```python
async with create_span('rag_retrieve', tags={'department': department}):
    chunks = await self.rag.search(...)

async with create_span('llm_generate', tags={'model': model}):
    async for chunk in self.client.messages.stream(...):
        # ...
```

**Actual:** No tracing (only logs and metrics)

---

#### EnterpriseRAG.search() (core/enterprise_rag.py:225-298)
**Expected:**
```python
async with create_span('embedding') as span:
    embedding = await self._generate_embedding(query)
    span.set_tag('model', 'text-embedding-3-small')

async with create_span('vector_search') as span:
    results = await conn.fetch("""SELECT ...""")
    span.set_tag('results', len(results))
```

**Actual:** No tracing (only metrics_collector calls)

---

**Search Results:**
```bash
# Only 3 files mention tracing functions:
1. core/tracing.py - Self-definition
2. core/structured_logging.py - Imports get_trace_id() for correlation
3. memory/reasoning_trace.py - Different tracing (CogTwin internal, not observability)
```

**Impact:** Frontend `/admin/traces` page shows zero data because no spans are ever created.

**File Citations:**
- Tracing API: `core/tracing.py:330-409`
- Missing integration points: `core/main.py:806`, `core/enterprise_twin.py:536,573`, `core/enterprise_rag.py:228,285`

---

### Structured Logging
**Status:** 🟡 READY BUT SILENT FAILURE

**Architecture:** Complete (core/structured_logging.py):
- ✅ DatabaseLogHandler - attaches to root logger
- ✅ Background flush thread (2s interval)
- ✅ Trace correlation via get_trace_id()
- ✅ Batch writes to enterprise.structured_logs

**Initialization:** `core/main.py:477`
```python
setup_structured_logging(db_pool)
logger.info("[STARTUP] Structured logging enabled")
```

**What happens at runtime:**
1. All `logger.info()`, `logger.error()` calls captured
2. Log records buffered in-memory queue
3. Background thread wakes every 2s
4. Attempts INSERT to `enterprise.structured_logs`
5. **Table doesn't exist** → Exception
6. Exception caught, printed to stdout (not logged)
7. Buffer keeps growing

**Impact:**
- Logs accumulate in memory
- Never persisted to database
- Frontend `/admin/logs` page shows zero data
- Silent failure - no visible error to user

**File Citations:**
- Handler implementation: `core/structured_logging.py:50-173`
- Initialization: `core/main.py:477`
- Expected table: Schema in INSERT statement at line 159-170

---

### Audit Logging
**Status:** 🟢 WORKING (partial)

**What's working:**
- ✅ Admin actions audited (grant/revoke access, promote/demote users)
- ✅ Synchronous DB writes to `enterprise.audit_log`
- ✅ Table exists and receives data
- ✅ Frontend audit page works

**What's missing:**
- ❌ Authentication events (login, logout, failed auth)
- ❌ Department switch events
- ❌ Query events (user messages)

**Integration points:**

**Working:**
- `auth/admin_routes.py:392-399` - Grant department access
- `auth/admin_routes.py:449-457` - Promote dept head
- `auth/admin_routes.py:519-527` - Promote super user
- `auth/admin_routes.py:572-580,631-639,677-685` - Revokes

**Missing:**
- `core/main.py:878` - WebSocket verify (should log login)
- `core/main.py:903,927` - Failed auth attempts
- `auth/auth_service.py` - No audit calls

**Recommendation:** Add audit calls for security events (login, logout, failed auth).

**File Citations:**
- Audit service: `auth/audit_service.py:58-134`
- Admin integration: `auth/admin_routes.py:28,392-685`
- Missing integration: `core/main.py:850-933`, `auth/auth_service.py`

---

### Metrics Collector
**Status:** 🟢 WORKING (in-memory)

**Architecture:**
- ✅ Singleton pattern
- ✅ Thread-safe with locks
- ✅ Ring buffers for recent data
- ✅ Tracks: HTTP requests, WebSocket connections, RAG queries, LLM calls, cache hits
- ✅ Returns health status (healthy/warning/degraded/critical)

**Integration points (all working):**
- `core/main.py:353` - HTTP request timing
- `core/main.py:808,839-1276,1243-1276` - WebSocket events
- `core/enterprise_rag.py:228,285,298` - RAG query tracking
- (LLM tracking appears to be missing - search found no record_llm calls)

**Gap:**
- **Metrics are ephemeral** - stored in-memory only
- On restart, all historical data is lost
- Should have background flush to `enterprise.metrics` table (which doesn't exist)

**What frontend sees:**
- ✅ Real-time metrics via WebSocket `/api/metrics/stream`
- ✅ Snapshot via HTTP `/api/metrics/snapshot`
- ❌ No historical trends (can't query past data)

**File Citations:**
- Metrics collector: `core/metrics_collector.py:67-352`
- Integration points: `core/main.py:353,808,839,1243`, `core/enterprise_rag.py:228,285,298`
- Frontend consumption: `frontend/src/lib/stores/metrics.ts:39-99`

---

## 3. API ENDPOINTS

### Path Mismatch

**Frontend expects:**
```
/api/admin/traces
/api/admin/logs
/api/admin/alerts
```

**Backend serves:**
```
/api/observability/traces
/api/observability/logs
/api/observability/alerts/instances
```

**Location:** `core/main.py:376-381`
```python
if OBSERVABILITY_LOADED:
    app.include_router(tracing_router, prefix="/api/observability", tags=["observability"])
    app.include_router(logging_router, prefix="/api/observability", tags=["observability"])
    app.include_router(alerting_router, prefix="/api/observability/alerts", tags=["observability"])
```

**Impact:**
- Frontend calls wrong paths → 404 Not Found
- OR frontend was updated to match backend paths (need to verify deployed frontend)

**Recommendation:** Change prefix to `/api/admin` to match frontend expectations.

---

### Endpoint Implementation Status

| Endpoint | Status | Data Source | Issue |
|----------|--------|-------------|-------|
| **Analytics** | | | |
| `/api/admin/analytics/overview` | ✅ Working | PostgreSQL | None |
| `/api/admin/analytics/queries` | ✅ Working | PostgreSQL | None |
| `/api/admin/analytics/categories` | ✅ Working | PostgreSQL | None |
| `/api/admin/analytics/departments` | ✅ Working | PostgreSQL | None |
| `/api/admin/analytics/errors` | ✅ Working | PostgreSQL | None |
| `/api/admin/analytics/realtime` | ✅ Working | PostgreSQL | None |
| **Metrics** | | | |
| `/api/metrics/snapshot` | ✅ Working | In-memory | None |
| `/api/metrics/health` | ✅ Working | In-memory | None |
| `/api/metrics/stream` (WebSocket) | ✅ Working | In-memory | None |
| **Health** | | | |
| `/health` | ⚠️ Basic | Static | Doesn't check DB/Redis/observability |
| `/health/detailed` | ❌ Missing | - | Not implemented |
| **Traces** | | | |
| `/api/observability/traces` | 🔴 Broken | PostgreSQL | Missing core/database.py |
| `/api/observability/traces/{id}` | 🔴 Broken | PostgreSQL | Missing core/database.py |
| `/api/observability/traces/stats/summary` | 🔴 Broken | PostgreSQL | Missing core/database.py |
| **Logs** | | | |
| `/api/observability/logs` | 🔴 Broken | PostgreSQL | Missing core/database.py |
| `/api/observability/logs/{id}` | 🔴 Broken | PostgreSQL | Missing core/database.py |
| `/api/observability/logs/stream` (WebSocket) | 🔴 Broken | PostgreSQL | Missing core/database.py |
| **Alerts** | | | |
| `/api/observability/alerts/rules` | 🔴 Broken | PostgreSQL | Missing core/database.py |
| `/api/observability/alerts/instances` | 🔴 Broken | PostgreSQL | Missing core/database.py |

**File Citations:**
- Analytics routes: `auth/analytics_engine/analytics_routes.py:20-165`
- Metrics routes: `auth/metrics_routes.py:19-119`
- Health endpoint: `core/main.py:508-515`
- Tracing routes: `auth/tracing_routes.py:17-147`
- Logging routes: `auth/logging_routes.py:19-221`
- Alerting routes: `auth/alerting_routes.py:43-234`
- Missing import: `auth/tracing_routes.py:8`, `auth/logging_routes.py:8`, `auth/alerting_routes.py:8`

---

## 4. FRONTEND ANALYSIS

### Frontend Architecture
**Status:** 🟢 WELL-BUILT

**Stores:**
- ✅ `analytics.ts` - Fetches 6 analytics endpoints in parallel
- ✅ `metrics.ts` - WebSocket connection with auto-reconnect
- ✅ `observability.ts` - Handles traces, logs, alerts

**Pages:**
- ✅ `/admin/system` - System health + metrics charts
- ✅ `/admin/analytics` - Query trends, category breakdown, department stats
- ✅ `/admin/traces` - Trace list + waterfall viewer
- ✅ `/admin/logs` - Log explorer with real-time streaming
- ✅ `/admin/alerts` - Alert rules and active instances

**Components:**
- ✅ SystemHealthPanel - CPU, memory, disk, process stats
- ✅ RagPerformancePanel - RAG latency, cache hit rate, chunk count
- ✅ LlmCostPanel - LLM latency, tokens, cost, errors
- ✅ LineChart, DoughnutChart, BarChart - Chart.js wrappers

**Contract Alignment:**
- ✅ Analytics responses match expected shapes
- ✅ Metrics snapshot matches expected shape
- ✅ Observability responses match expected shapes
- ⚠️ Alert rules have extra fields (window_minutes, notification_channels, cooldown_minutes) that frontend ignores

**Error Handling:**
- ⚠️ Stores track errors but pages don't display them
- ⚠️ No loading skeletons (users see blank screens during load)
- ✅ Graceful degradation (null checks prevent crashes)

**File Citations:**
- Stores: `frontend/src/lib/stores/analytics.ts`, `metrics.ts`, `observability.ts`
- Pages: `frontend/src/routes/admin/system/+page.svelte`, `analytics/+page.svelte`, `traces/+page.svelte`, `logs/+page.svelte`, `alerts/+page.svelte`
- Components: `frontend/src/lib/components/admin/observability/*.svelte`

---

## 5. INITIALIZATION & LIFECYCLE

### Startup Sequence

**Location:** `core/main.py:390-486`

**Order:**
1. Config loader (line 399) - ✅ Works
2. Email whitelist (line 403) - ✅ Works (graceful fallback)
3. Twin router init (line 406) - ✅ Works
4. Redis cache (line 420) - ✅ Works (optional, graceful fallback to NoOpCache)
5. RAG connection pool (line 431) - ✅ Works (graceful on error)
6. Analytics service (line 445) - ✅ Works (graceful on error)
7. **Observability stack (line 462)** - ⚠️ **RISKY**

**Observability Init:**
```python
if OBSERVABILITY_LOADED:
    logger.info("[STARTUP] Initializing observability stack...")
    try:
        db_pool = await rag._get_pool()

        trace_collector.set_db_pool(db_pool)
        await trace_collector.start()
        logger.info("[STARTUP] Trace collector started")

        setup_structured_logging(db_pool)
        logger.info("[STARTUP] Structured logging enabled")

        alert_engine.set_db_pool(db_pool)
        await alert_engine.start()
        logger.info("[STARTUP] Alert engine started")
    except Exception as e:
        logger.error(f"[STARTUP] Observability init failed: {e}")
        # CONTINUES WITHOUT RAISING
```

**Problem:** If observability init fails (e.g., tables missing):
- Error is logged
- **System continues as if everything is fine**
- No traces collected (silent data loss)
- No logs persisted (silent data loss)
- No alerts evaluated (production issues undetected)

**Recommendation:** Make observability init failures LOUD (raise exception) or add health check that detects this.

---

### Background Tasks

**Running continuously:**

1. **Trace Collector Flush Loop**
   - File: `core/tracing.py:221-225`
   - Interval: 5 seconds
   - Action: Batch-write traces and spans to DB
   - Status: ✅ Working (but tables missing)

2. **Alert Engine Evaluation Loop**
   - File: `core/alerting.py:119-127`
   - Interval: 60 seconds
   - Action: Evaluate alert rules, fire notifications
   - Status: ✅ Working (but tables missing)

3. **Structured Logging Flush Thread**
   - File: `core/structured_logging.py:128-153`
   - Interval: 2 seconds
   - Action: Batch-write logs to DB
   - Status: ✅ Working (but table missing)

**All three tasks continue running even if DB writes fail.**

---

### Graceful Degradation

**Component Failure Modes:**

| Component | Failure Mode | Logged? | Continues? | Impact |
|-----------|--------------|---------|------------|--------|
| Config Loader | LOUD | Yes (ERROR) | No (exits) | Fatal |
| Redis Cache | GRACEFUL | Yes (WARN) | Yes (NoOpCache) | Performance loss |
| RAG Pool | GRACEFUL | Yes (WARN) | Yes | Degraded |
| Analytics | GRACEFUL | Yes (WARN) | Yes | Feature lost |
| **Trace Collector** | **SILENT** | **Yes (ERROR)** | **Yes** | **Data loss** |
| **Structured Logging** | **SILENT** | **Stdout only** | **Yes** | **Data loss** |
| **Alert Engine** | **SILENT** | **Yes (ERROR)** | **Yes** | **No alerts** |

**The observability stack is "too graceful" - it fails silently.**

---

### Health Check

**Current:** `GET /health`
```json
{
  "status": "ok",
  "app": "Enterprise RAG Bot",
  "timestamp": "2024-12-23T12:00:00Z",
  "engine_ready": true
}
```

**This does NOT check:**
- Database connectivity
- Redis connectivity
- Trace collector status
- Alert engine status
- Structured logging status
- Background task health

**Recommendation:** Add `/health/deep` endpoint that validates all subsystems.

**File Citations:**
- Startup sequence: `core/main.py:390-486`
- Background tasks: `core/tracing.py:221-225`, `core/alerting.py:119-127`, `core/structured_logging.py:128-153`
- Health endpoint: `core/main.py:508-515`

---

## PRIORITY FIXES

### Priority 1: DATABASE FOUNDATION (CRITICAL)
**Impact:** Blocks all observability persistence

**Tasks:**
1. Create `db/migrations/005_observability_tables.sql`:
   ```sql
   -- Traces table
   CREATE TABLE IF NOT EXISTS enterprise.traces (
       trace_id VARCHAR(32) PRIMARY KEY,
       entry_point VARCHAR(20) NOT NULL,
       endpoint TEXT,
       method VARCHAR(10),
       session_id VARCHAR(64),
       user_email VARCHAR(255),
       department VARCHAR(50),
       start_time TIMESTAMPTZ NOT NULL,
       end_time TIMESTAMPTZ,
       duration_ms FLOAT,
       status VARCHAR(20),
       error_message TEXT,
       tags JSONB DEFAULT '{}'
   );

   CREATE INDEX idx_traces_start_time ON enterprise.traces(start_time DESC);
   CREATE INDEX idx_traces_user_email ON enterprise.traces(user_email);
   CREATE INDEX idx_traces_status ON enterprise.traces(status);

   -- Trace spans table
   CREATE TABLE IF NOT EXISTS enterprise.trace_spans (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       trace_id VARCHAR(32) NOT NULL REFERENCES enterprise.traces(trace_id) ON DELETE CASCADE,
       span_id VARCHAR(16) NOT NULL,
       parent_span_id VARCHAR(16),
       operation_name VARCHAR(100) NOT NULL,
       start_time TIMESTAMPTZ NOT NULL,
       end_time TIMESTAMPTZ,
       duration_ms FLOAT,
       status VARCHAR(20),
       error_message TEXT,
       tags JSONB DEFAULT '{}',
       logs JSONB DEFAULT '[]'
   );

   CREATE INDEX idx_spans_trace_id ON enterprise.trace_spans(trace_id);
   CREATE INDEX idx_spans_operation ON enterprise.trace_spans(operation_name);

   -- Structured logs table
   CREATE TABLE IF NOT EXISTS enterprise.structured_logs (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       timestamp TIMESTAMPTZ NOT NULL,
       level VARCHAR(20) NOT NULL,
       logger_name VARCHAR(100) NOT NULL,
       message TEXT NOT NULL,
       trace_id VARCHAR(32),
       span_id VARCHAR(16),
       user_email VARCHAR(255),
       department VARCHAR(50),
       session_id VARCHAR(64),
       endpoint TEXT,
       extra JSONB DEFAULT '{}',
       exception_type VARCHAR(100),
       exception_message TEXT,
       exception_traceback TEXT
   );

   CREATE INDEX idx_logs_timestamp ON enterprise.structured_logs(timestamp DESC);
   CREATE INDEX idx_logs_level ON enterprise.structured_logs(level);
   CREATE INDEX idx_logs_trace_id ON enterprise.structured_logs(trace_id);
   CREATE INDEX idx_logs_user_email ON enterprise.structured_logs(user_email);

   -- Full-text search on logs
   ALTER TABLE enterprise.structured_logs ADD COLUMN search_vector tsvector;
   CREATE INDEX idx_logs_search ON enterprise.structured_logs USING gin(search_vector);

   CREATE OR REPLACE FUNCTION update_log_search_vector() RETURNS trigger AS $$
   BEGIN
       NEW.search_vector := to_tsvector('english', COALESCE(NEW.message, '') || ' ' || COALESCE(NEW.logger_name, ''));
       RETURN NEW;
   END;
   $$ LANGUAGE plpgsql;

   CREATE TRIGGER trg_logs_search_vector BEFORE INSERT OR UPDATE ON enterprise.structured_logs
   FOR EACH ROW EXECUTE FUNCTION update_log_search_vector();

   -- Alert rules table
   CREATE TABLE IF NOT EXISTS enterprise.alert_rules (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       name VARCHAR(100) NOT NULL UNIQUE,
       description TEXT,
       metric_type VARCHAR(50) NOT NULL,
       condition VARCHAR(20) NOT NULL,
       threshold FLOAT NOT NULL,
       window_minutes INT DEFAULT 5,
       severity VARCHAR(20) DEFAULT 'warning',
       notification_channels TEXT[] DEFAULT '{}',
       cooldown_minutes INT DEFAULT 10,
       enabled BOOLEAN DEFAULT true,
       last_evaluated_at TIMESTAMPTZ,
       last_triggered_at TIMESTAMPTZ,
       created_at TIMESTAMPTZ DEFAULT NOW()
   );

   -- Alert instances table
   CREATE TABLE IF NOT EXISTS enterprise.alert_instances (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       rule_id UUID NOT NULL REFERENCES enterprise.alert_rules(id) ON DELETE CASCADE,
       severity VARCHAR(20) NOT NULL,
       message TEXT NOT NULL,
       metric_value FLOAT,
       triggered_at TIMESTAMPTZ NOT NULL,
       acknowledged_at TIMESTAMPTZ,
       resolved_at TIMESTAMPTZ,
       acknowledged_by VARCHAR(255),
       status VARCHAR(20) DEFAULT 'firing'
   );

   CREATE INDEX idx_alert_instances_rule_id ON enterprise.alert_instances(rule_id);
   CREATE INDEX idx_alert_instances_triggered_at ON enterprise.alert_instances(triggered_at DESC);
   CREATE INDEX idx_alert_instances_status ON enterprise.alert_instances(status);

   -- Metrics table (optional - for historical trends)
   CREATE TABLE IF NOT EXISTS enterprise.metrics (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       timestamp TIMESTAMPTZ NOT NULL,
       metric_type VARCHAR(50) NOT NULL,
       metric_name VARCHAR(100) NOT NULL,
       metric_value FLOAT NOT NULL,
       tags JSONB DEFAULT '{}'
   );

   CREATE INDEX idx_metrics_timestamp ON enterprise.metrics(timestamp DESC);
   CREATE INDEX idx_metrics_type_name ON enterprise.metrics(metric_type, metric_name);
   ```

2. Run migration:
   ```bash
   psql $AZURE_PG_CONNECTION_STRING -f db/migrations/005_observability_tables.sql
   ```

3. Verify tables exist:
   ```sql
   \dt enterprise.*
   SELECT count(*) FROM enterprise.traces; -- Should return 0
   SELECT count(*) FROM enterprise.structured_logs; -- Should return 0
   ```

**Files to create:**
- `db/migrations/005_observability_tables.sql`

**Estimated time:** 1 hour

---

### Priority 2: CREATE DATABASE MODULE (CRITICAL)
**Impact:** Unblocks all observability endpoints

**Task:** Create `core/database.py`:

```python
"""
Database connection pool management for observability endpoints.

Provides a shared connection pool for routes that need direct database access.
"""
from typing import Optional
import asyncpg
import logging

logger = logging.getLogger(__name__)

_db_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """
    Get or create the shared database connection pool.

    Uses the EnterpriseRAGRetriever's pool initialization logic.

    Returns:
        asyncpg.Pool: Shared connection pool
    """
    global _db_pool

    if _db_pool is not None:
        return _db_pool

    # Reuse the EnterpriseRAGRetriever pattern
    from core.enterprise_rag import EnterpriseRAGRetriever
    from core.config_loader import get_config

    logger.info("[Database] Initializing shared connection pool")
    config = get_config()
    rag = EnterpriseRAGRetriever(config)
    _db_pool = await rag._get_pool()

    logger.info("[Database] Connection pool ready")
    return _db_pool


async def close_db_pool():
    """Close the database connection pool (call on shutdown)."""
    global _db_pool

    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None
        logger.info("[Database] Connection pool closed")
```

**Update shutdown handler in `core/main.py`:**
```python
@app.on_event("shutdown")
async def shutdown_event():
    if OBSERVABILITY_LOADED:
        logger.info("[SHUTDOWN] Stopping observability stack...")
        try:
            await trace_collector.stop()
            await alert_engine.stop()
            shutdown_structured_logging()

            # Add this line
            from core.database import close_db_pool
            await close_db_pool()

            logger.info("[SHUTDOWN] Observability stack stopped")
        except Exception as e:
            logger.error(f"[SHUTDOWN] Observability cleanup error: {e}")
```

**Files to create:**
- `core/database.py`

**Files to modify:**
- `core/main.py:491-502` (add close_db_pool call)

**Estimated time:** 30 minutes

---

### Priority 3: FIX ROUTE PREFIXES (CRITICAL)
**Impact:** Unblocks frontend-backend communication

**Task:** Update `core/main.py:376-381`:

```python
# Change from:
if OBSERVABILITY_LOADED:
    app.include_router(tracing_router, prefix="/api/observability", tags=["observability"])
    app.include_router(logging_router, prefix="/api/observability", tags=["observability"])
    app.include_router(alerting_router, prefix="/api/observability/alerts", tags=["observability"])

# To:
if OBSERVABILITY_LOADED:
    app.include_router(tracing_router, prefix="/api/admin", tags=["observability"])
    app.include_router(logging_router, prefix="/api/admin", tags=["observability"])
    app.include_router(alerting_router, prefix="/api/admin/alerts", tags=["observability"])
```

**Files to modify:**
- `core/main.py:376-381`

**Estimated time:** 5 minutes

---

### Priority 4: INTEGRATE TRACING INTO REQUEST FLOW (HIGH)
**Impact:** Enables distributed tracing

**Tasks:**

#### 4a. Add Tracing to WebSocket Handler

**File:** `core/main.py:806-1277`

**Wrap entire handler in trace context:**
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = None
    user_email = None
    department = None

    # ... (existing auth code to extract user_email, session_id, department) ...

    # ADD THIS WRAPPER
    async with start_trace(
        entry_point='websocket',
        endpoint='/ws',
        session_id=session_id,
        user_email=user_email,
        department=department
    ):
        try:
            # ... (existing message handling loop) ...
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
```

---

#### 4b. Add Spans to EnterpriseTwin

**File:** `core/enterprise_twin.py:509-598`

**Add at top of file:**
```python
from core.tracing import create_span
```

**Wrap RAG retrieval:**
```python
async def think_streaming(self, ...):
    # ... existing code ...

    # Around line 536 - RAG retrieval
    async with create_span('rag_retrieve', tags={'department': department, 'chat_id': chat_id}) as span:
        chunks = await self.rag.search(
            query=query,
            department=department,
            top_k=top_k
        )
        span.set_tag('chunks_retrieved', len(chunks))
        span.set_tag('top_k', top_k)

    # ... existing code ...

    # Around line 573 - LLM generation
    async with create_span('llm_generate', tags={'model': model, 'provider': provider}) as span:
        token_count = 0
        async for chunk in self.client.messages.stream(...):
            yield chunk
            token_count += 1

        span.set_tag('tokens_generated', token_count)
```

---

#### 4c. Add Spans to EnterpriseRAG

**File:** `core/enterprise_rag.py:225-298`

**Add at top of file:**
```python
from core.tracing import create_span
```

**Wrap embedding generation:**
```python
async def search(self, query: str, department: str, top_k: int = 5) -> List[Dict[str, Any]]:
    # ... existing code ...

    # Around line 228 - Embedding generation
    async with create_span('embedding_generate', tags={'department': department}) as span:
        embedding = await self._generate_embedding(query)
        span.set_tag('embedding_model', 'text-embedding-3-small')
        span.set_tag('embedding_dim', len(embedding))

    # Around line 245 - Vector search
    async with create_span('vector_search', tags={'department': department, 'top_k': top_k}) as span:
        results = await conn.fetch("""
            SELECT ... FROM enterprise.rag_embeddings ...
        """, embedding, top_k, department)
        span.set_tag('results_found', len(results))
```

**Files to modify:**
- `core/main.py:806-1277`
- `core/enterprise_twin.py:509-598`
- `core/enterprise_rag.py:225-298`

**Estimated time:** 2 hours

---

### Priority 5: ADD COMPREHENSIVE HEALTH CHECK (MEDIUM)
**Impact:** Enables monitoring and debugging

**Task:** Add new endpoint to `core/main.py`:

```python
@app.get("/health/deep")
async def health_deep():
    """
    Comprehensive health check that validates all subsystems.

    Returns:
        {
            "status": "healthy" | "degraded" | "critical",
            "checks": {
                "engine": {"status": "ok", "message": "..."},
                "database": {"status": "ok", "message": "..."},
                "redis": {"status": "ok", "message": "..."},
                "trace_collector": {"status": "ok", "message": "..."},
                "alert_engine": {"status": "ok", "message": "..."},
                "structured_logging": {"status": "ok", "message": "..."}
            }
        }
    """
    checks = {}
    overall_status = "healthy"

    # Check engine
    if engine is not None:
        checks["engine"] = {"status": "ok", "message": "Twin engine initialized"}
    else:
        checks["engine"] = {"status": "error", "message": "Twin engine not initialized"}
        overall_status = "critical"

    # Check database
    try:
        from core.enterprise_rag import EnterpriseRAGRetriever
        rag = EnterpriseRAGRetriever(get_config())
        pool = await rag._get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            if result == 1:
                checks["database"] = {"status": "ok", "message": "PostgreSQL connected"}
            else:
                checks["database"] = {"status": "error", "message": "Unexpected query result"}
                overall_status = "degraded"
    except Exception as e:
        checks["database"] = {"status": "error", "message": f"Database error: {e}"}
        overall_status = "critical"

    # Check Redis
    try:
        from core.cache import get_cache
        cache = get_cache()
        stats = await cache.get_stats()
        if stats.get("connected"):
            checks["redis"] = {"status": "ok", "message": f"Redis connected ({stats.get('type')})"}
        else:
            checks["redis"] = {"status": "warning", "message": "Redis not configured (using NoOpCache)"}
            if overall_status == "healthy":
                overall_status = "degraded"
    except Exception as e:
        checks["redis"] = {"status": "error", "message": f"Cache error: {e}"}
        if overall_status == "healthy":
            overall_status = "degraded"

    # Check observability stack
    if OBSERVABILITY_LOADED:
        # Trace collector
        try:
            from core.tracing import trace_collector
            if trace_collector._db_pool is not None and trace_collector._flush_task is not None:
                checks["trace_collector"] = {"status": "ok", "message": "Trace collector running"}
            else:
                checks["trace_collector"] = {"status": "error", "message": "Trace collector not started"}
                if overall_status == "healthy":
                    overall_status = "degraded"
        except Exception as e:
            checks["trace_collector"] = {"status": "error", "message": f"Trace collector error: {e}"}
            if overall_status == "healthy":
                overall_status = "degraded"

        # Alert engine
        try:
            from core.alerting import alert_engine
            if alert_engine._db_pool is not None and alert_engine._running:
                checks["alert_engine"] = {"status": "ok", "message": "Alert engine running"}
            else:
                checks["alert_engine"] = {"status": "error", "message": "Alert engine not started"}
                if overall_status == "healthy":
                    overall_status = "degraded"
        except Exception as e:
            checks["alert_engine"] = {"status": "error", "message": f"Alert engine error: {e}"}
            if overall_status == "healthy":
                overall_status = "degraded"

        # Structured logging
        try:
            from core.structured_logging import _db_handler
            if _db_handler is not None and _db_handler._db_pool is not None:
                checks["structured_logging"] = {"status": "ok", "message": "Structured logging active"}
            else:
                checks["structured_logging"] = {"status": "error", "message": "Structured logging not initialized"}
                if overall_status == "healthy":
                    overall_status = "degraded"
        except Exception as e:
            checks["structured_logging"] = {"status": "error", "message": f"Structured logging error: {e}"}
            if overall_status == "healthy":
                overall_status = "degraded"
    else:
        checks["observability"] = {"status": "warning", "message": "Observability modules not loaded"}
        if overall_status == "healthy":
            overall_status = "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }
```

**Files to modify:**
- `core/main.py` (add new endpoint after line 515)

**Estimated time:** 1 hour

---

### Priority 6: ADD AUTH EVENT AUDITING (MEDIUM)
**Impact:** Security compliance and forensics

**Tasks:**

#### 6a. Audit WebSocket Login

**File:** `core/main.py:878`

**Add after successful auth:**
```python
if user_data and user_data.get("valid"):
    user_email = user_data.get("email")
    department = user_data.get("department")
    session_id = user_data.get("session_id")

    # ADD THIS
    from auth.audit_service import get_audit_service
    audit = get_audit_service()
    await audit.log_event(
        action="login",
        actor_email=user_email,
        department_slug=department,
        metadata={"session_id": session_id, "entry_point": "websocket"}
    )
```

---

#### 6b. Audit Failed Auth Attempts

**File:** `core/main.py:903,927`

**Add after failed auth:**
```python
# Line 903 - Invalid token
await websocket.send_json({"error": "Invalid or expired token"})

# ADD THIS
from auth.audit_service import get_audit_service
audit = get_audit_service()
await audit.log_event(
    action="failed_login",
    metadata={"reason": "invalid_token", "entry_point": "websocket"}
)

# Line 927 - No active session
await websocket.send_json({"error": "No active session found"})

# ADD THIS
from auth.audit_service import get_audit_service
audit = get_audit_service()
await audit.log_event(
    action="failed_login",
    actor_email=email,
    metadata={"reason": "no_session", "entry_point": "websocket"}
)
```

**Files to modify:**
- `core/main.py:878,903,927`

**Estimated time:** 30 minutes

---

### Priority 7: MAKE OBSERVABILITY FAILURES LOUD (LOW)
**Impact:** Prevents silent data loss

**Task:** Update `core/main.py:462-485`:

```python
# Change from:
if OBSERVABILITY_LOADED:
    logger.info("[STARTUP] Initializing observability stack...")
    try:
        # ... initialization code ...
    except Exception as e:
        logger.error(f"[STARTUP] Observability init failed: {e}")
        # CONTINUES

# To:
if OBSERVABILITY_LOADED:
    logger.info("[STARTUP] Initializing observability stack...")
    try:
        # ... initialization code ...
    except Exception as e:
        logger.error(f"[STARTUP] Observability init failed: {e}")
        logger.error("[STARTUP] CRITICAL: Observability stack failed to initialize. Traces, logs, and alerts will NOT be collected.")
        # Optionally: raise e  # Uncomment to make startup fail if observability is critical
```

**Alternative:** Add observability health to `/health/deep` instead of failing startup.

**Files to modify:**
- `core/main.py:462-485`

**Estimated time:** 10 minutes

---

## BUILD SHEET SCOPE RECOMMENDATION

### Single Build Sheet: "Observability Infrastructure - Foundation & Integration"

**Scope:** Full-stack (database, backend, minimal frontend updates)

**Phase 1: Database & Module (CRITICAL - 2 hours)**
- Create observability tables migration
- Run migration against Azure PostgreSQL
- Create `core/database.py` module
- Update shutdown handler

**Phase 2: API Fixes (CRITICAL - 30 minutes)**
- Fix route prefixes `/api/observability` → `/api/admin`
- Test all 14 observability endpoints

**Phase 3: Tracing Integration (HIGH - 2 hours)**
- Add trace context to WebSocket handler
- Add spans to EnterpriseTwin.think_streaming()
- Add spans to EnterpriseRAG.search()
- Verify traces appear in database

**Phase 4: Health & Audit (MEDIUM - 1.5 hours)**
- Add `/health/deep` endpoint
- Add auth event auditing (login, failed login)
- Make observability failures more visible

**Total Estimated Time:** 6 hours

**Success Criteria:**
1. ✅ All observability tables exist in database
2. ✅ Trace collector writes spans to `enterprise.traces`
3. ✅ Structured logging writes logs to `enterprise.structured_logs`
4. ✅ Alert engine queries `enterprise.alert_rules`
5. ✅ Frontend `/admin/traces` page shows data
6. ✅ Frontend `/admin/logs` page shows data
7. ✅ Frontend `/admin/alerts` page shows data
8. ✅ `/health/deep` reports all checks passing

---

## FILE CITATIONS INDEX

**Core Files:**
- `core/main.py` - Main application, middleware, routes, startup/shutdown
- `core/tracing.py` - Tracing infrastructure (TraceCollector, start_trace, create_span)
- `core/structured_logging.py` - Structured logging (DatabaseLogHandler, setup_structured_logging)
- `core/metrics_collector.py` - Metrics collection (MetricsCollector singleton)
- `core/alerting.py` - Alert engine (AlertEngine, evaluation loop)
- `core/enterprise_twin.py` - CogTwin implementation (think_streaming method)
- `core/enterprise_rag.py` - RAG retrieval (search method, embeddings)

**Auth & Routes:**
- `auth/audit_service.py` - Audit logging service
- `auth/admin_routes.py` - Admin API endpoints
- `auth/analytics_engine/analytics_routes.py` - Analytics endpoints
- `auth/metrics_routes.py` - Metrics endpoints
- `auth/tracing_routes.py` - Tracing endpoints (BROKEN - missing core/database.py)
- `auth/logging_routes.py` - Logging endpoints (BROKEN - missing core/database.py)
- `auth/alerting_routes.py` - Alerting endpoints (BROKEN - missing core/database.py)

**Database:**
- `db/migrations/004_audit_log.sql` - Audit log table (EXISTS)
- Missing: `db/migrations/005_observability_tables.sql` (MUST CREATE)

**Frontend:**
- `frontend/src/lib/stores/analytics.ts` - Analytics store
- `frontend/src/lib/stores/metrics.ts` - Metrics store (WebSocket)
- `frontend/src/lib/stores/observability.ts` - Observability store (traces, logs, alerts)
- `frontend/src/routes/admin/system/+page.svelte` - System health page
- `frontend/src/routes/admin/analytics/+page.svelte` - Analytics page
- `frontend/src/routes/admin/traces/+page.svelte` - Traces page
- `frontend/src/routes/admin/logs/+page.svelte` - Logs page
- `frontend/src/routes/admin/alerts/+page.svelte` - Alerts page
- `frontend/src/lib/components/admin/observability/*.svelte` - Observability components

---

## CONCLUSION

**Root Cause Summary:**

1. **Database tables don't exist** - Migrations were created but deleted before deployment
2. **Database module doesn't exist** - Routes import non-existent `core/database.py`
3. **Tracing never integrated** - Infrastructure exists but never called
4. **Silent failures** - Observability errors logged but system continues

**Severity:** CRITICAL - Entire observability stack is non-functional

**Estimated Fix Time:** 6 hours (database + module + integration + health)

**Dependencies:** Azure PostgreSQL access (for migration), Backend code access

**Risk:** Low - All changes are additive (no breaking changes to existing functionality)

---

**END OF REPORT**
