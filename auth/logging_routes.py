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
