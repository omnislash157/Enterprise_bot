# SDK HANDOFF: Smart RAG Schema Design

**Date:** 2024-12-22  
**Priority:** HIGH  
**Mode:** CREATIVE ENGINEERING  
**Deliverable:** Migration 003 SQL + Updated ingestion mapping  

---

## MISSION

Design a **devilishly clever** document schema that makes vector search trivially easy by doing the hard work at ingest time.

**Creative freedom:** ON  
**Constraints:** Yes, but minimal  
**Goal:** Make the embedder's job so easy it returns lights-out relevant chunks in <100ms

---

## THE PHILOSOPHY

### Old RAG (Dumb)
```
Query → Embed → cosine(query, ALL_CHUNKS) → sort → top 5
Result: Slow, noisy, misses connections
```

### New RAG (Smart)
```
Query → Classify intent/entities → Pre-filter to tiny candidate set → Threshold search → ALL relevant chunks
Result: Fast, precise, shows connections
```

### The Key Insight

**Don't return "top N most similar."**  
**Return "everything above 0.6 threshold."**

Why? 
- ADHD-friendly: show me all the related things, let me see the web
- Cross-training: related procedures surface naturally
- Process development: see how things connect across departments
- No arbitrary cutoffs: if it's relevant, include it

---

## DESIGN CONSTRAINTS

### Hard Requirements

1. **Single table** - No joins for retrieval queries
2. **All tags computed at ingest** - Zero computation at query time
3. **GIN indexes on arrays** - Sub-10ms filtering
4. **IVFFlat on vectors** - Fast cosine similarity
5. **Threshold-based retrieval** - Not top-N, but score >= 0.6
6. **Works with existing JSON chunks** - Source data in `Manuals/Driscoll/*.json`

### Soft Requirements

1. Hierarchical chunk relationships (parent/child/sibling)
2. Process sequencing (step 1 → step 2 → step 3)
3. Cross-department linking (credit process touches sales + warehouse)
4. Heuristic scoring (importance, specificity)

### Anti-Requirements (Don't Do)

1. No separate tables for tags/categories (denormalize everything)
2. No query-time LLM calls for classification
3. No external services for tagging
4. No over-engineering - clever, not complex

---

## SEMANTIC DIMENSIONS TO CONSIDER

These are suggestions. Add, remove, combine as you see fit.

### Intent Classification
What kind of question does this chunk answer?

```sql
query_types text[]  -- ['how_to', 'lookup', 'policy', 'troubleshoot', 'definition', 'escalation']
```

Retrieval: `'how_to' = ANY(query_types)` before vector search

### Action Verbs
What actions are described?

```sql
verbs text[]  -- ['approve', 'reject', 'submit', 'create', 'void', 'escalate', 'review']
```

Retrieval: `'approve' = ANY(verbs)` narrows to approval procedures

### Entity Tags  
What objects/concepts are involved?

```sql
entities text[]  -- ['credit_memo', 'purchase_order', 'invoice', 'customer', 'vendor', 'return']
```

Retrieval: `'credit_memo' = ANY(entities)` narrows to credit domain

### Actor Roles
Who performs this action?

```sql
actors text[]  -- ['sales_rep', 'warehouse_mgr', 'credit_analyst', 'purchasing_agent']
```

Retrieval: Filter by user's role for personalized results

### Process Structure
Where does this fit in a workflow?

```sql
process_name text       -- 'credit_approval', 'returns_processing', 'new_vendor_onboarding'
process_step int        -- 1, 2, 3... (NULL if not procedural)
is_procedure bool       -- Quick filter for step-by-step content
```

Retrieval: Get all steps in a process, ordered

### Heuristic Scores
Pre-computed relevance signals:

```sql
importance int          -- 1-10, how critical (policy > tip)
specificity int         -- 1-10, how narrow (1=broad overview, 10=edge case)
complexity int          -- 1-10, how advanced (1=anyone, 10=specialist)
```

Retrieval: `ORDER BY importance DESC, score ASC`

### Chunk Relationships
Build the knowledge graph at ingest:

```sql
parent_id uuid          -- Document/section this chunk belongs to
chunk_index int         -- Position in parent
sibling_ids uuid[]      -- Related chunks at same level
prerequisite_ids uuid[] -- What you should read first
see_also_ids uuid[]     -- Related but different topic
```

Retrieval: After finding relevant chunk, pull siblings/see_also for context

### Pre-computed Clusters
Topic clustering done at ingest:

```sql
cluster_id int          -- Topic cluster (HDBSCAN or k-means at ingest)
cluster_label text      -- Human-readable cluster name
```

Retrieval: `WHERE cluster_id = (SELECT cluster_id FROM ... LIMIT 1)` to expand results

---

## THE RETRIEVAL PATTERN

Design the schema to enable this query pattern:

```sql
-- Input: query_embedding, intent, entities, user_department, threshold

WITH smart_candidates AS (
  SELECT 
    id, content, section_title, source_file,
    embedding, importance, process_name, process_step,
    see_also_ids, sibling_ids
  FROM enterprise.documents
  WHERE 
    -- Fast pre-filters (GIN indexes, sub-10ms)
    department_id = $user_department
    AND $intent = ANY(query_types)
    AND entities && $extracted_entities  -- Array overlap
    AND is_active = true
),
scored AS (
  SELECT 
    *,
    1 - (embedding <=> $query_embedding) AS similarity  -- Cosine similarity
  FROM smart_candidates
  WHERE embedding IS NOT NULL
),
threshold_results AS (
  -- EVERYTHING above threshold, not just top N
  SELECT * FROM scored
  WHERE similarity >= 0.6
)
SELECT 
  *,
  -- Boost procedural content when asking "how to"
  CASE WHEN is_procedure AND $intent = 'how_to' THEN similarity + 0.1 ELSE similarity END AS boosted_score
FROM threshold_results
ORDER BY 
  importance DESC,
  boosted_score DESC,
  process_step ASC NULLS LAST
-- NO LIMIT - return everything relevant
```

---

## SOURCE DATA

Existing JSON chunks in `Manuals/Driscoll/`:

```json
{
  "chunk_id": "warehouse-receiving-001",
  "content": "When receiving shipments, verify the packing slip matches...",
  "department": "warehouse",
  "category": "procedures",
  "subcategory": "receiving",
  "keywords": ["receiving", "packing slip", "verification"],
  "source_file": "Warehouse_Manual.docx",
  "token_count": 245
}
```

Your schema must:
1. Accept these fields from JSON
2. Add computed fields (query_types, verbs, entities, etc.)
3. Handle chunks that don't have all fields (nullable defaults)

---

## HEURISTIC TAGGING STRATEGY

At ingest time, compute semantic tags using simple rules:

### Verb Extraction (Regex-based)
```python
VERB_PATTERNS = {
    'approve': r'\b(approve|approval|approved)\b',
    'reject': r'\b(reject|denial|denied|decline)\b',
    'submit': r'\b(submit|send|forward)\b',
    'create': r'\b(create|new|generate|open)\b',
    'void': r'\b(void|cancel|reverse)\b',
    'escalate': r'\b(escalate|supervisor|manager|exception)\b',
}
```

### Intent Classification (Keyword-based)
```python
def classify_query_types(content, section_title):
    types = []
    text = (content + section_title).lower()
    
    if any(w in text for w in ['step', 'procedure', 'process', 'how to']):
        types.append('how_to')
    if any(w in text for w in ['policy', 'rule', 'requirement', 'must']):
        types.append('policy')
    if any(w in text for w in ['error', 'issue', 'problem', 'fix']):
        types.append('troubleshoot')
    if any(w in text for w in ['definition', 'means', 'refers to']):
        types.append('definition')
    if any(w in text for w in ['contact', 'escalate', 'supervisor']):
        types.append('escalation')
    
    return types or ['reference']  # Default
```

### Entity Extraction (Domain-specific)
```python
ENTITIES = {
    'credit_memo', 'purchase_order', 'invoice', 'customer', 'vendor',
    'return', 'shipment', 'pallet', 'driver', 'route', 'claim',
    'shortage', 'overage', 'damage', 'pricing', 'discount'
}

def extract_entities(content):
    content_lower = content.lower()
    return [e for e in ENTITIES if e.replace('_', ' ') in content_lower]
```

---

## DELIVERABLES

### 1. Migration 003 SQL (`db/migrations/003_smart_documents.sql`)

Complete DDL with:
- Table definition with all semantic columns
- GIN indexes on array columns
- IVFFlat index on embedding
- Full-text search index
- Any helper functions

### 2. Updated Ingestion Mapping (`docs/INGESTION_MAPPING.md`)

Document how JSON chunk fields map to new schema columns:
- Direct mappings (content → content)
- Computed fields (content → verbs, entities, query_types)
- Default values for missing fields

### 3. Tagging Functions (`memory/ingest/semantic_tagger.py`)

Simple Python functions for:
- `extract_verbs(content) -> List[str]`
- `extract_entities(content) -> List[str]`
- `classify_query_types(content, section_title) -> List[str]`
- `compute_importance(content, category) -> int`
- `detect_procedure(content) -> bool`

Keep it simple. Regex and keyword matching. No LLM calls.

### 4. Example Retrieval Query (`docs/SMART_RAG_QUERY.sql`)

A reference query showing the full pre-filter → threshold → expand pattern.

---

## CREATIVE LICENSE

You have freedom to:

1. **Add dimensions** I didn't think of
2. **Combine dimensions** if they overlap
3. **Remove dimensions** if they're not useful
4. **Invent clever indexing strategies**
5. **Design hierarchical structures** for chunk relationships
6. **Pre-compute anything** that speeds up retrieval

You must NOT:

1. Add additional tables (single table rule)
2. Require query-time LLM calls
3. Break compatibility with existing JSON chunks
4. Make retrieval slower than dumb RAG
5. Over-engineer (this needs to work tomorrow)

---

## SUCCESS CRITERIA

- [ ] Migration 003 SQL runs without errors
- [ ] Schema supports threshold-based retrieval (not top-N)
- [ ] GIN indexes on all array columns
- [ ] IVFFlat index on embedding column
- [ ] Tagging functions are simple (regex/keyword, no ML)
- [ ] Ingestion mapping documented
- [ ] Example retrieval query provided
- [ ] Total new code < 500 lines

---

## THE VISION

A user asks: "How do I approve a credit memo when the customer is disputing the amount?"

**Dumb RAG:** Returns 5 random chunks mentioning "credit"

**Smart RAG:** 
1. Intent: `how_to` + `troubleshoot`
2. Entities: `credit_memo`, `customer`, `dispute`
3. Verbs: `approve`
4. Pre-filter: 5000 chunks → 23 candidates
5. Vector search + 0.6 threshold → 7 relevant chunks
6. Expand: Pull `see_also_ids` → 3 related procedures
7. Order by: importance DESC, process_step ASC
8. Return: 10 chunks covering the full picture

Time: <100ms  
Quality: Shows the approval process, exception handling, AND related credit policies

---

## GO NUTS

Design something clever. Make the embedder's job trivially easy. Return everything relevant, not an arbitrary top-5.

The goal: When a Driscoll Foods employee asks a question, they get **the complete picture** - not a filtered glimpse.

---

*"Make it so the embedding search is just confirming what the schema already knows."*