"""
Analytics API Routes - Dashboard data endpoints.

All endpoints require admin access (dept_head or super_user).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging

logger = logging.getLogger(__name__)

analytics_router = APIRouter()

# =============================================================================
# DASHBOARD ENDPOINTS
# =============================================================================

@analytics_router.get("/overview")
async def get_analytics_overview(
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 7 days
):
    """
    Get dashboard overview stats.
    Returns: active_users, total_queries, avg_response_time, error_rate
    """
    try:
        from analytics_service import get_analytics_service
        analytics = get_analytics_service()
        return analytics.get_overview_stats(hours=hours)
    except Exception as e:
        logger.error(f"Error fetching overview: {e}")
        return {
            "active_users": 0,
            "total_queries": 0,
            "avg_response_time_ms": 0,
            "error_rate_percent": 0,
            "period_hours": hours,
            "error": str(e)
        }


@analytics_router.get("/queries")
async def get_queries_over_time(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get query counts grouped by hour.
    For the "Queries by Hour" chart.
    """
    try:
        from analytics_service import get_analytics_service
        analytics = get_analytics_service()
        return {
            "period_hours": hours,
            "data": analytics.get_queries_by_hour(hours=hours)
        }
    except Exception as e:
        logger.error(f"Error fetching queries by hour: {e}")
        return {"period_hours": hours, "data": [], "error": str(e)}


@analytics_router.get("/categories")
async def get_category_breakdown(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get query category breakdown.
    For the "Query Categories" pie/bar chart.
    """
    try:
        from analytics_service import get_analytics_service
        analytics = get_analytics_service()
        return {
            "period_hours": hours,
            "data": analytics.get_category_breakdown(hours=hours)
        }
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        return {"period_hours": hours, "data": [], "error": str(e)}


@analytics_router.get("/departments")
async def get_department_stats(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get per-department statistics.
    For the department heatmap/breakdown.
    """
    try:
        from analytics_service import get_analytics_service
        analytics = get_analytics_service()
        return {
            "period_hours": hours,
            "data": analytics.get_department_stats(hours=hours)
        }
    except Exception as e:
        logger.error(f"Error fetching department stats: {e}")
        return {"period_hours": hours, "data": [], "error": str(e)}


@analytics_router.get("/errors")
async def get_recent_errors(
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get recent error events.
    For the error log panel.
    """
    try:
        from analytics_service import get_analytics_service
        analytics = get_analytics_service()
        return {
            "limit": limit,
            "data": analytics.get_recent_errors(limit=limit)
        }
    except Exception as e:
        logger.error(f"Error fetching recent errors: {e}")
        return {"limit": limit, "data": [], "error": str(e)}


@analytics_router.get("/users/{user_email}")
async def get_user_activity(
    user_email: str,
    days: int = Query(7, ge=1, le=30),
):
    """
    Get activity stats for a specific user.
    For the user detail panel.
    """
    try:
        from analytics_service import get_analytics_service
        analytics = get_analytics_service()
        return analytics.get_user_activity(user_email=user_email, days=days)
    except Exception as e:
        logger.error(f"Error fetching user activity: {e}")
        return {
            "user_email": user_email,
            "total_queries": 0,
            "active_days": 0,
            "avg_response_time_ms": 0,
            "last_active": None,
            "category_breakdown": {},
            "error": str(e)
        }


@analytics_router.get("/realtime")
async def get_realtime_sessions():
    """
    Get currently active sessions.
    For the "Active Now" widget.
    """
    try:
        from analytics_service import get_analytics_service
        analytics = get_analytics_service()
        return {"sessions": analytics.get_realtime_sessions()}
    except Exception as e:
        logger.error(f"Error fetching realtime sessions: {e}")
        return {"sessions": [], "error": str(e)}
