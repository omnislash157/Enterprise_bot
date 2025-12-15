-- ============================================
-- CogTwin 3-Tier Permission System - Complete Schema
-- ============================================
-- 
-- Tier 1: USER
--   - Sees only their department's content
--   - Data filtered by employee_id (sales rep sees only their customers)
--   - No admin access
--
-- Tier 2: DEPT_HEAD  
--   - Sees their department's content
--   - Sees ALL data in department (no employee filter)
--   - Can view users in their department
--
-- Tier 3: SUPER_USER
--   - Sees everything
--   - Full admin: add/remove users, assign dept heads
--   - Creator access
--
-- ============================================


-- ===========================================
-- 1. CORE TABLES
-- ===========================================

-- Tenants (customers/organizations)
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

-- Departments within tenants
CREATE TABLE IF NOT EXISTS tenant_departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, slug)
);

-- User-Tenant mapping with department and role
CREATE TABLE IF NOT EXISTS user_tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    department_id UUID REFERENCES tenant_departments(id) ON DELETE SET NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'readonly', 'dept_head', 'super_user')),
    employee_id TEXT,  -- For data filtering (e.g., 'JA' for sales rep Jafflerbach)
    permissions JSONB DEFAULT '{}',  -- Granular overrides
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, tenant_id)
);

-- Department content (manuals, context docs for AI)
CREATE TABLE IF NOT EXISTS department_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id UUID NOT NULL REFERENCES tenant_departments(id) ON DELETE CASCADE,
    content_type TEXT NOT NULL CHECK (content_type IN ('manual', 'prompt_context', 'faq', 'executive_summary')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    active BOOLEAN DEFAULT true,
    version INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);


-- ===========================================
-- 2. INDEXES
-- ===========================================

CREATE INDEX IF NOT EXISTS idx_user_tenants_user_id ON user_tenants(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tenants_tenant_id ON user_tenants(tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_tenants_department_id ON user_tenants(department_id);
CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);
CREATE INDEX IF NOT EXISTS idx_departments_tenant_slug ON tenant_departments(tenant_id, slug);
CREATE INDEX IF NOT EXISTS idx_dept_content_lookup ON department_content(department_id, content_type, active);


-- ===========================================
-- 3. ROW-LEVEL SECURITY
-- ===========================================

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE department_content ENABLE ROW LEVEL SECURITY;

-- Tenants: Users see only tenants they belong to
CREATE POLICY "Users view their tenants"
    ON tenants FOR SELECT
    USING (
        id IN (SELECT tenant_id FROM user_tenants WHERE user_id = auth.uid())
    );

-- Departments: Users see departments in their tenant
CREATE POLICY "Users view tenant departments"
    ON tenant_departments FOR SELECT
    USING (
        tenant_id IN (SELECT tenant_id FROM user_tenants WHERE user_id = auth.uid())
    );

-- User_tenants: Complex policy based on role
-- Users see their own mapping
-- Dept heads see all mappings in their department
-- Super users see all mappings in their tenant
CREATE POLICY "Users view tenant mappings"
    ON user_tenants FOR SELECT
    USING (
        -- Own mapping
        user_id = auth.uid()
        OR
        -- Super user sees all in tenant
        tenant_id IN (
            SELECT tenant_id FROM user_tenants 
            WHERE user_id = auth.uid() AND role = 'super_user'
        )
        OR
        -- Dept head sees their department
        department_id IN (
            SELECT department_id FROM user_tenants 
            WHERE user_id = auth.uid() AND role = 'dept_head'
        )
    );

-- Super users can insert/update/delete user_tenants
CREATE POLICY "Super users manage tenant users"
    ON user_tenants FOR ALL
    USING (
        tenant_id IN (
            SELECT tenant_id FROM user_tenants 
            WHERE user_id = auth.uid() AND role = 'super_user'
        )
    );

-- Department content: Users see content for their department (or all if super_user)
CREATE POLICY "Users view department content"
    ON department_content FOR SELECT
    USING (
        -- Own department
        department_id IN (
            SELECT department_id FROM user_tenants WHERE user_id = auth.uid()
        )
        OR
        -- Super user sees all content in their tenant
        department_id IN (
            SELECT td.id FROM tenant_departments td
            JOIN user_tenants ut ON ut.tenant_id = td.tenant_id
            WHERE ut.user_id = auth.uid() AND ut.role = 'super_user'
        )
    );


-- ===========================================
-- 4. TRIGGERS
-- ===========================================

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_tenants_updated_at
    BEFORE UPDATE ON user_tenants FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dept_content_updated_at
    BEFORE UPDATE ON department_content FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ===========================================
-- 5. HELPER FUNCTIONS
-- ===========================================

-- Get user by email (for admin functions)
CREATE OR REPLACE FUNCTION get_user_by_email(p_email TEXT)
RETURNS TABLE(id UUID, email TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT au.id, au.email::TEXT
    FROM auth.users au
    WHERE au.email = p_email;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ===========================================
-- 6. DRISCOLL FOODS SEED DATA
-- ===========================================

-- Insert Driscoll tenant
INSERT INTO tenants (name, slug, data_source_type, features)
VALUES (
    'Driscoll Foods',
    'driscoll',
    'direct_sql',
    '{
        "credit_lookup": true,
        "credit_pipeline": true,
        "chat_basic": true,
        "inventory_lookup": true,
        "customer_search": true,
        "vendor_lookup": true
    }'::jsonb
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    features = EXCLUDED.features;

-- Insert departments
WITH driscoll AS (SELECT id FROM tenants WHERE slug = 'driscoll')
INSERT INTO tenant_departments (tenant_id, slug, name, config)
SELECT 
    driscoll.id,
    v.slug,
    v.name,
    v.config::jsonb
FROM driscoll, (VALUES
    ('warehouse', 'Warehouse Operations', '{"ai_personality": "direct_and_efficient", "features": ["inventory_lookup"]}'),
    ('sales', 'Sales', '{"ai_personality": "helpful_and_professional", "features": ["credit_lookup", "customer_search"]}'),
    ('purchasing', 'Purchasing', '{"ai_personality": "analytical", "features": ["vendor_lookup"]}'),
    ('credit', 'Credit Department', '{"ai_personality": "professional_and_thorough", "features": ["credit_lookup", "credit_pipeline"]}'),
    ('transportation', 'Transportation', '{"ai_personality": "logistics_focused", "features": ["route_lookup"]}'),
    ('executive', 'Executive Team', '{"ai_personality": "strategic_overview", "features": ["all"]}')
) AS v(slug, name, config)
ON CONFLICT (tenant_id, slug) DO UPDATE SET
    name = EXCLUDED.name,
    config = EXCLUDED.config;


-- ===========================================
-- 7. SAMPLE CONTENT (Placeholder manuals)
-- ===========================================

-- Sales manual
WITH sales_dept AS (
    SELECT td.id 
    FROM tenant_departments td
    JOIN tenants t ON t.id = td.tenant_id
    WHERE t.slug = 'driscoll' AND td.slug = 'sales'
)
INSERT INTO department_content (department_id, content_type, title, content)
SELECT 
    sales_dept.id,
    'manual',
    'Driscoll Foods Sales Manual',
    '# Sales Department Manual

## Customer Credit Lookup
When a customer asks about their credit status:
1. Look up their account using the credit tool
2. Provide their current balance, credit limit, and terms
3. Note any holds or special conditions

## Pricing Inquiries
- Always verify pricing in the system before quoting
- Special pricing requires manager approval
- Volume discounts follow the standard tier structure

## Order Process
- Verify customer credit status before large orders
- Check inventory availability
- Confirm delivery schedule with transportation

## Your Territory
You can only view customers assigned to your sales rep code.
For customers outside your territory, escalate to your manager.'
FROM sales_dept
ON CONFLICT DO NOTHING;

-- Warehouse manual
WITH warehouse_dept AS (
    SELECT td.id 
    FROM tenant_departments td
    JOIN tenants t ON t.id = td.tenant_id
    WHERE t.slug = 'driscoll' AND td.slug = 'warehouse'
)
INSERT INTO department_content (department_id, content_type, title, content)
SELECT 
    warehouse_dept.id,
    'manual',
    'Driscoll Foods Warehouse Operations Manual',
    '# Warehouse Operations Manual

## Inventory Management
- FIFO rotation is mandatory for all perishables
- Temperature logs must be checked every 4 hours
- Report discrepancies immediately to supervisor

## Receiving
- Inspect all deliveries before signing
- Check temperatures on refrigerated items
- Match packing slips to PO

## Shipping
- Verify order accuracy before loading
- Check truck temperature before loading
- Document any substitutions

## Safety
- Forklift certification required for all operators
- PPE required in all work areas
- Report spills immediately'
FROM warehouse_dept
ON CONFLICT DO NOTHING;

-- Purchasing manual
WITH purchasing_dept AS (
    SELECT td.id 
    FROM tenant_departments td
    JOIN tenants t ON t.id = td.tenant_id
    WHERE t.slug = 'driscoll' AND td.slug = 'purchasing'
)
INSERT INTO department_content (department_id, content_type, title, content)
SELECT 
    purchasing_dept.id,
    'manual',
    'Driscoll Foods Purchasing Manual',
    '# Purchasing Department Manual

## Vendor Management
- All vendors must be approved before first order
- Annual vendor reviews required
- Maintain backup suppliers for critical items

## Purchase Orders
- Orders over $10,000 require manager approval
- Orders over $50,000 require executive approval
- Document all pricing negotiations

## Quality Standards
- Reject any items below spec
- Document all quality issues
- Track vendor performance metrics

## Payment Terms
- Standard terms: Net 30
- Early payment discounts when beneficial
- Coordinate with Credit on vendor credit issues'
FROM purchasing_dept
ON CONFLICT DO NOTHING;

-- Credit manual  
WITH credit_dept AS (
    SELECT td.id 
    FROM tenant_departments td
    JOIN tenants t ON t.id = td.tenant_id
    WHERE t.slug = 'driscoll' AND td.slug = 'credit'
)
INSERT INTO department_content (department_id, content_type, title, content)
SELECT 
    credit_dept.id,
    'manual',
    'Driscoll Foods Credit Department Manual',
    '# Credit Department Manual

## Credit Application Processing
1. Verify all application information
2. Run credit check through approved bureaus
3. Calculate recommended credit limit
4. Document decision rationale

## Credit Limits
- Starter accounts: $5,000 max
- Established accounts: Based on payment history and volume
- Review limits annually or upon request

## Collections Process
- 30 days: Friendly reminder
- 45 days: Formal notice
- 60 days: Account hold, escalate to management
- 90 days: Collections action

## Holds and Releases
- Document all hold reasons
- Manager approval required for hold release
- Notify sales rep of any holds on their accounts

## Payment Plans
- Requires manager approval
- Document all terms in writing
- Monitor compliance weekly'
FROM credit_dept
ON CONFLICT DO NOTHING;

-- Executive summary (for super users)
WITH exec_dept AS (
    SELECT td.id 
    FROM tenant_departments td
    JOIN tenants t ON t.id = td.tenant_id
    WHERE t.slug = 'driscoll' AND td.slug = 'executive'
)
INSERT INTO department_content (department_id, content_type, title, content)
SELECT 
    exec_dept.id,
    'executive_summary',
    'Driscoll Foods Executive Overview',
    '# Executive Overview

You have full access to all departments and data.

## Quick Links
- Credit: Review AR aging, approve holds/releases, set credit limits
- Sales: Territory performance, customer issues, pricing approvals
- Purchasing: Vendor negotiations, large order approvals
- Warehouse: Inventory levels, operational issues
- Transportation: Delivery performance, route optimization

## Escalation Matters
Items requiring your attention will be flagged in the system.

## Reporting
All department KPIs are available in the analytics dashboard.'
FROM exec_dept
ON CONFLICT DO NOTHING;


-- ===========================================
-- 8. SAMPLE USERS (Run after users sign up)
-- ===========================================
-- 
-- After users create accounts via Supabase Auth, run these to assign them:
--
-- -- Your account (super user)
-- SELECT admin_add_user_to_tenant('your_email@gmail.com', 'driscoll', 'executive', 'super_user', NULL);
--
-- -- Sales rep Jafflerbach (tier 1, filtered to JA customers)
-- SELECT admin_add_user_to_tenant('jafflerbach@driscollfoods.com', 'driscoll', 'sales', 'user', 'JA');
--
-- -- Sales manager (tier 2, sees all sales data)
-- SELECT admin_add_user_to_tenant('salesmanager@driscollfoods.com', 'driscoll', 'sales', 'dept_head', NULL);
--
-- -- Buyer (tier 1, purchasing only)
-- SELECT admin_add_user_to_tenant('buyer@driscollfoods.com', 'driscoll', 'purchasing', 'user', NULL);


-- ===========================================
-- 9. ADMIN FUNCTION: Add user to tenant
-- ===========================================

CREATE OR REPLACE FUNCTION admin_add_user_to_tenant(
    p_user_email TEXT,
    p_tenant_slug TEXT,
    p_department_slug TEXT,
    p_role TEXT DEFAULT 'user',
    p_employee_id TEXT DEFAULT NULL
)
RETURNS TEXT AS $$
DECLARE
    v_user_id UUID;
    v_tenant_id UUID;
    v_department_id UUID;
BEGIN
    -- Get user
    SELECT id INTO v_user_id FROM auth.users WHERE email = p_user_email;
    IF v_user_id IS NULL THEN
        RETURN 'ERROR: User not found - ' || p_user_email;
    END IF;
    
    -- Get tenant
    SELECT id INTO v_tenant_id FROM tenants WHERE slug = p_tenant_slug;
    IF v_tenant_id IS NULL THEN
        RETURN 'ERROR: Tenant not found - ' || p_tenant_slug;
    END IF;
    
    -- Get department
    SELECT id INTO v_department_id 
    FROM tenant_departments 
    WHERE tenant_id = v_tenant_id AND slug = p_department_slug;
    IF v_department_id IS NULL THEN
        RETURN 'ERROR: Department not found - ' || p_department_slug;
    END IF;
    
    -- Upsert user_tenant
    INSERT INTO user_tenants (user_id, tenant_id, department_id, role, employee_id)
    VALUES (v_user_id, v_tenant_id, v_department_id, p_role, p_employee_id)
    ON CONFLICT (user_id, tenant_id) 
    DO UPDATE SET 
        department_id = v_department_id,
        role = p_role,
        employee_id = p_employee_id,
        updated_at = now();
    
    RETURN 'SUCCESS: ' || p_user_email || ' added to ' || p_tenant_slug || '/' || p_department_slug || ' as ' || p_role;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ===========================================
-- 10. AUTO-ASSIGN BY EMAIL DOMAIN
-- ===========================================

CREATE OR REPLACE FUNCTION assign_user_by_email_domain()
RETURNS TRIGGER AS $$
DECLARE
    v_tenant_id UUID;
    v_department_id UUID;
    v_email_domain TEXT;
BEGIN
    v_email_domain := split_part(NEW.email, '@', 2);
    
    -- Driscoll Foods employees go to a default department
    IF v_email_domain = 'driscollfoods.com' THEN
        SELECT id INTO v_tenant_id FROM tenants WHERE slug = 'driscoll';
        
        -- Default to sales department (can be changed later)
        SELECT id INTO v_department_id 
        FROM tenant_departments 
        WHERE tenant_id = v_tenant_id AND slug = 'sales';
        
        IF v_tenant_id IS NOT NULL AND v_department_id IS NOT NULL THEN
            INSERT INTO user_tenants (user_id, tenant_id, department_id, role)
            VALUES (NEW.id, v_tenant_id, v_department_id, 'user')
            ON CONFLICT DO NOTHING;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger (drop if exists first to avoid conflicts)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION assign_user_by_email_domain();


-- ===========================================
-- DONE! 
-- ===========================================
-- 
-- Next steps:
-- 1. Run this SQL in Supabase SQL Editor
-- 2. Sign up your account through the app
-- 3. Run: SELECT admin_add_user_to_tenant('your@email.com', 'driscoll', 'executive', 'super_user', NULL);
-- 4. You now have full admin access
-- 5. Add other users as they sign up
--
-- ENV VARS NEEDED:
-- SUPABASE_URL=https://xxxxx.supabase.co
-- SUPABASE_KEY=eyJ... (anon key)
-- SUPABASE_JWT_SECRET=your-jwt-secret
-- DRISCOLL_SQL_SERVER=...
-- DRISCOLL_SQL_DATABASE=...
-- DRISCOLL_SQL_USERNAME=...
-- DRISCOLL_SQL_PASSWORD=...
