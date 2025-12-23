-- Migration 004: Create audit_log table
-- Recreates deleted access_audit_log with enhanced schema

CREATE TABLE IF NOT EXISTS enterprise.audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action VARCHAR(100) NOT NULL,
    actor_email VARCHAR(255),
    actor_user_id UUID REFERENCES enterprise.users(id),
    target_email VARCHAR(255),
    target_user_id UUID REFERENCES enterprise.users(id),
    department_slug VARCHAR(50),
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    ip_address INET,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX idx_audit_action ON enterprise.audit_log(action);
CREATE INDEX idx_audit_actor ON enterprise.audit_log(actor_email);
CREATE INDEX idx_audit_target ON enterprise.audit_log(target_email);
CREATE INDEX idx_audit_department ON enterprise.audit_log(department_slug);
CREATE INDEX idx_audit_created ON enterprise.audit_log(created_at DESC);

-- Composite index for filtered + paginated queries
CREATE INDEX idx_audit_filter_combo ON enterprise.audit_log(action, department_slug, created_at DESC);

-- Comment for documentation
COMMENT ON TABLE enterprise.audit_log IS 'Audit trail for admin actions and data access - created 2024-12-23';
