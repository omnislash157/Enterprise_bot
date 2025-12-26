"""
Analytics API Routes - Dashboard data endpoints.

All endpoints require admin access (dept_head or super_user).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

analytics_router = APIRouter()

# =============================================================================
# DASHBOARD ENDPOINTS
# =============================================================================

@analytics_router.get("/overview")
def get_analytics_overview(
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 7 days
):
    """
    Get dashboard overview stats.
    Returns: active_users, total_queries, avg_response_time, error_rate
    """
    try:
        from .analytics_service import get_analytics_service
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
def get_queries_over_time(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get query counts grouped by hour.
    For the "Queries by Hour" chart.
    """
    try:
        from .analytics_service import get_analytics_service
        analytics = get_analytics_service()
        return {
            "period_hours": hours,
            "data": analytics.get_queries_by_hour(hours=hours)
        }
    except Exception as e:
        logger.error(f"Error fetching queries by hour: {e}")
        return {"period_hours": hours, "data": [], "error": str(e)}


@analytics_router.get("/categories")
def get_category_breakdown(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get query category breakdown.
    For the "Query Categories" pie/bar chart.
    """
    try:
        from .analytics_service import get_analytics_service
        analytics = get_analytics_service()
        return {
            "period_hours": hours,
            "data": analytics.get_category_breakdown(hours=hours)
        }
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        return {"period_hours": hours, "data": [], "error": str(e)}


@analytics_router.get("/departments")
def get_department_stats(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get per-department statistics.
    For the department heatmap/breakdown.
    """
    try:
        from .analytics_service import get_analytics_service
        analytics = get_analytics_service()
        return {
            "period_hours": hours,
            "data": analytics.get_department_stats(hours=hours)
        }
    except Exception as e:
        logger.error(f"Error fetching department stats: {e}")
        return {"period_hours": hours, "data": [], "error": str(e)}


@analytics_router.get("/errors")
def get_recent_errors(
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get recent error events.
    For the error log panel.
    """
    try:
        from .analytics_service import get_analytics_service
        analytics = get_analytics_service()
        return {
            "limit": limit,
            "data": analytics.get_recent_errors(limit=limit)
        }
    except Exception as e:
        logger.error(f"Error fetching recent errors: {e}")
        return {"limit": limit, "data": [], "error": str(e)}


@analytics_router.get("/users/{user_email}")
def get_user_activity(
    user_email: str,
    days: int = Query(7, ge=1, le=30),
):
    """
    Get activity stats for a specific user.
    For the user detail panel.
    """
    try:
        from .analytics_service import get_analytics_service
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
def get_realtime_sessions():
    """
    Get currently active sessions.
    For the "Active Now" widget.
    """
    try:
        from .analytics_service import get_analytics_service
        analytics = get_analytics_service()
        return {"sessions": analytics.get_realtime_sessions()}
    except Exception as e:
        logger.error(f"Error fetching realtime sessions: {e}")
        return {"sessions": [], "error": str(e)}


@analytics_router.get("/dashboard")
def get_full_dashboard(
    hours: int = Query(24, ge=1, le=168),
    include_errors: bool = Query(True),
    include_realtime: bool = Query(True),
):
    """
    Combined dashboard endpoint - all data in ONE request.

    SYNC function - FastAPI runs in threadpool, doesn't block event loop.
    Uses single DB connection for all queries via connection pool.
    """
    try:
        from .analytics_service import get_analytics_service
        analytics = get_analytics_service()

        data = analytics.get_dashboard_data(
            hours=hours,
            include_errors=include_errors,
            include_realtime=include_realtime
        )
        data["timestamp"] = datetime.utcnow().isoformat()

        return data
    except Exception as e:
        logger.error(f"Error fetching dashboard: {e}")
        return {
            "overview": {
                "active_users": 0,
                "total_queries": 0,
                "avg_response_time_ms": 0,
                "error_rate_percent": 0,
                "period_hours": hours
            },
            "queries_by_hour": [],
            "categories": [],
            "departments": [],
            "errors": [],
            "realtime": [],
            "period_hours": hours,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


# =============================================================================
# ENHANCED ANALYTICS ENDPOINTS (Query Heuristics Redesign)
# =============================================================================

@analytics_router.get("/department-usage-inferred")
def get_department_usage_inferred(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get department usage based on INFERRED content analysis,
    not dropdown selection.

    Uses heuristic analysis of query content to determine which
    department's knowledge base is actually being queried.

    Returns:
        List of department usage with:
        - department: inferred department name
        - query_count: number of queries
        - unique_users: unique users asking about this dept
        - avg_complexity: average complexity score (0-1)
        - avg_response_time_ms: average response time
    """
    try:
        from .analytics_service import get_analytics_service
        analytics = get_analytics_service()

        # TODO: Implement get_department_usage_by_content() in analytics_service.py
        # This requires Phase 1 completion (query_heuristics.py + DB migration)
        if hasattr(analytics, 'get_department_usage_by_content'):
            return {
                "period_hours": hours,
                "data": analytics.get_department_usage_by_content(hours=hours)
            }
        else:
            logger.warning("[ANALYTICS] get_department_usage_by_content not yet implemented")
            return {
                "period_hours": hours,
                "data": [],
                "note": "Phase 1 implementation required: query_heuristics.py and DB migration"
            }
    except Exception as e:
        logger.error(f"Error fetching inferred department usage: {e}")
        return {
            "period_hours": hours,
            "data": [],
            "error": str(e)
        }


@analytics_router.get("/query-intents")
def get_query_intents(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get breakdown of query intents.

    Intent types:
    - INFORMATION_SEEKING: "what is", "tell me about"
    - ACTION_ORIENTED: "how do i", "steps to"
    - DECISION_SUPPORT: "should i", "which option"
    - VERIFICATION: "is it correct", "confirm"

    Returns:
        List of intent breakdowns with:
        - intent: intent type
        - count: number of queries
        - complexity: average complexity score for this intent
    """
    try:
        from .analytics_service import get_analytics_service
        analytics = get_analytics_service()

        # TODO: Implement get_query_intent_breakdown() in analytics_service.py
        # This requires Phase 1 completion (query_heuristics.py + DB migration)
        if hasattr(analytics, 'get_query_intent_breakdown'):
            return {
                "period_hours": hours,
                "data": analytics.get_query_intent_breakdown(hours=hours)
            }
        else:
            logger.warning("[ANALYTICS] get_query_intent_breakdown not yet implemented")
            return {
                "period_hours": hours,
                "data": [],
                "note": "Phase 1 implementation required: query_heuristics.py and DB migration"
            }
    except Exception as e:
        logger.error(f"Error fetching query intents: {e}")
        return {
            "period_hours": hours,
            "data": [],
            "error": str(e)
        }


@analytics_router.get("/complexity-distribution")
def get_complexity_distribution(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get distribution of query complexity scores.

    Bins queries into complexity ranges:
    - Simple (0.0-0.3): Basic lookups
    - Medium (0.3-0.6): Standard questions
    - Complex (0.6-0.8): Multi-part queries
    - Very Complex (0.8-1.0): Deep reasoning required

    Returns:
        List of complexity bins with counts
    """
    try:
        from .analytics_service import get_analytics_service
        analytics = get_analytics_service()

        # TODO: Implement get_complexity_distribution() in analytics_service.py
        # This requires Phase 1 completion (query_heuristics.py + DB migration)
        if hasattr(analytics, 'get_complexity_distribution'):
            return {
                "period_hours": hours,
                "data": analytics.get_complexity_distribution(hours=hours)
            }
        else:
            logger.warning("[ANALYTICS] get_complexity_distribution not yet implemented")
            return {
                "period_hours": hours,
                "data": [],
                "note": "Phase 1 implementation required: query_heuristics.py and DB migration"
            }
    except Exception as e:
        logger.error(f"Error fetching complexity distribution: {e}")
        return {
            "period_hours": hours,
            "data": [],
            "error": str(e)
        }


@analytics_router.get("/temporal-patterns")
def get_temporal_patterns(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get temporal usage patterns.

    Analyzes:
    - Peak usage times per department
    - Emerging topics (sudden spikes in categories)
    - Query flow trends over time
    - Anomalies in usage patterns

    Returns:
        Dictionary with:
        - peak_hours: list of peak usage times by department
        - emerging_topics: categories with recent growth
        - trends: temporal trend data
        - anomalies: detected anomalies
    """
    try:
        from .analytics_service import get_analytics_service
        analytics = get_analytics_service()

        # TODO: Implement pattern_detector.detect_department_usage_trends()
        # This requires Phase 1 completion (QueryPatternDetector in query_heuristics.py)
        if hasattr(analytics, 'pattern_detector') and analytics.pattern_detector:
            return {
                "period_hours": hours,
                "data": analytics.pattern_detector.detect_department_usage_trends(hours=hours)
            }
        else:
            logger.warning("[ANALYTICS] pattern_detector not yet implemented")
            return {
                "period_hours": hours,
                "data": {
                    "peak_hours": [],
                    "emerging_topics": [],
                    "trends": [],
                    "anomalies": []
                },
                "note": "Phase 1 implementation required: QueryPatternDetector in query_heuristics.py"
            }
    except Exception as e:
        logger.error(f"Error fetching temporal patterns: {e}")
        return {
            "period_hours": hours,
            "data": {
                "peak_hours": [],
                "emerging_topics": [],
                "trends": [],
                "anomalies": []
            },
            "error": str(e)
        }


@analytics_router.get("/memory-graph-data")
def get_memory_graph_data(
    hours: int = Query(24, ge=1, le=168),
):
    """
    Combined endpoint for rotating memory graph (3D visualization).

    Returns all data needed for Nerve Center visualization:
    - categories: query category breakdown (existing)
    - departments: inferred department usage (new)
    - intents: query intent breakdown (new)
    - temporal_patterns: temporal trends (new)
    - overview: basic stats
    - urgency_distribution: temporal urgency breakdown (new)

    This is the primary data source for the 3D rotating memory graph
    in the admin Nerve Center dashboard.
    """
    try:
        from .analytics_service import get_analytics_service
        analytics = get_analytics_service()

        # Build response with both existing and new data
        response = {
            "period_hours": hours,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Existing data (always available)
        try:
            response["categories"] = analytics.get_category_breakdown(hours=hours)
            response["overview"] = analytics.get_overview_stats(hours=hours)
        except Exception as e:
            logger.error(f"Error fetching existing data for memory graph: {e}")
            response["categories"] = []
            response["overview"] = {
                "active_users": 0,
                "total_queries": 0,
                "avg_response_time_ms": 0,
                "error_rate_percent": 0
            }

        # New data (requires Phase 1 implementation)
        try:
            if hasattr(analytics, 'get_department_usage_by_content'):
                response["departments"] = analytics.get_department_usage_by_content(hours=hours)
            else:
                response["departments"] = []
                response["departments_note"] = "Phase 1 implementation required"
        except Exception as e:
            logger.error(f"Error fetching department usage: {e}")
            response["departments"] = []

        try:
            if hasattr(analytics, 'get_query_intent_breakdown'):
                response["intents"] = analytics.get_query_intent_breakdown(hours=hours)
            else:
                response["intents"] = []
                response["intents_note"] = "Phase 1 implementation required"
        except Exception as e:
            logger.error(f"Error fetching query intents: {e}")
            response["intents"] = []

        try:
            if hasattr(analytics, 'pattern_detector') and analytics.pattern_detector:
                response["temporal_patterns"] = analytics.pattern_detector.detect_department_usage_trends(hours=hours)
            else:
                response["temporal_patterns"] = {
                    "peak_hours": [],
                    "emerging_topics": [],
                    "trends": [],
                    "anomalies": []
                }
                response["temporal_patterns_note"] = "Phase 1 implementation required"
        except Exception as e:
            logger.error(f"Error fetching temporal patterns: {e}")
            response["temporal_patterns"] = {
                "peak_hours": [],
                "emerging_topics": [],
                "trends": [],
                "anomalies": []
            }

        try:
            if hasattr(analytics, 'get_temporal_urgency_distribution'):
                response["urgency_distribution"] = analytics.get_temporal_urgency_distribution(hours=hours)
            else:
                response["urgency_distribution"] = {}
                response["urgency_distribution_note"] = "Phase 1 implementation required"
        except Exception as e:
            logger.error(f"Error fetching urgency distribution: {e}")
            response["urgency_distribution"] = {}

        return response

    except Exception as e:
        logger.error(f"Error fetching memory graph data: {e}")
        return {
            "period_hours": hours,
            "timestamp": datetime.utcnow().isoformat(),
            "categories": [],
            "departments": [],
            "intents": [],
            "temporal_patterns": {
                "peak_hours": [],
                "emerging_topics": [],
                "trends": [],
                "anomalies": []
            },
            "overview": {
                "active_users": 0,
                "total_queries": 0,
                "avg_response_time_ms": 0,
                "error_rate_percent": 0
            },
            "urgency_distribution": {},
            "error": str(e)
        }
