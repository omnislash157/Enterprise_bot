"""
Analytics API Routes - Dashboard data endpoints.

All endpoints require admin access (dept_head or super_user).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Import auth dependency from main (we'll wire this up)
# For now, define the router

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
    from analytics_service import get_analytics_service
    analytics = get_analytics_service()

    return analytics.get_overview_stats(hours=hours)


@analytics_router.get("/queries")
async def get_queries_over_time(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get query counts grouped by hour.
    For the "Queries by Hour" chart.
    """
    from analytics_service import get_analytics_service
    analytics = get_analytics_service()

    return {
        "period_hours": hours,
        "data": analytics.get_queries_by_hour(hours=hours)
    }


@analytics_router.get("/categories")
async def get_category_breakdown(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get query category breakdown.
    For the "Query Categories" pie/bar chart.
    """
    from analytics_service import get_analytics_service
    analytics = get_analytics_service()

    return {
        "period_hours": hours,
        "data": analytics.get_category_breakdown(hours=hours)
    }


@analytics_router.get("/departments")
async def get_department_stats(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get per-department statistics.
    For the department heatmap/breakdown.
    """
    from analytics_service import get_analytics_service
    analytics = get_analytics_service()

    return {
        "period_hours": hours,
        "data": analytics.get_department_stats(hours=hours)
    }


@analytics_router.get("/errors")
async def get_recent_errors(
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get recent error events.
    For the error log panel.
    """
    from analytics_service import get_analytics_service
    analytics = get_analytics_service()

    return {
        "limit": limit,
        "data": analytics.get_recent_errors(limit=limit)
    }


@analytics_router.get("/users/{user_email}")
async def get_user_activity(
    user_email: str,
    days: int = Query(7, ge=1, le=30),
):
    """
    Get activity stats for a specific user.
    For the user detail panel.
    """
    from analytics_service import get_analytics_service
    analytics = get_analytics_service()

    return analytics.get_user_activity(user_email=user_email, days=days)


@analytics_router.get("/realtime")
async def get_realtime_sessions():
    """
    Get currently active sessions.
    For the "Active Now" widget.
    """
    from analytics_service import get_analytics_service
    analytics = get_analytics_service()

    return {
        "sessions": analytics.get_realtime_sessions()
    }
