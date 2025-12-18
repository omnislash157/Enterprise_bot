# Memory Backend Quick Start Guide

## TL;DR

Phase 5.1 adds pluggable storage backends for memory nodes. Switch between file-based and PostgreSQL storage via config.

## 5-Minute Setup

### 1. Import and Initialize

```python
from memory_backend import get_backend
from config import get_config

backend = get_backend(get_config())
```

### 2. Get Nodes (with auth)

```python
# Enterprise mode (tenant isolation)
nodes = backend.get_nodes(tenant_id="driscoll")

# Personal mode (user isolation)
nodes = backend.get_nodes(user_id="user123")

# No auth = empty results (fail secure)
nodes = backend.get_nodes()  # Returns []
```

### 3. Vector Search

```python
import numpy as np

# Get query embedding (from embedder)
query_emb = np.array([...])  # 1024-dim vector

# Search with auth scoping
results, scores = backend.vector_search(
    query_emb,
    tenant_id="driscoll",
    top_k=10,
    min_score=0.3
)

for node, score in zip(results, scores):
    print(f"[{score:.3f}] {node.human_content[:80]}...")
```

### 4. Insert Node

```python
from schemas import MemoryNode, Source
from datetime import datetime

node = MemoryNode(
    id="node_123",
    conversation_id="conv_456",
    sequence_index=0,
    human_content="Question here",
    assistant_content="Answer here",
    source=Source.ANTHROPIC,
    created_at=datetime.now(),
    tenant_id="driscoll"  # Important for auth scoping!
)

backend.insert_node(node)
```

## Configuration

In `config.yaml`:

```yaml
memory:
  backend: file  # or "postgres" (future)

  postgres:  # Only if backend = "postgres"
    host: localhost
    port: 5432
    database: enterprise_bot
    user: postgres
    password: ${POSTGRES_PASSWORD}
```

## Backend Comparison

| Feature | FileBackend | PostgresBackend |
|---------|-------------|-----------------|
| Status | ✅ Implemented | 🚧 Future |
| Setup | None | PostgreSQL + pgvector |
| Scale | <100k nodes | Unlimited |
| Speed | Fast (in-memory) | Network latency |
| Transactions | No | Yes (ACID) |
| Concurrent writes | No | Yes |

## Key Security Features

### Fail Secure by Default
```python
# ✅ SAFE: Explicit auth context
nodes = backend.get_nodes(tenant_id="driscoll")

# ✅ SAFE: Returns [] (no data leak)
nodes = backend.get_nodes()

# ❌ NEVER: Don't trust user input without validation
tenant_id = request.headers.get("X-Tenant-Id")  # DON'T DO THIS
nodes = backend.get_nodes(tenant_id=tenant_id)  # Vulnerable!
```

### Filter Before Search
Auth filtering happens BEFORE similarity computation to prevent timing attacks.

## API Reference

### MemoryBackend (Abstract Base Class)

```python
class MemoryBackend(ABC):
    def get_nodes(
        user_id: str = None,
        tenant_id: str = None,
        limit: int = None,
        offset: int = 0
    ) -> List[MemoryNode]

    def vector_search(
        query_embedding: np.ndarray,
        user_id: str = None,
        tenant_id: str = None,
        top_k: int = 10,
        min_score: float = 0.0
    ) -> Tuple[List[MemoryNode], List[float]]

    def insert_node(node: MemoryNode) -> None

    def get_embeddings(
        user_id: str = None,
        tenant_id: str = None
    ) -> np.ndarray

    def get_cluster_info() -> Dict[int, List[int]]
```

## Testing

```bash
# Run built-in tests
python memory_backend.py

# Expected output:
# - FileBackend initialized
# - Fail-secure tests pass
# - Auth-scoped retrieval works
# - All tests pass ✅
```

## Common Patterns

### Pattern 1: Tenant-Scoped Retrieval
```python
def get_tenant_memories(tenant_id: str, query: str, embedder):
    backend = get_backend(get_config())
    query_emb = embedder.embed(query)
    return backend.vector_search(
        query_emb,
        tenant_id=tenant_id,
        top_k=5
    )
```

### Pattern 2: Pagination
```python
def get_all_tenant_nodes(tenant_id: str, page_size: int = 100):
    backend = get_backend(get_config())
    offset = 0
    while True:
        nodes = backend.get_nodes(
            tenant_id=tenant_id,
            limit=page_size,
            offset=offset
        )
        if not nodes:
            break
        yield nodes
        offset += page_size
```

### Pattern 3: Multi-Tenant Search
```python
def search_all_tenants(query_emb: np.ndarray, tenant_ids: List[str]):
    backend = get_backend(get_config())
    all_results = {}
    for tid in tenant_ids:
        results, scores = backend.vector_search(
            query_emb,
            tenant_id=tid,
            top_k=5
        )
        all_results[tid] = list(zip(results, scores))
    return all_results
```

## Troubleshooting

### Problem: Empty results even with valid tenant_id
**Solution:** Check if nodes.json has data and nodes have tenant_id set:
```python
backend = FileBackend(Path("./data"))
nodes = backend._load_nodes()  # Load without filtering
print(f"Total nodes: {len(nodes)}")
print(f"First node tenant_id: {nodes[0].tenant_id if nodes else 'N/A'}")
```

### Problem: "No such file or directory: nodes.json"
**Solution:** Initialize data directory:
```bash
python init_empty_data.py
```

### Problem: NotImplementedError when using PostgreSQL
**Solution:** PostgresBackend not yet implemented. Use FileBackend for now:
```yaml
memory:
  backend: file  # Change from "postgres"
```

## Migration Path

### Current: Phase 5.1 ✅
- Abstract base class
- FileBackend implemented
- Configuration support

### Next: Phase 5.2 (Integration)
- Update retrieval.py
- Pass auth context through system
- Add tenant_id to DualRetriever.load()

### Future: Phase 5.3 (PostgreSQL)
- Implement PostgresBackend
- Database schema setup
- Migration tooling

### Future: Phase 5.4 (Testing)
- Performance benchmarks
- Load testing
- Production rollout

## Files Reference

- `memory_backend.py` - Core implementation
- `MEMORY_BACKEND_INTEGRATION.md` - Detailed integration guide
- `PHASE_5_MEMORY_BACKEND_SUMMARY.md` - Implementation summary
- `config.yaml` - Configuration file

## Quick Links

```python
# Import everything you need
from memory_backend import get_backend, MemoryBackend, FileBackend
from config import get_config
from schemas import MemoryNode, Source

# Initialize
backend = get_backend(get_config())

# Use it
nodes = backend.get_nodes(tenant_id="driscoll")
```

---

**That's it!** You now have pluggable memory storage. 🚀

For more details, see `MEMORY_BACKEND_INTEGRATION.md`.
