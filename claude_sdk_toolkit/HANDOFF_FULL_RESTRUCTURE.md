# HANDOFF: Memory Architecture Consolidation + Protocol Completion

**Date:** 2024-12-21  
**Mode:** Execute  
**Prerequisite:** None - this document is self-contained

---

## Mission Overview

This handoff consolidates two tasks:
1. **Restructure:** Move `ingestion/` into `memory/`, relocate `embedder.py`
2. **Protocol Completion:** Add missing exports to `protocols.py` based on recon findings

**CRITICAL:** Only modify files explicitly listed. Log all changes. Create diffs.

---

## PHASE 1: File Structure Changes

### 1.1 Create New Directories

```bash
mkdir -p memory/ingest
```

### 1.2 Move Files

Execute these moves in order:

| Source | Destination |
|--------|-------------|
| `ingestion/embedder.py` | `memory/embedder.py` |
| `ingestion/ingest.py` | `memory/ingest/pipeline.py` |
| `ingestion/chat_parser_agnostic.py` | `memory/ingest/chat_parser.py` |
| `ingestion/doc_loader.py` | `memory/ingest/doc_loader.py` |
| `ingestion/docx_to_json_chunks.py` | `memory/ingest/docx_to_json_chunks.py` |
| `ingestion/batch_convert_warehouse_docx.py` | `memory/ingest/batch_convert_warehouse.py` |
| `ingestion/ingest_to_postgres.py` | `memory/ingest/ingest_to_postgres.py` |
| `ingestion/json_chunk_loader.py` | `memory/ingest/json_chunk_loader.py` |

### 1.3 Create __init__.py Files

**CREATE: `memory/__init__.py`**
```python
"""
Memory subsystem - retrieval, embeddings, search, and ingestion.

This module provides:
- AsyncEmbedder: Multi-provider embedding pipeline (BGE-M3)
- DualRetriever: Combined process + episodic memory retrieval
- Ingest subpackage: Chat parsing and batch processing
"""
from .embedder import AsyncEmbedder, create_embedder, embed_episodes, embed_memory_nodes
from .retrieval import DualRetriever, EpisodicMemoryRetriever
```

**CREATE: `memory/ingest/__init__.py`**
```python
"""
Ingestion pipeline - chat parsing, document loading, batch processing.

Supports multiple chat export formats:
- Anthropic (Claude)
- OpenAI (ChatGPT)
- Grok
- Gemini
"""
from .pipeline import IngestPipeline
from .chat_parser import ChatParserFactory, AnthropicParser
```

### 1.4 Delete Empty Directory

After all files moved, delete:
```bash
rmdir ingestion/  # Only if empty
```

---

## PHASE 2: Fix Imports in Moved Files

### 2.1 memory/embedder.py

No changes needed - this file has no internal imports.

### 2.2 memory/ingest/pipeline.py (was ingest.py)

Find and replace these imports:

| Old Import | New Import |
|------------|------------|
| `from embedder import AsyncEmbedder` | `from memory.embedder import AsyncEmbedder` |
| `from heuristic_enricher import` | `from memory.heuristic_enricher import` |
| `from schemas import` | `from core.schemas import` |

### 2.3 memory/ingest/chat_parser.py (was chat_parser_agnostic.py)

No changes expected - verify no broken imports.

### 2.4 memory/retrieval.py

Find and replace:

| Old Import | New Import |
|------------|------------|
| `from embedder import AsyncEmbedder` | `from .embedder import AsyncEmbedder` |

### 2.5 memory/memory_pipeline.py

Find and replace:

| Old Import | New Import |
|------------|------------|
| `from embedder import AsyncEmbedder` | `from .embedder import AsyncEmbedder` |

### 2.6 core/cog_twin.py

Find and replace:

| Old Import | New Import |
|------------|------------|
| `from embedder import AsyncEmbedder` | `from memory.embedder import AsyncEmbedder` |
| `from ingest import ingest_reasoning_traces` | `from memory.ingest.pipeline import ingest_reasoning_traces` |
| `from dedup import DedupBatch` | `from memory.dedup import DedupBatch` |

---

## PHASE 3: Update protocols.py

### 3.1 Add Embeddings Section

Insert after the COGNITIVE ENGINE section:

```python
# =============================================================================
# EMBEDDINGS
# =============================================================================
from memory.embedder import (
    AsyncEmbedder,
    create_embedder,
)
```

### 3.2 Add Missing Schema Enums

Update the DATA SCHEMAS import to include all enums:

```python
# =============================================================================
# DATA SCHEMAS
# =============================================================================
from schemas import (
    MemoryNode,
    EpisodicMemory,
    # Enums (commonly needed with the dataclasses)
    Source,
    IntentType,
    Complexity,          # ADD
    EmotionalValence,    # ADD  
    Urgency,             # ADD
    ConversationMode,    # ADD
)
```

### 3.3 Update __all__ Export List

Replace the entire `__all__` list with:

```python
__all__ = [
    # Config
    "cfg",
    "load_config",
    "get_config",
    "memory_enabled",
    "is_enterprise_mode",
    # Auth
    "get_auth_service",
    "authenticate_user",
    "User",
    # Tenant
    "get_tenant_service",
    "TenantContext",
    # Cognitive
    "CogTwin",
    "DualRetriever",
    "create_adapter",
    # Embeddings
    "AsyncEmbedder",
    "create_embedder",
    # Data Schemas
    "MemoryNode",
    "EpisodicMemory",
    "Source",
    "IntentType",
    "Complexity",
    "EmotionalValence",
    "Urgency",
    "ConversationMode",
]
```

### 3.4 Update Module Docstring

Replace the docstring at the top of protocols.py:

```python
"""
protocols.py - The Nuclear Elements

This is the ONLY file new code should import from for cross-module dependencies.
Everything else is internal implementation detail.

These 23 exports are the stable API surface of enterprise_bot:

CONFIGURATION (5):
    cfg(key, default)           - Get any config value (dot notation)
    load_config(path)           - Load config from yaml
    get_config()                - Get full config object
    memory_enabled()            - Check if memory subsystem enabled
    is_enterprise_mode()        - Check if enterprise mode active

AUTH (3):
    get_auth_service()          - Singleton for all auth operations
    authenticate_user(email)    - SSO -> database user
    User                        - Auth user dataclass

TENANT (2):
    get_tenant_service()        - Singleton for tenant/dept data
    TenantContext               - Request context carrier dataclass

COGNITIVE (3):
    CogTwin                     - The brain (query/response pipeline)
    DualRetriever               - Memory retrieval system
    create_adapter(provider)    - LLM factory (Grok/Claude/etc)

EMBEDDINGS (2):
    AsyncEmbedder               - Multi-provider BGE-M3 embeddings
    create_embedder(provider)   - Embedder factory

DATA SCHEMAS (8):
    MemoryNode                  - Atomic memory chunk dataclass
    EpisodicMemory              - Conversation episode dataclass
    Source                      - Enum: memory source type
    IntentType                  - Enum: intent classification
    Complexity                  - Enum: cognitive complexity
    EmotionalValence            - Enum: emotional tone
    Urgency                     - Enum: priority level
    ConversationMode            - Enum: conversation context

Usage:
    from core.protocols import cfg, get_auth_service, CogTwin, MemoryNode, AsyncEmbedder

Version: 2.0.0
"""
```

---

## PHASE 4: Update FILE_TREE.md

Replace the `ingestion/` section and update `memory/` section in `docs/FILE_TREE.md`:

### Remove This Section:
```
├── ingestion/                         # DATA INGESTION PIPELINE
│   ├── __init__.py
│   ├── ingest.py                      # Main ingestion orchestrator
│   ├── chat_parser_agnostic.py        # Parse chat across LLM providers
│   ... (entire ingestion section)
```

### Update memory/ Section To:
```
├── memory/                            # MEMORY & RETRIEVAL
│   ├── __init__.py                    # Exports: AsyncEmbedder, DualRetriever
│   ├── embedder.py                    # AsyncEmbedder - BGE-M3 via DeepInfra/TEI
│   ├── retrieval.py                   # DualRetriever - vector + keyword search
│   ├── memory_pipeline.py             # Ingest loop, CognitiveOutput -> memory
│   ├── memory_backend.py              # Abstract backend, FileBackend
│   ├── postgres_backend.py            # PostgreSQL + pgvector implementation
│   ├── hybrid_search.py               # Vector + BM25 fusion scoring
│   ├── memory_grep.py                 # BM25 keyword search over memories
│   ├── heuristic_enricher.py          # Auto-tag memories with metadata
│   ├── cluster_schema.py              # ClusterSchemaEngine for topic clustering
│   ├── streaming_cluster.py           # Real-time cluster assignment
│   ├── evolution_engine.py            # Memory consolidation over time
│   ├── metacognitive_mirror.py        # Self-monitoring, drift detection
│   ├── reasoning_trace.py             # CognitiveTracer for debug/audit
│   ├── scoring.py                     # ResponseScore, training mode UI
│   ├── chat_memory.py                 # ChatMemoryStore - recent exchanges
│   ├── squirrel.py                    # SquirrelTool - context retrieval tool
│   ├── llm_tagger.py                  # LLM-based memory tagging
│   ├── fast_filter.py                 # Fast intent classification
│   ├── dedup.py                       # Memory deduplication
│   ├── read_traces.py                 # CLI to read reasoning traces
│   │
│   └── ingest/                        # INGESTION SUBPACKAGE
│       ├── __init__.py                # Exports: IngestPipeline, ChatParserFactory
│       ├── pipeline.py                # Main ingestion orchestrator
│       ├── chat_parser.py             # Parse chat across LLM providers
│       ├── doc_loader.py              # Load documents for RAG
│       ├── docx_to_json_chunks.py     # Convert DOCX manuals to JSON chunks
│       ├── batch_convert_warehouse.py # Batch convert Driscoll manuals
│       ├── ingest_to_postgres.py      # Load chunks into PostgreSQL
│       └── json_chunk_loader.py       # JSON chunk parsing utilities
```

### Update Quick Start Example:
```python
# The one import to rule them all:
from core.protocols import cfg, get_auth_service, CogTwin, MemoryNode, AsyncEmbedder

# Or explicit module imports:
from memory.retrieval import DualRetriever
from memory.embedder import AsyncEmbedder
from memory.ingest.pipeline import IngestPipeline
from auth.auth_service import authenticate_user
```

---

## PHASE 5: Validation

Run these checks in order. Stop and fix if any fail.

### 5.1 Syntax Check
```bash
python -m py_compile memory/__init__.py
python -m py_compile memory/embedder.py
python -m py_compile memory/ingest/__init__.py
python -m py_compile memory/ingest/pipeline.py
python -m py_compile memory/retrieval.py
python -m py_compile core/protocols.py
python -m py_compile core/cog_twin.py
```

### 5.2 Import Tests
```bash
python -c "from core.protocols import cfg, AsyncEmbedder, CogTwin, DualRetriever"
python -c "from core.protocols import Complexity, EmotionalValence, Urgency, ConversationMode"
python -c "from memory import AsyncEmbedder, DualRetriever"
python -c "from memory.embedder import AsyncEmbedder, create_embedder"
python -c "from memory.ingest.pipeline import IngestPipeline"
python -c "from memory.ingest.chat_parser import ChatParserFactory"
```

### 5.3 Full Import Chain Test
```bash
python -c "
from core.protocols import (
    cfg, load_config, get_config, memory_enabled, is_enterprise_mode,
    get_auth_service, authenticate_user, User,
    get_tenant_service, TenantContext,
    CogTwin, DualRetriever, create_adapter,
    AsyncEmbedder, create_embedder,
    MemoryNode, EpisodicMemory, Source, IntentType,
    Complexity, EmotionalValence, Urgency, ConversationMode,
)
print('All 23 exports validated ✓')
"
```

---

## FILES YOU MAY MODIFY

**Create:**
- `memory/__init__.py`
- `memory/ingest/__init__.py`

**Move (delete source, create destination):**
- `ingestion/embedder.py` → `memory/embedder.py`
- `ingestion/ingest.py` → `memory/ingest/pipeline.py`
- `ingestion/chat_parser_agnostic.py` → `memory/ingest/chat_parser.py`
- `ingestion/doc_loader.py` → `memory/ingest/doc_loader.py`
- `ingestion/docx_to_json_chunks.py` → `memory/ingest/docx_to_json_chunks.py`
- `ingestion/batch_convert_warehouse_docx.py` → `memory/ingest/batch_convert_warehouse.py`
- `ingestion/ingest_to_postgres.py` → `memory/ingest/ingest_to_postgres.py`
- `ingestion/json_chunk_loader.py` → `memory/ingest/json_chunk_loader.py`

**Edit imports:**
- `memory/ingest/pipeline.py`
- `memory/retrieval.py`
- `memory/memory_pipeline.py`
- `core/cog_twin.py`
- `core/protocols.py`

**Update documentation:**
- `docs/FILE_TREE.md`

**Delete (only after moves complete):**
- `ingestion/` directory (if empty)

---

## DO NOT TOUCH

- `core/venom_voice.py`
- `core/enterprise_twin.py`
- `core/main.py`
- `core/schemas.py`
- `core/config.py`
- `core/config_loader.py`
- `auth/*` (all files)
- `frontend/*` (all files)
- `db/*` (all files)
- `claude_sdk/*` (all files)

---

## OUTPUT REQUIRED

After completion, create `docs/RESTRUCTURE_COMPLETE.md` with:

1. **Files Created** - list with paths
2. **Files Moved** - source → destination
3. **Files Edited** - list with summary of changes
4. **Validation Results** - output of all test commands
5. **Issues Encountered** - any problems and how resolved

---

## SUCCESS CRITERIA

- [ ] `ingestion/` directory no longer exists (or is empty)
- [ ] `memory/ingest/` contains 8 files
- [ ] `memory/embedder.py` exists
- [ ] `memory/__init__.py` exports AsyncEmbedder, DualRetriever
- [ ] `core/protocols.py` exports 23 items
- [ ] All validation commands pass
- [ ] `docs/FILE_TREE.md` reflects new structure
- [ ] `docs/RESTRUCTURE_COMPLETE.md` created

---

**END OF HANDOFF**
