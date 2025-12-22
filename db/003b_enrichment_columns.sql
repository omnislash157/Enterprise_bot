-- Migration 003b: Enrichment Columns for Smart RAG
-- Date: 2024-12-22
-- Depends on: 003_smart_documents.sql
--
-- Adds columns for enhanced LLM ingestion pipeline:
-- - Synthetic questions for query matching
-- - Quality metrics (completeness, actionability)
-- - Key concept extraction (acronyms, jargon, thresholds)
-- - Contradiction tracking
-- - Confidence scores

BEGIN;

-- ============================================================================
-- SYNTHETIC QUESTIONS (The Secret Weapon)
-- ============================================================================

-- 5 questions per chunk that this content answers
-- Used for direct query-to-question matching
ALTER TABLE enterprise.documents 
ADD COLUMN IF NOT EXISTS synthetic_questions TEXT[] NOT NULL DEFAULT '{}';

-- Average embedding of all synthetic questions
-- Allows matching user query against "what questions does this answer?"
ALTER TABLE enterprise.documents 
ADD COLUMN IF NOT EXISTS synthetic_questions_embedding VECTOR(1024);

-- Index for question embedding similarity search
CREATE INDEX IF NOT EXISTS idx_documents_questions_embedding 
ON enterprise.documents USING ivfflat (synthetic_questions_embedding vector_cosine_ops)
WITH (lists = 100);

-- ============================================================================
-- QUALITY METRICS
-- ============================================================================

-- Is this chunk self-contained or does it need context?
-- 10 = fully standalone, 1 = needs heavy context
ALTER TABLE enterprise.documents 
ADD COLUMN IF NOT EXISTS completeness_score INTEGER CHECK (completeness_score BETWEEN 1 AND 10);

-- Can someone act on this immediately?
-- 10 = clear actionable steps, 1 = reference only
ALTER TABLE enterprise.documents 
ADD COLUMN IF NOT EXISTS actionability_score INTEGER CHECK (actionability_score BETWEEN 1 AND 10);

-- LLM's confidence in its own tagging (for QA prioritization)
ALTER TABLE enterprise.documents 
ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 1.0 CHECK (confidence_score BETWEEN 0 AND 1);

-- ============================================================================
-- KEY CONCEPT EXTRACTION
-- ============================================================================

-- Acronyms with expansions: {"BOL": "Bill of Lading", "PO": "Purchase Order"}
ALTER TABLE enterprise.documents 
ADD COLUMN IF NOT EXISTS acronyms JSONB DEFAULT '{}';

-- Domain jargon with definitions: {"cross-dock": "Transfer without storage"}
ALTER TABLE enterprise.documents 
ADD COLUMN IF NOT EXISTS jargon JSONB DEFAULT '{}';

-- Numeric thresholds: {"credit_limit": {"value": 50000, "unit": "USD", "context": "..."}}
ALTER TABLE enterprise.documents 
ADD COLUMN IF NOT EXISTS numeric_thresholds JSONB DEFAULT '{}';

-- ============================================================================
-- CONTRADICTION TRACKING
-- ============================================================================

-- Chunk IDs this might conflict with (flagged during Phase 2)
ALTER TABLE enterprise.documents 
ADD COLUMN IF NOT EXISTS contradiction_flags UUID[] DEFAULT '{}';

-- Human review status for contradictions
ALTER TABLE enterprise.documents 
ADD COLUMN IF NOT EXISTS needs_review BOOLEAN DEFAULT FALSE;

ALTER TABLE enterprise.documents 
ADD COLUMN IF NOT EXISTS review_reason TEXT;

-- Index for finding chunks needing review
CREATE INDEX IF NOT EXISTS idx_documents_needs_review 
ON enterprise.documents (needs_review) WHERE needs_review = TRUE;

-- ============================================================================
-- COMPUTED QUALITY INDICATOR
-- ============================================================================

-- Overall enrichment quality (for monitoring)
ALTER TABLE enterprise.documents 
ADD COLUMN IF NOT EXISTS enrichment_complete BOOLEAN 
GENERATED ALWAYS AS (
    COALESCE(array_length(synthetic_questions, 1), 0) >= 3
    AND importance IS NOT NULL
    AND completeness_score IS NOT NULL
    AND confidence_score >= 0.7
) STORED;

CREATE INDEX IF NOT EXISTS idx_documents_enrichment_incomplete
ON enterprise.documents (enrichment_complete) WHERE enrichment_complete = FALSE;

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Get chunks needing enrichment (for retry/backfill)
CREATE OR REPLACE FUNCTION get_unenriched_chunks(limit_count INTEGER DEFAULT 100)
RETURNS TABLE (
    id UUID,
    content TEXT,
    section_title TEXT,
    source_file TEXT
) AS $$
    SELECT id, content, section_title, source_file
    FROM enterprise.documents
    WHERE enrichment_complete = FALSE
      AND is_active = TRUE
    ORDER BY created_at ASC
    LIMIT limit_count;
$$ LANGUAGE SQL;

-- Get chunks with contradictions for human review
CREATE OR REPLACE FUNCTION get_contradiction_review_queue()
RETURNS TABLE (
    id UUID,
    content TEXT,
    contradiction_flags UUID[],
    review_reason TEXT
) AS $$
    SELECT id, content, contradiction_flags, review_reason
    FROM enterprise.documents
    WHERE needs_review = TRUE
      AND is_active = TRUE
    ORDER BY importance DESC;
$$ LANGUAGE SQL;

-- Compute average embedding for synthetic questions
CREATE OR REPLACE FUNCTION compute_question_embedding(question_embeddings VECTOR(1024)[])
RETURNS VECTOR(1024) AS $$
DECLARE
    result FLOAT[1024];
    i INTEGER;
    j INTEGER;
    n INTEGER;
BEGIN
    n := array_length(question_embeddings, 1);
    IF n IS NULL OR n = 0 THEN
        RETURN NULL;
    END IF;
    
    -- Initialize result array
    FOR i IN 1..1024 LOOP
        result[i] := 0;
    END LOOP;
    
    -- Sum all embeddings
    FOR j IN 1..n LOOP
        FOR i IN 1..1024 LOOP
            result[i] := result[i] + (question_embeddings[j])[i];
        END LOOP;
    END LOOP;
    
    -- Average
    FOR i IN 1..1024 LOOP
        result[i] := result[i] / n;
    END LOOP;
    
    RETURN result::VECTOR(1024);
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- ============================================================================
-- POST-MIGRATION
-- ============================================================================

-- After running enrichment pipeline:
-- VACUUM ANALYZE enterprise.documents;
--
-- Monitor enrichment progress:
-- SELECT 
--     COUNT(*) as total,
--     COUNT(*) FILTER (WHERE enrichment_complete) as enriched,
--     COUNT(*) FILTER (WHERE needs_review) as needs_review
-- FROM enterprise.documents;
