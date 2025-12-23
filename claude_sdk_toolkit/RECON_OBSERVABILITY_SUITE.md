# RECON MISSION: Observability Suite Integration Mapping

## Objective
Map the complete integration landscape for building an in-house observability suite. We need to understand what exists, where instrumentation can be added, and how frontend/backend connect.

---

## PHASE 1: Backend Structure

### Task 1.1 - File Tree
```bash
# Get full backend structure
find . -type f -name "*.py" | grep -v __pycache__ | grep -v .venv | sort
```

### Task 1.2 - Main Application Entry
```bash
# Find main.py and understand router structure
cat main.py | head -200
```

### Task 1.3 - Existing Analytics Infrastructure
```bash
# Check analytics module structure
ls -la analytics/
cat analytics/analytics_routes.py
cat analytics/analytics_service.py
```

### Task 1.4 - WebSocket Handler
```bash
# Find WebSocket endpoint - this is where we'll instrument real-time metrics
grep -n "websocket" main.py -A 50
# Or if in separate file:
grep -rn "WebSocket" --include="*.py" | head -30
```

### Task 1.5 - RAG Pipeline
```bash
# Find enterprise RAG - need to understand where to instrument
cat core/enterprise_rag.py | head -100
# Find the query method
grep -n "def.*query\|def.*search\|def.*retrieve" core/enterprise_rag.py
```

### Task 1.6 - Cache Implementation
```bash
# Check existing cache (from changelog, Redis is in use)
cat core/cache.py
```

### Task 1.7 - LLM/Grok Integration
```bash
# Find where LLM calls happen
grep -rn "grok\|openai\|anthropic\|llm" --include="*.py" | grep -v __pycache__
# Check enterprise_twin for streaming
cat core/enterprise_twin.py | head -150
```

### Task 1.8 - Database Models
```bash
# Check if there's a models file or schema
ls -la models/ 2>/dev/null || ls -la core/models* 2>/dev/null
# Check for any existing metrics tables
grep -rn "CREATE TABLE.*metric\|CREATE TABLE.*log\|CREATE TABLE.*event" --include="*.sql" --include="*.py"
```

### Task 1.9 - Existing Admin Routes
```bash
# Check what admin endpoints exist
cat auth/admin_routes.py | head -100
# List all route files
ls -la auth/*routes*.py
```

---

## PHASE 2: Frontend Structure

### Task 2.1 - Route Structure
```bash
cd frontend
find src/routes -type f -name "*.svelte" | sort
```

### Task 2.2 - Admin Pages
```bash
# Check existing admin route structure
ls -la src/routes/admin/
cat src/routes/admin/+layout.svelte
cat src/routes/admin/+page.svelte | head -100
```

### Task 2.3 - Analytics Page (existing)
```bash
cat src/routes/admin/analytics/+page.svelte
```

### Task 2.4 - Store Structure
```bash
ls -la src/lib/stores/
# Check analytics store
cat src/lib/stores/analytics.ts
```

### Task 2.5 - Admin Components
```bash
ls -la src/lib/components/admin/
ls -la src/lib/components/admin/charts/
```

### Task 2.6 - StateMonitor (Phase 0)
```bash
cat src/lib/components/nervecenter/StateMonitor.svelte
```

### Task 2.7 - WebSocket Store
```bash
cat src/lib/stores/websocket.ts
```

### Task 2.8 - Chart Components
```bash
# List chart components
ls -la src/lib/components/admin/charts/
# Check one to understand pattern
cat src/lib/components/admin/charts/LineChart.svelte
cat src/lib/components/admin/charts/StatCard.svelte
```

### Task 2.9 - Threlte/3D Components
```bash
ls -la src/lib/components/admin/threlte/
cat src/lib/components/admin/threlte/NerveCenterScene.svelte | head -80
```

---

## PHASE 3: Integration Points Analysis

### Task 3.1 - API Base URL Pattern
```bash
# How does frontend connect to backend?
grep -rn "VITE_API_URL\|API_URL\|fetch(" src/lib/stores/ | head -20
```

### Task 3.2 - Auth Header Pattern
```bash
# How are authenticated requests made?
grep -rn "X-User-Email\|Authorization\|getHeaders" src/lib/stores/ | head -20
```

### Task 3.3 - WebSocket Message Types
```bash
# What message types flow through WebSocket?
grep -rn "type.*:" src/lib/stores/session.ts | head -30
grep -rn "msg_type\|message.*type" main.py | head -30
```

### Task 3.4 - Existing Instrumentation
```bash
# Any existing timing/metrics in backend?
grep -rn "time.time\|perf_counter\|latency\|duration" --include="*.py" | grep -v __pycache__ | head -30
```

### Task 3.5 - Logging Pattern
```bash
# How is logging currently done?
grep -rn "logger\.\|logging\." --include="*.py" | head -20
# Check if structured logging exists
grep -rn "structlog\|json.*log" --include="*.py"
```

---

## PHASE 4: Config & Environment

### Task 4.1 - Backend Config
```bash
cat config.yaml 2>/dev/null || cat config/config.yaml 2>/dev/null
# Or check for settings
grep -rn "Settings\|BaseSettings" --include="*.py" | head -10
```

### Task 4.2 - Frontend Environment
```bash
cd frontend
cat .env.example 2>/dev/null || cat .env 2>/dev/null
# Check vite config for env vars
grep -n "VITE_" vite.config.ts
```

### Task 4.3 - Railway/Deployment Config
```bash
cat railway.toml 2>/dev/null
cat Procfile 2>/dev/null
```

---

## DELIVERABLE

After running all tasks, compile findings into this structure:

```markdown
# OBSERVABILITY RECON RESULTS

## Backend Summary
- Main entry: [file]
- Router registration pattern: [how routers are added]
- Existing analytics: [endpoints, service methods]
- WebSocket location: [file:line]
- RAG pipeline: [file, key methods]
- Cache: [implementation details]
- LLM calls: [where streaming happens]
- Logging: [current pattern]

## Frontend Summary  
- Admin routes: [list]
- Stores: [list with purposes]
- Chart components: [list]
- API pattern: [how requests are made]
- WebSocket usage: [how messages are handled]

## Integration Points for Observability
1. [Point 1 - where and what]
2. [Point 2 - where and what]
...

## Existing Gaps
- [What's missing for full observability]

## Recommended Architecture
- [Based on what exists, how should we structure this]
```

---

## EXECUTION

Run this mission with:
```bash
python claude_sdk_toolkit/claude_cli.py run -f RECON_OBSERVABILITY_SUITE.md
```

Agent should execute each task, capture output, and compile the deliverable summary.
