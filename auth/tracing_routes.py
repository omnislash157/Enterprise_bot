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
