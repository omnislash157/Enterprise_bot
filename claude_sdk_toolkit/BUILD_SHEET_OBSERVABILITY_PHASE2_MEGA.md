# Feature Build Sheet: Observability Suite - Phase 2 MEGA BUILD

## Feature: OBSERVABILITY_PHASE_2_FULL_STACK
**Priority:** P1  
**Estimated Complexity:** High (3x Phase 1)  
**Timeline:** Parallel execution recommended  
**Dependencies:** Phase 1 complete (metrics_collector, /admin/system)

---

## ⚡ PARALLEL EXECUTION DIRECTIVE

**THIS IS A LARGE BUILD. USE PARALLEL SUB-AGENTS.**

Split into 4 parallel workstreams:
1. **Agent A: Backend Tracing** - contextvars, spans, trace collector
2. **Agent B: Backend Logging** - JSON handler, DB writer, log service
3. **Agent C: Backend Alerts** - rule engine, dispatcher, notifications
4. **Agent D: Frontend** - trace viewer, log viewer, alert dashboard

Coordinate on shared files:
- `core/main.py` - All agents touch this (coordinate edits)
- `migrations/` - Run in order (008, 009, 010)

---

## 1. OVERVIEW

### What We're Building
Complete production observability stack replacing Jaeger + Loki + Alertmanager:

| Component | Replaces | Deliverable |
|-----------|----------|-------------|
| Distributed Tracing | Jaeger/Zipkin | Trace waterfall, span breakdown |
| Structured Logging | Loki/Splunk | Searchable logs, real-time stream |
| Alert Engine | Alertmanager/PagerDuty | Rules, thresholds, Slack/email |

### User Stories
> As an admin, I want to see the full request lifecycle so I can debug slow queries.

> As an admin, I want searchable logs with trace correlation so I can investigate issues.

> As an admin, I want alerts when things break so I know before users complain.

### Acceptance Criteria
- [ ] Every request gets a trace_id that flows through RAG → LLM → Response
- [ ] Trace waterfall shows timing breakdown for each span
- [ ] All logs stored in DB with trace_id correlation
- [ ] Log viewer with real-time streaming and filters
- [ ] Alert rules evaluate every 60 seconds
- [ ] Alerts fire to Slack webhook and/or email
- [ ] All 3 new admin pages functional (/traces, /logs, /alerts)

---

## 2. DATABASE MIGRATIONS

### Migration 008: `migrations/008_tracing_tables.sql`

```sql
-- =============================================================================
-- DISTRIBUTED TRACING TABLES
-- =============================================================================

-- Traces: One per request
CREATE TABLE IF NOT EXISTS enterprise.traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(32) NOT NULL UNIQUE,
    
    -- Request context
    entry_point VARCHAR(20) NOT NULL,  -- 'http', 'websocket'
    endpoint VARCHAR(255),
    method VARCHAR(10),
    session_id VARCHAR(64),
    user_email VARCHAR(255),
    department VARCHAR(50),
    
    -- Timing
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    duration_ms FLOAT,
    
    -- Status
    status VARCHAR(20) DEFAULT 'in_progress',  -- 'in_progress', 'completed', 'error'
    error_message TEXT,
    
    -- Metadata
    tags JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_traces_trace_id ON enterprise.traces(trace_id);
CREATE INDEX idx_traces_start_time ON enterprise.traces(start_time DESC);
CREATE INDEX idx_traces_user ON enterprise.traces(user_email);
CREATE INDEX idx_traces_status ON enterprise.traces(status);
CREATE INDEX idx_traces_session ON enterprise.traces(session_id);

-- Spans: Multiple per trace
CREATE TABLE IF NOT EXISTS enterprise.trace_spans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(32) NOT NULL,
    span_id VARCHAR(16) NOT NULL,
    parent_span_id VARCHAR(16),
    
    -- Operation
    operation_name VARCHAR(100) NOT NULL,
    service_name VARCHAR(50) DEFAULT 'enterprise_bot',
    
    -- Timing
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    duration_ms FLOAT,
    
    -- Status
    status VARCHAR(20) DEFAULT 'in_progress',
    error_message TEXT,
    
    -- Context
    tags JSONB DEFAULT '{}',
    logs JSONB DEFAULT '[]',  -- [{timestamp, message}, ...]
    
    CONSTRAINT fk_trace FOREIGN KEY (trace_id) REFERENCES enterprise.traces(trace_id) ON DELETE CASCADE
);

CREATE INDEX idx_spans_trace_id ON enterprise.trace_spans(trace_id);
CREATE INDEX idx_spans_operation ON enterprise.trace_spans(operation_name);
CREATE INDEX idx_spans_start_time ON enterprise.trace_spans(start_time DESC);
CREATE INDEX idx_spans_parent ON enterprise.trace_spans(parent_span_id);
```

### Migration 009: `migrations/009_structured_logs.sql`

```sql
-- =============================================================================
-- STRUCTURED LOGGING TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS enterprise.structured_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Log metadata
    level VARCHAR(10) NOT NULL,  -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    logger_name VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    
    -- Trace correlation
    trace_id VARCHAR(32),
    span_id VARCHAR(16),
    
    -- Request context
    user_email VARCHAR(255),
    department VARCHAR(50),
    session_id VARCHAR(64),
    endpoint VARCHAR(255),
    
    -- Extra data
    extra JSONB DEFAULT '{}',
    
    -- Exception info
    exception_type VARCHAR(255),
    exception_message TEXT,
    exception_traceback TEXT
);

CREATE INDEX idx_logs_timestamp ON enterprise.structured_logs(timestamp DESC);
CREATE INDEX idx_logs_level ON enterprise.structured_logs(level);
CREATE INDEX idx_logs_trace_id ON enterprise.structured_logs(trace_id);
CREATE INDEX idx_logs_logger ON enterprise.structured_logs(logger_name);
CREATE INDEX idx_logs_user ON enterprise.structured_logs(user_email);

-- Full-text search on message
CREATE INDEX idx_logs_message_search ON enterprise.structured_logs USING gin(to_tsvector('english', message));

-- Notify trigger for real-time streaming
CREATE OR REPLACE FUNCTION notify_new_log() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('new_log', json_build_object(
        'id', NEW.id,
        'timestamp', NEW.timestamp,
        'level', NEW.level,
        'logger_name', NEW.logger_name,
        'message', NEW.message,
        'trace_id', NEW.trace_id
    )::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_inserted
    AFTER INSERT ON enterprise.structured_logs
    FOR EACH ROW EXECUTE FUNCTION notify_new_log();
```

### Migration 010: `migrations/010_alert_tables.sql`

```sql
-- =============================================================================
-- ALERTING SYSTEM TABLES
-- =============================================================================

-- Alert Rules: What conditions trigger alerts
CREATE TABLE IF NOT EXISTS enterprise.alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Rule definition
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Metric to watch
    metric_type VARCHAR(50) NOT NULL,  -- 'error_rate', 'latency_p95', 'llm_cost', 'cache_miss', 'custom_sql'
    
    -- Condition
    condition VARCHAR(20) NOT NULL,  -- 'gt', 'lt', 'gte', 'lte', 'eq', 'neq'
    threshold FLOAT NOT NULL,
    
    -- Evaluation
    window_minutes INTEGER DEFAULT 5,
    evaluation_interval_seconds INTEGER DEFAULT 60,
    
    -- For custom SQL alerts
    custom_sql TEXT,
    
    -- Notification
    severity VARCHAR(20) DEFAULT 'warning',  -- 'info', 'warning', 'critical'
    notification_channels JSONB DEFAULT '["slack"]',  -- ['slack', 'email']
    
    -- Cooldown (don't re-alert for this many minutes after firing)
    cooldown_minutes INTEGER DEFAULT 15,
    
    -- Status
    enabled BOOLEAN DEFAULT TRUE,
    last_evaluated_at TIMESTAMPTZ,
    last_triggered_at TIMESTAMPTZ,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(255),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alert_rules_enabled ON enterprise.alert_rules(enabled);
CREATE INDEX idx_alert_rules_metric ON enterprise.alert_rules(metric_type);

-- Alert Instances: Fired alerts
CREATE TABLE IF NOT EXISTS enterprise.alert_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id UUID NOT NULL REFERENCES enterprise.alert_rules(id) ON DELETE CASCADE,
    
    -- Alert details
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    
    -- Status
    status VARCHAR(20) DEFAULT 'firing',  -- 'firing', 'acknowledged', 'resolved'
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMPTZ,
    
    -- Context
    metric_value FLOAT,
    threshold_value FLOAT,
    message TEXT,
    context JSONB DEFAULT '{}',
    
    -- Notifications
    notifications_sent JSONB DEFAULT '[]'  -- [{channel, sent_at, success}, ...]
);

CREATE INDEX idx_alert_instances_rule ON enterprise.alert_instances(rule_id);
CREATE INDEX idx_alert_instances_status ON enterprise.alert_instances(status);
CREATE INDEX idx_alert_instances_triggered ON enterprise.alert_instances(triggered_at DESC);

-- Insert default alert rules
INSERT INTO enterprise.alert_rules (name, description, metric_type, condition, threshold, window_minutes, severity, notification_channels) VALUES
    ('High Error Rate', 'More than 10 errors in 5 minutes', 'error_count', 'gt', 10, 5, 'critical', '["slack"]'),
    ('Slow RAG Queries', 'RAG P95 latency above 3 seconds', 'rag_latency_p95', 'gt', 3000, 5, 'warning', '["slack"]'),
    ('LLM Cost Spike', 'LLM cost exceeds $10 in 1 hour', 'llm_cost_hourly', 'gt', 10, 60, 'warning', '["slack", "email"]'),
    ('Low Cache Hit Rate', 'Cache hit rate below 20%', 'cache_hit_rate', 'lt', 20, 15, 'info', '["slack"]'),
    ('High Memory Usage', 'Memory usage above 85%', 'memory_percent', 'gt', 85, 5, 'warning', '["slack"]')
ON CONFLICT DO NOTHING;
```

---

## 3. BACKEND: DISTRIBUTED TRACING

### 3.1 New File: `core/tracing.py`

```python
"""
Distributed Tracing - Request lifecycle tracking

Provides trace_id propagation via contextvars and span collection.

Usage:
    from core.tracing import trace_context, create_span, get_trace_id
    
    # Start a trace (at request entry)
    with trace_context.start_trace(entry_point='websocket', user_email=email):
        # Create spans for operations
        with create_span('rag_retrieve') as span:
            span.set_tag('chunks', 5)
            # ... do work ...
        
        # Nested spans
        with create_span('llm_generate', parent=span):
            # ... do work ...
    
    # Get current trace_id anywhere
    trace_id = get_trace_id()
"""

import uuid
import time
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from contextlib import contextmanager, asynccontextmanager
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# =============================================================================
# CONTEXT VARIABLES
# =============================================================================

# Current trace context (async-safe)
_trace_context: ContextVar[Optional['TraceContext']] = ContextVar('trace_context', default=None)
_current_span: ContextVar[Optional['Span']] = ContextVar('current_span', default=None)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Span:
    """A single operation within a trace."""
    span_id: str
    trace_id: str
    operation_name: str
    parent_span_id: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: str = 'in_progress'
    error_message: Optional[str] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    
    def set_tag(self, key: str, value: Any):
        """Add a tag to the span."""
        self.tags[key] = value
    
    def log(self, message: str, **kwargs):
        """Add a log entry to the span."""
        self.logs.append({
            'timestamp': datetime.utcnow().isoformat(),
            'message': message,
            **kwargs
        })
    
    def set_error(self, error: Exception):
        """Mark span as errored."""
        self.status = 'error'
        self.error_message = str(error)
        self.log(f"Error: {error}", level='error')
    
    def finish(self):
        """Complete the span."""
        self.end_time = datetime.utcnow()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        if self.status == 'in_progress':
            self.status = 'completed'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DB storage."""
        return {
            'span_id': self.span_id,
            'trace_id': self.trace_id,
            'parent_span_id': self.parent_span_id,
            'operation_name': self.operation_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': self.duration_ms,
            'status': self.status,
            'error_message': self.error_message,
            'tags': self.tags,
            'logs': self.logs,
        }


@dataclass
class TraceContext:
    """Context for a single request trace."""
    trace_id: str
    entry_point: str  # 'http' or 'websocket'
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: str = 'in_progress'
    error_message: Optional[str] = None
    
    # Request context
    endpoint: Optional[str] = None
    method: Optional[str] = None
    session_id: Optional[str] = None
    user_email: Optional[str] = None
    department: Optional[str] = None
    
    # Collected spans
    spans: List[Span] = field(default_factory=list)
    tags: Dict[str, Any] = field(default_factory=dict)
    
    def add_span(self, span: Span):
        """Add a span to this trace."""
        self.spans.append(span)
    
    def set_tag(self, key: str, value: Any):
        """Add a tag to the trace."""
        self.tags[key] = value
    
    def set_error(self, error: Exception):
        """Mark trace as errored."""
        self.status = 'error'
        self.error_message = str(error)
    
    def finish(self):
        """Complete the trace."""
        self.end_time = datetime.utcnow()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        if self.status == 'in_progress':
            self.status = 'completed'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DB storage."""
        return {
            'trace_id': self.trace_id,
            'entry_point': self.entry_point,
            'endpoint': self.endpoint,
            'method': self.method,
            'session_id': self.session_id,
            'user_email': self.user_email,
            'department': self.department,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': self.duration_ms,
            'status': self.status,
            'error_message': self.error_message,
            'tags': self.tags,
        }


# =============================================================================
# TRACE COLLECTOR (Singleton)
# =============================================================================

class TraceCollector:
    """
    Collects traces and spans, periodically flushes to database.
    
    Uses a buffer to batch writes for performance.
    """
    
    _instance: Optional['TraceCollector'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self._trace_buffer: List[TraceContext] = []
        self._span_buffer: List[Span] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._db_pool = None
        
        logger.info("[Tracing] TraceCollector initialized")
    
    def set_db_pool(self, pool):
        """Set the database connection pool."""
        self._db_pool = pool
    
    async def start(self):
        """Start the background flush task."""
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())
            logger.info("[Tracing] Background flush task started")
    
    async def stop(self):
        """Stop the background flush task."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        # Final flush
        await self.flush()
    
    async def _flush_loop(self):
        """Periodically flush buffers to database."""
        while True:
            await asyncio.sleep(5)  # Flush every 5 seconds
            await self.flush()
    
    async def add_trace(self, trace: TraceContext):
        """Add a completed trace to the buffer."""
        async with self._buffer_lock:
            self._trace_buffer.append(trace)
    
    async def add_span(self, span: Span):
        """Add a completed span to the buffer."""
        async with self._buffer_lock:
            self._span_buffer.append(span)
    
    async def flush(self):
        """Flush buffers to database."""
        if not self._db_pool:
            logger.warning("[Tracing] No DB pool configured, skipping flush")
            return
        
        async with self._buffer_lock:
            traces = self._trace_buffer[:]
            spans = self._span_buffer[:]
            self._trace_buffer.clear()
            self._span_buffer.clear()
        
        if not traces and not spans:
            return
        
        try:
            async with self._db_pool.acquire() as conn:
                # Insert traces
                if traces:
                    await conn.executemany("""
                        INSERT INTO enterprise.traces 
                        (trace_id, entry_point, endpoint, method, session_id, user_email, department,
                         start_time, end_time, duration_ms, status, error_message, tags)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        ON CONFLICT (trace_id) DO UPDATE SET
                            end_time = EXCLUDED.end_time,
                            duration_ms = EXCLUDED.duration_ms,
                            status = EXCLUDED.status,
                            error_message = EXCLUDED.error_message
                    """, [
                        (t.trace_id, t.entry_point, t.endpoint, t.method, t.session_id,
                         t.user_email, t.department, t.start_time, t.end_time,
                         t.duration_ms, t.status, t.error_message, str(t.tags))
                        for t in traces
                    ])
                
                # Insert spans
                if spans:
                    await conn.executemany("""
                        INSERT INTO enterprise.trace_spans
                        (trace_id, span_id, parent_span_id, operation_name, start_time, end_time,
                         duration_ms, status, error_message, tags, logs)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """, [
                        (s.trace_id, s.span_id, s.parent_span_id, s.operation_name,
                         s.start_time, s.end_time, s.duration_ms, s.status,
                         s.error_message, str(s.tags), str(s.logs))
                        for s in spans
                    ])
            
            logger.debug(f"[Tracing] Flushed {len(traces)} traces, {len(spans)} spans")
        except Exception as e:
            logger.error(f"[Tracing] Flush error: {e}")
            # Re-add to buffer for retry
            async with self._buffer_lock:
                self._trace_buffer.extend(traces)
                self._span_buffer.extend(spans)


# Global collector
trace_collector = TraceCollector()


# =============================================================================
# PUBLIC API
# =============================================================================

def generate_trace_id() -> str:
    """Generate a new trace ID (32 hex chars)."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a new span ID (16 hex chars)."""
    return uuid.uuid4().hex[:16]


def get_trace_id() -> Optional[str]:
    """Get current trace ID from context."""
    ctx = _trace_context.get()
    return ctx.trace_id if ctx else None


def get_current_trace() -> Optional[TraceContext]:
    """Get current trace context."""
    return _trace_context.get()


def get_current_span() -> Optional[Span]:
    """Get current span from context."""
    return _current_span.get()


@asynccontextmanager
async def start_trace(
    entry_point: str,
    endpoint: str = None,
    method: str = None,
    session_id: str = None,
    user_email: str = None,
    department: str = None,
    trace_id: str = None,
):
    """
    Start a new trace context.
    
    Usage:
        async with start_trace(entry_point='websocket', user_email='user@example.com'):
            # ... handle request ...
    """
    trace_id = trace_id or generate_trace_id()
    
    ctx = TraceContext(
        trace_id=trace_id,
        entry_point=entry_point,
        endpoint=endpoint,
        method=method,
        session_id=session_id,
        user_email=user_email,
        department=department,
    )
    
    token = _trace_context.set(ctx)
    
    try:
        yield ctx
    except Exception as e:
        ctx.set_error(e)
        raise
    finally:
        ctx.finish()
        _trace_context.reset(token)
        await trace_collector.add_trace(ctx)


@asynccontextmanager
async def create_span(operation_name: str, tags: Dict[str, Any] = None):
    """
    Create a span within the current trace.
    
    Usage:
        async with create_span('rag_retrieve', tags={'department': 'sales'}):
            # ... do work ...
    """
    ctx = _trace_context.get()
    if not ctx:
        # No trace context, create a dummy span that does nothing
        yield Span(span_id='none', trace_id='none', operation_name=operation_name)
        return
    
    parent = _current_span.get()
    
    span = Span(
        span_id=generate_span_id(),
        trace_id=ctx.trace_id,
        operation_name=operation_name,
        parent_span_id=parent.span_id if parent else None,
        tags=tags or {},
    )
    
    ctx.add_span(span)
    token = _current_span.set(span)
    
    try:
        yield span
    except Exception as e:
        span.set_error(e)
        raise
    finally:
        span.finish()
        _current_span.reset(token)
        await trace_collector.add_span(span)


# Synchronous versions for non-async code
@contextmanager
def create_span_sync(operation_name: str, tags: Dict[str, Any] = None):
    """Synchronous version of create_span (doesn't persist to DB immediately)."""
    ctx = _trace_context.get()
    if not ctx:
        yield Span(span_id='none', trace_id='none', operation_name=operation_name)
        return
    
    parent = _current_span.get()
    
    span = Span(
        span_id=generate_span_id(),
        trace_id=ctx.trace_id,
        operation_name=operation_name,
        parent_span_id=parent.span_id if parent else None,
        tags=tags or {},
    )
    
    ctx.add_span(span)
    token = _current_span.set(span)
    
    try:
        yield span
    except Exception as e:
        span.set_error(e)
        raise
    finally:
        span.finish()
        _current_span.reset(token)
```

### 3.2 New File: `auth/tracing_routes.py`

```python
"""
Tracing API Routes - Trace viewing and querying

Provides endpoints for the trace viewer UI.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

tracing_router = APIRouter()


@tracing_router.get("/traces")
async def list_traces(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    min_duration_ms: Optional[float] = Query(None),
    hours: int = Query(24, ge=1, le=168),
):
    """List recent traces with optional filters."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        query = """
            SELECT trace_id, entry_point, endpoint, method, session_id, user_email,
                   department, start_time, end_time, duration_ms, status, error_message, tags
            FROM enterprise.traces
            WHERE start_time > NOW() - INTERVAL '1 hour' * $1
        """
        params = [hours]
        param_idx = 2
        
        if status:
            query += f" AND status = ${param_idx}"
            params.append(status)
            param_idx += 1
        
        if user_email:
            query += f" AND user_email = ${param_idx}"
            params.append(user_email)
            param_idx += 1
        
        if min_duration_ms:
            query += f" AND duration_ms >= ${param_idx}"
            params.append(min_duration_ms)
            param_idx += 1
        
        query += f" ORDER BY start_time DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            # Get total count
            count_query = """
                SELECT COUNT(*) FROM enterprise.traces
                WHERE start_time > NOW() - INTERVAL '1 hour' * $1
            """
            total = await conn.fetchval(count_query, hours)
        
        return {
            'traces': [dict(r) for r in rows],
            'total': total,
            'limit': limit,
            'offset': offset,
        }
    except Exception as e:
        logger.error(f"[Tracing] List traces error: {e}")
        return {'traces': [], 'total': 0, 'error': str(e)}


@tracing_router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get a single trace with all its spans."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            # Get trace
            trace = await conn.fetchrow("""
                SELECT * FROM enterprise.traces WHERE trace_id = $1
            """, trace_id)
            
            if not trace:
                raise HTTPException(status_code=404, detail="Trace not found")
            
            # Get spans
            spans = await conn.fetch("""
                SELECT * FROM enterprise.trace_spans
                WHERE trace_id = $1
                ORDER BY start_time ASC
            """, trace_id)
        
        return {
            'trace': dict(trace),
            'spans': [dict(s) for s in spans],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tracing] Get trace error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@tracing_router.get("/traces/stats/summary")
async def get_trace_stats(hours: int = Query(24, ge=1, le=168)):
    """Get trace statistics summary."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_traces,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                    COUNT(*) FILTER (WHERE status = 'error') as errors,
                    AVG(duration_ms) as avg_duration_ms,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms) as p50_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_ms,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99_ms
                FROM enterprise.traces
                WHERE start_time > NOW() - INTERVAL '1 hour' * $1
                  AND duration_ms IS NOT NULL
            """, hours)
            
            # Top slow operations
            slow_ops = await conn.fetch("""
                SELECT operation_name, 
                       COUNT(*) as count,
                       AVG(duration_ms) as avg_ms,
                       MAX(duration_ms) as max_ms
                FROM enterprise.trace_spans
                WHERE start_time > NOW() - INTERVAL '1 hour' * $1
                GROUP BY operation_name
                ORDER BY avg_ms DESC
                LIMIT 10
            """, hours)
        
        return {
            'period_hours': hours,
            'total_traces': stats['total_traces'] or 0,
            'completed': stats['completed'] or 0,
            'errors': stats['errors'] or 0,
            'error_rate': round((stats['errors'] or 0) / max(stats['total_traces'] or 1, 1) * 100, 2),
            'avg_duration_ms': round(stats['avg_duration_ms'] or 0, 1),
            'p50_ms': round(stats['p50_ms'] or 0, 1),
            'p95_ms': round(stats['p95_ms'] or 0, 1),
            'p99_ms': round(stats['p99_ms'] or 0, 1),
            'slow_operations': [dict(o) for o in slow_ops],
        }
    except Exception as e:
        logger.error(f"[Tracing] Stats error: {e}")
        return {'error': str(e)}
```

---

## 4. BACKEND: STRUCTURED LOGGING

### 4.1 New File: `core/structured_logging.py`

```python
"""
Structured Logging - JSON logs with trace correlation

Provides a custom logging handler that writes to PostgreSQL
with trace_id correlation and real-time streaming via NOTIFY.

Usage:
    from core.structured_logging import setup_structured_logging
    
    # Call once at startup
    setup_structured_logging(db_pool)
    
    # Then use logging normally - it will be captured
    logger.info("Something happened", extra={'user_id': 123})
"""

import logging
import json
import asyncio
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from queue import Queue
from dataclasses import dataclass

from core.tracing import get_trace_id, get_current_span

logger = logging.getLogger(__name__)


@dataclass
class LogRecord:
    """Structured log record."""
    timestamp: datetime
    level: str
    logger_name: str
    message: str
    trace_id: Optional[str]
    span_id: Optional[str]
    user_email: Optional[str]
    department: Optional[str]
    session_id: Optional[str]
    endpoint: Optional[str]
    extra: Dict[str, Any]
    exception_type: Optional[str]
    exception_message: Optional[str]
    exception_traceback: Optional[str]


class DatabaseLogHandler(logging.Handler):
    """
    Logging handler that buffers records and writes to PostgreSQL.
    
    Uses a background thread to avoid blocking the main event loop.
    """
    
    def __init__(self, buffer_size: int = 100, flush_interval: float = 2.0):
        super().__init__()
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self._buffer: Queue = Queue()
        self._db_pool = None
        self._flush_thread: Optional[threading.Thread] = None
        self._running = False
    
    def set_db_pool(self, pool):
        """Set the database connection pool and start flushing."""
        self._db_pool = pool
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
    
    def stop(self):
        """Stop the flush thread."""
        self._running = False
        if self._flush_thread:
            self._flush_thread.join(timeout=5)
    
    def emit(self, record: logging.LogRecord):
        """Handle a log record."""
        try:
            # Get trace context
            trace_id = get_trace_id()
            span = get_current_span()
            span_id = span.span_id if span else None
            
            # Extract extra fields
            extra = {}
            for key, value in record.__dict__.items():
                if key not in logging.LogRecord.__dict__ and not key.startswith('_'):
                    try:
                        json.dumps(value)  # Check if JSON serializable
                        extra[key] = value
                    except (TypeError, ValueError):
                        extra[key] = str(value)
            
            # Handle exception info
            exc_type = None
            exc_message = None
            exc_traceback = None
            if record.exc_info:
                exc_type = record.exc_info[0].__name__ if record.exc_info[0] else None
                exc_message = str(record.exc_info[1]) if record.exc_info[1] else None
                exc_traceback = self.format(record) if record.exc_info[2] else None
            
            log_record = LogRecord(
                timestamp=datetime.utcnow(),
                level=record.levelname,
                logger_name=record.name,
                message=record.getMessage(),
                trace_id=trace_id,
                span_id=span_id,
                user_email=extra.pop('user_email', None),
                department=extra.pop('department', None),
                session_id=extra.pop('session_id', None),
                endpoint=extra.pop('endpoint', None),
                extra=extra,
                exception_type=exc_type,
                exception_message=exc_message,
                exception_traceback=exc_traceback,
            )
            
            self._buffer.put(log_record)
            
        except Exception:
            self.handleError(record)
    
    def _flush_loop(self):
        """Background thread that flushes logs to database."""
        import asyncio
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self._running:
            try:
                # Collect records from buffer
                records = []
                while not self._buffer.empty() and len(records) < self.buffer_size:
                    try:
                        records.append(self._buffer.get_nowait())
                    except:
                        break
                
                if records and self._db_pool:
                    loop.run_until_complete(self._write_records(records))
                
                # Sleep between flushes
                import time
                time.sleep(self.flush_interval)
                
            except Exception as e:
                print(f"[StructuredLogging] Flush error: {e}")
    
    async def _write_records(self, records: List[LogRecord]):
        """Write log records to database."""
        try:
            async with self._db_pool.acquire() as conn:
                await conn.executemany("""
                    INSERT INTO enterprise.structured_logs
                    (timestamp, level, logger_name, message, trace_id, span_id,
                     user_email, department, session_id, endpoint, extra,
                     exception_type, exception_message, exception_traceback)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """, [
                    (r.timestamp, r.level, r.logger_name, r.message, r.trace_id, r.span_id,
                     r.user_email, r.department, r.session_id, r.endpoint,
                     json.dumps(r.extra), r.exception_type, r.exception_message, r.exception_traceback)
                    for r in records
                ])
        except Exception as e:
            print(f"[StructuredLogging] Write error: {e}")


# Global handler instance
_db_handler: Optional[DatabaseLogHandler] = None


def setup_structured_logging(db_pool, level: int = logging.INFO):
    """
    Set up structured logging with database persistence.
    
    Call this once at application startup after DB pool is created.
    """
    global _db_handler
    
    # Create handler
    _db_handler = DatabaseLogHandler()
    _db_handler.setLevel(level)
    _db_handler.set_db_pool(db_pool)
    
    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(_db_handler)
    
    logger.info("[StructuredLogging] Database logging enabled")


def shutdown_structured_logging():
    """Shutdown structured logging (call on app shutdown)."""
    global _db_handler
    if _db_handler:
        _db_handler.stop()
        _db_handler = None
```

### 4.2 New File: `auth/logging_routes.py`

```python
"""
Logging API Routes - Log viewing and streaming

Provides endpoints for the log viewer UI.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from typing import Optional, List
from datetime import datetime, timedelta
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

logging_router = APIRouter()


@logging_router.get("/logs")
async def list_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    level: Optional[str] = Query(None),
    logger_name: Optional[str] = Query(None),
    trace_id: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
):
    """List logs with filters."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        query = """
            SELECT id, timestamp, level, logger_name, message, trace_id, span_id,
                   user_email, department, session_id, endpoint, extra,
                   exception_type, exception_message
            FROM enterprise.structured_logs
            WHERE timestamp > NOW() - INTERVAL '1 hour' * $1
        """
        params = [hours]
        param_idx = 2
        
        if level:
            query += f" AND level = ${param_idx}"
            params.append(level)
            param_idx += 1
        
        if logger_name:
            query += f" AND logger_name LIKE ${param_idx}"
            params.append(f"%{logger_name}%")
            param_idx += 1
        
        if trace_id:
            query += f" AND trace_id = ${param_idx}"
            params.append(trace_id)
            param_idx += 1
        
        if user_email:
            query += f" AND user_email = ${param_idx}"
            params.append(user_email)
            param_idx += 1
        
        if search:
            query += f" AND to_tsvector('english', message) @@ plainto_tsquery('english', ${param_idx})"
            params.append(search)
            param_idx += 1
        
        query += f" ORDER BY timestamp DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        return {
            'logs': [dict(r) for r in rows],
            'limit': limit,
            'offset': offset,
        }
    except Exception as e:
        logger.error(f"[Logging] List logs error: {e}")
        return {'logs': [], 'error': str(e)}


@logging_router.get("/logs/{log_id}")
async def get_log(log_id: str):
    """Get a single log entry with full details."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            log = await conn.fetchrow("""
                SELECT * FROM enterprise.structured_logs WHERE id = $1
            """, log_id)
        
        if not log:
            raise HTTPException(status_code=404, detail="Log not found")
        
        return dict(log)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Logging] Get log error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@logging_router.get("/logs/stats/levels")
async def get_log_level_stats(hours: int = Query(24, ge=1, le=168)):
    """Get log counts by level."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT level, COUNT(*) as count
                FROM enterprise.structured_logs
                WHERE timestamp > NOW() - INTERVAL '1 hour' * $1
                GROUP BY level
                ORDER BY count DESC
            """, hours)
        
        return {
            'period_hours': hours,
            'levels': {r['level']: r['count'] for r in rows}
        }
    except Exception as e:
        logger.error(f"[Logging] Stats error: {e}")
        return {'error': str(e)}


# WebSocket for real-time log streaming
class LogStreamManager:
    """Manages WebSocket connections for log streaming."""
    
    def __init__(self):
        self.connections: List[WebSocket] = []
        self._listener_task: Optional[asyncio.Task] = None
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
        
        # Start LISTEN if first connection
        if len(self.connections) == 1:
            self._listener_task = asyncio.create_task(self._listen_for_logs())
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
        
        # Stop LISTEN if no connections
        if not self.connections and self._listener_task:
            self._listener_task.cancel()
            self._listener_task = None
    
    async def _listen_for_logs(self):
        """Listen for PostgreSQL NOTIFY events."""
        try:
            from core.database import get_db_pool
            pool = await get_db_pool()
            
            async with pool.acquire() as conn:
                await conn.add_listener('new_log', self._on_log_notification)
                
                # Keep connection alive
                while self.connections:
                    await asyncio.sleep(1)
                
                await conn.remove_listener('new_log', self._on_log_notification)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[LogStream] Listener error: {e}")
    
    def _on_log_notification(self, conn, pid, channel, payload):
        """Handle NOTIFY event."""
        asyncio.create_task(self._broadcast(payload))
    
    async def _broadcast(self, payload: str):
        """Broadcast log to all connected clients."""
        disconnected = []
        for ws in self.connections:
            try:
                await ws.send_json({
                    'type': 'new_log',
                    'data': json.loads(payload)
                })
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.disconnect(ws)


log_stream_manager = LogStreamManager()


@logging_router.websocket("/logs/stream")
async def log_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time log streaming."""
    await log_stream_manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive, handle any client messages
            data = await websocket.receive_text()
            # Could handle filter updates here
    except WebSocketDisconnect:
        log_stream_manager.disconnect(websocket)
```

---

## 5. BACKEND: ALERT ENGINE

### 5.1 New File: `core/alerting.py`

```python
"""
Alert Engine - Threshold monitoring and notifications

Evaluates alert rules against metrics and sends notifications.

Usage:
    from core.alerting import alert_engine
    
    # Start the alert evaluation loop
    await alert_engine.start()
    
    # Stop on shutdown
    await alert_engine.stop()
"""

import asyncio
import logging
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    """Alert rule definition."""
    id: str
    name: str
    description: Optional[str]
    metric_type: str
    condition: str
    threshold: float
    window_minutes: int
    custom_sql: Optional[str]
    severity: str
    notification_channels: List[str]
    cooldown_minutes: int
    enabled: bool
    last_triggered_at: Optional[datetime]


@dataclass
class AlertInstance:
    """A fired alert instance."""
    rule_id: str
    rule_name: str
    severity: str
    metric_value: float
    threshold_value: float
    message: str


class AlertEngine:
    """
    Evaluates alert rules and sends notifications.
    
    Runs as a background task, checking rules every 60 seconds.
    """
    
    _instance: Optional['AlertEngine'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self._db_pool = None
        self._eval_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Notification config from environment
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        self.smtp_host = os.getenv('SMTP_HOST')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.alert_email_from = os.getenv('ALERT_EMAIL_FROM', 'alerts@cogtwin.local')
        self.alert_email_to = os.getenv('ALERT_EMAIL_TO', '').split(',')
        
        logger.info("[AlertEngine] Initialized")
    
    def set_db_pool(self, pool):
        """Set the database connection pool."""
        self._db_pool = pool
    
    async def start(self):
        """Start the alert evaluation loop."""
        if self._eval_task is not None:
            return
        
        self._running = True
        self._eval_task = asyncio.create_task(self._evaluation_loop())
        logger.info("[AlertEngine] Started evaluation loop")
    
    async def stop(self):
        """Stop the alert evaluation loop."""
        self._running = False
        if self._eval_task:
            self._eval_task.cancel()
            try:
                await self._eval_task
            except asyncio.CancelledError:
                pass
            self._eval_task = None
        logger.info("[AlertEngine] Stopped")
    
    async def _evaluation_loop(self):
        """Main evaluation loop."""
        while self._running:
            try:
                await self._evaluate_all_rules()
            except Exception as e:
                logger.error(f"[AlertEngine] Evaluation error: {e}")
            
            await asyncio.sleep(60)  # Evaluate every 60 seconds
    
    async def _evaluate_all_rules(self):
        """Evaluate all enabled alert rules."""
        if not self._db_pool:
            return
        
        async with self._db_pool.acquire() as conn:
            # Load enabled rules
            rows = await conn.fetch("""
                SELECT id, name, description, metric_type, condition, threshold,
                       window_minutes, custom_sql, severity, notification_channels,
                       cooldown_minutes, enabled, last_triggered_at
                FROM enterprise.alert_rules
                WHERE enabled = TRUE
            """)
            
            rules = [AlertRule(
                id=str(r['id']),
                name=r['name'],
                description=r['description'],
                metric_type=r['metric_type'],
                condition=r['condition'],
                threshold=r['threshold'],
                window_minutes=r['window_minutes'],
                custom_sql=r['custom_sql'],
                severity=r['severity'],
                notification_channels=r['notification_channels'] if isinstance(r['notification_channels'], list) else [],
                cooldown_minutes=r['cooldown_minutes'],
                enabled=r['enabled'],
                last_triggered_at=r['last_triggered_at'],
            ) for r in rows]
        
        for rule in rules:
            await self._evaluate_rule(rule)
    
    async def _evaluate_rule(self, rule: AlertRule):
        """Evaluate a single alert rule."""
        # Check cooldown
        if rule.last_triggered_at:
            cooldown_until = rule.last_triggered_at + timedelta(minutes=rule.cooldown_minutes)
            if datetime.utcnow() < cooldown_until:
                return  # Still in cooldown
        
        # Get metric value
        metric_value = await self._get_metric_value(rule)
        if metric_value is None:
            return
        
        # Check condition
        triggered = self._check_condition(metric_value, rule.condition, rule.threshold)
        
        if triggered:
            await self._fire_alert(rule, metric_value)
    
    async def _get_metric_value(self, rule: AlertRule) -> Optional[float]:
        """Get the current metric value for a rule."""
        if not self._db_pool:
            return None
        
        try:
            async with self._db_pool.acquire() as conn:
                if rule.metric_type == 'error_count':
                    result = await conn.fetchval("""
                        SELECT COUNT(*) FROM enterprise.structured_logs
                        WHERE level = 'ERROR'
                          AND timestamp > NOW() - INTERVAL '1 minute' * $1
                    """, rule.window_minutes)
                
                elif rule.metric_type == 'rag_latency_p95':
                    result = await conn.fetchval("""
                        SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_ms)
                        FROM enterprise.rag_metrics
                        WHERE timestamp > NOW() - INTERVAL '1 minute' * $1
                    """, rule.window_minutes)
                
                elif rule.metric_type == 'llm_cost_hourly':
                    result = await conn.fetchval("""
                        SELECT COALESCE(SUM(cost_usd), 0)
                        FROM enterprise.llm_call_metrics
                        WHERE timestamp > NOW() - INTERVAL '1 minute' * $1
                    """, rule.window_minutes)
                
                elif rule.metric_type == 'cache_hit_rate':
                    from core.metrics_collector import metrics_collector
                    total = metrics_collector.cache_hits + metrics_collector.cache_misses
                    result = (metrics_collector.cache_hits / total * 100) if total > 0 else 100
                
                elif rule.metric_type == 'memory_percent':
                    from core.metrics_collector import metrics_collector
                    system = metrics_collector.get_system_metrics()
                    result = system.get('memory_percent', 0)
                
                elif rule.metric_type == 'custom_sql' and rule.custom_sql:
                    result = await conn.fetchval(rule.custom_sql)
                
                else:
                    logger.warning(f"[AlertEngine] Unknown metric type: {rule.metric_type}")
                    return None
                
                return float(result) if result is not None else None
                
        except Exception as e:
            logger.error(f"[AlertEngine] Metric fetch error for {rule.name}: {e}")
            return None
    
    def _check_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Check if the condition is met."""
        if condition == 'gt':
            return value > threshold
        elif condition == 'gte':
            return value >= threshold
        elif condition == 'lt':
            return value < threshold
        elif condition == 'lte':
            return value <= threshold
        elif condition == 'eq':
            return value == threshold
        elif condition == 'neq':
            return value != threshold
        return False
    
    async def _fire_alert(self, rule: AlertRule, metric_value: float):
        """Fire an alert and send notifications."""
        logger.warning(f"[AlertEngine] ALERT FIRED: {rule.name} (value={metric_value}, threshold={rule.threshold})")
        
        alert = AlertInstance(
            rule_id=rule.id,
            rule_name=rule.name,
            severity=rule.severity,
            metric_value=metric_value,
            threshold_value=rule.threshold,
            message=f"{rule.name}: {rule.metric_type} is {metric_value} (threshold: {rule.threshold})"
        )
        
        # Record alert instance
        await self._record_alert_instance(alert)
        
        # Update last_triggered_at
        await self._update_rule_triggered(rule.id)
        
        # Send notifications
        notifications_sent = []
        
        if 'slack' in rule.notification_channels:
            success = await self._send_slack_notification(alert)
            notifications_sent.append({'channel': 'slack', 'success': success})
        
        if 'email' in rule.notification_channels:
            success = await self._send_email_notification(alert)
            notifications_sent.append({'channel': 'email', 'success': success})
        
        # Update notification status
        await self._update_alert_notifications(alert.rule_id, notifications_sent)
    
    async def _record_alert_instance(self, alert: AlertInstance):
        """Record a fired alert in the database."""
        if not self._db_pool:
            return
        
        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO enterprise.alert_instances
                    (rule_id, metric_value, threshold_value, message, context)
                    VALUES ($1, $2, $3, $4, $5)
                """, alert.rule_id, alert.metric_value, alert.threshold_value,
                     alert.message, '{}')
        except Exception as e:
            logger.error(f"[AlertEngine] Record alert error: {e}")
    
    async def _update_rule_triggered(self, rule_id: str):
        """Update last_triggered_at for a rule."""
        if not self._db_pool:
            return
        
        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE enterprise.alert_rules
                    SET last_triggered_at = NOW(), last_evaluated_at = NOW()
                    WHERE id = $1
                """, rule_id)
        except Exception as e:
            logger.error(f"[AlertEngine] Update rule error: {e}")
    
    async def _update_alert_notifications(self, rule_id: str, notifications: List[Dict]):
        """Update notifications_sent for the most recent alert."""
        if not self._db_pool:
            return
        
        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE enterprise.alert_instances
                    SET notifications_sent = $2
                    WHERE rule_id = $1
                    ORDER BY triggered_at DESC
                    LIMIT 1
                """, rule_id, str(notifications))
        except Exception as e:
            logger.error(f"[AlertEngine] Update notifications error: {e}")
    
    async def _send_slack_notification(self, alert: AlertInstance) -> bool:
        """Send alert to Slack webhook."""
        if not self.slack_webhook_url:
            logger.warning("[AlertEngine] Slack webhook URL not configured")
            return False
        
        try:
            # Severity emoji
            emoji = {
                'info': 'ℹ️',
                'warning': '⚠️',
                'critical': '🚨'
            }.get(alert.severity, '⚠️')
            
            payload = {
                'text': f"{emoji} *{alert.rule_name}*",
                'attachments': [{
                    'color': {
                        'info': '#36a64f',
                        'warning': '#ffcc00',
                        'critical': '#ff0000'
                    }.get(alert.severity, '#ffcc00'),
                    'fields': [
                        {'title': 'Severity', 'value': alert.severity.upper(), 'short': True},
                        {'title': 'Value', 'value': str(round(alert.metric_value, 2)), 'short': True},
                        {'title': 'Threshold', 'value': str(alert.threshold_value), 'short': True},
                    ],
                    'text': alert.message,
                    'footer': 'CogTwin Alert Engine',
                    'ts': int(datetime.utcnow().timestamp())
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.slack_webhook_url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info(f"[AlertEngine] Slack notification sent for {alert.rule_name}")
                        return True
                    else:
                        logger.error(f"[AlertEngine] Slack webhook failed: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"[AlertEngine] Slack notification error: {e}")
            return False
    
    async def _send_email_notification(self, alert: AlertInstance) -> bool:
        """Send alert via email."""
        if not self.smtp_host or not self.alert_email_to:
            logger.warning("[AlertEngine] Email not configured")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert.severity.upper()}] {alert.rule_name}"
            msg['From'] = self.alert_email_from
            msg['To'] = ', '.join(self.alert_email_to)
            
            # Plain text version
            text = f"""
Alert: {alert.rule_name}
Severity: {alert.severity.upper()}
Value: {alert.metric_value}
Threshold: {alert.threshold_value}

{alert.message}

---
CogTwin Alert Engine
"""
            
            # HTML version
            html = f"""
<html>
<body>
<h2 style="color: {'red' if alert.severity == 'critical' else 'orange'}">
    {alert.rule_name}
</h2>
<table>
    <tr><td><strong>Severity:</strong></td><td>{alert.severity.upper()}</td></tr>
    <tr><td><strong>Value:</strong></td><td>{alert.metric_value}</td></tr>
    <tr><td><strong>Threshold:</strong></td><td>{alert.threshold_value}</td></tr>
</table>
<p>{alert.message}</p>
<hr>
<small>CogTwin Alert Engine</small>
</body>
</html>
"""
            
            msg.attach(MIMEText(text, 'plain'))
            msg.attach(MIMEText(html, 'html'))
            
            # Send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"[AlertEngine] Email notification sent for {alert.rule_name}")
            return True
            
        except Exception as e:
            logger.error(f"[AlertEngine] Email notification error: {e}")
            return False


# Global instance
alert_engine = AlertEngine()
```

### 5.2 New File: `auth/alerting_routes.py`

```python
"""
Alerting API Routes - Alert management and viewing

Provides endpoints for alert rules CRUD and instance viewing.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

alerting_router = APIRouter()


class AlertRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    metric_type: str
    condition: str
    threshold: float
    window_minutes: int = 5
    custom_sql: Optional[str] = None
    severity: str = 'warning'
    notification_channels: List[str] = ['slack']
    cooldown_minutes: int = 15
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    threshold: Optional[float] = None
    window_minutes: Optional[int] = None
    severity: Optional[str] = None
    notification_channels: Optional[List[str]] = None
    cooldown_minutes: Optional[int] = None
    enabled: Optional[bool] = None


@alerting_router.get("/rules")
async def list_alert_rules():
    """List all alert rules."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, name, description, metric_type, condition, threshold,
                       window_minutes, severity, notification_channels, cooldown_minutes,
                       enabled, last_evaluated_at, last_triggered_at, created_at
                FROM enterprise.alert_rules
                ORDER BY created_at DESC
            """)
        
        return {'rules': [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"[Alerting] List rules error: {e}")
        return {'rules': [], 'error': str(e)}


@alerting_router.post("/rules")
async def create_alert_rule(rule: AlertRuleCreate):
    """Create a new alert rule."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO enterprise.alert_rules
                (name, description, metric_type, condition, threshold, window_minutes,
                 custom_sql, severity, notification_channels, cooldown_minutes, enabled)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id
            """, rule.name, rule.description, rule.metric_type, rule.condition,
                 rule.threshold, rule.window_minutes, rule.custom_sql, rule.severity,
                 rule.notification_channels, rule.cooldown_minutes, rule.enabled)
        
        return {'id': str(row['id']), 'message': 'Rule created'}
    except Exception as e:
        logger.error(f"[Alerting] Create rule error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alerting_router.put("/rules/{rule_id}")
async def update_alert_rule(rule_id: str, update: AlertRuleUpdate):
    """Update an alert rule."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        # Build dynamic update query
        updates = []
        params = []
        param_idx = 1
        
        for field, value in update.dict(exclude_unset=True).items():
            if value is not None:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1
        
        if not updates:
            return {'message': 'No updates provided'}
        
        params.append(rule_id)
        query = f"""
            UPDATE enterprise.alert_rules
            SET {', '.join(updates)}, updated_at = NOW()
            WHERE id = ${param_idx}
        """
        
        async with pool.acquire() as conn:
            await conn.execute(query, *params)
        
        return {'message': 'Rule updated'}
    except Exception as e:
        logger.error(f"[Alerting] Update rule error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alerting_router.delete("/rules/{rule_id}")
async def delete_alert_rule(rule_id: str):
    """Delete an alert rule."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM enterprise.alert_rules WHERE id = $1
            """, rule_id)
        
        return {'message': 'Rule deleted'}
    except Exception as e:
        logger.error(f"[Alerting] Delete rule error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alerting_router.get("/instances")
async def list_alert_instances(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    rule_id: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
):
    """List fired alert instances."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        query = """
            SELECT ai.id, ai.rule_id, ar.name as rule_name, ar.severity,
                   ai.triggered_at, ai.resolved_at, ai.status,
                   ai.acknowledged_by, ai.acknowledged_at,
                   ai.metric_value, ai.threshold_value, ai.message
            FROM enterprise.alert_instances ai
            JOIN enterprise.alert_rules ar ON ai.rule_id = ar.id
            WHERE ai.triggered_at > NOW() - INTERVAL '1 hour' * $1
        """
        params = [hours]
        param_idx = 2
        
        if status:
            query += f" AND ai.status = ${param_idx}"
            params.append(status)
            param_idx += 1
        
        if rule_id:
            query += f" AND ai.rule_id = ${param_idx}"
            params.append(rule_id)
            param_idx += 1
        
        query += f" ORDER BY ai.triggered_at DESC LIMIT ${param_idx}"
        params.append(limit)
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        return {'instances': [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"[Alerting] List instances error: {e}")
        return {'instances': [], 'error': str(e)}


@alerting_router.post("/instances/{instance_id}/acknowledge")
async def acknowledge_alert(instance_id: str, user_email: str = Query(...)):
    """Acknowledge an alert instance."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE enterprise.alert_instances
                SET status = 'acknowledged',
                    acknowledged_by = $2,
                    acknowledged_at = NOW()
                WHERE id = $1
            """, instance_id, user_email)
        
        return {'message': 'Alert acknowledged'}
    except Exception as e:
        logger.error(f"[Alerting] Acknowledge error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alerting_router.post("/instances/{instance_id}/resolve")
async def resolve_alert(instance_id: str):
    """Mark an alert as resolved."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE enterprise.alert_instances
                SET status = 'resolved', resolved_at = NOW()
                WHERE id = $1
            """, instance_id)
        
        return {'message': 'Alert resolved'}
    except Exception as e:
        logger.error(f"[Alerting] Resolve error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 6. BACKEND: MAIN.PY INTEGRATION

Add to `core/main.py`:

```python
# =============================================================================
# IMPORTS - Add near top
# =============================================================================
from core.tracing import trace_collector, start_trace, create_span, get_trace_id
from core.structured_logging import setup_structured_logging, shutdown_structured_logging
from core.alerting import alert_engine
from auth.tracing_routes import tracing_router
from auth.logging_routes import logging_router
from auth.alerting_routes import alerting_router

# =============================================================================
# ROUTER REGISTRATION - Add with other routers
# =============================================================================
app.include_router(tracing_router, prefix="/api/observability", tags=["tracing"])
app.include_router(logging_router, prefix="/api/observability", tags=["logging"])
app.include_router(alerting_router, prefix="/api/observability/alerts", tags=["alerting"])
logger.info("[STARTUP] Observability routes loaded at /api/observability")

# =============================================================================
# STARTUP EVENT - Add after DB pool creation
# =============================================================================
@app.on_event("startup")
async def startup_observability():
    # Get DB pool (assumes it's already created)
    from core.database import get_db_pool
    pool = await get_db_pool()
    
    # Initialize tracing
    trace_collector.set_db_pool(pool)
    await trace_collector.start()
    logger.info("[STARTUP] Trace collector started")
    
    # Initialize structured logging
    setup_structured_logging(pool)
    logger.info("[STARTUP] Structured logging enabled")
    
    # Initialize alert engine
    alert_engine.set_db_pool(pool)
    await alert_engine.start()
    logger.info("[STARTUP] Alert engine started")

@app.on_event("shutdown")
async def shutdown_observability():
    await trace_collector.stop()
    shutdown_structured_logging()
    await alert_engine.stop()
    logger.info("[SHUTDOWN] Observability services stopped")

# =============================================================================
# HTTP MIDDLEWARE - Replace existing timing middleware
# =============================================================================
@app.middleware("http")
async def tracing_middleware(request: Request, call_next):
    """HTTP middleware with distributed tracing."""
    user_email = request.headers.get('X-User-Email')
    
    async with start_trace(
        entry_point='http',
        endpoint=request.url.path,
        method=request.method,
        user_email=user_email,
    ) as trace:
        async with create_span('http_request'):
            response = await call_next(request)
            
            # Add trace ID to response headers
            response.headers['X-Trace-ID'] = trace.trace_id
            
            # Record to metrics
            elapsed_ms = trace.duration_ms or 0
            is_error = response.status_code >= 400
            metrics_collector.record_request(request.url.path, elapsed_ms, error=is_error)
            
            if is_error:
                trace.set_error(Exception(f"HTTP {response.status_code}"))
            
            return response

# =============================================================================
# WEBSOCKET HANDLER - Add tracing to existing handler
# =============================================================================
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket)
    metrics_collector.record_ws_connect()
    
    user_email = None  # Will be set on verify message
    department = None
    
    try:
        while True:
            data = await websocket.receive_json()
            metrics_collector.record_ws_message('in')
            
            msg_type = data.get('type')
            
            # Start a trace for each message
            async with start_trace(
                entry_point='websocket',
                endpoint=f'/ws/{msg_type}',
                session_id=session_id,
                user_email=user_email,
                department=department,
            ) as trace:
                
                if msg_type == 'verify':
                    user_email = data.get('email')
                    department = data.get('division')
                    trace.set_tag('user_email', user_email)
                    # ... existing verify logic ...
                
                elif msg_type == 'message':
                    async with create_span('message_handler'):
                        query = data.get('message', '')
                        
                        # RAG retrieval with tracing
                        async with create_span('rag_retrieve', tags={'query_length': len(query)}):
                            # ... existing RAG logic ...
                            pass
                        
                        # LLM generation with tracing
                        async with create_span('llm_generate'):
                            # ... existing LLM logic ...
                            pass
                
                # ... other message types ...
            
            metrics_collector.record_ws_message('out')
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        metrics_collector.record_ws_disconnect()
```

---

## 7. FRONTEND CHANGES

### 7.1 New Store: `src/lib/stores/observability.ts`

```typescript
/**
 * Observability Store - Tracing, Logging, Alerts
 */

import { writable, derived } from 'svelte/store';
import { auth } from './auth';

// =============================================================================
// TYPES
// =============================================================================

export interface Trace {
    trace_id: string;
    entry_point: string;
    endpoint: string;
    method: string;
    session_id: string;
    user_email: string;
    department: string;
    start_time: string;
    end_time: string;
    duration_ms: number;
    status: string;
    error_message: string | null;
}

export interface Span {
    span_id: string;
    trace_id: string;
    parent_span_id: string | null;
    operation_name: string;
    start_time: string;
    end_time: string;
    duration_ms: number;
    status: string;
    tags: Record<string, any>;
    logs: Array<{ timestamp: string; message: string }>;
}

export interface LogEntry {
    id: string;
    timestamp: string;
    level: string;
    logger_name: string;
    message: string;
    trace_id: string | null;
    user_email: string | null;
    extra: Record<string, any>;
}

export interface AlertRule {
    id: string;
    name: string;
    description: string;
    metric_type: string;
    condition: string;
    threshold: number;
    severity: string;
    enabled: boolean;
    last_triggered_at: string | null;
}

export interface AlertInstance {
    id: string;
    rule_id: string;
    rule_name: string;
    severity: string;
    triggered_at: string;
    status: string;
    metric_value: number;
    threshold_value: number;
    message: string;
}

// =============================================================================
// STORE
// =============================================================================

function createObservabilityStore() {
    const { subscribe, set, update } = writable({
        // Traces
        traces: [] as Trace[],
        tracesLoading: false,
        selectedTrace: null as (Trace & { spans: Span[] }) | null,
        
        // Logs
        logs: [] as LogEntry[],
        logsLoading: false,
        logStreamConnected: false,
        
        // Alerts
        alertRules: [] as AlertRule[],
        alertInstances: [] as AlertInstance[],
        alertsLoading: false,
    });
    
    let logWs: WebSocket | null = null;
    
    function getApiBase(): string {
        return import.meta.env.VITE_API_URL || 'http://localhost:8000';
    }
    
    function getHeaders(): Record<string, string> {
        return {
            'Content-Type': 'application/json',
            'X-User-Email': auth.getEmail() || '',
        };
    }
    
    const store = {
        subscribe,
        
        // =================================================================
        // TRACES
        // =================================================================
        
        async loadTraces(filters: {
            hours?: number;
            status?: string;
            user_email?: string;
            min_duration_ms?: number;
        } = {}) {
            update(s => ({ ...s, tracesLoading: true }));
            
            try {
                const params = new URLSearchParams();
                if (filters.hours) params.set('hours', String(filters.hours));
                if (filters.status) params.set('status', filters.status);
                if (filters.user_email) params.set('user_email', filters.user_email);
                if (filters.min_duration_ms) params.set('min_duration_ms', String(filters.min_duration_ms));
                
                const res = await fetch(`${getApiBase()}/api/observability/traces?${params}`, {
                    headers: getHeaders()
                });
                const data = await res.json();
                
                update(s => ({
                    ...s,
                    traces: data.traces || [],
                    tracesLoading: false,
                }));
            } catch (e) {
                console.error('[Observability] Load traces error:', e);
                update(s => ({ ...s, tracesLoading: false }));
            }
        },
        
        async loadTrace(traceId: string) {
            try {
                const res = await fetch(`${getApiBase()}/api/observability/traces/${traceId}`, {
                    headers: getHeaders()
                });
                const data = await res.json();
                
                update(s => ({
                    ...s,
                    selectedTrace: {
                        ...data.trace,
                        spans: data.spans || [],
                    },
                }));
            } catch (e) {
                console.error('[Observability] Load trace error:', e);
            }
        },
        
        clearSelectedTrace() {
            update(s => ({ ...s, selectedTrace: null }));
        },
        
        // =================================================================
        // LOGS
        // =================================================================
        
        async loadLogs(filters: {
            hours?: number;
            level?: string;
            trace_id?: string;
            search?: string;
        } = {}) {
            update(s => ({ ...s, logsLoading: true }));
            
            try {
                const params = new URLSearchParams();
                if (filters.hours) params.set('hours', String(filters.hours));
                if (filters.level) params.set('level', filters.level);
                if (filters.trace_id) params.set('trace_id', filters.trace_id);
                if (filters.search) params.set('search', filters.search);
                
                const res = await fetch(`${getApiBase()}/api/observability/logs?${params}`, {
                    headers: getHeaders()
                });
                const data = await res.json();
                
                update(s => ({
                    ...s,
                    logs: data.logs || [],
                    logsLoading: false,
                }));
            } catch (e) {
                console.error('[Observability] Load logs error:', e);
                update(s => ({ ...s, logsLoading: false }));
            }
        },
        
        connectLogStream() {
            if (logWs) return;
            
            const apiUrl = getApiBase();
            const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
            const host = new URL(apiUrl).host;
            const url = `${wsProtocol}://${host}/api/observability/logs/stream`;
            
            logWs = new WebSocket(url);
            
            logWs.onopen = () => {
                update(s => ({ ...s, logStreamConnected: true }));
            };
            
            logWs.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'new_log') {
                    update(s => ({
                        ...s,
                        logs: [msg.data, ...s.logs].slice(0, 500),
                    }));
                }
            };
            
            logWs.onclose = () => {
                update(s => ({ ...s, logStreamConnected: false }));
                logWs = null;
            };
        },
        
        disconnectLogStream() {
            if (logWs) {
                logWs.close();
                logWs = null;
            }
        },
        
        // =================================================================
        // ALERTS
        // =================================================================
        
        async loadAlertRules() {
            update(s => ({ ...s, alertsLoading: true }));
            
            try {
                const res = await fetch(`${getApiBase()}/api/observability/alerts/rules`, {
                    headers: getHeaders()
                });
                const data = await res.json();
                
                update(s => ({
                    ...s,
                    alertRules: data.rules || [],
                    alertsLoading: false,
                }));
            } catch (e) {
                console.error('[Observability] Load alert rules error:', e);
                update(s => ({ ...s, alertsLoading: false }));
            }
        },
        
        async loadAlertInstances(hours: number = 24) {
            try {
                const res = await fetch(`${getApiBase()}/api/observability/alerts/instances?hours=${hours}`, {
                    headers: getHeaders()
                });
                const data = await res.json();
                
                update(s => ({
                    ...s,
                    alertInstances: data.instances || [],
                }));
            } catch (e) {
                console.error('[Observability] Load alert instances error:', e);
            }
        },
        
        async toggleAlertRule(ruleId: string, enabled: boolean) {
            try {
                await fetch(`${getApiBase()}/api/observability/alerts/rules/${ruleId}`, {
                    method: 'PUT',
                    headers: getHeaders(),
                    body: JSON.stringify({ enabled }),
                });
                
                await store.loadAlertRules();
            } catch (e) {
                console.error('[Observability] Toggle rule error:', e);
            }
        },
        
        async acknowledgeAlert(instanceId: string) {
            try {
                const email = auth.getEmail();
                await fetch(`${getApiBase()}/api/observability/alerts/instances/${instanceId}/acknowledge?user_email=${email}`, {
                    method: 'POST',
                    headers: getHeaders(),
                });
                
                await store.loadAlertInstances();
            } catch (e) {
                console.error('[Observability] Acknowledge error:', e);
            }
        },
        
        reset() {
            store.disconnectLogStream();
            set({
                traces: [],
                tracesLoading: false,
                selectedTrace: null,
                logs: [],
                logsLoading: false,
                logStreamConnected: false,
                alertRules: [],
                alertInstances: [],
                alertsLoading: false,
            });
        },
    };
    
    return store;
}

export const observabilityStore = createObservabilityStore();

// Derived stores
export const traces = derived(observabilityStore, $s => $s.traces);
export const selectedTrace = derived(observabilityStore, $s => $s.selectedTrace);
export const logs = derived(observabilityStore, $s => $s.logs);
export const alertRules = derived(observabilityStore, $s => $s.alertRules);
export const alertInstances = derived(observabilityStore, $s => $s.alertInstances);
export const firingAlerts = derived(observabilityStore, $s => 
    $s.alertInstances.filter(a => a.status === 'firing')
);
```

### 7.2 New Route: `src/routes/admin/traces/+page.svelte`

```svelte
<!--
  Trace Viewer - Distributed tracing waterfall
-->

<script lang="ts">
    import { onMount } from 'svelte';
    import { observabilityStore, traces, selectedTrace } from '$lib/stores/observability';
    
    let filters = {
        hours: 24,
        status: '',
        min_duration_ms: 0,
    };
    
    onMount(() => {
        observabilityStore.loadTraces(filters);
    });
    
    function applyFilters() {
        observabilityStore.loadTraces(filters);
    }
    
    function selectTrace(traceId: string) {
        observabilityStore.loadTrace(traceId);
    }
    
    function getStatusColor(status: string): string {
        switch (status) {
            case 'completed': return '#00ff41';
            case 'error': return '#ff0055';
            default: return '#ffc800';
        }
    }
    
    function formatDuration(ms: number): string {
        if (ms < 1000) return `${ms.toFixed(0)}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    }
    
    // Calculate span position for waterfall
    function getSpanStyle(span: any, trace: any): string {
        if (!trace.duration_ms) return '';
        const start = new Date(span.start_time).getTime() - new Date(trace.start_time).getTime();
        const left = (start / trace.duration_ms) * 100;
        const width = (span.duration_ms / trace.duration_ms) * 100;
        return `left: ${left}%; width: ${Math.max(width, 1)}%;`;
    }
    
    function getSpanColor(operation: string): string {
        if (operation.includes('rag')) return '#00ffff';
        if (operation.includes('llm')) return '#ff00ff';
        if (operation.includes('http')) return '#00ff41';
        return '#ffc800';
    }
</script>

<svelte:head>
    <title>Traces | CogTwin Admin</title>
</svelte:head>

<div class="traces-page">
    <header class="page-header">
        <h1>Distributed Traces</h1>
        <div class="filters">
            <select bind:value={filters.hours} on:change={applyFilters}>
                <option value={1}>Last 1 hour</option>
                <option value={6}>Last 6 hours</option>
                <option value={24}>Last 24 hours</option>
                <option value={72}>Last 3 days</option>
            </select>
            <select bind:value={filters.status} on:change={applyFilters}>
                <option value="">All Status</option>
                <option value="completed">Completed</option>
                <option value="error">Error</option>
            </select>
            <input 
                type="number" 
                placeholder="Min duration (ms)"
                bind:value={filters.min_duration_ms}
                on:change={applyFilters}
            />
        </div>
    </header>
    
    <div class="content">
        <!-- Trace List -->
        <div class="trace-list">
            <div class="list-header">
                <span>Endpoint</span>
                <span>Duration</span>
                <span>Status</span>
                <span>Time</span>
            </div>
            
            {#each $traces as trace}
                <button 
                    class="trace-row" 
                    class:selected={$selectedTrace?.trace_id === trace.trace_id}
                    on:click={() => selectTrace(trace.trace_id)}
                >
                    <span class="endpoint">{trace.endpoint || '/'}</span>
                    <span class="duration">{formatDuration(trace.duration_ms)}</span>
                    <span class="status" style="color: {getStatusColor(trace.status)}">
                        {trace.status}
                    </span>
                    <span class="time">
                        {new Date(trace.start_time).toLocaleTimeString()}
                    </span>
                </button>
            {/each}
            
            {#if $traces.length === 0}
                <div class="empty">No traces found</div>
            {/if}
        </div>
        
        <!-- Trace Detail / Waterfall -->
        <div class="trace-detail">
            {#if $selectedTrace}
                <div class="detail-header">
                    <h2>{$selectedTrace.endpoint}</h2>
                    <span class="trace-id">Trace: {$selectedTrace.trace_id}</span>
                </div>
                
                <div class="trace-meta">
                    <span>Duration: <strong>{formatDuration($selectedTrace.duration_ms)}</strong></span>
                    <span>User: <strong>{$selectedTrace.user_email || 'N/A'}</strong></span>
                    <span>Status: <strong style="color: {getStatusColor($selectedTrace.status)}">{$selectedTrace.status}</strong></span>
                </div>
                
                <!-- Waterfall -->
                <div class="waterfall">
                    <div class="waterfall-header">
                        <span>Operation</span>
                        <span>Duration</span>
                        <span class="timeline-header">Timeline</span>
                    </div>
                    
                    {#each $selectedTrace.spans as span}
                        <div class="span-row">
                            <span class="span-name" style="padding-left: {span.parent_span_id ? '20px' : '0'}">
                                {span.operation_name}
                            </span>
                            <span class="span-duration">{formatDuration(span.duration_ms)}</span>
                            <div class="span-timeline">
                                <div 
                                    class="span-bar"
                                    style="{getSpanStyle(span, $selectedTrace)} background: {getSpanColor(span.operation_name)}"
                                ></div>
                            </div>
                        </div>
                    {/each}
                </div>
                
                {#if $selectedTrace.error_message}
                    <div class="error-box">
                        <strong>Error:</strong> {$selectedTrace.error_message}
                    </div>
                {/if}
            {:else}
                <div class="no-selection">
                    Select a trace to view details
                </div>
            {/if}
        </div>
    </div>
</div>

<style>
    .traces-page {
        padding: 24px;
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    
    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
    }
    
    .page-header h1 {
        margin: 0;
        font-size: 24px;
        color: #e0e0e0;
    }
    
    .filters {
        display: flex;
        gap: 12px;
    }
    
    .filters select, .filters input {
        padding: 8px 12px;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        color: #e0e0e0;
        font-size: 13px;
    }
    
    .content {
        display: grid;
        grid-template-columns: 400px 1fr;
        gap: 24px;
        flex: 1;
        overflow: hidden;
    }
    
    .trace-list {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        overflow-y: auto;
    }
    
    .list-header, .trace-row {
        display: grid;
        grid-template-columns: 1fr 80px 80px 80px;
        padding: 12px 16px;
        gap: 12px;
        font-size: 13px;
    }
    
    .list-header {
        color: #888;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        position: sticky;
        top: 0;
        background: rgba(0, 0, 0, 0.8);
    }
    
    .trace-row {
        width: 100%;
        background: none;
        border: none;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        color: #e0e0e0;
        cursor: pointer;
        text-align: left;
        transition: background 0.2s;
    }
    
    .trace-row:hover {
        background: rgba(255, 255, 255, 0.05);
    }
    
    .trace-row.selected {
        background: rgba(0, 255, 65, 0.1);
        border-left: 3px solid #00ff41;
    }
    
    .endpoint {
        font-family: 'JetBrains Mono', monospace;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    
    .trace-detail {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 20px;
        overflow-y: auto;
    }
    
    .detail-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }
    
    .detail-header h2 {
        margin: 0;
        font-size: 18px;
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .trace-id {
        font-size: 11px;
        color: #666;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .trace-meta {
        display: flex;
        gap: 24px;
        margin-bottom: 24px;
        font-size: 13px;
        color: #888;
    }
    
    .trace-meta strong {
        color: #e0e0e0;
    }
    
    .waterfall {
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        overflow: hidden;
    }
    
    .waterfall-header, .span-row {
        display: grid;
        grid-template-columns: 150px 80px 1fr;
        padding: 10px 12px;
        gap: 12px;
        font-size: 12px;
    }
    
    .waterfall-header {
        background: rgba(255, 255, 255, 0.05);
        color: #888;
    }
    
    .span-row {
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .span-name {
        font-family: 'JetBrains Mono', monospace;
        color: #e0e0e0;
    }
    
    .span-duration {
        color: #888;
        text-align: right;
    }
    
    .span-timeline {
        position: relative;
        height: 16px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 3px;
    }
    
    .span-bar {
        position: absolute;
        top: 2px;
        height: 12px;
        border-radius: 2px;
        min-width: 2px;
    }
    
    .error-box {
        margin-top: 16px;
        padding: 12px;
        background: rgba(255, 0, 85, 0.1);
        border: 1px solid rgba(255, 0, 85, 0.3);
        border-radius: 6px;
        color: #ff4444;
        font-size: 13px;
    }
    
    .no-selection, .empty {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 200px;
        color: #666;
    }
</style>
```

### 7.3 New Route: `src/routes/admin/logs/+page.svelte`

```svelte
<!--
  Log Viewer - Searchable logs with real-time streaming
-->

<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { observabilityStore, logs } from '$lib/stores/observability';
    
    let filters = {
        hours: 24,
        level: '',
        search: '',
        trace_id: '',
    };
    
    let streaming = false;
    
    onMount(() => {
        observabilityStore.loadLogs(filters);
    });
    
    onDestroy(() => {
        observabilityStore.disconnectLogStream();
    });
    
    function applyFilters() {
        observabilityStore.loadLogs(filters);
    }
    
    function toggleStreaming() {
        if (streaming) {
            observabilityStore.disconnectLogStream();
        } else {
            observabilityStore.connectLogStream();
        }
        streaming = !streaming;
    }
    
    function getLevelColor(level: string): string {
        switch (level) {
            case 'DEBUG': return '#888';
            case 'INFO': return '#00ff41';
            case 'WARNING': return '#ffc800';
            case 'ERROR': return '#ff0055';
            case 'CRITICAL': return '#ff0000';
            default: return '#e0e0e0';
        }
    }
    
    function filterByTrace(traceId: string) {
        filters.trace_id = traceId;
        applyFilters();
    }
</script>

<svelte:head>
    <title>Logs | CogTwin Admin</title>
</svelte:head>

<div class="logs-page">
    <header class="page-header">
        <h1>Structured Logs</h1>
        <div class="controls">
            <button 
                class="stream-btn" 
                class:active={streaming}
                on:click={toggleStreaming}
            >
                {streaming ? '⏸️ Pause' : '▶️ Stream Live'}
            </button>
        </div>
    </header>
    
    <div class="filters">
        <select bind:value={filters.level} on:change={applyFilters}>
            <option value="">All Levels</option>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
            <option value="CRITICAL">CRITICAL</option>
        </select>
        
        <input 
            type="text" 
            placeholder="Search logs..."
            bind:value={filters.search}
            on:keyup={(e) => e.key === 'Enter' && applyFilters()}
        />
        
        <input 
            type="text" 
            placeholder="Trace ID..."
            bind:value={filters.trace_id}
            on:keyup={(e) => e.key === 'Enter' && applyFilters()}
        />
        
        <button class="apply-btn" on:click={applyFilters}>Apply</button>
        
        {#if filters.trace_id}
            <button class="clear-btn" on:click={() => { filters.trace_id = ''; applyFilters(); }}>
                Clear Trace Filter
            </button>
        {/if}
    </div>
    
    <div class="log-container">
        <div class="log-header">
            <span class="col-time">Time</span>
            <span class="col-level">Level</span>
            <span class="col-logger">Logger</span>
            <span class="col-message">Message</span>
            <span class="col-trace">Trace</span>
        </div>
        
        <div class="log-list">
            {#each $logs as log}
                <div class="log-row" class:error={log.level === 'ERROR' || log.level === 'CRITICAL'}>
                    <span class="col-time">
                        {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                    <span class="col-level" style="color: {getLevelColor(log.level)}">
                        {log.level}
                    </span>
                    <span class="col-logger">{log.logger_name.split('.').pop()}</span>
                    <span class="col-message">{log.message}</span>
                    <span class="col-trace">
                        {#if log.trace_id}
                            <button class="trace-link" on:click={() => filterByTrace(log.trace_id)}>
                                {log.trace_id.slice(0, 8)}...
                            </button>
                        {/if}
                    </span>
                </div>
            {/each}
            
            {#if $logs.length === 0}
                <div class="empty">No logs found</div>
            {/if}
        </div>
    </div>
</div>

<style>
    .logs-page {
        padding: 24px;
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    
    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }
    
    .page-header h1 {
        margin: 0;
        font-size: 24px;
        color: #e0e0e0;
    }
    
    .stream-btn {
        padding: 8px 16px;
        background: rgba(0, 255, 65, 0.1);
        border: 1px solid rgba(0, 255, 65, 0.3);
        border-radius: 6px;
        color: #00ff41;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .stream-btn.active {
        background: rgba(0, 255, 65, 0.2);
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    
    .filters {
        display: flex;
        gap: 12px;
        margin-bottom: 16px;
    }
    
    .filters select, .filters input {
        padding: 8px 12px;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        color: #e0e0e0;
        font-size: 13px;
    }
    
    .filters input[type="text"] {
        flex: 1;
    }
    
    .apply-btn, .clear-btn {
        padding: 8px 16px;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        color: #e0e0e0;
        cursor: pointer;
    }
    
    .clear-btn {
        background: rgba(255, 0, 85, 0.1);
        border-color: rgba(255, 0, 85, 0.3);
        color: #ff4444;
    }
    
    .log-container {
        flex: 1;
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }
    
    .log-header, .log-row {
        display: grid;
        grid-template-columns: 100px 80px 120px 1fr 100px;
        padding: 10px 16px;
        gap: 12px;
        font-size: 12px;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .log-header {
        background: rgba(255, 255, 255, 0.05);
        color: #888;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .log-list {
        flex: 1;
        overflow-y: auto;
    }
    
    .log-row {
        border-bottom: 1px solid rgba(255, 255, 255, 0.03);
        color: #e0e0e0;
    }
    
    .log-row.error {
        background: rgba(255, 0, 85, 0.05);
    }
    
    .col-time {
        color: #666;
    }
    
    .col-logger {
        color: #888;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .col-message {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    
    .trace-link {
        background: none;
        border: none;
        color: #00ffff;
        cursor: pointer;
        font-family: inherit;
        font-size: inherit;
    }
    
    .trace-link:hover {
        text-decoration: underline;
    }
    
    .empty {
        padding: 40px;
        text-align: center;
        color: #666;
    }
</style>
```

### 7.4 New Route: `src/routes/admin/alerts/+page.svelte`

```svelte
<!--
  Alert Dashboard - Rules and fired alerts
-->

<script lang="ts">
    import { onMount } from 'svelte';
    import { observabilityStore, alertRules, alertInstances, firingAlerts } from '$lib/stores/observability';
    
    let activeTab = 'instances';
    
    onMount(() => {
        observabilityStore.loadAlertRules();
        observabilityStore.loadAlertInstances();
    });
    
    function getSeverityColor(severity: string): string {
        switch (severity) {
            case 'info': return '#36a64f';
            case 'warning': return '#ffc800';
            case 'critical': return '#ff0055';
            default: return '#888';
        }
    }
    
    function getStatusColor(status: string): string {
        switch (status) {
            case 'firing': return '#ff0055';
            case 'acknowledged': return '#ffc800';
            case 'resolved': return '#00ff41';
            default: return '#888';
        }
    }
</script>

<svelte:head>
    <title>Alerts | CogTwin Admin</title>
</svelte:head>

<div class="alerts-page">
    <header class="page-header">
        <h1>Alert Management</h1>
        
        {#if $firingAlerts.length > 0}
            <div class="firing-badge">
                🚨 {$firingAlerts.length} Firing
            </div>
        {/if}
    </header>
    
    <div class="tabs">
        <button 
            class="tab" 
            class:active={activeTab === 'instances'}
            on:click={() => activeTab = 'instances'}
        >
            Alerts ({$alertInstances.length})
        </button>
        <button 
            class="tab" 
            class:active={activeTab === 'rules'}
            on:click={() => activeTab = 'rules'}
        >
            Rules ({$alertRules.length})
        </button>
    </div>
    
    {#if activeTab === 'instances'}
        <div class="alert-list">
            {#each $alertInstances as alert}
                <div class="alert-card" class:firing={alert.status === 'firing'}>
                    <div class="alert-header">
                        <span class="severity" style="background: {getSeverityColor(alert.severity)}">
                            {alert.severity.toUpperCase()}
                        </span>
                        <span class="rule-name">{alert.rule_name}</span>
                        <span class="status" style="color: {getStatusColor(alert.status)}">
                            {alert.status}
                        </span>
                    </div>
                    
                    <div class="alert-body">
                        <p class="message">{alert.message}</p>
                        <div class="meta">
                            <span>Value: <strong>{alert.metric_value.toFixed(2)}</strong></span>
                            <span>Threshold: <strong>{alert.threshold_value}</strong></span>
                            <span>Triggered: <strong>{new Date(alert.triggered_at).toLocaleString()}</strong></span>
                        </div>
                    </div>
                    
                    {#if alert.status === 'firing'}
                        <div class="alert-actions">
                            <button 
                                class="ack-btn"
                                on:click={() => observabilityStore.acknowledgeAlert(alert.id)}
                            >
                                Acknowledge
                            </button>
                        </div>
                    {/if}
                </div>
            {/each}
            
            {#if $alertInstances.length === 0}
                <div class="empty">
                    ✨ No alerts - everything is running smoothly
                </div>
            {/if}
        </div>
    {:else}
        <div class="rules-list">
            {#each $alertRules as rule}
                <div class="rule-card" class:disabled={!rule.enabled}>
                    <div class="rule-header">
                        <span class="rule-name">{rule.name}</span>
                        <label class="toggle">
                            <input 
                                type="checkbox" 
                                checked={rule.enabled}
                                on:change={() => observabilityStore.toggleAlertRule(rule.id, !rule.enabled)}
                            />
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <p class="rule-desc">{rule.description || 'No description'}</p>
                    
                    <div class="rule-meta">
                        <span>Metric: <strong>{rule.metric_type}</strong></span>
                        <span>Condition: <strong>{rule.condition} {rule.threshold}</strong></span>
                        <span>Severity: 
                            <strong style="color: {getSeverityColor(rule.severity)}">
                                {rule.severity}
                            </strong>
                        </span>
                    </div>
                    
                    {#if rule.last_triggered_at}
                        <div class="last-triggered">
                            Last triggered: {new Date(rule.last_triggered_at).toLocaleString()}
                        </div>
                    {/if}
                </div>
            {/each}
        </div>
    {/if}
</div>

<style>
    .alerts-page {
        padding: 24px;
    }
    
    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
    }
    
    .page-header h1 {
        margin: 0;
        font-size: 24px;
        color: #e0e0e0;
    }
    
    .firing-badge {
        padding: 8px 16px;
        background: rgba(255, 0, 85, 0.2);
        border: 1px solid rgba(255, 0, 85, 0.5);
        border-radius: 20px;
        color: #ff0055;
        font-weight: 600;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    
    .tabs {
        display: flex;
        gap: 4px;
        margin-bottom: 24px;
    }
    
    .tab {
        padding: 10px 20px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px 6px 0 0;
        color: #888;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .tab.active {
        background: rgba(255, 255, 255, 0.1);
        color: #e0e0e0;
        border-bottom-color: transparent;
    }
    
    .alert-list, .rules-list {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }
    
    .alert-card, .rule-card {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 16px;
    }
    
    .alert-card.firing {
        border-color: rgba(255, 0, 85, 0.5);
        background: rgba(255, 0, 85, 0.05);
    }
    
    .alert-header, .rule-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
    }
    
    .severity {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 700;
        color: white;
    }
    
    .rule-name {
        font-size: 16px;
        font-weight: 600;
        color: #e0e0e0;
        flex: 1;
    }
    
    .status {
        font-size: 12px;
        font-weight: 600;
    }
    
    .message {
        margin: 0 0 12px 0;
        color: #e0e0e0;
    }
    
    .meta, .rule-meta {
        display: flex;
        gap: 24px;
        font-size: 13px;
        color: #888;
    }
    
    .meta strong, .rule-meta strong {
        color: #e0e0e0;
    }
    
    .alert-actions {
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .ack-btn {
        padding: 8px 16px;
        background: rgba(255, 200, 0, 0.2);
        border: 1px solid rgba(255, 200, 0, 0.5);
        border-radius: 6px;
        color: #ffc800;
        cursor: pointer;
    }
    
    .rule-card.disabled {
        opacity: 0.5;
    }
    
    .rule-desc {
        margin: 0 0 12px 0;
        color: #888;
        font-size: 14px;
    }
    
    .last-triggered {
        margin-top: 12px;
        font-size: 12px;
        color: #666;
    }
    
    .toggle {
        position: relative;
        width: 44px;
        height: 24px;
    }
    
    .toggle input {
        opacity: 0;
        width: 0;
        height: 0;
    }
    
    .slider {
        position: absolute;
        cursor: pointer;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(255, 255, 255, 0.2);
        transition: 0.3s;
        border-radius: 24px;
    }
    
    .slider:before {
        position: absolute;
        content: "";
        height: 18px;
        width: 18px;
        left: 3px;
        bottom: 3px;
        background-color: white;
        transition: 0.3s;
        border-radius: 50%;
    }
    
    .toggle input:checked + .slider {
        background-color: #00ff41;
    }
    
    .toggle input:checked + .slider:before {
        transform: translateX(20px);
    }
    
    .empty {
        padding: 60px;
        text-align: center;
        color: #00ff41;
        font-size: 18px;
    }
</style>
```

### 7.5 Update AdminDropdown

```svelte
const adminLinks = [
    { href: '/admin', label: 'Nerve Center', icon: '⚡', superOnly: false },
    { href: '/admin/system', label: 'System Health', icon: '💻', superOnly: false },
    { href: '/admin/traces', label: 'Traces', icon: '🔍', superOnly: false },      // NEW
    { href: '/admin/logs', label: 'Logs', icon: '📜', superOnly: false },          // NEW
    { href: '/admin/alerts', label: 'Alerts', icon: '🚨', superOnly: false },      // NEW
    { href: '/admin/analytics', label: 'Analytics', icon: '📊', superOnly: false },
    { href: '/admin/users', label: 'User Management', icon: '👥', superOnly: false },
    { href: '/admin/audit', label: 'Audit Log', icon: '📋', superOnly: true },
];
```

---

## 8. ENVIRONMENT VARIABLES

Add to Railway (optional - for notifications):

```env
# Slack notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Email notifications (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_EMAIL_FROM=alerts@yourdomain.com
ALERT_EMAIL_TO=admin@yourdomain.com,ops@yourdomain.com
```

---

## 9. AGENT EXECUTION BLOCK

```
FEATURE BUILD: OBSERVABILITY_PHASE_2_FULL_STACK

⚡ USE PARALLEL SUB-AGENTS - This is a large build ⚡

AGENT A - Backend Tracing:
- Create file: core/tracing.py
- Create file: auth/tracing_routes.py

AGENT B - Backend Logging:
- Create file: core/structured_logging.py
- Create file: auth/logging_routes.py

AGENT C - Backend Alerting:
- Create file: core/alerting.py
- Create file: auth/alerting_routes.py

AGENT D - Frontend:
- Create file: src/lib/stores/observability.ts
- Create file: src/routes/admin/traces/+page.svelte
- Create file: src/routes/admin/logs/+page.svelte
- Create file: src/routes/admin/alerts/+page.svelte
- Update: src/lib/components/ribbon/AdminDropdown.svelte

COORDINATED TASKS (after parallel work):
- Create migration: migrations/008_tracing_tables.sql
- Create migration: migrations/009_structured_logs.sql
- Create migration: migrations/010_alert_tables.sql
- Update core/main.py with all integrations

VERIFICATION:
- Backend: curl /api/observability/traces
- Backend: curl /api/observability/logs
- Backend: curl /api/observability/alerts/rules
- Frontend: Navigate to /admin/traces, /admin/logs, /admin/alerts

COMPLETION CRITERIA:
- All 3 migrations run successfully
- All new routes return data
- Trace waterfall renders
- Log viewer shows logs
- Alert rules listed
- No TypeScript/Python errors
```

---

## 10. ROLLBACK PLAN

```sql
-- Database rollback
DROP TABLE IF EXISTS enterprise.alert_instances;
DROP TABLE IF EXISTS enterprise.alert_rules;
DROP TABLE IF EXISTS enterprise.structured_logs;
DROP TABLE IF EXISTS enterprise.trace_spans;
DROP TABLE IF EXISTS enterprise.traces;

DROP FUNCTION IF EXISTS notify_new_log();
```

```bash
# Git rollback
git revert HEAD~N  # N = number of commits
```
