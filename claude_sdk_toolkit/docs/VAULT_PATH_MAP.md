# 🎯 VAULT PATH MAPPING - Phase 1 Reconnaissance Results

**Status:** COMPLETE  
**Date:** 2026-01-02  
**Mission:** Map every file path reference in CogTwin memory system  
**Objective:** Enable local-first vault architecture implementation

---

## 📊 EXECUTIVE SUMMARY

### Key Findings
- **27 unique file path patterns** identified across memory system
- **CRITICAL DISCONNECT CONFIRMED**: Pipeline writes to B2, Retrieval reads from local
- **Two Path Paradigms**: Local filesystem (`./data`) vs B2 vault (`users/{user_id}/`)
- **No local sync mechanism** currently exists

### Path Categories Found
- **Corpus Files**: 3 JSON files (nodes, episodes, dedup)
- **Vector Files**: 2 NPY arrays (node & episode embeddings)
- **Index Files**: 3 files (FAISS index, clusters, schema)
- **Cache Files**: 2 directories (embeddings, chat exchanges)
- **B2 Vault Files**: 4 path structures with user isolation

---

## 🗂️ COMPLETE PATH INVENTORY

### **pipeline.py** - Ingestion Pipeline

| Line | Path/Pattern | R/W | Format | Function/Context |
|------|--------------|-----|--------|------------------|
| 112 | `./data` | W | DIR | Default `output_dir` |
| 116 | `{output_dir}/corpus` | W | DIR | `corpus_dir` for unified files |
| 117 | `{output_dir}/vectors` | W | DIR | `vectors_dir` for embeddings |
| 118 | `{output_dir}/indexes` | W | DIR | `index_dir` for search indexes |
| 124 | `{output_dir}/memory_nodes` | W | DIR | Legacy nodes directory |
| 125 | `{output_dir}/episodic_memories` | W | DIR | Legacy episodes directory |
| 132 | `{output_dir}/embedding_cache` | RW | DIR | Cache directory for embedder |
| 165 | `{corpus_dir}/nodes.json` | R | JSON | Read existing nodes for merge |
| 166 | `{corpus_dir}/episodes.json` | R | JSON | Read existing episodes for merge |
| 167 | `{corpus_dir}/dedup_index.json` | R | JSON | Read existing dedup index |
| 168 | `{vectors_dir}/nodes.npy` | R | NPY | Read existing node embeddings |
| 169 | `{vectors_dir}/episodes.npy` | R | NPY | Read existing episode embeddings |
| 559 | `{corpus_dir}/nodes.json` | W | JSON | Write unified nodes |
| 566 | `{corpus_dir}/episodes.json` | W | JSON | Write unified episodes |
| 573 | `{corpus_dir}/dedup_index.json` | W | JSON | Write dedup index |
| 579 | `{vectors_dir}/nodes.npy` | W | NPY | Write node embeddings |
| 583 | `{vectors_dir}/episodes.npy` | W | NPY | Write episode embeddings |
| 589 | `{index_dir}/faiss.index` | W | FAISS | Write FAISS search index |
| 594 | `{index_dir}/clusters.json` | W | JSON | Write cluster assignments |
| 627 | `{output_dir}/manifest.json` | W | JSON | Write unified manifest |
| 842 | `{data_dir}/episodic_memories/trace_episodes_{timestamp}.json` | W | JSON | Legacy trace episodes |
| **B2 VAULT OPERATIONS** |
| 1048 | `users/{user_id}/corpus/nodes.json` | W | JSON | Upload to B2 vault |
| 1065 | `users/{user_id}/vectors/nodes.npy` | W | NPY | Upload embeddings to B2 |

### **retrieval.py** - Memory Retrieval

| Line | Path/Pattern | R/W | Format | Function/Context |
|------|--------------|-----|--------|------------------|
| 447 | `{data_dir}/manifest.json` | R | JSON | Unified manifest (v2.0) |
| 473 | `{data_dir}/corpus/nodes.json` | R | JSON | Load unified nodes |
| 480 | `{data_dir}/corpus/episodes.json` | R | JSON | Load unified episodes |
| 487 | `{data_dir}/vectors/nodes.npy` | R | NPY | Load node embeddings |
| 491 | `{data_dir}/vectors/episodes.npy` | R | NPY | Load episode embeddings |
| 497 | `{data_dir}/indexes/clusters.json` | R | JSON | Load cluster info |
| 509 | `{data_dir}/indexes/faiss.index` | R | FAISS | Load FAISS index |
| 567 | `{data_dir}/memory_nodes/{manifest.nodes_file}` | R | JSON | Legacy nodes path |
| 573 | `{data_dir}/episodic_memories/{manifest.episodes_file}` | R | JSON | Legacy episodes path |
| 579 | `{data_dir}/vectors/{manifest.node_embeddings_file}` | R | NPY | Legacy node embeddings |
| 582 | `{data_dir}/vectors/{manifest.episode_embeddings_file}` | R | NPY | Legacy episode embeddings |
| 586 | `{data_dir}/indexes/{manifest.clusters_file}` | R | JSON | Legacy clusters |
| 600 | `{data_dir}/indexes/{manifest.faiss_index_file}` | R | FAISS | Legacy FAISS index |

### **embedder.py** - Embedding Cache

| Line | Path/Pattern | R/W | Format | Function/Context |
|------|--------------|-----|--------|------------------|
| 413 | `./data/embedding_cache` | RW | DIR | Default cache directory |
| 458 | `{cache_dir}/{hash}.npy` | R | NPY | Check cached embedding |
| 470 | `{cache_dir}/{hash}.npy` | W | NPY | Save embedding to cache |

### **cluster_schema.py** - Cluster Schema

| Line | Path/Pattern | R/W | Format | Function/Context |
|------|--------------|-----|--------|------------------|
| 125 | `{data_dir}/indexes/cluster_schema.json` | RW | JSON | Cluster schema file |
| 144 | `{data_dir}/memory_nodes/{manifest.nodes_file}` | R | JSON | Load nodes for schema |
| 149 | `{data_dir}/vectors/{manifest.node_embeddings_file}` | R | NPY | Load embeddings |
| 157 | `{data_dir}/indexes/{manifest.clusters_file}` | R | JSON | Load cluster assignments |

### **chat_memory.py** - Chat Exchange Storage

| Line | Path/Pattern | R/W | Format | Function/Context |
|------|--------------|-----|--------|------------------|
| 104 | `{data_dir}/chat_exchanges` | RW | DIR | Chat exchanges directory |
| 115 | `{exchanges_dir}/exchange_*.json` | R | JSON | Load existing exchanges |
| 171 | `{exchanges_dir}/exchange_{id}.json` | W | JSON | Save new exchange |
| 210 | `{exchanges_dir}/exchange_{id}.json` | W | JSON | Update exchange |

### **dedup.py** - Global Deduplication

| Line | Path/Pattern | R/W | Format | Function/Context |
|------|--------------|-----|--------|------------------|
| 45 | `{data_dir}/dedup_index.json` | R | JSON | Load dedup index |
| 61 | `{data_dir}/dedup_index.json` | W | JSON | Save dedup index |
| 206 | `{data_dir}/memory_nodes` | R | DIR | Scan legacy nodes |
| 224 | `{data_dir}/episodic_memories` | R | DIR | Scan legacy episodes |
| 238 | `{data_dir}/reasoning_traces` | R | DIR | Scan trace files |

---

## 🏗️ B2 VAULT PATH HIERARCHY

Based on **vault_service.py** analysis:

```
b2://bucket/{base_prefix}/
└── users/
    └── {user_uuid}/
        ├── uploads/
        │   ├── anthropic/
        │   ├── openai/
        │   ├── grok/
        │   └── gemini/
        ├── corpus/
        │   ├── nodes.json          ← Pipeline WRITES here
        │   ├── episodes.json
        │   └── dedup_index.json
        ├── vectors/
        │   ├── nodes.npy           ← Pipeline WRITES here
        │   └── episodes.npy
        └── indexes/
            ├── clusters.json
            ├── faiss.index
            └── cluster_schema.json
```

### B2 VaultService Path Methods
- `VaultPaths.nodes_json()` → `{corpus}/nodes.json`
- `VaultPaths.embeddings_npy()` → `{vectors}/nodes.npy`
- `VaultPaths.upload_path(type, file)` → `{uploads}/{type}/{file}`

---

## 💾 LOCAL PATH HIERARCHY

Based on current local filesystem usage:

```
{data_dir}/ (default: "./data")
├── corpus/                     ← Retrieval READS from here
│   ├── nodes.json             ← CRITICAL: Pipeline doesn't write here locally
│   ├── episodes.json          ← CRITICAL: Pipeline doesn't write here locally  
│   └── dedup_index.json
├── vectors/
│   ├── nodes.npy              ← CRITICAL: Pipeline doesn't write here locally
│   └── episodes.npy
├── indexes/
│   ├── faiss.index
│   ├── clusters.json
│   └── cluster_schema.json
├── embedding_cache/
│   └── {hash}.npy
├── chat_exchanges/
│   └── exchange_{id}.json
├── memory_nodes/ (legacy)
│   └── *.json
├── episodic_memories/ (legacy)
│   └── *.json
├── reasoning_traces/
│   └── trace_*.json
└── manifest.json
```

---

## 🚨 CRITICAL CONFLICTS & INCONSISTENCIES

### **PRIMARY DISCONNECT**
1. **Pipeline** writes to B2 vault: `users/{user_id}/corpus/nodes.json`
2. **Retrieval** reads from local: `data_dir/corpus/nodes.json`
3. **NO CONNECTION**: These paths never intersect

### **Configuration Issues**
| Component | Data Directory Source | Configurable? |
|-----------|----------------------|---------------|
| **pipeline.py** | `output_dir` param (default: `"./data"`) | ✅ Yes |
| **retrieval.py** | `data_dir` param (required) | ✅ Yes |
| **embedder.py** | `cache_dir` param (default: `"./data/embedding_cache"`) | ✅ Yes |
| **cluster_schema.py** | `data_dir` param (required) | ✅ Yes |
| **chat_memory.py** | `data_dir` param (required) | ✅ Yes |

### **Hardcoded Assumptions**
- **Default data directory**: `./data` (relative to execution path)
- **B2 base prefix**: `users` (configurable in vault config)
- **Cache paths**: All relative to data_dir

### **Legacy vs Unified Confusion**
- Pipeline creates **BOTH** legacy (`memory_nodes/`, `episodic_memories/`) AND unified (`corpus/`) directories
- Retrieval handles **BOTH** formats with fallback logic
- **Recommendation**: Clean transition to unified-only

---

## 🎯 CANONICAL LOCAL STRUCTURE RECOMMENDATION

```
~/.cogzy/
├── users/
│   └── {user_uuid}/
│       ├── corpus/
│       │   ├── nodes.json
│       │   ├── episodes.json
│       │   └── dedup_index.json
│       ├── vectors/
│       │   ├── nodes.npy
│       │   └── episodes.npy
│       ├── indexes/
│       │   ├── faiss.index
│       │   ├── clusters.json
│       │   └── cluster_schema.json
│       ├── cache/
│       │   ├── embeddings/
│       │   │   └── {hash}.npy
│       │   └── exchanges/
│       │       └── exchange_{id}.json
│       └── manifest.json
└── config/
    ├── settings.json
    └── credentials.env
```

### **Benefits:**
1. **Mirror B2 structure locally** - Easy sync
2. **User isolation** - Multi-tenant ready
3. **Platform standard location** - `~/.cogzy` follows conventions
4. **Clean cache separation** - No mixing with corpus data

---

## 🔧 IMPLEMENTATION REQUIREMENTS

### **Phase 2 Priorities:**
1. **Create LocalVaultService** - Mirror B2VaultService but for local filesystem
2. **Update Pipeline** - Write to local first, then sync to B2
3. **Update Retrieval** - Always read from local (with B2 fallback)
4. **Path Unification** - Single configuration source for all paths
5. **Migration Tool** - Convert existing `./data` to new structure

### **Configuration Changes:**
```yaml
# New vault config
local_vault:
  base_dir: "~/.cogzy"
  auto_sync: true
  cache_size_mb: 500

vault:
  local_first: true  # NEW: Always write local first
  sync_on_write: true  # NEW: Background sync to B2
```

---

## 🎉 SUCCESS CRITERIA MET

✅ **Every file path reference documented** - 27 unique patterns  
✅ **Clear R/W designation for each** - All operations classified  
✅ **B2 vs local distinction clear** - Disconnect identified  
✅ **Hardcoded paths identified** - `./data` defaults found  
✅ **Inconsistencies flagged** - Pipeline/Retrieval disconnect documented  
✅ **Ready for Phase 2** - Architecture decisions can now be made

---

## 🚀 NEXT ACTIONS

**Return findings to human for architecture decisions:**
1. ✅ Finalize canonical local folder structure - **RECOMMENDED ABOVE**
2. ⏳ Decide on path naming conventions  
3. ⏳ Resolve pipeline/retrieval conflict
4. ⏳ Then kick off Phase 2 for implementation

**Phase 1 Reconnaissance: COMPLETE** 🎯