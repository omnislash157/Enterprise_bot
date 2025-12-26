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

        # RAG metrics - DISABLED (RAG removed, using context stuffing)
        # Kept for backwards compatibility but not actively used
        # self.rag_latency = RingBuffer(maxlen=500)
        # self.rag_embedding_latency = RingBuffer(maxlen=500)
        # self.rag_search_latency = RingBuffer(maxlen=500)
        # self.rag_chunks = RingBuffer(maxlen=500)
        # self.rag_total = 0
        # self.rag_zero_chunks = 0

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

    # def record_rag_query(
    #     self,
    #     total_ms: float,
    #     embedding_ms: float = 0,
    #     search_ms: float = 0,
    #     chunks: int = 0,
    #     cache_hit: bool = False,
    #     embedding_cache_hit: bool = False
    # ):
    #     """Record RAG pipeline metrics - DISABLED (RAG removed)."""
    #     with self._lock:
    #         self.rag_latency.append(total_ms)
    #         self.rag_embedding_latency.append(embedding_ms)
    #         self.rag_search_latency.append(search_ms)
    #         self.rag_chunks.append(chunks)
    #         self.rag_total += 1
    #
    #         if chunks == 0:
    #             self.rag_zero_chunks += 1
    #
    #         if cache_hit:
    #             self.cache_hits += 1
    #         else:
    #             self.cache_misses += 1
    #
    #         if embedding_cache_hit:
    #             self.embedding_cache_hits += 1
    #         else:
    #             self.embedding_cache_misses += 1

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

            # RAG metrics removed - using context stuffing instead
            # 'rag': {
            #     'total_queries': self.rag_total,
            #     'latency_avg_ms': round(self.rag_latency.avg(), 1),
            #     'latency_p95_ms': round(self.rag_latency.percentile(0.95), 1),
            #     'embedding_avg_ms': round(self.rag_embedding_latency.avg(), 1),
            #     'search_avg_ms': round(self.rag_search_latency.avg(), 1),
            #     'avg_chunks': round(self.rag_chunks.avg(), 1),
            #     'zero_chunk_rate': round(self.rag_zero_chunks / self.rag_total * 100, 1) if self.rag_total > 0 else 0,
            # },

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
