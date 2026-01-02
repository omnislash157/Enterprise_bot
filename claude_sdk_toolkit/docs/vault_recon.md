# SDK AGENT HANDOFF: Vault System Deep Recon
## Target: cog_twin project (the one that works)

---

## MISSION

Deep scan the existing cog_twin vault system to enable migration to enterprise_bot project.

**Goal:** Map every hardcoded path, every config reference, every wire-in point so we can:
1. Move the existing vault (with all data intact)
2. Point enterprise_bot at it
3. Have it "just work"

---

## CONTEXT

The user (Hartigan) has a working cog_twin project with:
- Functioning vault with chat exports and embeddings
- Dedup system (can re-import without duplicates)
- ~2 months of conversation data
- HDBSCAN that WORKS (because embeddings exist)

The enterprise_bot project is being refactored to use cloud storage (B2) but for now we need to understand the LOCAL vault structure that's proven to work.

---

## PRIMARY SCAN TARGETS

### 1. VAULT HARDCODED PATHS

Find ALL references to vault paths. Look for:

```python
# Patterns to grep
"./vault"
"vault/"
"data/"
"Process_nodes"
"embeddings"
"episodic"
Path(__file__).parent
data_dir
vault_root
VAULT_
```

**Files likely to contain paths:**
- `config.yaml` or any config file
- `config_loader.py`
- `memory_pipeline.py`
- `retrieval.py`
- `embedder.py`
- `cog_twin.py`
- Any `__init__.py` that sets defaults

**Output needed:**
```
FILE: path/to/file.py
LINE 47: data_dir = Path("./vault")
LINE 123: embeddings_path = data_dir / "embeddings"
...
```

### 2. VAULTCONFIG CLASS

There's a VaultConfig class (possibly in a config or schema file). Find it and document:

```python
class VaultConfig:
    root: str = ?
    source_dir: str = ?
    extraction_dir: str = ?
    embeddings_dir: str = ?
    process_memory_dir: str = ?
    episodic_memory_dir: str = ?
    # ... all fields
```

**We need the EXACT v13 or latest schema.**

### 3. MEMORY PIPELINE WIRE-INS

Trace the memory pipeline initialization:

```
Entry point (main.py or cog_twin.py)
    │
    ▼
Where is MemoryPipeline instantiated?
    │
    ▼
What paths does it receive?
    │
    ▼
Where does it READ from?
    │
    ▼
Where does it WRITE to?
```

**Specific questions:**
- When a new memory is created, where does the .yaml go?
- When embeddings are generated, where do the .npy files go?
- Is there a queue/batch system? Where's its state stored?

### 4. RETRIEVAL SYSTEM PATHS

The DualRetriever (or whatever retrieval class):
- Where does it load Process_nodes from?
- Where does it load embeddings from?
- Where does it load episodic memory from?
- Are there FAISS indexes? Where stored?
- BM25 inverted index location?

### 5. DEDUP SYSTEM

Critical for re-import without duplicates:
- Where is dedup state stored?
- What's the dedup key (hash of what)?
- Can we dump new data and have it skip existing?

### 6. CHAT MEMORY / SQUIRREL

- Where does ChatMemoryStore persist?
- What's the file format (.json, .yaml, SQLite)?
- How does Squirrel find recent conversations?

### 7. ACTUAL VAULT CONTENTS

List the actual files in the working vault:

```bash
find ./vault -type f | head -100
```

Document:
- File counts per directory
- File naming conventions (UUIDs? hashes? timestamps?)
- File formats (.yaml, .json, .npy)

---

## SECONDARY SCAN

### Config Loading Chain

How does config get loaded?
```
Environment variable? → Config file? → Defaults?
```

What's the precedence? Can we override vault path via env var?

### Import Chain

What imports what? We need to know if moving files will break relative imports:

```
cog_twin.py imports from...
    memory_pipeline.py imports from...
        retrieval.py imports from...
```

### Initialization Order

What needs to exist before what?
- Does the vault need to exist before startup?
- Are directories created on-demand?
- Any migrations or setup scripts?

---

## OUTPUT FORMAT

Create a document with:

### 1. PATH MAP
```
VAULT ROOT: ./vault (or whatever)
├── embeddings/           ← Written by: embedder.py:L45
│   └── process/          ← Read by: retrieval.py:L123
├── Process_nodes/        ← Written by: memory_pipeline.py:L89
│                         ← Read by: retrieval.py:L156
├── episodic_memory_nodes/
...
```

### 2. WIRE-IN POINTS
```
FILE                    LINE    WHAT
cog_twin.py            234     MemoryPipeline(data_dir=...)
memory_pipeline.py     45      self.nodes_dir = data_dir / "Process_nodes"
retrieval.py           67      DualRetriever.load(data_dir)
...
```

### 3. CONFIG DEPENDENCIES
```
Config Key              Default Value       Used By
paths.data_dir          ./vault             cog_twin.py, memory_pipeline.py
vault.embeddings_dir    embeddings          retrieval.py
...
```

### 4. MIGRATION CHECKLIST
```
[ ] Copy vault folder to new location
[ ] Update config.yaml path
[ ] Update environment variable (if any)
[ ] Verify: embeddings exist for Process_nodes
[ ] Verify: dedup state intact
[ ] Test: can load without re-indexing
```

---

## COMMANDS TO RUN

```bash
# Find all path references
grep -rn "vault" --include="*.py" .
grep -rn "data_dir" --include="*.py" .
grep -rn "Path(" --include="*.py" .

# Find config files
find . -name "*.yaml" -o -name "*.yml" -o -name "*.toml"

# Find VaultConfig class
grep -rn "class VaultConfig" --include="*.py" .
grep -rn "VaultConfig" --include="*.py" .

# List vault contents
find ./vault -type d
find ./vault -type f -name "*.yaml" | wc -l
find ./vault -type f -name "*.npy" | wc -l

# Find memory pipeline
grep -rn "MemoryPipeline" --include="*.py" .
grep -rn "memory_pipeline" --include="*.py" .
```

---

## SUCCESS CRITERIA

Recon is complete when we can answer:

1. **"Where is the vault?"** → Exact path, how it's configured
2. **"What's in it?"** → Full directory tree with file counts
3. **"What reads from it?"** → Every file:line that loads vault data
4. **"What writes to it?"** → Every file:line that saves to vault
5. **"How do we move it?"** → Step-by-step migration without data loss
6. **"Will dedup work?"** → Yes/no, and where dedup state lives

---

## PRIORITY

**HIGH:** Paths, VaultConfig, Memory Pipeline wire-ins
**MEDIUM:** Retrieval paths, dedup system
**LOW:** Import chains, secondary configs

Start with `grep -rn "vault"` and follow the threads.

---

**END OF HANDOFF**

Target project: cog_twin (the working one)
Goal: Full vault reconstruction for migration
Output: PATH_MAP.md + WIRE_IN_POINTS.md + MIGRATION_CHECKLIST.md