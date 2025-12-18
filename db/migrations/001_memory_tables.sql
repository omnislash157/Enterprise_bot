-- ═══════════════════════════════════════════════════════════════════════════
-- CogTwin PostgreSQL Migration - Phase 5
-- Memory Tables with pgvector Support
-- ═══════════════════════════════════════════════════════════════════════════

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- ═══════════════════════════════════════════════════════════════════════════
-- TENANTS TABLE
-- Multi-tenant isolation for enterprise deployments
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    azure_tenant_id VARCHAR(255) UNIQUE,
    config JSONB DEFAULT '{}',
    voice_engine VARCHAR(50) DEFAULT 'enterprise',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for Azure AD tenant lookup
CREATE INDEX idx_tenants_azure_tenant_id ON tenants(azure_tenant_id);

-- ═══════════════════════════════════════════════════════════════════════════
-- USERS TABLE
-- User authentication and tenant association
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_provider VARCHAR(50) NOT NULL,
    external_id VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    tenant_id UUID REFERENCES tenants(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(auth_provider, external_id)
);

-- Index for tenant-based user lookup
CREATE INDEX idx_users_tenant_id ON users(tenant_id);

-- Index for email lookup
CREATE INDEX idx_users_email ON users(email);

-- ═══════════════════════════════════════════════════════════════════════════
-- MEMORY NODES TABLE
-- Process memory with vector embeddings (1:1 Q/A pairs)
-- Matches MemoryNode schema from schemas.py
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE memory_nodes (
    -- Identity (matches schemas.py MemoryNode.id format: "mem_<hash>")
    id VARCHAR(255) PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL,
    sequence_index INTEGER NOT NULL,

    -- Auth scoping (CRITICAL: prevents cross-user/tenant leakage)
    user_id UUID REFERENCES users(id),
    tenant_id UUID REFERENCES tenants(id),

    -- Content
    human_content TEXT NOT NULL,
    assistant_content TEXT NOT NULL,

    -- Source & Time
    source VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Embedding (BGE-M3 1024-dimensional vector)
    embedding VECTOR(1024),

    -- Heuristic Signals (computed at ingest, zero LLM cost)
    intent_type VARCHAR(100) DEFAULT 'statement',
    complexity VARCHAR(50) DEFAULT 'simple',
    technical_depth INTEGER DEFAULT 0,
    emotional_valence VARCHAR(50) DEFAULT 'neutral',
    urgency VARCHAR(50) DEFAULT 'low',
    conversation_mode VARCHAR(50) DEFAULT 'chat',
    action_required BOOLEAN DEFAULT false,
    has_code BOOLEAN DEFAULT false,
    has_error BOOLEAN DEFAULT false,

    -- Dynamic Tags (emergent from data)
    tags JSONB DEFAULT '{"domains": [], "topics": [], "entities": [], "processes": []}',

    -- Cluster Metadata (assigned by HDBSCAN)
    cluster_id INTEGER,
    cluster_label VARCHAR(255),
    cluster_confidence FLOAT DEFAULT 0.0,

    -- Retrieval Metadata
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,

    -- Composite unique constraint (prevents duplicate Q/A pairs)
    UNIQUE(conversation_id, sequence_index, user_id, tenant_id)
);

-- ═══════════════════════════════════════════════════════════════════════════
-- INDEXES FOR FAST RETRIEVAL
-- ═══════════════════════════════════════════════════════════════════════════

-- CRITICAL: Auth scoping indexes (prevent cross-user leakage)
CREATE INDEX idx_memory_nodes_user ON memory_nodes(user_id);
CREATE INDEX idx_memory_nodes_tenant ON memory_nodes(tenant_id);

-- Vector similarity search index (IVFFlat for fast approximate nearest neighbor)
-- lists=100 is optimal for 10k-100k vectors; adjust based on corpus size
CREATE INDEX idx_memory_nodes_embedding ON memory_nodes
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Conversation-based lookup
CREATE INDEX idx_memory_nodes_conversation ON memory_nodes(conversation_id);

-- Cluster-based navigation
CREATE INDEX idx_memory_nodes_cluster ON memory_nodes(cluster_id) WHERE cluster_id IS NOT NULL;

-- Source filtering
CREATE INDEX idx_memory_nodes_source ON memory_nodes(source);

-- Time-based queries
CREATE INDEX idx_memory_nodes_created_at ON memory_nodes(created_at);

-- Composite index for scoped vector search (critical for performance)
CREATE INDEX idx_memory_nodes_user_embedding ON memory_nodes(user_id)
    WHERE user_id IS NOT NULL;
CREATE INDEX idx_memory_nodes_tenant_embedding ON memory_nodes(tenant_id)
    WHERE tenant_id IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════════════
-- COMMENTS (for database documentation)
-- ═══════════════════════════════════════════════════════════════════════════

COMMENT ON TABLE tenants IS 'Enterprise tenant isolation for multi-tenant deployments';
COMMENT ON TABLE users IS 'User authentication and tenant association';
COMMENT ON TABLE memory_nodes IS 'Process memory: 1:1 Q/A pairs with vector embeddings for RAG retrieval';

COMMENT ON COLUMN memory_nodes.embedding IS 'BGE-M3 1024-dim vector embedding for semantic similarity search';
COMMENT ON COLUMN memory_nodes.user_id IS 'Personal SaaS user scope (prevents cross-user leakage)';
COMMENT ON COLUMN memory_nodes.tenant_id IS 'Enterprise tenant scope (prevents cross-tenant leakage)';
COMMENT ON COLUMN memory_nodes.cluster_id IS 'HDBSCAN cluster assignment (-1 = noise, filtered out)';
COMMENT ON COLUMN memory_nodes.intent_type IS 'Heuristic intent classification (question/request/statement/complaint/celebration)';
COMMENT ON COLUMN memory_nodes.complexity IS 'Content complexity (simple/moderate/complex)';
COMMENT ON COLUMN memory_nodes.tags IS 'Dynamic tags from clustering: domains, topics, entities, processes';

-- ═══════════════════════════════════════════════════════════════════════════
-- VALIDATION CONSTRAINTS
-- ═══════════════════════════════════════════════════════════════════════════

-- Ensure at least one scope is set (fail secure: no auth = no storage)
ALTER TABLE memory_nodes ADD CONSTRAINT chk_memory_nodes_scope
    CHECK (user_id IS NOT NULL OR tenant_id IS NOT NULL);

-- Ensure technical_depth is in valid range
ALTER TABLE memory_nodes ADD CONSTRAINT chk_memory_nodes_technical_depth
    CHECK (technical_depth >= 0 AND technical_depth <= 10);

-- Ensure cluster_confidence is valid probability
ALTER TABLE memory_nodes ADD CONSTRAINT chk_memory_nodes_cluster_confidence
    CHECK (cluster_confidence >= 0.0 AND cluster_confidence <= 1.0);

-- ═══════════════════════════════════════════════════════════════════════════
-- GRANT PERMISSIONS (adjust based on deployment security model)
-- ═══════════════════════════════════════════════════════════════════════════

-- Example for a backend service user (uncomment and adjust as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON tenants, users, memory_nodes TO cogtwin_backend;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cogtwin_backend;
