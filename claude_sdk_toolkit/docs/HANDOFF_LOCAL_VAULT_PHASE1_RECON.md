# HANDOFF: Local Vault Architecture - Phase 1 (Reconnaissance)

## Status: READY FOR SDK AGENT

## Mission Brief

We're implementing a local-first storage architecture (like Claude's `.claude` folder) where CogTwin stores all memory data locally and syncs to B2 as backup. Before we can implement, we need a complete map of every file path expectation across the codebase.

## The Problem

Currently there's a disconnect:
- **Pipeline** writes to B2 vault (`users/{user_id}/corpus/nodes.json`)
- **Retrieval** reads from local filesystem (`data_dir / "corpus" / "nodes.json"`)
- These don't connect - queries can't see ingested data

## The Solution (High Level)

Create `~/.cogzy/` (or platform equivalent) as the primary storage location:
- All reads happen from local
- All writes go local first, then async sync to B2
- B2 becomes backup/sync layer, not primary storage

## Phase 1 Objective

**Hunt down EVERY file path reference** in the codebase and document:
1. What file/folder is expected
2. Is it a READ or WRITE operation
3. What module/function uses it
4. What format (JSON, NPY, FAISS index, etc.)

---

## Files to Search

Search these files exhaustively:

### Core Memory Files
- [ ] `pipeline.py` - Ingestion pipeline
- [ ] `retrieval.py` - Memory retrieval
- [ ] `memory_backend.py` - Backend storage
- [ ] `memory_pipeline.py` - Memory processing
- [ ] `chat_memory.py` - Chat memory handling

### Index/Search Files
- [ ] `hybrid_search.py` - Hybrid search
- [ ] `deep_context_search.py` - Deep context
- [ ] `fast_filter.py` - Fast filtering
- [ ] `streaming_cluster.py` - Clustering
- [ ] `cluster_schema.py` - Cluster schemas

### Embedding Files
- [ ] `embedder.py` - Embedding generation
- [ ] `scoring.py` - Scoring functions

### Supporting Files
- [ ] `dedup.py` - Deduplication
- [ ] `heuristic_enricher.py` - Enrichment
- [ ] `enrichment_pipeline.py` - Enrichment pipeline
- [ ] `llm_tagger.py` - LLM tagging
- [ ] `squirrel.py` - Temporal recall
- [ ] `memory_grep.py` - BM25 search

### Trace/Meta Files
- [ ] `reasoning_trace.py` - Reasoning traces
- [ ] `read_traces.py` - Trace reading
- [ ] `metacognitive_mirror.py` - Metacognition
- [ ] `evolution_engine.py` - Evolution tracking

### Auth/Vault Files
- [ ] `personal_vault_routes.py` - Vault API routes
- [ ] `personal_auth.py` - Personal auth
- [ ] `personal_auth_routes.py` - Auth routes
- [ ] `tenant_service.py` - Multi-tenant service

---

## Expected Output Format

Create a markdown table for each file with this structure:

```markdown
### pipeline.py

| Line | Path/Pattern | R/W | Format | Function/Context |
|------|--------------|-----|--------|------------------|
| 473 | `data_dir / "corpus" / "nodes.json"` | W | JSON | `_save_unified()` |
| 487 | `data_dir / "vectors" / "nodes.npy"` | W | NPY | `_save_unified()` |
| ... | ... | ... | ... | ... |
```

---

## Search Patterns

Use these grep patterns to find path references:

```bash
# File path constructions
grep -n "Path\|\.json\|\.npy\|\.index\|data_dir\|output_dir\|corpus\|vectors\|indexes\|manifest\|cache" <file>

# Open/save operations
grep -n "open(\|save\|load\|read\|write\|download\|upload" <file>

# Directory operations
grep -n "mkdir\|exists\|listdir\|glob" <file>

# B2/Vault specific
grep -n "vault\|bucket\|b2\|upload_bytes\|download_file" <file>
```

---

## Specific Questions to Answer

1. **Corpus Files**
   - Where does `nodes.json` get written?
   - Where does `nodes.json` get read from?
   - Same for `episodes.json`

2. **Vector Files**
   - Where does `nodes.npy` get written?
   - Where does `nodes.npy` get read from?
   - Same for `episodes.npy`

3. **Index Files**
   - Where does `faiss.index` get created?
   - Where does `clusters.json` get written?
   - Where does `manifest.json` live?

4. **Cache Files**
   - Where does embedding cache live?
   - Any other caches?

5. **B2 Vault Paths**
   - What's the full B2 path structure for users?
   - `users/{user_id}/corpus/nodes.json`?
   - `users/{user_id}/vectors/nodes.npy`?
   - Document the exact B2 path hierarchy

6. **Config Files**
   - Any `.env` or config file paths?
   - API key storage?

---

## Deliverable

Create a single comprehensive document:

```
VAULT_PATH_MAP.md
├── Summary of all unique paths
├── Per-file breakdown tables
├── B2 path hierarchy diagram
├── Local path hierarchy diagram
├── Conflicts/inconsistencies found
└── Recommendations for canonical structure
```

---

## Success Criteria

Phase 1 is complete when we have:
- [ ] Every file path reference documented
- [ ] Clear R/W designation for each
- [ ] B2 vs local distinction clear
- [ ] Any hardcoded paths identified
- [ ] Any inconsistencies flagged
- [ ] Ready to make architecture decisions for Phase 2

---

## Notes for Agent

- Be exhaustive - we need EVERY path reference
- Flag any hardcoded absolute paths
- Note any user_id or tenant_id path interpolation
- Look for both sync and async file operations
- Check for any Windows vs Unix path issues
- Document default values for optional path params

---

## After Phase 1

Return findings to human for architecture decisions:
1. Finalize canonical local folder structure
2. Decide on path naming conventions
3. Resolve any conflicts found
4. Then kick off Phase 2 for implementation
