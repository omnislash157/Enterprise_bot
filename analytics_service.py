"""
Analytics Service - Query logging, classification, and aggregation.

The fart detector - if they do it, we log it.

Usage:
    from analytics_service import get_analytics_service

    analytics = get_analytics_service()
    analytics.log_query(user_email, department, query_text, ...)
    analytics.log_event("login", user_email, ...)
"""

import re
import logging
import time
import functools
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from dataclasses import dataclass
import json

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)


def timed(func):
    """Decorator to log execution time of analytics queries."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"[PERF] {func.__name__}: {elapsed_ms:.1f}ms")
        return result
    return wrapper


# =============================================================================
# DATABASE CONFIG
# =============================================================================

DB_CONFIG = {
    "user": os.getenv("AZURE_PG_USER", "Mhartigan"),
    "password": os.getenv("AZURE_PG_PASSWORD"),
    "host": os.getenv("AZURE_PG_HOST", "enterprisebot.postgres.database.azure.com"),
    "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
    "sslmode": "require"
}

SCHEMA = "enterprise"

# =============================================================================
# QUERY CLASSIFICATION HEURISTICS
# =============================================================================

CATEGORY_PATTERNS = {
    "PROCEDURAL": [
        r"how do i", r"how to", r"where do i", r"what's the process",
        r"steps to", r"procedure for", r"what are the steps"
    ],
    "LOOKUP": [
        r"find", r"search", r"look up", r"what is the", r"where is",
        r"show me", r"get me", r"pull up"
    ],
    "TROUBLESHOOTING": [
        r"not working", r"error", r"problem", r"issue", r"broken",
        r"why is", r"why does", r"won't", r"can't", r"doesn't"
    ],
    "POLICY": [
        r"allowed", r"can i", r"policy", r"rule", r"permitted",
        r"approved", r"compliance", r"legal"
    ],
    "CONTACT": [
        r"who do i", r"contact", r"email", r"phone", r"reach",
        r"talk to", r"call", r"extension"
    ],
    "RETURNS": [
        r"return", r"credit", r"refund", r"damaged", r"wrong",
        r"rma", r"exchange"
    ],
    "INVENTORY": [
        r"stock", r"inventory", r"available", r"quantity", r"product",
        r"in stock", r"out of stock", r"how many"
    ],
    "SAFETY": [
        r"safety", r"hazard", r"emergency", r"injury", r"lockout",
        r"osha", r"ppe", r"accident"
    ],
    "SCHEDULE": [
        r"hours", r"shift", r"when", r"schedule", r"open", r"close",
        r"time", r"deadline"
    ],
    "ESCALATION": [
        r"supervisor", r"manager", r"escalate", r"urgent", r"emergency",
        r"help me", r"speak to"
    ],
}

FRUSTRATION_SIGNALS = [
    r"still don't", r"doesn't help", r"wrong", r"useless",
    r"stupid", r"frustrated", r"annoying", r"waste",
    r"already asked", r"again", r"same question"
]

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class QueryLog:
    id: str
    user_email: str
    department: str
    query_text: str
    query_category: Optional[str]
    response_time_ms: int
    created_at: datetime

@dataclass
class AnalyticsEvent:
    id: str
    event_type: str
    user_email: Optional[str]
    department: Optional[str]
    event_data: Optional[dict]
    created_at: datetime

@dataclass
class DailyStats:
    date: str
    department: Optional[str]
    total_queries: int
    unique_users: int
    total_sessions: int
    avg_response_time_ms: float
    error_count: int
    category_breakdown: Dict[str, int]

# =============================================================================
# ANALYTICS SERVICE
# =============================================================================

class AnalyticsService:
    """Analytics data collection and querying service."""

    def __init__(self):
        self._session_cache = {}  # session_id -> {last_query_time, query_count}

    @contextmanager
    def _get_connection(self):
        conn = psycopg2.connect(**DB_CONFIG)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _get_cursor(self, conn=None):
        if conn is None:
            with self._get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                try:
                    yield cur
                    conn.commit()
                finally:
                    cur.close()
        else:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cur
            finally:
                cur.close()

    # -------------------------------------------------------------------------
    # CLASSIFICATION
    # -------------------------------------------------------------------------

    def classify_query(self, query_text: str) -> tuple[str, List[str]]:
        """
        Classify query into category and extract keywords.
        Returns (category, keywords_list)
        """
        query_lower = query_text.lower()

        # Check each category
        for category, patterns in CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    # Extract keywords (nouns, basically)
                    words = re.findall(r'\b[a-z]{3,}\b', query_lower)
                    keywords = [w for w in words if w not in ['the', 'and', 'for', 'how', 'what', 'where', 'when', 'why', 'can', 'does', 'that', 'this', 'with']]
                    return category, keywords[:10]  # Cap at 10 keywords

        return "OTHER", []

    def detect_frustration(self, query_text: str) -> List[str]:
        """Detect frustration signals in query."""
        query_lower = query_text.lower()
        signals = []

        for pattern in FRUSTRATION_SIGNALS:
            if re.search(pattern, query_lower):
                signals.append(pattern)

        return signals

    def is_repeat_question(self, user_email: str, query_text: str, window_minutes: int = 10) -> tuple[bool, Optional[str]]:
        """
        Check if this is a repeat question from same user within window.
        Returns (is_repeat, original_query_id)
        """
        with self._get_cursor() as cur:
            cur.execute(f"""
                SELECT id, query_text
                FROM {SCHEMA}.query_log
                WHERE user_email = %s
                  AND created_at > NOW() - INTERVAL '{window_minutes} minutes'
                ORDER BY created_at DESC
                LIMIT 5
            """, (user_email,))

            recent = cur.fetchall()
            query_words = set(query_text.lower().split())

            for row in recent:
                prev_words = set(row['query_text'].lower().split())
                # Jaccard similarity > 0.5 = probably same question
                intersection = len(query_words & prev_words)
                union = len(query_words | prev_words)
                if union > 0 and intersection / union > 0.5:
                    return True, str(row['id'])

            return False, None

    # -------------------------------------------------------------------------
    # LOGGING
    # -------------------------------------------------------------------------

    def log_query(
        self,
        user_email: str,
        department: str,
        query_text: str,
        session_id: str,
        response_time_ms: int,
        response_length: int,
        tokens_input: int,
        tokens_output: int,
        model_used: str,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Log a query with classification.
        Returns the query_log ID.
        """
        # Classify
        category, keywords = self.classify_query(query_text)
        frustration = self.detect_frustration(query_text)
        is_repeat, repeat_of = self.is_repeat_question(user_email, query_text)

        # Session tracking
        session_data = self._session_cache.get(session_id, {"query_count": 0, "last_query_time": None})
        query_position = session_data["query_count"] + 1

        time_since_last = None
        if session_data["last_query_time"]:
            delta = datetime.utcnow() - session_data["last_query_time"]
            time_since_last = int(delta.total_seconds() * 1000)

        # Update session cache
        self._session_cache[session_id] = {
            "query_count": query_position,
            "last_query_time": datetime.utcnow()
        }

        with self._get_cursor() as cur:
            cur.execute(f"""
                INSERT INTO {SCHEMA}.query_log (
                    user_id, user_email, department, session_id,
                    query_text, query_length, query_word_count,
                    query_category, query_keywords,
                    frustration_signals, is_repeat_question, repeat_of_query_id,
                    response_time_ms, response_length, tokens_input, tokens_output, model_used,
                    query_position_in_session, time_since_last_query_ms
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s
                )
                RETURNING id
            """, (
                user_id, user_email, department, session_id,
                query_text, len(query_text), len(query_text.split()),
                category, keywords,
                frustration if frustration else None, is_repeat, repeat_of,
                response_time_ms, response_length, tokens_input, tokens_output, model_used,
                query_position, time_since_last
            ))

            result = cur.fetchone()
            query_id = str(result['id'])

            logger.info(f"[ANALYTICS] Query logged: {category} | {response_time_ms}ms | session={session_id}")
            return query_id

    def log_event(
        self,
        event_type: str,
        user_email: Optional[str] = None,
        department: Optional[str] = None,
        session_id: Optional[str] = None,
        event_data: Optional[dict] = None,
        user_id: Optional[str] = None,
        from_department: Optional[str] = None,
        to_department: Optional[str] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> str:
        """
        Log a non-query event (login, logout, dept_switch, error, etc.)
        Returns the event ID.
        """
        with self._get_cursor() as cur:
            cur.execute(f"""
                INSERT INTO {SCHEMA}.analytics_events (
                    event_type, user_id, user_email, department,
                    event_data, session_id,
                    from_department, to_department,
                    error_type, error_message
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s
                )
                RETURNING id
            """, (
                event_type, user_id, user_email, department,
                json.dumps(event_data) if event_data else None, session_id,
                from_department, to_department,
                error_type, error_message
            ))

            result = cur.fetchone()
            event_id = str(result['id'])

            logger.info(f"[ANALYTICS] Event logged: {event_type} | user={user_email}")
            return event_id

    # -------------------------------------------------------------------------
    # QUERIES FOR DASHBOARD
    # -------------------------------------------------------------------------

    @timed
    def get_overview_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get overview stats for dashboard."""
        with self._get_cursor() as cur:
            # Active users (queries in last hour)
            cur.execute(f"""
                SELECT COUNT(DISTINCT user_email) as active_users
                FROM {SCHEMA}.query_log
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """)
            active_users = cur.fetchone()['active_users']

            # Today's queries
            cur.execute(f"""
                SELECT COUNT(*) as total_queries
                FROM {SCHEMA}.query_log
                WHERE created_at > NOW() - INTERVAL '{hours} hours'
            """)
            total_queries = cur.fetchone()['total_queries']

            # Average response time
            cur.execute(f"""
                SELECT AVG(response_time_ms) as avg_response_time
                FROM {SCHEMA}.query_log
                WHERE created_at > NOW() - INTERVAL '{hours} hours'
            """)
            avg_response = cur.fetchone()['avg_response_time'] or 0

            # Error rate
            cur.execute(f"""
                SELECT
                    COUNT(*) FILTER (WHERE event_type = 'error') as errors,
                    COUNT(*) as total
                FROM {SCHEMA}.analytics_events
                WHERE created_at > NOW() - INTERVAL '{hours} hours'
            """)
            error_row = cur.fetchone()
            error_rate = (error_row['errors'] / error_row['total'] * 100) if error_row['total'] > 0 else 0

            return {
                "active_users": active_users,
                "total_queries": total_queries,
                "avg_response_time_ms": round(avg_response, 0),
                "error_rate_percent": round(error_rate, 2),
                "period_hours": hours
            }

    @timed
    def get_queries_by_hour(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get query counts grouped by hour."""
        with self._get_cursor() as cur:
            cur.execute(f"""
                SELECT
                    DATE_TRUNC('hour', created_at) as hour,
                    COUNT(*) as count
                FROM {SCHEMA}.query_log
                WHERE created_at > NOW() - INTERVAL '{hours} hours'
                GROUP BY DATE_TRUNC('hour', created_at)
                ORDER BY hour
            """)

            return [{"hour": str(row['hour']), "count": row['count']} for row in cur.fetchall()]

    @timed
    def get_category_breakdown(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get query category breakdown."""
        with self._get_cursor() as cur:
            cur.execute(f"""
                SELECT
                    query_category,
                    COUNT(*) as count
                FROM {SCHEMA}.query_log
                WHERE created_at > NOW() - INTERVAL '{hours} hours'
                GROUP BY query_category
                ORDER BY count DESC
            """)

            return [{"category": row['query_category'] or 'OTHER', "count": row['count']} for row in cur.fetchall()]

    @timed
    def get_department_stats(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get per-department statistics."""
        with self._get_cursor() as cur:
            cur.execute(f"""
                SELECT
                    department,
                    COUNT(*) as query_count,
                    COUNT(DISTINCT user_email) as unique_users,
                    AVG(response_time_ms) as avg_response_time
                FROM {SCHEMA}.query_log
                WHERE created_at > NOW() - INTERVAL '{hours} hours'
                GROUP BY department
                ORDER BY query_count DESC
            """)

            return [{
                "department": row['department'],
                "query_count": row['query_count'],
                "unique_users": row['unique_users'],
                "avg_response_time_ms": round(row['avg_response_time'] or 0, 0)
            } for row in cur.fetchall()]

    @timed
    def get_recent_errors(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent error events."""
        with self._get_cursor() as cur:
            cur.execute(f"""
                SELECT
                    id, event_type, user_email, department,
                    error_type, error_message, created_at
                FROM {SCHEMA}.analytics_events
                WHERE event_type = 'error'
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))

            return [{
                "id": str(row['id']),
                "user_email": row['user_email'],
                "department": row['department'],
                "error_type": row['error_type'],
                "error_message": row['error_message'],
                "created_at": str(row['created_at'])
            } for row in cur.fetchall()]

    def get_user_activity(self, user_email: str, days: int = 7) -> Dict[str, Any]:
        """Get activity stats for a specific user."""
        with self._get_cursor() as cur:
            cur.execute(f"""
                SELECT
                    COUNT(*) as total_queries,
                    COUNT(DISTINCT DATE(created_at)) as active_days,
                    AVG(response_time_ms) as avg_response_time,
                    MAX(created_at) as last_active
                FROM {SCHEMA}.query_log
                WHERE user_email = %s
                  AND created_at > NOW() - INTERVAL '{days} days'
            """, (user_email,))

            row = cur.fetchone()

            # Get category breakdown for this user
            cur.execute(f"""
                SELECT query_category, COUNT(*) as count
                FROM {SCHEMA}.query_log
                WHERE user_email = %s
                  AND created_at > NOW() - INTERVAL '{days} days'
                GROUP BY query_category
                ORDER BY count DESC
            """, (user_email,))

            categories = {r['query_category'] or 'OTHER': r['count'] for r in cur.fetchall()}

            return {
                "user_email": user_email,
                "total_queries": row['total_queries'],
                "active_days": row['active_days'],
                "avg_response_time_ms": round(row['avg_response_time'] or 0, 0),
                "last_active": str(row['last_active']) if row['last_active'] else None,
                "category_breakdown": categories
            }

    @timed
    def get_realtime_sessions(self) -> List[Dict[str, Any]]:
        """Get currently active sessions (activity in last 5 minutes)."""
        with self._get_cursor() as cur:
            cur.execute(f"""
                SELECT
                    session_id,
                    user_email,
                    department,
                    COUNT(*) as query_count,
                    MAX(created_at) as last_activity
                FROM {SCHEMA}.query_log
                WHERE created_at > NOW() - INTERVAL '5 minutes'
                GROUP BY session_id, user_email, department
                ORDER BY last_activity DESC
            """)

            return [{
                "session_id": row['session_id'],
                "user_email": row['user_email'],
                "department": row['department'],
                "query_count": row['query_count'],
                "last_activity": str(row['last_activity'])
            } for row in cur.fetchall()]


# =============================================================================
# SINGLETON
# =============================================================================

_analytics_service: Optional[AnalyticsService] = None

def get_analytics_service() -> AnalyticsService:
    """Get or create analytics service singleton."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service
