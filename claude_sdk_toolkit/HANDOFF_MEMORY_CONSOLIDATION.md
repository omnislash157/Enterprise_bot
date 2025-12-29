# HANDOFF: Memory Architecture Consolidation

**Date:** 2024-12-21  
**Mode:** Design → Execute  
**Parallel Agents:** Yes (Recon + Restructure)

---

## Mission Overview

Two parallel workstreams:

1. **RECON AGENT** - Deep discovery of cross-module imports to audit `protocols.py` completeness
2. **RESTRUCTURE AGENT** - Move `ingestion/` into `memory/`, relocate `embedder.py`

**CRITICAL CONSTRAINT:** Only alter files explicitly listed in the Restructure scope. All other work is read-only reconnaissance. Findings go to `docs/`.

---

## AGENT 1: Protocol Recon (Read-Only)

### Objective
Discover every cross-module import in the codebase. Identify what SHOULD be in `protocols.py` but isn't.

### Instructions

Use all available tools to scan the codebase. Find:

1. **Cross-boundary imports** - Any file importing from a different top-level folder
   - `core/` importing from `memory/`, `auth/`, `ingestion/`
   - `memory/` importing from `core/`, `auth/`
   - `auth/` importing from `core/`, `memory/`
   - `claude_sdk/` importing from anywhere
   - `frontend/` API contracts (what backend routes does it call?)

2. **Current protocols.py exports** - Read `core/protocols.py`, list all 16 exports in `__all__`

3. **Gap analysis** - What's imported cross-module but NOT exported from protocols?

4. **Circular dependency risks** - Any A→B→A import chains?

### Output

Create `docs/PROTOCOL_RECON.md` with:

```markdown
# Protocol Recon Report

## Current Exports (protocols.py)
- list each export and its source module

## Cross-Module Import Map
### core/ imports from:
- file: import statement

### memory/ imports from:
- file: import statement

### auth/ imports from:
- file: import statement

## Missing from Protocols
- ImportName (used in X, Y, Z files) - RECOMMEND ADD
- ImportName (used only in one place) - SKIP

## Circular Dependency Risks
- any chains found

## Recommendations
- prioritized list of what to add to protocols.py
```

Leave any detailed sub-reports in `docs/recon/` if needed.

**DO NOT MODIFY ANY FILES. READ ONLY.**

---

## AGENT 2: Restructure (Write)

### Objective
Move `ingestion/` to be a subpackage of `memory/`. Move `embedder.py` to `memory/` root.

### Files You MAY Modify

```
# CREATE these new files:
memory/__init__.py
memory/ingest/__init__.py

# MOVE these files (delete old, create new):
ingestion/embedder.py         → memory/embedder.py
ingestion/ingest.py           → memory/ingest/pipeline.py
ingestion/chat_parser_agnostic.py → memory/ingest/chat_parser.py
ingestion/doc_loader.py       → memory/ingest/doc_loader.py
ingestion/docx_to_json_chunks.py  → memory/ingest/docx_to_json_chunks.py
ingestion/batch_convert_warehouse_docx.py → memory/ingest/batch_convert_warehouse.py
ingestion/ingest_to_postgres.py   → memory/ingest/ingest_to_postgres.py
ingestion/json_chunk_loader.py    → memory/ingest/json_chunk_loader.py
ingestion/__init__.py         → DELETE (or move if has content)

# UPDATE imports in these files ONLY:
memory/ingest/pipeline.py     (fix internal imports)
memory/ingest/chat_parser.py  (fix internal imports)
memory/retrieval.py           (import from .embedder)
core/protocols.py             (add AsyncEmbedder, create_embedder)
docs/FILE_TREE.md             (update structure)
```

### Phase 1: Create Structure

```
memory/
├── __init__.py
├── embedder.py              ← from ingestion/
├── ingest/
│   ├── __init__.py
│   ├── pipeline.py          ← from ingestion/ingest.py
│   ├── chat_parser.py       ← from ingestion/chat_parser_agnostic.py
│   ├── doc_loader.py
│   ├── docx_to_json_chunks.py
│   ├── batch_convert_warehouse.py
│   ├── ingest_to_postgres.py
│   └── json_chunk_loader.py
```

### Phase 2: __init__.py Content

**memory/__init__.py:**
```python
"""
Memory subsystem - retrieval, embeddings, search, and ingestion.
"""
from .embedder import AsyncEmbedder, create_embedder, embed_episodes, embed_memory_nodes
from .retrieval import DualRetriever, EpisodicMemoryRetriever
```

**memory/ingest/__init__.py:**
```python
"""
Ingestion pipeline - chat parsing, document loading, batch processing.
"""
from .pipeline import IngestPipeline
from .chat_parser import ChatParserFactory, AnthropicParser
```

### Phase 3: Fix Imports

In moved files, change:
- `from embedder import` → `from memory.embedder import` OR `from ..embedder import`
- `from retrieval import` → `from memory.retrieval import` OR `from ..retrieval import`
- `from schemas import` → `from core.schemas import`
- `from config_loader import` → `from core.config_loader import`

Use relative imports within memory/ package where possible.

### Phase 4: Update protocols.py

Add to `core/protocols.py`:

```python
# =============================================================================
# EMBEDDINGS
# =============================================================================
from memory.embedder import (
    AsyncEmbedder,
    create_embedder,
)
```

Add to `__all__`:
```python
    # Embeddings
    "AsyncEmbedder",
    "create_embedder",
```

### Phase 5: Update FILE_TREE.md

Replace the `ingestion/` section with new `memory/ingest/` structure. Update the `memory/` section to show `embedder.py` at root.

### Phase 6: Validate

Run these checks:
```bash
python -m py_compile memory/*.py memory/ingest/*.py core/*.py
python -c "from core.protocols import cfg, AsyncEmbedder, CogTwin, DualRetriever"
python -c "from memory.ingest.pipeline import IngestPipeline"
python -c "from memory.embedder import AsyncEmbedder"
python -c "from memory import AsyncEmbedder, DualRetriever"
```

If any fail, fix the import errors before proceeding.

### Output

Create `docs/RESTRUCTURE_COMPLETE.md` confirming:
- Files moved
- Imports fixed
- Validation passed
- Any issues encountered

---

## Execution Order

1. **Start both agents in parallel**
2. Recon agent completes first (read-only, fast)
3. Restructure agent completes file moves
4. After restructure validates, review `docs/PROTOCOL_RECON.md`
5. Human decides which additional exports to add to protocols.py

---

## DO NOT TOUCH

- `core/cog_twin.py` - no changes
- `core/venom_voice.py` - no changes  
- `auth/` - no changes
- `frontend/` - no changes
- `db/` - no changes
- Any file not explicitly listed above

---

## Success Criteria

- [ ] `ingestion/` folder is empty or deleted
- [ ] `memory/ingest/` contains all moved files
- [ ] `memory/embedder.py` exists at memory root
- [ ] All import statements resolve
- [ ] `python -c "from core.protocols import AsyncEmbedder"` works
- [ ] `docs/PROTOCOL_RECON.md` exists with full audit
- [ ] `docs/FILE_TREE.md` reflects new structure
