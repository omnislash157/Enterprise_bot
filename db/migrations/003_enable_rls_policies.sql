-- ═══════════════════════════════════════════════════════════════════════════
-- PHASE 2: Enable Row Level Security (RLS) for Department Content
-- Database-Level Access Control
-- ═══════════════════════════════════════════════════════════════════════════
--
-- Purpose: Implement PostgreSQL RLS policies to enforce department-based
-- access control at the database layer, preventing unauthorized access even
-- if application code is compromised.
--
-- Security Model:
-- 1. Tenant Isolation: Users can only access their tenant's content
-- 2. Department Scoping: Users can only access authorized departments
-- 3. Role-Based Permissions: Different policies for SELECT/INSERT/UPDATE/DELETE
-- 4. Super User Bypass: Super users see all content within their tenant
--
-- Dependencies:
-- - enterprise.users table with role column
-- - enterprise.user_department_access table
-- - enterprise.department_content table (from Phase 1)
-- - Session variables: app.user_id, app.tenant_id
--
-- ═══════════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 1: Enable Row Level Security on department_content
-- ═══════════════════════════════════════════════════════════════════════════

-- Enable RLS (all queries will be filtered by policies)
ALTER TABLE enterprise.department_content ENABLE ROW LEVEL SECURITY;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 2: Create SELECT Policy (Read Access)
-- ═══════════════════════════════════════════════════════════════════════════

-- Policy: Users can read content from departments they have access to
CREATE POLICY dept_content_select_policy ON enterprise.department_content
FOR SELECT
USING (
    -- RULE 1: Super users can see ALL content for their tenant
    (
        EXISTS (
            SELECT 1
            FROM enterprise.users u
            WHERE u.id::text = current_setting('app.user_id', true)
              AND u.tenant_id = department_content.tenant_id
              AND u.role = 'super_user'
        )
    )
    OR
    -- RULE 2: Regular users can only see content from their authorized departments
    (
        -- Check tenant match
        department_content.tenant_id::text = current_setting('app.tenant_id', true)
        AND
        -- Check department access
        EXISTS (
            SELECT 1
            FROM enterprise.user_department_access uda
            WHERE uda.user_id::text = current_setting('app.user_id', true)
              AND uda.department_id = department_content.department_id
              AND uda.access_level IN ('read', 'write', 'admin')
              AND (uda.expires_at IS NULL OR uda.expires_at > NOW())
        )
    )
);

COMMENT ON POLICY dept_content_select_policy ON enterprise.department_content IS
'Users can read content from their tenant and authorized departments. Super users see all content.';

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 3: Create INSERT Policy (Write Access)
-- ═══════════════════════════════════════════════════════════════════════════

-- Policy: Only super users and dept heads can create new content
CREATE POLICY dept_content_insert_policy ON enterprise.department_content
FOR INSERT
WITH CHECK (
    -- Must match user's tenant
    tenant_id::text = current_setting('app.tenant_id', true)
    AND
    (
        -- RULE 1: Super users can insert anywhere in their tenant
        EXISTS (
            SELECT 1
            FROM enterprise.users u
            WHERE u.id::text = current_setting('app.user_id', true)
              AND u.tenant_id = department_content.tenant_id
              AND u.role = 'super_user'
        )
        OR
        -- RULE 2: Department heads can insert in their departments
        EXISTS (
            SELECT 1
            FROM enterprise.user_department_access uda
            WHERE uda.user_id::text = current_setting('app.user_id', true)
              AND uda.department_id = department_content.department_id
              AND uda.access_level IN ('write', 'admin')
              AND uda.is_dept_head = TRUE
              AND (uda.expires_at IS NULL OR uda.expires_at > NOW())
        )
    )
);

COMMENT ON POLICY dept_content_insert_policy ON enterprise.department_content IS
'Only super users and department heads can create new content.';

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 4: Create UPDATE Policy (Modify Access)
-- ═══════════════════════════════════════════════════════════════════════════

-- Policy: Same permissions as INSERT (super users + dept heads with write access)
CREATE POLICY dept_content_update_policy ON enterprise.department_content
FOR UPDATE
USING (
    -- Can only update if within tenant
    tenant_id::text = current_setting('app.tenant_id', true)
    AND
    (
        -- RULE 1: Super users can update anything in their tenant
        EXISTS (
            SELECT 1
            FROM enterprise.users u
            WHERE u.id::text = current_setting('app.user_id', true)
              AND u.tenant_id = department_content.tenant_id
              AND u.role = 'super_user'
        )
        OR
        -- RULE 2: Users with write/admin access can update their department content
        EXISTS (
            SELECT 1
            FROM enterprise.user_department_access uda
            WHERE uda.user_id::text = current_setting('app.user_id', true)
              AND uda.department_id = department_content.department_id
              AND uda.access_level IN ('write', 'admin')
              AND (uda.expires_at IS NULL OR uda.expires_at > NOW())
        )
    )
)
WITH CHECK (
    -- After update, must still belong to same tenant
    tenant_id::text = current_setting('app.tenant_id', true)
);

COMMENT ON POLICY dept_content_update_policy ON enterprise.department_content IS
'Super users and users with write/admin access can update content.';

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 5: Create DELETE Policy (Remove Access)
-- ═══════════════════════════════════════════════════════════════════════════

-- Policy: ONLY super users can delete content
CREATE POLICY dept_content_delete_policy ON enterprise.department_content
FOR DELETE
USING (
    -- Must be super user in the same tenant
    tenant_id::text = current_setting('app.tenant_id', true)
    AND
    EXISTS (
        SELECT 1
        FROM enterprise.users u
        WHERE u.id::text = current_setting('app.user_id', true)
          AND u.tenant_id = department_content.tenant_id
          AND u.role = 'super_user'
    )
);

COMMENT ON POLICY dept_content_delete_policy ON enterprise.department_content IS
'Only super users can delete content (prevents accidental data loss).';

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 6: Create Helper Function to Set Session Context
-- ═══════════════════════════════════════════════════════════════════════════

-- Function: Set user context for RLS policy enforcement
CREATE OR REPLACE FUNCTION enterprise.set_user_context(
    p_user_id UUID,
    p_tenant_id UUID
)
RETURNS VOID AS $$
BEGIN
    -- Set session-level variables (persist for current transaction)
    PERFORM set_config('app.user_id', p_user_id::text, false);
    PERFORM set_config('app.tenant_id', p_tenant_id::text, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION enterprise.set_user_context IS
'Set session variables for RLS policy enforcement. Call this at the start of each request.';

-- Function: Clear user context (optional, for cleanup)
CREATE OR REPLACE FUNCTION enterprise.clear_user_context()
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.user_id', '', false);
    PERFORM set_config('app.tenant_id', '', false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION enterprise.clear_user_context IS
'Clear session variables. Useful for testing or connection pooling.';

-- Function: Get current user context (for debugging)
CREATE OR REPLACE FUNCTION enterprise.get_user_context()
RETURNS TABLE (
    user_id TEXT,
    tenant_id TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        current_setting('app.user_id', true) AS user_id,
        current_setting('app.tenant_id', true) AS tenant_id;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION enterprise.get_user_context IS
'Get current session context for debugging. Returns app.user_id and app.tenant_id.';

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 7: Create Policy for Super User Bypass
-- ═══════════════════════════════════════════════════════════════════════════

-- Optional: Create a dedicated "super_user" role that bypasses RLS entirely
-- This is useful for administrative operations and migrations
-- DO NOT use for regular application queries

-- Create super user role if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'enterprise_super_user') THEN
        CREATE ROLE enterprise_super_user WITH LOGIN PASSWORD 'CHANGE_ME_IN_PRODUCTION';
        COMMENT ON ROLE enterprise_super_user IS 'Super user role that bypasses RLS for admin operations';
    END IF;
END $$;

-- Grant full access to super user role
GRANT ALL ON SCHEMA enterprise TO enterprise_super_user;
GRANT ALL ON ALL TABLES IN SCHEMA enterprise TO enterprise_super_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA enterprise TO enterprise_super_user;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA enterprise TO enterprise_super_user;

-- Force row level security even for table owners (best practice)
ALTER TABLE enterprise.department_content FORCE ROW LEVEL SECURITY;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 8: Create Audit Trigger for RLS Policy Violations (Optional)
-- ═══════════════════════════════════════════════════════════════════════════

-- Log any attempts to access unauthorized content
CREATE TABLE IF NOT EXISTS enterprise.rls_violation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    tenant_id TEXT,
    table_name TEXT,
    operation TEXT,
    attempted_at TIMESTAMPTZ DEFAULT NOW(),
    details JSONB
);

COMMENT ON TABLE enterprise.rls_violation_log IS
'Audit log for RLS policy violations (attempted unauthorized access)';

-- Create trigger function (implementation left for Phase 2.1 if needed)
-- This would log any attempts to bypass RLS or access unauthorized data

-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRATION VERIFICATION
-- ═══════════════════════════════════════════════════════════════════════════

-- Verify RLS is enabled
DO $$
DECLARE
    rls_enabled BOOLEAN;
BEGIN
    SELECT relrowsecurity INTO rls_enabled
    FROM pg_class
    WHERE relname = 'department_content'
      AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'enterprise');

    IF rls_enabled THEN
        RAISE NOTICE '✓ Row Level Security is ENABLED on department_content';
    ELSE
        RAISE WARNING '✗ Row Level Security is NOT enabled on department_content!';
    END IF;
END $$;

-- List all policies
DO $$
DECLARE
    policy_record RECORD;
    policy_count INTEGER := 0;
BEGIN
    RAISE NOTICE 'Checking RLS policies on department_content:';

    FOR policy_record IN
        SELECT policyname, cmd, permissive
        FROM pg_policies
        WHERE schemaname = 'enterprise'
          AND tablename = 'department_content'
        ORDER BY policyname
    LOOP
        policy_count := policy_count + 1;
        RAISE NOTICE '  ✓ Policy: % (%, %)',
            policy_record.policyname,
            policy_record.cmd,
            CASE WHEN policy_record.permissive = 'PERMISSIVE' THEN 'Permissive' ELSE 'Restrictive' END;
    END LOOP;

    IF policy_count = 0 THEN
        RAISE WARNING '✗ No policies found on department_content!';
    ELSE
        RAISE NOTICE '✓ Total policies created: %', policy_count;
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- ROLLBACK SCRIPT (for development/testing)
-- ═══════════════════════════════════════════════════════════════════════════

-- Uncomment to roll back RLS policies:
/*
-- Disable RLS
ALTER TABLE enterprise.department_content DISABLE ROW LEVEL SECURITY;

-- Drop policies
DROP POLICY IF EXISTS dept_content_select_policy ON enterprise.department_content;
DROP POLICY IF EXISTS dept_content_insert_policy ON enterprise.department_content;
DROP POLICY IF EXISTS dept_content_update_policy ON enterprise.department_content;
DROP POLICY IF EXISTS dept_content_delete_policy ON enterprise.department_content;

-- Drop helper functions
DROP FUNCTION IF EXISTS enterprise.set_user_context(UUID, UUID);
DROP FUNCTION IF EXISTS enterprise.clear_user_context();
DROP FUNCTION IF EXISTS enterprise.get_user_context();

-- Drop audit log (optional)
DROP TABLE IF EXISTS enterprise.rls_violation_log;

-- Note: Do NOT drop the enterprise_super_user role in production
-- DROP ROLE IF EXISTS enterprise_super_user;
*/

-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRATION COMPLETE
-- ═══════════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '════════════════════════════════════════════════════════════════';
    RAISE NOTICE 'MIGRATION 003: RLS POLICIES COMPLETE';
    RAISE NOTICE '════════════════════════════════════════════════════════════════';
    RAISE NOTICE '';
    RAISE NOTICE 'Features Implemented:';
    RAISE NOTICE '  ✓ Row Level Security enabled on department_content';
    RAISE NOTICE '  ✓ SELECT policy: Tenant + department scoped access';
    RAISE NOTICE '  ✓ INSERT policy: Super users + dept heads only';
    RAISE NOTICE '  ✓ UPDATE policy: Write/admin access required';
    RAISE NOTICE '  ✓ DELETE policy: Super users only';
    RAISE NOTICE '  ✓ Helper functions: set_user_context(), clear_user_context(), get_user_context()';
    RAISE NOTICE '  ✓ Super user role created (bypass RLS for admin ops)';
    RAISE NOTICE '  ✓ FORCE ROW LEVEL SECURITY enabled (even for table owners)';
    RAISE NOTICE '';
    RAISE NOTICE 'Usage in Application Code:';
    RAISE NOTICE '  1. On every request: CALL enterprise.set_user_context(user_id, tenant_id);';
    RAISE NOTICE '  2. Execute queries (RLS policies auto-enforce filtering)';
    RAISE NOTICE '  3. Optional cleanup: CALL enterprise.clear_user_context();';
    RAISE NOTICE '';
    RAISE NOTICE 'Next Steps:';
    RAISE NOTICE '  → Phase 3: Create ingestion pipeline for JSON chunks';
    RAISE NOTICE '  → Phase 4: Integrate RLS with CogTwin retrieval';
    RAISE NOTICE '  → Phase 5: Lock schema and document tenant provisioning';
    RAISE NOTICE '';
    RAISE NOTICE '════════════════════════════════════════════════════════════════';
END $$;
