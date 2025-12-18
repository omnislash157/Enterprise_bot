# Claude Chat Starter Prompts
# Copy-paste these into claude_chat.py

## INITIAL ORIENTATION (Run First)
Read SDK_MERGE_HANDOFF.md at the project root to understand the full context. Confirm you understand: 1) What Phases 1-2 accomplished 2) What Phase 3 requires 3) The fail-secure auth scoping requirement. Then run git status to confirm we're on merge/cogtwin-unified branch and python main.py to verify server boots. Report status.

---

## PHASE 3: Auth Scoping (Full Auto)
Execute Phase 3 Auth Scoping from SDK_MERGE_HANDOFF.md. Steps: 1) Add user_id and tenant_id Optional[str] fields to MemoryNode in schemas.py 2) Update CogTwin.think() in cog_twin.py to accept user_id and tenant_id params 3) Modify retrieve() in retrieval.py to filter nodes by scope - return empty results if no scope provided (fail secure) 4) Update websocket_endpoint in main.py to extract and pass auth context 5) Update memory_pipeline.py to stamp new memories with scope. Test python main.py after changes. Report all modifications.

---

## PHASE 4: Extraction Toggle (Full Auto)
Execute Phase 4 Extraction Toggle from SDK_MERGE_HANDOFF.md. Find the upload endpoint in main.py and add a guard that raises HTTPException 403 if cfg('features.extraction_enabled') is false. Verify config.yaml has the extraction_enabled flag. Test by checking the endpoint logic. Report changes.

---

## PHASE 5A: Database Schema
Execute Phase 5 Part A from SDK_MERGE_HANDOFF.md. Create db/migrations/001_memory_tables.sql with pgvector extension, tenants table, users table, memory_nodes table with VECTOR(1024) embedding column, and ivfflat indexes. Save file and confirm path.

---

## PHASE 5B: PostgreSQL Backend
Execute Phase 5 Part B from SDK_MERGE_HANDOFF.md. Create postgres_backend.py with PostgresBackend class using asyncpg. Methods: connect() with pool, get_nodes(user_id, tenant_id), vector_search(embedding, user_id, tenant_id, top_k), insert_node(node). Use register_vector for VECTOR type. Report implementation.

---

## PHASE 5C: Backend Abstraction
Execute Phase 5 Part C from SDK_MERGE_HANDOFF.md. Create memory_backend.py with abstract MemoryBackend base class, FileBackend wrapping existing retrieval.py logic, and get_backend(config) factory. Update cog_twin.py to use the factory. Test with memory.backend: file config. Report changes.

---

## PHASE 6: Cleanup
Execute Phase 6 Cleanup. Archive enterprise_twin.py (add DEPRECATED header, move to archive/ folder). Remove any context_stuffing code paths. Clean unused imports in modified files. Run python main.py to verify everything still works. Report what was cleaned.

---

## UTILITY PROMPTS

### Check Status
Run git status, then python main.py to test server boot. Report current state.

### Scan Architecture
Create WIRING_MAP.md documenting current architecture: entry points, data flow, key modules, config flags. Save and confirm path.

### Run Tests
Find and run any existing tests. If none exist, do a manual smoke test by booting the server and checking key endpoints respond. Report results.

### Commit Phase
Run git add -A and git commit -m "Phase [N]: [description]" for the current phase. Report commit hash.
