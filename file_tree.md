# Enterprise Bot - File Tree

**Last Updated:** 2025-12-17
**Repo:** enterprise_bot
**Deploy:** Railway (Azure PostgreSQL for auth, SQL Server for Driscoll data)

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
├── Config (Root)
│   ├── .env
│   ├── .env.azure-template
│   ├── .gitignore
│   ├── config.yaml              # App config (tenant, features, model settings)
│   ├── email_whitelist.json     # Allowed domains/emails
│   ├── requirements.txt         # Python dependencies
│   ├── runtime.txt              # Python version for Railway
│   └── Procfile                 # Railway start command
│
├── Docs
│   ├── README.md
│   ├── QUICKSTART.md
│   ├── CHANGELOG.md
│   ├── RAILWAY_SPEC_SHEET.md
│   ├── AZURE_SSO_README.md      # Azure AD SSO setup guide
│   ├── PHASE1_SETUP.md
│   ├── PHASE2_FRONTEND.md
│   ├── PHASE3_DEPLOYMENT.md
│   └── file_tree.md             # This file
│
├── ============ ACTIVE BACKEND ============
│
├── main.py                      # FastAPI app entry point
├── config.py                    # Settings class
├── config_loader.py             # YAML config loader, cfg() helper
├── schemas.py                   # Pydantic models
│
├── Auth & Admin
│   ├── auth_schema.py           # DB schema setup for auth + analytics tables
│   ├── auth_service.py          # User CRUD, permissions, audit logging
│   ├── admin_routes.py          # FastAPI router for admin portal
│   ├── azure_auth.py            # Azure AD SSO token validation
│   ├── sso_routes.py            # SSO OAuth callback endpoints
│   ├── tenant_service.py        # Department content loading
│   └── enterprise_tenant.py     # TenantContext dataclass
│
├── Analytics Engine
│   ├── analytics_service.py     # Query logging, classification, aggregation
│   └── analytics_routes.py      # Dashboard API endpoints at /api/admin/analytics
│
├── Enterprise Twin (Chat Engine)
│   ├── enterprise_twin.py       # Main chat engine, context stuffing
│   ├── chat_parser_agnostic.py  # Response parsing
│   └── model_adapter.py         # Model switching utility
│
├── Database Utils
│   ├── db_setup.py              # Azure PostgreSQL connection
│   ├── db_diagnostic.py         # Connection testing/debug
│   └── run_migration.py         # Database migrations
│
├── Document Processing
│   ├── doc_loader.py            # Document loading (JSON, CSV, Excel, MD, TXT)
│   ├── upload_manuals.py        # Manual uploader
│   ├── ingest.py                # Ingestion pipeline
│   ├── dedup.py                 # Deduplication
│   └── llm_tagger.py            # LLM tagging
│
├── ============ FUTURE: MEMORY SYSTEM ============
│
├── Memory Pipeline
│   ├── chat_memory.py           # Memory management
│   ├── memory_pipeline.py       # Embedding pipeline
│   ├── memory_grep.py           # Memory search
│   ├── reasoning_trace.py       # Trace logging
│   ├── read_traces.py           # Trace reader
│   └── streaming_cluster.py     # Cluster streaming
│
├── Search & Retrieval
│   ├── retrieval.py             # Vector retrieval
│   ├── scoring.py               # Relevance scoring
│   ├── hybrid_search.py         # Hybrid vector+keyword
│   ├── fast_filter.py           # Fast filtering
│   ├── heuristic_enricher.py    # Result enrichment
│   └── embedder.py              # Embedding generation
│
├── Voice (not currently used)
│   ├── venom_voice.py           # Voice synthesis
│   └── enterprise_voice.py      # Enterprise voice
│
├── Utilities
│   ├── squirrel.py              # Caching utility
│   └── init_sandbox.py          # Sandbox init
│
├── Testing
│   ├── debug_pipeline.py
│   ├── test_setup.py
│   ├── test_integration_quick.py
│   └── verify_chat_integration.py
│
├── ============ DATA ============
│
├── data/
│   ├── memory_index.json
│   ├── corpus/                  # Document corpus
│   └── vectors/                 # Vector embeddings
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
├── db/
│   ├── supabase_3tier_complete.sql   # OLD - Reference only
│   └── supabase_auth_setup.sql       # OLD - Reference only
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
        │   │   │
        │   │   ├── ribbon/                    # Intelligence Ribbon (Nav)
        │   │   │   ├── index.ts               # Barrel export
        │   │   │   ├── IntelligenceRibbon.svelte  # Main nav ribbon
        │   │   │   ├── NavLink.svelte         # Nav link with glow effect
        │   │   │   ├── AdminDropdown.svelte   # Admin menu dropdown
        │   │   │   └── UserMenu.svelte        # User profile dropdown
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
        │   ├── stores/
        │   │   ├── index.ts                 # Store exports
        │   │   ├── auth.ts                  # Auth state & API
        │   │   ├── admin.ts                 # Admin portal state + CRUD
        │   │   ├── analytics.ts             # Dashboard data store
        │   │   ├── credit.ts                # Credit form state
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
