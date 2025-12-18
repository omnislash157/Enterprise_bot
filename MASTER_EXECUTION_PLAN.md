# Process Manual RAG Wiring - Master Execution Plan
## CogTwin + Driscoll Manuals Full Integration

**Status:** PHASE 2.5 READY
**Target:** Replace context stuffing with full vector RAG for process manuals
**Timeline:** 17 days (Phase 2.5 parallel, rest sequential)

---

## Executive Summary

The enterprise bot currently **context-stuffs** raw manual JSON into prompts. This plan wires proper **vector RAG** with:

1. PostgreSQL + pgvector storage
2. BGE-M3 embeddings (1024-dim) via DeepInfra
3. Row-Level Security (RLS) for department isolation
4. CogTwin hybrid retrieval (manuals + conversation memory)

---

## Phase Execution Order

```
PHASE 2.5: DOCX Chunking [NOW - PARALLEL]
    |
    v
PHASE 1: Schema Enhancement [SEQUENTIAL]
    |
    v
PHASE 2: RLS Policies [SEQUENTIAL]
    |
    v
PHASE 3: Ingestion Pipeline [SEQUENTIAL]
    |
    v
PHASE 4: CogTwin Integration [SEQUENTIAL]
    |
    v
PHASE 5: Schema Lock [SEQUENTIAL]
```

---

## Phase-by-Phase Commits

### PHASE 2.5: DOCX Chunking (NOW)

**Files Created:**
- `ingestion/docx_to_json_chunks.py`
- `ingestion/batch_convert_warehouse_docx.py`
- `ingestion/__init__.py`
- `docs/PHASE_2_5_EXECUTION.md`

**Files Generated:**
- `Manuals/Driscoll/Warehouse/chunks/*.json` (21 new files)

**Commit:**
```bash
git add ingestion/ docs/PHASE_2_5_EXECUTION.md Manuals/Driscoll/Warehouse/chunks/
git commit -m "feat(ingest): Phase 2.5 - DOCX to JSON chunking pipeline

- Add docx_to_json_chunks.py core chunker module
- Add batch_convert_warehouse_docx.py with parallel support
- Convert 21 Warehouse DOCX files to JSON chunk format
- Total ~287 chunks matching Sales/Purchasing format
- Ready for Phase 3 PostgreSQL ingestion"
```

---

### PHASE 1: Schema Enhancement

**Files to Create/Modify:**
- `db/migrations/002_enhance_department_content.sql`

**Changes:**
- Add `embedding VECTOR(1024)` column
- Add `tenant_id`, `parent_document_id`, `chunk_index`
- Add `source_file`, `file_hash`, `section_title`
- Add `chunk_token_count`, `embedding_model`
- Create IVFFlat index for vector search

**Commit:**
```bash
git add db/migrations/002_enhance_department_content.sql
git commit -m "feat(db): Phase 1 - enhance department_content schema for RAG

- Add embedding VECTOR(1024) column for BGE-M3
- Add chunk hierarchy columns (parent_document_id, chunk_index)
- Add metadata columns (source_file, file_hash, section_title)
- Create IVFFlat vector index for similarity search
- Add unique constraint on (tenant_id, department_id, file_hash)"
```

---

### PHASE 2: RLS Policies

**Files to Create:**
- `db/migrations/003_enable_rls_policies.sql`

**Changes:**
- Enable RLS on `department_content`
- Create SELECT/INSERT/UPDATE/DELETE policies
- Add `enterprise.set_user_context()` function
- Super user bypass logic

**Commit:**
```bash
git add db/migrations/003_enable_rls_policies.sql
git commit -m "feat(db): Phase 2 - implement RLS policies for department isolation

- Enable Row Level Security on department_content
- Add SELECT policy: users see only authorized departments
- Add INSERT/UPDATE policies: dept heads and super users only
- Add DELETE policy: super users only
- Add set_user_context() function for session variables"
```

---

### PHASE 3: Ingestion Pipeline

**Files to Create:**
- `ingestion/json_chunk_loader.py`
- `ingestion/embed_chunks.py`
- `ingestion/ingest_to_postgres.py`

**Changes:**
- Load JSON chunks from all departments
- Generate BGE-M3 embeddings via DeepInfra API
- Insert into `department_content` with embeddings
- Deduplication via `file_hash`

**Commit:**
```bash
git add ingestion/json_chunk_loader.py ingestion/embed_chunks.py ingestion/ingest_to_postgres.py
git commit -m "feat(ingest): Phase 3 - document ingestion with embeddings

- Add json_chunk_loader.py for JSON parsing
- Add embed_chunks.py with DeepInfra BGE-M3 integration
- Add ingest_to_postgres.py for database insertion
- Ingest all 28 JSON files (24 Warehouse + 4 existing)
- ~287 chunks with 1024-dim embeddings in department_content"
```

---

### PHASE 4: CogTwin Integration

**Files to Modify:**
- `tenant_service.py` - Add vector search for department content
- `cog_twin.py` - Integrate manual RAG with memory retrieval
- `retrieval.py` - Add department content to retrieval pipeline

**Changes:**
- `get_relevant_manuals(query, user_id, tenant_id)` function
- Hybrid retrieval: conversation memory + manual chunks
- RLS enforcement via session context

**Commit:**
```bash
git add tenant_service.py cog_twin.py retrieval.py
git commit -m "feat(cogtwin): Phase 4 - integrate manual RAG with memory retrieval

- Add get_relevant_manuals() vector search in tenant_service
- Integrate manual chunks into CogTwin retrieval pipeline
- Hybrid context: conversation memory + process manuals
- RLS enforcement via set_user_context() on every query
- Sub-500ms retrieval target achieved"
```

---

### PHASE 5: Schema Lock

**Files to Create:**
- `docs/SCHEMA_LOCK_V1.md`

**Changes:**
- Document final schema as immutable foundation
- Create tenant provisioning checklist
- Archive deprecated files

**Commit:**
```bash
git add docs/SCHEMA_LOCK_V1.md
git commit -m "docs: Phase 5 - lock multi-tenant schema v1

- Document department_content schema as locked
- Add tenant provisioning checklist
- Driscoll = reference implementation for all future tenants
- Context stuffing officially deprecated
- Full RAG now the only retrieval mode"
```

---

## Current File State

### Already Created (This Session)

```
enterprise_bot/
├── ingestion/
│   ├── __init__.py
│   ├── docx_to_json_chunks.py    [NEW]
│   └── batch_convert_warehouse_docx.py [NEW]
├── docs/
│   ├── PHASE_2_5_EXECUTION.md    [NEW]
│   └── MASTER_EXECUTION_PLAN.md  [NEW]
```

### To Be Created (Subsequent Phases)

```
enterprise_bot/
├── db/migrations/
│   ├── 002_enhance_department_content.sql  [Phase 1]
│   └── 003_enable_rls_policies.sql         [Phase 2]
├── ingestion/
│   ├── json_chunk_loader.py                [Phase 3]
│   ├── embed_chunks.py                     [Phase 3]
│   └── ingest_to_postgres.py               [Phase 3]
├── docs/
│   └── SCHEMA_LOCK_V1.md                   [Phase 5]
```

### Files to Modify

```
tenant_service.py    [Phase 4]
cog_twin.py          [Phase 4]
retrieval.py         [Phase 4]
embedder.py          [Phase 3 - verify DeepInfra integration]
```

---

## Quality Gates

### Phase 2.5 Complete When:
- [ ] 24 JSON chunk files in `Warehouse/chunks/`
- [ ] 4 existing JSON files preserved
- [ ] Total ~287 chunks
- [ ] Git commit done

### Phase 1 Complete When:
- [ ] Migration 002 runs without errors
- [ ] `embedding` column exists with VECTOR(1024) type
- [ ] IVFFlat index created
- [ ] Git commit done

### Phase 2 Complete When:
- [ ] RLS enabled on `department_content`
- [ ] User can only SELECT authorized departments
- [ ] Super user can see all content
- [ ] Git commit done

### Phase 3 Complete When:
- [ ] All 28 JSON files ingested
- [ ] All chunks have embeddings
- [ ] Deduplication working (no duplicate file_hash)
- [ ] Git commit done

### Phase 4 Complete When:
- [ ] Vector search returns relevant manual chunks
- [ ] CogTwin hybrid retrieval working
- [ ] RLS filtering verified
- [ ] Sub-500ms retrieval
- [ ] Git commit done

### Phase 5 Complete When:
- [ ] Schema documentation complete
- [ ] Provisioning checklist written
- [ ] Git commit done

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| DOCX parsing fails | Fallback to single-chunk extraction |
| DeepInfra API rate limit | Batch embeddings, add retry logic |
| RLS performance impact | Measure with EXPLAIN ANALYZE, tune indexes |
| Cross-tenant leakage | Test extensively with multiple test users |

---

## Next Steps

1. **NOW:** Run Phase 2.5 (DOCX chunking) - see `docs/PHASE_2_5_EXECUTION.md`
2. **After 2.5:** Proceed to Phase 1 (schema enhancement)
3. **Sequential:** Complete phases 1 -> 2 -> 3 -> 4 -> 5

---

**Document Version:** 1.0
**Last Updated:** December 18, 2024
**Author:** Matt Hartigan + Claude Opus 4.5
