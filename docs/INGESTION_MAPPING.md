# Smart RAG Ingestion Mapping

**Date:** 2024-12-22
**Purpose:** Map JSON chunk fields → PostgreSQL `enterprise.documents` schema
**Philosophy:** Pre-compute structure at ingest, trivialize retrieval

---

## OVERVIEW

This document describes how to transform JSON chunks (from `Manuals/Driscoll/*.json`) into the smart RAG schema (`enterprise.documents` table).

**Ingestion Flow:**

```
JSON Chunk
  ↓
Extract source metadata (direct mapping)
  ↓
Compute semantic tags (via semantic_tagger.py)
  ↓
Generate embedding (via DeepInfra API)
  ↓
Insert into enterprise.documents
  ↓
Post-process: Compute relationships (siblings, see_also, etc.)
```

---

## FIELD MAPPING

### 1. DIRECT MAPPINGS (JSON → Schema, no computation)

| JSON Field | Schema Column | Type | Notes |
|------------|---------------|------|-------|
| `content` | `content` | TEXT | The chunk text itself |
| `chunk_id` | `id` | UUID | If JSON has UUID, use it; else generate |
| `source_file` | `source_file` | TEXT | Original document filename |
| `department` | `department_id` | TEXT | Lowercase, normalized |
| `category` | `source_type` | TEXT | 'manual', 'policy', 'form', 'faq' |
| `subcategory` | — | — | Use for section_title if present |
| `keywords` | — | — | Feed into entity extraction |
| `token_count` | `token_count` | INTEGER | Direct copy |

**Computed at insertion:**
```python
content_length = len(content)  # Character count
created_at = NOW()
updated_at = NOW()
is_active = True
version = 1
```

---

### 2. SEMANTIC TAG COMPUTATION (via `semantic_tagger.py`)

All of these are computed by `tag_document_chunk()`:

| Computed Field | Schema Column | Type | Source Function |
|----------------|---------------|------|-----------------|
| Query types | `query_types` | TEXT[] | `classify_query_types()` |
| Action verbs | `verbs` | TEXT[] | `extract_verbs()` |
| Domain entities | `entities` | TEXT[] | `extract_entities()` |
| Actor roles | `actors` | TEXT[] | `extract_actors()` |
| Conditions | `conditions` | TEXT[] | `extract_conditions()` |
| Importance score | `importance` | INTEGER | `compute_importance()` |
| Specificity score | `specificity` | INTEGER | `compute_specificity()` |
| Complexity score | `complexity` | INTEGER | `compute_complexity()` |
| Is procedure? | `is_procedure` | BOOLEAN | `detect_procedure()` |
| Is policy? | `is_policy` | BOOLEAN | `detect_policy()` |
| Is form? | `is_form` | BOOLEAN | `detect_form()` |
| Process name | `process_name` | TEXT | `extract_process_name()` |
| Process step | `process_step` | INTEGER | `extract_process_step()` |

**Example:**

```python
from memory.ingest.semantic_tagger import tag_document_chunk

# JSON chunk data
chunk = {
    "content": "Step 1: Submit credit request via online form...",
    "department": "credit",
    "category": "procedures"
}

# Compute semantic tags
tags = tag_document_chunk(
    content=chunk["content"],
    section_title=chunk.get("subcategory", ""),
    category=chunk["category"]
)

# Result:
# {
#   'query_types': ['how_to'],
#   'verbs': ['submit', 'create'],
#   'entities': ['credit_memo', 'customer'],
#   'actors': ['sales_rep'],
#   'conditions': [],
#   'is_procedure': True,
#   'is_policy': False,
#   'is_form': True,
#   'process_name': 'credit_approval',
#   'process_step': 1,
#   'importance': 6,
#   'specificity': 5,
#   'complexity': 4
# }
```

---

### 3. EMBEDDING GENERATION (via DeepInfra API)

**Field:** `embedding` (VECTOR(1024))

**Embedding text:** Concatenate multiple fields for rich context:

```python
def prepare_embedding_text(chunk: dict, tags: dict) -> str:
    """
    Build embedding input with structured metadata for better retrieval.
    """
    parts = []

    # Section context (if available)
    if chunk.get("subcategory"):
        parts.append(f"Section: {chunk['subcategory']}")

    # Main content
    parts.append(chunk["content"])

    # Metadata context
    parts.append(f"Department: {chunk['department']}")
    parts.append(f"Type: {', '.join(tags['query_types'])}")

    if tags['entities']:
        parts.append(f"Topics: {', '.join(tags['entities'])}")

    return "\n".join(parts)

# Generate embedding
embedding_text = prepare_embedding_text(chunk, tags)
embedding = embedder.embed_text(embedding_text)  # Returns 1024-dim vector
```

**Why embed metadata?**
Including department, entities, and query types in the embedded text improves semantic search by giving the model more context. The vector "learns" these structural hints.

---

### 4. ACCESS CONTROL

**Field:** `department_access` (TEXT[])

**Default logic:**

```python
def compute_department_access(chunk: dict, tags: dict) -> List[str]:
    """
    Determine which departments can access this chunk.
    """
    primary_dept = chunk["department"]
    access = [primary_dept]  # Always include primary department

    # Cross-department content detection
    cross_dept_entities = {
        'credit_memo': ['credit', 'sales'],  # Credit requests from sales
        'purchase_order': ['purchasing', 'warehouse'],  # PO receiving
        'return': ['warehouse', 'credit', 'sales'],  # Returns process
        'invoice': ['credit', 'sales'],  # Invoice disputes
    }

    for entity in tags['entities']:
        if entity in cross_dept_entities:
            access.extend(cross_dept_entities[entity])

    return sorted(set(access))  # Dedupe
```

**Example:**
- Chunk about "credit memo submission" in `sales` department
- Contains entity `credit_memo`
- Result: `department_access = ['credit', 'sales']`

---

### 5. RELATIONSHIPS (Post-ingestion batch process)

These are computed AFTER all chunks are inserted, using batch queries.

#### 5a. Sibling IDs (chunks in same document)

```sql
-- For each chunk with a parent_id, find siblings
UPDATE enterprise.documents d1
SET sibling_ids = ARRAY(
    SELECT id
    FROM enterprise.documents d2
    WHERE d2.parent_id = d1.parent_id
      AND d2.id != d1.id
    ORDER BY d2.chunk_index
)
WHERE parent_id IS NOT NULL;
```

#### 5b. Process Sequences (follow/precede relationships)

```sql
-- For procedural chunks, link sequential steps
UPDATE enterprise.documents d1
SET follows_ids = ARRAY(
    SELECT id
    FROM enterprise.documents d2
    WHERE d2.process_name = d1.process_name
      AND d2.process_step = d1.process_step - 1
)
WHERE process_name IS NOT NULL
  AND process_step > 1;
```

#### 5c. Prerequisite IDs (heuristic-based)

**Logic:** If chunk A mentions "see Section X" or "refer to Y", and chunk B has that title, link them.

```python
def extract_prerequisite_links(content: str, section_title: str) -> List[str]:
    """
    Extract references to other sections.
    Returns list of referenced section titles.
    """
    # Pattern: "see [Section Name]", "refer to [X]", "as described in [Y]"
    patterns = [
        r'see\s+([A-Z][^,.]{5,40})',
        r'refer to\s+([A-Z][^,.]{5,40})',
        r'described in\s+([A-Z][^,.]{5,40})',
        r'outlined in\s+([A-Z][^,.]{5,40})',
    ]

    references = []
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        references.extend(matches)

    return references

# Then, during post-processing:
# 1. Extract all references from each chunk
# 2. Match reference text to section_title of other chunks
# 3. Update prerequisite_ids with matched chunk IDs
```

#### 5d. See-Also IDs (semantic similarity-based)

**Logic:** After all embeddings are generated, find chunks with similar embeddings but different process_name.

```sql
-- For each chunk, find semantically similar chunks (different topic)
WITH similarities AS (
    SELECT
        d1.id AS source_id,
        d2.id AS related_id,
        1 - (d1.embedding <=> d2.embedding) AS similarity
    FROM enterprise.documents d1
    CROSS JOIN enterprise.documents d2
    WHERE d1.id != d2.id
      AND d1.department_id = d2.department_id  -- Same department
      AND (d1.process_name IS NULL OR d2.process_name IS NULL OR d1.process_name != d2.process_name)  -- Different process
      AND 1 - (d1.embedding <=> d2.embedding) >= 0.7  -- High similarity
)
UPDATE enterprise.documents d
SET see_also_ids = ARRAY(
    SELECT related_id
    FROM similarities
    WHERE source_id = d.id
    ORDER BY similarity DESC
    LIMIT 5  -- Top 5 related chunks
);
```

---

### 6. CLUSTERING (Optional, post-ingestion)

**Fields:** `cluster_id`, `cluster_label`, `cluster_centroid`

**Approach:** Use k-means or HDBSCAN on embeddings to group related content.

```python
from sklearn.cluster import KMeans
import numpy as np

# Fetch all embeddings
embeddings = np.array([row['embedding'] for row in all_chunks])

# Cluster (adjust n_clusters based on corpus size)
n_clusters = max(10, len(all_chunks) // 50)  # ~50 chunks per cluster
kmeans = KMeans(n_clusters=n_clusters, random_state=42)
cluster_ids = kmeans.fit_predict(embeddings)

# Compute centroids
centroids = kmeans.cluster_centers_

# Assign labels (use most common section_title in cluster)
for cluster_id in range(n_clusters):
    cluster_chunks = [chunk for chunk, cid in zip(all_chunks, cluster_ids) if cid == cluster_id]
    most_common_title = Counter([c['section_title'] for c in cluster_chunks]).most_common(1)[0][0]

    # Update database
    UPDATE enterprise.documents
    SET cluster_id = cluster_id,
        cluster_label = most_common_title,
        cluster_centroid = centroids[cluster_id]
    WHERE id = ANY(cluster_chunk_ids);
```

---

## FULL INGESTION PIPELINE

### Step 1: Load JSON chunks

```python
import json
from pathlib import Path

def load_chunks(json_file: Path) -> List[dict]:
    with open(json_file) as f:
        data = json.load(f)
    return data.get("chunks", [])

chunks = load_chunks(Path("Manuals/Driscoll/Warehouse_Manual_chunks.json"))
```

### Step 2: For each chunk, compute tags + embedding

```python
from memory.ingest.semantic_tagger import tag_document_chunk
from memory.embedder import AsyncEmbedder

embedder = AsyncEmbedder()

for chunk in chunks:
    # Compute semantic tags
    tags = tag_document_chunk(
        content=chunk["content"],
        section_title=chunk.get("subcategory", ""),
        category=chunk.get("category", "")
    )

    # Prepare embedding text
    embedding_text = prepare_embedding_text(chunk, tags)
    embedding = await embedder.embed_text(embedding_text)

    # Compute access control
    department_access = compute_department_access(chunk, tags)

    # Prepare database row
    row = {
        'id': chunk.get('chunk_id', str(uuid.uuid4())),
        'source_file': chunk['source_file'],
        'department_id': chunk['department'].lower(),
        'source_type': chunk.get('category', 'manual'),
        'section_title': chunk.get('subcategory'),
        'content': chunk['content'],
        'content_length': len(chunk['content']),
        'token_count': chunk.get('token_count'),
        'embedding': embedding,
        'department_access': department_access,
        **tags  # Unpack all computed tags
    }

    # Insert into database
    await db.insert('enterprise.documents', row)
```

### Step 3: Post-process relationships

```python
# After all chunks inserted, compute relationships
await compute_sibling_relationships()
await compute_process_sequences()
await compute_prerequisite_links()
await compute_see_also_links()
```

### Step 4: Run VACUUM ANALYZE

```sql
-- Critical for IVFFlat index performance
VACUUM ANALYZE enterprise.documents;
```

---

## VALIDATION CHECKLIST

After ingestion, verify data quality:

```sql
-- Check tag coverage
SELECT
    COUNT(*) AS total_chunks,
    COUNT(*) FILTER (WHERE array_length(query_types, 1) > 0) AS has_query_types,
    COUNT(*) FILTER (WHERE array_length(entities, 1) > 0) AS has_entities,
    COUNT(*) FILTER (WHERE array_length(verbs, 1) > 0) AS has_verbs,
    COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS has_embedding,
    COUNT(*) FILTER (WHERE importance BETWEEN 1 AND 10) AS has_importance,
    COUNT(*) FILTER (WHERE process_name IS NOT NULL) AS has_process
FROM enterprise.documents;

-- Check relationship coverage
SELECT
    COUNT(*) FILTER (WHERE array_length(sibling_ids, 1) > 0) AS has_siblings,
    COUNT(*) FILTER (WHERE array_length(prerequisite_ids, 1) > 0) AS has_prerequisites,
    COUNT(*) FILTER (WHERE array_length(see_also_ids, 1) > 0) AS has_see_also
FROM enterprise.documents;

-- Check department distribution
SELECT department_id, COUNT(*) AS chunk_count
FROM enterprise.documents
GROUP BY department_id
ORDER BY chunk_count DESC;
```

**Expected results:**
- 100% have `query_types`, `content`, `department_id`
- 90%+ have `embedding`
- 60%+ have `entities` or `verbs` (procedural content)
- 30%+ have relationships (depends on corpus structure)

---

## ERROR HANDLING

### Missing embeddings
If embedding generation fails, set `embedding = NULL` and log for retry. Chunks without embeddings won't appear in vector search but can still be found via full-text or filter-based queries.

### Invalid JSON structure
If JSON chunk is missing required fields (`content`, `department`), skip with warning:

```python
required_fields = ['content', 'department', 'source_file']
if not all(field in chunk for field in required_fields):
    logger.warning(f"Skipping invalid chunk: {chunk.get('chunk_id', 'unknown')}")
    continue
```

### Tag computation errors
If semantic tagging fails (regex error, etc.), use safe defaults:

```python
try:
    tags = tag_document_chunk(content, section_title, category)
except Exception as e:
    logger.error(f"Tagging failed for chunk {chunk_id}: {e}")
    tags = {
        'query_types': ['reference'],
        'verbs': [],
        'entities': [],
        'actors': [],
        'conditions': [],
        'is_procedure': False,
        'is_policy': False,
        'is_form': False,
        'process_name': None,
        'process_step': None,
        'importance': 5,
        'specificity': 5,
        'complexity': 5,
    }
```

---

## PERFORMANCE NOTES

### Batch Insertion
Don't insert one row at a time. Use batch inserts:

```python
# Prepare all rows first
rows = [prepare_row(chunk) for chunk in chunks]

# Batch insert (PostgreSQL supports up to 1000 rows per query)
batch_size = 500
for i in range(0, len(rows), batch_size):
    batch = rows[i:i+batch_size]
    await db.insert_many('enterprise.documents', batch)
```

### Embedding Generation
Use `AsyncEmbedder` with concurrency limits to avoid rate limiting:

```python
from asyncio import Semaphore

semaphore = Semaphore(10)  # Max 10 concurrent requests

async def embed_with_limit(text: str):
    async with semaphore:
        return await embedder.embed_text(text)

# Batch embed
embeddings = await asyncio.gather(*[
    embed_with_limit(prepare_embedding_text(chunk, tags))
    for chunk in chunks
])
```

### Relationship Computation
Don't update rows one at a time. Use batch UPDATE queries (shown in SQL examples above).

---

## MIGRATION FROM OLD SCHEMA

If you have existing data in the old 15-column schema:

```sql
-- Migrate existing content (if any)
INSERT INTO enterprise.documents_new (
    id, source_file, department_id, content, embedding,
    query_types, verbs, entities  -- Add defaults for new columns
)
SELECT
    id, source_file, department_id, content, embedding,
    ARRAY['reference']::TEXT[],  -- Default query_types
    ARRAY[]::TEXT[],  -- Empty verbs
    ARRAY[]::TEXT[]   -- Empty entities
FROM enterprise.documents_old;

-- Then run semantic tagging as a batch update
UPDATE enterprise.documents_new d
SET
    query_types = (SELECT classify_query_types(d.content, '')),
    verbs = (SELECT extract_verbs(d.content)),
    entities = (SELECT extract_entities(d.content))
    -- etc.
WHERE id = d.id;
```

But realistically, just re-ingest from source JSON—it's cleaner.

---

## SUMMARY

**What you need:**

1. ✅ JSON chunks (already exist in `Manuals/Driscoll/`)
2. ✅ `semantic_tagger.py` (this document's functions)
3. ✅ Schema (Migration 003)
4. ✅ Embedder (AsyncEmbedder already exists)

**What you do:**

1. Load JSON chunks
2. For each chunk:
   - Call `tag_document_chunk()` → get semantic tags
   - Call `embedder.embed_text()` → get embedding
   - Insert row into `enterprise.documents`
3. Run post-processing queries (relationships, clustering)
4. Run `VACUUM ANALYZE`

**Result:**
A blazingly fast, semantically rich document store where retrieval is 90% pre-filtering and 10% vector search.

---

*"Schema does the thinking, embeddings just confirm."*
