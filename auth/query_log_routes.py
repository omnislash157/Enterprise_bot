"""
Query Log API Routes - User Query Viewer

Provides endpoints for viewing the query log - what users are asking the bot.
Priority feature: "Where can we see the questions?"

Mount at: /api/admin/queries
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

query_log_router = APIRouter()


@query_log_router.get("/")
async def list_queries(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    hours: int = Query(24, ge=1, le=168),
    department: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    min_response_time: Optional[float] = Query(None),
):
    """
    List query log entries with filters.
    
    Returns paginated list of user queries with their responses.
    """
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()

        # Build dynamic query
        query = """
            SELECT 
                id,
                session_id,
                user_email,
                department,
                inferred_department,
                query_text,
                response_text,
                response_time_ms,
                chunks_used,
                complexity_score,
                intent_type,
                urgency,
                query_category,
                trace_id,
                created_at
            FROM enterprise.query_log
            WHERE created_at > NOW() - INTERVAL '1 hour' * $1
        """
        params = [hours]
        param_idx = 2

        if department:
            query += f" AND (department = ${param_idx} OR inferred_department = ${param_idx})"
            params.append(department)
            param_idx += 1

        if user_email:
            query += f" AND user_email ILIKE ${param_idx}"
            params.append(f"%{user_email}%")
            param_idx += 1

        if search:
            query += f" AND (query_text ILIKE ${param_idx} OR response_text ILIKE ${param_idx})"
            params.append(f"%{search}%")
            param_idx += 1

        if min_response_time:
            query += f" AND response_time_ms >= ${param_idx}"
            params.append(min_response_time)
            param_idx += 1

        # Count total before pagination
        count_query = query.replace(
            "SELECT \n                id,", 
            "SELECT COUNT(*) as total FROM (SELECT id,"
        )
        count_query = f"SELECT COUNT(*) FROM ({query}) as subq"

        query += f" ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])

        async with pool.acquire() as conn:
            # Get total count for pagination
            total_result = await conn.fetchrow(f"""
                SELECT COUNT(*) as total
                FROM enterprise.query_log
                WHERE created_at > NOW() - INTERVAL '1 hour' * $1
            """, hours)
            total = total_result['total'] if total_result else 0

            # Get paginated results
            rows = await conn.fetch(query, *params)

        return {
            'queries': [dict(r) for r in rows],
            'total': total,
            'limit': limit,
            'offset': offset,
            'period_hours': hours,
        }

    except Exception as e:
        logger.error(f"[QueryLog] List queries error: {e}")
        return {'queries': [], 'total': 0, 'error': str(e)}


@query_log_router.get("/stats")
async def get_query_stats(hours: int = Query(24, ge=1, le=168)):
    """Get query log statistics summary."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_queries,
                    COUNT(DISTINCT user_email) as unique_users,
                    COUNT(DISTINCT department) as departments_used,
                    AVG(response_time_ms) as avg_response_time_ms,
                    AVG(complexity_score) as avg_complexity,
                    AVG(chunks_used) as avg_chunks_used
                FROM enterprise.query_log
                WHERE created_at > NOW() - INTERVAL '1 hour' * $1
            """, hours)

            # Top departments
            dept_stats = await conn.fetch("""
                SELECT 
                    COALESCE(inferred_department, department, 'unknown') as dept,
                    COUNT(*) as count
                FROM enterprise.query_log
                WHERE created_at > NOW() - INTERVAL '1 hour' * $1
                GROUP BY COALESCE(inferred_department, department, 'unknown')
                ORDER BY count DESC
                LIMIT 10
            """, hours)

            # Top intents
            intent_stats = await conn.fetch("""
                SELECT 
                    intent_type,
                    COUNT(*) as count
                FROM enterprise.query_log
                WHERE created_at > NOW() - INTERVAL '1 hour' * $1
                  AND intent_type IS NOT NULL
                GROUP BY intent_type
                ORDER BY count DESC
                LIMIT 10
            """, hours)

        return {
            'period_hours': hours,
            'total_queries': stats['total_queries'] or 0,
            'unique_users': stats['unique_users'] or 0,
            'departments_used': stats['departments_used'] or 0,
            'avg_response_time_ms': round(stats['avg_response_time_ms'] or 0, 1),
            'avg_complexity': round(stats['avg_complexity'] or 0, 2),
            'avg_chunks_used': round(stats['avg_chunks_used'] or 0, 1),
            'by_department': [{'department': r['dept'], 'count': r['count']} for r in dept_stats],
            'by_intent': [{'intent': r['intent_type'], 'count': r['count']} for r in intent_stats],
        }

    except Exception as e:
        logger.error(f"[QueryLog] Stats error: {e}")
        return {'error': str(e)}


@query_log_router.get("/{query_id}")
async def get_query_detail(query_id: str):
    """Get a single query log entry with full details."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            query = await conn.fetchrow("""
                SELECT * FROM enterprise.query_log WHERE id = $1
            """, query_id)

            if not query:
                raise HTTPException(status_code=404, detail="Query not found")

        return dict(query)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[QueryLog] Get query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@query_log_router.get("/export/csv")
async def export_queries_csv(
    hours: int = Query(24, ge=1, le=168),
    department: Optional[str] = Query(None),
):
    """Export query log as CSV."""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    try:
        from core.database import get_db_pool
        pool = await get_db_pool()

        query = """
            SELECT 
                created_at,
                user_email,
                COALESCE(inferred_department, department) as department,
                query_text,
                response_time_ms,
                complexity_score,
                intent_type,
                chunks_used
            FROM enterprise.query_log
            WHERE created_at > NOW() - INTERVAL '1 hour' * $1
        """
        params = [hours]

        if department:
            query += " AND (department = $2 OR inferred_department = $2)"
            params.append(department)

        query += " ORDER BY created_at DESC"

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Timestamp', 'User', 'Department', 'Query', 'Response Time (ms)', 'Complexity', 'Intent', 'Chunks Used'])

        for row in rows:
            writer.writerow([
                row['created_at'].isoformat() if row['created_at'] else '',
                row['user_email'] or '',
                row['department'] or '',
                (row['query_text'] or '')[:500],  # Truncate for CSV
                row['response_time_ms'] or '',
                row['complexity_score'] or '',
                row['intent_type'] or '',
                row['chunks_used'] or '',
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=query_log_{hours}h.csv"}
        )

    except Exception as e:
        logger.error(f"[QueryLog] Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))