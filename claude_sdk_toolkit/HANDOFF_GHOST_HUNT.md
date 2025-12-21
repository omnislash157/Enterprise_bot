# HANDOFF: Final Ingestion Cleanup + Protocol Ghost Hunt

**Date:** 2024-12-21  
**Mode:** Execute + Recon  
**Prerequisite:** Memory Architecture Consolidation (completed)

---

## Mission Overview

Two objectives:

1. **CLEANUP:** Move remaining `ingestion/` files to proper locations
2. **GHOST HUNT:** Deep recon of entire codebase for missing protocol exports

We're looking for "enterprise_bot ghosts" - cross-module imports that bypass protocols, circular dependencies, orphaned code.

---

## PHASE 1: Final Ingestion Cleanup

### 1.1 Remaining Files to Move

| File | Current Location | New Location | Rationale |
|------|------------------|--------------|-----------|
| `dedup.py` | `ingestion/dedup.py` | `memory/dedup.py` | Deduplication is memory operation |
| `postgres_backend.py` | `ingestion/postgres_backend.py` | `memory/backends/postgres.py` | Database backend belongs with memory |

### 1.2 Create Backends Subpackage

```bash
mkdir -p memory/backends
```

**CREATE: `memory/backends/__init__.py`**
```python
"""
Memory storage backends.

Supports:
- FileBackend: JSON/pickle file storage (default)
- PostgresBackend: PostgreSQL + pgvector for production
"""
from .postgres import PostgresBackend

__all__ = ["PostgresBackend"]
```

### 1.3 Move Files

```bash
mv ingestion/dedup.py memory/dedup.py
mv ingestion/postgres_backend.py memory/backends/postgres.py
```

### 1.4 Fix Imports

**memory/dedup.py** - Check and fix any imports

**memory/backends/postgres.py** - Fix imports:
- `from schemas import` → `from core.schemas import`
- Any other cross-module imports

**core/cog_twin.py** - Update:
- `from ingestion.dedup import` → `from memory.dedup import`

**memory/memory_backend.py** - Update:
- `from postgres_backend import` → `from memory.backends.postgres import`

### 1.5 Delete Empty ingestion/

After moves complete:
```bash
# Check if empty
ls ingestion/

# If only __init__.py remains, remove the directory
rm -rf ingestion/
```

### 1.6 Update FILE_TREE.md

Remove the `ingestion/` section entirely. Update `memory/` to include:
```
├── memory/
│   ├── ...existing files...
│   ├── dedup.py                       # Memory deduplication
│   │
│   └── backends/                      # Storage backends
│       ├── __init__.py                # Exports: PostgresBackend
│       └── postgres.py                # PostgreSQL + pgvector
```

---

## PHASE 2: Protocol Ghost Hunt

### 2.1 Objective

Scan EVERY Python file in the codebase. Find:

1. **Cross-module imports that bypass protocols** - Any file importing directly from another module instead of from `core.protocols`
2. **Missing protocol exports** - Things used cross-module that SHOULD be in protocols but aren't
3. **Circular dependencies** - A imports B imports A chains
4. **Dead imports** - Imports that reference moved/deleted files
5. **Orphaned code** - Files that nothing imports

### 2.2 Scan Methodology

For each folder, catalog:
- What it exports (used by other modules)
- What it imports (from other modules)
- Any violations of the "import from protocols" rule

**Folders to scan:**
- `core/` (except protocols.py itself)
- `memory/` (all files including ingest/ and backends/)
- `auth/` (all files)
- `claude_sdk/` or `claude_sdk_toolkit/` (if exists)
- `db/` (migration scripts)
- Root level `.py` files (if any)

### 2.3 Output Format

Create `docs/PROTOCOL_GHOST_HUNT.md` with:

```markdown
# Protocol Ghost Hunt Report

## Summary
- Files scanned: X
- Ghost imports found: Y
- Missing protocol exports: Z
- Circular dependencies: N
- Dead imports: M

## Ghost Imports (bypass protocols)

### core/some_file.py
- Line 42: `from memory.something import Thing` 
- Should be: `from core.protocols import Thing` (if Thing should be exported)
- Or: This is internal, no change needed

### memory/other_file.py
...

## Recommended Protocol Additions

| Export | Source | Used By | Priority |
|--------|--------|---------|----------|
| `Thing` | memory/thing.py | core/x.py, core/y.py | HIGH |
| ... | ... | ... | ... |

## Circular Dependencies

### Chain 1
core/a.py → memory/b.py → core/a.py
**Fix:** Move shared dependency to protocols

## Dead Imports
- `core/old_file.py` line 10: `from ingestion.xyz import` (ingestion/ deleted)

## Orphaned Files
- `memory/unused_feature.py` - Nothing imports this

## Recommendations
1. ...
2. ...
```

---

## PHASE 3: Protocol Updates (if needed)

Based on ghost hunt findings, update `core/protocols.py`:

### Candidates from Previous Recon

These were identified as "MEDIUM priority" in the earlier recon:

| Export | Source | Used By | Add? |
|--------|--------|---------|------|
| `MemoryPipeline` | memory/memory_pipeline.py | core/enterprise_twin.py | EVALUATE |
| `SquirrelTool` | memory/squirrel.py | core/cog_twin.py, core/enterprise_twin.py | EVALUATE |
| `ChatMemoryStore` | memory/chat_memory.py | core/cog_twin.py | EVALUATE |
| `PostgresBackend` | memory/backends/postgres.py | memory/memory_backend.py | EVALUATE |

**Decision criteria:**
- If used by 2+ files across module boundaries → ADD
- If used by 1 file → SKIP (keep as internal)
- If only used within same module → SKIP

---

## FILES YOU MAY MODIFY

**Create:**
- `memory/backends/__init__.py`
- `docs/PROTOCOL_GHOST_HUNT.md`

**Move:**
- `ingestion/dedup.py` → `memory/dedup.py`
- `ingestion/postgres_backend.py` → `memory/backends/postgres.py`

**Edit (imports only):**
- `memory/dedup.py`
- `memory/backends/postgres.py`
- `memory/memory_backend.py`
- `core/cog_twin.py`
- `core/protocols.py` (only if ghost hunt finds additions needed)
- `docs/FILE_TREE.md`

**Delete:**
- `ingestion/` directory (after emptied)

---

## DO NOT TOUCH

- `core/venom_voice.py`
- `core/enterprise_twin.py` 
- `core/main.py`
- `core/schemas.py`
- `auth/*`
- `frontend/*`
- `db/*`
- `claude_sdk_toolkit/*` (except for reading)

---

## VALIDATION

After all changes:

```bash
# Syntax check new/moved files
python -m py_compile memory/dedup.py
python -m py_compile memory/backends/__init__.py
python -m py_compile memory/backends/postgres.py
python -m py_compile memory/memory_backend.py
python -m py_compile core/cog_twin.py

# Import chain test
python -c "from memory.backends.postgres import PostgresBackend; print('PostgresBackend OK')"
python -c "from memory.dedup import DedupBatch; print('DedupBatch OK')"
python -c "from core.protocols import *; print('All protocols OK')"

# Verify ingestion/ is gone
ls ingestion/ 2>/dev/null && echo "ERROR: ingestion/ still exists" || echo "OK: ingestion/ removed"
```

---

## SUCCESS CRITERIA

- [ ] `ingestion/` directory no longer exists
- [ ] `memory/dedup.py` exists and imports work
- [ ] `memory/backends/postgres.py` exists and imports work
- [ ] `docs/PROTOCOL_GHOST_HUNT.md` created with full audit
- [ ] All ghost imports documented
- [ ] Recommendations for protocol additions provided
- [ ] `docs/FILE_TREE.md` updated
- [ ] All validation commands pass

---

## OUTPUT REQUIRED

1. **`docs/PROTOCOL_GHOST_HUNT.md`** - Full recon report
2. **Append to `.claude/CHANGELOG.md`** - Summary of this session

---

**END OF HANDOFF**
