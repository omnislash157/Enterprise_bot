-- =============================================================================
-- STRUCTURED LOGGING TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS enterprise.structured_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Log metadata
    level VARCHAR(10) NOT NULL,  -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    logger_name VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,

    -- Trace correlation
    trace_id VARCHAR(32),
    span_id VARCHAR(16),

    -- Request context
    user_email VARCHAR(255),
    department VARCHAR(50),
    session_id VARCHAR(64),
    endpoint VARCHAR(255),

    -- Extra data
    extra JSONB DEFAULT '{}',

    -- Exception info
    exception_type VARCHAR(255),
    exception_message TEXT,
    exception_traceback TEXT
);

CREATE INDEX idx_logs_timestamp ON enterprise.structured_logs(timestamp DESC);
CREATE INDEX idx_logs_level ON enterprise.structured_logs(level);
CREATE INDEX idx_logs_trace_id ON enterprise.structured_logs(trace_id);
CREATE INDEX idx_logs_logger ON enterprise.structured_logs(logger_name);
CREATE INDEX idx_logs_user ON enterprise.structured_logs(user_email);

-- Full-text search on message
CREATE INDEX idx_logs_message_search ON enterprise.structured_logs USING gin(to_tsvector('english', message));

-- Notify trigger for real-time streaming
CREATE OR REPLACE FUNCTION notify_new_log() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('new_log', json_build_object(
        'id', NEW.id,
        'timestamp', NEW.timestamp,
        'level', NEW.level,
        'logger_name', NEW.logger_name,
        'message', NEW.message,
        'trace_id', NEW.trace_id
    )::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_inserted
    AFTER INSERT ON enterprise.structured_logs
    FOR EACH ROW EXECUTE FUNCTION notify_new_log();
