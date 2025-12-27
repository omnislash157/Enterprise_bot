"""
Metrics Routes - System Health & Performance Endpoints

Provides real-time system metrics via:
- /api/metrics/snapshot - HTTP endpoint for on-demand metrics
- /api/metrics/health - Simple health check
- /api/metrics/stream - WebSocket for real-time streaming (5s interval)

Uses the centralized MetricsCollector singleton for all data.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Header, HTTPException
from typing import Optional, Set
from datetime import datetime
import asyncio
import logging

from core.metrics_collector import metrics_collector

logger = logging.getLogger(__name__)

metrics_router = APIRouter()

# Track active WebSocket connections for metrics streaming
_active_stream_connections: Set[WebSocket] = set()

# Metrics streaming interval (seconds)
STREAM_INTERVAL = 5


# =============================================================================
# HTTP ENDPOINTS
# =============================================================================

@metrics_router.get("/snapshot")
async def get_metrics_snapshot(
    x_user_email: Optional[str] = Header(None, alias="X-User-Email"),
):
    """
    Get current metrics snapshot.

    Returns system health, RAG performance, cache stats, LLM costs.
    """
    try:
        snapshot = metrics_collector.get_snapshot()
        return snapshot
    except Exception as e:
        logger.error(f"Error building metrics snapshot: {e}")
        raise HTTPException(500, f"Error collecting metrics: {str(e)}")


@metrics_router.get("/health")
async def health_check():
    """Simple health check endpoint."""
    try:
        health = metrics_collector.get_health()
        return health
    except Exception as e:
        logger.error(f"Error getting health: {e}")
        return {
            "status": "unknown",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
        }


# =============================================================================
# WEBSOCKET STREAMING
# =============================================================================

@metrics_router.websocket("/stream")
async def metrics_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time metrics streaming.

    Sends metrics_snapshot every STREAM_INTERVAL seconds.
    Message format: { "type": "metrics_snapshot", "data": {...} }
    """
    await websocket.accept()
    _active_stream_connections.add(websocket)
    logger.info(f"[Metrics WS] Client connected. Total: {len(_active_stream_connections)}")

    try:
        while True:
            # Get snapshot from centralized collector
            snapshot = metrics_collector.get_snapshot()
            await websocket.send_json({
                "type": "metrics_snapshot",
                "data": snapshot
            })

            # Wait before next update
            await asyncio.sleep(STREAM_INTERVAL)

    except WebSocketDisconnect:
        logger.info("[Metrics WS] Client disconnected normally")
    except Exception as e:
        logger.error(f"[Metrics WS] Error: {e}")
    finally:
        _active_stream_connections.discard(websocket)
        logger.info(f"[Metrics WS] Client removed. Remaining: {len(_active_stream_connections)}")


# =============================================================================
# BROADCAST UTILITY (for external triggers)
# =============================================================================

async def broadcast_metrics():
    """Broadcast current metrics to all connected clients."""
    if not _active_stream_connections:
        return

    snapshot = metrics_collector.get_snapshot()
    message = {"type": "metrics_snapshot", "data": snapshot}

    disconnected = set()
    for ws in _active_stream_connections:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.add(ws)

    # Clean up disconnected clients
    for ws in disconnected:
        _active_stream_connections.discard(ws)
