-- Migration 003: Smart RAG Schema Design
-- Date: 2024-12-22
-- Philosophy: Pre-compute structure at ingest, trivialize retrieval
--
-- Design Principles:
-- 1. Single table - zero joins at query time
-- 2. Heavy indexing - GIN on arrays, IVFFlat on vectors, GiST on full-text
-- 3. Threshold-based retrieval - return EVERYTHING relevant (score >= 0.6)
-- 4. Pre-computed relationships - chunk graph built at ingest
-- 5. Heuristic boosting - importance, specificity, complexity scored upfront

BEGIN;

-- ============================================================================
-- CORE TABLE: enterprise.documents
-- ============================================================================

CREATE TABLE IF NOT EXISTS enterprise.documents (
    -- ========================================
    -- PRIMARY IDENTITY
    -- ========================================
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ========================================
    -- SOURCE METADATA (from JSON chunks)
    -- ========================================
    source_file TEXT NOT NULL,                -- Original document filename
    source_type TEXT,                         -- 'manual', 'policy', 'form', 'faq'
    department_id TEXT NOT NULL,              -- 'warehouse', 'sales', 'credit', etc.
    section_title TEXT,                       -- Section/heading this chunk lives under
    chunk_index INTEGER,                      -- Position within parent document (0-based)

    -- ========================================
    -- CONTENT
    -- ========================================
    content TEXT NOT NULL,                    -- The actual chunk text
    content_length INTEGER NOT NULL,          -- Character count
    token_count INTEGER,                      -- For LLM context budgets

    -- ========================================
    -- EMBEDDING (the star of the show)
    -- ========================================
    embedding VECTOR(1024),                   -- DeepInfra embeddings (1024-dim)

    -- ========================================
    -- SEMANTIC CLASSIFICATION
    -- (Pre-computed at ingest, zero query-time cost)
    -- ========================================

    -- Intent: What kind of question does this answer?
    query_types TEXT[] NOT NULL DEFAULT '{}',
    -- Values: 'how_to', 'policy', 'troubleshoot', 'definition', 'lookup', 'escalation', 'reference'
    -- Example: ['how_to', 'policy'] for "How to submit a credit request (Policy 4.2)"

    -- Actions: What verbs/operations are described?
    verbs TEXT[] NOT NULL DEFAULT '{}',
    -- Values: 'approve', 'reject', 'submit', 'create', 'void', 'escalate', 'review', 'verify', 'process', 'route'
    -- Example: ['submit', 'approve', 'escalate'] for credit approval workflow

    -- Entities: What domain objects are involved?
    entities TEXT[] NOT NULL DEFAULT '{}',
    -- Values: 'credit_memo', 'purchase_order', 'invoice', 'customer', 'vendor', 'return', 'shipment', etc.
    -- Example: ['credit_memo', 'customer', 'dispute'] for dispute handling

    -- Actors: Who performs these actions?
    actors TEXT[] NOT NULL DEFAULT '{}',
    -- Values: 'sales_rep', 'warehouse_mgr', 'credit_analyst', 'purchasing_agent', 'driver', 'supervisor'
    -- Example: ['credit_analyst', 'supervisor'] for credit approval process

    -- Conditions: What triggers or contexts apply?
    conditions TEXT[] NOT NULL DEFAULT '{}',
    -- Values: 'exception', 'dispute', 'rush_order', 'new_customer', 'over_limit', 'damage', 'shortage'
    -- Example: ['exception', 'over_limit'] for handling out-of-bounds credit requests

    -- ========================================
    -- PROCESS STRUCTURE
    -- (Makes procedural content trivially navigable)
    -- ========================================

    process_name TEXT,                        -- 'credit_approval', 'returns_processing', NULL if not procedural
    process_step INTEGER,                     -- 1, 2, 3... NULL if not sequential
    is_procedure BOOLEAN DEFAULT FALSE,       -- Fast filter for "how-to" queries
    is_policy BOOLEAN DEFAULT FALSE,          -- Fast filter for "what's the rule" queries
    is_form BOOLEAN DEFAULT FALSE,            -- Fast filter for "where's the template" queries

    -- ========================================
    -- HEURISTIC SCORES
    -- (Pre-computed relevance signals, no query-time calculation)
    -- ========================================

    importance INTEGER CHECK (importance BETWEEN 1 AND 10),
    -- 10 = Critical policy/compliance, 5 = Standard procedure, 1 = Helpful tip
    -- Computed from: policy keywords, regulatory terms, "must/required" language

    specificity INTEGER CHECK (specificity BETWEEN 1 AND 10),
    -- 10 = Narrow edge case, 5 = Common scenario, 1 = Broad overview
    -- Computed from: condition rarity, keyword uniqueness, content length

    complexity INTEGER CHECK (complexity BETWEEN 1 AND 10),
    -- 10 = Specialist-only, 5 = Requires training, 1 = Anyone can understand
    -- Computed from: jargon density, step count, prerequisite requirements

    -- ========================================
    -- CHUNK RELATIONSHIPS (The Knowledge Graph)
    -- (Built at ingest, enables instant context expansion)
    -- ========================================

    parent_id UUID REFERENCES enterprise.documents(id) ON DELETE CASCADE,
    -- The document/section this chunk belongs to (NULL for top-level)

    sibling_ids UUID[] DEFAULT '{}',
    -- Chunks at same level in same document (auto-computed from parent_id + chunk_index)

    prerequisite_ids UUID[] DEFAULT '{}',
    -- "Read these first" - chunks that provide necessary context
    -- Example: Credit policy overview → Credit approval procedure

    see_also_ids UUID[] DEFAULT '{}',
    -- "Related but different topic" - lateral connections
    -- Example: Credit memo creation ←→ Invoice adjustment procedure

    follows_ids UUID[] DEFAULT '{}',
    -- "This comes after" - sequential dependencies
    -- Example: Step 2 follows Step 1 (computed from process_name + process_step)

    supersedes_id UUID REFERENCES enterprise.documents(id) ON DELETE SET NULL,
    -- Version control: "This replaces that older chunk"

    -- ========================================
    -- TOPIC CLUSTERING
    -- (Pre-computed at ingest using embedding similarity)
    -- ========================================

    cluster_id INTEGER,
    -- Topic cluster ID (computed via HDBSCAN or k-means on embeddings)

    cluster_label TEXT,
    -- Human-readable topic name ('Credit Policies', 'Warehouse Receiving', etc.)

    cluster_centroid VECTOR(1024),
    -- Average embedding of all chunks in this cluster (for fast cluster-wide search)

    -- ========================================
    -- FULL-TEXT SEARCH
    -- (Because sometimes exact keyword matching beats embeddings)
    -- ========================================

    search_vector TSVECTOR,
    -- Pre-computed full-text search vector (from content + section_title + entities)

    -- ========================================
    -- ACCESS CONTROL
    -- ========================================

    department_access TEXT[] NOT NULL DEFAULT '{}',
    -- Departments that can see this chunk (supports cross-department content)
    -- Example: ['credit', 'sales'] for "How sales reps submit credit requests"

    requires_role TEXT[],
    -- Role-based restrictions (NULL = anyone in dept can see)
    -- Example: ['supervisor', 'manager'] for escalation procedures

    is_sensitive BOOLEAN DEFAULT FALSE,
    -- PII, financial, or compliance content requiring audit logging

    -- ========================================
    -- LIFECYCLE
    -- ========================================

    is_active BOOLEAN DEFAULT TRUE,
    -- Soft delete: FALSE = archived/deprecated

    version INTEGER DEFAULT 1,
    -- Document version (incremented when content changes)

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ,
    access_count INTEGER DEFAULT 0,

    -- ========================================
    -- QUALITY METRICS
    -- (Computed during ingestion validation)
    -- ========================================

    has_embedding BOOLEAN GENERATED ALWAYS AS (embedding IS NOT NULL) STORED,
    has_relationships BOOLEAN GENERATED ALWAYS AS (
        COALESCE(array_length(prerequisite_ids, 1), 0) > 0 OR
        COALESCE(array_length(see_also_ids, 1), 0) > 0
    ) STORED,
    tag_count INTEGER GENERATED ALWAYS AS (
        COALESCE(array_length(query_types, 1), 0) +
        COALESCE(array_length(verbs, 1), 0) +
        COALESCE(array_length(entities, 1), 0)
    ) STORED
);

-- ============================================================================
-- INDEXES (The Performance Secret Sauce)
-- ============================================================================

-- ----------------------------------------
-- VECTOR SEARCH (IVFFlat for cosine similarity)
-- ----------------------------------------
-- NOTE: IVFFlat requires manual clustering, so we'll use this initially
-- and upgrade to HNSW once pgvector 0.5.0+ is widely available
CREATE INDEX idx_documents_embedding ON enterprise.documents
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
-- lists = sqrt(row_count) for optimal performance
-- Will need VACUUM ANALYZE after initial data load

-- ----------------------------------------
-- ARRAY FILTERS (GIN for ANY/overlap queries)
-- ----------------------------------------
CREATE INDEX idx_documents_query_types ON enterprise.documents USING GIN (query_types);
CREATE INDEX idx_documents_verbs ON enterprise.documents USING GIN (verbs);
CREATE INDEX idx_documents_entities ON enterprise.documents USING GIN (entities);
CREATE INDEX idx_documents_actors ON enterprise.documents USING GIN (actors);
CREATE INDEX idx_documents_conditions ON enterprise.documents USING GIN (conditions);
CREATE INDEX idx_documents_dept_access ON enterprise.documents USING GIN (department_access);

-- ----------------------------------------
-- BOOLEAN FILTERS (B-tree for fast category filtering)
-- ----------------------------------------
CREATE INDEX idx_documents_is_procedure ON enterprise.documents (is_procedure) WHERE is_procedure = TRUE;
CREATE INDEX idx_documents_is_policy ON enterprise.documents (is_policy) WHERE is_policy = TRUE;
CREATE INDEX idx_documents_is_active ON enterprise.documents (is_active) WHERE is_active = TRUE;

-- ----------------------------------------
-- PROCESS NAVIGATION (B-tree for ordering)
-- ----------------------------------------
CREATE INDEX idx_documents_process ON enterprise.documents (process_name, process_step)
WHERE process_name IS NOT NULL;

-- ----------------------------------------
-- DEPARTMENT FILTERING (B-tree, most common filter)
-- ----------------------------------------
CREATE INDEX idx_documents_department ON enterprise.documents (department_id, is_active);

-- ----------------------------------------
-- FULL-TEXT SEARCH (GiST for fast text search)
-- ----------------------------------------
CREATE INDEX idx_documents_search_vector ON enterprise.documents USING GiST (search_vector);

-- ----------------------------------------
-- RELATIONSHIP TRAVERSAL (GIN for array lookups)
-- ----------------------------------------
CREATE INDEX idx_documents_parent ON enterprise.documents (parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX idx_documents_siblings ON enterprise.documents USING GIN (sibling_ids);
CREATE INDEX idx_documents_prerequisites ON enterprise.documents USING GIN (prerequisite_ids);
CREATE INDEX idx_documents_see_also ON enterprise.documents USING GIN (see_also_ids);

-- ----------------------------------------
-- CLUSTERING (B-tree for cluster-based expansion)
-- ----------------------------------------
CREATE INDEX idx_documents_cluster ON enterprise.documents (cluster_id) WHERE cluster_id IS NOT NULL;

-- ----------------------------------------
-- HEURISTIC SORTING (B-tree composite for ORDER BY)
-- ----------------------------------------
CREATE INDEX idx_documents_relevance ON enterprise.documents (importance DESC, specificity DESC, complexity ASC);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- ----------------------------------------
-- Auto-update search_vector on content change
-- ----------------------------------------
CREATE OR REPLACE FUNCTION update_document_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.section_title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(NEW.entities, ' '), '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trig_update_search_vector
BEFORE INSERT OR UPDATE OF content, section_title, entities
ON enterprise.documents
FOR EACH ROW
EXECUTE FUNCTION update_document_search_vector();

-- ----------------------------------------
-- Auto-update updated_at timestamp
-- ----------------------------------------
CREATE OR REPLACE FUNCTION update_document_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trig_update_timestamp
BEFORE UPDATE ON enterprise.documents
FOR EACH ROW
EXECUTE FUNCTION update_document_timestamp();

-- ----------------------------------------
-- Auto-compute sibling_ids for chunks in same document
-- ----------------------------------------
CREATE OR REPLACE FUNCTION compute_sibling_ids(doc_id UUID)
RETURNS UUID[] AS $$
    SELECT ARRAY(
        SELECT id
        FROM enterprise.documents
        WHERE parent_id = (SELECT parent_id FROM enterprise.documents WHERE id = doc_id)
          AND id != doc_id
        ORDER BY chunk_index
    );
$$ LANGUAGE SQL;

-- ----------------------------------------
-- Retrieve full process by name (all steps ordered)
-- ----------------------------------------
CREATE OR REPLACE FUNCTION get_process_steps(proc_name TEXT)
RETURNS TABLE (
    id UUID,
    step_number INTEGER,
    content TEXT,
    actors TEXT[],
    verbs TEXT[]
) AS $$
    SELECT id, process_step, content, actors, verbs
    FROM enterprise.documents
    WHERE process_name = proc_name
      AND is_active = TRUE
    ORDER BY process_step ASC;
$$ LANGUAGE SQL;

-- ----------------------------------------
-- Expand context: Get chunk + prerequisites + see_also
-- ----------------------------------------
CREATE OR REPLACE FUNCTION expand_chunk_context(chunk_id UUID)
RETURNS TABLE (
    id UUID,
    content TEXT,
    relationship TEXT  -- 'source', 'prerequisite', 'see_also'
) AS $$
    -- The original chunk
    SELECT id, content, 'source'::TEXT
    FROM enterprise.documents
    WHERE id = chunk_id

    UNION ALL

    -- Prerequisites
    SELECT d.id, d.content, 'prerequisite'::TEXT
    FROM enterprise.documents d
    WHERE d.id = ANY(
        SELECT unnest(prerequisite_ids)
        FROM enterprise.documents
        WHERE id = chunk_id
    )

    UNION ALL

    -- See also
    SELECT d.id, d.content, 'see_also'::TEXT
    FROM enterprise.documents d
    WHERE d.id = ANY(
        SELECT unnest(see_also_ids)
        FROM enterprise.documents
        WHERE id = chunk_id
    );
$$ LANGUAGE SQL;

-- ============================================================================
-- SAMPLE QUERIES (Commented out, for reference)
-- ============================================================================

/*
-- QUERY 1: Smart threshold-based retrieval
-- "How do I approve a credit memo when the customer is disputing?"

WITH smart_candidates AS (
    SELECT
        id, content, section_title, source_file, embedding,
        importance, process_name, process_step,
        see_also_ids, prerequisite_ids
    FROM enterprise.documents
    WHERE
        -- Fast pre-filters (sub-10ms with GIN indexes)
        is_active = TRUE
        AND 'credit' = ANY(department_access)  -- User's department
        AND ('how_to' = ANY(query_types) OR 'troubleshoot' = ANY(query_types))  -- Intent
        AND entities && ARRAY['credit_memo', 'customer', 'dispute']  -- Entity overlap
        AND 'approve' = ANY(verbs)  -- Action verb
),
scored AS (
    SELECT
        *,
        1 - (embedding <=> $query_embedding::vector) AS similarity
    FROM smart_candidates
    WHERE embedding IS NOT NULL
)
SELECT
    *,
    -- Boost procedural content for "how to" queries
    CASE
        WHEN is_procedure THEN similarity + 0.1
        ELSE similarity
    END AS boosted_score
FROM scored
WHERE similarity >= 0.6  -- Threshold, not top-N!
ORDER BY
    importance DESC,       -- Policies before tips
    boosted_score DESC,    -- Most relevant first
    process_step ASC NULLS LAST  -- Sequential if procedural
;

-- QUERY 2: Cluster expansion (find all related topics)
SELECT id, content, section_title, 1 - (embedding <=> $query_embedding::vector) AS score
FROM enterprise.documents
WHERE cluster_id = (
    SELECT cluster_id
    FROM enterprise.documents
    WHERE id = $initial_match_id
)
AND is_active = TRUE
ORDER BY score DESC;

-- QUERY 3: Process retrieval (get full workflow)
SELECT * FROM get_process_steps('credit_approval');

-- QUERY 4: Keyword + vector hybrid search
SELECT
    id,
    content,
    ts_rank(search_vector, query) AS text_rank,
    1 - (embedding <=> $query_embedding::vector) AS vector_score,
    -- Combine scores (60% semantic, 40% keyword)
    (0.6 * (1 - (embedding <=> $query_embedding::vector))) +
    (0.4 * ts_rank(search_vector, query)) AS hybrid_score
FROM enterprise.documents,
     plainto_tsquery('english', $query_text) query
WHERE
    search_vector @@ query  -- Text match first
    AND is_active = TRUE
ORDER BY hybrid_score DESC;
*/

COMMIT;

-- ============================================================================
-- POST-MIGRATION NOTES
-- ============================================================================

-- After initial data load, run:
-- VACUUM ANALYZE enterprise.documents;
--
-- This rebuilds statistics for the IVFFlat index and optimizes GIN indexes.
-- Critical for performance!
