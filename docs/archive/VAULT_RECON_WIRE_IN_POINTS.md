# VAULT WIRE-IN POINTS
## Complete Code Reference for Data Directory Usage

**Generated:** 2024-12-24
**Purpose:** Line-by-line mapping of how code interacts with the data directory

---

## TABLE OF CONTENTS
1. [Primary Entry Points](#1-primary-entry-points)
2. [Configuration Loading](#2-configuration-loading)
3. [Memory Pipeline](#3-memory-pipeline)
4. [Dual Retriever](#4-dual-retriever)
5. [Chat Memory Store](#5-chat-memory-store)
6. [Cognitive Tracer](#6-cognitive-tracer)
7. [Dedup System](#7-dedup-system)
8. [Cluster Engines](#8-cluster-engines)
9. [Memory Backend](#9-memory-backend)
10. [Ingest Pipeline](#10-ingest-pipeline)

---

## 1. PRIMARY ENTRY POINTS

### `core/cog_twin.py` - The System Hub

**Initialization (Lines 219-234):**
```python
def __init__(
    self,
    data_dir: Optional[Path] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
):
    # Load from config.yaml with argument overrides
    self.data_dir = Path(data_dir) if data_dir else Path(cfg("paths.data_dir", "./data"))
```
- **Line 234:** Sets `self.data_dir` from arg → config → default
- **Config Key:** `paths.data_dir`
- **Default:** `"./data"`

**Component Initialization:**
```python
# Line 241: Load retriever FIRST
self.retriever = DualRetriever.load(self.data_dir)

# Line 268-273: Initialize memory pipeline
self.memory_pipeline = MemoryPipeline(
    embedder=self.retriever.embedder,
    data_dir=self.data_dir,
    batch_interval=cfg("memory_pipeline.batch_interval", 5.0),
    max_batch_size=cfg("memory_pipeline.max_batch_size", 10),
)

# Line 280: Initialize tracer
self.tracer = CognitiveTracer(self.data_dir, memory_pipeline=self.memory_pipeline)

# Line 284: Initialize chat memory
self.chat_memory = ChatMemoryStore(self.data_dir)
```

**Usage in CLI (Lines 1389-1530):**
```python
# Line 1389: CLI argument parsing
data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None

# Line 1397: Pass to constructor
twin = CogTwin(data_dir=data_dir)

# Line 1517: Access for ingest
traces_dir = twin.data_dir / "reasoning_traces"

# Line 1519-1520: Dedup + ingest
with DedupBatch(twin.data_dir) as dedup:
    stats = ingest_reasoning_traces(traces_dir, twin.data_dir, dedup)

# Line 1530: Reload retriever after ingest
twin.retriever = DualRetriever.load(twin.data_dir)
```

---

### `core/main.py` - Alternate Entry Point

**Line 59:**
```python
data_dir: Path = Path("./data")
```
- Hardcoded default (not configurable)

---

## 2. CONFIGURATION LOADING

### `core/config.yaml` - Source of Truth

**Lines 114-116:**
```yaml
paths:
  data_dir: ./data              # Will be empty (no memories yet)
  manuals_root: ./manuals
```

**Resolution Order:**
1. Command-line arg to `CogTwin(data_dir=...)`
2. Config file `paths.data_dir`
3. Hardcoded fallback `"./data"`

**No Environment Variable Override Available**

---

## 3. MEMORY PIPELINE

### `memory/memory_pipeline.py` - Recursive Memory Loop

**Constructor (Lines 192-207):**
```python
def __init__(
    self,
    embedder: AsyncEmbedder,
    data_dir: Path,
    batch_interval: float = 5.0,
    max_batch_size: int = 10,
):
    self.embedder = embedder
    self.data_dir = data_dir
```

**Directory Creation (Lines 440-441):**
```python
(self.data_dir / "memory_nodes").mkdir(parents=True, exist_ok=True)
(self.data_dir / "vectors").mkdir(parents=True, exist_ok=True)
```

**File Writes (Lines 444-454):**
```python
# Line 444: Nodes file
nodes_file = self.data_dir / "memory_nodes" / f"session_nodes_{timestamp}.json"

# Line 450: Embeddings file
emb_file = self.data_dir / "vectors" / f"session_embeddings_{timestamp}.npy"

# Line 454: Outputs file
outputs_file = self.data_dir / "memory_nodes" / f"session_outputs_{timestamp}.json"
```

**Format:**
- `session_nodes_YYYYMMDD_HHMMSS.json` - Memory nodes
- `session_embeddings_YYYYMMDD_HHMMSS.npy` - NumPy embeddings
- `session_outputs_YYYYMMDD_HHMMSS.json` - Cognitive outputs

**Purpose:**
Persists session-level memories to disk in batches.

---

## 4. DUAL RETRIEVER

### `memory/retrieval.py` - Memory Loading System

**Entry Point (Lines 431-444):**
```python
@classmethod
def load(cls, data_dir: Path, manifest_file: Optional[str] = None) -> "DualRetriever":
    data_dir = Path(data_dir)

    # Check for unified manifest (v1.0.0)
    unified_manifest = data_dir / "manifest.json"
    if unified_manifest.exists():
        return cls._load_unified(data_dir)

    # Fall back to legacy
    manifest_path = data_dir / manifest_file
    manifests = list(data_dir.glob("manifest_*.json"))
    if not manifests:
        raise FileNotFoundError(f"No manifest found in {data_dir}")

    return cls._load_legacy(data_dir, manifest_path)
```

---

#### 4.1 Unified Load Path (NEW - v1.0.0)

**Method: `_load_unified()` (Lines 464-559)**

**Reads:**
```python
# Line 466: Manifest
manifest_path = data_dir / "manifest.json"

# Line 473: Process memory nodes
nodes_file = data_dir / "corpus" / "nodes.json"

# Line 480: Episodic memories
episodes_file = data_dir / "corpus" / "episodes.json"

# Line 487: Node embeddings
node_emb_file = data_dir / "vectors" / "nodes.npy"

# Line 491: Episode embeddings
episode_emb_file = data_dir / "vectors" / "episodes.npy"

# Line 496: Cluster assignments
clusters_file = data_dir / "indexes" / "clusters.json"

# Line 509: FAISS index (optional)
faiss_file = data_dir / "indexes" / "faiss.index"

# Line 519: Embedder cache
embedder = AsyncEmbedder(cache_dir=data_dir / "embedding_cache")

# Line 523: Cluster schema (optional)
schema_file = data_dir / "indexes" / "cluster_schema.json"
if schema_file.exists():
    cluster_schema = ClusterSchemaEngine(data_dir)
```

**File Dependencies:**
- ✅ **REQUIRED:** `corpus/nodes.json`, `corpus/episodes.json`, `vectors/nodes.npy`, `vectors/episodes.npy`, `indexes/clusters.json`
- ⚠️ **OPTIONAL:** `indexes/faiss.index`, `indexes/cluster_schema.json`

---

#### 4.2 Legacy Load Path (OLD - Session-based)

**Method: `_load_legacy()` (Lines 561-650)**

**Reads:**
```python
# Line 567: Nodes (from manifest)
nodes_file = data_dir / "memory_nodes" / manifest["nodes_file"]

# Line 573: Episodes (from manifest)
episodes_file = data_dir / "episodic_memories" / manifest["episodes_file"]

# Line 579: Node embeddings (from manifest)
node_emb_file = data_dir / "vectors" / manifest["node_embeddings_file"]

# Line 582: Episode embeddings (from manifest)
episode_emb_file = data_dir / "vectors" / manifest["episode_embeddings_file"]

# Line 586: Clusters (from manifest)
clusters_file = data_dir / "indexes" / manifest["clusters_file"]

# Line 600: FAISS index (from manifest, optional)
if "faiss_index_file" in manifest:
    faiss_file = data_dir / "indexes" / manifest["faiss_index_file"]

# Line 609: Embedder cache
embedder = AsyncEmbedder(cache_dir=data_dir / "embedding_cache")

# Line 613: Cluster schema (optional)
schema_file = data_dir / "indexes" / "cluster_schema.json"
```

**File Dependencies:**
- ✅ **REQUIRED:** `manifest_*.json`, timestamped node/episode files
- Format: `nodes_YYYYMMDD_HHMMSS.json`, `episodes_YYYYMMDD_HHMMSS.json`, etc.

---

#### 4.3 CLI Test Mode (Lines 931-938)

```python
# Line 931: Parse CLI arg
data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data")

# Line 937-938: Load and verify
retriever = DualRetriever.load(data_dir)
print(f"Loaded from {data_dir}")
```

---

## 5. CHAT MEMORY STORE

### `memory/chat_memory.py` - Conversation History

**Constructor (Lines 102-105):**
```python
def __init__(self, data_dir: Path):
    self.data_dir = Path(data_dir)
    self.exchanges_dir = self.data_dir / "chat_exchanges"
    self.exchanges_dir.mkdir(parents=True, exist_ok=True)
```

**Load Existing (Lines 113-127):**
```python
def _load_exchanges(self):
    """Load existing exchanges from disk."""
    for exchange_file in self.exchanges_dir.glob("exchange_*.json"):
        try:
            with open(exchange_file) as f:
                data = json.load(f)
                exchange = ChatExchange.from_dict(data)
                self.exchanges.append(exchange)
                self.exchange_map[exchange.id] = exchange
        except Exception as e:
            logger.warning(f"Failed to load exchange {exchange_file}: {e}")
```

**Write New Exchange (Lines 150-175):**
```python
# Generate ID
exchange_id = f"{timestamp_unix}_{query_hash[:8]}"

# Create file
exchange_file = self.exchanges_dir / f"exchange_{exchange_id}.json"

# Write JSON
with open(exchange_file, "w") as f:
    json.dump(exchange.to_dict(), f, indent=2)
```

**File Format:**
- `chat_exchanges/exchange_{id}.json`
- ID = `{unix_timestamp}_{hash(query)[:8]}`
- Example: `exchange_1701234567_a8f3c29d.json`

---

## 6. COGNITIVE TRACER

### `memory/reasoning_trace.py` - Reasoning Step Logger

**Constructor (Lines 199-201):**
```python
def __init__(self, data_dir: Path, memory_pipeline=None):
    self.data_dir = Path(data_dir)
    self.traces_dir = self.data_dir / "reasoning_traces"
```

**Write Trace (in `begin_trace()` and `finalize_trace()` methods):**
```python
# Creates directory if needed
self.traces_dir.mkdir(parents=True, exist_ok=True)

# Writes to
trace_file = self.traces_dir / f"trace_{trace_id}.json"
```

**File Format:**
- `reasoning_traces/trace_{id}.json`
- ID generated by tracer
- Contains step-by-step reasoning log

---

## 7. DEDUP SYSTEM

### `memory/dedup.py` - Duplicate Prevention

**File Location Constant (Line 36):**
```python
DEDUP_INDEX_FILE = "dedup_index.json"
```

**Load Function (Lines 39-56):**
```python
def load_dedup_index(data_dir: Path) -> Set[str]:
    index_file = Path(data_dir) / DEDUP_INDEX_FILE  # Line 45

    if index_file.exists():
        with open(index_file) as f:
            data = json.load(f)
            return set(data.get("ingested_ids", []))

    return set()
```
- **Expects:** `{data_dir}/dedup_index.json` (ROOT level, not in corpus/)

**Save Function (Lines 59-69):**
```python
def save_dedup_index(data_dir: Path, index: Set[str]):
    index_file = Path(data_dir) / DEDUP_INDEX_FILE  # Line 61

    with open(index_file, "w") as f:
        json.dump({"ingested_ids": sorted(list(index))}, f, indent=2)
```

**Build from Existing (Lines 189-252):**
```python
def build_dedup_index_from_existing(data_dir: Path) -> Set[str]:
    index: Set[str] = set()
    data_dir = Path(data_dir)

    # Scan memory nodes
    nodes_dir = data_dir / "memory_nodes"  # Line 206

    # Scan episodic memories
    episodes_dir = data_dir / "episodic_memories"  # Line 224

    # Scan reasoning traces
    traces_dir = data_dir / "reasoning_traces"  # Line 238
```

**Usage in Context Manager (Lines 118-147):**
```python
class DedupBatch:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)

    def __enter__(self):
        self.index = load_dedup_index(self.data_dir)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.dirty:
            save_dedup_index(self.data_dir, self.index)
```

**⚠️ LOCATION ISSUE:**
Current system has `corpus/dedup_index.json` (empty) but dedup.py expects `{data_dir}/dedup_index.json`.

---

## 8. CLUSTER ENGINES

### 8.1 `memory/cluster_schema.py` - Cluster Semantic Profiles

**Constructor (Lines 105-135):**
```python
def __init__(self, data_dir: Path):
    self.data_dir = Path(data_dir)  # Line 112

    # Schema file location
    self.schema_file = self.data_dir / "indexes" / "cluster_schema.json"  # Line 125

    # Load manifest
    manifest_path = self.data_dir / manifest_file  # Line 131
    # Or: manifests = list(self.data_dir.glob("manifest_*.json"))  # Line 133
```

**Read Paths (Lines 144-157):**
```python
# Line 144: Memory nodes
nodes_file = self.data_dir / "memory_nodes" / manifest["nodes_file"]

# Line 149: Node embeddings
emb_file = self.data_dir / "vectors" / manifest["node_embeddings_file"]

# Line 157: Clusters
clusters_file = self.data_dir / "indexes" / manifest["clusters_file"]
```

**Write Path:**
```python
self.schema_file = self.data_dir / "indexes" / "cluster_schema.json"
```

**CLI Usage (Lines 497-502):**
```python
data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data")
engine = ClusterSchemaEngine(data_dir)
```

---

### 8.2 `memory/streaming_cluster.py` - Real-time Clustering

**Constructor (Lines 74-98):**
```python
def __init__(
    self,
    data_dir: Path,
    ...
):
    self.data_dir = Path(data_dir)  # Line 86

    # Model location
    default_path = self.data_dir / "indexes" / "hdbscan_model.joblib"  # Line 98
```

**Read Vectors (Line 152):**
```python
vectors_dir = self.data_dir / "vectors"
# Loads all .npy files
```

**Write Clusters (Line 363):**
```python
session_file = self.data_dir / "indexes" / f"session_clusters_{timestamp}.json"
```

**CLI Usage (Lines 386-391):**
```python
data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data")
engine = StreamingClusterEngine(data_dir)
```

---

## 9. MEMORY BACKEND

### `memory/memory_backend.py` - File Storage Backend

**Constructor (Lines 181-198):**
```python
def __init__(self, data_dir: Path):
    self.data_dir = Path(data_dir)  # Line 188

    # Unified file locations
    self.nodes_file = self.data_dir / "corpus" / "nodes.json"  # Line 189
    self.embeddings_file = self.data_dir / "vectors" / "nodes.npy"  # Line 190
    self.clusters_file = self.data_dir / "indexes" / "clusters.json"  # Line 191

    logger.info(f"FileBackend initialized with data_dir={data_dir}")
```

**Factory Method (Lines 450-477):**
```python
@classmethod
def create_from_config(cls, config: Dict) -> "FileBackend":
    paths = config.get("paths", {})
    data_dir = Path(paths.get("data_dir", "./data"))  # Line 468

    # Make absolute if relative
    if not data_dir.is_absolute():  # Line 471
        project_root = Path(__file__).parent.parent
        data_dir = project_root / data_dir  # Line 474

    logger.info(f"Initializing FileBackend with data_dir={data_dir}")
    return FileBackend(data_dir.resolve())
```

**Writes To:**
- `corpus/nodes.json` - All memory nodes
- `corpus/episodes.json` - All episodic memories
- `vectors/nodes.npy` - Node embeddings
- `indexes/clusters.json` - Cluster assignments

---

## 10. INGEST PIPELINE

### `memory/ingest/pipeline.py` - Batch Import System

**Function (Lines 750-774):**
```python
def ingest_reasoning_traces(traces_dir: Path, data_dir: Path, dedup_batch) -> dict:
    """
    Args:
        traces_dir: Path to reasoning traces
        data_dir: Path to main data directory  # Line 760
    """
    data_dir = Path(data_dir)  # Line 774
```

**Write Episodic Memories (Line 842):**
```python
output_file = data_dir / "episodic_memories" / f"trace_episodes_{int(time.time())}.json"
```

**CLI Usage (Lines 878-893):**
```python
# Parse CLI args
data_dir = None
for arg in sys.argv[1:]:
    if not arg.startswith("--"):
        data_dir = Path(arg)  # Line 881

if not data_dir:
    print("Usage: python ingest.py <data_dir> --traces")
    sys.exit(1)

traces_dir = data_dir / "reasoning_traces"  # Line 889

with DedupBatch(data_dir) as dedup:  # Line 892
    stats = ingest_reasoning_traces(traces_dir, data_dir, dedup)
```

---

## 11. READ-ONLY UTILITIES

### `memory/read_traces.py` - Trace/Exchange Reader

**Functions use data_dir parameter:**

```python
# Line 20
def load_exchanges(data_dir: Path, limit: int = 10) -> List[Dict]:
    exchanges_dir = data_dir / "chat_exchanges"  # Line 22

# Line 41
def load_traces(data_dir: Path, limit: int = 10) -> List[Dict]:
    traces_dir = data_dir / "reasoning_traces"  # Line 43

# Line 149
def show_full(data_dir: Path, item_id: str):
    ex_file = data_dir / "chat_exchanges" / f"exchange_{item_id}.json"  # Line 152
    tr_file = data_dir / "reasoning_traces" / f"trace_{item_id}.json"  # Line 163

# Line 201: CLI
data_dir = Path(args.data_dir)
```

---

## 12. QUICK REFERENCE: ALL data_dir USAGE

### Files that WRITE to data_dir:
1. `memory/memory_pipeline.py` → `memory_nodes/`, `vectors/`
2. `memory/chat_memory.py` → `chat_exchanges/`
3. `memory/reasoning_trace.py` → `reasoning_traces/`
4. `memory/dedup.py` → `dedup_index.json`
5. `memory/streaming_cluster.py` → `indexes/session_clusters_*.json`
6. `memory/cluster_schema.py` → `indexes/cluster_schema.json`
7. `memory/memory_backend.py` → `corpus/`, `vectors/`, `indexes/`
8. `memory/ingest/pipeline.py` → `episodic_memories/`

### Files that READ from data_dir:
1. `memory/retrieval.py` → Everything (entry point for loading)
2. `memory/cluster_schema.py` → `memory_nodes/`, `vectors/`, `indexes/`
3. `memory/streaming_cluster.py` → `vectors/`, `indexes/`
4. `memory/dedup.py` → `memory_nodes/`, `episodic_memories/`, `reasoning_traces/`
5. `memory/read_traces.py` → `chat_exchanges/`, `reasoning_traces/`

---

## 13. MIGRATION CHECKLIST

When moving data_dir, update:
- [ ] `config.yaml:paths.data_dir`
- [ ] CLI arguments to scripts
- [ ] Verify all paths resolve correctly (relative → absolute conversion)
- [ ] Test: `DualRetriever.load(new_data_dir)` succeeds
- [ ] Test: `ChatMemoryStore(new_data_dir)` loads exchanges
- [ ] Test: Dedup index is found at `{new_data_dir}/dedup_index.json`

---

**END OF WIRE-IN POINTS DOCUMENTATION**
