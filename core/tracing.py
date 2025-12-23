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
