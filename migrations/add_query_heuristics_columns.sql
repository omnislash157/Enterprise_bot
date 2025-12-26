-- ============================================================================
-- Migration: Add Query Heuristics Columns
-- Date: 2025-12-26
-- Description: Adds new columns to enterprise.query_log table for enhanced
--              heuristics-based query analysis. This enables tracking of:
--              - Query complexity and specificity scores
--              - Intent type classification
--              - Temporal urgency detection
--              - Department context inference (based on content, not dropdown)
--              - Session pattern detection
-- ============================================================================

-- Add new columns to query_log table for enhanced heuristics
-- All columns are nullable for backward compatibility

ALTER TABLE enterprise.query_log
ADD COLUMN IF NOT EXISTS complexity_score FLOAT,
ADD COLUMN IF NOT EXISTS intent_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS specificity_score FLOAT,
ADD COLUMN IF NOT EXISTS temporal_urgency VARCHAR(20),
ADD COLUMN IF NOT EXISTS is_multi_part BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS department_context_inferred VARCHAR(100),
ADD COLUMN IF NOT EXISTS department_context_scores JSONB,
ADD COLUMN IF NOT EXISTS session_pattern VARCHAR(50);

-- ============================================================================
-- Performance Indexes
-- ============================================================================

-- Index on inferred department context for fast filtering by department
CREATE INDEX IF NOT EXISTS idx_query_log_dept_context
ON enterprise.query_log(department_context_inferred);

-- Index on intent type for query intent breakdown analytics
CREATE INDEX IF NOT EXISTS idx_query_log_intent_type
ON enterprise.query_log(intent_type);

-- Index on complexity score for complexity distribution queries
CREATE INDEX IF NOT EXISTS idx_query_log_complexity
ON enterprise.query_log(complexity_score);

-- Index on temporal urgency for urgency distribution analytics
CREATE INDEX IF NOT EXISTS idx_query_log_temporal_urgency
ON enterprise.query_log(temporal_urgency);

-- GIN index for JSONB department context scores (enables efficient JSON queries)
CREATE INDEX IF NOT EXISTS idx_query_log_dept_scores_gin
ON enterprise.query_log USING GIN(department_context_scores);

-- ============================================================================
-- Column Documentation
-- ============================================================================

COMMENT ON COLUMN enterprise.query_log.complexity_score IS
'Query complexity score (0-1) based on sentence count, question depth, conditional phrases, and multi-criteria requests. Higher scores indicate more complex queries requiring deeper reasoning.';

COMMENT ON COLUMN enterprise.query_log.intent_type IS
'Query intent classification: INFORMATION_SEEKING (what is, tell me about), ACTION_ORIENTED (how do i, steps to), DECISION_SUPPORT (should i, which option), VERIFICATION (is it correct, confirm)';

COMMENT ON COLUMN enterprise.query_log.specificity_score IS
'Query specificity score (0-1) based on named entities, numerical values, and specific technical terms vs generic language. Higher scores indicate more targeted, specific queries.';

COMMENT ON COLUMN enterprise.query_log.temporal_urgency IS
'Urgency level detected from query text: LOW (no temporal indicators), MEDIUM (soon, this week), HIGH (today, now, urgent), URGENT (immediately, asap, emergency)';

COMMENT ON COLUMN enterprise.query_log.is_multi_part IS
'Whether query contains multiple questions or parts (detected via multiple question marks, "and also", "additionally", numbered lists)';

COMMENT ON COLUMN enterprise.query_log.department_context_inferred IS
'Primary department inferred from query content using keyword analysis (not from dropdown selection). Values: warehouse, hr, it, finance, safety, maintenance, general';

COMMENT ON COLUMN enterprise.query_log.department_context_scores IS
'Probability distribution over all departments based on content analysis (JSON format). Example: {"warehouse": 0.7, "safety": 0.2, "hr": 0.1}. Enables multi-department query tracking.';

COMMENT ON COLUMN enterprise.query_log.session_pattern IS
'Detected session pattern based on query sequence: EXPLORATORY (diverse topics), FOCUSED (repeated same topic), TROUBLESHOOTING_ESCALATION (increasing frustration), ONBOARDING (procedural sequence)';

-- ============================================================================
-- Migration Complete
-- ============================================================================
--
-- Next Steps:
-- 1. Verify migration success: SELECT column_name FROM information_schema.columns
--    WHERE table_schema = 'enterprise' AND table_name = 'query_log';
-- 2. Check indexes: SELECT indexname FROM pg_indexes
--    WHERE tablename = 'query_log' AND schemaname = 'enterprise';
-- 3. Deploy query_heuristics.py to begin populating new columns
-- 4. Monitor query performance with EXPLAIN ANALYZE
--
-- Rollback (if needed):
-- ALTER TABLE enterprise.query_log
-- DROP COLUMN IF EXISTS complexity_score,
-- DROP COLUMN IF EXISTS intent_type,
-- DROP COLUMN IF EXISTS specificity_score,
-- DROP COLUMN IF EXISTS temporal_urgency,
-- DROP COLUMN IF EXISTS is_multi_part,
-- DROP COLUMN IF EXISTS department_context_inferred,
-- DROP COLUMN IF EXISTS department_context_scores,
-- DROP COLUMN IF EXISTS session_pattern;
--
-- DROP INDEX IF EXISTS enterprise.idx_query_log_dept_context;
-- DROP INDEX IF EXISTS enterprise.idx_query_log_intent_type;
-- DROP INDEX IF EXISTS enterprise.idx_query_log_complexity;
-- DROP INDEX IF EXISTS enterprise.idx_query_log_temporal_urgency;
-- DROP INDEX IF EXISTS enterprise.idx_query_log_dept_scores_gin;
-- ============================================================================
