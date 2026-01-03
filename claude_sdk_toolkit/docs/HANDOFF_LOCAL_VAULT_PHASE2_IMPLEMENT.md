# HANDOFF: Local Vault Architecture - Phase 2 (Implementation)

## Status: BLOCKED - Waiting for Phase 1 Recon

## Prerequisites

- [ ] Phase 1 `VAULT_PATH_MAP.md` completed
- [ ] Architecture decisions made by human
- [ ] Canonical folder structure approved

---

## Target Architecture

```
Platform Paths:
├── Windows: C:\Users\{user}\AppData\Local\cogzy\
├── macOS:   ~/Library/Application Support/cogzy/
└── Linux:   ~/.local/share/cogzy/

Local Vault Structure (TBD after Phase 1):
~/.cogzy/
├── config.json              # User config, API keys
├── corpus/
│   ├── nodes.json           # Memory nodes
│   └── episodes.json        # Episodic memories
├── vectors/
│   ├── nodes.npy            # Node embeddings
│   └── episodes.npy         # Episode embeddings
├── indexes/
│   ├── faiss.index          # FAISS vector index
│   └── clusters.json        # Cluster assignments
├── cache/
│   └── embeddings/          # Embedding cache
├── traces/                  # Reasoning traces
│   └── *.json
├── sync/
│   ├── manifest.json        # Sync state
│   └── last_sync.json       # Last sync timestamp
└── logs/
    └── cogzy.log            # Local logs
```

---

## Implementation Tasks

### Task 1: Create `LocalVaultService` Class

```python
# core/local_vault.py

class LocalVaultService:
    """
    Local-first storage with B2 sync.
    
    All reads from local.
    All writes to local first, then async sync to B2.
    """
    
    def __init__(self, user_id: str, config: dict):
        self.user_id = user_id
        self.root = self._get_platform_path()
        self.b2_service = B2VaultService(config)  # For sync
        
    def _get_platform_path(self) -> Path:
        """Get platform-specific cogzy folder."""
        # Windows: LOCALAPPDATA
        # macOS: ~/Library/Application Support
        # Linux: ~/.local/share
        ...
    
    # Core operations
    def read_nodes(self) -> List[MemoryNode]: ...
    def write_nodes(self, nodes: List[MemoryNode]): ...
    def read_embeddings(self) -> np.ndarray: ...
    def write_embeddings(self, embeddings: np.ndarray): ...
    
    # Sync operations
    async def sync_to_b2(self): ...
    async def sync_from_b2(self): ...
    async def reset_from_b2(self): ...
    
    # Status
    def get_sync_status(self) -> dict: ...
    def get_node_count(self) -> int: ...
```

### Task 2: Update Pipeline to Write Local First

```python
# In pipeline.py run_pipeline_for_user()

# OLD: Write directly to B2
await vault.upload_bytes(user_id, "corpus/nodes.json", nodes_json.encode())

# NEW: Write local, then sync
local_vault.write_nodes(all_nodes)
local_vault.write_embeddings(all_embeddings)
await local_vault.sync_to_b2()  # Async background
```

### Task 3: Update Retrieval to Read Local

```python
# In retrieval.py

# OLD: Read from data_dir parameter
nodes_file = data_dir / "corpus" / "nodes.json"

# NEW: Read from local vault
local_vault = LocalVaultService(user_id, config)
nodes = local_vault.read_nodes()
embeddings = local_vault.read_embeddings()
```

### Task 4: Add Sync Commands

```python
# CLI or API endpoints

async def cmd_sync(user_id: str):
    """Force sync with B2."""
    vault = LocalVaultService(user_id, config)
    await vault.sync_to_b2()
    
async def cmd_reset(user_id: str):
    """Nuke local, re-pull from B2."""
    vault = LocalVaultService(user_id, config)
    vault.clear_local()
    await vault.sync_from_b2()
    
async def cmd_status(user_id: str):
    """Show sync state."""
    vault = LocalVaultService(user_id, config)
    return vault.get_sync_status()
```

### Task 5: Add API Routes

```python
# In personal_vault_routes.py

@router.post("/sync")
async def force_sync(user: AuthUser = Depends(get_current_user)):
    """Force sync local vault with B2."""
    ...

@router.post("/reset")  
async def reset_vault(user: AuthUser = Depends(get_current_user)):
    """Reset local vault from B2 backup."""
    ...

@router.get("/status")
async def vault_status(user: AuthUser = Depends(get_current_user)):
    """Get vault sync status and stats."""
    ...
```

### Task 6: Startup Sync Check

```python
# In main.py or app startup

@app.on_event("startup")
async def startup_sync_check():
    """Check if local vault needs sync from B2."""
    # For web app: sync on first user request
    # For desktop: sync on app launch
    ...
```

---

## Sync Logic

```python
class SyncEngine:
    """
    Sync rules:
    - WRITE: Local first → async push to B2
    - READ: Always local
    - CONFLICT: B2 wins (timestamp-based)
    - RESET: Nuke local → pull B2
    """
    
    async def sync_to_b2(self):
        """Push local changes to B2."""
        local_manifest = self.read_local_manifest()
        
        # Upload changed files
        for file in local_manifest.changed_files:
            await self.b2.upload(file)
            
        # Update B2 manifest
        await self.b2.upload_manifest(local_manifest)
    
    async def sync_from_b2(self):
        """Pull B2 changes to local."""
        b2_manifest = await self.b2.get_manifest()
        local_manifest = self.read_local_manifest()
        
        if b2_manifest.timestamp > local_manifest.timestamp:
            # B2 is newer, pull everything
            await self.pull_all_from_b2()
        
    def should_sync(self) -> bool:
        """Check if sync needed."""
        local = self.read_local_manifest()
        # Sync if >5 min since last sync or >100 new nodes
        ...
```

---

## Migration Plan

1. **Phase 2a**: Create LocalVaultService (no changes to existing code)
2. **Phase 2b**: Update pipeline to write local + B2
3. **Phase 2c**: Update retrieval to read local
4. **Phase 2d**: Add sync commands/routes
5. **Phase 2e**: Test full flow
6. **Phase 2f**: Deprecate direct B2 reads

---

## Files to Modify

Based on Phase 1 findings, update these files:
- [ ] `pipeline.py` - Write local first
- [ ] `retrieval.py` - Read local
- [ ] `personal_vault_routes.py` - Add sync endpoints
- [ ] `core/vault_service.py` - Refactor for local+B2
- [ ] `main.py` - Startup sync
- [ ] (others TBD from Phase 1)

---

## Testing Checklist

- [ ] Fresh install creates `~/.cogzy/` correctly
- [ ] Pipeline writes to local AND syncs to B2
- [ ] Retrieval reads from local
- [ ] `reset` command nukes local and re-pulls
- [ ] `sync` command forces bidirectional sync
- [ ] Works on Windows, macOS, Linux
- [ ] Handles missing B2 backup gracefully
- [ ] Handles corrupt local files gracefully

---

## Blocked Until

- Phase 1 recon complete
- Human approves folder structure
- Human decides on any naming conflicts
