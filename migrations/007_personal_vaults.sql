-- Personal Vaults - Per-user cloud storage for memory
-- Part of Cogzy personal tier

BEGIN;

-- Vault metadata
CREATE TABLE personal.vaults (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES personal.users(id) ON DELETE CASCADE,

    -- B2 location
    bucket TEXT NOT NULL DEFAULT 'cogzy-vaults',
    prefix TEXT NOT NULL,  -- users/{user_uuid}

    -- Stats (updated by pipeline)
    node_count INTEGER DEFAULT 0,
    total_bytes BIGINT DEFAULT 0,
    last_sync_at TIMESTAMPTZ,

    -- State machine
    status TEXT NOT NULL DEFAULT 'empty'
        CHECK (status IN ('empty', 'syncing', 'ready', 'error')),
    error_message TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_user_vault UNIQUE(user_id)
);

-- Upload tracking
CREATE TABLE personal.vault_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vault_id UUID NOT NULL REFERENCES personal.vaults(id) ON DELETE CASCADE,

    -- Source identification
    source_type TEXT NOT NULL
        CHECK (source_type IN ('anthropic', 'openai', 'grok', 'gemini', 'unknown')),
    original_filename TEXT,
    uploaded_bytes BIGINT,

    -- Processing state
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'complete', 'failed')),
    progress_pct INTEGER DEFAULT 0,

    -- Results
    nodes_created INTEGER DEFAULT 0,
    nodes_deduplicated INTEGER DEFAULT 0,
    error_message TEXT,

    -- Timing
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ
);

-- User tier tracking (for rate limiting)
CREATE TABLE personal.user_tiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES personal.users(id) ON DELETE CASCADE,

    tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'premium')),

    -- Usage tracking (reset daily)
    messages_today INTEGER DEFAULT 0,
    messages_reset_at DATE DEFAULT CURRENT_DATE,

    -- Subscription info (for premium)
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    subscription_status TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_user_tier UNIQUE(user_id)
);

-- Indexes
CREATE INDEX idx_vaults_user ON personal.vaults(user_id);
CREATE INDEX idx_vaults_status ON personal.vaults(status);
CREATE INDEX idx_uploads_vault ON personal.vault_uploads(vault_id);
CREATE INDEX idx_uploads_status ON personal.vault_uploads(status);
CREATE INDEX idx_tiers_user ON personal.user_tiers(user_id);

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER vaults_updated_at
    BEFORE UPDATE ON personal.vaults
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tiers_updated_at
    BEFORE UPDATE ON personal.user_tiers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMIT;
