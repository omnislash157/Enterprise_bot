# Enterprise Bot - File Tree

**Last Updated:** 2025-12-18
**Repo:** enterprise_bot
**Deploy:** Railway (Azure PostgreSQL for auth, SQL Server for Driscoll data)
**Status:** CogTwin Merge Complete - Phases 1-5 ✅

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
│   ├── .gitignore
│   ├── config.yaml              # App config (tenant, features, model settings, voice toggle)
│   ├── email_whitelist.json     # Allowed domains/emails (legacy)
│   ├── requirements.txt         # Python dependencies (updated with pgvector)
│   ├── runtime.txt              # Python version for Railway
│   └── Procfile                 # Railway start command
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
│   │   ├── PHASE_5_MEMORY_BACKEND_SUMMARY.md  # Backend implementation details
│   │   ├── MEMORY_BACKEND_INTEGRATION.md  # Backend integration guide
│   │   ├── MEMORY_BACKEND_QUICKSTART.md   # Quick start for developers
│   │   ├── MIGRATION_GUIDE.md             # Complete migration guide
│   │   └── QUICK_START_MIGRATION.md       # 5-minute quick start
│   │
│   ├── Architecture
│   │   ├── WIRING_MAP.md                  # Complete system architecture
│   │   └── CLAUDE_CHAT_PROMPTS.md         # Claude chat system prompts
│   │
│   └── README.md (in root)                # Main project README
│
├── Root Files
│   ├── README.md                          # Main project README (stays in root)
│
├── ============ ACTIVE BACKEND ============
│
├── Core Backend
│   ├── main.py                      # FastAPI app entry point
│   ├── config.py                    # Settings class (legacy)
│   ├── config_loader.py             # YAML config loader, cfg() helper
│   ├── schemas.py                   # Pydantic models (MemoryNode, EpisodicMemory)
│   ├── model_adapter.py             # LLM client factory (Grok/Claude)
│   └── enterprise_tenant.py         # TenantContext dataclass
│
├── Auth & Admin
│   ├── auth_schema.py               # DB schema setup for auth + analytics tables
│   ├── auth_service.py              # User CRUD, permissions, audit logging
│   ├── admin_routes.py              # FastAPI router for admin portal
│   ├── azure_auth.py                # Azure AD SSO token validation
│   ├── sso_routes.py                # SSO OAuth callback endpoints
│   └── tenant_service.py            # Department content loading
│
├── Analytics Engine
│   ├── analytics_service.py         # Query logging, classification, aggregation
│   └── analytics_routes.py          # Dashboard API endpoints at /api/admin/analytics
│
├── ============ UNIFIED ENGINE (CogTwin) ============
│
├── CogTwin Core (Phases 1-2 Complete)
│   ├── cog_twin.py                  # Main cognitive engine (NOW ACTIVE!)
│   ├── venom_voice.py               # Venom personality system prompt builder
│   └── enterprise_voice.py          # Enterprise personality (compatible interface)
│
├── Enterprise Mode (Legacy - Context Stuffing)
│   ├── enterprise_twin.py           # Simplified chat engine (pre-merge)
│   ├── chat_parser_agnostic.py      # Response parsing
│   └── doc_loader.py                # Document loading (JSON, CSV, Excel, MD, TXT, DOCX)
│
├── ============ MEMORY SYSTEM (Phase 3-5 Complete) ============
│
├── Memory Backend Abstraction (Phase 5.1)
│   ├── memory_backend.py            # Abstract base class + FileBackend
│   ├── postgres_backend.py          # PostgreSQL + pgvector backend
│   └── migrate_to_postgres.py       # Migration script (file → PostgreSQL)
│
├── Memory Pipeline (Phase 3 - Auth Scoping Complete)
│   ├── chat_memory.py               # Memory management
│   ├── memory_pipeline.py           # Embedding pipeline (Phase 3: now stamps user_id/tenant_id)
│   ├── memory_grep.py               # Memory search
│   ├── reasoning_trace.py           # Trace logging
│   ├── read_traces.py               # Trace reader
│   └── streaming_cluster.py         # Cluster streaming
│
├── Search & Retrieval (Phase 3 - Auth Filtering Complete)
│   ├── retrieval.py                 # Vector retrieval (Phase 3: filters by user_id/tenant_id)
│   ├── scoring.py                   # Relevance scoring
│   ├── hybrid_search.py             # Hybrid vector+keyword
│   ├── fast_filter.py               # Fast filtering
│   ├── heuristic_enricher.py        # Result enrichment
│   └── embedder.py                  # Embedding generation
│
├── Metacognitive System
│   ├── metacognitive_mirror.py      # Cognitive state monitoring
│   ├── evolution_engine.py          # Learning and adaptation
│   └── cluster_schema.py            # Cluster profiling
│
├── ============ DATABASE ============
│
├── Database (PostgreSQL + pgvector - Phase 5 Complete)
│   ├── db_setup.py                  # Azure PostgreSQL connection
│   ├── db_diagnostic.py             # Connection testing/debug
│   ├── run_migration.py             # Database migrations
│   └── generate_test_user.py        # Helper script for test user/tenant SQL
│
├── db/
│   ├── migrations/
│   │   └── 001_memory_tables.sql    # Phase 5: PostgreSQL schema (tenants, users, memory_nodes)
│   ├── supabase_3tier_complete.sql  # OLD - Reference only
│   └── supabase_auth_setup.sql      # OLD - Reference only
│
├── ============ DOCUMENT PROCESSING ============
│
├── Document Processing
│   ├── ingest.py                    # Ingestion pipeline
│   ├── dedup.py                     # Deduplication
│   ├── llm_tagger.py                # LLM tagging
│   └── upload_manuals.py            # Manual uploader
│
├── ============ DATA ============
│
├── data/
│   ├── memory_index.json            # Memory index
│   ├── corpus/
│   │   ├── nodes.json               # Memory nodes (Phase 3: now includes user_id/tenant_id)
│   │   ├── episodes.json            # Episodic memories
│   │   └── dedup_index.json         # Deduplication index
│   ├── vectors/
│   │   ├── nodes.npy                # Node embeddings (1024-dim BGE-M3)
│   │   └── episodes.npy             # Episode embeddings
│   └── indexes/
│       └── clusters.json            # Cluster assignments
│
├── Manuals/
│   └── Driscoll/
│       ├── Purchasing/
│       │   └── purchasing_manual_chunks.json
│       └── Sales/
│           ├── bid_management_chunks.json
│           ├── sales_support_chunks.json
│           └── telnet_sop_chunks.json
│
├── ============ TESTING & UTILITIES ============
│
├── Testing
│   ├── debug_pipeline.py            # Memory pipeline debugging
│   ├── test_setup.py                # Database setup test
│   ├── test_integration_quick.py    # Quick integration test
│   ├── verify_chat_integration.py   # Chat memory verification
│   └── init_empty_data.py           # Bootstrap empty data structure (Phase 1)
│
├── Utilities
│   ├── squirrel.py                  # Temporal recall tool
│   ├── init_sandbox.py              # Sandbox init
│   ├── claude_chat.py               # Claude SDK agent chat
│   ├── claude_run.py                # Claude agent runner
│   └── sdk_recon.py                 # SDK reconnaissance tool
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
        │   │   ├── csvExport.ts         # CSV export utility
        │   │   └── clickOutside.ts      # Click outside action for dropdowns
        │   │
        │   ├── transitions/
        │   │   └── pageTransition.ts    # Page transition utilities
        │   │
        │   ├── components/
        │   │   ├── ChatOverlay.svelte       # Main chat UI
        │   │   ├── Login.svelte             # Auth login form
        │   │   ├── DepartmentSelector.svelte # Dept picker
        │   │   ├── CreditForm.svelte        # Credit request form
        │   │   ├── DupeOverrideModal.svelte # Dupe handling modal
        │   │   ├── CheekyLoader.svelte      # Personality loading with emerge transition
        │   │   ├── CheekyInline.svelte      # Minimal inline loader
        │   │   ├── CheekyToast.svelte       # Standalone toast component
        │   │   ├── ToastProvider.svelte     # Global toast with context module
        │   │   │
        │   │   ├── ribbon/                  # Intelligence Ribbon (Nav)
        │   │   │   ├── index.ts             # Barrel export
        │   │   │   ├── IntelligenceRibbon.svelte  # Main nav ribbon
        │   │   │   ├── NavLink.svelte       # Nav link with glow effect
        │   │   │   ├── AdminDropdown.svelte # Admin menu dropdown
        │   │   │   └── UserMenu.svelte      # User profile dropdown
        │   │   │
        │   │   ├── admin/                   # Admin Portal
        │   │   │   ├── UserRow.svelte       # User list row
        │   │   │   ├── AccessModal.svelte   # Grant/revoke modal
        │   │   │   ├── RoleModal.svelte     # Role change modal
        │   │   │   ├── CreateUserModal.svelte  # Single user creation
        │   │   │   ├── BatchImportModal.svelte # Batch CSV import
        │   │   │   ├── LoadingSkeleton.svelte  # Shimmer loading component
        │   │   │   │
        │   │   │   ├── charts/              # Nerve Center Charts
        │   │   │   │   ├── chartTheme.ts    # Cyberpunk Chart.js config
        │   │   │   │   ├── StatCard.svelte  # Metric display widget
        │   │   │   │   ├── LineChart.svelte # Time series
        │   │   │   │   ├── DoughnutChart.svelte # Category breakdown
        │   │   │   │   ├── BarChart.svelte  # Department comparison
        │   │   │   │   ├── RealtimeSessions.svelte # Live sessions
        │   │   │   │   ├── NerveCenterWidget.svelte # 3D viz wrapper
        │   │   │   │   ├── DateRangePicker.svelte   # Date filtering
        │   │   │   │   └── ExportButton.svelte      # CSV export button
        │   │   │   │
        │   │   │   └── threlte/             # 3D Neural Network
        │   │   │       ├── NeuralNode.svelte     # Glowing category node
        │   │   │       ├── DataSynapse.svelte    # Curved lines + packets
        │   │   │       ├── NeuralNetwork.svelte  # Category nodes + synapses
        │   │   │       └── NerveCenterScene.svelte # Full scene + particles
        │   │   │
        │   │   └── archive/                 # Archived components
        │   │       ├── AnalyticsDashboard.svelte
        │   │       ├── ArtifactPane.svelte
        │   │       ├── FloatingPanel.svelte
        │   │       └── WorkspaceNav.svelte
        │   │
        │   ├── cheeky/                       # CheekyLoader Engine
        │   │   ├── index.ts                 # Barrel export
        │   │   ├── CheekyStatus.ts          # Phrase rotation, seasonal, config
        │   │   └── phrases.ts               # 200+ personality phrases + spinners
        │   │
        │   ├── stores/
        │   │   ├── index.ts                 # Store exports
        │   │   ├── auth.ts                  # Auth state & API
        │   │   ├── admin.ts                 # Admin portal state + CRUD
        │   │   ├── analytics.ts             # Dashboard data store
        │   │   ├── credit.ts                # Credit form state
        │   │   ├── cheeky.ts                # Cheeky loading state management
        │   │   ├── websocket.ts             # WS connection
        │   │   ├── session.ts               # Chat session
        │   │   ├── config.ts                # App config
        │   │   ├── theme.ts                 # Dark mode
        │   │   ├── artifacts.ts
        │   │   ├── panels.ts
        │   │   └── workspaces.ts
        │   │
        │   └── threlte/                     # 3D visualization
        │       ├── CoreBrain.svelte
        │       ├── Scene.svelte
        │       ├── CreditAmbientOrbs.svelte # Credit page decoration
        │       └── archive/                 # Archived 3D components
        │           ├── AgentNode.svelte
        │           ├── ConnectionLines.svelte
        │           ├── MemoryNode.svelte
        │           └── MemorySpace.svelte
        │
        └── routes/
            ├── +layout.svelte               # Root layout, auth gate
            ├── +page.svelte                 # Main chat page
            │
            ├── auth/
            │   └── callback/
            │       └── +page.svelte         # Azure AD SSO callback
            │
            ├── admin/                       # Admin Portal
            │   ├── +layout.svelte           # Admin layout + sidebar
            │   ├── +page.svelte             # Nerve Center dashboard
            │   ├── analytics/
            │   │   └── +page.svelte         # Analytics deep dive
            │   ├── users/
            │   │   └── +page.svelte         # User management + CRUD
            │   └── audit/
            │       └── +page.svelte         # Audit log (super_user)
            │
            └── credit/
                └── +page.svelte             # Credit request page
```

---

## Key Files by Function

### Entry Points
- **main.py** - FastAPI application, WebSocket endpoint, HTTP routes
- **frontend/src/routes/+page.svelte** - Main chat interface

### Configuration
- **config.yaml** - All application configuration (NEW: voice toggle, memory backend)
- **config_loader.py** - Config helper functions
- **.env** - Environment variables (secrets)

### Core Engine (Post-Merge)
- **cog_twin.py** - Unified cognitive engine (Phases 1-2: NOW ACTIVE)
- **venom_voice.py** - Venom personality voice (toggled via config)
- **enterprise_voice.py** - Enterprise voice (toggled via config)

### Memory System (Phase 3-5)
- **memory_backend.py** - Backend abstraction (file/postgres)
- **postgres_backend.py** - PostgreSQL + pgvector implementation
- **retrieval.py** - Auth-scoped retrieval (user_id/tenant_id filtering)
- **memory_pipeline.py** - Stamps memories with auth context
- **schemas.py** - MemoryNode with user_id/tenant_id fields

### Database
- **db/migrations/001_memory_tables.sql** - PostgreSQL schema with pgvector
- **db_setup.py** - Connection management
- **migrate_to_postgres.py** - Data migration tool

### Auth & Permissions
- **auth_service.py** - User management, department access
- **azure_auth.py** - Azure AD integration
- **tenant_service.py** - Tenant/department logic

### Analytics
- **analytics_service.py** - Query logging and metrics
- **analytics_routes.py** - Analytics API

### Document Processing
- **doc_loader.py** - Multi-format document loader
- **ingest.py** - Document ingestion pipeline

---

## Merge Status Summary

### ✅ Phase 1: CogTwin Activated
- `main.py` uses CogTwin instead of EnterpriseTwin
- Empty data handling implemented
- `init_empty_data.py` created for bootstrap

### ✅ Phase 2: Voice Toggle
- Config flag: `voice.engine: venom | enterprise`
- Conditional voice import in cog_twin.py
- Both voices share same interface

### ✅ Phase 3: Auth Scoping
- MemoryNode has `user_id` and `tenant_id` fields
- Retrieval filters by scope BEFORE similarity search
- Fail-secure: no auth = no results
- WebSocket passes auth context to engine

### ✅ Phase 4: Extraction Toggle
- Config flag: `features.chat_import: true/false`
- Upload endpoint returns 403 when disabled
- Enterprise mode blocks external log imports

### ✅ Phase 5: PostgreSQL + pgvector
- Database schema with pgvector extension
- Migration script (file → PostgreSQL)
- Backend abstraction layer (FileBackend + PostgresBackend)
- IVFFlat indexes for fast similarity search
- Auth scoping enforced at database level

---

## Configuration Flags (config.yaml)

```yaml
voice:
  engine: venom              # Toggle: venom | enterprise

deployment:
  mode: personal             # Toggle: personal | enterprise
  tier: full

features:
  memory_pipelines: true
  context_stuffing: false    # Deprecated - replaced by RAG
  chat_import: false         # Phase 4: disable for enterprise
  extraction_enabled: false  # Phase 4: disable for enterprise

memory:
  backend: file              # Phase 5: Toggle: file | postgres

  postgres:                  # Phase 5: PostgreSQL configuration
    host: localhost
    port: 5432
    database: enterprise_bot
    user: postgres
    password: ${POSTGRES_PASSWORD}
```

---

## Documentation Organization ✅

All documentation is now organized in the `docs/` folder:

**Setup & Deployment:**
- `docs/AZURE_SSO_README.md` - Azure AD SSO configuration
- `docs/RAILWAY_SPEC_SHEET.md` - Railway deployment guide

**Merge Documentation:**
- `docs/SDK_MERGE_HANDOFF.md` - Phases 1-2 handoff
- `docs/MERGE_HANDOFF_PHASES_3_4_5.md` - Phases 3-5 handoff
- `docs/PHASES_3_4_5_COMPLETE.md` - Complete implementation summary

**Phase 5 - PostgreSQL Migration:**
- `docs/PHASE_5_SUMMARY.md` - Migration overview
- `docs/PHASE_5_MEMORY_BACKEND_SUMMARY.md` - Backend details
- `docs/MEMORY_BACKEND_INTEGRATION.md` - Integration guide
- `docs/MEMORY_BACKEND_QUICKSTART.md` - Developer quick start
- `docs/MIGRATION_GUIDE.md` - Complete migration walkthrough
- `docs/QUICK_START_MIGRATION.md` - 5-minute quick start

**Architecture Documentation:**
- `docs/WIRING_MAP.md` - Complete system architecture (52KB)
- `docs/CLAUDE_CHAT_PROMPTS.md` - Chat system prompts
- `docs/file_tree.md` - This file (project structure)

**Root Files:**
- `README.md` - Main project README (kept in root for GitHub)

---

## File Counts

- **Total Python Files:** 56
- **Active Backend Files:** ~25
- **Memory System Files:** ~15
- **Frontend Files:** ~100+ (components, routes, stores)
- **Documentation Files:** 13+ (need to organize)

---

## Next Steps

1. **Move documentation to docs/ folder** for better organization
2. **Update README.md** to reflect CogTwin merge completion
3. **Create deployment checklist** for PostgreSQL migration
4. **Archive legacy files** (enterprise_twin.py, old context stuffing)
5. **Update Railway deployment** with new env vars for PostgreSQL

---

**Last Session Accomplishments:**
- Phases 3, 4, 5 completed
- 19 files created/modified
- 4,172 lines of production code
- 62 KB of documentation
- PostgreSQL + pgvector infrastructure complete
- Auth scoping implemented
- Ready for production! 🚀
