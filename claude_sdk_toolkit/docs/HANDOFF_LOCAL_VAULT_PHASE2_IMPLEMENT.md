# HANDOFF: Local Vault Architecture - Phase 2 (Implementation)

## Status: READY FOR SDK AGENT

## Prerequisites

- [x] Phase 1 `VAULT_PATH_MAP.md` completed
- [x] Architecture decisions made by human
- [x] Canonical folder structure approved

---

## Architecture Decisions (APPROVED)

1. **DROP LEGACY SUPPORT** - No `memory_nodes/`, `episodic_memories/` fallbacks. Unified `corpus/` only.
2. **SINGLE-USER SIMPLE STRUCTURE** - No `users/{uuid}/` nesting locally. Just `~/.cogzy/corpus/`
3. **B2 KEEPS USER NESTING** - B2 still uses `users/{uuid}/` for multi-device sync
4. **CONFIG APPROVED** - `~/.cogzy/config/` is good

---

## Target Architecture

```
Platform Paths:
├── Windows: C:\Users\{user}\AppData\Local\cogzy\
├── macOS:   ~/Library/Application Support/cogzy/
└── Linux:   ~/.local/share/cogzy/

Local Vault Structure (APPROVED - Single User, No Legacy):
~/.cogzy/
├── corpus/
│   ├── nodes.json           # Memory nodes
│   ├── episodes.json        # Episodic memories
│   └── dedup_index.json     # Deduplication index
├── vectors/
│   ├── nodes.npy            # Node embeddings
│   └── episodes.npy         # Episode embeddings
├── indexes/
│   ├── faiss.index          # FAISS vector index
│   ├── clusters.json        # Cluster assignments
│   └── cluster_schema.json  # Cluster schema
├── cache/
│   └── embeddings/          # Embedding cache
│       └── {hash}.npy
├── sync/
│   ├── manifest.json        # What's been synced
│   └── last_sync.json       # Timestamp + user_id for B2 mapping
├── config/
│   ├── settings.json        # User preferences
│   └── credentials.env      # API keys (gitignored)
└── logs/
    └── cogzy.log            # Local debug logs

B2 Vault Structure (unchanged - keeps user isolation):
b2://bucket/users/{user_uuid}/
├── corpus/
│   ├── nodes.json
│   ├── episodes.json
│   └── dedup_index.json
├── vectors/
│   ├── nodes.npy
│   └── episodes.npy
└── indexes/
    ├── faiss.index
    ├── clusters.json
    └── cluster_schema.json
```

## Sync Mapping

```
LOCAL                          B2
~/.cogzy/corpus/nodes.json  ↔  users/{uuid}/corpus/nodes.json
~/.cogzy/vectors/nodes.npy  ↔  users/{uuid}/vectors/nodes.npy
...etc

The user_id is stored in ~/.cogzy/sync/last_sync.json to map local → B2
```

---

## Implementation Tasks

### Task 1: Create `LocalVaultService` Class

**File:** `core/local_vault.py` (NEW FILE)

```python
"""
Local-first vault storage with B2 sync.

All reads from local ~/.cogzy/
All writes to local first, then async sync to B2.
"""

import os
import json
import platform
from pathlib import Path
from typing import List, Optional
import numpy as np

class LocalVaultService:
    """
    Local-first storage with B2 sync.
    
    Single-user structure (no user_id nesting locally).
    B2 sync uses user_id from sync/last_sync.json.
    """
    
    def __init__(self, user_id: Optional[str] = None, b2_config: Optional[dict] = None):
        self.root = self._get_platform_path()
        self.user_id = user_id  # For B2 sync mapping
        self.b2_service = None
        if b2_config:
            from core.vault_service import VaultService
            self.b2_service = VaultService(b2_config)
        
        # Ensure directories exist
        self._init_directories()
        
    def _get_platform_path(self) -> Path:
        """Get platform-specific cogzy folder."""
        system = platform.system()
        
        if system == "Windows":
            base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            return Path(base) / "cogzy"
        elif system == "Darwin":  # macOS
            return Path.home() / "Library" / "Application Support" / "cogzy"
        else:  # Linux and others
            xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
            return Path(xdg_data) / "cogzy"
    
    def _init_directories(self):
        """Create directory structure if not exists."""
        dirs = [
            self.root / "corpus",
            self.root / "vectors", 
            self.root / "indexes",
            self.root / "cache" / "embeddings",
            self.root / "sync",
            self.root / "config",
            self.root / "logs",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    # === Path Properties ===
    @property
    def corpus_dir(self) -> Path:
        return self.root / "corpus"
    
    @property
    def vectors_dir(self) -> Path:
        return self.root / "vectors"
    
    @property
    def indexes_dir(self) -> Path:
        return self.root / "indexes"
    
    @property
    def cache_dir(self) -> Path:
        return self.root / "cache" / "embeddings"
    
    # === File Paths ===
    def nodes_json(self) -> Path:
        return self.corpus_dir / "nodes.json"
    
    def episodes_json(self) -> Path:
        return self.corpus_dir / "episodes.json"
    
    def dedup_index_json(self) -> Path:
        return self.corpus_dir / "dedup_index.json"
    
    def nodes_npy(self) -> Path:
        return self.vectors_dir / "nodes.npy"
    
    def episodes_npy(self) -> Path:
        return self.vectors_dir / "episodes.npy"
    
    def faiss_index(self) -> Path:
        return self.indexes_dir / "faiss.index"
    
    def clusters_json(self) -> Path:
        return self.indexes_dir / "clusters.json"
    
    # === Core Read Operations ===
    def read_nodes(self) -> List[dict]:
        """Read memory nodes from local."""
        path = self.nodes_json()
        if not path.exists():
            return []
        with open(path) as f:
            return json.load(f)
    
    def read_episodes(self) -> List[dict]:
        """Read episodes from local."""
        path = self.episodes_json()
        if not path.exists():
            return []
        with open(path) as f:
            return json.load(f)
    
    def read_node_embeddings(self) -> Optional[np.ndarray]:
        """Read node embeddings from local."""
        path = self.nodes_npy()
        if not path.exists():
            return None
        return np.load(path)
    
    def read_episode_embeddings(self) -> Optional[np.ndarray]:
        """Read episode embeddings from local."""
        path = self.episodes_npy()
        if not path.exists():
            return None
        return np.load(path)
    
    # === Core Write Operations ===
    def write_nodes(self, nodes: List[dict], sync: bool = True):
        """Write nodes to local, optionally sync to B2."""
        with open(self.nodes_json(), 'w') as f:
            json.dump(nodes, f, default=str)
        if sync:
            self._queue_sync("corpus/nodes.json")
    
    def write_episodes(self, episodes: List[dict], sync: bool = True):
        """Write episodes to local, optionally sync to B2."""
        with open(self.episodes_json(), 'w') as f:
            json.dump(episodes, f, default=str)
        if sync:
            self._queue_sync("corpus/episodes.json")
    
    def write_node_embeddings(self, embeddings: np.ndarray, sync: bool = True):
        """Write node embeddings to local, optionally sync to B2."""
        np.save(self.nodes_npy(), embeddings)
        if sync:
            self._queue_sync("vectors/nodes.npy")
    
    def write_episode_embeddings(self, embeddings: np.ndarray, sync: bool = True):
        """Write episode embeddings to local, optionally sync to B2."""
        np.save(self.episodes_npy(), embeddings)
        if sync:
            self._queue_sync("vectors/episodes.npy")
    
    # === Sync Operations ===
    def _queue_sync(self, relative_path: str):
        """Queue a file for B2 sync (async background)."""
        # TODO: Implement background sync queue
        pass
    
    async def sync_to_b2(self):
        """Push all local changes to B2."""
        if not self.b2_service or not self.user_id:
            return
        
        # Upload each file type
        files_to_sync = [
            (self.nodes_json(), f"users/{self.user_id}/corpus/nodes.json"),
            (self.episodes_json(), f"users/{self.user_id}/corpus/episodes.json"),
            (self.nodes_npy(), f"users/{self.user_id}/vectors/nodes.npy"),
            (self.episodes_npy(), f"users/{self.user_id}/vectors/episodes.npy"),
            (self.clusters_json(), f"users/{self.user_id}/indexes/clusters.json"),
        ]
        
        for local_path, b2_path in files_to_sync:
            if local_path.exists():
                with open(local_path, 'rb') as f:
                    await self.b2_service.upload_bytes(b2_path, f.read())
        
        self._update_sync_timestamp()
    
    async def sync_from_b2(self):
        """Pull all data from B2 to local."""
        if not self.b2_service or not self.user_id:
            return
        
        files_to_pull = [
            (f"users/{self.user_id}/corpus/nodes.json", self.nodes_json()),
            (f"users/{self.user_id}/corpus/episodes.json", self.episodes_json()),
            (f"users/{self.user_id}/vectors/nodes.npy", self.nodes_npy()),
            (f"users/{self.user_id}/vectors/episodes.npy", self.episodes_npy()),
            (f"users/{self.user_id}/indexes/clusters.json", self.clusters_json()),
        ]
        
        for b2_path, local_path in files_to_pull:
            try:
                content = await self.b2_service.download_file(b2_path)
                with open(local_path, 'wb') as f:
                    f.write(content if isinstance(content, bytes) else content.encode())
            except Exception:
                pass  # File doesn't exist in B2 yet
        
        self._update_sync_timestamp()
    
    async def reset_from_b2(self):
        """Nuke local and re-pull everything from B2."""
        import shutil
        
        # Clear local data (keep config)
        for subdir in ["corpus", "vectors", "indexes", "cache"]:
            path = self.root / subdir
            if path.exists():
                shutil.rmtree(path)
        
        # Re-init directories
        self._init_directories()
        
        # Pull from B2
        await self.sync_from_b2()
    
    def _update_sync_timestamp(self):
        """Update last sync timestamp."""
        import datetime
        sync_file = self.root / "sync" / "last_sync.json"
        with open(sync_file, 'w') as f:
            json.dump({
                "user_id": self.user_id,
                "last_sync": datetime.datetime.utcnow().isoformat(),
            }, f)
    
    # === Status ===
    def get_status(self) -> dict:
        """Get vault status and stats."""
        nodes = self.read_nodes()
        episodes = self.read_episodes()
        
        sync_file = self.root / "sync" / "last_sync.json"
        last_sync = None
        if sync_file.exists():
            with open(sync_file) as f:
                last_sync = json.load(f)
        
        return {
            "root": str(self.root),
            "node_count": len(nodes),
            "episode_count": len(episodes),
            "last_sync": last_sync,
            "has_embeddings": self.nodes_npy().exists(),
            "has_faiss": self.faiss_index().exists(),
        }
    
    def clear_local(self):
        """Clear all local data (for reset)."""
        import shutil
        for subdir in ["corpus", "vectors", "indexes", "cache"]:
            path = self.root / subdir
            if path.exists():
                shutil.rmtree(path)
        self._init_directories()
```

### Task 2: Update Pipeline to Write Local First

**File:** `pipeline.py`

Find the `run_pipeline_for_user()` function (around line 930) and update:

```python
# OLD CODE (around line 1048):
await vault.upload_bytes(user_id, "corpus/nodes.json", nodes_json.encode())

# NEW CODE:
from core.local_vault import LocalVaultService

# Create local vault
local_vault = LocalVaultService(user_id=user_id, b2_config=config)

# Write to local first
local_vault.write_nodes([n.to_dict() for n in all_nodes], sync=False)
local_vault.write_node_embeddings(all_embeddings, sync=False)

# Sync to B2 in background
await local_vault.sync_to_b2()
```

**IMPORTANT:** Remove ALL legacy `memory_nodes/` and `episodic_memories/` directory creation and writes.

### Task 3: Update Retrieval to Read Local

**File:** `retrieval.py`

Find `_load_unified_v2()` method (around line 465) and update:

```python
# OLD CODE:
def _load_unified_v2(self, data_dir: Path) -> Tuple[...]:
    nodes_file = data_dir / "corpus" / "nodes.json"
    with open(nodes_file) as f:
        nodes_data = json.load(f)

# NEW CODE:
def _load_unified_v2(self, data_dir: Path = None) -> Tuple[...]:
    from core.local_vault import LocalVaultService
    
    # Use local vault instead of arbitrary data_dir
    local_vault = LocalVaultService()
    
    nodes_data = local_vault.read_nodes()
    nodes = [MemoryNode.from_dict(d) for d in nodes_data]
    
    episodes_data = local_vault.read_episodes()
    episodes = [EpisodicMemory.from_dict(d) for d in episodes_data]
    
    node_embeddings = local_vault.read_node_embeddings()
    episode_embeddings = local_vault.read_episode_embeddings()
    
    # ... rest of method
```

**IMPORTANT:** Remove ALL legacy fallback paths (`memory_nodes/`, etc.)

### Task 4: Add Sync API Routes

**File:** `personal_vault_routes.py`

Add new endpoints:

```python
from core.local_vault import LocalVaultService

@router.post("/vault/sync")
async def force_sync(user: AuthUser = Depends(get_current_user)):
    """Force sync local vault with B2."""
    local_vault = LocalVaultService(user_id=str(user.id), b2_config=get_config())
    await local_vault.sync_to_b2()
    return {"status": "synced", "stats": local_vault.get_status()}

@router.post("/vault/reset")
async def reset_vault(user: AuthUser = Depends(get_current_user)):
    """Reset local vault from B2 backup."""
    local_vault = LocalVaultService(user_id=str(user.id), b2_config=get_config())
    await local_vault.reset_from_b2()
    return {"status": "reset", "stats": local_vault.get_status()}

@router.get("/vault/local-status")
async def local_vault_status(user: AuthUser = Depends(get_current_user)):
    """Get local vault status and stats."""
    local_vault = LocalVaultService(user_id=str(user.id))
    return local_vault.get_status()
```

### Task 5: Update Startup to Check Sync

**File:** `main.py` or app startup

```python
from core.local_vault import LocalVaultService

@app.on_event("startup")
async def startup_sync_check():
    """Initialize local vault on startup."""
    # Just ensure directories exist
    # Actual sync happens on first authenticated request
    LocalVaultService()  # Creates ~/.cogzy/ structure
```

### Task 6: Remove Legacy Support

**Files to clean:** `pipeline.py`, `retrieval.py`, `dedup.py`, `cluster_schema.py`

Search and remove ALL references to:
- `memory_nodes/` directory
- `episodic_memories/` directory
- Legacy manifest format checks
- Fallback loading logic for old structure

Use these grep patterns:
```bash
grep -rn "memory_nodes\|episodic_memories\|legacy\|fallback" *.py
```

---

## Migration Plan

1. **Phase 2a**: Create `core/local_vault.py` (new file, no changes to existing code)
2. **Phase 2b**: Update `pipeline.py` to write local + sync B2
3. **Phase 2c**: Update `retrieval.py` to read local only
4. **Phase 2d**: Add sync routes to `personal_vault_routes.py`
5. **Phase 2e**: Remove ALL legacy path support
6. **Phase 2f**: Test full flow end-to-end

---

## Files to Modify

### NEW FILES
- [ ] `core/local_vault.py` - New LocalVaultService class

### MODIFY
- [ ] `pipeline.py` - Write local first, remove legacy dirs
- [ ] `retrieval.py` - Read from LocalVaultService, remove legacy fallbacks
- [ ] `personal_vault_routes.py` - Add /vault/sync, /vault/reset, /vault/local-status
- [ ] `main.py` - Add startup directory init
- [ ] `dedup.py` - Remove legacy path references
- [ ] `cluster_schema.py` - Remove legacy path references
- [ ] `embedder.py` - Update cache_dir to use LocalVaultService.cache_dir

### REMOVE/CLEAN
- All `memory_nodes/` references
- All `episodic_memories/` references
- All legacy manifest fallback logic
- Any hardcoded `./data` paths

---

## Testing Checklist

- [ ] Fresh install creates `~/.cogzy/` with correct structure
- [ ] Platform detection works (Windows/Mac/Linux paths)
- [ ] Pipeline writes to local `~/.cogzy/corpus/nodes.json`
- [ ] Pipeline syncs to B2 `users/{uuid}/corpus/nodes.json`
- [ ] Retrieval reads from local `~/.cogzy/`
- [ ] `/vault/sync` endpoint pushes to B2
- [ ] `/vault/reset` endpoint nukes local and re-pulls
- [ ] `/vault/local-status` returns correct stats
- [ ] Embedding cache works at `~/.cogzy/cache/embeddings/`
- [ ] No legacy paths created anywhere
- [ ] Handles missing B2 backup gracefully (new user)
- [ ] Handles corrupt local files gracefully

---

## Success Criteria

- [ ] All reads happen from `~/.cogzy/` (local)
- [ ] All writes go to local first, then sync to B2
- [ ] No more `./data` relative paths
- [ ] No more legacy `memory_nodes/` or `episodic_memories/`
- [ ] User can `reset` to recover from B2
- [ ] Multi-device works via B2 sync

---

## Notes for SDK Agent

1. **Create `core/local_vault.py` FIRST** - This is standalone, won't break anything
2. **Test LocalVaultService in isolation** before touching pipeline/retrieval
3. **Grep aggressively** for legacy paths - kill them all
4. **Platform testing** - If possible test Windows paths work (even if running on Linux)
5. **Don't forget `dedup_index.json`** - It's part of corpus, needs to sync too

---

## Deliverables

1. `core/local_vault.py` - Complete LocalVaultService implementation
2. Updated `pipeline.py` - Local-first writes
3. Updated `retrieval.py` - Local-only reads
4. Updated `personal_vault_routes.py` - New sync endpoints
5. Cleaned codebase - No legacy paths
6. Test report - All checklist items verified