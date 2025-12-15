-- ============================================
-- CogTwin Multi-Tenant Auth Setup for Supabase
-- ============================================
-- Run this in your Supabase SQL Editor
-- 
-- This creates the tables needed for multi-tenant auth:
-- - tenants: Your customer organizations
-- - user_tenants: Links Supabase auth users to tenants
-- ============================================

-- 1. Tenants table (you may already have this)
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    data_source_type TEXT NOT NULL CHECK (data_source_type IN ('direct_sql', 'etl', 'api')),
    connection_config JSONB DEFAULT '{}',
    features JSONB DEFAULT '{}',
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 2. User-Tenant mapping table
CREATE TABLE IF NOT EXISTS user_tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user', 'readonly')),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, tenant_id)
);

-- 3. Row-Level Security
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_tenants ENABLE ROW LEVEL SECURITY;

-- Tenants: Users can only see tenants they belong to
CREATE POLICY "Users can view their tenants"
    ON tenants FOR SELECT
    USING (
        id IN (
            SELECT tenant_id FROM user_tenants 
            WHERE user_id = auth.uid()
        )
    );

-- User_tenants: Users can only see their own mappings
CREATE POLICY "Users can view their tenant mappings"
    ON user_tenants FOR SELECT
    USING (auth.uid() = user_id);

-- 4. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_tenants_user_id ON user_tenants(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tenants_tenant_id ON user_tenants(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);

-- 5. Updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- INITIAL DATA: Driscoll Foods (your first tenant)
-- ============================================

INSERT INTO tenants (name, slug, data_source_type, features)
VALUES (
    'Driscoll Foods',
    'driscoll',
    'direct_sql',
    '{
        "credit_pipeline": true,
        "memory_system": false,
        "3d_visualization": false,
        "chat_basic": true
    }'::jsonb
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    features = EXCLUDED.features;

-- ============================================
-- HELPER FUNCTION: Auto-assign users by email domain
-- ============================================
-- Call this after a user signs up to auto-assign them to a tenant
-- based on their email domain.

CREATE OR REPLACE FUNCTION assign_user_by_email_domain()
RETURNS TRIGGER AS $$
DECLARE
    v_tenant_id UUID;
    v_email_domain TEXT;
BEGIN
    -- Extract domain from email
    v_email_domain := split_part(NEW.email, '@', 2);
    
    -- Driscoll Foods employees
    IF v_email_domain = 'driscollfoods.com' THEN
        SELECT id INTO v_tenant_id FROM tenants WHERE slug = 'driscoll';
        IF v_tenant_id IS NOT NULL THEN
            INSERT INTO user_tenants (user_id, tenant_id, role)
            VALUES (NEW.id, v_tenant_id, 'user')
            ON CONFLICT DO NOTHING;
        END IF;
    END IF;
    
    -- Add more email domain rules here as you add tenants:
    -- IF v_email_domain = 'acmecorp.com' THEN
    --     SELECT id INTO v_tenant_id FROM tenants WHERE slug = 'acme';
    --     ...
    -- END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to auto-assign on user creation
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION assign_user_by_email_domain();

-- ============================================
-- ADMIN HELPER: Manually add user to tenant
-- ============================================
-- Use this to manually add users (e.g., for testing or non-domain users)

CREATE OR REPLACE FUNCTION admin_add_user_to_tenant(
    p_user_email TEXT,
    p_tenant_slug TEXT,
    p_role TEXT DEFAULT 'user'
)
RETURNS BOOLEAN AS $$
DECLARE
    v_user_id UUID;
    v_tenant_id UUID;
BEGIN
    -- Get user ID
    SELECT id INTO v_user_id FROM auth.users WHERE email = p_user_email;
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'User not found: %', p_user_email;
    END IF;
    
    -- Get tenant ID
    SELECT id INTO v_tenant_id FROM tenants WHERE slug = p_tenant_slug;
    IF v_tenant_id IS NULL THEN
        RAISE EXCEPTION 'Tenant not found: %', p_tenant_slug;
    END IF;
    
    -- Add mapping
    INSERT INTO user_tenants (user_id, tenant_id, role)
    VALUES (v_user_id, v_tenant_id, p_role)
    ON CONFLICT (user_id, tenant_id) 
    DO UPDATE SET role = p_role;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Usage:
-- SELECT admin_add_user_to_tenant('john@example.com', 'driscoll', 'admin');

-- ============================================
-- VIEW: Easy user/tenant lookup for debugging
-- ============================================

CREATE OR REPLACE VIEW v_user_tenant_summary AS
SELECT 
    u.email,
    t.name as tenant_name,
    t.slug as tenant_slug,
    ut.role,
    ut.created_at as joined_at
FROM user_tenants ut
JOIN auth.users u ON u.id = ut.user_id
JOIN tenants t ON t.id = ut.tenant_id
ORDER BY t.name, u.email;

-- Grant access to authenticated users (they'll only see their own rows due to RLS)
-- Actually, this view needs special handling for RLS. For admin use, query directly.

-- ============================================
-- ENV VARS NEEDED (add to .env and Railway/hosting)
-- ============================================
-- SUPABASE_URL=https://xxxxx.supabase.co
-- SUPABASE_KEY=eyJhbGciOiJIUzI1NiIs... (anon key)
-- SUPABASE_JWT_SECRET=your-jwt-secret (from Supabase dashboard -> Settings -> API -> JWT Secret)
--
-- For Driscoll direct SQL:
-- DRISCOLL_SQL_SERVER=your-server.database.windows.net
-- DRISCOLL_SQL_DATABASE=DFIData
-- DRISCOLL_SQL_USERNAME=cogtwin_reader
-- DRISCOLL_SQL_PASSWORD=xxxxx
