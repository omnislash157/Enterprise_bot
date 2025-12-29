# Enhanced LLM Ingestion Pipeline - Implementation Plan

**Date:** 2024-12-22
**Priority:** HIGH - Foundational RAG Enhancement
**Philosophy:** Spend aggressively at ingest time ($4-6 per 500 chunks) to save $100+ in bad retrievals and user frustration

---

## Executive Summary

This document details the implementation of an enhanced ingestion pipeline that uses 3-5 LLM calls per chunk to generate:
- **Synthetic questions** (the secret weapon for query matching)
- **Quality scores** (completeness, actionability, importance)
- **Key concepts** (acronyms, jargon, numeric thresholds)
- **Relationships** (prerequisites, see-also, process chains)

**Cost:** ~$6.50 for 500 chunks (well within $26 budget at 4x baseline)
**Benefit:** Dramatically improved retrieval precision through pre-computed metadata

---

## Architecture Overview

```
Raw Chunks → Phase 1 (Per-Chunk) → Phase 2 (Cross-Chunk) → Phase 3 (QA) → Database
              ├─ Semantic tagging     ├─ Process chains    ├─ Spot checks
              ├─ Question generation  ├─ Prerequisites     └─ Edge cases
              ├─ Quality scoring      ├─ Lateral links
              └─ Concept extraction   └─ Contradictions
```

### Files to Create

1. **`memory/ingest/smart_tagger.py`** - Phase 1 per-chunk enrichment
2. **`memory/ingest/relationship_builder.py`** - Phase 2 cross-chunk analysis
3. **`memory/ingest/enrichment_pipeline.py`** - Main orchestrator
4. **`db/migrations/003_smart_documents.sql`** - Core schema (✅ DONE)
5. **`db/migrations/003b_enrichment_columns.sql`** - Enrichment columns (✅ DONE)

---

## Phase 1: Per-Chunk Enrichment

**Location:** `memory/ingest/smart_tagger.py`
**Parallelizable:** Yes (20 chunks at a time)
**Cost:** ~$1.50 per 500 chunks

### Pass 1.1: Semantic Classification

**Model:** Grok Fast ($0.50/M tokens)
**Input:** Chunk content + section + department
**Output:**
```python
{
    "query_types": ["how_to", "policy"],
    "verbs": ["approve", "submit", "escalate"],
    "entities": ["credit_memo", "customer"],
    "actors": ["credit_analyst", "supervisor"],
    "conditions": ["over_limit", "dispute"],
    "is_procedure": True,
    "is_policy": True,
    "is_form": False
}
```

**Prompt Strategy:**
- Exhaustive instructions: "Be thorough - missing tags mean missed retrievals"
- Domain-specific vocabulary provided
- Examples from food distribution context

### Pass 1.2: Synthetic Question Generation

**Model:** Grok Fast
**Input:** Chunk content + section title
**Output:**
```python
{
    "questions": [
        {"text": "How do I void a credit memo?", "complexity": 1},
        {"text": "What if customer disputes credit?", "complexity": 2},
        {"text": "Can I backdate a credit for last month?", "complexity": 3},
        {"text": "System won't let me submit - what's missing?", "complexity": 1},
        {"text": "Who approves credits over $50k?", "complexity": 2}
    ]
}
```

**Key Innovation:** These questions are embedded separately and matched against user queries. This is MORE effective than content embedding alone because:
- User queries are questions, not statements
- Matching "How do I X?" to "How do I X?" is more reliable than matching to procedural text
- 5 questions per chunk = 5x surface area for retrieval

### Pass 1.3: Quality & Importance Scoring

**Model:** Grok Fast
**Input:** Chunk content + metadata
**Output:**
```python
{
    "importance": 7,          # 1-10: How critical is this?
    "specificity": 5,         # 1-10: How narrow is the use case?
    "complexity": 4,          # 1-10: What expertise is needed?
    "completeness": 8,        # 1-10: Is this self-contained?
    "actionability": 9,       # 1-10: Can user act immediately?
    "confidence": 0.85,       # 0-1: LLM's confidence
    "reasoning": "Core credit process, well-documented steps"
}
```

**Usage:** These scores enable:
- Ranking results by importance
- Filtering out incomplete fragments
- Identifying actionable content for "how to" queries

### Pass 1.4: Key Concept Extraction

**Model:** Grok Fast
**Input:** Chunk content
**Output:**
```python
{
    "acronyms": {
        "BOL": "Bill of Lading",
        "PO": "Purchase Order"
    },
    "jargon": {
        "cross-dock": "Transfer without storage",
        "drop ship": "Direct vendor to customer"
    },
    "numeric_thresholds": {
        "credit_approval_limit": {
            "value": 50000,
            "unit": "USD",
            "context": "Supervisor approval required above"
        }
    }
}
```

**Usage:**
- Helps new employees understand domain terms
- Enables queries like "What's the credit limit?"
- Can be displayed as tooltips in UI

---

## Phase 2: Cross-Chunk Relationships

**Location:** `memory/ingest/relationship_builder.py`
**Requires:** All chunks from Phase 1
**Cost:** ~$3.00 per 500 chunks

### Pass 2.1: Process Chain Detection

**Model:** Claude Haiku (better at structured reasoning)
**Scope:** All chunks from same source document
**Input:** Array of all chunks from document
**Output:**
```python
{
    "processes": [
        {
            "process_name": "credit_memo_creation",
            "steps": [
                {"chunk_index": 2, "step_number": 1, "description": "Initiate"},
                {"chunk_index": 3, "step_number": 2, "description": "Enter details"},
                {"chunk_index": 5, "step_number": 3, "description": "Submit"}
            ]
        }
    ]
}
```

**Strategy:**
- Run once per document (not per chunk)
- Identify multi-step procedures
- Assign process_name and process_step
- Auto-compute follows_ids arrays

### Pass 2.2: Prerequisite Inference

**Model:** Grok Fast
**Scope:** Embedding-similar pairs (top 20 similar chunks)
**Input:** Chunk A + Chunk B
**Output:**
```python
{
    "is_prerequisite": True,
    "confidence": 0.85,
    "reasoning": "Chunk A defines terms used in B"
}
```

**Optimization:** Only check prerequisite relationship for pairs with cosine similarity > 0.7

### Pass 2.3: Lateral Connections (See Also)

**Model:** Grok Fast
**Scope:** Similar chunks from different sections
**Input:** Chunk A + Chunk B
**Output:**
```python
{
    "is_related": True,
    "relationship_type": "complementary",  # or "alternative", "exception"
    "confidence": 0.75,
    "reasoning": "Both discuss credit memos - A is creation, B is voiding"
}
```

**Usage:** Powers "Related Topics" UI and context expansion

### Pass 2.4: Contradiction Detection

**Model:** Claude Haiku (better at nuanced comparison)
**Scope:** Similar chunks with different dates
**Input:** Older chunk + Newer chunk
**Output:**
```python
{
    "has_conflict": True,
    "conflict_type": "supersession",  # or "contradiction", "ambiguity"
    "severity": "moderate",
    "details": "B updates approval threshold from $25k to $50k",
    "recommendation": "B supersedes A"
}
```

**Critical:** Prevents returning contradictory information

### Pass 2.5: Cluster Labeling

**Model:** Claude Haiku
**Scope:** All chunks in same HDBSCAN cluster
**Input:** Array of 5-10 representative chunks from cluster
**Output:**
```python
{
    "cluster_label": "Credit Memo Approval Procedures",
    "description": "Procedures for creating, reviewing, and approving customer credit memos",
    "key_concepts": ["credit memo", "approval workflow", "credit limits"]
}
```

**Usage:** Enables cluster-based expansion and topic browsing

---

## Phase 3: Quality Assurance

**Location:** Within `enrichment_pipeline.py`
**Scope:** 10% sample + edge cases
**Cost:** ~$0.50 per 500 chunks

### Pass 3.1: Spot Check (10% Sample)

- Random 10% of chunks
- Verify tag accuracy
- Check question quality
- Flag low-confidence extractions for human review

### Pass 3.2: Edge Case Review

Automatically flag:
- Chunks < 100 chars (may be table headers or fragments)
- Chunks with < 3 total tags (poor extraction)
- Chunks with zero relationships (isolated content)
- Chunks with confidence_score < 0.7

---

## Implementation Strategy

### Class Structure

```python
# memory/ingest/smart_tagger.py
class SmartTagger:
    """Phase 1: Per-chunk LLM enrichment."""

    async def classify_semantics(chunk: dict) -> dict:
        """Pass 1.1: Extract query_types, verbs, entities, actors, conditions."""

    async def generate_questions(chunk: dict) -> dict:
        """Pass 1.2: Generate 5 synthetic questions."""

    async def score_quality(chunk: dict) -> dict:
        """Pass 1.3: Score importance, completeness, actionability."""

    async def extract_concepts(chunk: dict) -> dict:
        """Pass 1.4: Extract acronyms, jargon, numeric thresholds."""

    async def enrich_chunk(chunk: dict) -> dict:
        """Run all Phase 1 passes on single chunk."""

    async def enrich_batch(chunks: list[dict], batch_size: int = 20) -> list[dict]:
        """Process chunks in parallel batches."""


# memory/ingest/relationship_builder.py
class RelationshipBuilder:
    """Phase 2: Cross-chunk relationship inference."""

    async def detect_process_chains(chunks_by_doc: dict) -> dict:
        """Pass 2.1: Identify multi-step procedures."""

    async def infer_prerequisites(chunks: list[dict]) -> dict:
        """Pass 2.2: Build prerequisite graph."""

    async def find_lateral_connections(chunks: list[dict]) -> dict:
        """Pass 2.3: Find see-also relationships."""

    async def detect_contradictions(chunks: list[dict]) -> dict:
        """Pass 2.4: Flag conflicting information."""

    async def generate_cluster_labels(clusters: dict) -> dict:
        """Pass 2.5: Create human-readable cluster names."""

    async def build_all_relationships(chunks: list[dict]) -> list[dict]:
        """Run all Phase 2 passes."""


# memory/ingest/enrichment_pipeline.py
class EnrichmentPipeline:
    """Main orchestrator for enhanced ingestion."""

    def __init__(self, db_config: dict, llm_config: dict):
        self.tagger = SmartTagger(llm_config)
        self.relationship_builder = RelationshipBuilder(llm_config)
        self.embedder = AsyncEmbedder(provider="deepinfra")

    async def run(self, chunks: list[dict]) -> dict:
        """
        Full pipeline:
        1. Phase 1: Enrich all chunks in parallel
        2. Embed content + synthetic questions
        3. Phase 2: Build relationships
        4. Phase 3: QA checks
        5. Insert into database
        """
```

### Database Integration

After enrichment, insert into `enterprise.documents`:

```python
async def insert_enriched_chunks(chunks: list[dict], conn):
    """Insert enriched chunks into enterprise.documents table."""

    for chunk in chunks:
        await conn.execute("""
            INSERT INTO enterprise.documents (
                -- Core fields
                source_file, department_id, section_title, content,
                content_length, token_count,

                -- Embeddings
                embedding, synthetic_questions_embedding,

                -- Phase 1: Semantic tags
                query_types, verbs, entities, actors, conditions,
                is_procedure, is_policy, is_form,

                -- Phase 1: Quality scores
                importance, specificity, complexity,
                completeness_score, actionability_score, confidence_score,

                -- Phase 1: Key concepts
                acronyms, jargon, numeric_thresholds,
                synthetic_questions,

                -- Phase 2: Relationships
                process_name, process_step,
                prerequisite_ids, see_also_ids, follows_ids,

                -- Phase 2: Quality flags
                contradiction_flags, needs_review, review_reason,

                -- Access control
                department_access, is_active
            ) VALUES (...)
        """)
```

---

## Enhanced Retrieval

With enriched data, retrieval becomes:

```python
async def smart_retrieve(query: str, department: str, user_role: str) -> list[dict]:
    # 1. Embed query once
    query_embedding = await embed(query)

    # 2. Extract query intent (cheap, fast)
    intent = await classify_query_intent(query)  # Returns: query_types, entities, verbs

    # 3. Dual-embedding retrieval
    results = await db.fetch("""
        WITH scored AS (
            SELECT
                d.*,
                -- Content similarity
                1 - (d.embedding <=> $1::vector) AS content_sim,
                -- Question similarity (THE SECRET WEAPON)
                1 - (d.synthetic_questions_embedding <=> $1::vector) AS question_sim,
                -- Tag overlap bonuses
                CASE WHEN d.query_types && $4::text[] THEN 0.1 ELSE 0 END AS type_bonus,
                CASE WHEN d.entities && $5::text[] THEN 0.1 ELSE 0 END AS entity_bonus
            FROM enterprise.documents d
            WHERE d.is_active = TRUE
              AND $2 = ANY(d.department_access)
              AND (d.requires_role IS NULL OR d.requires_role && $3::text[])
        )
        SELECT *,
            -- Combined score: weight question matching heavily
            (0.3 * content_sim) +          -- 30% content
            (0.5 * question_sim) +         -- 50% questions (!)
            (0.2 * (type_bonus + entity_bonus)) AS combined_score
        FROM scored
        WHERE question_sim >= 0.6 OR content_sim >= 0.6
        ORDER BY combined_score DESC, importance DESC
        LIMIT 20
    """, query_embedding, department, [user_role], intent.query_types, intent.entities)

    # 4. Expand with prerequisites (for top 5 results)
    expanded = await expand_with_prerequisites([r.id for r in results[:5]])

    return expanded
```

**Key Innovation:** 50% weight on `synthetic_questions_embedding` means we're primarily matching "what questions does this answer?" rather than "what does this say?" - much more aligned with how users query.

---

## Cost Analysis (500 Chunks)

| Pass | Calls | Tokens/Call | Model | Cost |
|------|-------|-------------|-------|------|
| **Phase 1** |
| 1.1 Semantic | 500 | 800 | Grok Fast | $0.50 |
| 1.2 Questions | 500 | 600 | Grok Fast | $0.40 |
| 1.3 Scoring | 500 | 500 | Grok Fast | $0.30 |
| 1.4 Concepts | 500 | 400 | Grok Fast | $0.25 |
| **Phase 2** |
| 2.1 Process | 50 (per doc) | 2000 | Claude Haiku | $2.00 |
| 2.2-2.3 Relations | ~2500 (pairs) | 600 | Grok Fast | $1.50 |
| 2.4 Contradictions | ~500 (pairs) | 800 | Claude Haiku | $1.00 |
| 2.5 Cluster Labels | ~20 | 1000 | Claude Haiku | $0.50 |
| **Phase 3** |
| 3.1 Spot Check | 50 (10%) | 500 | Grok Fast | $0.05 |
| **Embeddings** |
| Content | 500 | - | BGE-M3 | $0.00 |
| Questions | 2500 (5 per) | - | BGE-M3 | $0.00 |

**Total: ~$6.50** for 500 chunks
**Budget: $26** (4x baseline) - plenty of headroom

---

## Success Metrics

After enrichment, validate:

```sql
-- Enrichment coverage
SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE enrichment_complete) as enriched,
    COUNT(*) FILTER (WHERE array_length(synthetic_questions, 1) >= 5) as has_questions,
    COUNT(*) FILTER (WHERE importance IS NOT NULL) as has_scores,
    COUNT(*) FILTER (WHERE has_relationships) as has_relations,
    COUNT(*) FILTER (WHERE needs_review) as needs_review
FROM enterprise.documents;
```

**Target Metrics:**
- ✅ 100% chunks have `synthetic_questions` (5 per chunk)
- ✅ 95%+ chunks have importance/completeness/actionability scores
- ✅ 80%+ chunks have at least one relationship
- ✅ 100% process chunks have `process_name` + `process_step`
- ✅ <5% chunks flagged for human review

---

## Implementation Timeline

### Week 1: Phase 1 Implementation
- Day 1-2: Build `smart_tagger.py` with all 4 passes
- Day 3: Test on 50 chunks, validate output quality
- Day 4-5: Run on full Driscoll corpus (500 chunks)

### Week 2: Phase 2 Implementation
- Day 1-2: Build `relationship_builder.py`
- Day 3: Test relationship detection on 50 chunks
- Day 4-5: Run on full corpus, validate graph structure

### Week 3: Integration
- Day 1-2: Build `enrichment_pipeline.py` orchestrator
- Day 3: Test full pipeline end-to-end
- Day 4: Run database migration and ingest
- Day 5: Build enhanced retrieval function

### Week 4: Validation & Tuning
- Day 1-2: Human QA on 10% sample
- Day 3: Adjust prompts based on QA findings
- Day 4: Re-run enrichment on flagged chunks
- Day 5: Performance testing and optimization

---

## Next Steps

1. **Create `smart_tagger.py`** with Phase 1 passes
2. **Create `relationship_builder.py`** with Phase 2 passes
3. **Create `enrichment_pipeline.py`** orchestrator
4. **Run database migrations** (003 + 003b)
5. **Test on 50 chunks** from Driscoll manuals
6. **Run full ingestion** on 500-chunk corpus
7. **Build enhanced retrieval** with dual-embedding search
8. **Measure improvement** (precision/recall on test queries)

---

## Open Questions

1. **LLM Provider Mix:** Should we use Claude Haiku for all passes (higher quality) or Grok Fast (cheaper)?
   - **Recommendation:** Grok Fast for Phase 1 (volume), Claude Haiku for Phase 2 (reasoning)

2. **Relationship Candidate Pool:** Top 20 similar chunks per chunk = ~10k comparisons for 500 chunks. Is this too many?
   - **Recommendation:** Start with top 10, expand if recall is poor

3. **Cluster Algorithm:** HDBSCAN vs K-means for clustering?
   - **Recommendation:** HDBSCAN (already in codebase, handles variable density)

4. **Question Embedding Strategy:** Average of 5 question embeddings vs concatenate and re-embed?
   - **Recommendation:** Average (preserves semantic space, cheaper)

---

## References

- Schema: `db/migrations/003_smart_documents.sql`
- Enrichment columns: `db/migrations/003b_enrichment_columns.sql`
- Existing embedder: `memory/embedder.py`
- Existing tagger: `memory/llm_tagger.py` (for reference)
- Ingestion baseline: `memory/ingest/ingest_to_postgres.py`
