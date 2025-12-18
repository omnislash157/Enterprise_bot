# CogTwin Merge - SDK Agent Handoff
## For Claude Agent SDK / claude_chat.py

---

## PROJECT CONTEXT

You are working on **CogTwin**, a cognitive memory system that provides persistent, searchable memory for LLMs. We're merging the personal SaaS version with an enterprise deployment (Driscoll Foods) into ONE unified engine with config-driven behavior.

**Architecture Decision:**
```
ONE ENGINE (CogTwin) + CONFIG FLAGS
├── Personal SaaS: Full RAG + Venom voice + chat import enabled
└── Enterprise: Full RAG + Enterprise voice + chat import disabled + tenant scoping
```

---

## COMPLETED WORK (Phases 1-2) ✅

### Phase 1: CogTwin Activated
- `main.py` imports and uses `CogTwin` instead of `EnterpriseTwin`
- Empty data handling works (graceful boot with 0 memories)
- New file `init_empty_data.py` bootstraps empty data structure

### Phase 2: Voice Toggle
- Config flag `voice.engine: venom | enterprise` in `config.yaml`
- `cog_twin.py` conditionally imports voice engine (lines 103-117)
- Both voices share same `build_system_prompt()` interface

### Files Already Modified:
```
main.py              → CogTwin import/instantiation
cog_twin.py          → Conditional voice import
config.yaml          → voice.engine: venom
enterprise_voice.py  → Compatible interface
memory_grep.py       → Empty corpus guards
retrieval.py         → Graceful empty state
init_empty_data.py   → NEW bootstrap script
```

### Current Config (config.yaml):
```yaml
voice:
  engine: venom  # Toggle: venom | enterprise
  
deployment:
  mode: personal  # Toggle: personal | enterprise
  tier: full
  
features:
  memory_pipelines: true
  context_stuffing: false  # Dead - replaced by RAG
  extraction_enabled: true  # Phase 4 will use this
```

### Server Status:
```bash
python main.py
# → CogTwin initialized: 0 memories loaded
# → http://localhost:8000
```

---

## PHASE 3: Auth Scoping 🎯

### Objective
Every memory node and retrieval query must be scoped by `user_id` (personal) or `tenant_id` (enterprise). Users must NEVER see each other's memories. **Fail secure: no auth = no results.**

### Current Problem
- `retrieval.py` loads ALL nodes from `data/corpus/nodes.json`
- No filtering by user or tenant
- Enterprise users would see personal user data (catastrophic)

### Implementation Steps

#### 3.1: Add Fields to MemoryNode Schema
**File:** `schemas.py` (find MemoryNode class, around line 50-80)

Add these fields to MemoryNode:
```python
user_id: Optional[str] = None      # For personal SaaS
tenant_id: Optional[str] = None    # For enterprise
```

#### 3.2: Update CogTwin.think() Signature
**File:** `cog_twin.py` (find think method, around line 400-450)

Change from:
```python
async def think(self, query: str) -> AsyncIterator[str]:
```

To:
```python
async def think(self, query: str, user_id: str = None, tenant_id: str = None) -> AsyncIterator[str]:
```

Pass these to the retriever when calling `self.retriever.retrieve()`.

#### 3.3: Filter Retrieval by Scope
**File:** `retrieval.py` (find retrieve method in DualRetriever class)

Modify `retrieve()` to accept and filter by scope:
```python
def retrieve(self, query: str, top_k: int = 50, user_id: str = None, tenant_id: str = None) -> RetrievalResult:
    # Filter nodes BEFORE similarity search
    if tenant_id:
        filtered_nodes = [n for n in self.nodes if getattr(n, 'tenant_id', None) == tenant_id]
    elif user_id:
        filtered_nodes = [n for n in self.nodes if getattr(n, 'user_id', None) == user_id]
    else:
        # No auth = no results (fail secure)
        return RetrievalResult(nodes=[], episodes=[], scores={})
    
    # Continue with similarity search on filtered set...
```

#### 3.4: Pass Auth Context from WebSocket
**File:** `main.py` (find websocket_endpoint, around line 380-420)

Extract user context and pass to engine.think():
```python
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # Extract from auth (stub for now - actual extraction depends on Azure AD setup)
    user_id = websocket.query_params.get("user_id")  # Or from token
    tenant_id = websocket.query_params.get("tenant_id")  # Or from token
    
    # Pass to engine
    async for chunk in engine.think(content, user_id=user_id, tenant_id=tenant_id):
        # ...
```

#### 3.5: Stamp New Memories
**File:** `memory_pipeline.py` (find where new MemoryNode objects are created)

When creating new memory nodes, include user_id/tenant_id from request context.

### Quality Gate for Phase 3
- [ ] MemoryNode schema has user_id, tenant_id Optional[str] fields
- [ ] CogTwin.think() accepts user_id, tenant_id params
- [ ] Retriever filters by scope before similarity search
- [ ] Empty scope returns empty results (fail secure)
- [ ] Server boots: `python main.py`

---

## PHASE 4: Extraction Toggle

### Objective
Enterprise users cannot import ChatGPT/Claude logs. Memory builds only from their bot conversations.

### Implementation

#### 4.1: Guard Upload Endpoint
**File:** `main.py` (find upload endpoint - search for `@app.post` with "upload")

Add guard:
```python
@app.post("/upload")  # or whatever the route is
async def upload_chat(file: UploadFile, provider: str = "auto"):
    if not cfg("features.extraction_enabled", True):
        raise HTTPException(status_code=403, detail="Chat import disabled for enterprise accounts")
    # ... existing processing
```

### Quality Gate for Phase 4
- [ ] Upload endpoint returns 403 when extraction_enabled: false
- [ ] Upload works normally when extraction_enabled: true
- [ ] Server boots: `python main.py`

---

## PHASE 5: PostgreSQL + pgvector Migration

### Objective
Replace file-based storage with PostgreSQL + pgvector for production scalability and proper multi-tenant isolation.

### Part A: Database Schema
**Create:** `db/migrations/001_memory_tables.sql`

```sql
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Tenants table
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    azure_tenant_id VARCHAR(255) UNIQUE,
    config JSONB DEFAULT '{}',
    voice_engine VARCHAR(50) DEFAULT 'enterprise',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_provider VARCHAR(50) NOT NULL,
    external_id VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    tenant_id UUID REFERENCES tenants(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(auth_provider, external_id)
);

-- Memory nodes with vector embeddings
CREATE TABLE memory_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    tenant_id UUID REFERENCES tenants(id),
    conversation_id VARCHAR(255),
    sequence_index INTEGER,
    human_content TEXT,
    assistant_content TEXT,
    source VARCHAR(50),
    embedding VECTOR(1024),
    intent_type VARCHAR(100),
    complexity FLOAT,
    cluster_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast retrieval
CREATE INDEX idx_memory_nodes_user ON memory_nodes(user_id);
CREATE INDEX idx_memory_nodes_tenant ON memory_nodes(tenant_id);
CREATE INDEX idx_memory_nodes_embedding ON memory_nodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### Part B: Backend Implementation
**Create:** `postgres_backend.py`

PostgresBackend class with:
- `connect()` - connection pool setup
- `get_nodes(user_id, tenant_id)` - fetch nodes by scope
- `vector_search(embedding, user_id, tenant_id, top_k)` - similarity search with scope filter
- `insert_node(node)` - insert new memory

Use asyncpg + pgvector register_vector for proper VECTOR type handling.

### Part C: Backend Abstraction
**Create:** `memory_backend.py`

Abstract base class + FileBackend wrapper + factory function:
```python
def get_backend(config) -> MemoryBackend:
    if cfg("memory.backend") == "postgres":
        return PostgresBackend(cfg("memory.postgres.connection_string"))
    return FileBackend(data_dir)
```

Update `cog_twin.py` to use the factory.

### Part D: Migration Script
**Create:** `migrate_to_postgres.py`

Script to migrate existing file-based nodes to PostgreSQL, stamping with user_id.

### Quality Gate for Phase 5
- [ ] Migration SQL runs without errors
- [ ] PostgresBackend connects and queries work
- [ ] FileBackend maintains existing functionality
- [ ] Factory returns correct backend based on config
- [ ] Server boots with both backend types

---

## PHASE 6: Cleanup

### Objective
Archive dead code, remove deprecated paths, clean up imports.

### Tasks
- Archive `enterprise_twin.py` (no longer used, CogTwin replaces it)
- Remove `context_stuffing` code paths (replaced by RAG)
- Clean up unused imports across modified files
- Update any outdated comments
- Verify all tests pass

---

## GIT WORKFLOW

```bash
# Current branch
git checkout merge/cogtwin-unified

# After each phase
git add -A
git commit -m "Phase N: [description]"

# Safety tag exists
git tag pre-merge-backup  # Already created

# When all phases complete
git checkout main
git merge merge/cogtwin-unified
```

---

## TESTING COMMANDS

```bash
# Boot server
python main.py

# Should see:
# INFO:cog_twin:CogTwin initialized: X memories loaded
# INFO:     Uvicorn running on http://0.0.0.0:8000

# Quick health check
curl http://localhost:8000/health
```

---

## SUCCESS CRITERIA

When merge is complete:

1. **Personal SaaS user can:**
   - Sign up via Azure B2C
   - Import ChatGPT/Claude logs
   - Get Venom personality responses
   - Have private memory (user_id scoped)

2. **Enterprise user (Driscoll) can:**
   - Sign in via Azure AD
   - NOT import external logs
   - Get EnterpriseVoice responses
   - Have tenant-scoped memory

3. **System guarantees:**
   - No cross-user memory leakage
   - No cross-tenant data access
   - Sub-500ms retrieval
   - Graceful degradation with empty memory
