-- Azure AD Migration Verification
-- Run this query to check if the migration has been applied

-- Check if azure_oid column exists
SELECT
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'enterprise'
  AND table_name = 'users'
  AND column_name = 'azure_oid';

-- Check if index exists
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'enterprise'
  AND tablename = 'users'
  AND indexname = 'idx_users_azure_oid';

-- If column doesn't exist, run this to add it:
-- ALTER TABLE enterprise.users ADD COLUMN IF NOT EXISTS azure_oid VARCHAR(36) UNIQUE;
-- CREATE INDEX IF NOT EXISTS idx_users_azure_oid ON enterprise.users(azure_oid) WHERE azure_oid IS NOT NULL;
