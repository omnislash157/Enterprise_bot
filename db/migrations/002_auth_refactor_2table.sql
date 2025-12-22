-- ============================================================================
-- MIGRATION 002: Auth Refactor - 2-Table Schema
-- ============================================================================
-- Date: 2024-12-22
-- Purpose: Nuke complex schema, rebuild with ONLY tenants + users
-- 
-- BEFORE: 7 tables (tenants, departments, users, access_config, access_audit_log, documents, query_log)
-- AFTER:  2 tables (tenants, users with embedded arrays)
--
-- Changes:
-- - departments → users.department_access[] (array of slugs)
-- - access_config → users.department_access[] + users.dept_head_for[]
-- - access_audit_log → DELETED (not needed for MVP)
-- - documents → DELETED (RAG concern, not auth)
-- - query_log → DELETED (analytics concern, not auth)
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: NUKE OLD TABLES
-- ============================================================================

DROP TABLE IF EXISTS enterprise.access_audit_log CASCADE;
DROP TABLE IF EXISTS enterprise.access_config CASCADE;
DROP TABLE IF EXISTS enterprise.analytics_events CASCADE;
DROP TABLE IF EXISTS enterprise.documents CASCADE;
DROP TABLE IF EXISTS enterprise.query_log CASCADE;
DROP TABLE IF EXISTS enterprise.users CASCADE;
DROP TABLE IF EXISTS enterprise.departments CASCADE;
DROP TABLE IF EXISTS enterprise.tenants CASCADE;

-- ============================================================================
-- PHASE 2: CREATE CLEAN 2-TABLE SCHEMA
-- ============================================================================

-- TABLE 1: TENANTS (domain validation only)
CREATE TABLE enterprise.tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug varchar(50) UNIQUE NOT NULL,       -- 'driscoll'
    name varchar(255) NOT NULL,             -- 'Driscoll Foods'
    domain varchar(255) NOT NULL,           -- 'driscollfoods.com'
    created_at timestamptz DEFAULT now()
);

-- TABLE 2: USERS (everything about a person)
CREATE TABLE enterprise.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES enterprise.tenants(id) ON DELETE CASCADE,
    email varchar(255) UNIQUE NOT NULL,     -- SSO identity
    display_name varchar(255),              -- From Azure AD
    azure_oid varchar(255) UNIQUE,          -- Azure Object ID
    department_access varchar[] DEFAULT '{}',  -- ['sales','purchasing'] - can query these
    dept_head_for varchar[] DEFAULT '{}',      -- ['sales'] - can grant access to these
    is_super_user boolean DEFAULT false,       -- God mode
    is_active boolean DEFAULT true,            -- Account enabled?
    created_at timestamptz DEFAULT now(),
    last_login_at timestamptz
);

-- ============================================================================
-- PHASE 3: INDEXES
-- ============================================================================

CREATE INDEX idx_users_email ON enterprise.users(email);
CREATE INDEX idx_users_azure_oid ON enterprise.users(azure_oid);
CREATE INDEX idx_users_tenant_id ON enterprise.users(tenant_id);
CREATE INDEX idx_users_dept_access ON enterprise.users USING gin(department_access);
CREATE INDEX idx_users_dept_head ON enterprise.users USING gin(dept_head_for);
CREATE INDEX idx_users_active ON enterprise.users(is_active) WHERE is_active = true;

-- ============================================================================
-- PHASE 4: SEED DATA
-- ============================================================================

-- Insert Driscoll Foods tenant
INSERT INTO enterprise.tenants (slug, name, domain) 
VALUES ('driscoll', 'Driscoll Foods', 'driscollfoods.com')
ON CONFLICT (slug) DO NOTHING;

-- Insert Matt Hartigan as super user with full access
INSERT INTO enterprise.users (
    tenant_id, 
    email, 
    display_name, 
    department_access, 
    dept_head_for, 
    is_super_user,
    is_active
)
SELECT 
    id, 
    'mhartigan@driscollfoods.com', 
    'Matt Hartigan', 
    ARRAY['sales', 'purchasing', 'warehouse', 'credit', 'accounting', 'it'],
    ARRAY['sales', 'purchasing', 'warehouse', 'credit', 'accounting', 'it'],
    true,
    true
FROM enterprise.tenants 
WHERE slug = 'driscoll'
ON CONFLICT (email) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    department_access = EXCLUDED.department_access,
    dept_head_for = EXCLUDED.dept_head_for,
    is_super_user = EXCLUDED.is_super_user,
    is_active = EXCLUDED.is_active;

COMMIT;

-- ============================================================================
-- VALIDATION QUERIES (run these to verify)
-- ============================================================================

-- Check table structure
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_schema = 'enterprise' 
  AND table_name IN ('tenants', 'users')
ORDER BY table_name, ordinal_position;

-- Check indexes
SELECT 
    schemaname, 
    tablename, 
    indexname 
FROM pg_indexes 
WHERE schemaname = 'enterprise' 
  AND tablename IN ('tenants', 'users')
ORDER BY tablename, indexname;

-- Check seed data
SELECT 
    u.email,
    u.display_name,
    u.department_access,
    u.dept_head_for,
    u.is_super_user,
    t.slug as tenant_slug
FROM enterprise.users u
JOIN enterprise.tenants t ON u.tenant_id = t.id;

-- Test SSO lookup query (CRITICAL - must work for login)
SELECT 
    id,
    email,
    display_name,
    tenant_id,
    azure_oid,
    department_access,
    dept_head_for,
    is_super_user,
    is_active,
    created_at,
    last_login_at
FROM enterprise.users
WHERE azure_oid = '12345' OR email = 'mhartigan@driscollfoods.com';
