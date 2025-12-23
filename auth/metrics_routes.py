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
