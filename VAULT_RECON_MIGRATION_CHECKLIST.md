# VAULT MIGRATION CHECKLIST
## Step-by-Step Guide to Move Data Directory Without Data Loss

**Generated:** 2024-12-24
**Source System:** enterprise_bot (working)
**Target System:** (to be determined)

---

## EXECUTIVE SUMMARY

**Current Vault Location:** `C:\Users\mthar\projects\enterprise_bot\data`
**Current Status:** ✅ ACTIVE with live data
**Data Integrity:** ✅ Dedup system ready (corpus/dedup_index.json exists)
**Migration Risk:** 🟡 MEDIUM - Multiple format versions, dedup location mismatch

**Key Findings:**
- System uses **unified format (v1.0.0)** - single manifest.json
- Dedup index location inconsistency (corpus/ vs root)
- 112 chat exchanges, 156 reasoning traces, 34 memory node sessions
- FAISS index and HDBSCAN model exist (can rebuild if needed)

---

## PRE-MIGRATION CHECKS

### ✅ Step 1: Verify Current System Health

Run these commands to verify data integrity:

```bash
# Navigate to project root
cd C:\Users\mthar\projects\enterprise_bot

# 1. Check data directory exists
ls -la data/

# 2. Verify manifest format
cat data/manifest.json
# Should show: "version": "1.0.0"

# 3. Count core files
find data/corpus -name "*.json" | wc -l      # Should be 3 (nodes, episodes, dedup)
find data/vectors -name "*.npy" | wc -l      # Should be 21
find data/indexes -name "*" -type f | wc -l  # Should be 6

# 4. Check file sizes
du -sh data/corpus/*
du -sh data/vectors/*
du -sh data/indexes/*

# 5. Test load (Python)
python -c "
from memory.retrieval import DualRetriever
r = DualRetriever.load('data')
print(f'✅ Loaded {len(r.process.nodes)} nodes')
print(f'✅ Loaded {len(r.episodic.episodes)} episodes')
"

# 6. Check chat memory
python -c "
from memory.chat_memory import ChatMemoryStore
from pathlib import Path
cm = ChatMemoryStore(Path('data'))
print(f'✅ Loaded {len(cm.exchanges)} exchanges')
"
```

**Expected Results:**
- Manifest version: 1.0.0
- 3 corpus files: nodes.json, episodes.json, dedup_index.json
- 21 vector files (.npy)
- 6 index files
- Load succeeds without errors
- Exchange count: 112

---

### ✅ Step 2: Backup Current System

**CRITICAL:** Create a complete backup before any migration!

```bash
# Create backup directory with timestamp
BACKUP_DIR="data_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Copy entire data directory
cp -r data/ "$BACKUP_DIR/data_original/"

# Create manifest of what was backed up
cd "$BACKUP_DIR"
find data_original -type f > file_manifest.txt
du -sh data_original/* > size_manifest.txt

# Verify backup
echo "Backup created at: $(pwd)"
wc -l file_manifest.txt  # Should show ~300+ files
```

**Backup Verification:**
```bash
# Compare file counts
echo "Original:"
find data -type f | wc -l
echo "Backup:"
find "$BACKUP_DIR/data_original" -type f | wc -l
# Should match!
```

---

### ✅ Step 3: Identify What to Migrate

#### Critical Files (MUST migrate):
```
data/
├── manifest.json                    ← System bootstrap file
├── corpus/
│   ├── nodes.json                   ← All process memories
│   └── episodes.json                ← All episodic memories
├── vectors/
│   ├── nodes.npy                    ← Node embeddings
│   └── episodes.npy                 ← Episode embeddings
└── indexes/
    └── clusters.json                ← Cluster assignments
```

**Size:** ~50-100 KB (corpus), ~10-50 MB (vectors)

#### Important Files (Should migrate):
```
data/
├── chat_exchanges/                  ← 112 files - Conversation history
├── reasoning_traces/                ← 156 files - Training data
├── indexes/
│   ├── faiss.index                  ← Fast search (can rebuild)
│   ├── cluster_schema.json          ← Semantic profiles (can rebuild)
│   ├── hdbscan_model.joblib         ← Clustering model (can rebuild)
│   └── hdbscan_clusters.json        ← Cluster metadata
└── embedding_cache/                 ← API response cache
```

**Size:** ~10-20 MB (exchanges + traces), ~1-10 MB (indexes)

#### Optional Files (Can skip):
```
data/
├── archive/                         ← Old data (Nov 28 - Dec 1)
├── memory_nodes/                    ← Legacy format (migrated to corpus/)
├── chunks.jsonl                     ← RAG documents (68 MB - not memory)
└── debug_pipeline_output.json       ← Debug artifact
```

---

## MIGRATION SCENARIOS

### Scenario A: Move to New Directory (Same Machine)

**Use Case:** Reorganizing file structure on same computer

```bash
# 1. Define new location
NEW_DATA_DIR="/path/to/new/location/data"

# 2. Create new directory structure
mkdir -p "$NEW_DATA_DIR"

# 3. Copy critical files
cp data/manifest.json "$NEW_DATA_DIR/"
cp -r data/corpus "$NEW_DATA_DIR/"
cp -r data/vectors "$NEW_DATA_DIR/"
cp -r data/indexes "$NEW_DATA_DIR/"

# 4. Copy important files
cp -r data/chat_exchanges "$NEW_DATA_DIR/"
cp -r data/reasoning_traces "$NEW_DATA_DIR/"
cp -r data/embedding_cache "$NEW_DATA_DIR/"

# 5. Update config.yaml
sed -i 's|data_dir: ./data|data_dir: '"$NEW_DATA_DIR"'|' core/config.yaml

# 6. Verify
python -c "
from memory.retrieval import DualRetriever
from pathlib import Path
r = DualRetriever.load(Path('$NEW_DATA_DIR'))
print(f'✅ SUCCESS: Loaded {len(r.process.nodes)} nodes from new location')
"
```

---

### Scenario B: Move to Different Machine

**Use Case:** Deploying to production server, sharing with team

```bash
# ON SOURCE MACHINE:

# 1. Create migration package
MIGRATION_PKG="enterprise_bot_data_$(date +%Y%m%d).tar.gz"

tar -czf "$MIGRATION_PKG" \
    data/manifest.json \
    data/corpus/ \
    data/vectors/ \
    data/indexes/ \
    data/chat_exchanges/ \
    data/reasoning_traces/ \
    data/embedding_cache/

# 2. Verify archive
tar -tzf "$MIGRATION_PKG" | head -20
du -sh "$MIGRATION_PKG"

# 3. Generate checksum
sha256sum "$MIGRATION_PKG" > "$MIGRATION_PKG.sha256"

# 4. Transfer (choose method)
# Option A: SCP
scp "$MIGRATION_PKG" user@target-server:/path/to/

# Option B: Cloud storage (S3, B2, etc.)
# aws s3 cp "$MIGRATION_PKG" s3://bucket/path/

# Option C: Physical media
# cp "$MIGRATION_PKG" /media/usb-drive/


# ON TARGET MACHINE:

# 1. Verify checksum
sha256sum -c "$MIGRATION_PKG.sha256"

# 2. Extract
mkdir -p /path/to/enterprise_bot
cd /path/to/enterprise_bot
tar -xzf "$MIGRATION_PKG"

# 3. Update config
vi core/config.yaml
# Set: data_dir: /path/to/enterprise_bot/data

# 4. Verify
python -c "
from memory.retrieval import DualRetriever
r = DualRetriever.load('data')
print(f'✅ Migration successful: {len(r.process.nodes)} nodes')
"
```

---

### Scenario C: Cloud Storage (B2) Integration

**Use Case:** Moving to cloud-backed storage (Phase 5 plan)

⚠️ **WARNING:** This requires code changes to support remote storage backend.

**Current State:**
- System uses `FileBackend` (local disk only)
- Config: `memory.backend: file`

**To Use B2:**
1. Implement `B2Backend` class (not yet built)
2. Update `memory_backend.py` to support B2 URLs
3. Upload data files to B2 bucket
4. Update config: `memory.backend: b2`

**Not covered in this checklist** - requires development work.

---

## POST-MIGRATION VERIFICATION

### ✅ Step 4: Verify Data Integrity

Run these tests after migration:

```python
# test_migration.py
from pathlib import Path
from memory.retrieval import DualRetriever
from memory.chat_memory import ChatMemoryStore
from memory.dedup import load_dedup_index
import json

data_dir = Path("./data")  # Or new location

print("=" * 60)
print("MIGRATION VERIFICATION TESTS")
print("=" * 60)

# Test 1: Manifest exists and is valid
print("\n[1] Checking manifest...")
manifest_file = data_dir / "manifest.json"
assert manifest_file.exists(), "manifest.json missing!"
with open(manifest_file) as f:
    manifest = json.load(f)
    assert manifest["version"] == "1.0.0", "Wrong manifest version!"
print("✅ Manifest OK")

# Test 2: Corpus files exist
print("\n[2] Checking corpus files...")
nodes_file = data_dir / "corpus" / "nodes.json"
episodes_file = data_dir / "corpus" / "episodes.json"
assert nodes_file.exists(), "corpus/nodes.json missing!"
assert episodes_file.exists(), "corpus/episodes.json missing!"
print(f"✅ Corpus OK - nodes: {nodes_file.stat().st_size / 1024:.1f} KB")

# Test 3: Vector files exist
print("\n[3] Checking vector files...")
node_emb = data_dir / "vectors" / "nodes.npy"
episode_emb = data_dir / "vectors" / "episodes.npy"
assert node_emb.exists(), "vectors/nodes.npy missing!"
assert episode_emb.exists(), "vectors/episodes.npy missing!"
print(f"✅ Vectors OK - nodes: {node_emb.stat().st_size / 1024 / 1024:.1f} MB")

# Test 4: Load retriever
print("\n[4] Loading retriever...")
retriever = DualRetriever.load(data_dir)
node_count = len(retriever.process.nodes)
episode_count = len(retriever.episodic.episodes)
print(f"✅ Retriever loaded - {node_count} nodes, {episode_count} episodes")

# Test 5: Load chat memory
print("\n[5] Loading chat memory...")
chat_memory = ChatMemoryStore(data_dir)
exchange_count = len(chat_memory.exchanges)
print(f"✅ Chat memory loaded - {exchange_count} exchanges")

# Test 6: Check dedup
print("\n[6] Checking dedup index...")
dedup_index = load_dedup_index(data_dir)
print(f"✅ Dedup index loaded - {len(dedup_index)} entries")

# Test 7: Test retrieval
print("\n[7] Testing retrieval...")
import asyncio
results = asyncio.run(retriever.retrieve("test query", top_k=5))
print(f"✅ Retrieval works - returned {len(results.process_results)} results")

print("\n" + "=" * 60)
print("ALL TESTS PASSED ✅")
print("=" * 60)
```

Run:
```bash
python test_migration.py
```

---

### ✅ Step 5: Test Core Functionality

```bash
# Start CogTwin in test mode
python -m core.cog_twin

# Should see:
# ✅ Loading memory system...
# ✅ Loaded N memory nodes
# ✅ MetacognitiveMirror initialized
# ✅ Memory pipeline started

# Test query
# > How does the memory system work?

# Verify response uses memories (check logs)
```

---

## ROLLBACK PROCEDURE

If migration fails:

```bash
# 1. Stop any running processes
pkill -f cog_twin

# 2. Restore from backup
rm -rf data/  # Remove broken migration
cp -r "$BACKUP_DIR/data_original/" data/

# 3. Restore config
git checkout core/config.yaml  # If using git
# Or manually revert data_dir setting

# 4. Verify rollback
python -c "
from memory.retrieval import DualRetriever
r = DualRetriever.load('data')
print(f'✅ Rollback successful: {len(r.process.nodes)} nodes')
"
```

---

## KNOWN ISSUES & FIXES

### Issue 1: Dedup Index Location Mismatch

**Problem:** Dedup index exists in two places:
- `data/corpus/dedup_index.json` (empty, wrong location)
- `data/dedup_index.json` (expected location - doesn't exist yet)

**Fix:**
```bash
# Option A: Move existing to correct location
mv data/corpus/dedup_index.json data/dedup_index.json

# Option B: Rebuild from scratch
python -c "
from memory.dedup import build_dedup_index_from_existing, save_dedup_index
from pathlib import Path
index = build_dedup_index_from_existing(Path('data'))
save_dedup_index(Path('data'), index)
print(f'✅ Rebuilt dedup index: {len(index)} entries')
"
```

---

### Issue 2: Legacy vs Unified Format Confusion

**Problem:** System has both old and new format files:
- `data/memory_nodes/` (legacy)
- `data/corpus/` (unified)

**Current State:** System is using **unified format** (manifest.json exists)

**Migration Strategy:**
- ✅ Keep `corpus/` directory (active)
- ⚠️ Archive or delete `memory_nodes/` (legacy, not loaded)
- ✅ Keep session files if you want historical record

**Action:**
```bash
# Option A: Archive legacy files
mkdir -p data/archive/legacy_nodes
mv data/memory_nodes/* data/archive/legacy_nodes/

# Option B: Delete if not needed
# rm -rf data/memory_nodes/  # CAREFUL!
```

---

### Issue 3: Relative vs Absolute Paths

**Problem:** Config uses relative path `./data` which breaks if working directory changes.

**Fix:**
```yaml
# In config.yaml, use absolute path
paths:
  data_dir: /absolute/path/to/enterprise_bot/data
```

Or use environment variable:
```bash
export ENTERPRISE_BOT_DATA_DIR="/path/to/data"
```

Then update config_loader.py to read from env var.

---

## CONFIGURATION UPDATES

After migration, update these files:

### 1. `core/config.yaml`

```yaml
paths:
  data_dir: /new/path/to/data  # Update this line
  manuals_root: ./manuals
```

### 2. CLI Scripts

If you use these scripts with hardcoded paths, update them:
- `memory/cluster_schema.py` (line 497)
- `memory/streaming_cluster.py` (line 386)
- `memory/retrieval.py` (line 931)
- `memory/ingest/pipeline.py` (line 881)

All support CLI arg: `python script.py /new/data/path`

### 3. Systemd/Service Files (if applicable)

Update working directory in service files:
```ini
[Service]
WorkingDirectory=/path/to/enterprise_bot
Environment="DATA_DIR=/path/to/data"
```

---

## DATA RETENTION POLICY

What to keep, what to delete:

### Keep Forever:
- `corpus/nodes.json`, `corpus/episodes.json` - Core memories
- `vectors/nodes.npy`, `vectors/episodes.npy` - Required for retrieval
- `chat_exchanges/` - Conversation history (training data)
- `reasoning_traces/` - Cognitive logs (training data)

### Can Rebuild:
- `indexes/faiss.index` - Rebuild from vectors
- `indexes/cluster_schema.json` - Rebuild from clusters
- `indexes/hdbscan_model.joblib` - Retrain from vectors

### Can Delete:
- `archive/` - Old data (unless needed for rollback)
- `memory_nodes/` - Legacy format (migrated to corpus/)
- `debug_pipeline_output.json` - Debug artifacts
- `chunks.jsonl` - RAG documents (not memory system)

---

## PERFORMANCE BENCHMARKS

Verify migration didn't degrade performance:

```python
# benchmark.py
import time
import asyncio
from pathlib import Path
from memory.retrieval import DualRetriever

data_dir = Path("./data")

print("Performance Benchmarks")
print("=" * 60)

# Load time
start = time.time()
retriever = DualRetriever.load(data_dir)
load_time = (time.time() - start) * 1000
print(f"Load time: {load_time:.1f}ms")

# Retrieval time (50 nodes)
query = "How does memory work?"
start = time.time()
results = asyncio.run(retriever.retrieve(query, top_k=50))
retrieval_time = (time.time() - start) * 1000
print(f"Retrieval time (top-50): {retrieval_time:.1f}ms")

print("\nTarget performance:")
print("  Load time: < 5000ms")
print("  Retrieval time: < 500ms (should be ~0.3ms with cached embeddings)")
print("=" * 60)
```

Expected results:
- **Load time:** 2-5 seconds (cold start)
- **Retrieval time:** 0.3-10ms (depending on cache state)

---

## SUCCESS CRITERIA

Migration is successful when ALL of these are true:

- [ ] ✅ All verification tests pass (Step 4)
- [ ] ✅ CogTwin starts without errors
- [ ] ✅ Can query and get relevant results
- [ ] ✅ Chat history loads (112 exchanges)
- [ ] ✅ Reasoning traces accessible (156 traces)
- [ ] ✅ Dedup system working (no duplicate ingestion)
- [ ] ✅ Performance within expected range
- [ ] ✅ No "FileNotFoundError" in logs
- [ ] ✅ Backup verified and stored safely

---

## EMERGENCY CONTACTS

If migration fails and you need help:

1. **Check logs:** `tail -f logs/cog_twin.log`
2. **Review this checklist:** Start at rollback procedure
3. **Verify backup exists:** `ls -la $BACKUP_DIR`
4. **Test individual components:** Run verification tests one by one

---

## APPENDIX: File Inventory

Complete list of files in working system (for comparison):

```bash
# Generate inventory
find data -type f | sort > data_inventory.txt

# Expected categories:
# - 112 chat_exchanges/*.json
# - 156 reasoning_traces/*.json
# - 34 memory_nodes/*.json (legacy)
# - 21 vectors/*.npy
# - 6 indexes/* (json, index, joblib)
# - 3 corpus/*.json
# - ~30 archive/* (old data)
# - 1 manifest.json
# - Misc: chunks.jsonl, debug files

# Total: ~330-350 files
```

---

## FINAL CHECKLIST

Before you begin:
- [ ] Read entire migration plan
- [ ] Choose migration scenario (A, B, or C)
- [ ] Create complete backup
- [ ] Verify backup integrity
- [ ] Note current file counts/sizes
- [ ] Ensure sufficient disk space at target
- [ ] Schedule maintenance window (if production)
- [ ] Have rollback plan ready

During migration:
- [ ] Follow steps in order
- [ ] Don't skip verification steps
- [ ] Document any issues encountered
- [ ] Save logs/error messages

After migration:
- [ ] Run all verification tests
- [ ] Test core functionality
- [ ] Monitor for 24-48 hours
- [ ] Keep backup for at least 1 week
- [ ] Update documentation with new paths

---

**END OF MIGRATION CHECKLIST**

**Last Updated:** 2024-12-24
**Version:** 1.0.0
**Tested On:** enterprise_bot project (cog_twin)
