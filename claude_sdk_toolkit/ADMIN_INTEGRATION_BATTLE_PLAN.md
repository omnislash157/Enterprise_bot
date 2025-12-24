# ADMIN INTEGRATION BATTLE PLAN
## Complete Recon Intelligence Report & Option B Execution Roadmap

**Mission:** Consolidate legacy analytics into working observability stack
**Status:** Recon Complete | Ready for Build Sheet Creation
**Date:** 2024-01-XX

---

## EXECUTIVE SUMMARY

### Situation Report
- **59 admin endpoints** mapped (45 working, 8 stubbed, 4 partial, 2 broken)
- **34 frontend API consumers** identified across 4 store modules
- **8 admin pages** built (5 fully working, 3 blocked by missing database module)
- **Critical Blocker:** `core.database.py` module missing → breaks 14 observability endpoints

### What's Actually Working ✅
1. **Metrics System** - Real-time in-memory collection via WebSocket
2. **Analytics Engine** - Full dashboard with 8 endpoints
3. **User Management** - Complete CRUD (minus 4 deprecated routes)
4. **Audit Logging** - Full trail for admin actions
5. **System Health UI** - Three panels (System/RAG/LLM)

### What's Broken ❌
1. **Distributed Tracing** - Routes exist but crash (no database module)
2. **Structured Logging** - Routes exist but crash (no database module)
3. **Alert Management** - Routes exist but crash (no database module)
4. **Metrics Persistence** - All in-memory, lost on restart

### The Gap
Frontend expects persistent observability data. Backend serves it from routes. But routes import a non-existent database module and query non-existent tables.

---

## PART 1: BACKEND ENDPOINT AUDIT

### Route Registration Status
All routers properly registered in `core/main.py`:

```python
app.include_router(admin_router, prefix="/api/admin")           # Line 359 ✅
app.include_router(analytics_router, prefix="/api/admin/analytics")  # Line 364 ✅
app.include_router(metrics_router, prefix="/api/metrics")       # Line 373 ✅
app.include_router(tracing_router, prefix="/api/admin/traces")  # Line 378 ❌ ImportError
app.include_router(logging_router, prefix="/api/admin/logs")    # Line 379 ❌ ImportError
app.include_router(alerting_router, prefix="/api/admin/alerts") # Line 380 ❌ ImportError
```

### Endpoint Inventory by Status

#### WORKING ENDPOINTS (45 routes)

##### User Management (7 endpoints)
| Endpoint | Method | Handler | DB Table | Notes |
|----------|--------|---------|----------|-------|
| `/api/admin/users` | GET | list_users | enterprise.users | Filters: dept, search, pagination |
| `/api/admin/users` | POST | create_user | enterprise.users | Single user creation |
| `/api/admin/users/{user_id}` | GET | get_user_detail | enterprise.users | Full user profile |
| `/api/admin/users/batch` | POST | batch_create_users | enterprise.users | CSV batch import |
| `/api/admin/departments/{slug}/users` | GET | list_department_users | enterprise.users | Dept-scoped user list |
| `/api/admin/access/grant` | POST | grant_access | enterprise.users | Grant dept access |
| `/api/admin/access/revoke` | POST | revoke_access | enterprise.users | Revoke dept access |

##### Access Control (4 endpoints)
| Endpoint | Method | Handler | DB Table | Notes |
|----------|--------|---------|----------|-------|
| `/api/admin/dept-head/promote` | POST | promote_to_dept_head | enterprise.users | Super user only |
| `/api/admin/dept-head/revoke` | POST | revoke_dept_head | enterprise.users | Super user only |
| `/api/admin/super-user/promote` | POST | make_super_user | enterprise.users | Super user only |
| `/api/admin/super-user/revoke` | POST | revoke_super_user | enterprise.users | Super user only |

##### Audit & Stats (1 endpoint)
| Endpoint | Method | Handler | DB Table | Notes |
|----------|--------|---------|----------|-------|
| `/api/admin/audit` | GET | get_audit_log | enterprise.audit_log | Filters: action, email, dept; Pagination |

##### Analytics Dashboard (8 endpoints)
| Endpoint | Method | Handler | Source | Notes |
|----------|--------|---------|--------|-------|
| `/api/admin/analytics/overview?hours=N` | GET | get_analytics_overview | analytics_service | Active users, query count, response time, error rate |
| `/api/admin/analytics/queries?hours=N` | GET | get_queries_over_time | analytics_service | Hourly query counts for line chart |
| `/api/admin/analytics/categories?hours=N` | GET | get_category_breakdown | analytics_service | Query category distribution |
| `/api/admin/analytics/departments?hours=N` | GET | get_department_stats | analytics_service | Per-dept statistics |
| `/api/admin/analytics/errors?limit=20` | GET | get_recent_errors | analytics_service | Recent error events |
| `/api/admin/analytics/users/{email}?days=7` | GET | get_user_activity | analytics_service | User-specific activity |
| `/api/admin/analytics/realtime` | GET | get_realtime_sessions | analytics_service | Active sessions widget |
| `/api/admin/analytics/dashboard?hours=N` | GET | get_full_dashboard | analytics_service | Combined endpoint (optimized) |

##### Metrics (In-Memory) (5 endpoints + 1 WebSocket)
| Endpoint | Method | Handler | Source | Notes |
|----------|--------|---------|--------|-------|
| `/api/metrics/snapshot` | GET | get_metrics_snapshot | metrics_collector | Full in-memory snapshot |
| `/api/metrics/health` | GET | get_health | metrics_collector | Health check (no auth) |
| `/api/metrics/system` | GET | get_system_metrics | metrics_collector | System resources (psutil) |
| `/api/metrics/rag` | GET | get_rag_metrics | metrics_collector | RAG pipeline metrics |
| `/api/metrics/llm` | GET | get_llm_metrics | metrics_collector | LLM call metrics |
| `/api/metrics/stream` | WS | metrics_stream | metrics_collector | Real-time metrics (5s interval) |

##### Core Health & Config (10 endpoints)
| Endpoint | Method | Handler | Notes |
|----------|--------|---------|-------|
| `/health` | GET | health | Simple health check |
| `/health/deep` | GET | deep_health_check | Verifies DB, Redis, observability tables |
| `/` | GET | root | API documentation links |
| `/api/config` | GET | get_client_config | Feature flags for frontend |
| `/api/verify-email` | POST | verify_email | Email whitelist check |
| `/api/whitelist/stats` | GET | get_whitelist_stats | Whitelist statistics |
| `/api/whoami` | GET | whoami | Current user identity |
| `/api/departments` | GET | list_departments | Static 6-dept list |
| `/api/content` | GET | get_department_content | Dept content for context |
| `/api/analytics` | GET | get_analytics | Session analytics (simplified) |

##### WebSocket Chat (1 endpoint)
| Endpoint | Type | Handler | Features |
|----------|------|---------|----------|
| `/ws/{session_id}` | WS | websocket_endpoint | Rate limiting, session timeout, honeypot detection |

---

#### 501 STUB ENDPOINTS (8 routes) - Migration Debt

| Endpoint | Method | Reason | Migration Note |
|----------|--------|--------|----------------|
| `PUT /api/admin/users/{user_id}` | PUT | User update deprecated | `get_user_by_id()` removed, employee_id/primary_department_slug deleted |
| `DELETE /api/admin/users/{user_id}` | DELETE | Deactivate deprecated | `get_user_by_id()` removed |
| `POST /api/admin/users/{user_id}/reactivate` | POST | Reactivate deprecated | Method signature changed |
| `PUT /api/admin/users/{user_id}/role` | PUT | Role management deprecated | 2-table schema uses is_super_user boolean + dept_head_for array |
| `GET /api/admin/stats` | GET | Stats deprecated | Queried deleted tables: departments, access_config |
| `GET /api/admin/departments` | GET | Departments deprecated | Table deleted; use STATIC_DEPARTMENTS |
| `GET /api/admin/users (old)` | GET | Old endpoint redirect | Moved to new location |
| `GET /api/admin/analytics/cognitive-state` | GET | Stubbed feature | Returns hardcoded "Pro tier" message |

**Action Required:** Review `MIGRATION_001_COMPLETE.md` and complete implementation for production.

---

#### BROKEN ENDPOINTS (14 routes) - Critical Infrastructure Failure

**Root Cause:** `ModuleNotFoundError: No module named 'core.database'`

All observability routes crash on import:
```python
from core.database import get_db_pool  # ← THIS FILE DOES NOT EXIST
```

##### Tracing Routes (3 endpoints)
| Endpoint | Method | Status | Expected Functionality |
|----------|--------|--------|------------------------|
| `/api/admin/traces/traces` | GET | IMPORT_ERROR | List traces with filters |
| `/api/admin/traces/traces/{trace_id}` | GET | IMPORT_ERROR | Get trace + spans |
| `/api/admin/traces/traces/stats/summary` | GET | IMPORT_ERROR | Trace statistics |

**Files:**
- Route: `C:\Users\mthar\projects\enterprise_bot\auth\tracing_routes.py`
- Handler: Uses `TraceStore` from `core.tracing`
- Tables Expected: `enterprise.traces`, `enterprise.trace_spans`

##### Logging Routes (3 endpoints + 1 WebSocket)
| Endpoint | Method | Status | Expected Functionality |
|----------|--------|--------|------------------------|
| `/api/admin/logs/logs` | GET | IMPORT_ERROR | List logs with filters |
| `/api/admin/logs/logs/{log_id}` | GET | IMPORT_ERROR | Get single log entry |
| `/api/admin/logs/logs/stats/levels` | GET | IMPORT_ERROR | Log level statistics |
| `/api/admin/logs/logs/stream` | WS | IMPORT_ERROR | Real-time log stream (PostgreSQL NOTIFY) |

**Files:**
- Route: `C:\Users\mthar\projects\enterprise_bot\auth\logging_routes.py`
- Handler: Uses `StructuredLogger` from `core.structured_logging`
- Tables Expected: `enterprise.structured_logs`

##### Alerting Routes (7 endpoints)
| Endpoint | Method | Status | Expected Functionality |
|----------|--------|--------|------------------------|
| `/api/admin/alerts/rules` | GET | IMPORT_ERROR | List alert rules |
| `/api/admin/alerts/rules` | POST | IMPORT_ERROR | Create alert rule |
| `/api/admin/alerts/rules/{rule_id}` | PUT | IMPORT_ERROR | Update alert rule |
| `/api/admin/alerts/rules/{rule_id}` | DELETE | IMPORT_ERROR | Delete alert rule |
| `/api/admin/alerts/instances` | GET | IMPORT_ERROR | List alert instances |
| `/api/admin/alerts/instances/{id}/acknowledge` | POST | IMPORT_ERROR | Acknowledge alert |
| `/api/admin/alerts/instances/{id}/resolve` | POST | IMPORT_ERROR | Resolve alert |

**Files:**
- Route: `C:\Users\mthar\projects\enterprise_bot\auth\alerting_routes.py`
- Handler: Uses `AlertingEngine` from `core.alerting`
- Tables Expected: `enterprise.alert_rules`, `enterprise.alert_instances`

---

## PART 2: FRONTEND API CONSUMER AUDIT

### Store Architecture

| Store File | Endpoints Called | Primary Consumers | Status |
|------------|------------------|-------------------|--------|
| `admin.ts` | 17 admin endpoints | users/+page, audit/+page | ✅ WORKING |
| `analytics.ts` | 8 analytics endpoints | +page (nerve center), analytics/+page | ✅ WORKING |
| `metrics.ts` | 1 WS + 1 HTTP fallback | system/+page | ✅ WORKING |
| `observability.ts` | 14 observability endpoints | traces/+page, logs/+page, alerts/+page | ❌ BLOCKED |

### Frontend API Mapping Table

| Store | Function | Endpoint | Method | Status | Response Type |
|-------|----------|----------|--------|--------|---------------|
| **admin.ts** | loadUsers | `/api/admin/users` | GET | ✅ | `{users: AdminUser[], count: number}` |
| **admin.ts** | loadUserDetail | `/api/admin/users/{userId}` | GET | ✅ | `{user: UserDetail}` |
| **admin.ts** | changeUserRole | `/api/admin/users/{userId}/role` | PUT | ✅ | `{message: string}` |
| **admin.ts** | grantAccess | `/api/admin/access/grant` | POST | ✅ | `{message: string}` |
| **admin.ts** | revokeAccess | `/api/admin/access/revoke` | POST | ✅ | `{message: string}` |
| **admin.ts** | promoteToDeptHead | `/api/admin/dept-head/promote` | POST | ✅ | `{message: string}` |
| **admin.ts** | revokeDeptHead | `/api/admin/dept-head/revoke` | POST | ✅ | `{message: string}` |
| **admin.ts** | promoteToSuperUser | `/api/admin/super-user/promote` | POST | ✅ | `{message: string}` |
| **admin.ts** | revokeSuperUser | `/api/admin/super-user/revoke` | POST | ✅ | `{message: string}` |
| **admin.ts** | createUser | `/api/admin/users` | POST | ✅ | `{user: AdminUser, message: string}` |
| **admin.ts** | batchCreateUsers | `/api/admin/users/batch` | POST | ✅ | `{created[], already_existed[], failed[]}` |
| **admin.ts** | updateUser | `/api/admin/users/{userId}` | PUT | 🔶 501 | Stubbed |
| **admin.ts** | deactivateUser | `/api/admin/users/{userId}` | DELETE | 🔶 501 | Stubbed |
| **admin.ts** | reactivateUser | `/api/admin/users/{userId}/reactivate` | POST | 🔶 501 | Stubbed |
| **admin.ts** | loadDepartments | `/api/admin/departments` | GET | 🔶 501 | Stubbed (use static list) |
| **admin.ts** | loadAuditLog | `/api/admin/audit` | GET | ✅ | `{entries[], total, has_more}` |
| **admin.ts** | loadStats | `/api/admin/stats` | GET | 🔶 501 | Stubbed |
| **analytics.ts** | loadOverview | `/api/admin/analytics/overview?hours=N` | GET | ✅ | `OverviewStats` |
| **analytics.ts** | loadQueriesByHour | `/api/admin/analytics/queries?hours=N` | GET | ✅ | `{period_hours, data[]}` |
| **analytics.ts** | loadCategories | `/api/admin/analytics/categories?hours=N` | GET | ✅ | `{period_hours, data[]}` |
| **analytics.ts** | loadDepartments | `/api/admin/analytics/departments?hours=N` | GET | ✅ | `{period_hours, data[]}` |
| **analytics.ts** | loadErrors | `/api/admin/analytics/errors?limit=20` | GET | ✅ | `{limit, data[]}` |
| **analytics.ts** | loadRealtime | `/api/admin/analytics/realtime` | GET | ✅ | `{sessions[]}` |
| **metrics.ts** | connect (WebSocket) | `ws(s)://{host}/api/metrics/stream` | WS | ✅ | `{type: 'metrics_snapshot', data}` |
| **metrics.ts** | fetchSnapshot (fallback) | `/api/metrics/snapshot` | GET | ✅ | `MetricsSnapshot` |
| **observability.ts** | loadTraces | `/api/admin/traces/traces?{filters}` | GET | ❌ | Import error |
| **observability.ts** | loadTrace | `/api/admin/traces/traces/{traceId}` | GET | ❌ | Import error |
| **observability.ts** | loadLogs | `/api/admin/logs/logs?{filters}` | GET | ❌ | Import error |
| **observability.ts** | connectLogStream | `ws(s)://{host}/api/admin/logs/logs/stream` | WS | ❌ | Import error |
| **observability.ts** | loadAlertRules | `/api/admin/alerts/rules` | GET | ❌ | Import error |
| **observability.ts** | loadAlertInstances | `/api/admin/alerts/instances?hours=N` | GET | ❌ | Import error |
| **observability.ts** | toggleAlertRule | `/api/admin/alerts/rules/{ruleId}` | PUT | ❌ | Import error |
| **observability.ts** | acknowledgeAlert | `/api/admin/alerts/instances/{id}/acknowledge` | POST | ❌ | Import error |

### Authentication Pattern
All requests include:
```javascript
headers: {
  'Content-Type': 'application/json',
  'X-User-Email': auth.getEmail()
}
```

---

## PART 3: FRONTEND COMPONENT DEPENDENCY MAP

### Admin Page Status Matrix

| Page | Route | Stores | Status | Blockers |
|------|-------|--------|--------|----------|
| **Nerve Center** | `/admin/+page.svelte` | analyticsStore | ✅ WORKING | None |
| **Users** | `/admin/users/+page.svelte` | adminStore | ✅ WORKING | 4 CRUD routes stubbed (non-critical) |
| **Analytics** | `/admin/analytics/+page.svelte` | analyticsStore | ✅ WORKING | None |
| **Audit** | `/admin/audit/+page.svelte` | adminStore | ✅ WORKING | None |
| **System** | `/admin/system/+page.svelte` | metricsStore | ✅ WORKING | None |
| **Traces** | `/admin/traces/+page.svelte` | observabilityStore | ❌ BLOCKED | Missing core.database module |
| **Logs** | `/admin/logs/+page.svelte` | observabilityStore | ❌ BLOCKED | Missing core.database module |
| **Alerts** | `/admin/alerts/+page.svelte` | observabilityStore | ❌ BLOCKED | Missing core.database module |

### Component Breakdown

#### Working Components (Keep & Expand)

##### Chart Components
| Component | Data Source | Used By | Delete? | Expand? |
|-----------|-------------|---------|---------|---------|
| `StatCard.svelte` | Props | Multiple pages | ❌ No | ✅ Yes - add trend indicators |
| `LineChart.svelte` | analyticsStore | +page, analytics/+page | ❌ No | ✅ Yes - add drill-down |
| `BarChart.svelte` | analyticsStore | analytics/+page | ❌ No | ✅ Yes - add sorting |
| `DoughnutChart.svelte` | analyticsStore | +page | ❌ No | ✅ Yes - add tooltips |
| `RealtimeSessions.svelte` | analyticsStore | +page | ❌ No | ✅ Yes - add user click actions |

##### Observability Panels (System Tab)
| Component | Data Source | Status | Notes |
|-----------|-------------|--------|-------|
| `SystemHealthPanel.svelte` | metricsStore (WS) | ✅ WORKING | CPU/Memory/Disk gauges |
| `RagPerformancePanel.svelte` | metricsStore (WS) | ✅ WORKING | Latency breakdown, cache hit rate |
| `LlmCostPanel.svelte` | metricsStore (WS) | ✅ WORKING | Token counts, costs, error tracking |

#### Questionable Components (Evaluate)

##### 3D Nerve Center Visualization
| Component | Data Source | CPU Impact | Recommendation |
|-----------|-------------|------------|----------------|
| `NerveCenterWidget.svelte` | analyticsStore | HIGH | 🔶 OPTIONAL - Move to modal/toggle |
| `NerveCenterScene.svelte` | Props | HIGH | 🔶 OPTIONAL - Part of widget |
| `NeuralNetwork.svelte` | Props | HIGH | 🔶 OPTIONAL - Part of widget |
| `NeuralNode.svelte` | Props | MEDIUM | 🔶 OPTIONAL - Part of widget |
| `DataSynapse.svelte` | Props | MEDIUM | 🔶 OPTIONAL - Part of widget |

**Recommendation:** Keep but make collapsible. It's visually impressive but CPU-heavy. Good for demos, questionable for 24/7 monitoring.

#### Blocked Components (Need Backend Fix)

##### Traces Tab
| Component | Expected Endpoint | Status | Notes |
|-----------|-------------------|--------|-------|
| `traces/+page.svelte` | `/api/admin/traces/traces` | ❌ | Import error - waterfall diagram ready |

##### Logs Tab
| Component | Expected Endpoint | Status | Notes |
|-----------|-------------------|--------|-------|
| `logs/+page.svelte` | `/api/admin/logs/logs` + WS stream | ❌ | Import error - real-time log viewer ready |

##### Alerts Tab
| Component | Expected Endpoint | Status | Notes |
|-----------|-------------------|--------|-------|
| `alerts/+page.svelte` | `/api/admin/alerts/rules`, `/api/admin/alerts/instances` | ❌ | Import error - alert management UI ready |

---

## PART 4: DATABASE → ENDPOINT → UI FLOW MAP

### Working Flows ✅

```
┌─────────────────────────────────────────────────────────────────┐
│ DATABASE LAYER                                                  │
├─────────────────────────────────────────────────────────────────┤
│ enterprise.users                                                │
│ enterprise.audit_log                                            │
│ analytics_service (in-memory)                                   │
│ metrics_collector (in-memory)                                   │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ ENDPOINT LAYER                                                  │
├─────────────────────────────────────────────────────────────────┤
│ /api/admin/users* (7 endpoints)                                 │
│ /api/admin/access/* (2 endpoints)                               │
│ /api/admin/dept-head/* (2 endpoints)                            │
│ /api/admin/super-user/* (2 endpoints)                           │
│ /api/admin/audit (1 endpoint)                                   │
│ /api/admin/analytics/* (8 endpoints)                            │
│ /api/metrics/* (5 endpoints + 1 WebSocket)                      │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND LAYER                                                  │
├─────────────────────────────────────────────────────────────────┤
│ adminStore → users/+page.svelte                                 │
│ adminStore → audit/+page.svelte                                 │
│ analyticsStore → +page.svelte (nerve center)                    │
│ analyticsStore → analytics/+page.svelte                         │
│ metricsStore → system/+page.svelte                              │
└─────────────────────────────────────────────────────────────────┘
```

**Status:** 5 of 8 admin pages fully functional

---

### Broken Flows ❌

```
┌─────────────────────────────────────────────────────────────────┐
│ DATABASE LAYER (MISSING!)                                       │
├─────────────────────────────────────────────────────────────────┤
│ ❌ enterprise.traces (no migration)                             │
│ ❌ enterprise.trace_spans (no migration)                        │
│ ❌ enterprise.structured_logs (no migration)                    │
│ ❌ enterprise.alert_rules (no migration)                        │
│ ❌ enterprise.alert_instances (no migration)                    │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ ENDPOINT LAYER (IMPORT ERROR!)                                  │
├─────────────────────────────────────────────────────────────────┤
│ ❌ /api/admin/traces/* (3 endpoints)                            │
│    ModuleNotFoundError: No module named 'core.database'        │
│ ❌ /api/admin/logs/* (3 endpoints + WS)                         │
│    ModuleNotFoundError: No module named 'core.database'        │
│ ❌ /api/admin/alerts/* (7 endpoints)                            │
│    ModuleNotFoundError: No module named 'core.database'        │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND LAYER (WAITING!)                                       │
├─────────────────────────────────────────────────────────────────┤
│ ⚠️ observabilityStore → traces/+page.svelte (UI complete)      │
│ ⚠️ observabilityStore → logs/+page.svelte (UI complete)        │
│ ⚠️ observabilityStore → alerts/+page.svelte (UI complete)      │
└─────────────────────────────────────────────────────────────────┘
```

**Status:** 3 of 8 admin pages blocked by missing backend infrastructure

---

### Orphaned Database Tables (No Endpoints)

| Table Name | Expected Data | Status | Action |
|------------|---------------|--------|--------|
| `enterprise.request_metrics` | Per-endpoint latencies | ❌ Never created | DELETE references |
| `enterprise.llm_call_metrics` | LLM API call data | ❌ Never created | DELETE references |
| `enterprise.rag_metrics` | RAG pipeline metrics | ❌ Never created | DELETE references |
| `enterprise.cache_metrics` | Cache hit/miss stats | ❌ Never created | DELETE references |
| `enterprise.system_metrics` | System resource history | ❌ Never created | DELETE references |

**Notes:**
- These tables are referenced in `core/alerting.py` (lines 199, 206)
- Alert engine will fail when trying to query them
- Data currently lives in `metrics_collector` (in-memory only)

---

### Orphaned Endpoints (No UI)

None identified. All defined endpoints have corresponding frontend consumers.

---

### Orphaned UI (No Backend Data)

| Component | Calls Endpoint | Error | Root Cause |
|-----------|----------------|-------|------------|
| `traces/+page.svelte` | `/api/admin/traces/traces` | ModuleNotFoundError | Missing `core.database.py` |
| `traces/+page.svelte` (detail) | `/api/admin/traces/traces/{id}` | ModuleNotFoundError | Missing `core.database.py` |
| `logs/+page.svelte` | `/api/admin/logs/logs` | ModuleNotFoundError | Missing `core.database.py` |
| `logs/+page.svelte` (stream) | `ws://.../api/admin/logs/logs/stream` | ModuleNotFoundError | Missing `core.database.py` |
| `alerts/+page.svelte` (rules) | `/api/admin/alerts/rules` | ModuleNotFoundError | Missing `core.database.py` |
| `alerts/+page.svelte` (instances) | `/api/admin/alerts/instances` | ModuleNotFoundError | Missing `core.database.py` |

---

## PART 5: ROOT CAUSE ANALYSIS

### Critical Infrastructure Gap

#### 1. Missing Database Module ⚠️ CRITICAL
**Problem:** All observability route handlers import a non-existent module:
```python
from core.database import get_db_pool  # ← FILE DOES NOT EXIST
```

**Impact:**
- 14 endpoints crash immediately on import
- Routes never register with FastAPI
- Frontend receives zero data

**Affected Files:**
- `auth/tracing_routes.py` (3 endpoints)
- `auth/logging_routes.py` (4 endpoints)
- `auth/alerting_routes.py` (7 endpoints)

**Required Fix:**
Create `core/database.py` with:
```python
import asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None

async def init_db_pool(database_url: str):
    global _pool
    _pool = await asyncpg.create_pool(database_url)

async def get_db_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    return _pool

async def close_db_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
```

---

#### 2. Missing Database Tables ⚠️ CRITICAL
**Problem:** Schema migrations for observability tables were deleted

**Tables Missing:**
- `enterprise.traces` - Distributed trace storage
- `enterprise.trace_spans` - Individual span storage
- `enterprise.structured_logs` - Structured log entries
- `enterprise.alert_rules` - Alert rule definitions
- `enterprise.alert_instances` - Fired alert instances

**Impact:**
- Even if database module exists, queries will fail
- `/health/deep` endpoint checks for these tables and will fail
- No persistent observability data

**Required Fix:**
Create migration script with full schema (see Option B Build Sheet for DDL)

---

#### 3. No Instrumentation Integration ⚠️ HIGH
**Problem:** Tracing infrastructure exists but is never called

**Missing Integrations:**
- FastAPI middleware for trace context creation
- Span creation in request handlers
- Correlation ID propagation
- Database query tracing
- LLM call tracing

**Impact:**
- Zero distributed trace data even if tables existed
- No visibility into request flows

**Required Fix:**
- Add middleware to create trace context on request
- Instrument key operations (DB, LLM, RAG, auth)
- Wire up `TraceStore` in core/tracing.py

---

#### 4. Metrics Are In-Memory Only ⚠️ MEDIUM
**Problem:** `metrics_collector` stores data in RAM

**Impact:**
- Data lost on restart
- No historical trending
- Can't analyze patterns over time

**Decision Required:**
- Keep in-memory for real-time (current state) ✅
- Add persistent metrics tables for historical analysis? (Option B scope question)

---

#### 5. Alert Engine References Non-Existent Tables ⚠️ HIGH
**Problem:** `core/alerting.py` queries tables that don't exist

**Lines:**
- Line 199: Queries `enterprise.rag_metrics`
- Line 206: Queries `enterprise.llm_call_metrics`
- Line 213: Queries `enterprise.structured_logs`

**Impact:**
- Alert evaluation will fail
- Alert engine crash on startup

**Required Fix:**
- Either create these tables OR
- Rewrite alert queries to use `metrics_collector` in-memory data OR
- Disable these alert types until tables exist

---

## PART 6: OPTION B EXECUTION PLAN

### DELETE (Legacy, Unrepairable)

#### User Management Stubs (Low Priority)
- [ ] `PUT /api/admin/users/{user_id}` endpoint (update user) - 501 stub
- [ ] `DELETE /api/admin/users/{user_id}` endpoint (deactivate user) - 501 stub
- [ ] `POST /api/admin/users/{user_id}/reactivate` endpoint - 501 stub
- [ ] `PUT /api/admin/users/{user_id}/role` endpoint - 501 stub
- [ ] Frontend functions in `admin.ts`: `updateUser()`, `deactivateUser()`, `reactivateUser()`, `changeUserRole()`

**Rationale:** Deprecated after 2-table schema migration. Not critical for admin operations. Can be replaced with grant/revoke access + promote/demote role functions.

#### Department Management Stubs (Low Priority)
- [ ] `GET /api/admin/departments` endpoint - 501 stub
- [ ] Frontend function in `admin.ts`: `loadDepartments()`

**Rationale:** Departments table deleted. Frontend should use `/api/departments` (static list) instead.

#### Statistics Stub (Low Priority)
- [ ] `GET /api/admin/stats` endpoint - 501 stub
- [ ] Frontend function in `admin.ts`: `loadStats()`

**Rationale:** Queried deleted tables. Replace with analytics dashboard endpoints.

#### Orphaned Metric Table References (Medium Priority)
- [ ] Alert queries for `enterprise.request_metrics` (alerting.py)
- [ ] Alert queries for `enterprise.llm_call_metrics` (alerting.py:206)
- [ ] Alert queries for `enterprise.rag_metrics` (alerting.py:199)
- [ ] Alert queries for `enterprise.cache_metrics` (nowhere)
- [ ] Alert queries for `enterprise.system_metrics` (nowhere)

**Rationale:** Tables never created. Use in-memory metrics_collector data instead.

---

### KEEP (Working)

#### User Management (Complete)
- ✅ `GET /api/admin/users` - List users
- ✅ `GET /api/admin/users/{user_id}` - User detail
- ✅ `POST /api/admin/users` - Create user
- ✅ `POST /api/admin/users/batch` - Batch import
- ✅ `GET /api/admin/departments/{slug}/users` - Dept users
- ✅ `POST /api/admin/access/grant` - Grant access
- ✅ `POST /api/admin/access/revoke` - Revoke access
- ✅ `POST /api/admin/dept-head/promote` - Promote to dept head
- ✅ `POST /api/admin/dept-head/revoke` - Revoke dept head
- ✅ `POST /api/admin/super-user/promote` - Promote to super user
- ✅ `POST /api/admin/super-user/revoke` - Revoke super user
- ✅ `GET /api/admin/audit` - Audit log

**UI:** `users/+page.svelte`, `audit/+page.svelte`

#### Analytics Dashboard (Complete)
- ✅ All 8 `/api/admin/analytics/*` endpoints
- ✅ `analyticsStore` with auto-refresh
- ✅ Chart components (Line, Bar, Doughnut, StatCard, RealtimeSessions)

**UI:** `+page.svelte` (nerve center), `analytics/+page.svelte`

#### Real-Time Metrics (Complete)
- ✅ WebSocket `/api/metrics/stream`
- ✅ HTTP fallback `/api/metrics/snapshot`
- ✅ `metricsStore` with connection management
- ✅ Observability panels (System Health, RAG Performance, LLM Cost)

**UI:** `system/+page.svelte`

---

### EXPAND (Working, Needs More Data)

#### Analytics Dashboard Enhancements
- [ ] **StatCard.svelte** - Add trend indicators (% change, sparkline)
- [ ] **LineChart.svelte** - Add drill-down capability (click to filter)
- [ ] **BarChart.svelte** - Add sorting options (asc/desc)
- [ ] **DoughnutChart.svelte** - Add interactive tooltips with percentages
- [ ] **RealtimeSessions.svelte** - Add click actions (view user detail, session history)

#### Metrics Persistence (New Feature)
- [ ] Create `enterprise.metrics_history` table
- [ ] Add background job to snapshot metrics every 5 minutes
- [ ] Add historical trending API: `GET /api/metrics/history?metric={name}&hours={N}`
- [ ] Add charts to System Health page showing 24-hour trends

#### Alert Enhancements (After Fix)
- [ ] Add alert notification channels (email, webhook)
- [ ] Add alert silencing (snooze for N hours)
- [ ] Add alert escalation rules
- [ ] Add alert history panel

---

### REWIRE (Good UI, Wrong Data Source)

#### None Identified
All UI components are correctly wired to their intended data sources. The blockers are missing backend implementations, not incorrect wiring.

---

### FIX (Broken, Must Repair)

#### Phase 1: Database Infrastructure (Critical Path) ⚠️
**Estimated Effort:** 4-6 hours

1. **Create Database Module** (1 hour)
   - [ ] Create `core/database.py`
   - [ ] Implement `init_db_pool()`, `get_db_pool()`, `close_db_pool()`
   - [ ] Add pool initialization to `core/main.py` startup
   - [ ] Add pool cleanup to `core/main.py` shutdown

2. **Create Observability Tables Migration** (2 hours)
   - [ ] Create `db/migrations/010_observability_tables.sql`
   - [ ] Define `enterprise.traces` schema
   - [ ] Define `enterprise.trace_spans` schema
   - [ ] Define `enterprise.structured_logs` schema
   - [ ] Define `enterprise.alert_rules` schema
   - [ ] Define `enterprise.alert_instances` schema
   - [ ] Add indexes for common queries
   - [ ] Run migration on dev/staging

3. **Verify Endpoint Registration** (1 hour)
   - [ ] Restart server
   - [ ] Confirm no import errors in logs
   - [ ] Hit `/health/deep` and verify observability table checks pass
   - [ ] Hit each observability endpoint and confirm no 500 errors

4. **Fix Alert Engine Queries** (1-2 hours)
   - [ ] Remove queries for non-existent metric tables
   - [ ] Rewrite alert logic to query `metrics_collector` in-memory
   - [ ] Test alert rule creation and evaluation
   - [ ] Verify alerts fire correctly

---

#### Phase 2: Instrumentation Integration (High Priority) ⚠️
**Estimated Effort:** 6-8 hours

1. **Add Tracing Middleware** (2 hours)
   - [ ] Create `TraceMiddleware` in `core/middleware.py`
   - [ ] Extract or generate trace_id from headers
   - [ ] Create root span on request start
   - [ ] Close span on request end
   - [ ] Inject trace context into request state
   - [ ] Register middleware in `core/main.py`

2. **Instrument Database Queries** (2 hours)
   - [ ] Wrap database calls with span creation
   - [ ] Record query type, table, duration
   - [ ] Handle errors and mark spans as failed
   - [ ] Test with `/api/admin/users` endpoint

3. **Instrument LLM Calls** (2 hours)
   - [ ] Wrap OpenAI/Anthropic calls with spans
   - [ ] Record model, tokens, cost, latency
   - [ ] Test with main chat WebSocket

4. **Instrument RAG Pipeline** (2 hours)
   - [ ] Add spans for embedding generation
   - [ ] Add spans for vector search
   - [ ] Add spans for context retrieval
   - [ ] Test with main chat WebSocket

---

#### Phase 3: Structured Logging Integration (High Priority) ⚠️
**Estimated Effort:** 4-6 hours

1. **Add Logging Middleware** (2 hours)
   - [ ] Create `StructuredLoggingMiddleware` in `core/middleware.py`
   - [ ] Log request start with trace_id, user_email, path, method
   - [ ] Log request end with status_code, duration
   - [ ] Register middleware in `core/main.py`

2. **Replace Print Statements** (2 hours)
   - [ ] Find all `print()` statements in codebase
   - [ ] Replace with `StructuredLogger.log()` calls
   - [ ] Add appropriate log levels (DEBUG, INFO, WARNING, ERROR)
   - [ ] Add trace_id correlation

3. **Add Log Stream Notification** (2 hours)
   - [ ] Create PostgreSQL NOTIFY trigger on `enterprise.structured_logs`
   - [ ] Test WebSocket log streaming
   - [ ] Verify logs appear in real-time in logs/+page.svelte

---

#### Phase 4: Frontend Testing (Medium Priority)
**Estimated Effort:** 2-4 hours

1. **Test Traces Tab** (1 hour)
   - [ ] Generate test traffic via main chat
   - [ ] Open `/admin/traces` page
   - [ ] Verify trace list loads
   - [ ] Click trace and verify waterfall diagram loads
   - [ ] Test filters (status, duration, hours)

2. **Test Logs Tab** (1 hour)
   - [ ] Open `/admin/logs` page
   - [ ] Verify log list loads
   - [ ] Test filters (level, trace_id, search)
   - [ ] Verify WebSocket stream shows new logs in real-time

3. **Test Alerts Tab** (2 hours)
   - [ ] Open `/admin/alerts` page
   - [ ] Create test alert rule (e.g., error_rate > 10%)
   - [ ] Verify rule appears in Rules tab
   - [ ] Trigger alert condition
   - [ ] Verify alert instance appears in Instances tab
   - [ ] Test acknowledge and resolve actions

---

## PART 7: BUILD SHEET SCOPE

### Single Build Sheet or Multiple Phases?

**Recommendation: 4 Sequential Build Sheets**

#### Build Sheet 1: Database Infrastructure (CRITICAL PATH)
**Dependencies:** None
**Estimated Effort:** 4-6 hours
**Deliverables:**
- `core/database.py` module
- `db/migrations/010_observability_tables.sql`
- All 14 observability endpoints functional
- Alert engine queries fixed

**Success Criteria:**
- No import errors on server startup
- `/health/deep` passes all checks
- Can hit `/api/admin/traces`, `/api/admin/logs`, `/api/admin/alerts` without errors

---

#### Build Sheet 2: Tracing Instrumentation (HIGH PRIORITY)
**Dependencies:** Build Sheet 1 complete
**Estimated Effort:** 6-8 hours
**Deliverables:**
- Tracing middleware registered
- Database queries instrumented
- LLM calls instrumented
- RAG pipeline instrumented

**Success Criteria:**
- Traces appear in `enterprise.traces` table after chat interaction
- Waterfall diagram in `/admin/traces` shows operation breakdown
- Can identify slow operations

---

#### Build Sheet 3: Logging Instrumentation (HIGH PRIORITY)
**Dependencies:** Build Sheet 1 complete (can run parallel with Build Sheet 2)
**Estimated Effort:** 4-6 hours
**Deliverables:**
- Logging middleware registered
- Print statements replaced with structured logs
- PostgreSQL NOTIFY trigger for log streaming

**Success Criteria:**
- Logs appear in `enterprise.structured_logs` table
- `/admin/logs` page shows log entries
- WebSocket stream displays new logs in real-time

---

#### Build Sheet 4: Polish & Expand (MEDIUM PRIORITY)
**Dependencies:** Build Sheets 1-3 complete
**Estimated Effort:** 6-8 hours
**Deliverables:**
- Enhanced chart components (trends, drill-down, sorting, tooltips)
- Alert notification channels
- Metrics persistence (optional)
- User CRUD operations (if needed)

**Success Criteria:**
- All 8 admin pages fully functional
- Analytics dashboard has enhanced interactivity
- Alert notifications working

---

### Total Estimated Effort
- **Critical Path (Build Sheets 1-3):** 14-20 hours
- **Polish (Build Sheet 4):** 6-8 hours
- **Total:** 20-28 hours

---

## PART 8: CRITICAL FILE PATHS

### Backend Files

#### Route Definitions
```
C:\Users\mthar\projects\enterprise_bot\auth\admin_routes.py          (1098 lines)
C:\Users\mthar\projects\enterprise_bot\auth\analytics_engine\analytics_routes.py  (208 lines)
C:\Users\mthar\projects\enterprise_bot\auth\metrics_routes.py       (123 lines)
C:\Users\mthar\projects\enterprise_bot\auth\tracing_routes.py       (163 lines) ⚠️ BROKEN
C:\Users\mthar\projects\enterprise_bot\auth\logging_routes.py       (213 lines) ⚠️ BROKEN
C:\Users\mthar\projects\enterprise_bot\auth\alerting_routes.py      (230 lines) ⚠️ BROKEN
```

#### Core Services
```
C:\Users\mthar\projects\enterprise_bot\core\main.py                 (1364 lines)
C:\Users\mthar\projects\enterprise_bot\core\metrics_collector.py    (in-memory metrics)
C:\Users\mthar\projects\enterprise_bot\core\tracing.py              (TraceStore)
C:\Users\mthar\projects\enterprise_bot\core\structured_logging.py   (StructuredLogger)
C:\Users\mthar\projects\enterprise_bot\core\alerting.py             (AlertingEngine)
C:\Users\mthar\projects\enterprise_bot\core\database.py             ⚠️ DOES NOT EXIST
```

#### Database
```
C:\Users\mthar\projects\enterprise_bot\db\migrations\              (migration files)
```

---

### Frontend Files

#### Stores
```
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\stores\admin.ts           (17 API calls)
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\stores\analytics.ts       (8 API calls)
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\stores\metrics.ts         (1 WS + fallback)
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\stores\observability.ts   (14 API calls) ⚠️ BLOCKED
```

#### Pages
```
C:\Users\mthar\projects\enterprise_bot\frontend\src\routes\admin\+page.svelte            ✅ WORKING
C:\Users\mthar\projects\enterprise_bot\frontend\src\routes\admin\users\+page.svelte      ✅ WORKING
C:\Users\mthar\projects\enterprise_bot\frontend\src\routes\admin\analytics\+page.svelte  ✅ WORKING
C:\Users\mthar\projects\enterprise_bot\frontend\src\routes\admin\audit\+page.svelte      ✅ WORKING
C:\Users\mthar\projects\enterprise_bot\frontend\src\routes\admin\system\+page.svelte     ✅ WORKING
C:\Users\mthar\projects\enterprise_bot\frontend\src\routes\admin\traces\+page.svelte     ⚠️ BLOCKED
C:\Users\mthar\projects\enterprise_bot\frontend\src\routes\admin\logs\+page.svelte       ⚠️ BLOCKED
C:\Users\mthar\projects\enterprise_bot\frontend\src\routes\admin\alerts\+page.svelte     ⚠️ BLOCKED
```

#### Components (Charts)
```
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\components\admin\charts\StatCard.svelte
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\components\admin\charts\LineChart.svelte
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\components\admin\charts\BarChart.svelte
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\components\admin\charts\DoughnutChart.svelte
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\components\admin\charts\RealtimeSessions.svelte
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\components\admin\charts\NerveCenterWidget.svelte
```

#### Components (Observability Panels)
```
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\components\admin\observability\SystemHealthPanel.svelte
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\components\admin\observability\RagPerformancePanel.svelte
C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\components\admin\observability\LlmCostPanel.svelte
```

---

## PART 9: QUICK REFERENCE

### Known Status Summary

#### Working ✅
- `/health/deep` - System health
- `/api/admin/users*` - User management (7 endpoints)
- `/api/admin/access/*` - Access control (2 endpoints)
- `/api/admin/dept-head/*` - Dept head management (2 endpoints)
- `/api/admin/super-user/*` - Super user management (2 endpoints)
- `/api/admin/audit` - Audit log
- `/api/admin/analytics/*` - Analytics dashboard (8 endpoints)
- `/api/metrics/*` - Real-time metrics (5 endpoints + WebSocket)
- `/ws/{session_id}` - Main chat WebSocket
- UI: Nerve center, Users, Analytics, Audit, System pages

#### Stubbed (501) 🔶
- `/api/admin/departments` - Departments list (use static instead)
- `/api/admin/stats` - Admin statistics (use analytics instead)
- `PUT /api/admin/users/{user_id}` - Update user
- `DELETE /api/admin/users/{user_id}` - Deactivate user
- `POST /api/admin/users/{user_id}/reactivate` - Reactivate user
- `PUT /api/admin/users/{user_id}/role` - Change role

#### Broken (Import Error) ❌
- `/api/admin/traces/*` - Distributed tracing (3 endpoints)
- `/api/admin/logs/*` - Structured logging (3 endpoints + WebSocket)
- `/api/admin/alerts/*` - Alert management (7 endpoints)
- Root Cause: Missing `core/database.py` module
- UI: Traces, Logs, Alerts pages (UI ready, backend blocked)

---

## PART 10: RECOMMENDED NEXT STEPS

### Immediate Actions (This Week)
1. **Create Build Sheet 1** - Database Infrastructure
   - Highest priority, unblocks 3 admin pages
   - Estimated 4-6 hours
   - Zero dependencies

2. **Review Migration Debt** - 501 Stub Endpoints
   - Decide: Keep stubs or implement?
   - If implement, create separate build sheet
   - Not blocking for observability stack

### Next Sprint
3. **Execute Build Sheet 2** - Tracing Instrumentation
   - Depends on Build Sheet 1
   - Estimated 6-8 hours
   - Unlocks distributed tracing visibility

4. **Execute Build Sheet 3** - Logging Instrumentation
   - Depends on Build Sheet 1 (can run parallel with Build Sheet 2)
   - Estimated 4-6 hours
   - Unlocks real-time log streaming

### Future Enhancements
5. **Execute Build Sheet 4** - Polish & Expand
   - Chart enhancements
   - Alert notifications
   - Metrics persistence (optional)

---

## BATTLE PLAN COMPLETE ✅

**Recon Status:** COMPLETE
**Deliverable:** Single document with full integration map
**Next Step:** Create Build Sheet 1 for database infrastructure
**Blockers:** None (all intelligence gathered)

**Key Findings:**
- 5 of 8 admin pages fully functional
- 3 of 8 admin pages blocked by single missing module
- Frontend UI 100% complete and waiting for backend data
- Clear critical path identified (4-6 hour fix for 14 endpoints)

**Recommendation:** Execute Build Sheet 1 immediately. Highest ROI fix in the codebase.
