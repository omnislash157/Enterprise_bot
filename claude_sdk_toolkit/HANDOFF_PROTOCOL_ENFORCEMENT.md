# HANDOFF: Protocol Enforcement - Health Score 72→95

**Date:** 2024-12-21  
**Mode:** Execute  
**Prerequisite:** Ghost Hunt Complete (health score 72/100)

---

## Mission Overview

Enforce the protocol boundary. All cross-module imports go through `core/protocols.py`.

Three objectives:
1. **ADD** 8 missing exports to protocols.py
2. **REFACTOR** cog_twin.py to import from protocols (eliminate 13 ghost imports)
3. **FIX** 4 relative import violations in memory/

---

## PHASE 1: Add Missing Protocol Exports

### 1.1 Update `core/protocols.py`

Add new section after EMBEDDINGS, before DATA SCHEMAS:

```python
# =============================================================================
# COGNITIVE PIPELINE
# =============================================================================
from memory.metacognitive_mirror import (
    MetacognitiveMirror,
    QueryEvent,
    CognitivePhase,
)

from memory.memory_pipeline import (
    MemoryPipeline,
    CognitiveOutput,
    ThoughtType,
)

from memory.reasoning_trace import (
    CognitiveTracer,
    StepType,
    ReasoningTrace,
)

from memory.scoring import (
    ResponseScore,
    TrainingModeUI,
)

from memory.chat_memory import ChatMemoryStore

from memory.squirrel import (
    SquirrelTool,
    SquirrelQuery,
)
```

### 1.2 Update `__all__` in protocols.py

Add to the `__all__` list:

```python
__all__ = [
    # Config (5)
    "cfg",
    "load_config",
    "get_config",
    "memory_enabled",
    "is_enterprise_mode",
    # Auth (3)
    "get_auth_service",
    "authenticate_user",
    "User",
    # Tenant (2)
    "get_tenant_service",
    "TenantContext",
    # Cognitive (3)
    "CogTwin",
    "DualRetriever",
    "create_adapter",
    # Embeddings (2)
    "AsyncEmbedder",
    "create_embedder",
    # Cognitive Pipeline (14) - NEW
    "MetacognitiveMirror",
    "QueryEvent",
    "CognitivePhase",
    "MemoryPipeline",
    "CognitiveOutput",
    "ThoughtType",
    "CognitiveTracer",
    "StepType",
    "ReasoningTrace",
    "ResponseScore",
    "TrainingModeUI",
    "ChatMemoryStore",
    "SquirrelTool",
    "SquirrelQuery",
    # Data Schemas (8)
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

### 1.3 Update protocols.py docstring

Update the docstring header to reflect new count:

```python
"""
protocols.py - The Nuclear Elements

This is the ONLY file new code should import from for cross-module dependencies.
Everything else is internal implementation detail.

These 37 exports are the stable API surface of enterprise_bot:

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

COGNITIVE PIPELINE (14):
    MetacognitiveMirror         - Self-monitoring, drift detection
    QueryEvent                  - Query event dataclass
    CognitivePhase              - Enum: cognitive processing phase
    MemoryPipeline              - Ingest loop, CognitiveOutput -> memory
    CognitiveOutput             - Pipeline output dataclass
    ThoughtType                 - Enum: thought classification
    CognitiveTracer             - Debug/audit trace recorder
    StepType                    - Enum: reasoning step type
    ReasoningTrace              - Trace dataclass
    ResponseScore               - Response quality score
    TrainingModeUI              - Training mode interface
    ChatMemoryStore             - Recent exchanges store
    SquirrelTool                - Context retrieval tool
    SquirrelQuery               - Query dataclass for squirrel

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

Version: 3.0.0
"""
```

---

## PHASE 2: Refactor cog_twin.py Imports

### 2.1 Find and Replace Ghost Imports

In `core/cog_twin.py`, locate these direct memory imports (around lines 82-129):

**DELETE these lines:**
```python
from memory.metacognitive_mirror import MetacognitiveMirror, QueryEvent, CognitivePhase
from memory.memory_pipeline import MemoryPipeline, CognitiveOutput, ThoughtType
from memory.reasoning_trace import CognitiveTracer, StepType, ReasoningTrace
from memory.scoring import ResponseScore, TrainingModeUI
from memory.chat_memory import ChatMemoryStore
from memory.squirrel import SquirrelTool, SquirrelQuery
```

**REPLACE with single protocol import:**

Find existing protocol import line (should be near top):
```python
from core.protocols import cfg, ...
```

Extend it to include the new exports:
```python
from core.protocols import (
    # Config
    cfg,
    memory_enabled,
    is_enterprise_mode,
    # Auth
    get_auth_service,
    User,
    # Tenant
    get_tenant_service,
    TenantContext,
    # Cognitive
    DualRetriever,
    create_adapter,
    # Embeddings
    AsyncEmbedder,
    # Cognitive Pipeline
    MetacognitiveMirror,
    QueryEvent,
    CognitivePhase,
    MemoryPipeline,
    CognitiveOutput,
    ThoughtType,
    CognitiveTracer,
    StepType,
    ReasoningTrace,
    ResponseScore,
    TrainingModeUI,
    ChatMemoryStore,
    SquirrelTool,
    SquirrelQuery,
    # Data Schemas
    MemoryNode,
    EpisodicMemory,
    Source,
    IntentType,
)
```

### 2.2 Fix Dead Import

In `core/cog_twin.py`, find and **DELETE** (around line 108):
```python
from core.enterprise_voice import ...
```
This file doesn't exist. Remove the import entirely.

---

## PHASE 3: Fix Relative Import Violations

### 3.1 memory/cluster_schema.py (line ~29)

**FIND:**
```python
from heuristic_enricher import
```

**REPLACE:**
```python
from .heuristic_enricher import
```

### 3.2 memory/hybrid_search.py (line ~25)

**FIND:**
```python
from memory_grep import
```

**REPLACE:**
```python
from .memory_grep import
```

### 3.3 memory/llm_tagger.py (line ~33)

**FIND:**
```python
from schemas import
```

**REPLACE:**
```python
from core.schemas import
```

### 3.4 memory/squirrel.py (line ~25)

**FIND:**
```python
from chat_memory import
```

**REPLACE:**
```python
from .chat_memory import
```

---

## VALIDATION

After all changes:

```bash
# Syntax check modified files
python -m py_compile core/protocols.py
python -m py_compile core/cog_twin.py
python -m py_compile memory/cluster_schema.py
python -m py_compile memory/hybrid_search.py
python -m py_compile memory/llm_tagger.py
python -m py_compile memory/squirrel.py

# Test all 37 protocol exports
python -c "from core.protocols import *; print(f'All {len(__all__)} protocols OK')"

# Test specific new exports
python -c "from core.protocols import MetacognitiveMirror, MemoryPipeline, CognitiveTracer; print('Cognitive Pipeline OK')"
python -c "from core.protocols import ChatMemoryStore, SquirrelTool, ResponseScore; print('Memory Tools OK')"

# Verify no direct memory imports in cog_twin
grep -n "from memory\." core/cog_twin.py | head -20
# Should return ZERO lines (or only relative imports if CogTwin is in core/)
```

---

## FILES YOU MAY MODIFY

**Edit:**
- `core/protocols.py` - Add 14 new exports, update docstring to v3.0.0
- `core/cog_twin.py` - Replace 13 direct imports with protocol import, remove dead import
- `memory/cluster_schema.py` - Fix relative import
- `memory/hybrid_search.py` - Fix relative import
- `memory/llm_tagger.py` - Fix core.schemas import
- `memory/squirrel.py` - Fix relative import

**Update:**
- `.claude/CHANGELOG.md` - Append session summary
- `.claude/CHANGELOG_COMPACT.md` - Update if needed

---

## DO NOT TOUCH

- `core/venom_voice.py`
- `core/enterprise_twin.py`
- `core/main.py`
- `core/schemas.py`
- `auth/*`
- `frontend/*`
- `memory/backends/*`
- `memory/ingest/*`

---

## SUCCESS CRITERIA

- [ ] `core/protocols.py` exports 37 items (was 23)
- [ ] `core/protocols.py` version updated to 3.0.0
- [ ] `core/cog_twin.py` has ZERO direct `from memory.` imports
- [ ] `core/cog_twin.py` dead import removed
- [ ] All 4 relative import violations fixed
- [ ] All validation commands pass
- [ ] Health score: 95/100

---

## OUTPUT REQUIRED

1. **Update `.claude/CHANGELOG.md`** - Session summary
2. **Update `.claude/CHANGELOG_COMPACT.md`** - If approaching token limits

---

**END OF HANDOFF**
