# PHASE 2 OBSERVABILITY RECON RESULTS

**Date:** 2024-12-23
**Mission:** Map integration points for distributed tracing, structured logging, and alerting

---

## Executive Summary

Comprehensive reconnaissance of the enterprise_bot codebase has identified all key integration points for observability infrastructure. The system already has foundational metrics collection via `metrics_collector`, basic structured logging with prefixes like `[Admin]`, `[ANALYTICS]`, `[Cache]`, and database tables ready for observability data. This report details the findings across 8 phases of investigation.

---

## 1. Request Lifecycle

### Entry Points

**HTTP Routes (FastAPI):**
- SSO/Auth routes: `/api/config`, `/api/verify-email`, `/api/whoami`, `/api/admin/users`
- Core routes: `/health`, `/`, `/api/config`, `/api/upload/chat`, `/api/departments`, `/api/content`, `/api/analytics`
- Admin routes: User management, department access, audit logs (`auth/admin_routes.py`)
- Analytics routes: Dashboard, queries, events (`auth/analytics_engine/analytics_routes.py`)
- Metrics routes: Real-time WebSocket metrics stream (`auth/metrics_routes.py`)

**WebSocket Handler:**
- Single WebSocket endpoint: `/ws/{session_id}` (line 702 in `core/main.py`)
- Manages active connections via `ConnectionManager` class
- Handles message types: `ping`, `pong`, `message`, `artifact`, etc.
- Receives via `websocket.receive_json()`, sends via `websocket.send_json()`

### Middleware Chain

1. **CORS Middleware** (line 313): `CORSMiddleware` with allowed origins, methods, headers
2. **GZip Middleware** (line 323): Compression for responses >500 bytes
3. **Custom Timing Middleware** (line 326): `@app.middleware("http")` decorator
   - Measures request latency with `time.perf_counter()`
   - Calls `metrics_collector.record_request(endpoint, elapsed_ms, error=is_error)`
   - This is the **primary injection point for distributed tracing**

### Call Flow: Request → RAG → LLM → Response

```
WebSocket Message
    ↓
websocket_endpoint() [core/main.py:703]
    ↓
await websocket.receive_json()
    ↓
Parse data.type (message, ping, etc.)
    ↓
If type == 'message':
    ↓
EnterpriseTwin.think_streaming() [core/enterprise_twin.py:509]
    ↓
EnterpriseRAGRetriever.retrieve() [core/enterprise_rag.py:200]
    ↓ (embedding + search timing tracked)
ModelAdapter.generate_streaming() [core/model_adapter.py:168]
    ↓ (TTFT + latency tracked)
Stream chunks back via websocket.send_json()
```

**Key Orchestration Points:**
- `EnterpriseTwin.__init__()` - Line 228: Initializes RAG and ModelAdapter
- `EnterpriseTwin.think_streaming()` - Line 509: Main orchestration method
- `EnterpriseTwin._build_system_prompt()` - Line 599: Context assembly
- `EnterpriseRAGRetriever.retrieve()` - Line 200: RAG pipeline
- `ModelAdapter.generate_streaming()` - Line 168: LLM API call

### Context Carriers

- **session_id**: WebSocket path parameter, used throughout request lifecycle
- **user_email**: Extracted from `X-User-Email` header (trusted proxy mode) or JWT
- **department**: Derived from user's department_access field, used in RAG filtering
- **trace_id**: Currently only in `CogTwin` for training mode (line 281, 339, 428), NOT in EnterpriseTwin yet

---

## 2. Current Logging

### Logger Pattern

**Standard Pattern:** `logger = logging.getLogger(__name__)`

All modules use Python's standard logging library with module-level loggers:
- 30+ files follow this pattern
- Configured via `logging.basicConfig(level=logging.INFO)` in `core/main.py` (line 34)
- No centralized dictConfig or custom handlers (yet)

### Log Format

**Current Format:** Default Python logging format
```
INFO:core.main:[STARTUP] Initializing Redis cache...
INFO:auth.analytics_engine.analytics_service:[ANALYTICS] Query logged: technical | 1234ms | session=abc123
```

**Prefixes Used:**
- `[STARTUP]` - Initialization events
- `[Admin]` - Admin operations (user management, permissions)
- `[ANALYTICS]` - Query/event logging
- `[POOL]` - Database connection pool events
- `[PERF]` - Performance timing logs
- `[Audit]` - Audit trail events
- `[AuthService]` - Authentication/authorization actions
- `[Cache]` - Redis cache hits/misses
- `[EnterpriseRAG]` - RAG retrieval operations
- `[Metrics WS]` - Metrics WebSocket events

### Log Levels Used

- **INFO**: Most common - startup, operations, query logging, metrics
- **WARNING**: Cache failures, token expiry, unknown actions
- **ERROR**: Exception handling, API failures, database errors
- **DEBUG**: Cache hits/misses (conditional), detailed flow

### Gaps Identified

1. **No structured JSON logging** - Current logs are string-based, hard to parse
2. **No trace_id propagation** - Except in CogTwin (training mode), not in EnterpriseTwin
3. **No request_id/correlation_id** - Can't correlate logs across service boundaries
4. **Inconsistent timing** - Some use `time.time()`, some `perf_counter()`
5. **No log aggregation** - Logs not stored in database for querying
6. **No log levels per module** - All modules use INFO (no granular control)
7. **Missing context in exceptions** - `logger.exception()` used but no rich context

---

## 3. Trace Injection Points

### Request Entry (HTTP)

**Middleware Injection Point:** `core/main.py:326` - `@app.middleware("http")`
- Currently measures timing only
- **ACTION NEEDED:** Generate `trace_id = uuid.uuid4().hex` at start of request
- **ACTION NEEDED:** Add to response headers: `X-Trace-ID: {trace_id}`
- **ACTION NEEDED:** Store in context variable for downstream access

### Request Entry (WebSocket)

**WebSocket Handler:** `core/main.py:703` - `websocket_endpoint()`
- Currently only tracks session_id
- **ACTION NEEDED:** Generate trace_id per message received
- **ACTION NEEDED:** Include in `data` dict: `{"trace_id": trace_id, "type": "message", ...}`
- **ACTION NEEDED:** Pass to EnterpriseTwin.think_streaming()

### Context Propagation

**Existing Context Flow:**
1. `session_id` → WebSocket path → EnterpriseTwin → RAG → stored in query_log
2. `user_email` → X-User-Email header → stored in analytics/audit tables
3. `department` → user.department_access → RAG filtering

**Proposed Trace Context Flow:**
```
Middleware/WebSocket Handler
    ↓ (generate trace_id)
contextvars.ContextVar("trace_id")
    ↓ (accessible anywhere in async context)
EnterpriseTwin.think_streaming(trace_id=trace_id)
    ↓
EnterpriseRAG.retrieve(trace_id=trace_id)
    ↓
ModelAdapter.generate_streaming(trace_id=trace_id)
    ↓
All log statements include trace_id
    ↓
All DB writes include trace_id
```

### Span Boundaries

**Critical Operations to Instrument:**

1. **HTTP Request Handling** (middleware)
   - Start: Request received
   - End: Response sent
   - Attributes: endpoint, method, status_code, user_email, department

2. **WebSocket Message Processing** (websocket_endpoint)
   - Start: Message received
   - End: Final chunk sent
   - Attributes: session_id, message_type, user_email

3. **RAG Embedding Generation** (EnterpriseRAG.retrieve)
   - Start: Line 239 `start_embed = time.time()`
   - End: Line 252 `embedding_ms = ...`
   - Attributes: query_length, cache_hit, embedding_provider

4. **RAG Vector Search** (EnterpriseRAG.retrieve)
   - Start: Line 255 `start_search = time.time()`
   - End: Line 274 `search_ms = ...`
   - Attributes: search_mode (semantic/keyword), chunks_retrieved, top_score

5. **LLM API Call** (ModelAdapter.generate_streaming)
   - Start: Line 135 `self._start_time = time.time()`
   - End: Line 152 `elapsed_ms = ...`
   - Attributes: model, provider, prompt_tokens, completion_tokens, ttft

6. **Response Streaming** (websocket loop)
   - Start: First token ready
   - End: Last chunk sent
   - Attributes: chunk_count, total_bytes

### Existing trace_id Infrastructure (CogTwin Only)

- `CogTwin` already has trace_id support for training mode:
  - `self.last_trace_id` (line 281)
  - `trace.id` stored in memory trace database
  - Used for ratings and training data
- **EnterpriseTwin does NOT have this yet**

---

## 4. Timing Instrumentation Audit

### Existing Timing Code

**Widespread Usage:**
- `time.time()` - 15+ occurrences (wall-clock time)
- `time.perf_counter()` - 2 occurrences (high-res timer) ✅ Preferred
- Patterns: `start = time.time()` → `elapsed_ms = (time.time() - start) * 1000`

**Key Locations:**
1. **analytics_service.py:70** - `@timing` decorator for DB queries
2. **enterprise_rag.py:209-298** - Full RAG pipeline timing (total, embedding, search)
3. **model_adapter.py:135-188** - LLM call timing + TTFT (streaming)
4. **main.py:337** - Middleware timing for HTTP requests

### metrics_collector Usage

**Heavily Used (25+ call sites):**

1. **Request Metrics:**
   - `metrics_collector.record_request(endpoint, elapsed_ms, error)` (main.py:337)

2. **WebSocket Metrics:**
   - `record_ws_connect()` - On connection (main.py:705)
   - `record_ws_message('in'/'out')` - Per message (main.py:729+)
   - `record_ws_disconnect()` - On close (main.py:988)

3. **RAG Metrics:**
   - `record_rag_query(total_ms, embedding_ms, search_ms, chunks)` (enterprise_rag.py:228, 285, 298)

4. **LLM Metrics:**
   - `record_llm_call(latency_ms, first_token_ms, tokens_in, tokens_out, model, provider, error)` (model_adapter.py:156-175)

5. **Metrics Endpoints:**
   - `/api/metrics/snapshot` - Current state
   - `/api/metrics/health` - Health check
   - `/api/metrics/system` - System resources
   - `/ws/metrics` - Real-time WebSocket stream

### Timing in RAG Pipeline

**enterprise_rag.py - Comprehensive Timing:**
```python
start_total = time.time()  # Line 209
embedding_ms = 0
search_ms = 0

# Embedding phase
start_embed = time.time()  # Line 239
# ... embedding logic ...
embedding_ms = (time.time() - start_embed) * 1000  # Line 252

# Search phase
start_search = time.time()  # Line 255
# ... search logic ...
search_ms = (time.time() - start_search) * 1000  # Line 274
elapsed_total = (time.time() - start_total) * 1000  # Line 275

# Record metrics
metrics_collector.record_rag_query(
    total_ms=elapsed_total,
    embedding_ms=embedding_ms,
    search_ms=search_ms,
    chunks=len(results)
)
```

**Cache Hit Detection:**
- Cache hits logged with timing (line 225)
- Cache misses also tracked

### Timing in LLM Calls

**model_adapter.py - TTFT Tracking:**
```python
self._start_time = time.time()  # Line 135
self._first_token_time = None

# During streaming:
if self._first_token_time is None:
    self._first_token_time = time.time()  # Line 188

# At end:
elapsed_ms = (time.time() - self._start_time) * 1000  # Line 152
first_token_ms = (self._first_token_time - self._start_time) * 1000  # Line 153

metrics_collector.record_llm_call(
    latency_ms=elapsed_ms,
    first_token_ms=first_token_ms,
    tokens_in=input_tokens,
    tokens_out=output_tokens,
    model=model_name,
    provider=provider,
    error=False
)
```

**Non-Streaming (Grok):**
- Start timing at line 304
- No TTFT (set to 0)
- Records on success/error

---

## 5. Alert/Notification Capabilities

### Email Configuration

**Limited Email Support:**
- **EMAIL_WHITELIST_PATH** environment variable (main.py:47)
- Used for access control, NOT for notifications
- No SMTP configuration found
- **RECOMMENDATION:** Add SMTP settings to .env for alert emails

```env
# Proposed .env additions
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@company.com
SMTP_PASSWORD=***
ALERT_RECIPIENTS=ops-team@company.com,devops@company.com
```

### Slack/Webhook Integration

**No Existing Integration:**
- No Slack client or webhook code found
- Keywords `slack`, `webhook` only appear in:
  - Semantic tagging patterns (memory/ingest/semantic_tagger.py:35) - false positive
  - Heuristic enricher (memory/heuristic_enricher.py:89) - "alert" as a keyword
- **RECOMMENDATION:** Add webhook support for critical alerts

```python
# Proposed webhook handler
import aiohttp

async def send_alert_webhook(severity: str, message: str, details: dict):
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if not webhook_url:
        return

    payload = {
        "severity": severity,  # "critical", "warning", "info"
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "details": details
    }

    async with aiohttp.ClientSession() as session:
        await session.post(webhook_url, json=payload)
```

### Environment Variables for Notifications

**Current State:**
- No SLACK_*, WEBHOOK_*, SMTP_*, NOTIFY_*, ALERT_* variables found
- Only EMAIL_WHITELIST_PATH exists

**Proposed .env Additions:**
```env
# Alert Configuration
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
ALERT_EMAIL_ENABLED=true
ALERT_THRESHOLDS_ERROR_RATE=0.05  # 5% error rate triggers alert
ALERT_THRESHOLDS_LATENCY_P99=5000  # 5s p99 latency triggers alert
ALERT_THRESHOLDS_LLM_COST_HOURLY=50.0  # $50/hour LLM spend triggers alert
```

### Background Task Capability

**Existing Infrastructure:**

1. **asyncio.create_task()** - Used for background tasks:
   - `claude_cli.py:402` - Interrupt monitor task
   - `memory/memory_pipeline.py:246` - Background memory processing loop

2. **No Job Scheduler:**
   - No Celery, RQ, APScheduler, or cron setup
   - No periodic health checks
   - **RECOMMENDATION:** Add APScheduler for periodic alert checks

```python
# Proposed alert scheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=5)
async def check_system_health():
    metrics = metrics_collector.get_snapshot()

    # Check error rate
    if metrics.get("error_rate", 0) > 0.05:
        await send_alert_webhook(
            "critical",
            "Error rate exceeds 5%",
            {"error_rate": metrics["error_rate"]}
        )

    # Check latency
    if metrics.get("p99_latency_ms", 0) > 5000:
        await send_alert_webhook(
            "warning",
            "P99 latency exceeds 5s",
            {"p99_latency_ms": metrics["p99_latency_ms"]}
        )

# Start scheduler at app startup
@app.on_event("startup")
async def start_scheduler():
    scheduler.start()
```

---

## 6. Database Schema

### Existing Observability Tables

**migrations/007_observability_tables.sql - 5 Tables:**

1. **enterprise.request_metrics** (line 7)
   - Columns: id, timestamp, endpoint, method, status_code, response_time_ms, user_email, department, request_size_bytes, response_size_bytes, trace_id
   - Indexes: timestamp, endpoint, status_code
   - **Status:** ✅ Ready for use

2. **enterprise.system_metrics** (line 26)
   - Columns: id, timestamp, metric_type, metric_name, value, unit, tags (JSONB)
   - Indexes: timestamp, (metric_type, metric_name)
   - **Status:** ✅ Ready for use

3. **enterprise.llm_call_metrics** (line 40)
   - Columns: id, timestamp, model, provider, prompt_tokens, completion_tokens, total_tokens, elapsed_ms, first_token_ms, user_email, department, query_category, trace_id, cost_usd, success, error_message
   - Indexes: timestamp, model, user_email, department
   - **Status:** ✅ Ready for use

4. **enterprise.rag_metrics** (line 65)
   - Columns: id, timestamp, trace_id, user_email, department, query_hash, total_ms, embedding_ms, vector_search_ms, rerank_ms, chunks_retrieved, chunks_used, cache_hit, embedding_cache_hit, top_score, avg_score, threshold_used
   - Indexes: timestamp, department, cache_hit
   - **Status:** ✅ Ready for use

5. **enterprise.cache_metrics** (line 93)
   - Columns: id, timestamp, cache_type, hits, misses, hit_rate, memory_used_bytes, keys_count
   - Indexes: timestamp, cache_type
   - **Status:** ✅ Ready for use

### Existing Analytics Tables

**Used by analytics_service.py:**

1. **enterprise.query_log** (referenced 20+ times)
   - Stores all user queries with timing, tokens, category
   - Used by analytics dashboard

2. **enterprise.analytics_events** (referenced 10+ times)
   - Generic event logging (login, logout, errors)
   - Has session_id, user_email, department

### Schema Recommendations

#### 1. Distributed Traces Table

**Proposed: enterprise.distributed_traces**

```sql
CREATE TABLE IF NOT EXISTS enterprise.distributed_traces (
    trace_id VARCHAR(32) PRIMARY KEY,
    parent_trace_id VARCHAR(32),  -- For nested traces
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trace_type VARCHAR(50) NOT NULL,  -- 'http_request', 'websocket_message', 'background_job'

    -- Context
    user_email VARCHAR(255),
    department VARCHAR(50),
    session_id VARCHAR(100),

    -- Request info
    endpoint VARCHAR(255),
    method VARCHAR(10),
    status_code INTEGER,

    -- Timing
    duration_ms FLOAT NOT NULL,

    -- Metadata
    tags JSONB DEFAULT '{}',
    error BOOLEAN DEFAULT FALSE,
    error_message TEXT
);

CREATE INDEX idx_traces_timestamp ON enterprise.distributed_traces(timestamp DESC);
CREATE INDEX idx_traces_user ON enterprise.distributed_traces(user_email);
CREATE INDEX idx_traces_dept ON enterprise.distributed_traces(department);
CREATE INDEX idx_traces_error ON enterprise.distributed_traces(error) WHERE error = TRUE;
```

#### 2. Trace Spans Table

**Proposed: enterprise.trace_spans**

```sql
CREATE TABLE IF NOT EXISTS enterprise.trace_spans (
    span_id VARCHAR(32) PRIMARY KEY,
    trace_id VARCHAR(32) NOT NULL REFERENCES enterprise.distributed_traces(trace_id) ON DELETE CASCADE,
    parent_span_id VARCHAR(32),

    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    span_name VARCHAR(100) NOT NULL,  -- 'rag_embedding', 'vector_search', 'llm_call', 'response_stream'

    -- Timing
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    duration_ms FLOAT NOT NULL,

    -- Metadata
    attributes JSONB DEFAULT '{}',  -- Flexible key-value pairs
    events JSONB DEFAULT '[]',      -- Array of timestamped events within span

    error BOOLEAN DEFAULT FALSE,
    error_message TEXT
);

CREATE INDEX idx_spans_trace ON enterprise.trace_spans(trace_id);
CREATE INDEX idx_spans_timestamp ON enterprise.trace_spans(timestamp DESC);
CREATE INDEX idx_spans_name ON enterprise.trace_spans(span_name);
```

#### 3. Structured Logs Table

**Proposed: enterprise.structured_logs**

```sql
CREATE TABLE IF NOT EXISTS enterprise.structured_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Tracing context
    trace_id VARCHAR(32),
    span_id VARCHAR(32),

    -- Log metadata
    level VARCHAR(10) NOT NULL,  -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    logger_name VARCHAR(100) NOT NULL,  -- e.g., 'core.enterprise_rag'
    message TEXT NOT NULL,

    -- Context
    user_email VARCHAR(255),
    department VARCHAR(50),
    session_id VARCHAR(100),

    -- Request context
    endpoint VARCHAR(255),
    method VARCHAR(10),

    -- Exception info (if applicable)
    exc_info TEXT,

    -- Flexible attributes
    extra JSONB DEFAULT '{}'
);

CREATE INDEX idx_logs_timestamp ON enterprise.structured_logs(timestamp DESC);
CREATE INDEX idx_logs_level ON enterprise.structured_logs(level);
CREATE INDEX idx_logs_trace ON enterprise.structured_logs(trace_id);
CREATE INDEX idx_logs_user ON enterprise.structured_logs(user_email);
CREATE INDEX idx_logs_dept ON enterprise.structured_logs(department);
```

#### 4. Alert Rules Table

**Proposed: enterprise.alert_rules**

```sql
CREATE TABLE IF NOT EXISTS enterprise.alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Rule definition
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    severity VARCHAR(20) NOT NULL,  -- 'info', 'warning', 'critical'
    enabled BOOLEAN DEFAULT TRUE,

    -- Condition (SQL WHERE clause or metric threshold)
    condition_type VARCHAR(50) NOT NULL,  -- 'sql_query', 'metric_threshold', 'error_rate', 'cost_threshold'
    condition_config JSONB NOT NULL,  -- Flexible config per condition type

    -- Evaluation
    check_interval_minutes INTEGER DEFAULT 5,
    evaluation_window_minutes INTEGER DEFAULT 15,

    -- Notification
    notification_channels JSONB DEFAULT '["webhook"]',  -- ['email', 'slack', 'webhook']
    notification_config JSONB DEFAULT '{}',

    -- Deduplication
    cooldown_minutes INTEGER DEFAULT 30,  -- Don't re-alert for 30 min

    -- Metadata
    created_by VARCHAR(255),
    tags JSONB DEFAULT '{}'
);

CREATE INDEX idx_alert_rules_enabled ON enterprise.alert_rules(enabled) WHERE enabled = TRUE;
```

#### 5. Alert Instances Table

**Proposed: enterprise.alert_instances**

```sql
CREATE TABLE IF NOT EXISTS enterprise.alert_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id UUID NOT NULL REFERENCES enterprise.alert_rules(id) ON DELETE CASCADE,

    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- 'active', 'resolved', 'acknowledged'

    -- Alert details
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',

    -- Notifications sent
    notifications_sent JSONB DEFAULT '[]',  -- Array of {channel, sent_at, success}

    -- Resolution
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMPTZ,
    resolution_notes TEXT
);

CREATE INDEX idx_alert_instances_rule ON enterprise.alert_instances(rule_id);
CREATE INDEX idx_alert_instances_triggered ON enterprise.alert_instances(triggered_at DESC);
CREATE INDEX idx_alert_instances_status ON enterprise.alert_instances(status);
```

### Foreign Key Opportunities

**Existing Tables with FK Potential:**

1. **enterprise.users** - Referenced by:
   - audit_log.actor_user_id (db/migrations/004_audit_log.sql:8)
   - audit_log.target_user_id (db/migrations/004_audit_log.sql:10)
   - Could add FK from observability tables' user_email → users.email

2. **enterprise.documents** - Referenced by:
   - documents.parent_id (db/003_smart_documents.sql:108)
   - documents.supersedes_id (db/003_smart_documents.sql:126)

**Proposed Foreign Keys:**

```sql
-- Add user_id columns for proper FK relationships
ALTER TABLE enterprise.request_metrics ADD COLUMN user_id UUID;
ALTER TABLE enterprise.llm_call_metrics ADD COLUMN user_id UUID;
ALTER TABLE enterprise.rag_metrics ADD COLUMN user_id UUID;
ALTER TABLE enterprise.distributed_traces ADD COLUMN user_id UUID;
ALTER TABLE enterprise.structured_logs ADD COLUMN user_id UUID;

-- Add foreign keys
ALTER TABLE enterprise.request_metrics
    ADD CONSTRAINT fk_request_metrics_user
    FOREIGN KEY (user_id) REFERENCES enterprise.users(id) ON DELETE SET NULL;

ALTER TABLE enterprise.llm_call_metrics
    ADD CONSTRAINT fk_llm_metrics_user
    FOREIGN KEY (user_id) REFERENCES enterprise.users(id) ON DELETE SET NULL;

-- (repeat for other tables)

-- Keep user_email for denormalization (faster queries)
```

**Retention Policies (from 007 comments):**
- request_metrics: 30 days
- system_metrics: 7 days
- llm_call_metrics: 90 days (cost tracking)
- rag_metrics: 30 days
- cache_metrics: 7 days

---

## 7. Frontend Integration Points

### Existing Admin Routes

**Frontend Structure (frontend/src/routes/admin/):**
- `/admin` - Main dashboard (`+page.svelte`)
- `/admin/analytics` - Analytics dashboard
- `/admin/audit` - Audit log viewer
- `/admin/system` - System metrics (NEW - recently added)
- `/admin/users` - User management

**Layout:** `+layout.svelte` - Shared navigation for admin section

### Proposed New Routes

1. **/admin/traces** - Distributed trace viewer
   - Waterfall view of request traces
   - Filter by user, department, endpoint, time range
   - Drill down into spans

2. **/admin/logs** - Structured log viewer
   - Real-time log stream
   - Filter by level, logger, trace_id, user
   - Search functionality

3. **/admin/alerts** - Alert configuration & history
   - Manage alert rules
   - View active alerts
   - Alert history & acknowledgments

### WebSocket Message Types

**Existing Message Types (src/lib/stores/):**

**session.ts (line 93):**
- `data.type === 'set_division'` - Set user division
- `data.type === 'verify'` - Email verification
- `data.type === 'message'` - User message

**websocket.ts (line 95):**
- `data.type === 'artifact_emit'` - Code/artifact generation

**metrics.ts (line 160):**
- `msg.type === 'metrics_snapshot'` - Real-time metrics update

**Proposed New Message Types:**

1. **trace_update** - Real-time trace updates for active requests
   ```typescript
   {
       type: 'trace_update',
       trace_id: string,
       spans: Array<{span_id, name, duration_ms, status}>,
       status: 'active' | 'completed' | 'error'
   }
   ```

2. **log_event** - Real-time log streaming
   ```typescript
   {
       type: 'log_event',
       timestamp: string,
       level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR',
       logger: string,
       message: string,
       trace_id?: string,
       extra?: object
   }
   ```

3. **alert_triggered** - Real-time alert notifications
   ```typescript
   {
       type: 'alert_triggered',
       alert_id: string,
       rule_name: string,
       severity: 'info' | 'warning' | 'critical',
       message: string,
       details: object
   }
   ```

### Toast/Notification System

**Existing:** `src/lib/components/CheekyToast.svelte` (line 13)

```typescript
interface Toast {
    id: number;
    message: string;
    category: 'success' | 'error' | 'warning' | 'info';
}

// Usage:
toasts = [...toasts, toast];
```

**Integration Plan:**
- Use CheekyToast for alert notifications
- Add `alert` category for critical alerts
- Auto-dismiss after 10s for info/warning, manual dismiss for critical

### Existing Chart Infrastructure

**Chart Components (src/lib/components/admin/charts/):**

1. **BarChart.svelte** - Bar charts for metrics
2. **DoughnutChart.svelte** - Pie/donut charts
3. **LineChart.svelte** - Time series data
4. **StatCard.svelte** - Metric cards with icon
5. **RealtimeSessions.svelte** - Real-time session list
6. **NerveCenterWidget.svelte** - Custom widget template
7. **chartTheme.ts** - Consistent color palette

**Supporting Components:**
- **DateRangePicker.svelte** - Filter by date range
- **ExportButton.svelte** - Export data to CSV

**Proposed New Components:**

1. **TraceWaterfall.svelte** - Gantt-style trace visualization
   ```svelte
   <script>
       export let trace: Trace;
       export let spans: Span[];
   </script>

   <div class="waterfall">
       {#each spans as span}
           <div class="span-row" style="margin-left: {span.depth * 20}px">
               <div class="span-bar" style="width: {span.duration_ms / maxDuration * 100}%">
                   {span.name} ({span.duration_ms}ms)
               </div>
           </div>
       {/each}
   </div>
   ```

2. **LogViewer.svelte** - Scrollable log table with filters
   ```svelte
   <script>
       export let logs: Log[];
       let levelFilter = 'all';
       let searchQuery = '';
   </script>

   <div class="log-viewer">
       <div class="filters">
           <select bind:value={levelFilter}>...</select>
           <input bind:value={searchQuery} placeholder="Search logs..." />
       </div>
       <div class="log-table">
           {#each filteredLogs as log}
               <div class="log-entry log-{log.level.toLowerCase()}">
                   <span class="timestamp">{formatTime(log.timestamp)}</span>
                   <span class="level">{log.level}</span>
                   <span class="message">{log.message}</span>
               </div>
           {/each}
       </div>
   </div>
   ```

3. **AlertConfig.svelte** - Alert rule builder
   ```svelte
   <script>
       let rule: AlertRule = {
           name: '',
           severity: 'warning',
           condition_type: 'metric_threshold',
           condition_config: {},
           enabled: true
       };
   </script>

   <form on:submit={createRule}>
       <input bind:value={rule.name} placeholder="Rule name" />
       <select bind:value={rule.severity}>...</select>
       <!-- Dynamic condition builder based on condition_type -->
       <button type="submit">Create Rule</button>
   </form>
   ```

4. **AlertList.svelte** - Active alerts dashboard
   ```svelte
   <script>
       export let alerts: AlertInstance[];
   </script>

   <div class="alert-list">
       {#each alerts as alert}
           <div class="alert-card alert-{alert.severity}">
               <h3>{alert.message}</h3>
               <span class="time">{timeAgo(alert.triggered_at)}</span>
               <button on:click={() => acknowledgeAlert(alert.id)}>
                   Acknowledge
               </button>
           </div>
       {/each}
   </div>
   ```

---

## 8. External Service Inventory

### API Integrations

**External HTTP Calls:**

1. **Azure AD (Microsoft Identity Platform)**
   - Authority: `https://login.microsoftonline.com/{tenant_id}` (azure_auth.py:36)
   - Graph API: `https://graph.microsoft.com/v1.0` (azure_auth.py:37)
   - JWKS URL: `https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys` (azure_auth.py:251)
   - **Purpose:** SSO authentication, user provisioning, token validation
   - **Observability Needs:** Track auth latency, token refresh failures, user provisioning errors

2. **X.AI (Grok LLM)**
   - API Base: `https://api.x.ai/v1` (model_adapter.py:237)
   - Endpoints: `/chat/completions` (enterprise_twin.py:478)
   - **Purpose:** LLM inference (streaming + non-streaming)
   - **Observability Needs:** Track latency, TTFT, token usage, cost, errors

3. **DeepInfra (Embeddings)**
   - Endpoint: `https://api.deepinfra.com/v1/inference/BAAI/bge-m3` (embedder.py:79, enterprise_rag.py:71)
   - **Purpose:** Generate embeddings for RAG
   - **Observability Needs:** Track embedding latency, batch size, cache hit rate, failures

4. **Cloudflare Workers AI (Optional)**
   - URL: `https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/baai/bge-m3` (embedder.py:234)
   - **Purpose:** Alternative embedding provider
   - **Observability Needs:** Same as DeepInfra

5. **Railway API (Infrastructure Management)**
   - URL: `https://backboard.railway.app/graphql/v2` (railway_tools.py:56)
   - **Purpose:** Infrastructure automation (via claude_sdk_toolkit)
   - **Observability Needs:** Track deployment status, service health

### Database Connections

**PostgreSQL (asyncpg + psycopg2):**

1. **Async Pool (asyncpg):**
   - Not directly used in core app yet
   - Used in memory backends (memory/backends/postgres.py:32)

2. **Sync Pool (psycopg2):**
   - **ThreadedConnectionPool** (analytics_service.py:48)
   - Min connections: 2, Max connections: 10
   - Used by analytics_engine for all analytics queries
   - **Lifecycle:**
     - Created on first use: `get_pool()` (line 43)
     - Closed via `atexit.register(_close_pool)` (line 53)
   - **Observability Needs:**
     - Track pool exhaustion (all connections in use)
     - Track slow queries (>1s)
     - Track connection errors
     - Monitor active connection count

3. **Direct Connections:**
   - Some modules use direct psycopg2.connect() (not pooled)
   - **Risk:** Connection leaks if not properly closed

**Database Operations:**
- CRUD on users, departments, documents, chunks
- Analytics writes (query_log, analytics_events)
- Metrics writes (if observability tables used)
- Audit log writes

**Observability Needs:**
- Query performance monitoring
- Connection pool metrics
- Transaction rollback tracking
- Deadlock detection

### Redis Usage

**Redis Client (redis.asyncio):**

**Implementation:** `core/cache.py` - `RedisCache` class (line 41)

**Configuration:**
- URL from `REDIS_URL` environment variable (cache.py:199)
- Decode responses: True
- Max connections: 10 (default pool size)

**Lifecycle:**
- Initialized on app startup (main.py:397)
- Connection attempt at `await cache.connect()` (cache.py:58)
- Graceful degradation if Redis unavailable (cache.py:70) - logs warning, continues without cache

**Cache Types:**
1. **Embedding Cache:**
   - Key format: `embedding:{model}:{text_hash}`
   - TTL: 24 hours (cache.py:83)
   - Hit/miss logging (cache.py:97-99)

2. **RAG Results Cache:**
   - Key format: `rag:{query_hash}:{search_mode}`
   - TTL: 1 hour (cache.py:115)
   - Stores serialized search results

**Observability Needs:**
- Track hit rate (already logged, needs DB persistence)
- Track memory usage (Redis INFO command)
- Track eviction rate
- Track connection errors
- Alert on cache unavailability

**Fallback Behavior:**
- `NoOpCache` class (cache.py:183) - Stubs all methods, always returns miss
- Used when Redis connection fails

### AI Provider Call Patterns

**1. OpenAI SDK (used for X.AI):**

**Provider:** X.AI (Grok)
**Usage Locations:**
- `model_adapter.py:237` - Main LLM interface
- `claude_cli.py:308` - CLI tool
- `claude_chat.py:518` - Legacy chat interface

**Call Pattern (Streaming):**
```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1"
)

response = await client.chat.completions.create(
    model="grok-beta",
    messages=[...],
    stream=True,
    temperature=0.7
)

async for chunk in response:
    # Process streaming chunks
```

**Call Pattern (Non-Streaming):**
```python
response = await client.chat.completions.create(
    model="grok-beta",
    messages=[...],
    stream=False
)
# Access response.choices[0].message.content
```

**Observability Instrumentation:**
- Start timer before API call (model_adapter.py:135, 304)
- Track TTFT for streaming (model_adapter.py:187-188)
- Record metrics on completion (model_adapter.py:156-175)
- Handle errors and record (model_adapter.py:345-346)

**2. HTTP POST (used for embeddings):**

**Provider:** DeepInfra (bge-m3)
**Usage Location:** `enterprise_rag.py:240-251`, `embedder.py:79-120`

**Call Pattern:**
```python
import aiohttp

async with aiohttp.ClientSession() as session:
    async with session.post(
        "https://api.deepinfra.com/v1/inference/BAAI/bge-m3",
        headers={"Authorization": f"Bearer {DEEPINFRA_TOKEN}"},
        json={"inputs": text, "normalize": True}
    ) as resp:
        data = await resp.json()
        embedding = data["embeddings"][0]
```

**Observability Instrumentation:**
- Timing already tracked (enterprise_rag.py:239-252)
- Cache check before API call (enterprise_rag.py:218-236)
- Metrics recorded (enterprise_rag.py:228)

**3. Anthropic SDK (NOT currently used):**
- Only referenced in `openai\|anthropic` grep pattern
- Not actually imported or used in codebase
- **Future integration possible**

**Provider Comparison:**

| Provider | Model | Usage | Latency | Cost | Error Handling |
|----------|-------|-------|---------|------|----------------|
| X.AI | grok-beta | LLM | ~2-5s (TTFT ~500ms) | $5/1M tokens | ✅ Try/catch + metrics |
| DeepInfra | bge-m3 | Embeddings | ~200-800ms | $0.10/1M tokens | ✅ Try/catch + cache fallback |
| Cloudflare | bge-m3 | Embeddings (alt) | ~100-500ms | Free tier | ⚠️ Optional, not default |

**Observability Needs:**
- Track provider availability (uptime %)
- Track latency percentiles (p50, p95, p99)
- Track error rates by provider
- Track cost per hour/day/month
- Alert on:
  - Provider downtime (3+ consecutive failures)
  - Latency spikes (p99 > 10s)
  - Cost spikes (>$X/hour)
  - Rate limit errors

---

## 9. Recommended Architecture

### Distributed Tracing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ CLIENT REQUEST                                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ MIDDLEWARE (HTTP) / WEBSOCKET HANDLER                           │
│ • Generate trace_id = uuid.uuid4().hex                          │
│ • Store in contextvars.ContextVar("trace_id")                   │
│ • Create root span: "http_request" or "websocket_message"       │
│ • Add to response headers: X-Trace-ID                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ ENTERPRISE TWIN (Orchestration)                                 │
│ • Extract trace_id from context                                 │
│ • Create span: "twin_think"                                     │
│ • Pass trace_id to RAG and ModelAdapter                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
           ┌─────────────┴─────────────┐
           ▼                           ▼
┌──────────────────────┐    ┌──────────────────────┐
│ RAG RETRIEVER        │    │ MODEL ADAPTER        │
│ • Create span:       │    │ • Create span:       │
│   "rag_retrieve"     │    │   "llm_generate"     │
│ • Sub-spans:         │    │ • Record TTFT        │
│   - rag_embed        │    │ • Stream chunks      │
│   - vector_search    │    │                      │
└──────────────────────┘    └──────────────────────┘
           │                           │
           └─────────────┬─────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ OBSERVABILITY PIPELINE                                          │
│ • Write spans to enterprise.trace_spans                         │
│ • Write trace summary to enterprise.distributed_traces          │
│ • Write metrics to enterprise.llm_call_metrics, rag_metrics     │
│ • Write logs to enterprise.structured_logs (with trace_id)      │
└─────────────────────────────────────────────────────────────────┘
```

**Key Components:**

1. **TraceContext (contextvars):**
```python
from contextvars import ContextVar

trace_context = ContextVar("trace_context", default=None)

@dataclass
class TraceContext:
    trace_id: str
    span_stack: List[str]  # Stack of active span_ids
    user_email: Optional[str]
    department: Optional[str]
    session_id: Optional[str]
```

2. **Span Manager:**
```python
@asynccontextmanager
async def create_span(name: str, attributes: Dict = None):
    ctx = trace_context.get()
    span_id = uuid.uuid4().hex[:16]
    start_time = datetime.now()

    # Push span onto stack
    ctx.span_stack.append(span_id)

    try:
        yield span_id
    except Exception as e:
        # Record error in span
        await record_span_error(span_id, e)
        raise
    finally:
        # Pop span from stack
        ctx.span_stack.pop()

        # Record span to DB
        await db.execute(
            """
            INSERT INTO enterprise.trace_spans
            (span_id, trace_id, parent_span_id, span_name, start_time, end_time, duration_ms, attributes)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            span_id, ctx.trace_id, ctx.span_stack[-1] if ctx.span_stack else None,
            name, start_time, datetime.now(), (datetime.now() - start_time).total_seconds() * 1000,
            json.dumps(attributes or {})
        )
```

**Usage Example:**
```python
async def think_streaming(...):
    async with create_span("twin_think", {"user": user_email}):
        # RAG retrieval
        async with create_span("rag_retrieve", {"query": query[:50]}):
            results = await rag.retrieve(query)

        # LLM generation
        async with create_span("llm_generate", {"model": model}):
            async for chunk in model_adapter.generate_streaming(...):
                yield chunk
```

### Log Aggregation

```
┌─────────────────────────────────────────────────────────────────┐
│ APPLICATION CODE                                                │
│ logger.info("Message", extra={"trace_id": ctx.trace_id, ...})   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ CUSTOM LOG HANDLER (StructuredLogHandler)                       │
│ • Extract trace_id from contextvars or log record              │
│ • Format as JSON                                                │
│ • Enrich with user_email, department, endpoint                  │
│ • Write to enterprise.structured_logs (async)                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ DATABASE (enterprise.structured_logs)                           │
│ • Indexed by timestamp, level, trace_id                         │
│ • Queryable via SQL                                             │
│ • Real-time tail via PostgreSQL LISTEN/NOTIFY                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND LOG VIEWER (/admin/logs)                               │
│ • WebSocket stream of new logs                                  │
│ • Filters: level, logger, trace_id, user, department            │
│ • Search: full-text search on message                           │
│ • Click trace_id → jump to trace viewer                         │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import logging
from logging import Handler

class StructuredLogHandler(Handler):
    def __init__(self, db_pool):
        super().__init__()
        self.db_pool = db_pool

    def emit(self, record: logging.LogRecord):
        ctx = trace_context.get()

        log_data = {
            "timestamp": datetime.now(),
            "level": record.levelname,
            "logger_name": record.name,
            "message": record.getMessage(),
            "trace_id": ctx.trace_id if ctx else None,
            "user_email": ctx.user_email if ctx else None,
            "department": ctx.department if ctx else None,
            "exc_info": self.format(record) if record.exc_info else None,
            "extra": {k: v for k, v in record.__dict__.items() if k not in STANDARD_ATTRS}
        }

        # Async write to DB (via queue to avoid blocking)
        log_queue.put_nowait(log_data)

# Setup in main.py
log_handler = StructuredLogHandler(db_pool)
log_handler.setLevel(logging.INFO)
logging.root.addHandler(log_handler)
```

**PostgreSQL LISTEN/NOTIFY for Real-time Logs:**

```sql
-- Trigger on structured_logs table
CREATE OR REPLACE FUNCTION notify_log_insert() RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('log_events', row_to_json(NEW)::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_insert_trigger
AFTER INSERT ON enterprise.structured_logs
FOR EACH ROW EXECUTE FUNCTION notify_log_insert();
```

```python
# WebSocket endpoint for log streaming
@app.websocket("/ws/logs")
async def logs_websocket(websocket: WebSocket):
    await websocket.accept()

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("LISTEN log_events")

            async for notification in conn.notifications():
                log_data = json.loads(notification.payload)
                await websocket.send_json(log_data)
```

### Alert Engine

```
┌─────────────────────────────────────────────────────────────────┐
│ ALERT EVALUATOR (APScheduler - runs every 5 minutes)            │
│ • Load enabled alert rules from enterprise.alert_rules          │
│ • For each rule:                                                │
│   - Evaluate condition (SQL query or metric threshold)          │
│   - Check if threshold breached                                 │
│   - Check cooldown period (don't re-alert)                      │
│   - If triggered: Create alert instance                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ ALERT DISPATCHER                                                │
│ • For each triggered alert:                                     │
│   - Send to configured channels (email, Slack, webhook)         │
│   - Record notification attempt in alert_instances              │
│   - Retry on failure (exponential backoff)                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │  EMAIL   │  │  SLACK   │  │ WEBHOOK  │
   └──────────┘  └──────────┘  └──────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND ALERT VIEWER (/admin/alerts)                           │
│ • Real-time WebSocket updates for new alerts                    │
│ • Alert list with severity badges                               │
│ • Acknowledge button (updates alert_instances.status)           │
│ • Alert rule configuration UI                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Built-in Alert Rules (Examples):**

1. **High Error Rate:**
```json
{
    "name": "high_error_rate",
    "severity": "critical",
    "condition_type": "sql_query",
    "condition_config": {
        "query": "SELECT COUNT(*) as error_count FROM enterprise.request_metrics WHERE timestamp > NOW() - INTERVAL '15 minutes' AND status_code >= 500",
        "threshold": 10,
        "operator": ">"
    },
    "check_interval_minutes": 5,
    "evaluation_window_minutes": 15
}
```

2. **High P99 Latency:**
```json
{
    "name": "high_p99_latency",
    "severity": "warning",
    "condition_type": "metric_threshold",
    "condition_config": {
        "metric": "p99_response_time_ms",
        "threshold": 5000,
        "operator": ">"
    },
    "check_interval_minutes": 5
}
```

3. **LLM Cost Spike:**
```json
{
    "name": "llm_cost_spike",
    "severity": "warning",
    "condition_type": "sql_query",
    "condition_config": {
        "query": "SELECT SUM(cost_usd) as hourly_cost FROM enterprise.llm_call_metrics WHERE timestamp > NOW() - INTERVAL '1 hour'",
        "threshold": 50.0,
        "operator": ">"
    },
    "check_interval_minutes": 15
}
```

4. **Cache Unavailable:**
```json
{
    "name": "cache_unavailable",
    "severity": "critical",
    "condition_type": "metric_threshold",
    "condition_config": {
        "metric": "cache_available",
        "threshold": 0,
        "operator": "=="
    },
    "check_interval_minutes": 1
}
```

**Alert Evaluator Implementation:**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=5)
async def evaluate_alerts():
    async with db_pool.acquire() as conn:
        rules = await conn.fetch(
            "SELECT * FROM enterprise.alert_rules WHERE enabled = TRUE"
        )

        for rule in rules:
            # Check cooldown
            last_alert = await conn.fetchrow(
                """
                SELECT triggered_at FROM enterprise.alert_instances
                WHERE rule_id = $1 AND status = 'active'
                ORDER BY triggered_at DESC LIMIT 1
                """,
                rule['id']
            )

            if last_alert and (datetime.now() - last_alert['triggered_at']).total_seconds() < rule['cooldown_minutes'] * 60:
                continue  # Still in cooldown

            # Evaluate condition
            condition_met = await evaluate_condition(conn, rule)

            if condition_met:
                # Trigger alert
                alert_id = await conn.fetchval(
                    """
                    INSERT INTO enterprise.alert_instances
                    (rule_id, severity, message, details)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                    """,
                    rule['id'], rule['severity'], rule['name'], json.dumps({})
                )

                # Dispatch notifications
                await dispatch_alert(alert_id, rule)

async def evaluate_condition(conn, rule):
    if rule['condition_type'] == 'sql_query':
        config = rule['condition_config']
        result = await conn.fetchval(config['query'])

        if config['operator'] == '>':
            return result > config['threshold']
        elif config['operator'] == '<':
            return result < config['threshold']
        elif config['operator'] == '==':
            return result == config['threshold']

    elif rule['condition_type'] == 'metric_threshold':
        config = rule['condition_config']
        metrics = metrics_collector.get_snapshot()
        value = metrics.get(config['metric'], 0)

        if config['operator'] == '>':
            return value > config['threshold']
        # ... etc

    return False

async def dispatch_alert(alert_id, rule):
    channels = rule['notification_channels']

    if 'webhook' in channels:
        await send_webhook_alert(alert_id, rule)
    if 'email' in channels:
        await send_email_alert(alert_id, rule)
    if 'slack' in channels:
        await send_slack_alert(alert_id, rule)
```

---

## 10. Implementation Priority

### Phase 1: Distributed Tracing Foundation (Week 1)
**Impact:** High | **Effort:** Medium

1. **Create trace context infrastructure:**
   - Add `contextvars.ContextVar("trace_context")`
   - Implement `TraceContext` dataclass
   - Implement `create_span()` context manager

2. **Inject trace_id at entry points:**
   - HTTP middleware: Generate trace_id, store in context, add to response headers
   - WebSocket handler: Generate trace_id per message, store in context

3. **Create database tables:**
   - Run `migrations/008_tracing_tables.sql` (to be created)
   - Tables: `distributed_traces`, `trace_spans`

4. **Instrument critical paths:**
   - EnterpriseTwin.think_streaming → span "twin_think"
   - EnterpriseRAG.retrieve → span "rag_retrieve" with sub-spans
   - ModelAdapter.generate_streaming → span "llm_generate"

5. **Frontend trace viewer (basic):**
   - Add `/admin/traces` route
   - Simple table view with trace_id, duration, status
   - Click to expand and see spans

**Success Metrics:**
- Every request has a trace_id
- Traces are stored in DB
- Can view traces in frontend
- Can correlate logs with trace_id

---

### Phase 2: Structured Logging (Week 2)
**Impact:** High | **Effort:** Low

1. **Create StructuredLogHandler:**
   - Custom logging handler that writes to DB
   - Extracts trace_id from context
   - Enriches with user_email, department, endpoint

2. **Create database table:**
   - Run `migrations/009_structured_logs.sql`
   - Table: `structured_logs`

3. **Configure logging:**
   - Add StructuredLogHandler to root logger
   - Keep console handler for local dev
   - Set appropriate log levels per module

4. **Frontend log viewer:**
   - Add `/admin/logs` route
   - Real-time log stream via WebSocket (LISTEN/NOTIFY)
   - Filters: level, logger, trace_id, user, search

**Success Metrics:**
- All logs stored in DB
- Can filter by trace_id
- Can search logs
- Real-time log streaming works

---

### Phase 3: Alert Engine (Week 3)
**Impact:** Medium | **Effort:** Medium

1. **Create database tables:**
   - Run `migrations/010_alert_tables.sql`
   - Tables: `alert_rules`, `alert_instances`

2. **Implement alert evaluator:**
   - APScheduler job that runs every 5 minutes
   - Load enabled rules
   - Evaluate conditions (SQL + metric thresholds)
   - Create alert instances

3. **Implement alert dispatcher:**
   - Webhook sender (Slack/generic)
   - Email sender (SMTP)
   - Retry logic with exponential backoff

4. **Pre-configure critical alerts:**
   - High error rate (>10 errors/15min)
   - High p99 latency (>5s)
   - LLM cost spike (>$50/hour)
   - Cache unavailable

5. **Frontend alert viewer:**
   - Add `/admin/alerts` route
   - Active alerts list with severity badges
   - Acknowledge button
   - Alert rule configuration form

**Success Metrics:**
- Alerts trigger correctly
- Notifications sent to Slack/email
- No false positives
- Can acknowledge alerts
- Can create custom alert rules

---

### Phase 4: Observability Optimization (Week 4)
**Impact:** Medium | **Effort:** Low

1. **Optimize database writes:**
   - Batch writes for logs (don't write every log individually)
   - Use COPY for bulk inserts
   - Add retention policies (auto-delete old data)

2. **Add more metrics:**
   - Database pool metrics (active connections, queue depth)
   - Redis metrics (memory usage, eviction rate)
   - External API metrics (Azure AD latency, X.AI latency)

3. **Enhance trace waterfall view:**
   - Gantt-style visualization
   - Color-code by operation type
   - Show parent-child relationships
   - Export trace as JSON

4. **Add dashboards:**
   - Observability overview dashboard
   - Show key metrics: error rate, p99 latency, cost, cache hit rate
   - Real-time charts with auto-refresh

**Success Metrics:**
- Database write performance acceptable
- All external services monitored
- Trace waterfall view is intuitive
- Dashboards provide actionable insights

---

### Phase 5: Advanced Features (Future)
**Impact:** Low | **Effort:** High

1. **Distributed tracing across services:**
   - If system becomes multi-service (microservices)
   - Propagate trace_id in HTTP headers (W3C Trace Context)
   - Implement OpenTelemetry SDK

2. **Log sampling:**
   - Sample DEBUG logs (only keep 10%)
   - Always keep ERROR logs
   - Configurable sampling rate per logger

3. **Trace sampling:**
   - Sample traces (only keep 10% for low-traffic endpoints)
   - Always keep error traces
   - Configurable sampling rate

4. **Cost attribution:**
   - Track LLM cost per user, department, session
   - Budget alerts (department exceeds $X/month)
   - Cost optimization recommendations

5. **Anomaly detection:**
   - ML-based anomaly detection on metrics
   - Auto-generate alerts for unusual patterns
   - Forecasting (predict when metrics will breach thresholds)

---

## 11. Key Findings Summary

### ✅ Strengths

1. **Metrics collector already in place** - `metrics_collector` tracks HTTP, WS, RAG, LLM metrics
2. **Timing instrumentation solid** - RAG and LLM pipelines have comprehensive timing
3. **Structured log prefixes** - Consistent use of `[PREFIX]` for categorization
4. **Database tables ready** - `007_observability_tables.sql` provides 5 observability tables
5. **Frontend chart infrastructure** - Chart components and themes already exist
6. **Context carriers exist** - session_id, user_email, department flow through requests

### ⚠️ Gaps

1. **No trace_id propagation** - EnterpriseTwin doesn't use trace_id (CogTwin does)
2. **No structured JSON logging** - Logs are string-based, not easily queryable
3. **No log aggregation** - Logs printed to console, not stored in DB
4. **No alert system** - No rules, no notifications, no alerting infrastructure
5. **No real-time observability UI** - Frontend has analytics, but no traces/logs/alerts

### 🎯 Quick Wins

1. **Add trace_id to EnterpriseTwin** - Copy pattern from CogTwin (1 day)
2. **Write observability data to DB** - Use existing tables (1 day)
3. **Create basic trace viewer** - Simple table in frontend (1 day)
4. **Add webhook alerts** - 3-5 critical alerts (2 days)
5. **Enhance log statements** - Add trace_id to all logs (1 day)

---

## 12. Next Steps

### Immediate Actions

1. **Review this report** - Validate findings with team
2. **Prioritize phases** - Confirm Phase 1-3 priority order
3. **Set up .env variables** - Add SLACK_WEBHOOK_URL, SMTP_*, ALERT_* settings
4. **Run migrations** - Execute `007_observability_tables.sql`
5. **Start Phase 1** - Begin distributed tracing implementation

### Questions for Team

1. **Alert channels:** Prefer Slack, email, or both for alerts?
2. **Log retention:** Keep logs for 30 days, 90 days, or longer?
3. **Trace sampling:** Sample all traces initially, or only sample errors?
4. **Cost tracking:** Need per-user LLM cost tracking for billing?
5. **External tools:** Consider Datadog/New Relic/Grafana integration, or build custom?

---

**End of Report**
