-- Analytics Performance Indexes
-- Run with a user that has CREATE INDEX permissions
--
-- Purpose: Speed up dashboard queries by 40%+
-- Run: psql -h enterprisebot.postgres.database.azure.com -U Mhartigan -d postgres -f migrations/add_analytics_indexes.sql

-- =============================================================================
-- QUERY LOG INDEXES
-- =============================================================================

-- Primary time-based index (most queries filter by created_at)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_query_log_created_at
ON enterprise.query_log (created_at DESC);

-- User lookup index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_query_log_user_email
ON enterprise.query_log (user_email);

-- Department filtering index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_query_log_department
ON enterprise.query_log (department);

-- Category aggregation index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_query_log_category
ON enterprise.query_log (query_category);

-- Composite index for dashboard queries (covers most common access patterns)
-- INCLUDE columns are stored in index but not used for sorting/filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_query_log_dashboard
ON enterprise.query_log (created_at DESC, department, query_category)
INCLUDE (user_email, response_time_ms, session_id);

-- =============================================================================
-- ANALYTICS EVENTS INDEXES
-- =============================================================================

-- Primary time-based index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analytics_events_created_at
ON enterprise.analytics_events (created_at DESC);

-- Event type filtering index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analytics_events_type
ON enterprise.analytics_events (event_type);

-- Partial index for error queries (only indexes error rows - very efficient)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analytics_events_errors
ON enterprise.analytics_events (created_at DESC)
WHERE event_type = 'error';

-- =============================================================================
-- REFRESH STATISTICS
-- =============================================================================

-- Update table statistics for query planner
ANALYZE enterprise.query_log;
ANALYZE enterprise.analytics_events;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

-- List created indexes
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'enterprise'
  AND tablename IN ('query_log', 'analytics_events')
ORDER BY tablename, indexname;
