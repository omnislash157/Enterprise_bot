# Feature Build Sheet: Observability Suite - Phase 1 Foundation

## Feature: OBSERVABILITY_PHASE_1
**Priority:** P1  
**Estimated Complexity:** Medium (leverages 60% existing infrastructure)  
**Timeline:** 1 week  
**Dependencies:** Redis (exists), PostgreSQL (exists), WebSocket (exists)

---

## 1. OVERVIEW

### What We're Building
Real-time system observability dashboard that replaces Grafana/Datadog. Phase 1 delivers:
- System health metrics (CPU, memory, connections)
- RAG pipeline performance breakdown
- Cache hit/miss rates
- LLM cost tracking
- Real-time WebSocket metrics streaming
- Enhanced Nerve Center dashboard

### User Story
> As an admin, I want to see real-time system health and RAG performance metrics in the Nerve Center so I can monitor system health without external tools.

### Acceptance Criteria
- [ ] System metrics display (CPU, memory, disk, connections)
- [ ] RAG latency breakdown (embedding, vector search, total)
- [ ] Cache performance gauges (hit rate %)
- [ ] LLM metrics (requests, tokens, estimated cost)
- [ ] WebSocket live streaming (5s refresh)
- [ ] All data persisted to PostgreSQL for historical queries

---

## 2. DATABASE CHANGES

### Migration File: `migrations/007_observability_tables.sql`

```sql
-- =============================================================================
-- OBSERVABILITY TABLES - Phase 1
-- Run: psql -f migrations/007_observability_tables.sql
-- =============================================================================

-- Table 1: Request-level metrics (enhanced from existing timing middleware)
CREATE TABLE IF NOT EXISTS enterprise.request_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    response_time_ms FLOAT NOT NULL,
    user_email VARCHAR(255),
    department VARCHAR(50),
    request_size_bytes INTEGER,
    response_size_bytes INTEGER,
    trace_id VARCHAR(32)
);

CREATE INDEX idx_request_metrics_ts ON enterprise.request_metrics(timestamp DESC);
CREATE INDEX idx_request_metrics_endpoint ON enterprise.request_metrics(endpoint);
CREATE INDEX idx_request_metrics_status ON enterprise.request_metrics(status_code);

-- Table 2: System metrics (CPU, memory, connections)
CREATE TABLE IF NOT EXISTS enterprise.system_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_type VARCHAR(50) NOT NULL,  -- 'cpu', 'memory', 'disk', 'connections'
    metric_name VARCHAR(100) NOT NULL,
    value FLOAT NOT NULL,
    unit VARCHAR(20),  -- 'percent', 'bytes', 'count', 'ms'
    tags JSONB DEFAULT '{}'
);

CREATE INDEX idx_system_metrics_ts ON enterprise.system_metrics(timestamp DESC);
CREATE INDEX idx_system_metrics_type ON enterprise.system_metrics(metric_type, metric_name);

-- Table 3: LLM call metrics (cost tracking)
CREATE TABLE IF NOT EXISTS enterprise.llm_call_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,  -- 'xai', 'anthropic'
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    elapsed_ms FLOAT NOT NULL,
    first_token_ms FLOAT,  -- Time to first token (streaming)
    user_email VARCHAR(255),
    department VARCHAR(50),
    query_category VARCHAR(50),
    trace_id VARCHAR(32),
    cost_usd DECIMAL(10, 6),
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT
);

CREATE INDEX idx_llm_metrics_ts ON enterprise.llm_call_metrics(timestamp DESC);
CREATE INDEX idx_llm_metrics_model ON enterprise.llm_call_metrics(model);
CREATE INDEX idx_llm_metrics_user ON enterprise.llm_call_metrics(user_email);
CREATE INDEX idx_llm_metrics_dept ON enterprise.llm_call_metrics(department);

-- Table 4: RAG pipeline metrics (per-query breakdown)
CREATE TABLE IF NOT EXISTS enterprise.rag_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trace_id VARCHAR(32),
    user_email VARCHAR(255),
    department VARCHAR(50),
    query_hash VARCHAR(64),
    -- Timing breakdown
    total_ms FLOAT NOT NULL,
    embedding_ms FLOAT,
    vector_search_ms FLOAT,
    rerank_ms FLOAT,
    -- Results
    chunks_retrieved INTEGER,
    chunks_used INTEGER,
    cache_hit BOOLEAN DEFAULT FALSE,
    embedding_cache_hit BOOLEAN DEFAULT FALSE,
    -- Quality signals
    top_score FLOAT,
    avg_score FLOAT,
    threshold_used FLOAT
);

CREATE INDEX idx_rag_metrics_ts ON enterprise.rag_metrics(timestamp DESC);
CREATE INDEX idx_rag_metrics_dept ON enterprise.rag_metrics(department);
CREATE INDEX idx_rag_metrics_cache ON enterprise.rag_metrics(cache_hit);

-- Table 5: Cache metrics (aggregated snapshots)
CREATE TABLE IF NOT EXISTS enterprise.cache_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cache_type VARCHAR(50) NOT NULL,  -- 'rag', 'embedding'
    hits INTEGER NOT NULL DEFAULT 0,
    misses INTEGER NOT NULL DEFAULT 0,
    hit_rate FLOAT,
    memory_used_bytes BIGINT,
    keys_count INTEGER
);

CREATE INDEX idx_cache_metrics_ts ON enterprise.cache_metrics(timestamp DESC);
CREATE INDEX idx_cache_metrics_type ON enterprise.cache_metrics(cache_type);

-- Cleanup: Auto-delete old metrics (retention policy)
-- Run this as a scheduled job or PostgreSQL cron
-- DELETE FROM enterprise.request_metrics WHERE timestamp < NOW() - INTERVAL '30 days';
-- DELETE FROM enterprise.system_metrics WHERE timestamp < NOW() - INTERVAL '7 days';
-- DELETE FROM enterprise.llm_call_metrics WHERE timestamp < NOW() - INTERVAL '90 days';
-- DELETE FROM enterprise.rag_metrics WHERE timestamp < NOW() - INTERVAL '30 days';
-- DELETE FROM enterprise.cache_metrics WHERE timestamp < NOW() - INTERVAL '7 days';
```

---

## 3. BACKEND CHANGES

### 3.1 New File: `core/metrics_collector.py`

```python
"""
Metrics Collector - Centralized observability data collection

Collects system metrics, aggregates cache stats, and provides
real-time snapshots for WebSocket streaming.

Usage:
    from core.metrics_collector import metrics_collector
    
    # Record a metric
    metrics_collector.record_llm_call(model, tokens, elapsed_ms, ...)
    
    # Get current snapshot
    snapshot = await metrics_collector.get_snapshot()
"""

import asyncio
import time
import logging
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from collections import deque
import threading

logger = logging.getLogger(__name__)

# Try to import psutil for system metrics
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("[Metrics] psutil not available - system metrics disabled")


@dataclass
class RingBuffer:
    """Thread-safe ring buffer for recent values."""
    maxlen: int = 100
    _data: deque = field(default_factory=lambda: deque(maxlen=100))
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def append(self, value: float):
        with self._lock:
            self._data.append(value)
    
    def avg(self) -> float:
        with self._lock:
            if not self._data:
                return 0.0
            return sum(self._data) / len(self._data)
    
    def percentile(self, p: float) -> float:
        with self._lock:
            if not self._data:
                return 0.0
            sorted_data = sorted(self._data)
            idx = int(len(sorted_data) * p)
            return sorted_data[min(idx, len(sorted_data) - 1)]
    
    def count(self) -> int:
        return len(self._data)


class MetricsCollector:
    """
    Central metrics collection service.
    
    Collects in-memory metrics and periodically flushes to database.
    Provides real-time snapshots for WebSocket streaming.
    """
    
    _instance: Optional['MetricsCollector'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.start_time = time.time()
        
        # WebSocket connection tracking
        self.ws_connections_active = 0
        self.ws_connections_total = 0
        self.ws_messages_in = 0
        self.ws_messages_out = 0
        
        # Request metrics (ring buffers for percentiles)
        self.request_latencies: Dict[str, RingBuffer] = {}
        self.request_counts: Dict[str, int] = {}
        self.request_errors: Dict[str, int] = {}
        
        # RAG metrics
        self.rag_latency = RingBuffer(maxlen=500)
        self.rag_embedding_latency = RingBuffer(maxlen=500)
        self.rag_search_latency = RingBuffer(maxlen=500)
        self.rag_chunks = RingBuffer(maxlen=500)
        self.rag_total = 0
        self.rag_zero_chunks = 0
        
        # Cache metrics (counters)
        self.cache_hits = 0
        self.cache_misses = 0
        self.embedding_cache_hits = 0
        self.embedding_cache_misses = 0
        
        # LLM metrics
        self.llm_requests = 0
        self.llm_latency = RingBuffer(maxlen=500)
        self.llm_first_token = RingBuffer(maxlen=500)
        self.llm_tokens_in = 0
        self.llm_tokens_out = 0
        self.llm_errors = 0
        
        # Cost tracking (USD)
        self.llm_cost_total = 0.0
        
        # Thread safety
        self._lock = threading.Lock()
        
        logger.info("[Metrics] MetricsCollector initialized")
    
    # =========================================================================
    # RECORDING METHODS
    # =========================================================================
    
    def record_ws_connect(self):
        """Record WebSocket connection."""
        with self._lock:
            self.ws_connections_active += 1
            self.ws_connections_total += 1
    
    def record_ws_disconnect(self):
        """Record WebSocket disconnection."""
        with self._lock:
            self.ws_connections_active = max(0, self.ws_connections_active - 1)
    
    def record_ws_message(self, direction: str = 'in'):
        """Record WebSocket message."""
        with self._lock:
            if direction == 'in':
                self.ws_messages_in += 1
            else:
                self.ws_messages_out += 1
    
    def record_request(self, endpoint: str, latency_ms: float, error: bool = False):
        """Record HTTP request metrics."""
        with self._lock:
            if endpoint not in self.request_latencies:
                self.request_latencies[endpoint] = RingBuffer(maxlen=200)
                self.request_counts[endpoint] = 0
                self.request_errors[endpoint] = 0
            
            self.request_latencies[endpoint].append(latency_ms)
            self.request_counts[endpoint] += 1
            if error:
                self.request_errors[endpoint] += 1
    
    def record_rag_query(
        self,
        total_ms: float,
        embedding_ms: float = 0,
        search_ms: float = 0,
        chunks: int = 0,
        cache_hit: bool = False,
        embedding_cache_hit: bool = False
    ):
        """Record RAG pipeline metrics."""
        with self._lock:
            self.rag_latency.append(total_ms)
            self.rag_embedding_latency.append(embedding_ms)
            self.rag_search_latency.append(search_ms)
            self.rag_chunks.append(chunks)
            self.rag_total += 1
            
            if chunks == 0:
                self.rag_zero_chunks += 1
            
            if cache_hit:
                self.cache_hits += 1
            else:
                self.cache_misses += 1
            
            if embedding_cache_hit:
                self.embedding_cache_hits += 1
            else:
                self.embedding_cache_misses += 1
    
    def record_llm_call(
        self,
        latency_ms: float,
        first_token_ms: float = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0,
        error: bool = False
    ):
        """Record LLM API call metrics."""
        with self._lock:
            self.llm_requests += 1
            self.llm_latency.append(latency_ms)
            if first_token_ms > 0:
                self.llm_first_token.append(first_token_ms)
            self.llm_tokens_in += tokens_in
            self.llm_tokens_out += tokens_out
            self.llm_cost_total += cost_usd
            if error:
                self.llm_errors += 1
    
    # =========================================================================
    # SNAPSHOT METHODS
    # =========================================================================
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system resource metrics."""
        if not PSUTIL_AVAILABLE:
            return {'error': 'psutil not available'}
        
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Process-specific metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_gb': round(memory.used / (1024**3), 2),
                'memory_total_gb': round(memory.total / (1024**3), 2),
                'disk_percent': disk.percent,
                'disk_used_gb': round(disk.used / (1024**3), 2),
                'process_memory_mb': round(process_memory.rss / (1024**2), 2),
                'process_threads': process.num_threads(),
            }
        except Exception as e:
            logger.error(f"[Metrics] System metrics error: {e}")
            return {'error': str(e)}
    
    def get_snapshot(self) -> Dict[str, Any]:
        """Get complete metrics snapshot for API/WebSocket."""
        uptime = time.time() - self.start_time
        
        # Cache hit rates
        total_cache = self.cache_hits + self.cache_misses
        cache_hit_rate = (self.cache_hits / total_cache * 100) if total_cache > 0 else 0
        
        total_embed_cache = self.embedding_cache_hits + self.embedding_cache_misses
        embed_hit_rate = (self.embedding_cache_hits / total_embed_cache * 100) if total_embed_cache > 0 else 0
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'uptime_seconds': round(uptime, 0),
            
            'system': self.get_system_metrics(),
            
            'websocket': {
                'connections_active': self.ws_connections_active,
                'connections_total': self.ws_connections_total,
                'messages_in': self.ws_messages_in,
                'messages_out': self.ws_messages_out,
            },
            
            'rag': {
                'total_queries': self.rag_total,
                'latency_avg_ms': round(self.rag_latency.avg(), 1),
                'latency_p95_ms': round(self.rag_latency.percentile(0.95), 1),
                'embedding_avg_ms': round(self.rag_embedding_latency.avg(), 1),
                'search_avg_ms': round(self.rag_search_latency.avg(), 1),
                'avg_chunks': round(self.rag_chunks.avg(), 1),
                'zero_chunk_rate': round(self.rag_zero_chunks / self.rag_total * 100, 1) if self.rag_total > 0 else 0,
            },
            
            'cache': {
                'rag_hit_rate': round(cache_hit_rate, 1),
                'embedding_hit_rate': round(embed_hit_rate, 1),
                'rag_hits': self.cache_hits,
                'rag_misses': self.cache_misses,
                'embedding_hits': self.embedding_cache_hits,
                'embedding_misses': self.embedding_cache_misses,
            },
            
            'llm': {
                'total_requests': self.llm_requests,
                'latency_avg_ms': round(self.llm_latency.avg(), 1),
                'latency_p95_ms': round(self.llm_latency.percentile(0.95), 1),
                'first_token_avg_ms': round(self.llm_first_token.avg(), 1),
                'tokens_in_total': self.llm_tokens_in,
                'tokens_out_total': self.llm_tokens_out,
                'cost_total_usd': round(self.llm_cost_total, 4),
                'error_count': self.llm_errors,
            },
            
            'api': {
                'endpoints': {
                    endpoint: {
                        'requests': self.request_counts.get(endpoint, 0),
                        'latency_avg_ms': round(buf.avg(), 1),
                        'latency_p95_ms': round(buf.percentile(0.95), 1),
                        'errors': self.request_errors.get(endpoint, 0),
                    }
                    for endpoint, buf in self.request_latencies.items()
                }
            },
        }
    
    def get_health(self) -> Dict[str, Any]:
        """Quick health check for uptime monitoring."""
        system = self.get_system_metrics()
        
        # Determine health status
        status = 'healthy'
        issues = []
        
        if system.get('cpu_percent', 0) > 90:
            status = 'degraded'
            issues.append('High CPU usage')
        
        if system.get('memory_percent', 0) > 90:
            status = 'critical'
            issues.append('High memory usage')
        
        if system.get('disk_percent', 0) > 90:
            status = 'critical'
            issues.append('Low disk space')
        
        cache_total = self.cache_hits + self.cache_misses
        if cache_total > 100 and (self.cache_hits / cache_total) < 0.2:
            status = 'degraded' if status == 'healthy' else status
            issues.append('Low cache hit rate')
        
        return {
            'status': status,
            'issues': issues,
            'uptime_seconds': round(time.time() - self.start_time, 0),
            'ws_connections': self.ws_connections_active,
            'timestamp': datetime.utcnow().isoformat(),
        }


# Global singleton
metrics_collector = MetricsCollector()
```

### 3.2 New File: `auth/metrics_routes.py`

```python
"""
Metrics API Routes - Observability endpoints

All routes require admin access.
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from typing import Optional
import asyncio
import logging

from core.metrics_collector import metrics_collector

logger = logging.getLogger(__name__)

metrics_router = APIRouter()


@metrics_router.get("/snapshot")
async def get_metrics_snapshot():
    """Get full metrics snapshot."""
    return metrics_collector.get_snapshot()


@metrics_router.get("/health")
async def get_health():
    """
    Health check endpoint for uptime monitoring.
    No auth required - used by load balancers/monitors.
    """
    return metrics_collector.get_health()


@metrics_router.get("/system")
async def get_system_metrics():
    """Get system resource metrics only."""
    return metrics_collector.get_system_metrics()


@metrics_router.get("/rag")
async def get_rag_metrics():
    """Get RAG pipeline metrics only."""
    snapshot = metrics_collector.get_snapshot()
    return {
        'rag': snapshot['rag'],
        'cache': snapshot['cache'],
    }


@metrics_router.get("/llm")
async def get_llm_metrics():
    """Get LLM/AI metrics only."""
    snapshot = metrics_collector.get_snapshot()
    return snapshot['llm']


# =============================================================================
# WEBSOCKET STREAMING
# =============================================================================

class MetricsStreamManager:
    """Manages WebSocket connections for metrics streaming."""
    
    def __init__(self):
        self.connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
        logger.info(f"[Metrics WS] Client connected. Total: {len(self.connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
        logger.info(f"[Metrics WS] Client disconnected. Total: {len(self.connections)}")
    
    async def broadcast(self, data: dict):
        """Send metrics to all connected clients."""
        disconnected = []
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)


metrics_stream_manager = MetricsStreamManager()


@metrics_router.websocket("/stream")
async def metrics_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time metrics streaming.
    Sends snapshot every 5 seconds.
    
    Connect: ws://host/api/metrics/stream
    """
    await metrics_stream_manager.connect(websocket)
    
    try:
        # Send initial snapshot immediately
        await websocket.send_json({
            'type': 'metrics_snapshot',
            'data': metrics_collector.get_snapshot()
        })
        
        # Stream updates every 5 seconds
        while True:
            await asyncio.sleep(5)
            await websocket.send_json({
                'type': 'metrics_snapshot',
                'data': metrics_collector.get_snapshot()
            })
    except WebSocketDisconnect:
        metrics_stream_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"[Metrics WS] Error: {e}")
        metrics_stream_manager.disconnect(websocket)
```

### 3.3 Wire into `core/main.py`

Add these changes to main.py:

```python
# =============================================================================
# IMPORTS - Add near top of file
# =============================================================================
from core.metrics_collector import metrics_collector
from auth.metrics_routes import metrics_router

# =============================================================================
# ROUTER REGISTRATION - Add with other routers (~line 50-60)
# =============================================================================
app.include_router(metrics_router, prefix="/api/metrics", tags=["metrics"])
logger.info("[STARTUP] Metrics routes loaded at /api/metrics")

# =============================================================================
# TIMING MIDDLEWARE - Enhance existing middleware (~line 100-120)
# Replace or enhance existing timing middleware:
# =============================================================================
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start) * 1000
    
    # Add header (existing behavior)
    response.headers["X-Response-Time"] = f"{elapsed_ms:.2f}ms"
    
    # Record to metrics collector (NEW)
    endpoint = request.url.path
    is_error = response.status_code >= 400
    metrics_collector.record_request(endpoint, elapsed_ms, error=is_error)
    
    return response

# =============================================================================
# WEBSOCKET INSTRUMENTATION - In websocket_endpoint (~line 683)
# Add at connection start:
# =============================================================================
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket)
    metrics_collector.record_ws_connect()  # ADD THIS
    
    try:
        while True:
            data = await websocket.receive_json()
            metrics_collector.record_ws_message('in')  # ADD THIS
            
            # ... existing message handling ...
            
            await websocket.send_json(response)
            metrics_collector.record_ws_message('out')  # ADD THIS
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        metrics_collector.record_ws_disconnect()  # ADD THIS
    except Exception as e:
        logger.error(f"[WS] Error: {e}")
        metrics_collector.record_ws_disconnect()  # ADD THIS

# =============================================================================
# STARTUP EVENT - Add psutil check (~line 200)
# =============================================================================
@app.on_event("startup")
async def startup_event():
    # ... existing startup code ...
    
    # Check psutil availability
    try:
        import psutil
        logger.info("[STARTUP] psutil available - system metrics enabled")
    except ImportError:
        logger.warning("[STARTUP] psutil not installed - run: pip install psutil")
```

### 3.4 Instrument `core/enterprise_rag.py`

Add timing instrumentation to the RAG search method:

```python
# At top of file, add import
from core.metrics_collector import metrics_collector
import time

# In the search() method, wrap the logic:
async def search(self, query: str, department_id: str, threshold: float = 0.7) -> List[Dict]:
    """Search for relevant documents."""
    start_total = time.time()
    embedding_ms = 0
    search_ms = 0
    cache_hit = False
    embedding_cache_hit = False
    
    try:
        # Check RAG cache first
        cache_key = f"rag:{hash(query)}:{department_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            cache_hit = True
            elapsed_total = (time.time() - start_total) * 1000
            metrics_collector.record_rag_query(
                total_ms=elapsed_total,
                chunks=len(cached),
                cache_hit=True
            )
            return cached
        
        # Generate embedding
        start_embed = time.time()
        # Check embedding cache
        embed_cache_key = f"emb:{hash(query)}"
        embedding = await self.cache.get(embed_cache_key)
        if embedding:
            embedding_cache_hit = True
        else:
            embedding = await self._generate_embedding(query)
            await self.cache.set(embed_cache_key, embedding, ttl=86400)
        embedding_ms = (time.time() - start_embed) * 1000
        
        # Vector search
        start_search = time.time()
        results = await self._vector_search(embedding, department_id, threshold)
        search_ms = (time.time() - start_search) * 1000
        
        # Cache results
        await self.cache.set(cache_key, results, ttl=300)
        
        elapsed_total = (time.time() - start_total) * 1000
        
        # Record metrics
        metrics_collector.record_rag_query(
            total_ms=elapsed_total,
            embedding_ms=embedding_ms,
            search_ms=search_ms,
            chunks=len(results),
            cache_hit=False,
            embedding_cache_hit=embedding_cache_hit
        )
        
        return results
        
    except Exception as e:
        elapsed_total = (time.time() - start_total) * 1000
        metrics_collector.record_rag_query(total_ms=elapsed_total, chunks=0)
        raise
```

### 3.5 Instrument `core/model_adapter.py`

Add LLM metrics collection:

```python
# At top of file
from core.metrics_collector import metrics_collector

# LLM pricing (per 1M tokens) - update as needed
LLM_PRICING = {
    'grok-4-1-fast-reasoning': {'input': 3.00, 'output': 15.00},
    'grok-4-1': {'input': 3.00, 'output': 15.00},
    'claude-3-sonnet': {'input': 3.00, 'output': 15.00},
}

def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate USD cost for LLM call."""
    pricing = LLM_PRICING.get(model, {'input': 5.00, 'output': 15.00})
    cost = (tokens_in * pricing['input'] + tokens_out * pricing['output']) / 1_000_000
    return cost

# In the streaming method, add instrumentation:
async def stream_response(self, messages, ...):
    start = time.time()
    first_token_time = None
    tokens_in = 0
    tokens_out = 0
    
    try:
        async for chunk in self._stream_api_call(messages):
            if first_token_time is None:
                first_token_time = time.time()
            
            # ... existing streaming logic ...
            tokens_out += len(chunk.get('content', '').split())  # Rough estimate
            
            yield chunk
        
        elapsed_ms = (time.time() - start) * 1000
        first_token_ms = (first_token_time - start) * 1000 if first_token_time else 0
        
        # Record metrics
        cost = calculate_cost(self.model, tokens_in, tokens_out)
        metrics_collector.record_llm_call(
            latency_ms=elapsed_ms,
            first_token_ms=first_token_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost
        )
        
    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        metrics_collector.record_llm_call(latency_ms=elapsed_ms, error=True)
        raise
```

---

## 4. FRONTEND CHANGES

### 4.1 New File: `src/lib/stores/metrics.ts`

```typescript
/**
 * Metrics Store - Real-time observability data
 * 
 * Connects to /api/metrics/stream for live updates
 * Falls back to polling if WebSocket unavailable
 */

import { writable, derived } from 'svelte/store';
import { auth } from './auth';

// =============================================================================
// TYPES
// =============================================================================

export interface SystemMetrics {
    cpu_percent: number;
    memory_percent: number;
    memory_used_gb: number;
    memory_total_gb: number;
    disk_percent: number;
    disk_used_gb: number;
    process_memory_mb: number;
    process_threads: number;
}

export interface WebSocketMetrics {
    connections_active: number;
    connections_total: number;
    messages_in: number;
    messages_out: number;
}

export interface RagMetrics {
    total_queries: number;
    latency_avg_ms: number;
    latency_p95_ms: number;
    embedding_avg_ms: number;
    search_avg_ms: number;
    avg_chunks: number;
    zero_chunk_rate: number;
}

export interface CacheMetrics {
    rag_hit_rate: number;
    embedding_hit_rate: number;
    rag_hits: number;
    rag_misses: number;
    embedding_hits: number;
    embedding_misses: number;
}

export interface LlmMetrics {
    total_requests: number;
    latency_avg_ms: number;
    latency_p95_ms: number;
    first_token_avg_ms: number;
    tokens_in_total: number;
    tokens_out_total: number;
    cost_total_usd: number;
    error_count: number;
}

export interface MetricsSnapshot {
    timestamp: string;
    uptime_seconds: number;
    system: SystemMetrics;
    websocket: WebSocketMetrics;
    rag: RagMetrics;
    cache: CacheMetrics;
    llm: LlmMetrics;
    api: {
        endpoints: Record<string, {
            requests: number;
            latency_avg_ms: number;
            latency_p95_ms: number;
            errors: number;
        }>;
    };
}

interface MetricsState {
    snapshot: MetricsSnapshot | null;
    connected: boolean;
    error: string | null;
    lastUpdated: Date | null;
    history: {
        timestamps: string[];
        cpu: number[];
        memory: number[];
        ragLatency: number[];
        cacheHitRate: number[];
        wsConnections: number[];
    };
}

// =============================================================================
// STORE
// =============================================================================

const MAX_HISTORY = 60;

function createMetricsStore() {
    const { subscribe, set, update } = writable<MetricsState>({
        snapshot: null,
        connected: false,
        error: null,
        lastUpdated: null,
        history: {
            timestamps: [],
            cpu: [],
            memory: [],
            ragLatency: [],
            cacheHitRate: [],
            wsConnections: [],
        },
    });
    
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    
    function getWsUrl(): string {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
        const host = new URL(apiUrl).host;
        return `${wsProtocol}://${host}/api/metrics/stream`;
    }
    
    function appendHistory(state: MetricsState, snapshot: MetricsSnapshot): MetricsState['history'] {
        const time = new Date().toLocaleTimeString();
        return {
            timestamps: [...state.history.timestamps, time].slice(-MAX_HISTORY),
            cpu: [...state.history.cpu, snapshot.system?.cpu_percent || 0].slice(-MAX_HISTORY),
            memory: [...state.history.memory, snapshot.system?.memory_percent || 0].slice(-MAX_HISTORY),
            ragLatency: [...state.history.ragLatency, snapshot.rag?.latency_avg_ms || 0].slice(-MAX_HISTORY),
            cacheHitRate: [...state.history.cacheHitRate, snapshot.cache?.rag_hit_rate || 0].slice(-MAX_HISTORY),
            wsConnections: [...state.history.wsConnections, snapshot.websocket?.connections_active || 0].slice(-MAX_HISTORY),
        };
    }
    
    const store = {
        subscribe,
        
        connect() {
            if (ws?.readyState === WebSocket.OPEN) return;
            
            try {
                ws = new WebSocket(getWsUrl());
                
                ws.onopen = () => {
                    reconnectAttempts = 0;
                    update(s => ({ ...s, connected: true, error: null }));
                    console.log('[Metrics WS] Connected');
                };
                
                ws.onmessage = (event) => {
                    try {
                        const msg = JSON.parse(event.data);
                        if (msg.type === 'metrics_snapshot') {
                            update(s => ({
                                ...s,
                                snapshot: msg.data,
                                lastUpdated: new Date(),
                                history: appendHistory(s, msg.data),
                            }));
                        }
                    } catch (e) {
                        console.error('[Metrics WS] Parse error:', e);
                    }
                };
                
                ws.onerror = (error) => {
                    console.error('[Metrics WS] Error:', error);
                    update(s => ({ ...s, error: 'Connection error' }));
                };
                
                ws.onclose = () => {
                    update(s => ({ ...s, connected: false }));
                    console.log('[Metrics WS] Disconnected');
                    
                    // Auto-reconnect with backoff
                    if (reconnectAttempts < maxReconnectAttempts) {
                        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
                        reconnectAttempts++;
                        reconnectTimer = setTimeout(() => store.connect(), delay);
                    }
                };
            } catch (e) {
                update(s => ({ ...s, error: `Failed to connect: ${e}` }));
            }
        },
        
        disconnect() {
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
            if (ws) {
                ws.close();
                ws = null;
            }
            reconnectAttempts = maxReconnectAttempts; // Prevent auto-reconnect
            update(s => ({ ...s, connected: false }));
        },
        
        // Fallback: manual fetch if WebSocket not available
        async fetchSnapshot() {
            try {
                const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                const res = await fetch(`${apiUrl}/api/metrics/snapshot`, {
                    headers: { 'X-User-Email': auth.getEmail() || '' }
                });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                update(s => ({
                    ...s,
                    snapshot: data,
                    lastUpdated: new Date(),
                    history: appendHistory(s, data),
                }));
            } catch (e) {
                update(s => ({ ...s, error: `Fetch failed: ${e}` }));
            }
        },
        
        reset() {
            store.disconnect();
            set({
                snapshot: null,
                connected: false,
                error: null,
                lastUpdated: null,
                history: {
                    timestamps: [],
                    cpu: [],
                    memory: [],
                    ragLatency: [],
                    cacheHitRate: [],
                    wsConnections: [],
                },
            });
        },
    };
    
    return store;
}

export const metricsStore = createMetricsStore();

// =============================================================================
// DERIVED STORES
// =============================================================================

export const metricsSnapshot = derived(metricsStore, $s => $s.snapshot);
export const metricsConnected = derived(metricsStore, $s => $s.connected);
export const metricsHistory = derived(metricsStore, $s => $s.history);

export const systemHealth = derived(metricsStore, $s => {
    if (!$s.snapshot) return 'unknown';
    const { system, cache, rag } = $s.snapshot;
    
    if (system?.cpu_percent > 90 || system?.memory_percent > 90) return 'critical';
    if (cache?.rag_hit_rate < 20 || rag?.latency_p95_ms > 5000) return 'degraded';
    if (system?.cpu_percent > 70 || system?.memory_percent > 70) return 'warning';
    return 'healthy';
});
```

### 4.2 New File: `src/lib/components/admin/observability/SystemHealthPanel.svelte`

```svelte
<!--
  SystemHealthPanel - Real-time system health gauges
  
  Displays: CPU, Memory, Disk, Process stats
-->

<script lang="ts">
    import { metricsSnapshot, systemHealth } from '$lib/stores/metrics';
    
    $: system = $metricsSnapshot?.system;
    $: health = $systemHealth;
    
    function getHealthColor(status: string): string {
        switch (status) {
            case 'healthy': return '#00ff41';
            case 'warning': return '#ffc800';
            case 'degraded': return '#ff8c00';
            case 'critical': return '#ff0055';
            default: return '#666';
        }
    }
    
    function getGaugeColor(value: number): string {
        if (value > 90) return '#ff0055';
        if (value > 70) return '#ffc800';
        return '#00ff41';
    }
</script>

<div class="health-panel">
    <div class="panel-header">
        <h3>
            <span class="status-dot" style="background: {getHealthColor(health)}"></span>
            System Health
        </h3>
        <span class="status-text" style="color: {getHealthColor(health)}">
            {health.toUpperCase()}
        </span>
    </div>
    
    {#if system}
        <div class="gauges">
            <div class="gauge">
                <div class="gauge-label">CPU</div>
                <div class="gauge-bar">
                    <div 
                        class="gauge-fill" 
                        style="width: {system.cpu_percent}%; background: {getGaugeColor(system.cpu_percent)}"
                    ></div>
                </div>
                <div class="gauge-value">{system.cpu_percent.toFixed(1)}%</div>
            </div>
            
            <div class="gauge">
                <div class="gauge-label">Memory</div>
                <div class="gauge-bar">
                    <div 
                        class="gauge-fill" 
                        style="width: {system.memory_percent}%; background: {getGaugeColor(system.memory_percent)}"
                    ></div>
                </div>
                <div class="gauge-value">{system.memory_percent.toFixed(1)}%</div>
            </div>
            
            <div class="gauge">
                <div class="gauge-label">Disk</div>
                <div class="gauge-bar">
                    <div 
                        class="gauge-fill" 
                        style="width: {system.disk_percent}%; background: {getGaugeColor(system.disk_percent)}"
                    ></div>
                </div>
                <div class="gauge-value">{system.disk_percent.toFixed(1)}%</div>
            </div>
        </div>
        
        <div class="stats-row">
            <div class="stat">
                <span class="stat-value">{system.process_memory_mb.toFixed(0)}</span>
                <span class="stat-label">MB Process</span>
            </div>
            <div class="stat">
                <span class="stat-value">{system.process_threads}</span>
                <span class="stat-label">Threads</span>
            </div>
            <div class="stat">
                <span class="stat-value">{system.memory_used_gb.toFixed(1)}</span>
                <span class="stat-label">GB Used</span>
            </div>
        </div>
    {:else}
        <div class="loading">Loading system metrics...</div>
    {/if}
</div>

<style>
    .health-panel {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(0, 255, 65, 0.3);
        border-radius: 8px;
        padding: 16px;
    }
    
    .panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }
    
    .panel-header h3 {
        margin: 0;
        font-size: 14px;
        color: #00ff41;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    .status-text {
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 1px;
    }
    
    .gauges {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    
    .gauge {
        display: grid;
        grid-template-columns: 60px 1fr 50px;
        align-items: center;
        gap: 12px;
    }
    
    .gauge-label {
        font-size: 12px;
        color: #888;
    }
    
    .gauge-bar {
        height: 8px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 4px;
        overflow: hidden;
    }
    
    .gauge-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.3s ease;
    }
    
    .gauge-value {
        font-size: 12px;
        font-family: 'JetBrains Mono', monospace;
        color: #e0e0e0;
        text-align: right;
    }
    
    .stats-row {
        display: flex;
        justify-content: space-around;
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .stat {
        text-align: center;
    }
    
    .stat-value {
        display: block;
        font-size: 18px;
        font-weight: 600;
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .stat-label {
        font-size: 10px;
        color: #666;
        text-transform: uppercase;
    }
    
    .loading {
        color: #666;
        text-align: center;
        padding: 20px;
    }
</style>
```

### 4.3 New File: `src/lib/components/admin/observability/RagPerformancePanel.svelte`

```svelte
<!--
  RagPerformancePanel - RAG pipeline metrics
  
  Displays: Latency breakdown, cache rates, chunk stats
-->

<script lang="ts">
    import { metricsSnapshot } from '$lib/stores/metrics';
    
    $: rag = $metricsSnapshot?.rag;
    $: cache = $metricsSnapshot?.cache;
</script>

<div class="rag-panel">
    <div class="panel-header">
        <h3>🧠 RAG Pipeline</h3>
    </div>
    
    {#if rag && cache}
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{rag.latency_avg_ms.toFixed(0)}<span class="unit">ms</span></div>
                <div class="metric-label">Avg Latency</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-value">{rag.latency_p95_ms.toFixed(0)}<span class="unit">ms</span></div>
                <div class="metric-label">P95 Latency</div>
            </div>
            
            <div class="metric-card highlight">
                <div class="metric-value">{cache.rag_hit_rate.toFixed(0)}<span class="unit">%</span></div>
                <div class="metric-label">Cache Hit Rate</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-value">{rag.avg_chunks.toFixed(1)}</div>
                <div class="metric-label">Avg Chunks</div>
            </div>
        </div>
        
        <div class="breakdown">
            <div class="breakdown-title">Latency Breakdown</div>
            <div class="breakdown-bar">
                <div 
                    class="segment embedding" 
                    style="width: {(rag.embedding_avg_ms / rag.latency_avg_ms) * 100}%"
                    title="Embedding: {rag.embedding_avg_ms.toFixed(0)}ms"
                ></div>
                <div 
                    class="segment search" 
                    style="width: {(rag.search_avg_ms / rag.latency_avg_ms) * 100}%"
                    title="Search: {rag.search_avg_ms.toFixed(0)}ms"
                ></div>
            </div>
            <div class="breakdown-legend">
                <span class="legend-item"><span class="dot embedding"></span> Embedding</span>
                <span class="legend-item"><span class="dot search"></span> Vector Search</span>
            </div>
        </div>
        
        <div class="stats-footer">
            <span>Total Queries: <strong>{rag.total_queries.toLocaleString()}</strong></span>
            <span>Zero-Chunk: <strong>{rag.zero_chunk_rate.toFixed(1)}%</strong></span>
        </div>
    {:else}
        <div class="loading">Loading RAG metrics...</div>
    {/if}
</div>

<style>
    .rag-panel {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(0, 255, 255, 0.3);
        border-radius: 8px;
        padding: 16px;
    }
    
    .panel-header h3 {
        margin: 0 0 16px 0;
        font-size: 14px;
        color: #00ffff;
    }
    
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        margin-bottom: 16px;
    }
    
    .metric-card {
        background: rgba(0, 255, 255, 0.05);
        border-radius: 6px;
        padding: 12px;
        text-align: center;
    }
    
    .metric-card.highlight {
        background: rgba(0, 255, 65, 0.1);
        border: 1px solid rgba(0, 255, 65, 0.3);
    }
    
    .metric-value {
        font-size: 24px;
        font-weight: 600;
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .unit {
        font-size: 12px;
        color: #888;
        margin-left: 2px;
    }
    
    .metric-label {
        font-size: 11px;
        color: #888;
        margin-top: 4px;
    }
    
    .breakdown {
        margin-bottom: 16px;
    }
    
    .breakdown-title {
        font-size: 11px;
        color: #888;
        margin-bottom: 8px;
    }
    
    .breakdown-bar {
        height: 12px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        overflow: hidden;
        display: flex;
    }
    
    .segment {
        height: 100%;
        transition: width 0.3s ease;
    }
    
    .segment.embedding {
        background: #ff00ff;
    }
    
    .segment.search {
        background: #00ffff;
    }
    
    .breakdown-legend {
        display: flex;
        gap: 16px;
        margin-top: 8px;
        font-size: 10px;
        color: #888;
    }
    
    .legend-item {
        display: flex;
        align-items: center;
        gap: 4px;
    }
    
    .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }
    
    .dot.embedding {
        background: #ff00ff;
    }
    
    .dot.search {
        background: #00ffff;
    }
    
    .stats-footer {
        display: flex;
        justify-content: space-between;
        font-size: 11px;
        color: #666;
        padding-top: 12px;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .stats-footer strong {
        color: #e0e0e0;
    }
    
    .loading {
        color: #666;
        text-align: center;
        padding: 20px;
    }
</style>
```

### 4.4 New File: `src/lib/components/admin/observability/LlmCostPanel.svelte`

```svelte
<!--
  LlmCostPanel - LLM usage and cost tracking
-->

<script lang="ts">
    import { metricsSnapshot } from '$lib/stores/metrics';
    
    $: llm = $metricsSnapshot?.llm;
    
    function formatCost(usd: number): string {
        if (usd < 0.01) return `$${(usd * 100).toFixed(2)}¢`;
        return `$${usd.toFixed(2)}`;
    }
    
    function formatTokens(n: number): string {
        if (n > 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
        if (n > 1_000) return `${(n / 1_000).toFixed(1)}K`;
        return n.toString();
    }
</script>

<div class="llm-panel">
    <div class="panel-header">
        <h3>⚡ LLM Performance</h3>
        {#if llm}
            <span class="cost-badge">{formatCost(llm.cost_total_usd)}</span>
        {/if}
    </div>
    
    {#if llm}
        <div class="metrics-row">
            <div class="metric">
                <div class="metric-value">{llm.first_token_avg_ms.toFixed(0)}</div>
                <div class="metric-label">First Token (ms)</div>
            </div>
            <div class="metric">
                <div class="metric-value">{llm.latency_avg_ms.toFixed(0)}</div>
                <div class="metric-label">Avg Latency (ms)</div>
            </div>
            <div class="metric">
                <div class="metric-value">{llm.latency_p95_ms.toFixed(0)}</div>
                <div class="metric-label">P95 Latency (ms)</div>
            </div>
        </div>
        
        <div class="token-stats">
            <div class="token-row">
                <span class="token-label">Input Tokens</span>
                <span class="token-value">{formatTokens(llm.tokens_in_total)}</span>
            </div>
            <div class="token-row">
                <span class="token-label">Output Tokens</span>
                <span class="token-value">{formatTokens(llm.tokens_out_total)}</span>
            </div>
            <div class="token-row">
                <span class="token-label">Requests</span>
                <span class="token-value">{llm.total_requests.toLocaleString()}</span>
            </div>
            <div class="token-row error">
                <span class="token-label">Errors</span>
                <span class="token-value">{llm.error_count}</span>
            </div>
        </div>
    {:else}
        <div class="loading">Loading LLM metrics...</div>
    {/if}
</div>

<style>
    .llm-panel {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 200, 0, 0.3);
        border-radius: 8px;
        padding: 16px;
    }
    
    .panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }
    
    .panel-header h3 {
        margin: 0;
        font-size: 14px;
        color: #ffc800;
    }
    
    .cost-badge {
        background: rgba(0, 255, 65, 0.2);
        color: #00ff41;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .metrics-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 16px;
    }
    
    .metric {
        text-align: center;
        flex: 1;
    }
    
    .metric-value {
        font-size: 20px;
        font-weight: 600;
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .metric-label {
        font-size: 10px;
        color: #888;
        margin-top: 4px;
    }
    
    .token-stats {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding-top: 16px;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .token-row {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
    }
    
    .token-label {
        color: #888;
    }
    
    .token-value {
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .token-row.error .token-value {
        color: #ff4444;
    }
    
    .loading {
        color: #666;
        text-align: center;
        padding: 20px;
    }
</style>
```

### 4.5 New Route: `src/routes/admin/system/+page.svelte`

```svelte
<!--
  System Observability Dashboard
  
  Real-time system health, RAG performance, LLM costs
-->

<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { metricsStore, metricsConnected, metricsSnapshot, metricsHistory } from '$lib/stores/metrics';
    import SystemHealthPanel from '$lib/components/admin/observability/SystemHealthPanel.svelte';
    import RagPerformancePanel from '$lib/components/admin/observability/RagPerformancePanel.svelte';
    import LlmCostPanel from '$lib/components/admin/observability/LlmCostPanel.svelte';
    import LineChart from '$lib/components/admin/charts/LineChart.svelte';
    import StateMonitor from '$lib/components/nervecenter/StateMonitor.svelte';
    
    let showStateMonitor = false;
    
    onMount(() => {
        metricsStore.connect();
    });
    
    onDestroy(() => {
        metricsStore.disconnect();
    });
    
    $: uptime = $metricsSnapshot?.uptime_seconds || 0;
    $: wsStats = $metricsSnapshot?.websocket;
    
    function formatUptime(seconds: number): string {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        return `${h}h ${m}m`;
    }
</script>

<svelte:head>
    <title>System Health | CogTwin Admin</title>
</svelte:head>

<div class="observability-page">
    <header class="page-header">
        <div class="header-left">
            <h1>System Observability</h1>
            <div class="connection-status" class:connected={$metricsConnected}>
                <span class="status-dot"></span>
                {$metricsConnected ? 'Live' : 'Disconnected'}
            </div>
        </div>
        <div class="header-right">
            <span class="uptime">Uptime: {formatUptime(uptime)}</span>
            <button class="toggle-btn" on:click={() => showStateMonitor = !showStateMonitor}>
                {showStateMonitor ? 'Hide' : 'Show'} State Monitor
            </button>
        </div>
    </header>
    
    <div class="dashboard-grid">
        <!-- Row 1: Health + WebSocket -->
        <div class="grid-item span-2">
            <SystemHealthPanel />
        </div>
        
        <div class="grid-item">
            <div class="ws-panel">
                <h3>🔌 WebSocket</h3>
                {#if wsStats}
                    <div class="ws-stats">
                        <div class="ws-stat">
                            <span class="value">{wsStats.connections_active}</span>
                            <span class="label">Active</span>
                        </div>
                        <div class="ws-stat">
                            <span class="value">{wsStats.messages_in.toLocaleString()}</span>
                            <span class="label">Messages In</span>
                        </div>
                        <div class="ws-stat">
                            <span class="value">{wsStats.messages_out.toLocaleString()}</span>
                            <span class="label">Messages Out</span>
                        </div>
                    </div>
                {/if}
            </div>
        </div>
        
        <!-- Row 2: RAG + LLM -->
        <div class="grid-item span-2">
            <RagPerformancePanel />
        </div>
        
        <div class="grid-item">
            <LlmCostPanel />
        </div>
        
        <!-- Row 3: Charts -->
        <div class="grid-item span-3">
            <div class="chart-panel">
                <h3>📈 System Resources (Last 5 min)</h3>
                <LineChart 
                    labels={$metricsHistory.timestamps}
                    datasets={[
                        { label: 'CPU %', data: $metricsHistory.cpu, borderColor: '#ff0055' },
                        { label: 'Memory %', data: $metricsHistory.memory, borderColor: '#00ffff' },
                    ]}
                />
            </div>
        </div>
        
        <!-- Row 4: More Charts -->
        <div class="grid-item span-2">
            <div class="chart-panel">
                <h3>🧠 RAG Latency Trend</h3>
                <LineChart 
                    labels={$metricsHistory.timestamps}
                    datasets={[
                        { label: 'Latency (ms)', data: $metricsHistory.ragLatency, borderColor: '#00ff41' },
                    ]}
                />
            </div>
        </div>
        
        <div class="grid-item">
            <div class="chart-panel">
                <h3>💾 Cache Hit Rate</h3>
                <LineChart 
                    labels={$metricsHistory.timestamps}
                    datasets={[
                        { label: 'Hit Rate %', data: $metricsHistory.cacheHitRate, borderColor: '#ffc800' },
                    ]}
                />
            </div>
        </div>
    </div>
    
    {#if showStateMonitor}
        <div class="state-monitor-overlay">
            <StateMonitor />
        </div>
    {/if}
</div>

<style>
    .observability-page {
        padding: 24px;
        min-height: 100vh;
    }
    
    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
    }
    
    .header-left {
        display: flex;
        align-items: center;
        gap: 16px;
    }
    
    .page-header h1 {
        margin: 0;
        font-size: 24px;
        color: #e0e0e0;
    }
    
    .connection-status {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: #888;
    }
    
    .connection-status.connected {
        color: #00ff41;
    }
    
    .connection-status .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #888;
    }
    
    .connection-status.connected .status-dot {
        background: #00ff41;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    .header-right {
        display: flex;
        align-items: center;
        gap: 16px;
    }
    
    .uptime {
        font-size: 12px;
        color: #888;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .toggle-btn {
        padding: 8px 16px;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        color: #e0e0e0;
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .toggle-btn:hover {
        background: rgba(255, 255, 255, 0.15);
        border-color: #00ff41;
    }
    
    .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
    }
    
    .grid-item.span-2 {
        grid-column: span 2;
    }
    
    .grid-item.span-3 {
        grid-column: span 3;
    }
    
    .ws-panel, .chart-panel {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 16px;
        height: 100%;
    }
    
    .ws-panel h3, .chart-panel h3 {
        margin: 0 0 16px 0;
        font-size: 14px;
        color: #888;
    }
    
    .ws-stats {
        display: flex;
        justify-content: space-around;
    }
    
    .ws-stat {
        text-align: center;
    }
    
    .ws-stat .value {
        display: block;
        font-size: 24px;
        font-weight: 600;
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .ws-stat .label {
        font-size: 10px;
        color: #666;
        text-transform: uppercase;
    }
    
    .state-monitor-overlay {
        position: fixed;
        bottom: 24px;
        right: 24px;
        width: 400px;
        z-index: 1000;
    }
    
    @media (max-width: 1024px) {
        .dashboard-grid {
            grid-template-columns: 1fr;
        }
        
        .grid-item.span-2,
        .grid-item.span-3 {
            grid-column: span 1;
        }
    }
</style>
```

### 4.6 Update Admin Dropdown

Add new route to `AdminDropdown.svelte`:

```svelte
const adminLinks = [
    { href: '/admin', label: 'Nerve Center', icon: '⚡', superOnly: false },
    { href: '/admin/system', label: 'System Health', icon: '💻', superOnly: false },  // ADD THIS
    { href: '/admin/analytics', label: 'Analytics', icon: '📊', superOnly: false },
    { href: '/admin/users', label: 'User Management', icon: '👥', superOnly: false },
    { href: '/admin/audit', label: 'Audit Log', icon: '📋', superOnly: true },
];
```

---

## 5. ENVIRONMENT VARIABLES

### Backend (Railway)
```env
# No new env vars needed - uses existing AZURE_PG_* and REDIS_URL
```

### requirements.txt additions
```
psutil>=5.9.0
```

---

## 6. INTEGRATION CHECKLIST

### Backend
- [ ] Run database migration `007_observability_tables.sql`
- [ ] Create `core/metrics_collector.py`
- [ ] Create `auth/metrics_routes.py`
- [ ] Wire metrics router into `main.py`
- [ ] Enhance timing middleware to record metrics
- [ ] Instrument WebSocket connect/disconnect
- [ ] Instrument RAG pipeline in `enterprise_rag.py`
- [ ] Instrument LLM calls in `model_adapter.py`
- [ ] Add `psutil` to requirements.txt
- [ ] Test `/api/metrics/health` endpoint

### Frontend
- [ ] Create `src/lib/stores/metrics.ts`
- [ ] Create `src/lib/components/admin/observability/` directory
- [ ] Create `SystemHealthPanel.svelte`
- [ ] Create `RagPerformancePanel.svelte`
- [ ] Create `LlmCostPanel.svelte`
- [ ] Create `src/routes/admin/system/+page.svelte`
- [ ] Update `AdminDropdown.svelte` with new link
- [ ] Verify WebSocket streaming works

### Deployment
- [ ] Deploy backend first
- [ ] Verify `/api/metrics/health` returns 200
- [ ] Deploy frontend
- [ ] Test WebSocket connection to `/api/metrics/stream`
- [ ] Verify all panels show data

---

## 7. TESTING COMMANDS

```bash
# Backend health check
curl -X GET https://your-app.railway.app/api/metrics/health

# Full metrics snapshot
curl -X GET https://your-app.railway.app/api/metrics/snapshot \
  -H "X-User-Email: admin@yourcompany.com"

# WebSocket test (using wscat)
wscat -c wss://your-app.railway.app/api/metrics/stream

# Database verification
psql -c "SELECT COUNT(*) FROM enterprise.system_metrics;"
```

---

## 8. AGENT EXECUTION BLOCK

```
FEATURE BUILD: OBSERVABILITY_PHASE_1

TASK 1 - Database:
- Run migration: migrations/007_observability_tables.sql
- Verify: SELECT * FROM enterprise.system_metrics LIMIT 1;

TASK 2 - Backend Core:
- Create file: core/metrics_collector.py
- Create file: auth/metrics_routes.py

TASK 3 - Backend Wiring:
- Edit main.py: Add metrics router import and registration
- Edit main.py: Enhance timing middleware
- Edit main.py: Instrument WebSocket endpoint

TASK 4 - Backend Instrumentation:
- Edit core/enterprise_rag.py: Add timing instrumentation
- Edit core/model_adapter.py: Add LLM metrics recording

TASK 5 - Frontend Store:
- Create file: src/lib/stores/metrics.ts

TASK 6 - Frontend Components:
- Create directory: src/lib/components/admin/observability/
- Create file: SystemHealthPanel.svelte
- Create file: RagPerformancePanel.svelte
- Create file: LlmCostPanel.svelte

TASK 7 - Frontend Route:
- Create file: src/routes/admin/system/+page.svelte
- Edit: src/lib/components/ribbon/AdminDropdown.svelte

TASK 8 - Verify:
- Backend: curl /api/metrics/health
- Frontend: Navigate to /admin/system
- WebSocket: Check live data streaming

COMPLETION CRITERIA:
- All files created without errors
- /api/metrics/health returns 200
- /admin/system shows live metrics
- WebSocket streams data every 5s
```

---

## 9. ROLLBACK PLAN

```sql
-- Database rollback
DROP TABLE IF EXISTS enterprise.request_metrics;
DROP TABLE IF EXISTS enterprise.system_metrics;
DROP TABLE IF EXISTS enterprise.llm_call_metrics;
DROP TABLE IF EXISTS enterprise.rag_metrics;
DROP TABLE IF EXISTS enterprise.cache_metrics;
```

```bash
# Git rollback
git revert HEAD~N  # N = number of commits for this feature
```
