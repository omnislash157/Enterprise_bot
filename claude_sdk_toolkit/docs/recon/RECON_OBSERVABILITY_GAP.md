# RECON MISSION: Observability Data Gap Analysis

## Mission Brief
The observability suite (metrics, traces, logs, alerts, nerve center) is fully built but **collecting zero data**. We need to find where the pipeline breaks.

**Symptom:** Admin dashboards show empty/zero state despite active testing
**Hypothesis:** Instrumentation layer isn't wired into request flow, or collectors aren't initialized

---

## AGENT DEPLOYMENT

### Agent 1: Backend Instrumentation Audit
**Focus:** Is data being captured and written?

```
INVESTIGATE:

1. MIDDLEWARE REGISTRATION (core/main.py)
   - Is metrics middleware actually attached to FastAPI app?
   - Search for: @app.middleware, app.add_middleware
   - Check startup events: Are collectors initialized?
   - Look for: MetricsCollector, HealthMonitor, TracingMiddleware instantiation
   
2. METRICS COLLECTOR (core/metrics.py)
   - How is MetricsCollector supposed to be called?
   - Is it a singleton? Class instance? Needs initialization?
   - What triggers a metric write? (request count, latency, etc.)
   - Check: Does it require Redis connection? Is that validated?
   
3. TRACING INSTRUMENTATION (core/tracing.py)
   - How are spans created? Decorator? Context manager?
   - Are any endpoints actually decorated with tracing?
   - Search entire codebase for: @trace, create_span, start_span
   
4. STRUCTURED LOGGING (core/structured_logging.py)
   - Is the structured logger replacing default logging?
   - Are request logs being captured or just app logs?
   - Check: logging.setLoggerClass or handler attachment

5. AUDIT LOGGING (core/audit.py)
   - Is AuditLogger.log() being called anywhere?
   - Check auth_service.py for audit calls
   - Is batch writer actually flushing to DB?

REPORT FORMAT:
- File: [filename]
- Expected: [what should happen]
- Actual: [what the code shows]
- Gap: [what's missing]
```

---

### Agent 2: Database State Verification
**Focus:** Are tables empty or receiving writes?

```
INVESTIGATE:

1. CHECK TABLE CONTENTS
   Run these queries against Azure PostgreSQL:
   
   -- Metrics table
   SELECT COUNT(*) FROM enterprise.metrics;
   SELECT * FROM enterprise.metrics ORDER BY created_at DESC LIMIT 5;
   
   -- System health
   SELECT COUNT(*) FROM enterprise.system_health;
   SELECT * FROM enterprise.system_health ORDER BY checked_at DESC LIMIT 5;
   
   -- Traces
   SELECT COUNT(*) FROM enterprise.traces;
   SELECT * FROM enterprise.traces ORDER BY started_at DESC LIMIT 5;
   
   -- Structured logs
   SELECT COUNT(*) FROM enterprise.structured_logs;
   SELECT * FROM enterprise.structured_logs ORDER BY timestamp DESC LIMIT 5;
   
   -- Audit log
   SELECT COUNT(*) FROM enterprise.audit_log;
   SELECT * FROM enterprise.audit_log ORDER BY created_at DESC LIMIT 5;
   
   -- Alerts
   SELECT COUNT(*) FROM enterprise.alerts;

2. CHECK TABLE SCHEMAS
   - Do tables exist? (migrations may not have run)
   - \dt enterprise.*
   - Are there any constraint violations in logs?

3. CHECK PERMISSIONS
   - Does the app user have INSERT rights?
   - Are there any RLS policies blocking writes?

REPORT FORMAT:
- Table: [name]
- Row count: [N]
- Last write: [timestamp or "never"]
- Schema status: [exists/missing/wrong]
```

---

### Agent 3: API Endpoint Audit
**Focus:** Do observability endpoints return data or 501s?

```
INVESTIGATE:

1. TEST EACH ENDPOINT (use curl or httpie)
   
   # Metrics
   GET /api/admin/metrics/summary
   GET /api/admin/metrics/timeseries?period=1h
   
   # Health
   GET /health
   GET /health/detailed
   GET /api/admin/health/history
   
   # Traces
   GET /api/admin/traces
   GET /api/admin/traces/{trace_id}
   
   # Logs
   GET /api/admin/logs
   GET /api/admin/logs/search?query=error
   
   # Alerts
   GET /api/admin/alerts
   GET /api/admin/alerts/active
   
   # Analytics (nerve center)
   GET /api/admin/analytics/overview
   GET /api/admin/analytics/sessions
   GET /api/admin/analytics/rag-performance

2. CHECK RESPONSE PATTERNS
   - 200 with empty array [] = endpoint works, no data
   - 501 Not Implemented = endpoint stub only
   - 500 = runtime error (check logs)
   - 404 = route not registered

3. TRACE ROUTE REGISTRATION
   - In core/main.py, find all router includes
   - Match against expected endpoints
   - List any missing routers

REPORT FORMAT:
- Endpoint: [path]
- Status: [code]
- Response: [summary]
- Issue: [none/stub/error/missing]
```

---

### Agent 4: Frontend-Backend Contract
**Focus:** Is frontend calling the right endpoints?

```
INVESTIGATE:

1. FRONTEND API CALLS
   Check these files for API URLs:
   - src/lib/api/analytics.ts
   - src/lib/api/metrics.ts
   - src/lib/api/observability.ts
   - src/lib/stores/*.ts (any that fetch admin data)
   
   Extract:
   - What endpoints are called?
   - What response shape is expected?
   - Are there error handlers?

2. ADMIN PAGES DATA FLOW
   Check these routes:
   - src/routes/admin/system/+page.svelte (health/metrics)
   - src/routes/admin/analytics/+page.svelte
   - src/routes/admin/traces/+page.svelte
   - src/routes/admin/logs/+page.svelte
   - src/routes/admin/alerts/+page.svelte
   
   For each:
   - onMount data fetching?
   - Store subscriptions?
   - Loading/error states?

3. NERVE CENTER COMPONENTS
   Check:
   - src/lib/components/NerveCenter/*.svelte
   - What data sources do they expect?
   - WebSocket subscriptions for real-time?

REPORT FORMAT:
- Component: [name]
- Data source: [endpoint/store/websocket]
- Expected shape: [interface]
- Fallback behavior: [loading/error/empty]
```

---

### Agent 5: Initialization & Lifecycle
**Focus:** Are background tasks running?

```
INVESTIGATE:

1. STARTUP SEQUENCE (core/main.py)
   Find @app.on_event("startup") handlers:
   - What gets initialized?
   - Are there try/except blocks hiding failures?
   - Check for: "initialized", "started", "ready" log messages
   
2. BACKGROUND TASKS
   - Is there a metrics collection loop?
   - Health check polling interval?
   - Log flush timer?
   - Search for: asyncio.create_task, BackgroundTasks, repeat_every
   
3. REDIS CONNECTION
   - Is Redis required for metrics?
   - What happens if Redis unavailable?
   - Check config.yaml for redis settings
   
4. ENVIRONMENT VARIABLES
   Check if these are set and documented:
   - METRICS_ENABLED
   - TRACING_ENABLED
   - Any feature flags that gate observability

5. GRACEFUL DEGRADATION
   - If a collector fails to init, does it log or silently skip?
   - Are there health checks for the health system itself?

REPORT FORMAT:
- Component: [name]
- Init location: [file:line]
- Dependencies: [list]
- Failure mode: [loud/silent/graceful]
```

---

## SYNTHESIS REQUIREMENTS

After all agents report, compile:

### Gap Summary Table
| Layer | Component | Status | Root Cause |
|-------|-----------|--------|------------|
| Middleware | Metrics | ??? | ??? |
| Middleware | Tracing | ??? | ??? |
| Collector | MetricsCollector | ??? | ??? |
| Database | Tables exist | ??? | ??? |
| Database | Data present | ??? | ??? |
| API | Endpoints | ??? | ??? |
| Frontend | Data binding | ??? | ??? |
| Lifecycle | Background tasks | ??? | ??? |

### Priority Fixes
Rank by impact:
1. [Highest impact fix]
2. [Second fix]
3. [etc.]

### Recommended Build Sheet Scope
Based on findings, recommend:
- Single fix? Multiple build sheets?
- Backend only? Full stack?
- Migration needed?

---

## EXECUTION

```bash
# Run with multiple agents
python claude_sdk_toolkit/claude_cli.py run -f RECON_OBSERVABILITY_GAP.md --agents 5

# Or interactive for complex investigation
python claude_sdk_toolkit/claude_cli.py chat
```

---

## SUCCESS CRITERIA

Recon complete when we know:
1. ✅ Which layer(s) are broken
2. ✅ Root cause for each gap
3. ✅ What code changes are needed
4. ✅ Scope for build sheet

**Deliverable:** Gap analysis report with specific file:line citations and recommended fixes
