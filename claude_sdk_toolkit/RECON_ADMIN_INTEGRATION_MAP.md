# RECON MISSION: Admin Endpoint & Integration Map

## Mission Brief
Map ALL admin endpoints (working and broken) and their frontend consumers to plan Option B: consolidate legacy analytics into the working observability stack.

**Goal:** Complete integration map showing what to keep, what to delete, what to expand

---

## AGENT DEPLOYMENT

### Agent 1: Backend Endpoint Audit
**Focus:** Every admin-related route in the codebase

```
INVESTIGATE:

1. FIND ALL ADMIN ROUTES
   Search for router definitions in:
   - auth/admin_routes.py
   - auth/analytics_engine/analytics_routes.py
   - auth/metrics_routes.py
   - auth/tracing_routes.py
   - auth/logging_routes.py
   - auth/alerting_routes.py
   - core/main.py (any inline routes)
   
   For each route found, document:
   - HTTP method (GET/POST/PUT/DELETE)
   - Full path (e.g., /api/admin/stats)
   - Handler function name
   - Implementation status: WORKING | 501_STUB | PARTIAL | ERROR

2. CATEGORIZE BY STATUS
   Group routes into:
   
   A. WORKING (returns real data):
      - List each endpoint
      - What database table(s) it queries
      - What it returns
   
   B. 501 STUBS (Not Implemented):
      - List each endpoint
      - What frontend expects it to return
      - Why it was stubbed (legacy? never built?)
   
   C. BROKEN (errors on call):
      - List each endpoint
      - Error type (import error, db error, etc.)

3. WEBSOCKET ENDPOINTS
   Find all WebSocket routes:
   - /ws (main chat)
   - /api/metrics/stream (legacy?)
   - Any others
   
   Document status of each.

4. CHECK ROUTE REGISTRATION
   In core/main.py, find:
   - app.include_router() calls
   - What prefix each router uses
   - Are any routers defined but not registered?

REPORT FORMAT:
| Endpoint | Method | Status | Handler | DB Table | Notes |
|----------|--------|--------|---------|----------|-------|
```

---

### Agent 2: Frontend API Consumer Audit
**Focus:** Every frontend file that calls admin endpoints

```
INVESTIGATE:

1. ADMIN STORE (src/lib/stores/admin.ts)
   Extract ALL API calls:
   - What endpoints are called?
   - What functions expose them?
   - What components consume these functions?
   
2. ANALYTICS STORE (src/lib/stores/analytics.ts)
   Extract ALL API calls:
   - Endpoint URLs
   - Expected response shapes
   - Consumer components

3. METRICS STORE (src/lib/stores/metrics.ts)
   - HTTP endpoints called
   - WebSocket connections (metrics/stream?)
   - Consumer components

4. OBSERVABILITY STORE (src/lib/stores/observability.ts)
   - All endpoint calls
   - This is the NEW working system - document fully

5. SEARCH ALL FETCH CALLS
   grep/search for:
   - fetch(`${API_URL}/api/admin
   - fetch.*api/admin
   - /api/metrics
   - /api/analytics
   
   Create complete list of all admin API calls in frontend.

REPORT FORMAT:
| Store/File | Function | Endpoint Called | Status | Consumers |
|------------|----------|-----------------|--------|-----------|
```

---

### Agent 3: Frontend Component Dependency Map
**Focus:** Which components use which data sources

```
INVESTIGATE:

1. ADMIN PAGES
   For each page in src/routes/admin/:
   - +page.svelte (home/nerve center)
   - users/+page.svelte
   - analytics/+page.svelte
   - audit/+page.svelte
   - system/+page.svelte (WORKING)
   - traces/+page.svelte
   - logs/+page.svelte
   - alerts/+page.svelte
   
   Document for each:
   - What stores does it import?
   - What API calls on mount?
   - What data does it display?
   - Is it WORKING or BROKEN?

2. NERVE CENTER COMPONENTS
   In src/lib/components/admin/threlte/:
   - NerveCenterScene.svelte
   - NeuralNetwork.svelte
   - NeuralNode.svelte
   - DataSynapse.svelte
   
   Document:
   - What data do they consume?
   - Are they connected to real data or mock?
   - Dependencies on broken endpoints?

3. CHART COMPONENTS
   In src/lib/components/admin/charts/:
   - StatCard.svelte
   - LineChart.svelte
   - BarChart.svelte
   - DoughnutChart.svelte
   - RealtimeSessions.svelte
   - NerveCenterWidget.svelte
   
   Document data sources for each.

4. OBSERVABILITY PANELS (WORKING)
   In src/lib/components/admin/observability/:
   - SystemHealthPanel.svelte
   - RagPerformancePanel.svelte
   - LlmCostPanel.svelte
   
   Document what makes these work vs others.

REPORT FORMAT:
| Component | Data Source | Status | Delete? | Expand? |
|-----------|-------------|--------|---------|---------|
```

---

### Agent 4: Database Table → Endpoint → UI Map
**Focus:** Trace data flow end-to-end

```
INVESTIGATE:

1. MAP WORKING DATA FLOWS
   For tables that HAVE data pathways:
   
   enterprise.request_metrics → ? → ?
   enterprise.llm_call_metrics → ? → ?
   enterprise.rag_metrics → ? → ?
   enterprise.cache_metrics → ? → ?
   enterprise.system_metrics → ? → ?
   enterprise.traces → /api/admin/traces → ?
   enterprise.structured_logs → /api/admin/logs → ?
   enterprise.alerts → /api/admin/alerts → ?
   
   Fill in the ? with actual endpoint and UI component.

2. FIND ORPHANED TABLES
   Tables with NO endpoint serving them:
   - List table
   - What data it contains
   - Should it be exposed?

3. FIND ORPHANED ENDPOINTS
   Endpoints with NO UI consuming them:
   - List endpoint
   - What it returns
   - Should UI be built?

4. FIND ORPHANED UI
   Components expecting data that doesn't exist:
   - List component
   - What endpoint it calls
   - Should be deleted or rewired?

REPORT FORMAT:
## Working Flows
DB Table → Endpoint → UI Component → STATUS

## Orphaned Tables (no endpoint)
- table_name: [description]

## Orphaned Endpoints (no UI)
- /endpoint: [returns what]

## Orphaned UI (no data)
- Component: [calls what broken endpoint]
```

---

## SYNTHESIS REQUIREMENTS

After all agents report, compile:

### Master Integration Map

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATABASE LAYER                           │
├─────────────────────────────────────────────────────────────────┤
│ ✅ CONNECTED    │ ⚠️ ORPHANED     │ ❌ MISSING                  │
│ - table         │ - table         │ - expected table            │
└────────┬────────┴────────┬────────┴────────┬────────────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        ENDPOINT LAYER                           │
├─────────────────────────────────────────────────────────────────┤
│ ✅ WORKING      │ 🔶 501 STUB     │ ❌ BROKEN                   │
│ - /endpoint     │ - /endpoint     │ - /endpoint                 │
└────────┬────────┴────────┬────────┴────────┬────────────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                           │
├─────────────────────────────────────────────────────────────────┤
│ ✅ DISPLAYS DATA│ ⚠️ EMPTY/ERROR  │ ❌ CRASHES                  │
│ - Component     │ - Component     │ - Component                 │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

### Option B Execution Plan

Based on findings, categorize:

**DELETE (legacy, unrepairable):**
- [ ] Component/file 1
- [ ] Component/file 2

**KEEP (working):**
- [ ] Component/file 1
- [ ] Component/file 2

**EXPAND (working, needs more data):**
- [ ] Component: add X data source
- [ ] Endpoint: add Y query

**REWIRE (good UI, wrong data source):**
- [ ] Component: change from X to Y endpoint

### Recommended Build Sheet Scope

Single build sheet or multiple phases?
Estimated effort per phase?
Dependencies between phases?

---

## EXECUTION

```bash
# Run with 4 parallel agents
python claude_sdk_toolkit/claude_cli.py run -f RECON_ADMIN_INTEGRATION_MAP.md --agents 4
```

---

## SUCCESS CRITERIA

Recon complete when we have:
1. ✅ Complete endpoint inventory with status
2. ✅ Complete frontend consumer map
3. ✅ Complete component dependency graph
4. ✅ Clear DELETE / KEEP / EXPAND / REWIRE lists
5. ✅ Scope estimate for Option B build sheet

**Deliverable:** Integration map with specific file paths and recommended actions

---

## QUICK REFERENCE

Known 501 stubs from console errors:
- `/api/admin/departments` - 501
- `/api/admin/stats` - 501

Known broken WebSocket:
- `wss://*/api/metrics/stream` - Connection fails

Known working:
- `/health/deep` - System health
- `/api/admin/traces` - Tracing
- `/api/admin/logs` - Logging
- `/api/admin/alerts` - Alerting

Known working UI:
- System Health tab
- (others TBD)
