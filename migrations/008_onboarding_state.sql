-- Migration 008: Onboarding State Table
-- Track Cogzy persona onboarding progress for personal tier users

CREATE TABLE IF NOT EXISTS personal.onboarding_state (
    user_id UUID PRIMARY KEY REFERENCES personal.users(id) ON DELETE CASCADE,
    message_count INTEGER DEFAULT 0,
    total_user_chars INTEGER DEFAULT 0,
    substantive_exchanges INTEGER DEFAULT 0,
    troll_score INTEGER DEFAULT 0,
    topics_discovered JSONB DEFAULT '[]',
    message_history JSONB DEFAULT '[]',
    response_history JSONB DEFAULT '[]',
    graduated BOOLEAN DEFAULT FALSE,
    graduated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_onboarding_user ON personal.onboarding_state(user_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_graduated ON personal.onboarding_state(graduated);

COMMENT ON TABLE personal.onboarding_state IS 'Track Cogzy persona onboarding progress and graduation to Venom';
COMMENT ON COLUMN personal.onboarding_state.message_count IS 'Total number of user messages sent during onboarding';
COMMENT ON COLUMN personal.onboarding_state.substantive_exchanges IS 'Number of exchanges with meaningful content (>30 chars)';
COMMENT ON COLUMN personal.onboarding_state.troll_score IS 'Accumulated troll detection score';
COMMENT ON COLUMN personal.onboarding_state.topics_discovered IS 'Array of topics extracted during onboarding';
COMMENT ON COLUMN personal.onboarding_state.graduated IS 'Whether user has graduated from Cogzy to Venom';
