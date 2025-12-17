-- Migration: Add azure_oid column to users table for Azure AD SSO
-- Date: 2024-12-17
-- Sprint: Azure AD SSO Phase 1

-- Add azure_oid column to users table
ALTER TABLE enterprise.users
ADD COLUMN IF NOT EXISTS azure_oid VARCHAR(36) UNIQUE;

-- Create index for azure_oid lookups
CREATE INDEX IF NOT EXISTS idx_users_azure_oid
ON enterprise.users(azure_oid)
WHERE azure_oid IS NOT NULL;

-- Verify the column was added
SELECT
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'enterprise'
AND table_name = 'users'
AND column_name = 'azure_oid';
