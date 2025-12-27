-- ============================================================================
-- Migration: Observability Tables
-- Date: 2025-12-27
-- Description: Creates tables for tracing, structured logging, and alerting.
--              These are required by the observability routes:
--              - /api/observability/traces
--              - /api/observability/logs
--              - /api/observability/alerts
-- ============================================================================

-- Ensure enterprise schema exists
CREATE SCHEMA IF NOT EXISTS enterprise;

-- ============================================================================
-- TRACING TABLES
-- ============================================================================

-- Traces table - one row per request lifecycle
CREATE TABLE IF NOT EXISTS enterprise.traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(64) NOT NULL UNIQUE,
    entry_point VARCHAR(32) NOT NULL,  -- 'http' or 'websocket'
    endpoint VARCHAR(255),
    method VARCHAR(10),
    session_id VARCHAR(64),
    user_email VARCHAR(255),
    department VARCHAR(64),
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    duration_ms INTEGER,
    status VARCHAR(32) DEFAULT 'in_progress',  -- in_progress, completed, error
    error_message TEXT,
    tags JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trace spans table - operations within a trace
CREATE TABLE IF NOT EXISTS enterprise.trace_spans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(64) NOT NULL REFERENCES enterprise.traces(trace_id) ON DELETE CASCADE,
    span_id VARCHAR(32) NOT NULL,
    parent_span_id VARCHAR(32),
    operation_name VARCHAR(255) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    duration_ms INTEGER,
    status VARCHAR(32) DEFAULT 'in_progress',
    error_message TEXT,
    tags JSONB DEFAULT '{}',
    logs JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for trace queries
CREATE INDEX IF NOT EXISTS idx_traces_start_time ON enterprise.traces(start_time DESC);
CREATE INDEX IF NOT EXISTS idx_traces_status ON enterprise.traces(status);
CREATE INDEX IF NOT EXISTS idx_traces_user_email ON enterprise.traces(user_email) WHERE user_email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_traces_department ON enterprise.traces(department) WHERE department IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trace_spans_trace_id ON enterprise.trace_spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_trace_spans_operation ON enterprise.trace_spans(operation_name);

-- ============================================================================
-- STRUCTURED LOGGING TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS enterprise.structured_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level VARCHAR(20) NOT NULL,  -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    logger_name VARCHAR(255),
    message TEXT NOT NULL,
    trace_id VARCHAR(64),
    span_id VARCHAR(32),
    user_email VARCHAR(255),
    department VARCHAR(64),
    session_id VARCHAR(64),
    endpoint VARCHAR(255),
    extra JSONB DEFAULT '{}',
    exception_type VARCHAR(255),
    exception_message TEXT,
    exception_traceback TEXT
);

-- Indexes for log queries
CREATE INDEX IF NOT EXISTS idx_structured_logs_timestamp ON enterprise.structured_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_structured_logs_level ON enterprise.structured_logs(level);
CREATE INDEX IF NOT EXISTS idx_structured_logs_trace_id ON enterprise.structured_logs(trace_id) WHERE trace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_structured_logs_user_email ON enterprise.structured_logs(user_email) WHERE user_email IS NOT NULL;

-- Full-text search index on message
CREATE INDEX IF NOT EXISTS idx_structured_logs_message_fts ON enterprise.structured_logs
    USING GIN(to_tsvector('english', message));

-- ============================================================================
-- ALERTING TABLES
-- ============================================================================

-- Alert rules - threshold definitions
CREATE TABLE IF NOT EXISTS enterprise.alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    metric_type VARCHAR(64) NOT NULL,  -- error_count, rag_latency_p95, llm_cost_hourly, memory_percent, custom_sql
    condition VARCHAR(10) NOT NULL,  -- gt, gte, lt, lte, eq, neq
    threshold NUMERIC NOT NULL,
    window_minutes INTEGER DEFAULT 5,
    custom_sql TEXT,  -- For custom_sql metric type
    severity VARCHAR(20) DEFAULT 'warning',  -- info, warning, critical
    notification_channels TEXT[] DEFAULT ARRAY['slack'],  -- slack, email
    cooldown_minutes INTEGER DEFAULT 15,
    enabled BOOLEAN DEFAULT true,
    last_evaluated_at TIMESTAMPTZ,
    last_triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alert instances - fired alerts
CREATE TABLE IF NOT EXISTS enterprise.alert_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id UUID NOT NULL REFERENCES enterprise.alert_rules(id) ON DELETE CASCADE,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    status VARCHAR(32) DEFAULT 'firing',  -- firing, acknowledged, resolved
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMPTZ,
    metric_value NUMERIC NOT NULL,
    threshold_value NUMERIC NOT NULL,
    message TEXT,
    context JSONB DEFAULT '{}',
    notifications_sent JSONB DEFAULT '[]'
);

-- Indexes for alert queries
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON enterprise.alert_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_alert_instances_rule_id ON enterprise.alert_instances(rule_id);
CREATE INDEX IF NOT EXISTS idx_alert_instances_triggered_at ON enterprise.alert_instances(triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_instances_status ON enterprise.alert_instances(status);

-- ============================================================================
-- POSTGRESQL NOTIFY FOR REAL-TIME LOG STREAMING
-- ============================================================================

-- Function to notify on new log insertion
CREATE OR REPLACE FUNCTION enterprise.notify_new_log()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('new_log', json_build_object(
        'id', NEW.id,
        'timestamp', NEW.timestamp,
        'level', NEW.level,
        'logger_name', NEW.logger_name,
        'message', NEW.message,
        'trace_id', NEW.trace_id,
        'user_email', NEW.user_email,
        'extra', NEW.extra
    )::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for log notifications
DROP TRIGGER IF EXISTS trigger_new_log ON enterprise.structured_logs;
CREATE TRIGGER trigger_new_log
    AFTER INSERT ON enterprise.structured_logs
    FOR EACH ROW
    EXECUTE FUNCTION enterprise.notify_new_log();

-- ============================================================================
-- DEFAULT ALERT RULES
-- ============================================================================

INSERT INTO enterprise.alert_rules (name, description, metric_type, condition, threshold, window_minutes, severity, notification_channels)
VALUES
    ('High Error Rate', 'Triggers when error count exceeds threshold', 'error_count', 'gt', 10, 5, 'warning', ARRAY['slack']),
    ('High Memory Usage', 'Triggers when memory usage exceeds 90%', 'memory_percent', 'gt', 90, 1, 'critical', ARRAY['slack', 'email']),
    ('LLM Errors Spike', 'Triggers on LLM API errors', 'error_count', 'gt', 5, 5, 'warning', ARRAY['slack'])
ON CONFLICT DO NOTHING;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE enterprise.traces IS 'Distributed traces - one row per request lifecycle';
COMMENT ON TABLE enterprise.trace_spans IS 'Spans within traces - individual operations';
COMMENT ON TABLE enterprise.structured_logs IS 'Structured log entries with trace correlation';
COMMENT ON TABLE enterprise.alert_rules IS 'Alert rule definitions';
COMMENT ON TABLE enterprise.alert_instances IS 'Fired alert instances';

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- Run these to verify the migration succeeded:
--
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'enterprise'
-- AND table_name IN ('traces', 'trace_spans', 'structured_logs', 'alert_rules', 'alert_instances');
--
-- SELECT indexname FROM pg_indexes WHERE schemaname = 'enterprise';
-- ============================================================================
