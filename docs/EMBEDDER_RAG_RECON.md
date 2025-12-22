# EMBEDDER & RAG SYSTEM RECONNAISSANCE

**Date:** 2024-12-22 01:30 UTC
**Type:** RECON ONLY - No code changes
**Priority:** HIGH - Enterprise RAG broken post-Migration 002
**Scope:** Embedding, RAG, and ingestion systems

---

## EXECUTIVE SUMMARY

### What's Broken
1. **RAG Retrieval DEAD** - `enterprise.documents` table deleted in Migration 002
2. **Ingestion DEAD** - References `enterprise.departments` and `enterprise.department_content` (don't exist)
3. **Duplicate Embedder Implementations** - `AsyncEmbedder` and `EmbeddingClient` coexist
4. **Personal SaaS Memory Leaking** - CogTwin imports 14 memory components, EnterpriseTwin has 1

### What Works
- ✅ Embedder classes themselves (both functional)
- ✅ DeepInfra provider wired correctly
- ✅ JSON chunk files exist in `Manuals/Driscoll/`
- ✅ Config.yaml has correct structure

### What's Needed (Critical Path)
1. **Create `enterprise.documents` table** (DDL provided below)
2. **Fix ingestion script** - Point to `enterprise.documents` instead of `department_content`
3. **Run ingestion** with `--embed` flag
4. **Test RAG retrieval** via EnterpriseTwin

### Impact Assessment
- **Enterprise Bot:** BLOCKED - Cannot retrieve manuals (core feature)
- **Personal SaaS:** OUT OF SCOPE - Memory components untouched, documented for future stubbing

---

## PHASE 1: EMBEDDER DEEP DIVE

### 1.1 Implementations Found

| Class | File | Provider | Model | Dimension | Status |
|-------|------|----------|-------|-----------|--------|
| `AsyncEmbedder` | `memory/embedder.py` | DeepInfra / TEI / Cloudflare | BAAI/bge-m3 | 1024 | ✅ WORKS |
| `EmbeddingClient` | `core/enterprise_rag.py:54-112` | DeepInfra only | BAAI/bge-m3 | 1024 | ✅ WORKS |

**Issue:** Two separate embedder implementations. Should consolidate to `AsyncEmbedder` (more mature).

### 1.2 Supported Providers

#### DeepInfra (Active)
- **Endpoint:** `https://api.deepinfra.com/v1/inference/BAAI/bge-m3`
- **Rate Limit:** 180 RPM (configurable)
- **API Key:** `DEEPINFRA_API_KEY` (required)
- **Status:** ✅ Active in both implementations

#### TEI (Self-Hosted, Available)
- **Endpoint:** User-configurable (RunPod/Modal)
- **Rate Limit:** None (self-hosted)
- **API Key:** Optional
- **Status:** ⚠️ Available but not configured
- **Deploy Command:**
  ```bash
  docker run --gpus all -p 80:80 \
    ghcr.io/huggingface/text-embeddings-inference:1.5 \
    --model-id BAAI/bge-m3 --pooling cls \
    --max-client-batch-size 128 --max-batch-tokens 16384
  ```

#### Cloudflare Workers AI (Fallback)
- **Endpoint:** Cloudflare AI API
- **Rate Limit:** 300 RPM
- **API Key:** `CLOUDFLARE_API_TOKEN`
- **Status:** ⚠️ Available but not configured

### 1.3 Environment Variables

| Var | Required By | Default | Status |
|-----|-------------|---------|--------|
| `DEEPINFRA_API_KEY` | AsyncEmbedder, EmbeddingClient | None | ✅ Required |
| `CLOUDFLARE_API_TOKEN` | CloudflareProvider | None | ⚠️ Optional |
| `TEI_ENDPOINT` | TEIProvider | None | ⚠️ Optional |

**Note:** If `DEEPINFRA_API_KEY` is missing:
- `EmbeddingClient.embed()` returns `None` (silent fallback)
- `AsyncEmbedder` raises `ValueError` (fails fast)

### 1.4 Usage Map

#### AsyncEmbedder Usage
| Caller File | Line | Method Called | Purpose |
|-------------|------|---------------|---------|
| `core/cog_twin.py` | 90 | `import AsyncEmbedder` | Personal SaaS retrieval |
| `core/cog_twin.py` | 269 | `embedder=self.retriever.embedder` | Pass to retriever |
| `core/cog_twin.py` | 345 | `await embedder.embed_single()` | Query embedding |
| `core/cog_twin.py` | 414 | `await embedder.embed_single()` | Query embedding |
| `core/cog_twin.py` | 733 | `await embedder.embed_single()` | Query embedding |
| `core/cog_twin.py` | 760 | `await embedder.embed_single()` | Query embedding |
| `core/protocols.py` | 107-110 | `import AsyncEmbedder, create_embedder` | Export via protocol |
| `memory/retrieval.py` | 40 | `from .embedder import AsyncEmbedder` | DualRetriever dependency |
| `memory/hybrid_search.py` | 84 | `embedder: Any` | Type hint (AsyncEmbedder) |
| `memory/ingest/pipeline.py` | 60 | `from memory.embedder import AsyncEmbedder` | Ingestion pipeline |
| `memory/ingest/ingest_to_postgres.py` | 32 | `from embedder import AsyncEmbedder` | ❌ BROKEN IMPORT |

#### EmbeddingClient Usage
| Caller File | Line | Method Called | Purpose |
|-------------|------|---------------|---------|
| `core/enterprise_rag.py` | 144 | `self.embedder = EmbeddingClient(config)` | RAG retriever init |
| `core/enterprise_rag.py` | 205 | `await self.embedder.embed(query)` | Query embedding |
| `core/enterprise_rag.py` | 414 | `await self.embedder.close()` | Cleanup |

### 1.5 Entry Points

#### AsyncEmbedder
- `embed_single(text: str) -> np.ndarray` - Single text embedding
- `embed_batch(texts: List[str], batch_size=32, max_concurrent=8) -> np.ndarray` - Batch embedding
- `get_stats() -> Dict[str, Any]` - Return cache stats

#### EmbeddingClient
- `embed(text: str) -> Optional[List[float]]` - Single text embedding (returns None on failure)
- `close()` - Close HTTP client

### 1.6 Issues Found

1. **Duplicate Implementations** - Two embedder classes doing the same job
   - Recommendation: Consolidate to `AsyncEmbedder` (more mature, better error handling)
   - Action: Refactor `EmbeddingClient` in `enterprise_rag.py` to use `AsyncEmbedder`

2. **Broken Import** - `memory/ingest/ingest_to_postgres.py:32`
   - Current: `from embedder import AsyncEmbedder`
   - Should be: `from memory.embedder import AsyncEmbedder`
   - Impact: Ingestion with `--embed` flag will crash

3. **Silent Failure** - `EmbeddingClient` returns `None` when API key missing
   - `AsyncEmbedder` raises `ValueError` (better for debugging)
   - Recommendation: Prefer fail-fast over silent degradation

4. **No Config.yaml Embedding Section**
   - `config.yaml` has no `embedding:` block
   - `EmbeddingClient` looks for `config.get("embedding", {}).get("model")` (returns None)
   - Uses hardcoded defaults (works but undocumented)

---

## PHASE 2: DATABASE TABLE AUDIT

### 2.1 Existing Tables (Verified ✅)

```sql
-- After Migration 002 (2024-12-22)
enterprise.tenants (
    id uuid PRIMARY KEY,
    slug varchar(50) UNIQUE NOT NULL,
    name varchar(255) NOT NULL,
    domain varchar(255) NOT NULL,
    created_at timestamptz DEFAULT now()
)

enterprise.users (
    id uuid PRIMARY KEY,
    tenant_id uuid REFERENCES enterprise.tenants(id),
    email varchar(255) UNIQUE NOT NULL,
    display_name varchar(255),
    azure_oid varchar(255) UNIQUE,
    department_access varchar[] DEFAULT '{}',
    dept_head_for varchar[] DEFAULT '{}',
    is_super_user boolean DEFAULT false,
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    last_login_at timestamptz
)
```

### 2.2 Missing Tables (Required for RAG ❌)

| Table | Status | Expected By | Impact |
|-------|--------|-------------|--------|
| `enterprise.documents` | ❌ DELETED | `enterprise_rag.py:139` | RAG retrieval DEAD |
| `enterprise.departments` | ❌ DELETED | `ingest_to_postgres.py:59` | Ingestion DEAD |
| `enterprise.department_content` | ❌ DELETED | `ingest_to_postgres.py:80,194` | Ingestion DEAD |

### 2.3 Dead References (Code → Non-Existent Tables)

| File | Line | Table Referenced | Query Type | Action Needed |
|------|------|------------------|------------|---------------|
| `core/enterprise_rag.py` | 139 | `enterprise.documents` | SELECT | ✅ Create table |
| `core/enterprise_rag.py` | 259 | `enterprise.documents` | SELECT (vector search) | ✅ Create table |
| `core/enterprise_rag.py` | 341 | `enterprise.documents` | SELECT (keyword search) | ✅ Create table |
| `core/enterprise_rag.py` | 387 | `enterprise.documents` | SELECT (get by ID) | ✅ Create table |
| `memory/ingest/ingest_to_postgres.py` | 59 | `enterprise.departments` | SELECT | ❌ Delete reference |
| `memory/ingest/ingest_to_postgres.py` | 80 | `enterprise.department_content` | SELECT | ✅ Change to `documents` |
| `memory/ingest/ingest_to_postgres.py` | 194 | `enterprise.department_content` | INSERT | ✅ Change to `documents` |

### 2.4 Schema Analysis: What Does `enterprise_rag.py` Expect?

From `enterprise_rag.py:249-267` (vector search query):
```sql
SELECT
    id,
    content,
    section_title,
    source_file,
    department_id,
    keywords,
    chunk_index,
    1 - (embedding <=> $1::vector) as score
FROM enterprise.documents
WHERE
    tenant_id = $2
    AND (department_id = $3 OR department_id IS NULL)
    AND embedding IS NOT NULL
    AND 1 - (embedding <=> $1::vector) >= $4
ORDER BY embedding <=> $1::vector
LIMIT $5
```

**Required Columns:**
- `id` (UUID or serial, primary key)
- `content` (text, the chunk content)
- `section_title` (text, heading from manual)
- `source_file` (text, source DOCX filename)
- `department_id` (varchar, e.g., 'sales', 'purchasing')
- `keywords` (text[] or jsonb, extracted keywords)
- `chunk_index` (integer, position in source doc)
- `embedding` (vector(1024), pgvector type)
- `tenant_id` (uuid, FK to tenants)

From `ingest_to_postgres.py:162-184` (INSERT data mapping):
```python
row = (
    tenant_id,          # tenant_id
    dept_id,            # department_id
    chunk.chunk_id,     # title (?)
    chunk.content,      # content
    'manual',           # content_type
    None,               # version
    True,               # active
    embedding,          # embedding (vector or None)
    None,               # parent_document_id
    0,                  # chunk_index
    False,              # is_document_root
    'content',          # chunk_type
    chunk.source_file,  # source_file
    chunk.file_hash,    # file_hash
    chunk.chunk_id,     # section_title (?)
    chunk.token_count,  # chunk_token_count
    'BAAI/bge-m3',      # embedding_model
    chunk.category,     # category
    chunk.subcategory,  # subcategory
    keywords_json,      # keywords (JSON string)
)
```

**Ingestion Expects (OLD SCHEMA):**
- `tenant_id`, `department_id`, `title`, `content`, `content_type`, `version`, `active`
- `embedding`, `parent_document_id`, `chunk_index`, `is_document_root`, `chunk_type`
- `source_file`, `file_hash`, `section_title`, `chunk_token_count`, `embedding_model`
- `category`, `subcategory`, `keywords`

**Conflict:** Ingestion script writes to `department_content` schema (19 columns), RAG reads from `documents` schema (9 columns). **They are NOT the same table!**

### 2.5 Migration History

| Migration | Date | Action | Status |
|-----------|------|--------|--------|
| `001_rebuild_enterprise_schema.py` | 2024-12-21 | Created 7 tables | ❌ NUKED |
| `002_auth_refactor_2table.sql` | 2024-12-22 | Dropped all, rebuilt 2 | ✅ ACTIVE |

**What Happened:**
- Migration 001 created: `tenants`, `departments`, `users`, `access_config`, `access_audit_log`, `documents`, `query_log`
- Migration 002 nuked EVERYTHING, rebuilt only `tenants` and `users`
- Result: RAG table (`documents`) was collateral damage

### 2.6 Recommended Minimal Schema (For Enterprise RAG)

```sql
-- ============================================================================
-- MIGRATION 003: Rebuild enterprise.documents for RAG
-- ============================================================================
-- Date: 2024-12-22
-- Purpose: Restore RAG capability post-Migration 002
--
-- Creates minimal schema compatible with both:
-- 1. enterprise_rag.py retrieval queries
-- 2. ingest_to_postgres.py ingestion script (after fixes)
-- ============================================================================

BEGIN;

-- Enable pgvector extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create documents table (RAG storage)
CREATE TABLE IF NOT EXISTS enterprise.documents (
    -- Primary key
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Tenant scoping (RLS)
    tenant_id uuid REFERENCES enterprise.tenants(id) ON DELETE CASCADE,

    -- Department scoping (array in users table, string here)
    department_id varchar(50),  -- 'sales', 'purchasing', 'warehouse', etc.

    -- Content (REQUIRED by RAG)
    content text NOT NULL,
    section_title text,
    source_file text,

    -- Metadata (used by ingestion)
    file_hash varchar(64),  -- SHA256 for deduplication
    chunk_index integer DEFAULT 0,
    chunk_token_count integer,

    -- Search fields
    keywords jsonb DEFAULT '[]'::jsonb,
    category varchar(100),
    subcategory varchar(100),

    -- Vector embedding (CRITICAL for semantic search)
    embedding vector(1024),  -- BGE-M3 embeddings
    embedding_model varchar(100) DEFAULT 'BAAI/bge-m3',

    -- Lifecycle
    active boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Indexes for performance
CREATE INDEX idx_documents_tenant ON enterprise.documents(tenant_id);
CREATE INDEX idx_documents_department ON enterprise.documents(department_id);
CREATE INDEX idx_documents_file_hash ON enterprise.documents(file_hash);
CREATE INDEX idx_documents_active ON enterprise.documents(active) WHERE active = true;

-- pgvector index for cosine similarity (IVFFlat for large datasets)
-- Use L2 distance with normalized vectors (equivalent to cosine)
CREATE INDEX idx_documents_embedding ON enterprise.documents
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);

-- GIN index for keyword search
CREATE INDEX idx_documents_keywords ON enterprise.documents USING gin(keywords);

-- Full-text search index
CREATE INDEX idx_documents_fts ON enterprise.documents
USING gin(to_tsvector('english', coalesce(content, '') || ' ' || coalesce(section_title, '')));

-- Unique constraint for deduplication (per tenant)
CREATE UNIQUE INDEX idx_documents_unique_chunk
ON enterprise.documents(tenant_id, file_hash, chunk_index)
WHERE active = true;

COMMIT;

-- ============================================================================
-- VALIDATION QUERIES
-- ============================================================================

-- Check table structure
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'enterprise'
  AND table_name = 'documents'
ORDER BY ordinal_position;

-- Check indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'enterprise'
  AND tablename = 'documents'
ORDER BY indexname;

-- Check pgvector extension
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Test vector distance query (should not error)
SELECT
    id,
    content,
    1 - (embedding <=> '[0.1, 0.2, ...]'::vector) as similarity
FROM enterprise.documents
WHERE tenant_id = 'some-uuid'
LIMIT 1;
```

**Schema Notes:**
1. **Simplified from `department_content`** - Removed 6 unused columns
2. **Compatible with RAG** - All columns from `enterprise_rag.py` queries present
3. **Compatible with Ingestion** - Core columns from `ingest_to_postgres.py` present
4. **Deduplication** - Unique index on `(tenant_id, file_hash, chunk_index)`
5. **Performance** - IVFFlat index for vector search, GIN for keyword search

---

## PHASE 3: PERSONAL SAAS MEMORY COMPONENTS (STUB IDENTIFICATION)

**Scope:** Identify memory components used by CogTwin (personal SaaS) vs EnterpriseTwin (enterprise bot).

**Goal:** Document which components to STUB/DISABLE, not fix. Enterprise bot is priority.

### 3.1 CogTwin Memory Imports (Personal SaaS)

From `core/cog_twin.py:82-107`:

| Component | File | Purpose | Guard Present? | Notes |
|-----------|------|---------|----------------|-------|
| `MetacognitiveMirror` | `memory/metacognitive_mirror.py` | Self-monitoring, phase detection | ❌ No | Always imported |
| `DualRetriever` | `memory/retrieval.py` | Process + Episodic memory | ❌ No | Always imported |
| `AsyncEmbedder` | `memory/embedder.py` | BGE-M3 embeddings | ❌ No | Always imported |
| `MemoryPipeline` | `memory/memory_pipeline.py` | Ingest loop | ✅ Yes | `memory_enabled()` check |
| `CognitiveTracer` | `memory/reasoning_trace.py` | Debug trace recorder | ❌ No | Always imported |
| `ResponseScore` | `memory/scoring.py` | Response quality scoring | ❌ No | Always imported |
| `TrainingModeUI` | `memory/scoring.py` | Training interface | ❌ No | Always imported |
| `ChatMemoryStore` | `memory/chat_memory.py` | Recent exchanges | ❌ No | Always imported |
| `SquirrelTool` | `memory/squirrel.py` | Temporal context retrieval | ✅ Yes | `memory_enabled()` check |

**Total:** 9 memory imports, 2 guarded by `memory_enabled()`.

### 3.2 EnterpriseTwin Memory Usage

From `core/enterprise_twin.py:285`:
```python
from memory_pipeline import MemoryPipeline  # ❌ BROKEN IMPORT (relative path missing)
```

**Total:** 1 memory import, **broken import path**.

**Expected Memory Usage (Enterprise):**
- None for basic tier (`features.memory_pipelines: false` in config.yaml)
- Only RAG retrieval via `EnterpriseRAGRetriever` (not memory pipeline)

### 3.3 Memory Pipeline Guards

From `config.yaml:26-30`:
```yaml
features:
  memory_pipelines: false       # No 5-lane retrieval
  session_memory: false         # Don't remember within session
```

From `core/config_loader.py`:
```python
def memory_enabled() -> bool:
    """Check if memory subsystem is enabled."""
    return cfg('features.memory_pipelines', False)
```

**Usage in CogTwin:**
- Line 269: `if memory_enabled():` - Initialize MemoryPipeline
- Line 345: No guard - Always embeds query
- Line 414: No guard - Always embeds query

**Issue:** Memory components imported even when `memory_pipelines: false`. Imports don't crash, but waste resources.

### 3.4 Stub Strategy (If Needed Later)

**Scenario:** If memory imports cause import errors or performance issues.

| Component | Stub Location | Stub Strategy |
|-----------|---------------|---------------|
| `MetacognitiveMirror` | `memory/metacognitive_mirror.py` | Return empty `QueryEvent` |
| `DualRetriever` | `memory/retrieval.py` | Return empty results |
| `MemoryPipeline` | `memory/memory_pipeline.py` | No-op `enqueue()` |
| `CognitiveTracer` | `memory/reasoning_trace.py` | No-op trace recording |
| `SquirrelTool` | `memory/squirrel.py` | Return "Memory disabled" |

**Stub Template:**
```python
class DualRetriever:
    def __init__(self, *args, **kwargs):
        logger.warning("DualRetriever stub - memory disabled")

    async def retrieve(self, *args, **kwargs):
        return RetrievalResult(
            process_results=[],
            episodic_results=[],
            combined_context="",
            metadata={"stub": True, "reason": "memory_pipelines disabled"}
        )
```

**Recommendation:** Don't stub yet. Wait for actual import errors. Imports are cheap, instantiation is expensive.

### 3.5 Memory Backend Configuration

From `config.yaml:124-135`:
```yaml
memory:
  backend: file                 # "file" or "postgres"

  postgres:
    host: localhost
    port: 5432
    database: enterprise_bot
    user: postgres
    password: ${POSTGRES_PASSWORD}
```

**Current State:**
- Backend: `file` (JSON/NumPy storage in `data/` directory)
- PostgreSQL: Configured but not used
- Personal SaaS memory: Stored in `data/corpus/`, `data/vectors/`, `data/indexes/`

**Data Directory Structure:**
```
data/
├── corpus/
│   ├── nodes.json           # Personal SaaS memory nodes
│   └── episodes.json        # Personal SaaS episodes
├── vectors/
│   ├── nodes.npy            # Personal SaaS embeddings
│   └── episodes.npy         # Personal SaaS embeddings
├── indexes/
│   ├── faiss.index          # Personal SaaS FAISS index
│   └── clusters.json        # Personal SaaS clusters
├── embedding_cache/         # Shared embedding cache
├── reasoning_traces/        # Personal SaaS reasoning logs
└── manifest.json            # Personal SaaS manifest
```

**Enterprise Data:** Should be in PostgreSQL `enterprise.documents`, not `data/` directory.

---

## PHASE 4: INGESTION PIPELINE AUDIT

### 4.1 Pipeline Flow (Current)

```
JSON Chunks → ingest_to_postgres.py → department_content table (❌ MISSING)
    ↓
    Load chunks from Manuals/Driscoll/
    ↓
    Map department slugs (❌ enterprise.departments missing)
    ↓
    Optional: Generate embeddings (--embed flag)
    ↓
    Insert into enterprise.department_content (❌ table missing)
```

**Status:** BROKEN - Both target tables don't exist.

### 4.2 Scripts Inventory

| Script | Location | Purpose | Status | Notes |
|--------|----------|---------|--------|-------|
| `ingest_to_postgres.py` | `memory/ingest/ingest_to_postgres.py` | Main ingestion | ❌ BROKEN | Targets wrong table |
| `pipeline.py` | `memory/ingest/pipeline.py` | Chat export ingestion | ✅ WORKS | For personal SaaS only |
| `docx_to_json_chunks.py` | `memory/ingest/docx_to_json_chunks.py` | DOCX → JSON converter | ⚠️ UNTESTED | Not checked in recon |
| `json_chunk_loader.py` | `memory/ingest/json_chunk_loader.py` | Load JSON chunks | ✅ WORKS | Used by ingest_to_postgres.py |
| `doc_loader.py` | `memory/ingest/doc_loader.py` | Runtime doc loader | ✅ WORKS | Used by EnterpriseTwin (DEPRECATED) |

**Key Finding:** There are TWO ingestion paths:
1. **Batch Ingestion** (`ingest_to_postgres.py`) - Offline, loads JSON chunks into PostgreSQL
2. **Runtime Loading** (`doc_loader.py`) - Online, loads DOCX files directly into LLM context

**Current Workaround:** EnterpriseTwin uses `doc_loader.py` (runtime loading), bypassing broken RAG.

### 4.3 Database Writes (Target Tables)

From `memory/ingest/ingest_to_postgres.py`:

| Line | Operation | Target Table | Status |
|------|-----------|--------------|--------|
| 59 | `SELECT slug, id FROM enterprise.departments` | `enterprise.departments` | ❌ BROKEN |
| 80 | `SELECT ... FROM enterprise.department_content` | `enterprise.department_content` | ❌ BROKEN |
| 194 | `INSERT INTO enterprise.department_content` | `enterprise.department_content` | ❌ BROKEN |

**Fix Required:**
1. Change `enterprise.departments` → Use hardcoded department map or `users.department_access`
2. Change `enterprise.department_content` → `enterprise.documents`
3. Update INSERT column mapping to match new schema

### 4.4 Embedder Integration

From `memory/ingest/ingest_to_postgres.py:31-35`:
```python
# Optional: embedder for vector generation
try:
    from embedder import AsyncEmbedder  # ❌ BROKEN IMPORT
    EMBEDDER_AVAILABLE = True
except ImportError:
    EMBEDDER_AVAILABLE = False
```

**Fix:** Change to `from memory.embedder import AsyncEmbedder`

From `memory/ingest/ingest_to_postgres.py:99-120`:
```python
async def generate_embeddings(chunks: List[LoadedChunk]) -> Dict[str, List[float]]:
    embedder = AsyncEmbedder(provider="deepinfra")
    embeddings = await embedder.embed_batch(
        contents,
        batch_size=10,  # DeepInfra rate limit
        max_concurrent=2,
        show_progress=True
    )
```

**Status:** Logic is correct, import is broken.

**Flag:** `--embed` (optional, can ingest without embeddings and add later)

### 4.5 Source Data Location

From filesystem scan:
```
Manuals/Driscoll/
├── Purchasing/
│   └── purchasing_manual_chunks.json
├── Sales/
│   ├── bid_management_chunks.json
│   ├── sales_support_chunks.json
│   └── telnet_sop_chunks.json
└── Warehouse/
    └── chunks/
        ├── dispatching_manual_chunks.json
        ├── driver_check-in_manual_chunks.json
        ├── driver_manual_chunks.json
        ├── hr_manual_chunks.json
        ├── inventory_control_manual_chunks.json
        └── invoice_cleaning_department_manual_chunks.json
```

**Status:** ✅ JSON chunk files exist (10+ files, ready for ingestion)

**Sample Chunk Structure (Expected):**
```json
{
  "chunk_id": "sales_001",
  "content": "How to process a credit memo...",
  "source_file": "sales_manual.docx",
  "file_hash": "abc123...",
  "department": "sales",
  "category": "procedures",
  "subcategory": "credit",
  "keywords": ["credit", "memo", "refund"],
  "token_count": 245
}
```

### 4.6 Environment Requirements

| Variable | Required By | Purpose | Status |
|----------|-------------|---------|--------|
| `AZURE_PG_HOST` | ingest_to_postgres.py | Database connection | ✅ Required |
| `AZURE_PG_DATABASE` | ingest_to_postgres.py | Database name | ✅ Required |
| `AZURE_PG_USER` | ingest_to_postgres.py | Database user | ✅ Required |
| `AZURE_PG_PASSWORD` | ingest_to_postgres.py | Database password | ✅ Required |
| `AZURE_PG_PORT` | ingest_to_postgres.py | Database port (5432) | ✅ Required |
| `AZURE_PG_SSLMODE` | ingest_to_postgres.py | SSL mode (require) | ✅ Required |
| `DEEPINFRA_API_KEY` | AsyncEmbedder | Embedding generation | ⚠️ Optional (only if --embed) |

**All present in `.env.example`**

### 4.7 Ingestion Issues Found

1. **Wrong Table Names** (3 occurrences)
   - Line 59: `enterprise.departments` → Should use hardcoded map
   - Line 80: `enterprise.department_content` → Should be `enterprise.documents`
   - Line 194: `enterprise.department_content` → Should be `enterprise.documents`

2. **Broken Import** (1 occurrence)
   - Line 32: `from embedder import AsyncEmbedder` → Should be `from memory.embedder import AsyncEmbedder`

3. **Column Mismatch** (19 columns → 15 columns)
   - Current INSERT: 19 columns for `department_content` schema
   - New INSERT: ~15 columns for `documents` schema
   - Columns to REMOVE: `content_type`, `version`, `parent_document_id`, `is_document_root`, `chunk_type`
   - Columns to ADD: None (all required columns present)

4. **Department Mapping** (Logic Issue)
   - Function `get_department_ids()` queries `enterprise.departments` table
   - Alternative: Hardcode department map: `{'sales': 'sales', 'purchasing': 'purchasing', ...}`
   - Or: Query `SELECT DISTINCT unnest(department_access) FROM enterprise.users`

### 4.8 Recommended Fix Order

**Step 1: Create `enterprise.documents` table**
- Run Migration 003 (DDL provided in Section 2.6)
- Verify table creation: `\d enterprise.documents`

**Step 2: Fix `ingest_to_postgres.py` imports**
```python
# Line 32 - Fix broken import
from memory.embedder import AsyncEmbedder  # Was: from embedder import AsyncEmbedder
```

**Step 3: Fix `ingest_to_postgres.py` department mapping**
```python
# Replace lines 56-62
def get_department_ids(conn) -> Dict[str, str]:
    """Get department slug -> slug mapping (no UUID needed)."""
    # Hardcoded map - departments are just strings now
    return {
        'sales': 'sales',
        'purchasing': 'purchasing',
        'warehouse': 'warehouse',
        'credit': 'credit',
        'accounting': 'accounting',
        'it': 'it',
    }
```

**Step 4: Fix `ingest_to_postgres.py` table references**
```python
# Line 80 - Change table name
cur.execute(
    "SELECT DISTINCT file_hash FROM enterprise.documents WHERE file_hash = ANY(%s)",
    (file_hashes,)
)

# Line 194 - Change table name and column list
insert_query = """
    INSERT INTO enterprise.documents (
        tenant_id, department_id, content, section_title, source_file,
        file_hash, chunk_index, chunk_token_count, embedding_model,
        keywords, category, subcategory, embedding, active
    ) VALUES %s
"""
```

**Step 5: Fix INSERT data mapping**
```python
# Lines 162-184 - Simplify row tuple
row = (
    tenant_id,              # tenant_id
    chunk.department,       # department_id (string, not UUID)
    chunk.content,          # content
    chunk.chunk_id,         # section_title
    chunk.source_file,      # source_file
    chunk.file_hash,        # file_hash
    chunk_index,            # chunk_index (use actual index)
    chunk.token_count,      # chunk_token_count
    'BAAI/bge-m3',          # embedding_model
    keywords_json,          # keywords (JSONB)
    chunk.category,         # category
    chunk.subcategory,      # subcategory
    embedding,              # embedding (vector or None)
    True,                   # active
)
```

**Step 6: Test ingestion without embeddings**
```bash
python memory/ingest/ingest_to_postgres.py
# Expected: Insert ~100-500 chunks without embeddings
```

**Step 7: Test ingestion with embeddings**
```bash
python memory/ingest/ingest_to_postgres.py --embed
# Expected: Insert chunks WITH embeddings (slower, ~2-5 minutes)
```

**Step 8: Verify data in database**
```sql
-- Check row counts by department
SELECT department_id, COUNT(*)
FROM enterprise.documents
WHERE tenant_id = (SELECT id FROM enterprise.tenants WHERE slug = 'driscoll')
GROUP BY department_id;

-- Check embedding coverage
SELECT
    department_id,
    COUNT(*) as total,
    COUNT(embedding) as with_embedding,
    COUNT(*) - COUNT(embedding) as without_embedding
FROM enterprise.documents
WHERE tenant_id = (SELECT id FROM enterprise.tenants WHERE slug = 'driscoll')
GROUP BY department_id;

-- Test vector search query (should not crash)
SELECT
    section_title,
    department_id,
    1 - (embedding <=> '[0.1, 0.2, ...]'::vector(1024)) as similarity
FROM enterprise.documents
WHERE tenant_id = (SELECT id FROM enterprise.tenants WHERE slug = 'driscoll')
  AND department_id = 'sales'
  AND embedding IS NOT NULL
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector(1024)
LIMIT 5;
```

**Step 9: Test RAG retrieval via EnterpriseTwin**
```python
# In Python REPL or test script
from core.enterprise_rag import EnterpriseRAGRetriever
from core.config_loader import get_config

config = get_config()
rag = EnterpriseRAGRetriever(config)

results = await rag.search(
    query="how do I process a credit memo",
    department="sales",
    tenant_id="<uuid-from-db>",
    top_k=5,
    threshold=0.6
)

print(f"Found {len(results)} results")
for r in results:
    print(f"  [{r['score']:.2f}] {r['section_title']}")
    print(f"    {r['content'][:100]}...")
```

---

## DELIVERABLES SUMMARY

### Critical Path (Must Do Now)
1. ✅ **This Document** - `docs/EMBEDDER_RAG_RECON.md` (960 lines)
2. ⬜ **Migration 003** - Create `enterprise.documents` table (DDL in Section 2.6)
3. ⬜ **Fix Ingestion Script** - 4 file edits in `ingest_to_postgres.py`
4. ⬜ **Run Ingestion** - `python memory/ingest/ingest_to_postgres.py --embed`
5. ⬜ **Test RAG** - Verify EnterpriseTwin can retrieve manuals

### Environment Checklist
- ✅ `DEEPINFRA_API_KEY` - Required for embeddings
- ✅ `AZURE_PG_*` variables (7 vars) - Required for database
- ⚠️ `CLOUDFLARE_API_TOKEN` - Optional (fallback provider)
- ⚠️ TEI endpoint - Optional (self-hosted provider)

### Code Changes Required (Next Handoff)
**File 1:** `db/migrations/003_create_documents_table.sql` (NEW)
- Create `enterprise.documents` table
- Create 6 indexes (vector, keyword, full-text)
- ~80 lines

**File 2:** `memory/ingest/ingest_to_postgres.py` (EDIT)
- Line 32: Fix import
- Line 56-62: Hardcode department map
- Line 80: Change table name
- Line 194: Change table name and column list
- Line 162-184: Simplify row tuple
- ~8 edits, ~30 lines changed

**File 3:** `core/enterprise_rag.py` (OPTIONAL - Future)
- Replace `EmbeddingClient` with `AsyncEmbedder`
- ~50 lines changed (low priority)

### Success Criteria
- [ ] `enterprise.documents` table exists with 15+ columns
- [ ] Ingestion script runs without errors
- [ ] 100+ chunks inserted into database
- [ ] Embeddings generated for all chunks (or NULL if skipped)
- [ ] RAG retrieval returns results for test query
- [ ] EnterpriseTwin can cite manual chunks in responses

---

## APPENDICES

### A. Glossary

- **BGE-M3** - BAAI General Embedding Model 3, 1024-dim multilingual embeddings
- **DeepInfra** - Hosted embedding API service (rate limited)
- **TEI** - Text Embeddings Inference, self-hosted embedding service (unlimited)
- **pgvector** - PostgreSQL extension for vector similarity search
- **IVFFlat** - Inverted File Flat index for approximate nearest neighbor search
- **RLS** - Row-Level Security (PostgreSQL feature)
- **RAG** - Retrieval-Augmented Generation

### B. Related Files (NOT Checked)

These files are part of the ingestion/RAG system but were not audited in this recon:

- `memory/ingest/docx_to_json_chunks.py` - DOCX → JSON converter (upstream of ingestion)
- `memory/ingest/batch_convert_warehouse.py` - Batch DOCX processing
- `memory/ingest/chat_parser.py` - Chat export parser (personal SaaS only)
- `memory/memory_backend.py` - Memory backend abstraction
- `memory/llm_tagger.py` - LLM-based tagging (not used in basic tier)
- `memory/heuristic_enricher.py` - Heuristic metadata extraction

**Recommendation:** Audit these in next recon if ingestion quality issues arise.

### C. Performance Estimates

**Ingestion Performance (DeepInfra):**
- **Without embeddings:** ~5-10 seconds for 500 chunks
- **With embeddings:** ~3-5 minutes for 500 chunks (180 RPM rate limit)
- **Bottleneck:** DeepInfra API rate limit (180 requests/minute)

**RAG Query Performance:**
- **Vector search:** ~50-200ms (depends on table size, IVFFlat index)
- **Keyword search:** ~10-50ms (full-text index)
- **Total latency:** <300ms for typical query

**Optimization Options:**
- Use TEI for faster embedding (22k embeddings in 2-3 minutes)
- Use IVFFlat index with more lists for larger datasets (>10k chunks)
- Cache frequent queries in Redis (future enhancement)

### D. Security Notes

**RLS (Row-Level Security):**
- Currently NOT enabled on `enterprise.documents`
- Application-level filtering via `tenant_id` and `department_id` WHERE clauses
- **Recommendation:** Enable RLS for defense-in-depth

**RLS Policy Example:**
```sql
-- Enable RLS
ALTER TABLE enterprise.documents ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see documents for their tenant and departments
CREATE POLICY tenant_isolation ON enterprise.documents
    FOR SELECT
    USING (
        tenant_id = current_setting('app.tenant_id')::uuid
        AND (
            department_id = ANY(string_to_array(current_setting('app.department_access'), ','))
            OR department_id IS NULL  -- Shared documents
        )
    );
```

**Set Context in Query:**
```python
# Before RAG query
await conn.execute("SET app.tenant_id = $1", tenant_id)
await conn.execute("SET app.department_access = $1", ','.join(user.department_access))

# Now RLS enforces isolation automatically
results = await conn.fetch("SELECT * FROM enterprise.documents WHERE ...")
```

**Current Status:** Not implemented (future hardening task).

---

**END OF RECONNAISSANCE REPORT**

**Lines:** 960
**Next Steps:** See "Recommended Fix Order" in Section 4.8
**Estimated Time to Fix:** 2-3 hours (including testing)

---

*Generated by Claude Sonnet 4.5 via enterprise_bot SDK*
*Date: 2024-12-22 01:30 UTC*
*Session: EMBEDDER_RAG_RECON*
