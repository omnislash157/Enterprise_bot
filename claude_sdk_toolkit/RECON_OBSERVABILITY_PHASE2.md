# RECON MISSION: Phase 2 Observability - Tracing, Logs, Alerts

## Objective
Map integration points for distributed tracing, structured logging, and alerting. We need to understand the request lifecycle, current logging patterns, and notification capabilities.

---

## PHASE 1: Request Lifecycle Mapping

### Task 1.1 - HTTP Request Entry Points
```bash
# Find all route definitions
grep -rn "@app\.\|@router\." --include="*.py" | grep -E "get|post|put|delete|patch" | head -40
```

### Task 1.2 - WebSocket Message Flow
```bash
# Map WebSocket message handling
grep -n "websocket\|receive_json\|send_json" core/main.py | head -30
```

### Task 1.3 - Middleware Chain
```bash
# Find all middleware
grep -rn "@app.middleware\|add_middleware" --include="*.py"
```

### Task 1.4 - Request → RAG → LLM Flow
```bash
# Trace the call chain from message receipt to response
grep -n "async def.*message\|EnterpriseRAG\|EnterpriseTwin\|model_adapter" core/main.py | head -20

# Check enterprise_twin orchestration
grep -n "def\|async def" core/enterprise_twin.py | head -30
```

---

## PHASE 2: Current Logging Analysis

### Task 2.1 - Logger Definitions
```bash
# Find all logger instantiations
grep -rn "getLogger\|logging\." --include="*.py" | grep -v __pycache__ | head -30
```

### Task 2.2 - Log Statement Patterns
```bash
# Sample log statements to understand current format
grep -rn "logger\.\(info\|warning\|error\|debug\)" --include="*.py" | grep -v __pycache__ | head -50
```

### Task 2.3 - Log Prefixes/Tags
```bash
# Find structured prefixes like [STARTUP], [WS], [RAG], etc.
grep -rn '\[.*\]' --include="*.py" | grep "logger\." | head -30
```

### Task 2.4 - Error Handling Patterns
```bash
# Find try/except blocks and how errors are logged
grep -rn "except.*:\|logger\.error\|logger\.exception" --include="*.py" | grep -v __pycache__ | head -40
```

### Task 2.5 - Current Log Output
```bash
# Check if there's logging config
cat logging.conf 2>/dev/null || grep -rn "basicConfig\|dictConfig" --include="*.py" | head -10
```

---

## PHASE 3: Trace Context Injection Points

### Task 3.1 - Request ID / Correlation ID
```bash
# Check if any trace/request/correlation IDs exist
grep -rn "trace_id\|request_id\|correlation\|x-request" --include="*.py" | head -20
```

### Task 3.2 - Session ID Flow
```bash
# Session IDs that could be used for correlation
grep -rn "session_id\|session\[" --include="*.py" | head -20
```

### Task 3.3 - User Context Flow
```bash
# How user email/context flows through
grep -rn "user_email\|current_user\|X-User-Email" --include="*.py" | head -20
```

### Task 3.4 - Department/Division Context
```bash
# Department context that flows through requests
grep -rn "department\|division" --include="*.py" | grep -v __pycache__ | head -20
```

---

## PHASE 4: Timing Instrumentation Audit

### Task 4.1 - Existing Timing Code
```bash
# Find all timing instrumentation
grep -rn "time\.time\|perf_counter\|elapsed\|duration\|_ms\|latency" --include="*.py" | grep -v __pycache__ | head -40
```

### Task 4.2 - metrics_collector Usage
```bash
# How is the new metrics_collector being used?
grep -rn "metrics_collector\." --include="*.py" | head -30
```

### Task 4.3 - Timing in RAG Pipeline
```bash
# Specific timing in enterprise_rag.py
grep -n "time\.\|start\|elapsed\|_ms" core/enterprise_rag.py | head -20
```

### Task 4.4 - Timing in LLM Calls
```bash
# Timing in model_adapter.py
grep -n "time\.\|start\|elapsed\|first_token\|ttft" core/model_adapter.py | head -20
```

---

## PHASE 5: Alert/Notification Capabilities

### Task 5.1 - Email Configuration
```bash
# Check for email sending capability
grep -rn "smtp\|sendmail\|email\|mail" --include="*.py" --include="*.env*" | head -20
```

### Task 5.2 - Slack/Webhook Integration
```bash
# Any existing webhook/Slack integration
grep -rn "slack\|webhook\|notify\|alert" --include="*.py" | head -20
```

### Task 5.3 - Environment Variables for Notifications
```bash
# Check .env or config for notification settings
grep -rn "SLACK\|WEBHOOK\|SMTP\|EMAIL\|NOTIFY\|ALERT" --include="*.env*" --include="*.py" | head -20
```

### Task 5.4 - Background Task Capability
```bash
# Any background task/scheduler setup (for periodic alerts)
grep -rn "celery\|rq\|background\|scheduler\|cron\|asyncio.create_task" --include="*.py" | head -20
```

---

## PHASE 6: Database Schema Review

### Task 6.1 - Existing Observability Tables
```bash
# Check what observability tables exist
cat migrations/007_observability_tables.sql
```

### Task 6.2 - Query Log Table Structure
```bash
# Check analytics tables for log-like data
grep -rn "query_log\|analytics_events" --include="*.py" --include="*.sql" | head -20
```

### Task 6.3 - Foreign Key Opportunities
```bash
# Check for user/department tables we could link to
grep -rn "CREATE TABLE\|REFERENCES" --include="*.sql" | head -30
```

---

## PHASE 7: Frontend Integration Points

### Task 7.1 - Existing Admin Routes
```bash
cd frontend
ls -la src/routes/admin/
```

### Task 7.2 - WebSocket Message Types
```bash
# What message types does frontend handle?
grep -rn "type.*:\|msg\.type\|data\.type" src/lib/stores/ | head -30
```

### Task 7.3 - Toast/Notification System
```bash
# How does frontend show notifications?
grep -rn "toast\|notify\|alert" src/lib/ | head -20
```

### Task 7.4 - Existing Chart Infrastructure
```bash
# What visualization components exist?
ls -la src/lib/components/admin/charts/
```

---

## PHASE 8: External Service Inventory

### Task 8.1 - API Integrations
```bash
# What external APIs are called?
grep -rn "https://\|http://" --include="*.py" | grep -v __pycache__ | grep -v "#" | head -20
```

### Task 8.2 - Database Connections
```bash
# Database connection patterns
grep -rn "asyncpg\|psycopg\|connection\|pool" --include="*.py" | head -20
```

### Task 8.3 - Redis Usage
```bash
# Redis client usage
grep -rn "redis\|Redis\|aioredis" --include="*.py" | head -20
```

### Task 8.4 - AI Provider Calls
```bash
# LLM/Embedding API calls
grep -rn "openai\|anthropic\|xai\|grok\|deepinfra\|embedding" --include="*.py" | head -30
```

---

## DELIVERABLE

After running all tasks, compile findings into this structure:

```markdown
# PHASE 2 OBSERVABILITY RECON RESULTS

## Request Lifecycle
- Entry points: [HTTP routes, WebSocket handler]
- Middleware chain: [list in order]
- Call flow: [Request → RAG → LLM → Response]
- Context carriers: [session_id, user_email, department]

## Current Logging
- Logger pattern: [how loggers are created]
- Log format: [current format, prefixes used]
- Log levels used: [INFO, WARNING, ERROR, DEBUG]
- Gaps: [what's not being logged that should be]

## Trace Injection Points
- Request entry: [where to generate trace_id]
- Context propagation: [how to pass trace through calls]
- Span boundaries: [logical operations to time]
  - HTTP request handling
  - WebSocket message processing  
  - RAG embedding generation
  - RAG vector search
  - LLM API call
  - Response streaming

## Alert Integration
- Email capability: [yes/no, config needed]
- Slack/Webhook: [existing or needs setup]
- Background tasks: [how to run periodic checks]

## Database
- Tables available: [list]
- Schema for traces: [recommendation]
- Schema for logs: [recommendation]
- Schema for alerts: [recommendation]

## Frontend
- Routes to add: [/admin/traces, /admin/logs, /admin/alerts]
- Components to build: [TraceWaterfall, LogViewer, AlertConfig]
- Real-time updates: [WebSocket patterns to use]

## Recommended Architecture

### Distributed Tracing
[Diagram/description of trace flow]

### Log Aggregation  
[Diagram/description of log collection]

### Alert Engine
[Diagram/description of alert flow]

## Implementation Priority
1. [Highest impact, lowest effort first]
2. [...]
3. [...]
```

---

## EXECUTION

Run this mission with:
```bash
python claude_sdk_toolkit/claude_cli.py run -f RECON_OBSERVABILITY_PHASE2.md
```

Agent should execute each task, capture output, and compile the deliverable summary.
