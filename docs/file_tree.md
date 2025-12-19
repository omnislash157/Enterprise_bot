# Enterprise Bot - File Tree

**Last Updated:** 2025-12-18
**Repo:** enterprise_bot
**Deploy:** Railway (Azure PostgreSQL for auth, SQL Server for Driscoll data)
**Status:** DOCX Chunking + Schema Enhancement + RLS Complete ✅ (60% of Master Execution Plan)

---

## Recent Changes (Master Execution Plan)

### ✅ Phase 2.5: DOCX Chunking Pipeline (Commit: `a4bb32d`)
- `ingestion/docx_to_json_chunks.py` - Core chunker with heading-based sections
- `ingestion/batch_convert_warehouse_docx.py` - Parallel batch conversion (4 workers)
- **21 Warehouse DOCX → 21 JSON chunk files** (169 total chunks)

### ✅ Phase 1: Schema Enhancement (Commit: `6c54b23`)
- `db/migrations/002_enhance_department_content.sql` - Full schema for vector RAG
- `db/run_migration_002.py` - Migration runner with verification
- `db/install_pgvector.py` - pgvector extension installer

### ✅ Phase 2: RLS Policies (Commit: `d24c959`)
- `db/migrations/003_enable_rls_policies.sql` - Row Level Security implementation

### ⏳ Phase 3: Ingestion Pipeline (NEXT)
### ⏳ Phase 4: CogTwin Integration (PENDING)
### ⏳ Phase 5: Schema Lock Docs (PENDING)

---

## Project Structure

```
enterprise_bot/
├── .claude/
│   └── settings.local.json
│
├── .vscode/
│   └── settings.json
│
├── ============ CONFIGURATION ============
│
├── Config (Root)
│   ├── .env
│   ├── .env.azure-template
│   ├── .env.example
│   ├── .gitignore
│   ├── config.yaml              # App config (tier=basic, features OFF, model=grok)
│   ├── email_whitelist.json     # Allowed domains/emails
│   ├── requirements.txt         # Python dependencies
│   ├── runtime.txt              # Python version for Railway
│   ├── Procfile                 # Railway start command
│   ├── pyproject.toml           # Python project metadata (v0.1.0)
│   └── activate.ps1             # PowerShell activation script
│
├── ============ DOCUMENTATION ============
│
├── docs/
│   ├── file_tree.md                       # This file - Complete project structure
│   │
│   ├── Setup & Deployment
│   │   ├── AZURE_SSO_README.md            # Azure AD SSO setup guide
│   │   └── RAILWAY_SPEC_SHEET.md          # Railway deployment guide
│   │
│   ├── Merge Documentation
│   │   ├── SDK_MERGE_HANDOFF.md           # Phases 1-2 handoff doc
│   │   ├── MERGE_HANDOFF_PHASES_3_4_5.md  # Phases 3-5 handoff doc
│   │   └── PHASES_3_4_5_COMPLETE.md       # Complete phase summary
│   │
│   ├── Phase 5 - PostgreSQL Migration
│   │   ├── PHASE_5_SUMMARY.md             # PostgreSQL migration overview
│   │   ├── PHASE_5_MEMORY_BACKEND_SUMMARY.md
│   │   ├── MEMORY_BACKEND_INTEGRATION.md
│   │   ├── MEMORY_BACKEND_QUICKSTART.md
│   │   ├── MIGRATION_GUIDE.md
│   │   └── QUICK_START_MIGRATION.md
│   │
│   ├── Master Execution Plan (NEW)
│   │   ├── MASTER_EXECUTION_PLAN.md       # Full execution roadmap
│   │   ├── PHASE_1_EXECUTION.md           # Schema enhancement log
│   │   ├── PHASE_2_EXECUTION.md           # RLS policies log
│   │   ├── PHASE_2_5_EXECUTION.md         # DOCX chunking log
│   │   ├── PHASES_2.5_1_2_COMPLETE.md     # Completion summary
│   │   └── PROCESS_MANUAL_SCHEMA_LOCK_PLAN.md  # Schema lock strategy
│   │
│   ├── Architecture
│   │   ├── WIRING_MAP.md                  # Complete system architecture
│   │   └── CLAUDE_CHAT_PROMPTS.md         # Claude chat system prompts
│   │
│   └── README.md (in root)
│
├── ============ SDK AGENT CLI ============
│
├── SDK Agent Tools (NEW)
│   ├── claude_chat.py               # Interactive REPL for Claude SDK
│   │   ├── /db commands             # PostgreSQL query/export
│   │   ├── /skill commands          # Lazy-load skill docs
│   │   ├── /paste, /batch           # Bulk input modes
│   │   └── /timeout                 # Input timeout control
│   ├── claude_run.py                # One-shot prompt executor
│   └── db_tools.py                  # PostgreSQL tools (query, describe, CSV)
│
├── skills/                          # Lazy-loaded skill documentation
│   ├── SKILLS_INDEX.md              # Skills master index (~50 tokens)
│   ├── db.skill.md                  # Database operations skill
│   ├── etl.skill.md                 # ETL pipeline skill
│   ├── excel.skill.md               # Excel export skill
│   ├── powerbi.skill.md             # Power BI integration skill
│   ├── profile.skill.md             # Data profiling skill
│   └── schema.skill.md              # Schema navigation skill
│
├── ============ INGESTION PIPELINE (NEW) ============
│
├── ingestion/                       # Document ingestion pipeline
│   ├── __init__.py
│   ├── docx_to_json_chunks.py       # DOCX → JSON chunker (370 lines)
│   │   ├── Heading-based section splitting
│   │   ├── 500 token limit per chunk
│   │   ├── Automatic keyword extraction
│   │   └── SHA256 file hashing for dedup
│   └── batch_convert_warehouse_docx.py  # Parallel batch (4 workers)
│
├── ============ DATABASE MIGRATIONS ============
│
├── db/
│   ├── migrations/
│   │   ├── 001_memory_tables.sql              # Session/episodic memory
│   │   ├── 002_enhance_department_content.sql # Vector RAG schema (380 lines)
│   │   │   ├── 14 new columns (tenant_id, embedding, chunk hierarchy)
│   │   │   ├── 15 indexes (IVFFlat for vector search)
│   │   │   ├── 5 validation constraints
│   │   │   └── 3 utility functions
│   │   └── 003_enable_rls_policies.sql        # Row Level Security (540 lines)
│   │       ├── SELECT: tenant + dept scoped
│   │       ├── INSERT: super users + dept heads
│   │       ├── UPDATE: super users + write access
│   │       ├── DELETE: super users ONLY
│   │       └── Helper functions: set/clear/get_user_context()
│   │
│   ├── run_migration_002.py         # Migration runner with verification
│   ├── install_pgvector.py          # pgvector extension installer
│   ├── supabase_3tier_complete.sql  # OLD - Reference only
│   └── supabase_auth_setup.sql      # OLD - Reference only
│
├── migrations/                      # Legacy migrations folder
│   ├── add_analytics_indexes.sql
│   ├── add_azure_oid.sql
│   └── verify_azure_oid.sql
│
├── ============ ACTIVE BACKEND ============
│
├── Core Backend
│   ├── main.py                      # FastAPI app entry point (WebSocket streaming)
│   ├── config.py                    # Settings class
│   ├── config_loader.py             # YAML config loader, cfg() helper
│   ├── schemas.py                   # Pydantic models (MemoryNode, EpisodicMemory)
│   ├── model_adapter.py             # LLM client factory (Grok/Claude)
│   └── enterprise_tenant.py         # TenantContext dataclass
│
├── Auth & Admin
│   ├── auth_schema.py               # DB schema setup for auth tables
│   ├── auth_service.py              # User CRUD, permissions, audit logging
│   ├── admin_routes.py              # FastAPI router for admin portal
│   ├── azure_auth.py                # Azure AD SSO token validation
│   ├── sso_routes.py                # SSO OAuth callback endpoints
│   └── tenant_service.py            # Department content loading
│
├── Analytics Engine
│   ├── analytics_service.py         # Query logging, classification
│   └── analytics_routes.py          # Dashboard API endpoints
│
├── ============ COGTWIN ENGINE ============
│
├── CogTwin Core
│   ├── cog_twin.py                  # Main cognitive engine (vector/hybrid search)
│   ├── venom_voice.py               # Venom personality system prompt
│   └── enterprise_voice.py          # Enterprise personality
│
├── Enterprise Mode (Legacy)
│   ├── chat_parser_agnostic.py      # Response parsing
│   └── doc_loader.py                # Document loading (DOCX caching)
│
├── ============ MEMORY SYSTEM ============
│
├── Memory Backend Abstraction
│   ├── memory_backend.py            # Abstract base + FileBackend
│   ├── postgres_backend.py          # PostgreSQL + pgvector backend
│   └── migrate_to_postgres.py       # Migration script
│
├── Memory Pipeline
│   ├── chat_memory.py               # Memory management
│   ├── memory_pipeline.py           # Embedding pipeline (DORMANT in basic tier)
│   ├── memory_grep.py               # Memory search
│   ├── reasoning_trace.py           # Trace logging (OFF)
│   ├── read_traces.py               # Trace reader
│   └── streaming_cluster.py         # Cluster streaming
│
├── Search & Retrieval
│   ├── retrieval.py                 # Vector retrieval with auth filtering
│   ├── scoring.py                   # Relevance scoring
│   ├── hybrid_search.py             # Hybrid vector+keyword
│   ├── fast_filter.py               # Fast filtering
│   ├── heuristic_enricher.py        # Result enrichment
│   ├── embedder.py                  # Embedding generation
│   └── embedding_model.py           # BGE-M3 model wrapper
│
├── Metacognitive System (ALL OFF in basic tier)
│   ├── metacognitive_mirror.py      # Cognitive state monitoring
│   ├── evolution_engine.py          # Learning and adaptation
│   ├── llm_tagger.py                # Auto-tagging
│   └── cluster_schema.py            # Cluster profiling
│
├── ============ DOCUMENT PROCESSING ============
│
├── Document Processing
│   ├── ingest.py                    # Ingestion orchestrator
│   ├── dedup.py                     # Deduplication logic
│   └── upload_manuals.py            # Manual uploader
│
├── ============ DATA ============
│
├── data/
│   ├── memory_index.json
│   ├── manifest.json
│   ├── corpus/
│   │   ├── nodes.json               # Memory nodes
│   │   ├── episodes.json            # Episodic memories
│   │   └── dedup_index.json
│   ├── vectors/
│   │   ├── nodes.npy                # Node embeddings (1024-dim BGE-M3)
│   │   └── episodes.npy
│   └── indexes/
│       └── clusters.json
│
├── ============ MANUALS (Driscoll) ============
│
├── Manuals/Driscoll/
│   ├── Warehouse/
│   │   ├── chunks/                          # JSON chunk files (21 files)
│   │   │   ├── dispatching_manual_chunks.json
│   │   │   ├── driver_check-in_manual_chunks.json
│   │   │   ├── driver_manual_chunks.json
│   │   │   ├── hr_manual_chunks.json
│   │   │   ├── inventory_control_manual_chunks.json
│   │   │   ├── invoice_cleaning_department_manual_chunks.json
│   │   │   ├── john_cantelli_manual_chunks.json
│   │   │   ├── night_shift_checking_manual_chunks.json
│   │   │   ├── night_shift_clerk_manual_chunks.json
│   │   │   ├── night_shift_hi-lo_operating_manual_chunks.json
│   │   │   ├── night_shift_loading_manual_chunks.json
│   │   │   ├── night_shift_picking_manual_chunks.json
│   │   │   ├── night_shift_supervisor_manual_chunks.json
│   │   │   ├── night_shift_switcher_manual_chunks.json
│   │   │   ├── ops_admin_manual_(made_by_matt_fava)_chunks.json
│   │   │   ├── putaway_manual_chunks.json
│   │   │   ├── receiving_manual_chunks.json
│   │   │   ├── replen_manual_chunks.json
│   │   │   ├── routing_manual_chunks.json
│   │   │   ├── transportation_manual_chunks.json
│   │   │   └── upc_collecting_manual_chunks.json
│   │   │
│   │   └── (23 original DOCX files)
│   │
│   ├── Sales/
│   │   ├── bid_management_chunks.json
│   │   ├── sales_support_chunks.json
│   │   └── telnet_sop_chunks.json
│   │
│   └── Purchasing/
│       └── purchasing_manual_chunks.json
│
│   TOTAL: 25 JSON chunk files, 169 chunks across 3 departments
│
├── ============ TESTING & UTILITIES ============
│
├── Testing
│   ├── debug_pipeline.py
│   ├── test_setup.py
│   ├── test_integration_quick.py
│   ├── verify_chat_integration.py
│   ├── test_azure_sso.sh
│   └── init_empty_data.py
│
├── Utilities
│   ├── squirrel.py                  # Temporal recall tool
│   ├── init_sandbox.py
│   ├── sdk_recon.py
│   ├── generate_test_user.py
│   └── db_diagnostic.py
│
├── ============ ARCHIVE ============
│
├── archive/deprecated/
│   └── enterprise_twin.py.bak       # Old enterprise twin
│
├── ============ FRONTEND ============
│
└── frontend/
    ├── Config
    │   ├── package.json
    │   ├── package-lock.json
    │   ├── tsconfig.json
    │   ├── vite.config.ts
    │   ├── svelte.config.js
    │   ├── postcss.config.js
    │   └── tailwind.config.js
    │
    └── src/
        ├── app.html
        ├── app.css
        │
        ├── lib/
        │   ├── artifacts/
        │   │   └── registry.ts
        │   │
        │   ├── utils/
        │   │   ├── csvExport.ts
        │   │   └── clickOutside.ts
        │   │
        │   ├── transitions/
        │   │   └── pageTransition.ts
        │   │
        │   ├── components/
        │   │   ├── ChatOverlay.svelte
        │   │   ├── Login.svelte
        │   │   ├── DepartmentSelector.svelte
        │   │   ├── CreditForm.svelte
        │   │   ├── DupeOverrideModal.svelte
        │   │   ├── CheekyLoader.svelte
        │   │   ├── CheekyInline.svelte
        │   │   ├── CheekyToast.svelte
        │   │   ├── ToastProvider.svelte
        │   │   │
        │   │   ├── ribbon/
        │   │   │   ├── index.ts
        │   │   │   ├── IntelligenceRibbon.svelte
        │   │   │   ├── NavLink.svelte
        │   │   │   ├── AdminDropdown.svelte
        │   │   │   └── UserMenu.svelte
        │   │   │
        │   │   ├── admin/
        │   │   │   ├── UserRow.svelte
        │   │   │   ├── AccessModal.svelte
        │   │   │   ├── RoleModal.svelte
        │   │   │   ├── CreateUserModal.svelte
        │   │   │   ├── BatchImportModal.svelte
        │   │   │   ├── LoadingSkeleton.svelte
        │   │   │   │
        │   │   │   ├── charts/
        │   │   │   │   ├── chartTheme.ts
        │   │   │   │   ├── StatCard.svelte
        │   │   │   │   ├── LineChart.svelte
        │   │   │   │   ├── DoughnutChart.svelte
        │   │   │   │   ├── BarChart.svelte
        │   │   │   │   ├── RealtimeSessions.svelte
        │   │   │   │   ├── NerveCenterWidget.svelte
        │   │   │   │   ├── DateRangePicker.svelte
        │   │   │   │   └── ExportButton.svelte
        │   │   │   │
        │   │   │   └── threlte/
        │   │   │       ├── NeuralNode.svelte
        │   │   │       ├── DataSynapse.svelte
        │   │   │       ├── NeuralNetwork.svelte
        │   │   │       └── NerveCenterScene.svelte
        │   │   │
        │   │   ├── nervecenter/
        │   │   │   └── StateMonitor.svelte      # Debug panel (Phase 0)
        │   │   │
        │   │   └── archive/
        │   │       ├── AnalyticsDashboard.svelte
        │   │       ├── ArtifactPane.svelte
        │   │       ├── FloatingPanel.svelte
        │   │       └── WorkspaceNav.svelte
        │   │
        │   ├── cheeky/
        │   │   ├── index.ts
        │   │   ├── CheekyStatus.ts
        │   │   └── phrases.ts
        │   │
        │   ├── stores/
        │   │   ├── index.ts
        │   │   ├── auth.ts
        │   │   ├── admin.ts
        │   │   ├── analytics.ts
        │   │   ├── credit.ts
        │   │   ├── cheeky.ts
        │   │   ├── websocket.ts
        │   │   ├── session.ts
        │   │   ├── config.ts
        │   │   ├── theme.ts
        │   │   ├── artifacts.ts
        │   │   ├── panels.ts
        │   │   └── workspaces.ts
        │   │
        │   └── threlte/
        │       ├── CoreBrain.svelte
        │       ├── Scene.svelte
        │       ├── CreditAmbientOrbs.svelte
        │       └── archive/
        │           ├── AgentNode.svelte
        │           ├── ConnectionLines.svelte
        │           ├── MemoryNode.svelte
        │           └── MemorySpace.svelte
        │
        └── routes/
            ├── +layout.svelte
            ├── +page.svelte
            │
            ├── auth/
            │   └── callback/
            │       └── +page.svelte
            │
            ├── admin/
            │   ├── +layout.svelte
            │   ├── +page.svelte
            │   ├── analytics/
            │   │   └── +page.svelte
            │   ├── users/
            │   │   └── +page.svelte
            │   └── audit/
            │       └── +page.svelte
            │
            └── credit/
                └── +page.svelte
```

---

## File Counts

| Category | Count |
|----------|-------|
| Python Files | 60+ |
| Frontend Components | 40+ |
| Svelte Routes | 8 |
| Stores | 12 |
| Documentation Files | 20+ |
| Skill Files | 6 |
| JSON Chunk Files | 25 |
| SQL Migrations | 3 |

---

## Key Entry Points

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, WebSocket endpoint |
| `claude_chat.py` | Interactive SDK agent REPL |
| `claude_run.py` | One-shot prompt executor |
| `frontend/src/routes/+page.svelte` | Main chat interface |

---

## Configuration Summary (config.yaml)

```yaml
tier: basic                    # Dumb chatbot mode
model: grok-4-1-fast-reasoning

voice:
  engine: venom

features:
  memory_pipelines: false      # All OFF in basic tier
  context_stuffing: true       # Loads from Manuals/Driscoll/
  chat_import: false
  extraction_enabled: false

memory:
  backend: file                # Toggle: file | postgres
```

---

## Current Progress

**Master Execution Plan:** 60% Complete (3 of 5 phases)

| Phase | Status | Commit |
|-------|--------|--------|
| 2.5: DOCX Chunking | ✅ COMPLETE | `a4bb32d` |
| 1: Schema Enhancement | ✅ COMPLETE | `6c54b23` |
| 2: RLS Policies | ✅ COMPLETE | `d24c959` |
| 3: Ingestion Pipeline | ⏳ NEXT | - |
| 4: CogTwin Integration | ⏳ PENDING | - |
| 5: Schema Lock Docs | ⏳ PENDING | - |

---

## Git Commits (Recent)

```
b601f3b docs: Progress report - Phases 2.5, 1, 2 complete
d24c959 feat(db): Phase 2 - implement RLS policies
6c54b23 feat(db): Phase 1 - enhance department_content schema
a4bb32d feat(ingest): Phase 2.5 - DOCX to JSON chunking pipeline
01d2b2a SDK Agent CLI: Add database tools, skills system, batch mode
eea8f3b Phase 0: Add StateMonitor debug panel for Nerve Center
```

---

**Total New Code:** ~5,000 lines across 25+ new files
**Documentation:** ~3,000 lines across 12 new docs
**Chunks Created:** 169 chunks from 25 manual files
