# Memory Backend Integration Guide - Phase 5

This document explains how to integrate the new `memory_backend.py` abstraction layer into the existing retrieval system.

## Overview

The `memory_backend.py` module provides a pluggable backend abstraction that allows switching between:
- **FileBackend**: Current JSON/NumPy file-based storage (default)
- **PostgresBackend**: Future SQL-based storage with pgvector (Phase 5)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Application Layer                       │
│         (retrieval.py, memory_pipeline.py)              │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Uses MemoryBackend interface
                     │
┌────────────────────▼────────────────────────────────────┐
│              memory_backend.py                           │
│  ┌────────────────────────────────────────────────┐    │
│  │  MemoryBackend (Abstract Base Class)           │    │
│  │  - get_nodes(user_id, tenant_id)               │    │
│  │  - vector_search(embedding, ...)               │    │
│  │  - insert_node(node)                           │    │
│  │  - get_embeddings(...)                         │    │
│  │  - get_cluster_info()                          │    │
│  └────────────────────────────────────────────────┘    │
│           ▲                          ▲                   │
│           │                          │                   │
│  ┌────────┴─────────┐      ┌────────┴────────────┐    │
│  │   FileBackend    │      │  PostgresBackend     │    │
│  │  (implemented)   │      │  (future/stub)       │    │
│  └──────────────────┘      └──────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                     │
                     │ Storage layer
                     │
        ┌────────────┴──────────────┐
        │                           │
   ┌────▼─────┐              ┌─────▼──────┐
   │ JSON/NPY │              │ PostgreSQL  │
   │  Files   │              │  + pgvector │
   └──────────┘              └────────────┘
```

## Configuration

Add to `config.yaml`:

```yaml
memory:
  backend: file                 # "file" or "postgres"

  # PostgreSQL configuration (only needed if backend = "postgres")
  postgres:
    host: localhost
    port: 5432
    database: enterprise_bot
    user: postgres
    password: ${POSTGRES_PASSWORD}  # Use env var for secrets
```

## Basic Usage

### Option 1: Direct Backend Usage (Recommended for new code)

```python
from memory_backend import get_backend
from config import get_config

# Initialize backend from config
config = get_config()
backend = get_backend(config)

# Get nodes for a tenant
nodes = backend.get_nodes(tenant_id="driscoll")

# Perform vector search
query_embedding = embedder.embed("How do I handle returns?")
results, scores = backend.vector_search(
    query_embedding,
    tenant_id="driscoll",
    top_k=10,
    min_score=0.3
)

# Insert new node
from schemas import MemoryNode, Source
from datetime import datetime

node = MemoryNode(
    id="new_node_123",
    conversation_id="conv_456",
    sequence_index=0,
    human_content="How do I process returns?",
    assistant_content="To process returns...",
    source=Source.ANTHROPIC,
    created_at=datetime.now(),
    tenant_id="driscoll"
)
backend.insert_node(node)
```

### Option 2: Integrate with Existing Retrieval System

Update `retrieval.py` to use the backend abstraction:

```python
# In retrieval.py

from memory_backend import get_backend, MemoryBackend

class ProcessMemoryRetriever:
    """
    Retriever for clustered memory nodes (What/How).

    Now uses pluggable backend instead of loading files directly.
    """

    def __init__(
        self,
        backend: MemoryBackend,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        """
        Initialize process memory retriever.

        Args:
            backend: Memory backend instance (FileBackend or PostgresBackend)
            user_id: User context for filtering
            tenant_id: Tenant context for filtering
        """
        self.backend = backend
        self.user_id = user_id
        self.tenant_id = tenant_id

        # Load nodes from backend
        self.nodes = backend.get_nodes(user_id=user_id, tenant_id=tenant_id)
        self.embeddings = backend.get_embeddings(user_id=user_id, tenant_id=tenant_id)
        self.cluster_info = backend.get_cluster_info()

        # Pre-normalize for cosine similarity (existing logic)
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        self.normalized = self.embeddings / (norms + 1e-8)

        # ... rest of existing init logic

    def retrieve(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        relevance_threshold: float = 0.5,
        cluster_boost: float = 0.1,
    ) -> Tuple[List[MemoryNode], List[float]]:
        """
        Retrieve relevant memory nodes.

        Note: Auth filtering now happens at backend level,
        so we don't need user_id/tenant_id parameters here.
        """
        # Existing retrieval logic stays the same
        # Auth scope already enforced by backend during init
        # ...


# Factory method update
class DualRetriever:
    @classmethod
    def load(
        cls,
        data_dir: Path = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> "DualRetriever":
        """
        Load retriever from backend.

        Args:
            data_dir: Data directory (for FileBackend)
            user_id: User context for filtering
            tenant_id: Tenant context for filtering
        """
        from config import get_config
        from memory_backend import get_backend

        config = get_config()
        backend = get_backend(config)

        # Create retrievers using backend
        process_retriever = ProcessMemoryRetriever(
            backend=backend,
            user_id=user_id,
            tenant_id=tenant_id
        )

        # Similar for episodic retriever...

        return cls(process_retriever, episodic_retriever, ...)
```

## Migration Path

### Phase 5.1: Backend Abstraction (Current)
✅ **Completed:**
- Abstract base class `MemoryBackend`
- `FileBackend` wrapping existing file storage
- Factory function `get_backend(config)`
- Configuration support in `config.yaml`

### Phase 5.2: Integration with Retrieval
**Next step:**
- Update `retrieval.py` to use backend abstraction
- Add `user_id`/`tenant_id` to `DualRetriever.load()`
- Pass auth context through retrieval chain

### Phase 5.3: PostgreSQL Implementation
**Future:**
- Implement `PostgresBackend` methods
- Set up database schema with migrations
- Install pgvector extension
- Create indexes for performance

### Phase 5.4: Testing & Migration
**Future:**
- Test both backends in parallel
- Create data migration script (JSON → Postgres)
- Performance benchmarks
- Rollout strategy

## Security Considerations

### Fail Secure by Default
All backends MUST enforce auth scoping:

```python
# ✅ CORRECT: Fails secure without auth context
nodes = backend.get_nodes(tenant_id="driscoll")  # OK
nodes = backend.get_nodes()                      # Returns [] (fail secure)

# ❌ WRONG: Would leak data across tenants
nodes = backend.get_nodes(tenant_id=None)        # Should return []
```

### Auth Context Priority
1. **Enterprise mode**: `tenant_id` takes priority
2. **Personal mode**: `user_id` used if no `tenant_id`
3. **No context**: Return empty results (fail secure)

### SQL Injection Prevention (PostgresBackend)
When implementing PostgresBackend, ALWAYS use parameterized queries:

```python
# ✅ CORRECT
cursor.execute(
    "SELECT * FROM memory_nodes WHERE tenant_id = %s",
    (tenant_id,)
)

# ❌ WRONG: SQL injection vulnerability
cursor.execute(
    f"SELECT * FROM memory_nodes WHERE tenant_id = '{tenant_id}'"
)
```

## Testing

Run the built-in tests:

```bash
# Test backend abstraction
python memory_backend.py

# Expected output:
# - Test 1: get_nodes without auth returns []
# - Test 2: get_nodes with tenant_id returns filtered nodes
# - Test 3: vector_search returns top-k results
```

Create your own test:

```python
from memory_backend import get_backend
from config import get_config

config = get_config()
backend = get_backend(config)

# Test auth scoping
nodes_no_auth = backend.get_nodes()  # Should be empty
assert len(nodes_no_auth) == 0, "Fail secure check failed"

nodes_with_auth = backend.get_nodes(tenant_id="driscoll")
print(f"Found {len(nodes_with_auth)} nodes for tenant 'driscoll'")
```

## Performance Considerations

### FileBackend
- **Pros**: Simple, no external dependencies, fast for small datasets
- **Cons**: O(N) filtering, loads all data into memory
- **Best for**: Development, testing, small deployments (<100k nodes)

### PostgresBackend (Future)
- **Pros**: O(log N) filtering with indexes, efficient pagination, ACID
- **Cons**: Requires PostgreSQL + pgvector, network latency
- **Best for**: Production, large deployments (>100k nodes), multi-tenant SaaS

## Environment Variables

For PostgreSQL backend, set password in `.env`:

```bash
# .env
POSTGRES_PASSWORD=your_secure_password_here
```

The config loader will automatically substitute `${POSTGRES_PASSWORD}`.

## FAQ

### Q: Do I need to change existing code to use this?
**A:** Not immediately. FileBackend wraps the existing file-based storage, so it's backward compatible. However, you'll need to update code to pass `user_id`/`tenant_id` for proper auth scoping.

### Q: When should I use PostgreSQL backend?
**A:** When you have:
- More than 100k memory nodes
- Multiple tenants with strict isolation requirements
- Need for complex queries and filtering
- High concurrency requirements

### Q: How do I migrate from FileBackend to PostgresBackend?
**A:**
1. Implement PostgresBackend (Phase 5.3)
2. Create migration script to copy data from JSON → PostgreSQL
3. Update `config.yaml` to set `memory.backend: postgres`
4. Restart application

### Q: Can I run both backends simultaneously?
**A:** Yes, for testing/migration purposes you can instantiate both:

```python
file_backend = FileBackend(Path("./data"))
postgres_backend = PostgresBackend(pg_config)

# Compare results
file_nodes = file_backend.get_nodes(tenant_id="driscoll")
pg_nodes = postgres_backend.get_nodes(tenant_id="driscoll")
assert len(file_nodes) == len(pg_nodes), "Data mismatch!"
```

## Next Steps

1. **Review this integration guide**
2. **Test FileBackend** with existing data
3. **Update retrieval.py** to use backend abstraction (Phase 5.2)
4. **Plan PostgreSQL schema** (Phase 5.3)
5. **Implement PostgresBackend** (Phase 5.3)
6. **Create migration tooling** (Phase 5.4)

## References

- `memory_backend.py`: Backend abstraction implementation
- `retrieval.py`: Current retrieval system
- `schemas.py`: MemoryNode and EpisodicMemory definitions
- `config.yaml`: Configuration file
- `MERGE_HANDOFF_PHASES_3_4_5.md`: Phase 5 requirements
