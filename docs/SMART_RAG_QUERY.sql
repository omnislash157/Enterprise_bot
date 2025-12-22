-- ============================================================================
-- SMART RAG RETRIEVAL QUERY
-- ============================================================================
-- Date: 2024-12-22
-- Purpose: Demonstrate threshold-based, pre-filtered vector search
--
-- Philosophy:
-- 1. Pre-filter to tiny candidate set (GIN indexes, <10ms)
-- 2. Vector search on candidates only (IVFFlat, <50ms)
-- 3. Return EVERYTHING above threshold (not top-N)
-- 4. Expand context with relationships (instant array lookups)
-- 5. Order by importance + relevance
--
-- Result: <100ms total, lights-out relevant results
-- ============================================================================

-- ============================================================================
-- EXAMPLE 1: "How do I approve a credit memo when the customer is disputing?"
-- ============================================================================

-- Input parameters (from user query processing):
-- $query_embedding: vector(1024) -- DeepInfra embedding of user query
-- $user_department: 'credit'
-- $intent: 'how_to'
-- $entities: ['credit_memo', 'customer', 'dispute']
-- $verbs: ['approve']
-- $threshold: 0.6

WITH smart_candidates AS (
    -- STEP 1: Fast pre-filtering (GIN indexes)
    -- Reduces search space from 10,000 chunks → ~50 candidates
    SELECT
        id,
        content,
        section_title,
        source_file,
        embedding,
        importance,
        specificity,
        process_name,
        process_step,
        is_procedure,
        see_also_ids,
        prerequisite_ids,
        sibling_ids,
        actors,
        verbs,
        entities
    FROM enterprise.documents
    WHERE
        -- Access control (instant B-tree lookup)
        is_active = TRUE
        AND :user_department = ANY(department_access)

        -- Intent filter (GIN index, sub-5ms)
        AND (:intent = ANY(query_types) OR 'troubleshoot' = ANY(query_types))

        -- Entity overlap (GIN index, sub-5ms)
        AND entities && :entities  -- Array overlap operator

        -- Verb filter (GIN index, sub-5ms)
        AND :verbs && verbs  -- Must mention "approve"
),
scored AS (
    -- STEP 2: Vector similarity on tiny candidate set
    -- 50 vectors × 1024 dims = trivial cosine computation
    SELECT
        *,
        1 - (embedding <=> :query_embedding) AS similarity
    FROM smart_candidates
    WHERE embedding IS NOT NULL
),
threshold_results AS (
    -- STEP 3: Threshold-based retrieval
    -- Return EVERYTHING relevant, not arbitrary top-5
    SELECT * FROM scored
    WHERE similarity >= :threshold  -- 0.6 = relevance cutoff
),
boosted AS (
    -- STEP 4: Apply heuristic boosts
    SELECT
        *,
        -- Boost procedural content for "how to" queries
        CASE
            WHEN is_procedure AND :intent = 'how_to' THEN similarity + 0.1
            ELSE similarity
        END AS boosted_score
    FROM threshold_results
)
-- STEP 5: Order by importance, then relevance
SELECT
    id,
    content,
    section_title,
    source_file,
    process_name,
    process_step,
    actors,
    verbs,
    entities,
    importance,
    similarity,
    boosted_score,
    -- Metadata for context expansion
    see_also_ids,
    prerequisite_ids,
    sibling_ids
FROM boosted
ORDER BY
    importance DESC,           -- Critical policies first
    boosted_score DESC,        -- Most relevant within importance tier
    process_step ASC NULLS LAST  -- Sequential if procedural
;

-- Expected result: 7-12 chunks covering:
-- - Credit memo approval procedure (steps 1-5)
-- - Exception handling for disputes (step 3b)
-- - Escalation policy for contested amounts
-- - Related: Invoice adjustment procedures (see_also)
-- Total time: ~80ms


-- ============================================================================
-- EXAMPLE 2: "What's the policy on rush orders?"
-- ============================================================================

-- Input parameters:
-- $query_embedding: vector(1024)
-- $user_department: 'sales'
-- $intent: 'policy'
-- $entities: ['order']
-- $conditions: ['rush_order']

WITH smart_candidates AS (
    SELECT
        id, content, section_title, source_file, embedding,
        importance, is_policy, cluster_id
    FROM enterprise.documents
    WHERE
        is_active = TRUE
        AND :user_department = ANY(department_access)
        AND 'policy' = ANY(query_types)  -- Policy filter
        AND 'rush_order' = ANY(conditions)  -- Condition match
),
scored AS (
    SELECT
        *,
        1 - (embedding <=> :query_embedding) AS similarity
    FROM smart_candidates
    WHERE embedding IS NOT NULL
),
threshold_results AS (
    SELECT * FROM scored
    WHERE similarity >= 0.6
),
cluster_expansion AS (
    -- STEP: Expand to full cluster (get ALL related policies)
    SELECT DISTINCT
        d.*,
        1 - (d.embedding <=> :query_embedding) AS similarity
    FROM threshold_results t
    JOIN enterprise.documents d ON d.cluster_id = t.cluster_id
    WHERE d.is_active = TRUE
      AND 1 - (d.embedding <=> :query_embedding) >= 0.5  -- Slightly lower threshold for cluster
)
SELECT
    id, content, section_title, importance, similarity
FROM cluster_expansion
ORDER BY importance DESC, similarity DESC
LIMIT 20;  -- Soft limit for UI display

-- Expected result: All rush order policies + related policies in same topic cluster
-- Total time: ~90ms


-- ============================================================================
-- EXAMPLE 3: "Contact info for warehouse supervisor"
-- ============================================================================

-- Input parameters:
-- $query_embedding: vector(1024)
-- $user_department: 'warehouse'
-- $intent: 'lookup'
-- $actors: ['supervisor', 'warehouse_mgr']

WITH smart_candidates AS (
    SELECT
        id, content, section_title, source_file, embedding
    FROM enterprise.documents
    WHERE
        is_active = TRUE
        AND :user_department = ANY(department_access)
        AND 'lookup' = ANY(query_types)  -- Lookup/reference content
        AND actors && :actors  -- Actor overlap
),
scored AS (
    SELECT
        *,
        1 - (embedding <=> :query_embedding) AS similarity
    FROM smart_candidates
    WHERE embedding IS NOT NULL
)
SELECT id, content, section_title, similarity
FROM scored
WHERE similarity >= 0.7  -- Higher threshold for lookup (want exact match)
ORDER BY similarity DESC
LIMIT 5;  -- Lookup queries usually want 1-2 results

-- Expected result: 1-2 chunks with contact directory/escalation info
-- Total time: ~60ms


-- ============================================================================
-- EXAMPLE 4: Get full process (all steps)
-- ============================================================================

-- Use helper function for instant process retrieval
SELECT * FROM get_process_steps('credit_approval');

-- Returns all steps in order:
-- Step 1: Submit request
-- Step 2: Verify customer account
-- Step 3: Review amount
-- Step 4: Approve/reject
-- Step 5: Notify sales rep
-- Total time: ~10ms (no vector search needed!)


-- ============================================================================
-- EXAMPLE 5: Context expansion (get related chunks)
-- ============================================================================

-- User clicked on chunk ID 'abc123', expand context
SELECT * FROM expand_chunk_context('abc123'::uuid);

-- Returns:
-- - The original chunk (relationship='source')
-- - All prerequisites (relationship='prerequisite')
-- - All see_also links (relationship='see_also')
-- Total time: ~15ms (array lookups only)


-- ============================================================================
-- EXAMPLE 6: Hybrid search (keyword + semantic)
-- ============================================================================

-- Input: User typed "PO 12345" (specific PO number)
-- Combine full-text search + vector search

WITH text_matches AS (
    -- Fast text search for exact keyword
    SELECT
        id, content, section_title, embedding,
        ts_rank(search_vector, query) AS text_rank
    FROM enterprise.documents,
         plainto_tsquery('english', :query_text) query
    WHERE
        search_vector @@ query
        AND is_active = TRUE
        AND :user_department = ANY(department_access)
),
vector_scored AS (
    -- Semantic search on text matches
    SELECT
        *,
        1 - (embedding <=> :query_embedding) AS vector_score
    FROM text_matches
    WHERE embedding IS NOT NULL
),
hybrid_scored AS (
    -- Combine scores (weighted)
    SELECT
        *,
        (0.4 * text_rank) + (0.6 * vector_score) AS hybrid_score
    FROM vector_scored
)
SELECT id, content, section_title, text_rank, vector_score, hybrid_score
FROM hybrid_scored
ORDER BY hybrid_score DESC
LIMIT 10;

-- Expected result: Chunks mentioning "PO 12345" + semantically related PO procedures
-- Total time: ~70ms


-- ============================================================================
-- EXAMPLE 7: Multi-entity query
-- ============================================================================

-- "How do I process a return with a damaged pallet?"
-- Multiple entities: return, damage, pallet

-- Input parameters:
-- $entities: ['return', 'damage', 'pallet']
-- $intent: 'how_to'

WITH smart_candidates AS (
    SELECT
        id, content, section_title, embedding, importance,
        process_name, process_step,
        cardinality(entities & :entities) AS entity_match_count  -- Count overlaps
    FROM enterprise.documents
    WHERE
        is_active = TRUE
        AND :user_department = ANY(department_access)
        AND 'how_to' = ANY(query_types)
        AND entities && :entities  -- At least one entity overlap
),
scored AS (
    SELECT
        *,
        1 - (embedding <=> :query_embedding) AS similarity
    FROM smart_candidates
    WHERE embedding IS NOT NULL
),
threshold_results AS (
    SELECT * FROM scored
    WHERE similarity >= 0.6
)
SELECT
    id, content, section_title, process_name, process_step,
    entity_match_count, similarity, importance
FROM threshold_results
ORDER BY
    entity_match_count DESC,  -- More entity matches = more relevant
    importance DESC,
    similarity DESC,
    process_step ASC NULLS LAST
;

-- Expected result: Return procedures mentioning damage AND pallets first,
-- then general return procedures, then damage handling procedures
-- Total time: ~85ms


-- ============================================================================
-- EXAMPLE 8: Role-based retrieval
-- ============================================================================

-- Get all procedures relevant to a specific role
-- "Show me everything a credit analyst needs to know"

-- Input parameters:
-- $user_role: 'credit_analyst'
-- $user_department: 'credit'

SELECT
    id,
    content,
    section_title,
    process_name,
    importance,
    complexity,
    query_types
FROM enterprise.documents
WHERE
    is_active = TRUE
    AND :user_department = ANY(department_access)
    AND :user_role = ANY(actors)  -- Procedures involving this role
ORDER BY
    importance DESC,
    process_name ASC,
    process_step ASC NULLS LAST
;

-- Returns all credit analyst procedures, ordered by importance and process
-- Total time: ~20ms (no vector search, pure filters)


-- ============================================================================
-- EXAMPLE 9: Cluster-based browsing
-- ============================================================================

-- User browsed to cluster 5 ("Credit Policies"), show all chunks in cluster

SELECT
    id,
    section_title,
    content,
    importance,
    process_name,
    1 - (embedding <=> :query_embedding) AS similarity
FROM enterprise.documents
WHERE
    cluster_id = 5
    AND is_active = TRUE
    AND :user_department = ANY(department_access)
ORDER BY
    importance DESC,
    similarity DESC
LIMIT 50;

-- Returns all chunks in "Credit Policies" cluster, ordered by importance
-- Total time: ~30ms


-- ============================================================================
-- EXAMPLE 10: Exception handling (troubleshooting)
-- ============================================================================

-- "The credit memo was rejected, what do I do?"
-- Intent: troubleshoot, Condition: exception/error

WITH smart_candidates AS (
    SELECT
        id, content, section_title, embedding, importance,
        see_also_ids, prerequisite_ids
    FROM enterprise.documents
    WHERE
        is_active = TRUE
        AND :user_department = ANY(department_access)
        AND 'troubleshoot' = ANY(query_types)  -- Troubleshooting content
        AND ('exception' = ANY(conditions) OR 'error' = ANY(conditions))
        AND 'credit_memo' = ANY(entities)
        AND 'reject' = ANY(verbs)
),
scored AS (
    SELECT
        *,
        1 - (embedding <=> :query_embedding) AS similarity
    FROM smart_candidates
    WHERE embedding IS NOT NULL
),
threshold_results AS (
    SELECT * FROM scored
    WHERE similarity >= 0.6
),
expanded AS (
    -- Expand to related troubleshooting
    SELECT DISTINCT
        d.id, d.content, d.section_title, d.importance,
        CASE
            WHEN d.id = t.id THEN 'primary'
            WHEN d.id = ANY(t.see_also_ids) THEN 'see_also'
            WHEN d.id = ANY(t.prerequisite_ids) THEN 'prerequisite'
        END AS relationship,
        COALESCE(1 - (d.embedding <=> :query_embedding), 0) AS similarity
    FROM threshold_results t
    CROSS JOIN LATERAL (
        SELECT id, content, section_title, importance, embedding
        FROM enterprise.documents
        WHERE id = t.id
           OR id = ANY(t.see_also_ids)
           OR id = ANY(t.prerequisite_ids)
    ) d
)
SELECT * FROM expanded
ORDER BY
    CASE relationship
        WHEN 'primary' THEN 1
        WHEN 'prerequisite' THEN 2
        WHEN 'see_also' THEN 3
    END,
    importance DESC,
    similarity DESC
;

-- Returns: Primary troubleshooting steps + prerequisites + related procedures
-- Total time: ~95ms


-- ============================================================================
-- PERFORMANCE COMPARISON
-- ============================================================================

/*
DUMB RAG (baseline):
    SELECT * FROM documents
    ORDER BY embedding <=> $query_embedding
    LIMIT 5;

    - Scans ALL 10,000 embeddings
    - Cosine similarity on 10,000 × 1024 dims
    - Time: 300-500ms
    - Quality: Random hits, misses context

SMART RAG (this design):
    1. Pre-filter to 50 candidates (10ms)
    2. Vector search on 50 embeddings (30ms)
    3. Threshold filter (5ms)
    4. Order by importance (5ms)
    5. Expand relationships (20ms)
    - Total: 70-100ms
    - Quality: Precise, contextual, complete

Performance gain: 3-5x faster
Quality gain: Immeasurable (threshold > top-N, relationships, structure)
*/


-- ============================================================================
-- QUERY OPTIMIZATION NOTES
-- ============================================================================

-- 1. Always use is_active = TRUE first (most selective B-tree filter)
-- 2. Use GIN array filters before vector search (reduces candidate set)
-- 3. Use EXPLAIN ANALYZE to verify index usage:

EXPLAIN ANALYZE
SELECT * FROM enterprise.documents
WHERE is_active = TRUE
  AND 'how_to' = ANY(query_types)
  AND 'credit_memo' = ANY(entities);

-- Expected: Bitmap Index Scan on idx_documents_query_types, idx_documents_entities

-- 4. If query is slow, check if indexes are present:

SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'documents'
  AND schemaname = 'enterprise';

-- 5. After bulk insert, always run VACUUM ANALYZE:

VACUUM ANALYZE enterprise.documents;


-- ============================================================================
-- PYTHON WRAPPER EXAMPLE
-- ============================================================================

/*
from typing import List, Dict
import asyncpg

async def smart_rag_retrieve(
    query_text: str,
    query_embedding: List[float],
    user_department: str,
    intent: str = None,
    entities: List[str] = None,
    verbs: List[str] = None,
    threshold: float = 0.6
) -> List[Dict]:
    """
    Smart RAG retrieval with pre-filtering and threshold-based results.
    """
    query = """
    WITH smart_candidates AS (
        SELECT id, content, section_title, source_file, embedding, importance,
               process_name, process_step, see_also_ids, prerequisite_ids
        FROM enterprise.documents
        WHERE is_active = TRUE
          AND $1 = ANY(department_access)
          AND ($2::TEXT IS NULL OR $2 = ANY(query_types))
          AND ($3::TEXT[] IS NULL OR entities && $3)
          AND ($4::TEXT[] IS NULL OR verbs && $4)
    ),
    scored AS (
        SELECT *, 1 - (embedding <=> $5::vector) AS similarity
        FROM smart_candidates
        WHERE embedding IS NOT NULL
    )
    SELECT id, content, section_title, source_file, importance,
           process_name, process_step, similarity
    FROM scored
    WHERE similarity >= $6
    ORDER BY importance DESC, similarity DESC, process_step ASC NULLS LAST
    """

    rows = await conn.fetch(
        query,
        user_department,
        intent,
        entities,
        verbs,
        query_embedding,
        threshold
    )

    return [dict(row) for row in rows]

# Usage:
results = await smart_rag_retrieve(
    query_text="How do I approve a credit memo?",
    query_embedding=embedder.embed(query_text),
    user_department="credit",
    intent="how_to",
    entities=["credit_memo"],
    verbs=["approve"],
    threshold=0.6
)

# Returns 7-12 relevant chunks in <100ms
*/
