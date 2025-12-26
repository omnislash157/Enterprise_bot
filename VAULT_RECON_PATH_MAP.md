# VAULT SYSTEM PATH MAP
## Deep Reconnaissance Output for enterprise_bot Data Migration

**Reconnaissance Date:** 2024-12-24
**Target:** enterprise_bot project (working system)
**Vault Location:** `C:\Users\mthar\projects\enterprise_bot\data`
**Status:** ✅ ACTIVE - Contains live data

---

## 1. DIRECTORY STRUCTURE

```
C:\Users\mthar\projects\enterprise_bot\data/
├── archive/                       ← Old memory snapshots (timestamped)
│   ├── episodic_memories/         ← Archived episode files
│   ├── indexes/                   ← Archived cluster/FAISS indexes
│   ├── memory_nodes/              ← Archived node snapshots
│   ├── vectors/                   ← Archived embeddings
│   └── manifest_*.json            ← Archived manifests
│
├── chat_exchanges/                ← 112 files - User Q+A pairs with ratings
│   └── exchange_*.json            ← Written by: ChatMemoryStore
│                                  ← Read by: SquirrelTool (temporal search)
│
├── reasoning_traces/              ← 156 files - Cognitive reasoning steps
│   └── trace_*.json               ← Written by: CognitiveTracer
│                                  ← Read by: Training/ingest pipeline
│
├── memory_nodes/                  ← 34 files - Session memory nodes
│   ├── session_nodes_*.json       ← Written by: MemoryPipeline.flush()
│   └── session_outputs_*.json     ← Written by: MemoryPipeline.flush()
│                                  ← Read by: (Legacy - new system uses corpus/)
│
├── corpus/                        ← UNIFIED memory corpus (v1.0.0 format)
│   ├── nodes.json                 ← All process memory nodes
│   ├── episodes.json              ← All episodic memories
│   └── dedup_index.json           ← Dedup state (currently empty {})
│                                  ← Written by: FileBackend
│                                  ← Read by: DualRetriever._load_unified()
│
├── vectors/                       ← 21 .npy files - Embeddings
│   ├── nodes.npy                  ← Node embeddings (main)
│   ├── episodes.npy               ← Episode embeddings (main)
│   └── session_embeddings_*.npy   ← Session embeddings (legacy)
│                                  ← Written by: MemoryPipeline, AsyncEmbedder
│                                  ← Read by: DualRetriever.load()
│
├── indexes/                       ← Search indexes + clustering
│   ├── faiss.index                ← FAISS vector index (fast ANN search)
│   ├── clusters.json              ← Cluster assignments
│   ├── hdbscan_clusters.json      ← HDBSCAN cluster data
│   ├── hdbscan_model.joblib       ← Trained HDBSCAN model
│   └── cluster_schema.json        ← Cluster semantic profiles
│                                  ← Written by: StreamingClusterEngine
│                                  ← Read by: DualRetriever, ClusterSchemaEngine
│
├── embedding_cache/               ← Embeddings cache (Voyage AI)
│   └── (cache files)              ← Written/Read by: AsyncEmbedder
│
├── episodic_memories/             ← Legacy episodic storage (empty)
│   └── *.json                     ← Old format (migrated to corpus/)
│
├── manifest.json                  ← Unified manifest (v1.0.0)
├── manifest (2).json              ← Legacy backup
├── memory_index.json              ← Minimal index
├── chunks.jsonl                   ← 68MB - Document chunks (RAG data)
└── debug_pipeline_output.json     ← Debug artifacts
```

---

## 2. FILE COUNTS & DATA STATISTICS

| Directory           | File Count | Purpose                        | Active? |
|---------------------|------------|--------------------------------|---------|
| chat_exchanges      | 112        | User conversation history      | ✅ YES  |
| reasoning_traces    | 156        | Cognitive trace logs           | ✅ YES  |
| memory_nodes        | 34         | Session memory (legacy)        | ⚠️ OLD  |
| vectors             | 21         | Embeddings (.npy)              | ✅ YES  |
| indexes             | 6          | FAISS + clusters               | ✅ YES  |
| corpus              | 3          | Unified memory store           | ✅ YES  |
| archive             | ~30        | Historical backups             | 📦 ARCHIVE |
| embedding_cache     | (varies)   | Embedding cache                | ✅ YES  |

**Total Data Size:** ~82MB (including 68MB chunks.jsonl)

---

## 3. WIRE-IN POINTS: WHO READS/WRITES WHAT

### 3.1 DATA DIRECTORY INITIALIZATION

**Primary Entry Point:** `cog_twin.py:234`
```python
self.data_dir = Path(data_dir) if data_dir else Path(cfg("paths.data_dir", "./data"))
```

**Config Source:** `config.yaml:115`
```yaml
paths:
  data_dir: ./data
```

**Resolution Chain:**
1. Command line arg → `CogTwin(data_dir=...)`
2. Config file → `config.yaml:paths.data_dir`
3. Fallback → `"./data"` (hardcoded)

---

### 3.2 MEMORY PIPELINE (Session Outputs)

**File:** `memory_pipeline.py`

**Initialization (cog_twin.py:268-273):**
```python
self.memory_pipeline = MemoryPipeline(
    embedder=self.retriever.embedder,
    data_dir=self.data_dir,  # ← data_dir passed here
    batch_interval=cfg("memory_pipeline.batch_interval", 5.0),
    max_batch_size=cfg("memory_pipeline.max_batch_size", 10),
)
```

**Writes To:**
- **Line 440:** `(self.data_dir / "memory_nodes").mkdir(parents=True, exist_ok=True)`
- **Line 441:** `(self.data_dir / "vectors").mkdir(parents=True, exist_ok=True)`
- **Line 444:** `nodes_file = self.data_dir / "memory_nodes" / f"session_nodes_{timestamp}.json"`
- **Line 450:** `emb_file = self.data_dir / "vectors" / f"session_embeddings_{timestamp}.npy"`
- **Line 454:** `outputs_file = self.data_dir / "memory_nodes" / f"session_outputs_{timestamp}.json"`

**Purpose:** Persists session-level cognitive outputs to disk.

---

### 3.3 DUAL RETRIEVER (Memory Loading)

**File:** `retrieval.py`

**Initialization (cog_twin.py:241):**
```python
self.retriever = DualRetriever.load(self.data_dir)
```

**Load Method (retrieval.py:431-461):**
```python
@classmethod
def load(cls, data_dir: Path, manifest_file: Optional[str] = None) -> "DualRetriever":
    data_dir = Path(data_dir)

    # NEW: Unified manifest (v1.0.0)
    unified_manifest = data_dir / "manifest.json"
    if unified_manifest.exists():
        return cls._load_unified(data_dir)

    # LEGACY: Session-based manifests
    manifests = list(data_dir.glob("manifest_*.json"))
    return cls._load_legacy(data_dir, manifest_path)
```

**Unified Load (_load_unified method):**
- **Line 473:** `nodes_file = data_dir / "corpus" / "nodes.json"`
- **Line 480:** `episodes_file = data_dir / "corpus" / "episodes.json"`
- **Line 487:** `node_emb_file = data_dir / "vectors" / "nodes.npy"`
- **Line 491:** `episode_emb_file = data_dir / "vectors" / "episodes.npy"`
- **Line 496:** `clusters_file = data_dir / "indexes" / "clusters.json"`
- **Line 509:** `faiss_file = data_dir / "indexes" / "faiss.index"`
- **Line 519:** `embedder = AsyncEmbedder(cache_dir=data_dir / "embedding_cache")`
- **Line 523:** `schema_file = data_dir / "indexes" / "cluster_schema.json"`

**Legacy Load (_load_legacy method):**
- **Line 567:** `nodes_file = data_dir / "memory_nodes" / manifest["nodes_file"]`
- **Line 573:** `episodes_file = data_dir / "episodic_memories" / manifest["episodes_file"]`
- **Line 579:** `node_emb_file = data_dir / "vectors" / manifest["node_embeddings_file"]`
- **Line 582:** `episode_emb_file = data_dir / "vectors" / manifest["episode_embeddings_file"]`
- **Line 586:** `clusters_file = data_dir / "indexes" / manifest["clusters_file"]`
- **Line 600:** `faiss_file = data_dir / "indexes" / manifest["faiss_index_file"]`

**Purpose:** Loads all memory data into retrieval engine at startup.

---

### 3.4 CHAT MEMORY STORE (Conversation History)

**File:** `chat_memory.py`

**Initialization (cog_twin.py:284):**
```python
self.chat_memory = ChatMemoryStore(self.data_dir)
```

**Constructor (chat_memory.py:102-105):**
```python
def __init__(self, data_dir: Path):
    self.data_dir = Path(data_dir)
    self.exchanges_dir = self.data_dir / "chat_exchanges"
    self.exchanges_dir.mkdir(parents=True, exist_ok=True)
```

**Writes To:**
- `chat_exchanges/exchange_{id}.json` (one file per exchange)

**Reads From:**
- Loads all `exchange_*.json` files at startup

**Purpose:** Stores user Q+A pairs with ratings for temporal retrieval via Squirrel.

---

### 3.5 COGNITIVE TRACER (Reasoning Traces)

**File:** `reasoning_trace.py`

**Initialization (cog_twin.py:280):**
```python
self.tracer = CognitiveTracer(self.data_dir, memory_pipeline=self.memory_pipeline)
```

**Constructor (reasoning_trace.py:199-201):**
```python
def __init__(self, data_dir: Path, memory_pipeline=None):
    self.data_dir = Path(data_dir)
    self.traces_dir = self.data_dir / "reasoning_traces"
```

**Writes To:**
- `reasoning_traces/trace_{id}.json`

**Purpose:** Logs step-by-step reasoning for training/analysis.

---

### 3.6 CLUSTER SCHEMA ENGINE

**File:** `cluster_schema.py`

**Initialization (cluster_schema.py:105-125):**
```python
def __init__(self, data_dir: Path):
    self.data_dir = Path(data_dir)
    self.schema_file = self.data_dir / "indexes" / "cluster_schema.json"

    # Load manifest
    manifest_path = self.data_dir / manifest_file
    # Or find latest: manifests = list(self.data_dir.glob("manifest_*.json"))
```

**Reads From:**
- **Line 144:** `nodes_file = self.data_dir / "memory_nodes" / manifest["nodes_file"]`
- **Line 149:** `emb_file = self.data_dir / "vectors" / manifest["node_embeddings_file"]`
- **Line 157:** `clusters_file = self.data_dir / "indexes" / manifest["clusters_file"]`

**Writes To:**
- `indexes/cluster_schema.json`

**Purpose:** Generates semantic profiles for clusters.

---

### 3.7 STREAMING CLUSTER ENGINE

**File:** `streaming_cluster.py`

**Initialization (streaming_cluster.py:74-98):**
```python
def __init__(self, data_dir: Path, ...):
    self.data_dir = Path(data_dir)
    default_path = self.data_dir / "indexes" / "hdbscan_model.joblib"
```

**Reads From:**
- **Line 152:** `vectors_dir = self.data_dir / "vectors"`
- Loads all `.npy` files from vectors/

**Writes To:**
- **Line 363:** `session_file = self.data_dir / "indexes" / f"session_clusters_{timestamp}.json"`

**Purpose:** Real-time clustering of new memories.

---

### 3.8 DEDUP SYSTEM

**File:** `dedup.py`

**Location:** `data_dir / "dedup_index.json"` (root level)
**Note:** Also exists in `corpus/dedup_index.json` (empty)

**Used By:**
- `dedup.py:45` - `load_dedup_index(data_dir)`
- `dedup.py:61` - `save_dedup_index(data_dir, index)`
- `cog_twin.py:1519` - `with DedupBatch(twin.data_dir) as dedup:`

**Storage Format:**
```json
{
  "ingested_ids": ["id1", "hash1", "id2", ...]
}
```

**Keys Stored:**
1. Item IDs (e.g., `trace_abc123`)
2. Content hashes (SHA256[:16] of content)

**Purpose:** Prevents duplicate ingestion when re-importing traces/exchanges.

---

## 4. CONFIG DEPENDENCIES

| Config Key                  | Default Value | Used By                          |
|----------------------------|---------------|----------------------------------|
| `paths.data_dir`           | `./data`      | CogTwin, all memory systems      |
| `memory_pipeline.batch_interval` | `5.0` | MemoryPipeline                   |
| `memory_pipeline.max_batch_size` | `10`  | MemoryPipeline                   |
| `retrieval.process_top_k`  | `10`          | DualRetriever                    |
| `retrieval.episodic_top_k` | `5`           | DualRetriever                    |
| `retrieval.min_score`      | `0.3`         | DualRetriever                    |

**Environment Variables:**
- `XAI_API_KEY` - For Grok model
- `ANTHROPIC_API_KEY` - For Claude model
- `VOYAGE_API_KEY` - For embeddings

---

## 5. DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERACTION                         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 v
         ┌──────────────┐
         │   CogTwin    │ ← Entry point (cog_twin.py:234)
         │  data_dir    │    Reads: config.yaml or CLI arg
         └──────┬───────┘
                │
      ┌─────────┼─────────────────────────┐
      │         │                         │
      v         v                         v
┌──────────┐ ┌──────────────┐    ┌───────────────┐
│ChatMemory│ │DualRetriever │    │MemoryPipeline │
│  Store   │ │              │    │               │
└────┬─────┘ └──────┬───────┘    └───────┬───────┘
     │              │                     │
     │              │                     │
  WRITES         READS                 WRITES
     │              │                     │
     v              v                     v
┌──────────────────────────────────────────────────────┐
│              DATA DIRECTORY (./data)                  │
├──────────────────────────────────────────────────────┤
│ chat_exchanges/     ← ChatMemoryStore                │
│ reasoning_traces/   ← CognitiveTracer                │
│ memory_nodes/       ← MemoryPipeline (legacy)        │
│ corpus/             ← FileBackend (unified)          │
│   ├── nodes.json    ← DualRetriever reads this       │
│   └── episodes.json ← DualRetriever reads this       │
│ vectors/            ← MemoryPipeline + AsyncEmbedder │
│   ├── nodes.npy     ← DualRetriever reads this       │
│   └── episodes.npy  ← DualRetriever reads this       │
│ indexes/            ← StreamingClusterEngine         │
│   ├── faiss.index   ← DualRetriever reads this       │
│   └── clusters.json ← DualRetriever reads this       │
└──────────────────────────────────────────────────────┘
```

---

## 6. CRITICAL FILES FOR MIGRATION

### Must-Have Files (Core System Won't Work Without These):
1. ✅ `manifest.json` - Tells retriever what files to load
2. ✅ `corpus/nodes.json` - All process memories
3. ✅ `corpus/episodes.json` - All episodic memories
4. ✅ `vectors/nodes.npy` - Node embeddings
5. ✅ `vectors/episodes.npy` - Episode embeddings
6. ✅ `indexes/clusters.json` - Cluster assignments
7. ⚠️ `indexes/faiss.index` - Fast ANN search (can rebuild)

### Nice-to-Have (Will Degrade Gracefully):
- `chat_exchanges/*.json` - Squirrel won't work without this
- `reasoning_traces/*.json` - Training data (can re-import)
- `indexes/cluster_schema.json` - Semantic profiles (can rebuild)
- `indexes/hdbscan_model.joblib` - Clustering model (can retrain)
- `corpus/dedup_index.json` - Prevents duplicates (can rebuild)

### Can Ignore:
- `archive/` - Old data
- `memory_nodes/` - Legacy format (migrated to corpus/)
- `chunks.jsonl` - RAG documents (not memory system)
- `debug_pipeline_output.json` - Debug artifacts

---

## 7. FILE NAMING CONVENTIONS

**Session Files (Timestamped):**
- `session_nodes_YYYYMMDD_HHMMSS.json`
- `session_embeddings_YYYYMMDD_HHMMSS.npy`
- `session_outputs_YYYYMMDD_HHMMSS.json`

**Exchange Files (ID-based):**
- `exchange_{id}.json` where ID = `f"{timestamp_unix}_{hash(query)[:8]}"`

**Trace Files (ID-based):**
- `trace_{id}.json` where ID = generated by CognitiveTracer

**Unified Files (No timestamp):**
- `nodes.json`, `episodes.json`, `nodes.npy`, `episodes.npy`

---

## 8. SPECIAL NOTES

### Dual Manifest System
The system supports TWO loading modes:
1. **Unified (v1.0.0):** Single `manifest.json` + `corpus/` directory
2. **Legacy:** Timestamped `manifest_*.json` + session files

**Current Status:** Using **unified format** (manifest.json exists)

### Dedup Location Confusion
Dedup index exists in TWO places:
1. `data_dir/dedup_index.json` (expected by dedup.py)
2. `data_dir/corpus/dedup_index.json` (empty, wrong location)

**Action Required:** Verify dedup.py:45 is looking in the right place.

### Archive Directory
The `archive/` folder contains old data snapshots from Nov 28 - Dec 1.
These are NOT loaded by the system - safe to delete or ignore.

---

## 9. VERIFICATION COMMANDS

```bash
# Verify data directory exists
ls -la "C:\Users\mthar\projects\enterprise_bot\data"

# Count memory files
find data/memory_nodes -name "*.json" | wc -l  # Should see 34
find data/vectors -name "*.npy" | wc -l        # Should see 21
find data/chat_exchanges -name "*.json" | wc -l # Should see 112
find data/reasoning_traces -name "*.json" | wc -l # Should see 156

# Check manifest
cat data/manifest.json

# Check dedup index
cat data/corpus/dedup_index.json

# Test load
python -c "from memory.retrieval import DualRetriever; r = DualRetriever.load('data'); print(f'Loaded {len(r.process.nodes)} nodes')"
```

---

**END OF PATH MAP**
