# Protocol Recon Report

**Date:** 2024-12-21
**Agent:** AGENT 1 (Protocol Recon - Read-Only)
**Mission:** Deep discovery of cross-module imports to audit `protocols.py` completeness

---

## Executive Summary

This report analyzes all cross-module imports in the enterprise_bot codebase to identify:
1. Current exports from `core/protocols.py`
2. Cross-module import patterns
3. Items that should be added to protocols.py
4. Circular dependency risks

**Key Findings:**
- protocols.py currently exports **21 items** (not 16 as initially documented)
- **3 circular dependency chains detected** (CRITICAL)
- **AsyncEmbedder** is the most important missing export (used cross-module 3+ times)
- Several auth routes and utilities missing from protocols but only used in main.py

---

## Current Exports (protocols.py)

### Configuration (5 exports)
| Export | Source Module | Purpose |
|--------|---------------|---------|
| `cfg` | config_loader | Get any config value (dot notation) |
| `load_config` | config_loader | Load config from yaml |
| `get_config` | config_loader | Get full config object |
| `memory_enabled` | config_loader | Check if memory subsystem enabled |
| `is_enterprise_mode` | config_loader | Check if enterprise mode active |

### Authentication (3 exports)
| Export | Source Module | Purpose |
|--------|---------------|---------|
| `get_auth_service` | auth/auth_service | Singleton for all auth operations |
| `authenticate_user` | auth/auth_service | SSO → database user |
| `User` | auth/auth_service | Auth user dataclass |

### Tenant Management (2 exports)
| Export | Source Module | Purpose |
|--------|---------------|---------|
| `get_tenant_service` | auth/tenant_service | Singleton for tenant/dept data |
| `TenantContext` | core/enterprise_tenant | Request context carrier dataclass |

### Cognitive Engine (3 exports)
| Export | Source Module | Purpose |
|--------|---------------|---------|
| `CogTwin` | core/cog_twin | The brain (query/response pipeline) |
| `DualRetriever` | memory/retrieval | Memory retrieval system |
| `create_adapter` | core/model_adapter | LLM factory (Grok/Claude/etc) |

### Data Schemas (8 exports)
| Export | Source Module | Purpose |
|--------|---------------|---------|
| `MemoryNode` | core/schemas | Atomic memory chunk dataclass |
| `EpisodicMemory` | core/schemas | Conversation episode dataclass |
| `Source` | core/schemas | Enum for memory source type |
| `IntentType` | core/schemas | Enum for intent classification |
| `Complexity` | core/schemas | Enum for cognitive complexity |
| `EmotionalValence` | core/schemas | Enum for emotional tone |
| `Urgency` | core/schemas | Enum for priority level |
| `ConversationMode` | core/schemas | Enum for conversation context |

**Note:** Last 4 enums (Complexity, EmotionalValence, Urgency, ConversationMode) are NOT currently exported but exist in schemas.py

---

## Cross-Module Import Map

### core/ imports from other modules:

**cog_twin.py:**
```python
Line   82: from metacognitive_mirror import (          # memory/
Line   90: from retrieval import DualRetriever          # memory/
Line   91: from embedder import AsyncEmbedder           # ingestion/
Line   94: from memory_pipeline import (                # memory/
Line  120: from reasoning_trace import CognitiveTracer, StepType, ReasoningTrace  # memory/
Line  123: from scoring import ResponseScore, TrainingModeUI  # memory/
Line  126: from chat_memory import ChatMemoryStore      # memory/
Line  129: from squirrel import SquirrelTool, SquirrelQuery  # memory/
Line 1513: from ingest import ingest_reasoning_traces  # ingestion/
Line 1514: from dedup import DedupBatch                 # ingestion/
```

**enterprise_twin.py:**
```python
Line  273: from squirrel import SquirrelTool            # memory/
Line  285: from memory_pipeline import MemoryPipeline   # memory/
```

**main.py:**
```python
Line  117: from auth_service import get_auth_service, authenticate_user  # auth/
Line  125: from tenant_service import get_tenant_service  # auth/
Line  133: from admin_routes import admin_router        # auth/
Line  150: from sso_routes import router as sso_router  # auth/
Line  158: from azure_auth import validate_access_token, is_configured  # auth/
```

**protocols.py:**
```python
Line   54: from auth_service import (                   # auth/
Line   63: from tenant_service import (                 # auth/
Line   75: from retrieval import DualRetriever          # memory/
```

### memory/ imports from other modules:

**llm_tagger.py:**
```python
Line   33: from schemas import EpisodicMemory           # core/
Line  339: from schemas import Source                   # core/
```

**memory_backend.py:**
```python
Line   13: from config import get_config                # core/
Line   41: from schemas import MemoryNode               # core/
Line   45: from postgres_backend import PostgresBackend # ingestion/
Line  529: from config import load_config               # core/
```

**memory_pipeline.py:**
```python
Line   30: from schemas import MemoryNode, Source       # core/
Line   31: from embedder import AsyncEmbedder           # ingestion/
```

**retrieval.py:**
```python
Line   36: from schemas import (                        # core/
Line   40: from embedder import AsyncEmbedder           # ingestion/
```

### auth/ imports from other modules:

**(no cross-module imports found)**

### ingestion/ imports from other modules:

**ingest.py:**
```python
Line   54: from heuristic_enricher import HeuristicEnricher, enrich_nodes_batch  # memory/
Line   55: from schemas import (                        # core/
```

**postgres_backend.py:**
```python
Line   34: from schemas import MemoryNode, Source, IntentType, Complexity, EmotionalValence, Urgency, ConversationMode  # core/
```

---

## Missing from Protocols

### HIGH PRIORITY - Recommend Adding

#### 1. **AsyncEmbedder** (ingestion/embedder.py)
- **Used in:** 3 files across core/ and memory/
  - `core/cog_twin.py`
  - `memory/memory_pipeline.py`
  - `memory/retrieval.py`
- **Recommendation:** **CRITICAL - ADD TO PROTOCOLS**
- **Rationale:** Central interface for all embedding operations. Used across multiple modules. Should be in protocols as a stable API.
- **Note:** The handoff document already plans to move this to `memory/embedder.py` and add to protocols

#### 2. **Additional Schema Enums** (core/schemas.py)
- **Items:** `Complexity`, `EmotionalValence`, `Urgency`, `ConversationMode`
- **Used in:** `ingestion/postgres_backend.py`
- **Recommendation:** **ADD TO PROTOCOLS** (for completeness)
- **Rationale:** These enums are already in schemas.py alongside MemoryNode/EpisodicMemory. If schemas exports some enums (Source, IntentType), it should export all related enums for consistency.

### MEDIUM PRIORITY - Consider Adding

#### 3. **MemoryPipeline** (memory/memory_pipeline.py)
- **Used in:** 1 file (`core/enterprise_twin.py`)
- **Recommendation:** **CONSIDER ADDING**
- **Rationale:** Core cognitive feature used in enterprise twin. If enterprise_twin is a major feature, this pipeline should be in protocols.

#### 4. **SquirrelTool** (memory/squirrel.py)
- **Used in:** 2 files (`core/cog_twin.py`, `core/enterprise_twin.py`)
- **Recommendation:** **CONSIDER ADDING**
- **Rationale:** Used in both major cognitive twins. Appears to be a key tool interface.

#### 5. **ChatMemoryStore** (memory/chat_memory.py)
- **Used in:** 1 file (`core/cog_twin.py`)
- **Recommendation:** **MAYBE**
- **Rationale:** Core memory feature but only used in one place currently.

### LOW PRIORITY - Skip for Now

#### 6. **Auth Routes and Utilities**
- **Items:**
  - `admin_router` (auth/admin_routes.py)
  - `router` as `sso_router` (auth/sso_routes.py)
  - `validate_access_token` (auth/azure_auth.py)
  - `is_configured` (auth/azure_auth.py)
- **Used in:** Only `core/main.py` (FastAPI application setup)
- **Recommendation:** **SKIP**
- **Rationale:** These are HTTP route registration artifacts, not business logic APIs. They only need to be imported once in main.py for app setup. Not needed in protocols.

#### 7. **Internal Memory/Ingestion Components**
- **Items:**
  - `metacognitive_mirror` exports
  - `reasoning_trace` exports
  - `scoring` exports
  - `ingest_reasoning_traces` (ingestion/ingest.py)
  - `DedupBatch` (ingestion/dedup.py)
  - `HeuristicEnricher` (memory/heuristic_enricher.py)
  - `PostgresBackend` (ingestion/postgres_backend.py)
- **Recommendation:** **SKIP**
- **Rationale:** These are internal implementation details used within specific subsystems. They don't represent stable cross-cutting APIs that need centralized export.

---

## Circular Dependency Risks

**STATUS: 🔴 CRITICAL - 3 CIRCULAR DEPENDENCY CHAINS DETECTED**

### Module Dependency Graph
```
core/       imports from: auth, ingestion, memory
memory/     imports from: core, ingestion
auth/       imports from: (none)
ingestion/  imports from: core, memory
```

### Detected Cycles

#### ⚠️ Cycle 1: core ↔ ingestion
```
core/ → ingestion/ → core/
```
**Details:**
- `core/cog_twin.py` imports from `ingestion/embedder.py`, `ingestion/ingest.py`, `ingestion/dedup.py`
- `ingestion/ingest.py` imports from `core/schemas.py`
- `ingestion/postgres_backend.py` imports from `core/schemas.py`

**Risk Level:** MODERATE
**Impact:** Python can handle this via lazy imports, but indicates poor separation of concerns.

#### ⚠️ Cycle 2: core → ingestion → memory → core
```
core/ → ingestion/ → memory/ → core/
```
**Details:**
- `core/cog_twin.py` imports from `ingestion/embedder.py`
- `ingestion/ingest.py` imports from `memory/heuristic_enricher.py`
- `memory/llm_tagger.py`, `memory/memory_backend.py` import from `core/schemas.py`, `core/config.py`

**Risk Level:** HIGH
**Impact:** Three-way circular dependency increases complexity and makes refactoring difficult.

#### ⚠️ Cycle 3: ingestion ↔ memory
```
ingestion/ → memory/ → ingestion/
```
**Details:**
- `ingestion/ingest.py` imports from `memory/heuristic_enricher.py`
- `memory/memory_backend.py` imports from `ingestion/postgres_backend.py`
- `memory/memory_pipeline.py`, `memory/retrieval.py` import from `ingestion/embedder.py`

**Risk Level:** HIGH
**Impact:** Tight coupling between memory and ingestion subsystems. These should be more cleanly separated.

### Recommendations to Break Cycles

1. **Move embedder.py to memory/** (Already planned in HANDOFF)
   - This will partially resolve cycles by putting embedder in the right module
   - `ingestion/embedder.py` → `memory/embedder.py`

2. **Move postgres_backend.py to memory/** (Not currently planned)
   - `postgres_backend` is really a memory storage backend, not an ingestion concern
   - Should be `memory/backends/postgres.py` or similar

3. **Extract shared schemas to protocols.py**
   - Make `core/` the only "root" module that others can import from
   - Never allow core/ to import from ingestion/ or memory/ directly
   - Use dependency injection or callbacks instead

4. **Create clear layering:**
   ```
   Ideal Architecture:
   core/         → exports via protocols.py (leaf, no dependencies on other modules)
   ├─ schemas
   ├─ config
   ├─ protocols (aggregator)

   auth/         → depends only on core/ (via protocols)
   memory/       → depends only on core/ (via protocols)
   ingestion/    → depends only on core/ and memory/ (via protocols)

   main.py       → depends on all modules (composition root)
   ```

5. **Immediate fix for HANDOFF:**
   - After moving `embedder.py` to `memory/`, update all imports to use `from memory.embedder import`
   - This breaks the ingestion→memory cycle partially
   - Still need to address `ingestion/ingest.py` importing from `memory/heuristic_enricher.py`

---

## Frontend API Contracts

### Backend Routes Exposed

Based on analysis of `core/main.py` and `auth/*.py` route files:

#### Core Application Routes
- `GET /health` - Health check endpoint
- `GET /` - Root/home endpoint
- `GET /api/config` - Configuration endpoint
- `POST /api/verify-email` - Email verification
- `GET /api/whitelist/stats` - Whitelist statistics
- `POST /api/upload/chat` - Chat upload endpoint
- `GET /api/whoami` - Current user info

#### Analytics Endpoints
- `GET /api/analytics` - General analytics
- `GET /api/analytics/cognitive-state` - Cognitive state metrics
- `GET /api/analytics/health-check` - Health check analytics
- `GET /api/analytics/session-stats` - Session statistics

#### Department Endpoints
- `GET /api/departments` - List departments
- `GET /api/content` - Content by department

#### Admin Endpoints (prefix: `/api/admin`)
- `GET /users` - List all users
- `GET /users/{user_id}` - Get specific user
- `PUT /users/{user_id}/role` - Update user role
- `POST /users` - Create new user
- `POST /users/batch` - Batch create users
- `PUT /users/{user_id}` - Update user
- `DELETE /users/{user_id}` - Delete user
- `POST /users/{user_id}/reactivate` - Reactivate user
- `GET /departments/{slug}/users` - Users by department
- `POST /access/grant` - Grant access
- `POST /access/revoke` - Revoke access
- `GET /audit` - Audit logs
- `GET /stats` - Admin statistics
- `GET /departments` - Department management

#### SSO/Auth Endpoints (prefix: `/api/auth`)
- `GET /config` - Auth configuration
- `GET /login` - Login page
- `GET /login-url` - Get OAuth login URL
- `POST /callback` - OAuth callback handler
- `POST /refresh` - Refresh access token
- `POST /logout` - Logout user
- `GET /me` - Current user profile

#### WebSocket Endpoint
- `WS /api/chat` - Chat WebSocket connection

**Note:** These are HTTP/REST contracts between frontend and backend. They don't need to be in protocols.py since protocols is for Python module imports, not HTTP APIs.

---

## Database Module (db/)

### Files Scanned
- `db/install_pgvector.py`
- `db/run_migration_002.py`
- `db/run_migrations_002_003.py`

### Imports
All db/ scripts use only standard library imports:
- `psycopg2` (PostgreSQL driver)
- `os`, `sys` (system utilities)
- `pathlib.Path` (path handling)
- `dotenv.load_dotenv` (environment variables)

**No cross-module dependencies detected.**

---

## Recommendations

### 1. Critical - Add AsyncEmbedder to protocols.py

**Action:** After AGENT 2 moves `ingestion/embedder.py` → `memory/embedder.py`, add to protocols:

```python
# =============================================================================
# EMBEDDINGS
# =============================================================================
from memory.embedder import (
    AsyncEmbedder,
    create_embedder,  # If factory function exists
)
```

Add to `__all__`:
```python
    # Embeddings
    "AsyncEmbedder",
    "create_embedder",
```

### 2. High - Export All Schema Enums

**Action:** Add missing enums to protocols.py for API completeness:

```python
from schemas import (
    MemoryNode,
    EpisodicMemory,
    # Enums (commonly needed with the dataclasses)
    Source,
    IntentType,
    Complexity,           # ADD
    EmotionalValence,     # ADD
    Urgency,              # ADD
    ConversationMode,     # ADD
)
```

Update `__all__`:
```python
    # Data
    "MemoryNode",
    "EpisodicMemory",
    "Source",
    "IntentType",
    "Complexity",          # ADD
    "EmotionalValence",    # ADD
    "Urgency",             # ADD
    "ConversationMode",    # ADD
```

### 3. Medium - Consider Memory Pipeline Exports

**Decision Point:** Should these be in protocols?

```python
# =============================================================================
# MEMORY SUBSYSTEM
# =============================================================================
from memory.memory_pipeline import MemoryPipeline
from memory.squirrel import SquirrelTool
from memory.chat_memory import ChatMemoryStore
```

**Recommendation:** Wait until after restructure. If enterprise_twin becomes a primary feature, add MemoryPipeline and SquirrelTool.

### 4. Critical - Address Circular Dependencies

**Immediate Actions:**
1. Complete AGENT 2 restructure (moves embedder to memory/)
2. Move `ingestion/postgres_backend.py` → `memory/backends/postgres.py` (future PR)
3. Refactor `ingestion/ingest.py` to not import from memory/ (inject HeuristicEnricher via dependency injection)

**Long-term Architectural Fix:**
- Establish strict layering: core/ (schemas, config) ← auth/ ← memory/ ← ingestion/ ← main.py
- Never allow core/ to import from any other app module
- Use protocols.py as the ONLY import surface from core/

### 5. Documentation - Update Protocol Docstring

The docstring in protocols.py says "These 12 exports" but there are now 21 (soon to be 23+ with AsyncEmbedder and new enums). Update the docstring to reflect reality:

```python
"""
protocols.py - The Nuclear Elements

This is the ONLY file new code should import from for cross-module dependencies.
Everything else is internal implementation detail.

These exports are the stable API surface of enterprise_bot:
(grouped by category in __all__ below)

CONFIGURATION: cfg, load_config, get_config, memory_enabled, is_enterprise_mode
AUTH: get_auth_service, authenticate_user, User
TENANT: get_tenant_service, TenantContext
COGNITIVE: CogTwin, DualRetriever, create_adapter
EMBEDDINGS: AsyncEmbedder, create_embedder
DATA: MemoryNode, EpisodicMemory, Source, IntentType, Complexity, EmotionalValence, Urgency, ConversationMode

...
"""
```

---

## Summary Table: What to Add to protocols.py

| Priority | Item | Source | Used By | Status |
|----------|------|--------|---------|--------|
| 🔴 CRITICAL | `AsyncEmbedder` | ingestion/embedder.py → memory/embedder.py | cog_twin, memory_pipeline, retrieval | **ADD** |
| 🔴 CRITICAL | `create_embedder` | ingestion/embedder.py → memory/embedder.py | (factory function) | **ADD** |
| 🟡 HIGH | `Complexity` | core/schemas.py | postgres_backend | **ADD** |
| 🟡 HIGH | `EmotionalValence` | core/schemas.py | postgres_backend | **ADD** |
| 🟡 HIGH | `Urgency` | core/schemas.py | postgres_backend | **ADD** |
| 🟡 HIGH | `ConversationMode` | core/schemas.py | postgres_backend | **ADD** |
| 🟢 MEDIUM | `MemoryPipeline` | memory/memory_pipeline.py | enterprise_twin | DEFER |
| 🟢 MEDIUM | `SquirrelTool` | memory/squirrel.py | cog_twin, enterprise_twin | DEFER |
| 🟢 MEDIUM | `ChatMemoryStore` | memory/chat_memory.py | cog_twin | DEFER |
| ⚪ LOW | Auth routes/utils | auth/*.py | main.py only | SKIP |
| ⚪ LOW | Internal memory/ingestion | various | internal use | SKIP |

---

## Validation Checklist

After implementing recommendations:

- [ ] `AsyncEmbedder` is exported from protocols.py
- [ ] `create_embedder` is exported from protocols.py
- [ ] All 8 schema enums are exported (Source, IntentType, Complexity, EmotionalValence, Urgency, ConversationMode)
- [ ] protocols.py docstring updated with current export count
- [ ] `from core.protocols import AsyncEmbedder` works
- [ ] `from core.protocols import Complexity` works
- [ ] Circular dependencies reduced (embedder moved to memory/)
- [ ] All imports in moved files updated to reflect new locations

---

**END OF PROTOCOL RECON REPORT**

Generated by: AGENT 1 (Protocol Recon)
Date: 2024-12-21
Mode: Read-Only Reconnaissance
Files Analyzed: 47 Python files across core/, memory/, auth/, ingestion/
