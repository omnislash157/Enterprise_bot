-- =============================================================================
-- OBSERVABILITY TABLES - Phase 1
-- Run: psql -f migrations/007_observability_tables.sql
-- =============================================================================

-- Table 1: Request-level metrics (enhanced from existing timing middleware)
CREATE TABLE IF NOT EXISTS enterprise.request_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    response_time_ms FLOAT NOT NULL,
    user_email VARCHAR(255),
    department VARCHAR(50),
    request_size_bytes INTEGER,
    response_size_bytes INTEGER,
    trace_id VARCHAR(32)
);

CREATE INDEX idx_request_metrics_ts ON enterprise.request_metrics(timestamp DESC);
CREATE INDEX idx_request_metrics_endpoint ON enterprise.request_metrics(endpoint);
CREATE INDEX idx_request_metrics_status ON enterprise.request_metrics(status_code);

-- Table 2: System metrics (CPU, memory, connections)
CREATE TABLE IF NOT EXISTS enterprise.system_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_type VARCHAR(50) NOT NULL,  -- 'cpu', 'memory', 'disk', 'connections'
    metric_name VARCHAR(100) NOT NULL,
    value FLOAT NOT NULL,
    unit VARCHAR(20),  -- 'percent', 'bytes', 'count', 'ms'
    tags JSONB DEFAULT '{}'
);

CREATE INDEX idx_system_metrics_ts ON enterprise.system_metrics(timestamp DESC);
CREATE INDEX idx_system_metrics_type ON enterprise.system_metrics(metric_type, metric_name);

-- Table 3: LLM call metrics (cost tracking)
CREATE TABLE IF NOT EXISTS enterprise.llm_call_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,  -- 'xai', 'anthropic'
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    elapsed_ms FLOAT NOT NULL,
    first_token_ms FLOAT,  -- Time to first token (streaming)
    user_email VARCHAR(255),
    department VARCHAR(50),
    query_category VARCHAR(50),
    trace_id VARCHAR(32),
    cost_usd DECIMAL(10, 6),
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT
);

CREATE INDEX idx_llm_metrics_ts ON enterprise.llm_call_metrics(timestamp DESC);
CREATE INDEX idx_llm_metrics_model ON enterprise.llm_call_metrics(model);
CREATE INDEX idx_llm_metrics_user ON enterprise.llm_call_metrics(user_email);
CREATE INDEX idx_llm_metrics_dept ON enterprise.llm_call_metrics(department);

-- Table 4: RAG pipeline metrics (per-query breakdown)
CREATE TABLE IF NOT EXISTS enterprise.rag_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trace_id VARCHAR(32),
    user_email VARCHAR(255),
    department VARCHAR(50),
    query_hash VARCHAR(64),
    -- Timing breakdown
    total_ms FLOAT NOT NULL,
    embedding_ms FLOAT,
    vector_search_ms FLOAT,
    rerank_ms FLOAT,
    -- Results
    chunks_retrieved INTEGER,
    chunks_used INTEGER,
    cache_hit BOOLEAN DEFAULT FALSE,
    embedding_cache_hit BOOLEAN DEFAULT FALSE,
    -- Quality signals
    top_score FLOAT,
    avg_score FLOAT,
    threshold_used FLOAT
);

CREATE INDEX idx_rag_metrics_ts ON enterprise.rag_metrics(timestamp DESC);
CREATE INDEX idx_rag_metrics_dept ON enterprise.rag_metrics(department);
CREATE INDEX idx_rag_metrics_cache ON enterprise.rag_metrics(cache_hit);

-- Table 5: Cache metrics (aggregated snapshots)
CREATE TABLE IF NOT EXISTS enterprise.cache_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cache_type VARCHAR(50) NOT NULL,  -- 'rag', 'embedding'
    hits INTEGER NOT NULL DEFAULT 0,
    misses INTEGER NOT NULL DEFAULT 0,
    hit_rate FLOAT,
    memory_used_bytes BIGINT,
    keys_count INTEGER
);

CREATE INDEX idx_cache_metrics_ts ON enterprise.cache_metrics(timestamp DESC);
CREATE INDEX idx_cache_metrics_type ON enterprise.cache_metrics(cache_type);

-- Cleanup: Auto-delete old metrics (retention policy)
-- Run this as a scheduled job or PostgreSQL cron
-- DELETE FROM enterprise.request_metrics WHERE timestamp < NOW() - INTERVAL '30 days';
-- DELETE FROM enterprise.system_metrics WHERE timestamp < NOW() - INTERVAL '7 days';
-- DELETE FROM enterprise.llm_call_metrics WHERE timestamp < NOW() - INTERVAL '90 days';
-- DELETE FROM enterprise.rag_metrics WHERE timestamp < NOW() - INTERVAL '30 days';
-- DELETE FROM enterprise.cache_metrics WHERE timestamp < NOW() - INTERVAL '7 days';
