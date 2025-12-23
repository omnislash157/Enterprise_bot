-- =============================================================================
-- DISTRIBUTED TRACING TABLES
-- =============================================================================

-- Traces: One per request
CREATE TABLE IF NOT EXISTS enterprise.traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(32) NOT NULL UNIQUE,

    -- Request context
    entry_point VARCHAR(20) NOT NULL,  -- 'http', 'websocket'
    endpoint VARCHAR(255),
    method VARCHAR(10),
    session_id VARCHAR(64),
    user_email VARCHAR(255),
    department VARCHAR(50),

    -- Timing
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    duration_ms FLOAT,

    -- Status
    status VARCHAR(20) DEFAULT 'in_progress',  -- 'in_progress', 'completed', 'error'
    error_message TEXT,

    -- Metadata
    tags JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_traces_trace_id ON enterprise.traces(trace_id);
CREATE INDEX idx_traces_start_time ON enterprise.traces(start_time DESC);
CREATE INDEX idx_traces_user ON enterprise.traces(user_email);
CREATE INDEX idx_traces_status ON enterprise.traces(status);
CREATE INDEX idx_traces_session ON enterprise.traces(session_id);

-- Spans: Multiple per trace
CREATE TABLE IF NOT EXISTS enterprise.trace_spans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(32) NOT NULL,
    span_id VARCHAR(16) NOT NULL,
    parent_span_id VARCHAR(16),

    -- Operation
    operation_name VARCHAR(100) NOT NULL,
    service_name VARCHAR(50) DEFAULT 'enterprise_bot',

    -- Timing
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    duration_ms FLOAT,

    -- Status
    status VARCHAR(20) DEFAULT 'in_progress',
    error_message TEXT,

    -- Context
    tags JSONB DEFAULT '{}',
    logs JSONB DEFAULT '[]',  -- [{timestamp, message}, ...]

    CONSTRAINT fk_trace FOREIGN KEY (trace_id) REFERENCES enterprise.traces(trace_id) ON DELETE CASCADE
);

CREATE INDEX idx_spans_trace_id ON enterprise.trace_spans(trace_id);
CREATE INDEX idx_spans_operation ON enterprise.trace_spans(operation_name);
CREATE INDEX idx_spans_start_time ON enterprise.trace_spans(start_time DESC);
CREATE INDEX idx_spans_parent ON enterprise.trace_spans(parent_span_id);
