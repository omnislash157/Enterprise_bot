-- =============================================================================
-- ALERTING SYSTEM TABLES
-- =============================================================================

-- Alert Rules: What conditions trigger alerts
CREATE TABLE IF NOT EXISTS enterprise.alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Rule definition
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Metric to watch
    metric_type VARCHAR(50) NOT NULL,  -- 'error_rate', 'latency_p95', 'llm_cost', 'cache_miss', 'custom_sql'

    -- Condition
    condition VARCHAR(20) NOT NULL,  -- 'gt', 'lt', 'gte', 'lte', 'eq', 'neq'
    threshold FLOAT NOT NULL,

    -- Evaluation
    window_minutes INTEGER DEFAULT 5,
    evaluation_interval_seconds INTEGER DEFAULT 60,

    -- For custom SQL alerts
    custom_sql TEXT,

    -- Notification
    severity VARCHAR(20) DEFAULT 'warning',  -- 'info', 'warning', 'critical'
    notification_channels JSONB DEFAULT '["slack"]',  -- ['slack', 'email']

    -- Cooldown (don't re-alert for this many minutes after firing)
    cooldown_minutes INTEGER DEFAULT 15,

    -- Status
    enabled BOOLEAN DEFAULT TRUE,
    last_evaluated_at TIMESTAMPTZ,
    last_triggered_at TIMESTAMPTZ,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(255),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alert_rules_enabled ON enterprise.alert_rules(enabled);
CREATE INDEX idx_alert_rules_metric ON enterprise.alert_rules(metric_type);

-- Alert Instances: Fired alerts
CREATE TABLE IF NOT EXISTS enterprise.alert_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id UUID NOT NULL REFERENCES enterprise.alert_rules(id) ON DELETE CASCADE,

    -- Alert details
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    -- Status
    status VARCHAR(20) DEFAULT 'firing',  -- 'firing', 'acknowledged', 'resolved'
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMPTZ,

    -- Context
    metric_value FLOAT,
    threshold_value FLOAT,
    message TEXT,
    context JSONB DEFAULT '{}',

    -- Notifications
    notifications_sent JSONB DEFAULT '[]'  -- [{channel, sent_at, success}, ...]
);

CREATE INDEX idx_alert_instances_rule ON enterprise.alert_instances(rule_id);
CREATE INDEX idx_alert_instances_status ON enterprise.alert_instances(status);
CREATE INDEX idx_alert_instances_triggered ON enterprise.alert_instances(triggered_at DESC);

-- Insert default alert rules
INSERT INTO enterprise.alert_rules (name, description, metric_type, condition, threshold, window_minutes, severity, notification_channels) VALUES
    ('High Error Rate', 'More than 10 errors in 5 minutes', 'error_count', 'gt', 10, 5, 'critical', '["slack"]'),
    ('Slow RAG Queries', 'RAG P95 latency above 3 seconds', 'rag_latency_p95', 'gt', 3000, 5, 'warning', '["slack"]'),
    ('LLM Cost Spike', 'LLM cost exceeds $10 in 1 hour', 'llm_cost_hourly', 'gt', 10, 60, 'warning', '["slack", "email"]'),
    ('Low Cache Hit Rate', 'Cache hit rate below 20%', 'cache_hit_rate', 'lt', 20, 15, 'info', '["slack"]'),
    ('High Memory Usage', 'Memory usage above 85%', 'memory_percent', 'gt', 85, 5, 'warning', '["slack"]')
ON CONFLICT DO NOTHING;
