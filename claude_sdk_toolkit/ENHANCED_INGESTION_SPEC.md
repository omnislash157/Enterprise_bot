# Enhanced LLM Ingestion Pipeline

**Philosophy:** Spend aggressively at ingest time. Every dollar here saves $100 in bad retrievals, user frustration, and support escalations.

**Budget:** 4x baseline LLM cost approved. Target 3-5 LLM calls per chunk + 1 relationship-building pass.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: CHUNK ENRICHMENT                    │
│                    (Per-chunk, parallelizable)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Pass 1.1: Semantic Classification                              │
│  ├── query_types, verbs, entities, actors, conditions           │
│  └── is_procedure, is_policy, is_form                           │
│                                                                 │
│  Pass 1.2: Synthetic Question Generation                        │
│  ├── 5 questions this chunk answers                             │
│  └── Question difficulty ratings                                │
│                                                                 │
│  Pass 1.3: Quality & Importance Scoring                         │
│  ├── importance, specificity, complexity (1-10)                 │
│  ├── completeness score (is this chunk self-contained?)         │
│  └── actionability score (can user act on this alone?)          │
│                                                                 │
│  Pass 1.4: Key Concept Extraction                               │
│  ├── Acronyms with expansions                                   │
│  ├── Domain jargon with definitions                             │
│  └── Numeric thresholds/limits mentioned                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                 PHASE 2: RELATIONSHIP BUILDING                  │
│                 (Cross-chunk, requires all data)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Pass 2.1: Process Chain Detection                              │
│  ├── Identify multi-step procedures                             │
│  ├── Assign process_name, process_step                          │
│  └── Build follows_ids chains                                   │
│                                                                 │
│  Pass 2.2: Prerequisite Inference                               │
│  ├── "To understand X, you need Y first"                        │
│  └── Build prerequisite_ids graph                               │
│                                                                 │
│  Pass 2.3: Lateral Connections                                  │
│  ├── "Related but different topic"                              │
│  └── Build see_also_ids                                         │
│                                                                 │
│  Pass 2.4: Contradiction Detection                              │
│  ├── Flag conflicting policies/procedures                       │
│  └── Identify supersedes_id relationships                       │
│                                                                 │
│  Pass 2.5: Cluster Labeling                                     │
│  ├── After HDBSCAN clustering on embeddings                     │
│  └── Generate human-readable cluster_label                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 3: QUALITY ASSURANCE                   │
│                    (Sampling + human-in-loop)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Pass 3.1: Spot Check (10% sample)                              │
│  ├── Verify tag accuracy                                        │
│  ├── Check question quality                                     │
│  └── Flag low-confidence extractions                            │
│                                                                 │
│  Pass 3.2: Edge Case Review                                     │
│  ├── Short chunks (< 100 chars)                                 │
│  ├── Low tag_count chunks                                       │
│  └── Zero-relationship chunks                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Schema Additions

Add these columns to `enterprise.documents`:

```sql
-- SYNTHETIC QUESTIONS (the secret weapon)
synthetic_questions TEXT[] NOT NULL DEFAULT '{}',
-- 5 questions this chunk answers, used for query matching
-- Example: ['How do I void a credit memo?', 'What's the credit void policy?', ...]

synthetic_questions_embedding VECTOR(1024),
-- Average embedding of all synthetic questions (for matching user queries)

-- KEY CONCEPTS
acronyms JSONB DEFAULT '{}',
-- Example: {"BOL": "Bill of Lading", "PO": "Purchase Order"}

jargon JSONB DEFAULT '{}',
-- Example: {"cross-dock": "Transfer without storage", "drop ship": "Direct vendor delivery"}

numeric_thresholds JSONB DEFAULT '{}',
-- Example: {"credit_limit_escalation": 50000, "approval_days": 3}

-- QUALITY METRICS
completeness_score INTEGER CHECK (completeness_score BETWEEN 1 AND 10),
-- 10 = fully self-contained, 1 = requires heavy context

actionability_score INTEGER CHECK (actionability_score BETWEEN 1 AND 10),
-- 10 = user can act immediately, 1 = reference-only

-- CONTRADICTION TRACKING
contradiction_flags TEXT[] DEFAULT '{}',
-- Chunk IDs this might conflict with

confidence_score FLOAT DEFAULT 1.0,
-- LLM's confidence in its own tagging (for QA prioritization)
```

---

## Phase 1: Detailed Prompts

### Pass 1.1: Semantic Classification

```
You are a document analyst for a food distribution company. Analyze this chunk and extract structured metadata.

CHUNK:
---
{content}
---

SECTION: {section_title}
SOURCE: {source_file}
DEPARTMENT: {department_id}

Extract the following. Be thorough - missing tags mean missed retrievals.

1. query_types - What kinds of questions does this answer?
   Options: how_to, policy, troubleshoot, definition, lookup, escalation, reference, compliance, training
   
2. verbs - What actions are described? Include ALL verbs, even implied ones.
   Common: approve, reject, submit, create, void, escalate, review, verify, process, route, receive, ship, return, cancel, modify, lookup, calculate, notify, document
   
3. entities - What domain objects are involved?
   Common: credit_memo, purchase_order, invoice, customer, vendor, return, shipment, pallet, BOL, driver, route, warehouse, dock, inventory, payment, discount, claim
   
4. actors - Who performs or is affected by these actions?
   Common: sales_rep, warehouse_mgr, credit_analyst, purchasing_agent, driver, supervisor, customer, vendor, accounting, dispatch, receiver
   
5. conditions - What triggers, exceptions, or contexts apply?
   Common: exception, dispute, rush_order, new_customer, over_limit, damage, shortage, late_delivery, temperature_violation, cod, prepaid, backorder

6. Document type flags:
   - is_procedure: Does this describe step-by-step instructions?
   - is_policy: Does this state rules, requirements, or compliance?
   - is_form: Does this describe a form, template, or document format?

Return ONLY valid JSON:
{
  "query_types": [...],
  "verbs": [...],
  "entities": [...],
  "actors": [...],
  "conditions": [...],
  "is_procedure": boolean,
  "is_policy": boolean,
  "is_form": boolean
}
```

### Pass 1.2: Synthetic Question Generation

```
You are creating a FAQ for a food distribution company's internal knowledge base.

Given this document chunk, generate 5 DIFFERENT questions that someone might ask that this chunk answers.

CHUNK:
---
{content}
---

SECTION: {section_title}

Requirements:
1. Questions should be natural - how a real employee would ask
2. Vary the phrasing: some direct ("How do I..."), some situational ("What if...")
3. Include at least one question that uses domain jargon
4. Include at least one question from a confused/frustrated employee
5. Rate each question's complexity: basic (1), intermediate (2), advanced (3)

Return JSON:
{
  "questions": [
    {"text": "How do I void a credit memo?", "complexity": 1},
    {"text": "What's the process when a customer disputes a credit amount?", "complexity": 2},
    {"text": "Can I backdate a credit memo for last month's billing cycle?", "complexity": 3},
    {"text": "The system won't let me submit - what am I missing?", "complexity": 1},
    {"text": "Who needs to approve credits over $50k?", "complexity": 2}
  ]
}
```

### Pass 1.3: Quality & Importance Scoring

```
You are evaluating document quality for a knowledge base. Score this chunk on multiple dimensions.

CHUNK:
---
{content}
---

SECTION: {section_title}
SOURCE: {source_file}

Score each dimension 1-10:

1. importance: How critical is this information?
   - 10: Compliance-critical, legal, safety
   - 7-9: Core business process, frequently needed
   - 4-6: Standard procedure, occasional reference
   - 1-3: Nice-to-know, rare edge case

2. specificity: How narrow is the use case?
   - 10: Extremely specific edge case
   - 5: Common but bounded scenario  
   - 1: Broad overview, applies widely

3. complexity: What expertise level is needed?
   - 10: Requires deep domain expertise
   - 5: Needs basic training
   - 1: Anyone could understand

4. completeness: Is this chunk self-contained?
   - 10: Fully answers the question, no other context needed
   - 5: Needs some related info
   - 1: Fragment, requires significant context

5. actionability: Can someone act on this immediately?
   - 10: Clear, specific steps they can take now
   - 5: Informative but needs interpretation
   - 1: Background info only, no direct action

Also provide:
6. confidence: How confident are you in these scores? (0.0-1.0)

Return JSON:
{
  "importance": 7,
  "specificity": 5,
  "complexity": 4,
  "completeness": 8,
  "actionability": 9,
  "confidence": 0.85,
  "reasoning": "Core credit process, well-documented steps, self-contained"
}
```

### Pass 1.4: Key Concept Extraction

```
Extract specialized terminology from this document chunk.

CHUNK:
---
{content}
---

Extract:
1. acronyms: Any abbreviations with their full meanings
2. jargon: Domain-specific terms that might confuse new employees
3. numeric_thresholds: Any specific numbers, limits, or thresholds mentioned

Return JSON:
{
  "acronyms": {
    "BOL": "Bill of Lading",
    "PO": "Purchase Order"
  },
  "jargon": {
    "cross-dock": "Transferring goods directly from receiving to shipping without storage",
    "drop ship": "Shipment sent directly from vendor to customer"
  },
  "numeric_thresholds": {
    "credit_approval_limit": {"value": 50000, "unit": "USD", "context": "Requires supervisor approval above this"},
    "processing_deadline": {"value": 3, "unit": "days", "context": "Credits must be processed within"}
  }
}
```

---

## Phase 2: Relationship Building

### Pass 2.1: Process Chain Detection

This pass operates on ALL chunks from the same source document.

```
You are analyzing a business process document to identify step sequences.

DOCUMENT: {source_file}
CHUNKS:
---
[0] {chunk_0_content}
---
[1] {chunk_1_content}
---
[2] {chunk_2_content}
... (all chunks from this document)

Identify any multi-step processes and map which chunks belong to each step.

For each process found:
1. process_name: Descriptive name (e.g., "credit_approval", "returns_processing")
2. steps: Ordered list of chunk indices that form this process

Return JSON:
{
  "processes": [
    {
      "process_name": "credit_memo_creation",
      "steps": [
        {"chunk_index": 2, "step_number": 1, "description": "Initiate request"},
        {"chunk_index": 3, "step_number": 2, "description": "Enter details"},
        {"chunk_index": 5, "step_number": 3, "description": "Submit for approval"}
      ]
    }
  ]
}
```

### Pass 2.2: Prerequisite Inference

This pass requires embedding similarity + LLM reasoning.

```
Given these two document chunks, determine if there's a prerequisite relationship.

CHUNK A (potential prerequisite):
---
{chunk_a_content}
---

CHUNK B (depends on A?):
---
{chunk_b_content}
---

Questions:
1. Does understanding Chunk B require knowledge from Chunk A?
2. Would reading A first make B clearer?
3. Does A define terms/concepts used in B?

Return JSON:
{
  "is_prerequisite": boolean,
  "confidence": 0.0-1.0,
  "reasoning": "Chunk A defines credit memo structure, Chunk B assumes that knowledge"
}
```

### Pass 2.3: Lateral Connections (See Also)

```
Given these two document chunks from different sections, determine if they're related.

CHUNK A:
---
{chunk_a_content}
SECTION: {a_section}
---

CHUNK B:
---
{chunk_b_content}
SECTION: {b_section}
---

Are these chunks related in a way that someone reading A might want to also see B?

Types of relationships:
- same_entity: Both discuss the same domain object from different angles
- complementary: Different parts of the same overall topic
- alternative: Different approaches to the same problem
- exception: One describes the rule, other describes exceptions

Return JSON:
{
  "is_related": boolean,
  "relationship_type": "same_entity" | "complementary" | "alternative" | "exception" | null,
  "confidence": 0.0-1.0,
  "reasoning": "Both discuss credit memos - A is creation, B is voiding"
}
```

### Pass 2.4: Contradiction Detection

```
Compare these two chunks for potential conflicts or contradictions.

CHUNK A (older or from document A):
---
{chunk_a_content}
SOURCE: {a_source}
DATE: {a_date}
---

CHUNK B (newer or from document B):
---
{chunk_b_content}
SOURCE: {b_source}
DATE: {b_date}
---

Analyze for:
1. Direct contradiction: Conflicting instructions or policies
2. Supersession: B updates/replaces A
3. Ambiguity: Both valid but could confuse users

Return JSON:
{
  "has_conflict": boolean,
  "conflict_type": "contradiction" | "supersession" | "ambiguity" | null,
  "severity": "critical" | "moderate" | "minor" | null,
  "details": "A says 3-day approval, B says same-day for rush orders - not contradictory, B is exception",
  "recommendation": "Link as exception case" | "Flag for human review" | "B supersedes A"
}
```

---

## Implementation Strategy

### Phase 1 Execution (Per-Chunk)

```python
async def enrich_chunk(chunk: dict) -> dict:
    """Run all Phase 1 passes on a single chunk."""
    
    # Run passes in parallel where possible
    classification, questions, scores, concepts = await asyncio.gather(
        classify_semantics(chunk),      # Pass 1.1
        generate_questions(chunk),       # Pass 1.2
        score_quality(chunk),            # Pass 1.3
        extract_concepts(chunk),         # Pass 1.4
    )
    
    # Merge results
    enriched = {
        **chunk,
        **classification,
        "synthetic_questions": [q["text"] for q in questions["questions"]],
        **scores,
        **concepts,
    }
    
    return enriched

# Process all chunks in parallel batches
async def run_phase_1(chunks: list[dict], batch_size: int = 20) -> list[dict]:
    enriched = []
    for batch in chunk_batches(chunks, batch_size):
        results = await asyncio.gather(*[enrich_chunk(c) for c in batch])
        enriched.extend(results)
    return enriched
```

### Phase 2 Execution (Cross-Chunk)

```python
async def build_relationships(enriched_chunks: list[dict]) -> list[dict]:
    """Run Phase 2 passes across all chunks."""
    
    # Group by source document for process detection
    by_source = group_by(enriched_chunks, key="source_file")
    
    # 2.1: Detect process chains within each document
    for source, doc_chunks in by_source.items():
        processes = await detect_process_chains(doc_chunks)
        apply_process_metadata(doc_chunks, processes)
    
    # 2.2 & 2.3: Build prerequisite and see_also relationships
    # Use embedding similarity to find candidates, then LLM to confirm
    for chunk in enriched_chunks:
        candidates = find_similar_chunks(chunk, enriched_chunks, threshold=0.7)
        
        prereqs = await asyncio.gather(*[
            check_prerequisite(candidate, chunk) 
            for candidate in candidates
        ])
        chunk["prerequisite_ids"] = [c.id for c, is_prereq in zip(candidates, prereqs) if is_prereq]
        
        see_also = await asyncio.gather(*[
            check_lateral_relation(candidate, chunk)
            for candidate in candidates
        ])
        chunk["see_also_ids"] = [c.id for c, is_related in zip(candidates, see_also) if is_related]
    
    # 2.4: Contradiction detection (compare within same entity/topic)
    contradictions = await detect_contradictions(enriched_chunks)
    flag_contradictions(enriched_chunks, contradictions)
    
    # 2.5: Cluster labeling (after HDBSCAN)
    clusters = cluster_by_embedding(enriched_chunks)
    for cluster_id, cluster_chunks in clusters.items():
        label = await generate_cluster_label(cluster_chunks)
        for chunk in cluster_chunks:
            chunk["cluster_id"] = cluster_id
            chunk["cluster_label"] = label
    
    return enriched_chunks
```

### Cost Estimation

Assuming ~500 chunks from Driscoll manuals:

| Pass | Calls | Tokens/Call | Model | Cost |
|------|-------|-------------|-------|------|
| 1.1 Semantic | 500 | ~800 | Grok Fast | $0.50 |
| 1.2 Questions | 500 | ~600 | Grok Fast | $0.40 |
| 1.3 Scoring | 500 | ~500 | Grok Fast | $0.30 |
| 1.4 Concepts | 500 | ~400 | Grok Fast | $0.25 |
| 2.1 Process | 50 (per doc) | ~2000 | Claude | $2.00 |
| 2.2-2.3 Relations | ~2500 (pairs) | ~600 | Grok Fast | $1.50 |
| 2.4 Contradictions | ~500 (pairs) | ~800 | Claude | $1.00 |
| 2.5 Cluster Labels | ~20 | ~1000 | Claude | $0.50 |

**Total: ~$6.50** for 500 chunks with full enrichment pipeline.

At 4x baseline, budget is ~$26 - we have headroom for:
- Retry low-confidence extractions
- Expand relationship candidate pools
- Add human-in-loop QA sampling

---

## Retrieval Enhancement

With this enriched data, retrieval becomes:

```python
async def smart_retrieve(query: str, department: str, user_role: str) -> list[dict]:
    # 1. Embed query
    query_embedding = await embed(query)
    
    # 2. Also embed as if it were a question (match synthetic questions)
    # Use the query directly against synthetic_questions_embedding
    
    # 3. Extract query intent
    intent = await classify_query_intent(query)
    # Returns: query_types, likely_entities, likely_verbs
    
    # 4. Smart retrieval with multiple signals
    results = await db.fetch("""
        WITH scored AS (
            SELECT 
                d.*,
                -- Content similarity
                1 - (d.embedding <=> $1::vector) AS content_sim,
                -- Question similarity (matches synthetic questions)
                1 - (d.synthetic_questions_embedding <=> $1::vector) AS question_sim,
                -- Tag overlap bonus
                CASE WHEN d.query_types && $4::text[] THEN 0.1 ELSE 0 END AS type_bonus,
                CASE WHEN d.entities && $5::text[] THEN 0.1 ELSE 0 END AS entity_bonus,
                CASE WHEN d.verbs && $6::text[] THEN 0.05 ELSE 0 END AS verb_bonus
            FROM enterprise.documents d
            WHERE d.is_active = TRUE
              AND $2 = ANY(d.department_access)
              AND (d.requires_role IS NULL OR d.requires_role && $3::text[])
        )
        SELECT *,
            -- Combined score: weight content vs question matching
            (0.4 * content_sim) + 
            (0.4 * question_sim) + 
            (0.2 * (type_bonus + entity_bonus + verb_bonus)) AS combined_score
        FROM scored
        WHERE content_sim >= 0.5 OR question_sim >= 0.6
        ORDER BY combined_score DESC, importance DESC
        LIMIT 20
    """, query_embedding, department, [user_role], 
         intent.query_types, intent.entities, intent.verbs)
    
    # 5. Expand top results with prerequisites
    top_ids = [r.id for r in results[:5]]
    expanded = await expand_with_prerequisites(top_ids)
    
    return expanded
```

---

## Files to Create

1. `memory/ingest/smart_tagger.py` - All Phase 1 prompts and execution
2. `memory/ingest/relationship_builder.py` - Phase 2 cross-chunk analysis
3. `memory/ingest/enrichment_pipeline.py` - Orchestrator for full pipeline
4. `db/migrations/003b_enrichment_columns.sql` - Additional columns for Phase 1 data

---

## Success Metrics

After enrichment:
- 100% chunks have synthetic_questions (5 per chunk)
- 95%+ chunks have importance/completeness/actionability scores
- 80%+ chunks have at least one relationship (prerequisite or see_also)
- 100% process chunks have process_name + process_step
- <5% chunks flagged for human review (contradictions, low confidence)
