-- ═══════════════════════════════════════════════════════════════════════════
-- PHASE 1: Enhance department_content for Vector RAG
-- Process Manual Schema Enhancement
-- ═══════════════════════════════════════════════════════════════════════════
--
-- Purpose: Upgrade department_content table to support:
-- 1. Vector embeddings (BGE-M3 1024-dim) for semantic search
-- 2. Chunk hierarchy (parent documents + child chunks)
-- 3. Rich metadata (source files, hashes, sections, tokens)
-- 4. Multi-tenant isolation via tenant_id
--
-- Dependencies:
-- - pgvector extension (from 001_memory_tables.sql)
-- - enterprise schema with existing department_content table
-- - tenants table (from 001_memory_tables.sql)
--
-- ═══════════════════════════════════════════════════════════════════════════

-- Ensure pgvector is available
CREATE EXTENSION IF NOT EXISTS vector;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 1: Add Multi-Tenant Isolation
-- ═══════════════════════════════════════════════════════════════════════════

-- Add tenant_id for multi-tenant isolation
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);

-- Set default tenant for existing rows (Driscoll Foods)
-- In production, you'd identify Driscoll's tenant_id from tenants table
UPDATE enterprise.department_content
SET tenant_id = (SELECT id FROM tenants WHERE name = 'Driscoll Foods' LIMIT 1)
WHERE tenant_id IS NULL;

-- Create index on tenant_id for fast tenant-scoped queries
CREATE INDEX IF NOT EXISTS idx_dept_content_tenant_id
ON enterprise.department_content(tenant_id);

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 2: Add Vector Embedding Column
-- ═══════════════════════════════════════════════════════════════════════════

-- Add 1024-dimensional vector for BGE-M3 embeddings
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS embedding VECTOR(1024);

-- Create IVFFlat index for fast approximate nearest neighbor search
-- lists=100 is optimal for 10k-100k vectors
-- For smaller datasets (<10k), lists=50 may be better
-- Adjust based on corpus size:
--   - <10k vectors: lists=50
--   - 10k-100k vectors: lists=100
--   - >100k vectors: lists=200
CREATE INDEX IF NOT EXISTS idx_dept_content_embedding
ON enterprise.department_content
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 3: Add Chunk Hierarchy Columns
-- ═══════════════════════════════════════════════════════════════════════════

-- Parent-child document-chunk relationship
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS parent_document_id UUID;

-- Order within document (0 for parent, 1+ for chunks)
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS chunk_index INTEGER DEFAULT 0;

-- Flag to identify root document vs chunks
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS is_document_root BOOLEAN DEFAULT FALSE;

-- Chunk type classification
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(50) DEFAULT 'content';

-- Create index for chunk hierarchy queries
CREATE INDEX IF NOT EXISTS idx_dept_content_parent
ON enterprise.department_content(parent_document_id)
WHERE parent_document_id IS NOT NULL;

-- Create index for ordered chunk retrieval
CREATE INDEX IF NOT EXISTS idx_dept_content_chunk_order
ON enterprise.department_content(parent_document_id, chunk_index)
WHERE parent_document_id IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 4: Add Rich Metadata Columns
-- ═══════════════════════════════════════════════════════════════════════════

-- Source file tracking
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS source_file VARCHAR(500);

-- File hash for deduplication (SHA256)
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64);

-- Section/heading title within document
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS section_title VARCHAR(500);

-- Token count for chunk size tracking
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS chunk_token_count INTEGER;

-- Embedding model identifier for versioning
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100) DEFAULT 'BAAI/bge-m3';

-- Category/subcategory for filtering
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS category VARCHAR(100);

ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS subcategory VARCHAR(100);

-- Keywords for enhanced search
ALTER TABLE enterprise.department_content
ADD COLUMN IF NOT EXISTS keywords JSONB DEFAULT '[]';

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 5: Create Metadata Indexes
-- ═══════════════════════════════════════════════════════════════════════════

-- Index for deduplication queries
CREATE INDEX IF NOT EXISTS idx_dept_content_file_hash
ON enterprise.department_content(file_hash)
WHERE file_hash IS NOT NULL;

-- Unique constraint on (tenant_id, department_id, file_hash) to prevent duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_dept_content_unique_file
ON enterprise.department_content(tenant_id, department_id, file_hash)
WHERE file_hash IS NOT NULL;

-- Index for category filtering
CREATE INDEX IF NOT EXISTS idx_dept_content_category
ON enterprise.department_content(category)
WHERE category IS NOT NULL;

-- Index for section-based queries
CREATE INDEX IF NOT EXISTS idx_dept_content_section
ON enterprise.department_content(section_title)
WHERE section_title IS NOT NULL;

-- GIN index for keyword array search
CREATE INDEX IF NOT EXISTS idx_dept_content_keywords
ON enterprise.department_content USING GIN (keywords);

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 6: Add Validation Constraints
-- ═══════════════════════════════════════════════════════════════════════════

-- Ensure chunk_token_count is positive
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_dept_content_token_count') THEN
        ALTER TABLE enterprise.department_content
        ADD CONSTRAINT chk_dept_content_token_count
        CHECK (chunk_token_count IS NULL OR chunk_token_count > 0);
    END IF;
END $$;

-- Ensure chunk_index is non-negative
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_dept_content_chunk_index') THEN
        ALTER TABLE enterprise.department_content
        ADD CONSTRAINT chk_dept_content_chunk_index
        CHECK (chunk_index >= 0);
    END IF;
END $$;

-- Ensure file_hash is valid SHA256 format (64 hex chars)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_dept_content_file_hash') THEN
        ALTER TABLE enterprise.department_content
        ADD CONSTRAINT chk_dept_content_file_hash
        CHECK (file_hash IS NULL OR file_hash ~ '^[a-f0-9]{64}$');
    END IF;
END $$;

-- Ensure embedding model is specified when embedding exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_dept_content_embedding_model') THEN
        ALTER TABLE enterprise.department_content
        ADD CONSTRAINT chk_dept_content_embedding_model
        CHECK (embedding IS NULL OR embedding_model IS NOT NULL);
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 7: Add Composite Indexes for Common Query Patterns
-- ═══════════════════════════════════════════════════════════════════════════

-- Tenant + Department scoped queries (critical for multi-tenant RAG)
CREATE INDEX IF NOT EXISTS idx_dept_content_tenant_dept
ON enterprise.department_content(tenant_id, department_id);

-- Tenant + Department + Active for production queries
CREATE INDEX IF NOT EXISTS idx_dept_content_tenant_dept_active
ON enterprise.department_content(tenant_id, department_id, active)
WHERE active = TRUE;

-- Department + Category for filtered retrieval
CREATE INDEX IF NOT EXISTS idx_dept_content_dept_category
ON enterprise.department_content(department_id, category)
WHERE category IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 8: Update Table Comments
-- ═══════════════════════════════════════════════════════════════════════════

COMMENT ON TABLE enterprise.department_content IS
'Process manuals and department content with vector embeddings for semantic RAG retrieval';

COMMENT ON COLUMN enterprise.department_content.tenant_id IS
'Multi-tenant isolation: associates content with specific tenant';

COMMENT ON COLUMN enterprise.department_content.embedding IS
'BGE-M3 1024-dimensional vector embedding for semantic similarity search';

COMMENT ON COLUMN enterprise.department_content.parent_document_id IS
'Parent document ID for chunk hierarchy (NULL for root documents)';

COMMENT ON COLUMN enterprise.department_content.chunk_index IS
'Order within parent document (0 for root, 1+ for chunks)';

COMMENT ON COLUMN enterprise.department_content.is_document_root IS
'TRUE for root documents, FALSE for chunks';

COMMENT ON COLUMN enterprise.department_content.file_hash IS
'SHA256 hash of source file for deduplication';

COMMENT ON COLUMN enterprise.department_content.section_title IS
'Section/heading title within document for context';

COMMENT ON COLUMN enterprise.department_content.chunk_token_count IS
'Approximate token count for chunk size tracking (~4 chars = 1 token)';

COMMENT ON COLUMN enterprise.department_content.embedding_model IS
'Embedding model identifier for versioning (default: BAAI/bge-m3)';

COMMENT ON COLUMN enterprise.department_content.keywords IS
'JSON array of extracted keywords for enhanced search';

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 9: Create Utility Functions
-- ═══════════════════════════════════════════════════════════════════════════

-- Function to get all chunks for a document
CREATE OR REPLACE FUNCTION enterprise.get_document_chunks(doc_id UUID)
RETURNS TABLE (
    id UUID,
    chunk_index INTEGER,
    section_title VARCHAR(500),
    content TEXT,
    chunk_token_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.chunk_index,
        dc.section_title,
        dc.content,
        dc.chunk_token_count
    FROM enterprise.department_content dc
    WHERE dc.parent_document_id = doc_id
    ORDER BY dc.chunk_index;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION enterprise.get_document_chunks IS
'Retrieve all chunks for a given parent document in order';

-- Function to search by vector similarity with department scoping
CREATE OR REPLACE FUNCTION enterprise.search_department_content(
    query_embedding VECTOR(1024),
    query_tenant_id UUID,
    query_department_ids UUID[],
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    department_id UUID,
    title VARCHAR(255),
    section_title VARCHAR(500),
    content TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.department_id,
        dc.title,
        dc.section_title,
        dc.content,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM enterprise.department_content dc
    WHERE dc.tenant_id = query_tenant_id
        AND dc.department_id = ANY(query_department_ids)
        AND dc.embedding IS NOT NULL
        AND dc.active = TRUE
    ORDER BY dc.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION enterprise.search_department_content IS
'Vector similarity search scoped to tenant and authorized departments';

-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRATION COMPLETE
-- ═══════════════════════════════════════════════════════════════════════════

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 002_enhance_department_content.sql completed successfully';
    RAISE NOTICE 'Schema enhancements:';
    RAISE NOTICE '  - Vector embedding column (VECTOR(1024))';
    RAISE NOTICE '  - Chunk hierarchy (parent_document_id, chunk_index)';
    RAISE NOTICE '  - Rich metadata (source_file, file_hash, section_title, etc.)';
    RAISE NOTICE '  - Multi-tenant isolation (tenant_id)';
    RAISE NOTICE '  - IVFFlat vector index for fast similarity search';
    RAISE NOTICE '  - Utility functions for chunk retrieval and search';
    RAISE NOTICE 'Ready for Phase 2: RLS Policies';
END $$;
