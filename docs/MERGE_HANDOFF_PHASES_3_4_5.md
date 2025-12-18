# CogTwin/Enterprise Bot Merge - Session Handoff

**Date:** 2025-12-18
**Branch:** `merge/cogtwin-unified`
**Safety Tag:** `pre-merge-backup`
**Status:** Phases 1-2 COMPLETE, Phases 3-5 READY

---

## Executive Summary

We're unifying CogTwin (personal RAG memory system) and Enterprise Bot (Driscoll deployment) into ONE engine with config-driven behavior. The breakthrough insight: instead of maintaining two parallel codebases, we use CogTwin for everything and toggle features via config.

**Architecture Decision:**
```
ONE ENGINE (CogTwin) + CONFIG FLAGS
├── Personal SaaS: Full stack + Venom voice + extraction enabled
└── Enterprise: Full stack + Enterprise voice + extraction disabled + tenant scoping
```

---

## What's Done (Phases 1-2)

### Phase 1: CogTwin Activated ✅
- `main.py` now imports and uses `CogTwin` instead of `EnterpriseTwin`
- Empty data handling: graceful boot with 0 memories
- Files changed: `main.py`, `memory_grep.py`, `retrieval.py`
- New file: `init_empty_data.py` (bootstraps empty data structure)

### Phase 2: Voice Toggle ✅
- Config flag: `voice.engine: venom | enterprise`
- `cog_twin.py` conditionally imports voice engine (lines 103-117)
- `enterprise_voice.py` updated with compatible `build_system_prompt()` interface
- Both voices now share same method signature

### Current Config (config.yaml)
```yaml
voice:
  engine: venom  # Toggle: venom | enterprise
  
deployment:
  mode: personal  # Toggle: personal | enterprise
  tier: full
  
features:
  memory_pipelines: true
  context_stuffing: false  # Dead - replaced by RAG
  extraction_enabled: true  # NEW - Phase 4 will use this
```

### Server Status
```bash
python main.py
# → CogTwin initialized: 0 memories loaded
# → http://localhost:8000
```

---

## Phase 3: Auth Scoping

### Objective
Every memory node and retrieval query must be scoped by `user_id` (personal) or `tenant_id` (enterprise). Users must NEVER see each other's memories.

### Current Problem
- `retrieval.py` loads ALL nodes from `data/corpus/nodes.json`
- No filtering by user or tenant
- Enterprise users would see personal user data (catastrophic)

### Implementation Plan

#### 3.1: Add user_id/tenant_id to MemoryNode Schema

**File:** `schemas.py`

```python
# CURRENT MemoryNode (around line 50-80)
class MemoryNode(BaseModel):
    id: str
    conversation_id: str
    sequence_index: int
    human_content: str
    assistant_content: str
    source: Source
    created_at: datetime
    # ... existing fields

# ADD THESE FIELDS:
    user_id: Optional[str] = None      # For personal SaaS
    tenant_id: Optional[str] = None    # For enterprise
```

#### 3.2: Pass Auth Context Through Request Chain

**File:** `main.py` - WebSocket handler

```python
# CURRENT (around line 380-420)
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # ... connection handling
    async for chunk in engine.think(content):
        # ...

# MODIFY TO:
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # Extract user context from auth (already have this from Azure AD)
    user_id = get_user_id_from_token(websocket)  # Personal users
    tenant_id = get_tenant_id_from_token(websocket)  # Enterprise users
    
    async for chunk in engine.think(
        content, 
        user_id=user_id, 
        tenant_id=tenant_id
    ):
        # ...
```

#### 3.3: Filter Retrieval by Scope

**File:** `retrieval.py` - DualRetriever class

```python
# CURRENT _load_unified method (around line 450-500)
# Loads ALL nodes without filtering

# ADD filtering in retrieve() method:
def retrieve(
    self, 
    query: str, 
    top_k: int = 50,
    user_id: str = None,      # NEW
    tenant_id: str = None     # NEW
) -> RetrievalResult:
    # Filter nodes BEFORE similarity search
    if tenant_id:
        # Enterprise: filter by tenant
        filtered_nodes = [n for n in self.nodes if n.tenant_id == tenant_id]
        filtered_embeddings = self.embeddings[[i for i, n in enumerate(self.nodes) if n.tenant_id == tenant_id]]
    elif user_id:
        # Personal: filter by user
        filtered_nodes = [n for n in self.nodes if n.user_id == user_id]
        filtered_embeddings = self.embeddings[[i for i, n in enumerate(self.nodes) if n.user_id == user_id]]
    else:
        # No auth = no results (fail secure)
        return RetrievalResult(nodes=[], episodes=[], scores={})
    
    # Continue with similarity search on filtered set
    # ...
```

#### 3.4: Update CogTwin.think() Signature

**File:** `cog_twin.py`

```python
# CURRENT (around line 400-450)
async def think(self, query: str) -> AsyncIterator[str]:
    # ...

# MODIFY TO:
async def think(
    self, 
    query: str,
    user_id: str = None,
    tenant_id: str = None
) -> AsyncIterator[str]:
    # Pass to retriever
    results = self.retriever.retrieve(
        query, 
        user_id=user_id, 
        tenant_id=tenant_id
    )
    # ...
```

#### 3.5: Stamp New Memories with Scope

**File:** `memory_pipeline.py`

When ingesting responses back into memory, stamp with user/tenant:

```python
# In ingest_response() or similar:
new_node = MemoryNode(
    # ... existing fields
    user_id=user_id,      # From request context
    tenant_id=tenant_id   # From request context
)
```

### SDK Prompt for Phase 3

```python
prompt = "Phase 3 Auth Scoping: 1) In schemas.py add user_id and tenant_id Optional[str] fields to MemoryNode class. 2) In main.py websocket_endpoint, extract user_id and tenant_id from auth context and pass to engine.think(). 3) In cog_twin.py modify think() to accept user_id and tenant_id params and pass to retriever. 4) In retrieval.py modify retrieve() to filter nodes by user_id or tenant_id before similarity search - if neither provided return empty results. 5) In memory_pipeline.py stamp new memories with user_id/tenant_id. Test by running python main.py. Report all changes."
```

### Quality Gate
- [ ] MemoryNode schema has user_id, tenant_id fields
- [ ] WebSocket extracts auth context
- [ ] CogTwin.think() accepts scope params
- [ ] Retriever filters by scope
- [ ] New memories are stamped
- [ ] Empty scope = empty results (fail secure)
- [ ] Server boots without errors

---

## Phase 4: Extraction Toggle

### Objective
Enterprise users cannot import ChatGPT/Claude logs (extraction). Memory builds only from their conversations with the bot.

### Current State
- `POST /upload` endpoint exists in `main.py`
- Accepts chat exports from Anthropic, OpenAI, Grok, Gemini
- No access control

### Implementation Plan

#### 4.1: Add Config Flag

**File:** `config.yaml`

```yaml
features:
  extraction_enabled: true  # false for enterprise
```

#### 4.2: Guard Upload Endpoint

**File:** `main.py`

```python
# CURRENT (search for @app.post("/upload") or similar)
@app.post("/upload")
async def upload_chat(file: UploadFile, provider: str = "auto"):
    # ... processing

# MODIFY TO:
@app.post("/upload")
async def upload_chat(file: UploadFile, provider: str = "auto"):
    if not cfg("features.extraction_enabled", True):
        raise HTTPException(
            status_code=403, 
            detail="Chat import disabled for enterprise accounts"
        )
    # ... existing processing
```

#### 4.3: Hide Upload UI in Frontend (Optional)

**File:** `frontend/src/lib/stores/config.ts` or relevant component

```typescript
// Expose extraction_enabled in config response
// Hide upload button when false
```

### SDK Prompt for Phase 4

```python
prompt = "Phase 4 Extraction Toggle: 1) In config.yaml add features.extraction_enabled: true. 2) In main.py find the upload endpoint and add guard: if not cfg('features.extraction_enabled', True) raise HTTPException 403 with message 'Chat import disabled'. 3) Optionally update /api/config response to include extraction_enabled flag. Test with extraction_enabled true then false. Report changes."
```

### Quality Gate
- [ ] Config flag exists in config.yaml
- [ ] Upload returns 403 when disabled
- [ ] Upload works when enabled
- [ ] Server boots both ways

---

## Phase 5: PostgreSQL + pgvector Migration

### Objective
Move from file-based storage to PostgreSQL with pgvector for production scalability and proper multi-tenant isolation.

### Current Storage (File-Based)
```
data/
├── corpus/
│   ├── nodes.json      # MemoryNode[]
│   ├── episodes.json   # EpisodicMemory[]
│   └── dedup_index.json
├── vectors/
│   ├── nodes.npy       # Embeddings (N × 1024)
│   └── episodes.npy
└── indexes/
    └── clusters.json
```

### Target Storage (PostgreSQL)
```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_provider VARCHAR(20) NOT NULL,  -- 'azure_ad', 'azure_b2c', 'google'
    external_id VARCHAR(255) NOT NULL,   -- ID from auth provider
    email VARCHAR(255),
    tenant_id UUID,                       -- NULL for personal, set for enterprise
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(auth_provider, external_id)
);

-- Tenants table (enterprise customers)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,           -- 'driscoll'
    azure_tenant_id VARCHAR(255),         -- Azure AD tenant
    config JSONB DEFAULT '{}',            -- tenant-specific overrides
    voice_engine VARCHAR(20) DEFAULT 'enterprise',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Memory nodes with pgvector
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE memory_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    tenant_id UUID REFERENCES tenants(id),  -- NULL for personal
    conversation_id VARCHAR(255),
    sequence_index INTEGER,
    human_content TEXT,
    assistant_content TEXT,
    source VARCHAR(50),                    -- 'anthropic', 'openai', 'session'
    embedding VECTOR(1024),                -- BGE-M3
    intent_type VARCHAR(50),
    complexity VARCHAR(20),
    emotional_valence FLOAT,
    cluster_id INTEGER,
    cluster_confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Episodic memories (conversation arcs)
CREATE TABLE episodic_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    tenant_id UUID REFERENCES tenants(id),
    conversation_id VARCHAR(255) NOT NULL,
    messages JSONB NOT NULL,              -- full exchange history
    summary TEXT,
    tags TEXT[],
    embedding VECTOR(1024),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enterprise documents (replaces Manuals/ folder)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    department VARCHAR(100),              -- 'purchasing', 'sales'
    title VARCHAR(255),
    content TEXT,
    chunk_index INTEGER,                  -- for chunked docs
    embedding VECTOR(1024),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast vector search
CREATE INDEX idx_memory_nodes_embedding ON memory_nodes 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_memory_nodes_user ON memory_nodes(user_id);
CREATE INDEX idx_memory_nodes_tenant ON memory_nodes(tenant_id);

CREATE INDEX idx_episodic_embedding ON episodic_memories 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_documents_embedding ON documents 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_documents_tenant_dept ON documents(tenant_id, department);
```

### Implementation Plan

#### 5.1: Create PostgresBackend Class

**New File:** `postgres_backend.py`

```python
import asyncpg
from pgvector.asyncpg import register_vector
from typing import List, Optional
from schemas import MemoryNode, EpisodicMemory

class PostgresBackend:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool = None
    
    async def connect(self):
        self.pool = await asyncpg.create_pool(self.connection_string)
        async with self.pool.acquire() as conn:
            await register_vector(conn)
    
    async def get_nodes(
        self, 
        user_id: str = None, 
        tenant_id: str = None
    ) -> List[MemoryNode]:
        query = "SELECT * FROM memory_nodes WHERE "
        if tenant_id:
            query += "tenant_id = $1"
            params = [tenant_id]
        elif user_id:
            query += "user_id = $1"
            params = [user_id]
        else:
            return []
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [MemoryNode(**dict(row)) for row in rows]
    
    async def vector_search(
        self,
        embedding: List[float],
        user_id: str = None,
        tenant_id: str = None,
        top_k: int = 50
    ) -> List[MemoryNode]:
        query = """
            SELECT *, embedding <=> $1 as distance
            FROM memory_nodes
            WHERE {} = $2
            ORDER BY distance
            LIMIT $3
        """
        scope_field = "tenant_id" if tenant_id else "user_id"
        scope_value = tenant_id or user_id
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                query.format(scope_field), 
                embedding, 
                scope_value, 
                top_k
            )
            return [MemoryNode(**dict(row)) for row in rows]
    
    async def insert_node(self, node: MemoryNode):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO memory_nodes 
                (user_id, tenant_id, conversation_id, human_content, 
                 assistant_content, source, embedding, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """, 
            node.user_id, node.tenant_id, node.conversation_id,
            node.human_content, node.assistant_content, 
            node.source.value, node.embedding
            )
```

#### 5.2: Create Backend Abstraction

**New File:** `memory_backend.py`

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from schemas import MemoryNode

class MemoryBackend(ABC):
    @abstractmethod
    async def get_nodes(self, user_id: str = None, tenant_id: str = None) -> List[MemoryNode]:
        pass
    
    @abstractmethod
    async def vector_search(self, embedding, user_id, tenant_id, top_k) -> List[MemoryNode]:
        pass
    
    @abstractmethod
    async def insert_node(self, node: MemoryNode):
        pass

class FileBackend(MemoryBackend):
    # Wrap existing file-based logic
    pass

class PostgresBackend(MemoryBackend):
    # From above
    pass
```

#### 5.3: Config-Driven Backend Selection

**File:** `config.yaml`

```yaml
memory:
  backend: file  # Toggle: file | postgres
  postgres:
    connection_string: ${DATABASE_URL}
```

**File:** `cog_twin.py`

```python
# In __init__:
if cfg("memory.backend") == "postgres":
    from postgres_backend import PostgresBackend
    self.backend = PostgresBackend(cfg("memory.postgres.connection_string"))
else:
    from file_backend import FileBackend
    self.backend = FileBackend(self.data_dir)
```

#### 5.4: Migration Script

**New File:** `migrate_to_postgres.py`

```python
"""
Migrate existing file-based data to PostgreSQL.
Stamps all existing nodes with a specified user_id.
"""
import asyncio
import json
import numpy as np
from postgres_backend import PostgresBackend

async def migrate(user_id: str, connection_string: str):
    backend = PostgresBackend(connection_string)
    await backend.connect()
    
    # Load existing nodes
    with open("data/corpus/nodes.json") as f:
        nodes = json.load(f)
    
    embeddings = np.load("data/vectors/nodes.npy")
    
    for i, node in enumerate(nodes):
        node["user_id"] = user_id
        node["embedding"] = embeddings[i].tolist()
        await backend.insert_node(MemoryNode(**node))
    
    print(f"Migrated {len(nodes)} nodes for user {user_id}")

if __name__ == "__main__":
    asyncio.run(migrate(
        user_id="YOUR_USER_ID",
        connection_string="postgresql://..."
    ))
```

### SDK Prompt for Phase 5 (Multi-Part)

**Part 1: Schema Setup**
```python
prompt = "Create database migration script in db/migrations/001_memory_tables.sql with tables: users (id UUID, auth_provider, external_id, email, tenant_id, created_at), tenants (id UUID, name, azure_tenant_id, config JSONB, voice_engine), memory_nodes (id UUID, user_id, tenant_id, conversation_id, human_content, assistant_content, source, embedding VECTOR(1024), intent_type, complexity, cluster_id, created_at), episodic_memories (same pattern), documents (tenant_id, department, title, content, chunk_index, embedding). Add pgvector extension and ivfflat indexes. Save file and confirm."
```

**Part 2: Backend Implementation**
```python
prompt = "Create postgres_backend.py with PostgresBackend class using asyncpg and pgvector. Methods: connect(), get_nodes(user_id, tenant_id), vector_search(embedding, user_id, tenant_id, top_k), insert_node(node). Use connection pooling. Handle the VECTOR type properly with register_vector. Test connection with a simple query. Report implementation."
```

**Part 3: Backend Abstraction**
```python  
prompt = "Create memory_backend.py with abstract MemoryBackend base class defining interface: get_nodes, vector_search, insert_node. Create FileBackend class wrapping existing file-based retrieval.py logic. Create factory function get_backend(config) that returns FileBackend or PostgresBackend based on cfg('memory.backend'). Update cog_twin.py to use the factory. Test with backend: file config. Report changes."
```

### Quality Gate
- [ ] Migration SQL runs without errors
- [ ] PostgresBackend connects and queries work
- [ ] FileBackend maintains existing functionality
- [ ] Factory returns correct backend based on config
- [ ] Vector search returns correct results
- [ ] Server boots with both backend types
- [ ] Retrieval performance < 500ms

---

## Environment Setup for Next Session

### Git Status
```bash
cd enterprise_bot
git checkout merge/cogtwin-unified
git status  # Should show Phase 1+2 changes
```

### Required Packages
```bash
pip install asyncpg pgvector psycopg2-binary
```

### Database Setup (for Phase 5)
```bash
# Railway PostgreSQL or local
# Ensure pgvector extension is available
CREATE EXTENSION IF NOT EXISTS vector;
```

### Test Server
```bash
python main.py
# Should see:
# INFO:cog_twin:CogTwin initialized: 0 memories loaded
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## File Reference

### Files Modified in Phases 1-2
- `main.py` - CogTwin import, engine instantiation
- `cog_twin.py` - Voice toggle (lines 103-117, 281)
- `config.yaml` - voice.engine setting
- `enterprise_voice.py` - Compatible interface
- `memory_grep.py` - Empty corpus guards
- `retrieval.py` - Graceful empty state

### Files to Modify in Phase 3
- `schemas.py` - Add user_id, tenant_id to MemoryNode
- `main.py` - Extract auth context in WebSocket
- `cog_twin.py` - Pass scope to retriever
- `retrieval.py` - Filter by scope
- `memory_pipeline.py` - Stamp new memories

### Files to Modify in Phase 4
- `config.yaml` - Add extraction_enabled
- `main.py` - Guard upload endpoint

### New Files for Phase 5
- `db/migrations/001_memory_tables.sql`
- `postgres_backend.py`
- `memory_backend.py`
- `migrate_to_postgres.py`

---

## Concern List (Resolved)

| ID | Concern | Resolution |
|----|---------|------------|
| H1 | schemas.py unused | ✅ Used by ingest.py, memory_pipeline.py, retrieval.py |
| H2 | Enterprise vs CogTwin divergence | ✅ Using CogTwin only, EnterpriseTwin deprecated |
| H3 | Config branching nightmare | ✅ Simple flags: voice.engine, extraction_enabled, memory.backend |
| H4 | doc_loader context stuffing | ✅ Deprecated, using full RAG |
| C1 | Two main.py files | ✅ Only root main.py, no backend/app/ |
| C2 | Voice interface mismatch | ✅ Fixed in Phase 2, same build_system_prompt() signature |
| C3 | Memory pipeline dormant | ✅ Now active via CogTwin |

---

## Success Criteria for Full Merge

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
   - Access department documents via RAG

3. **System guarantees:**
   - No cross-user memory leakage
   - No cross-tenant data access
   - Sub-500ms retrieval
   - Graceful degradation with empty memory

---

## Next Session Checklist

- [ ] Verify on `merge/cogtwin-unified` branch
- [ ] Server boots: `python main.py`
- [ ] Run Phase 3 SDK prompt
- [ ] Test auth scoping
- [ ] Run Phase 4 SDK prompt
- [ ] Test extraction toggle
- [ ] Set up PostgreSQL with pgvector
- [ ] Run Phase 5 SDK prompts (3 parts)
- [ ] Test full flow
- [ ] Commit and push
- [ ] Merge to main when stable
