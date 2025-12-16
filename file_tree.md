# Enterprise Bot - Source of Truth File Tree

**Last Updated:** 2024-12-16 (Phase 3 Nerve Center Dashboard Complete)
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
│   └── file_tree.md             # This file
│
├── ============ ACTIVE BACKEND ============
│
├── main.py                      # FastAPI app entry point
├── config.py                    # Settings class
├── config_loader.py             # YAML config loader, cfg() helper
├── schemas.py                   # Pydantic models
│
├── Auth & Admin (Phase 1-3 + User CRUD)
│   ├── auth_schema.py           # DB schema setup for auth + analytics tables
│   │                            # + init_analytics_tables() for Phase 2
│   ├── auth_service.py          # User CRUD, permissions, audit logging
│   │                            # + create_user, update_user, deactivate_user,
│   │                            #   reactivate_user, batch_create_users
│   ├── admin_routes.py          # FastAPI router for admin portal
│   │                            # + POST/PUT/DELETE /users endpoints
│   ├── tenant_service.py        # Department content loading
│   └── enterprise_tenant.py     # TenantContext dataclass
│
├── Analytics Engine (Phase 2 - Nerve Center)
│   ├── analytics_service.py     # Query logging, classification, aggregation
│   │                            # + classify_query(), detect_frustration()
│   │                            # + log_query(), log_event()
│   │                            # + get_overview_stats(), get_category_breakdown()
│   └── analytics_routes.py      # Dashboard API endpoints at /api/admin/analytics
│                                # + GET /overview, /queries, /categories
│                                # + GET /departments, /errors, /realtime
│
├── Enterprise Twin (Chat Engine)
│   ├── enterprise_twin.py       # Main chat engine, context stuffing
│   │                            # + Analytics instrumentation in think()
│   ├── chat_parser_agnostic.py  # Response parsing
│   └── model_adapter.py         # Model switching utility
│
├── Database Utils
│   ├── db_setup.py              # Azure PostgreSQL connection
│   └── db_diagnostic.py         # Connection testing/debug
│
├── Document Processing
│   ├── doc_loader.py            # Document loading
│   ├── upload_manuals.py        # Manual uploader (ACTIVE)
│   ├── ingest.py                # Ingestion pipeline
│   ├── dedup.py                 # Deduplication
│   └── llm_tagger.py            # LLM tagging
│
├── ============ FUTURE: MEMORY SYSTEM ============
│   (Planned for future sprint - hive mind architecture)
│
├── Memory Pipeline
│   ├── chat_memory.py           # Memory management
│   ├── memory_pipeline.py       # Embedding pipeline
│   ├── memory_grep.py           # Memory search
│   ├── reasoning_trace.py       # Trace logging
│   ├── read_traces.py           # Trace reader
│   └── streaming_cluster.py     # Cluster streaming
│
├── Search & Retrieval (for memory system)
│   ├── retrieval.py             # Vector retrieval
│   ├── scoring.py               # Relevance scoring
│   ├── hybrid_search.py         # Hybrid vector+keyword
│   ├── fast_filter.py           # Fast filtering
│   ├── heuristic_enricher.py    # Result enrichment
│   └── embedder.py              # Embedding generation
│
├── ============ INACTIVE / REVIEW ============
│
├── Voice (not currently used)
│   ├── venom_voice.py           # Voice synthesis
│   └── enterprise_voice.py      # Enterprise voice
│
├── Utilities (check usage)
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
    │   └── (svelte, postcss, tailwind configs)
    │
    └── src/
        ├── app.html
        ├── app.css
        │
        ├── lib/
        │   ├── artifacts/
        │   │   └── registry.ts
        │   │
        │   ├── components/
        │   │   ├── ChatOverlay.svelte       # Main chat UI
        │   │   ├── Login.svelte             # Auth login form
        │   │   ├── DepartmentSelector.svelte # Dept picker
        │   │   ├── CreditForm.svelte        # Credit request form
        │   │   ├── DupeOverridemodel.svelte # Dupe handling modal
        │   │   │
        │   │   ├── admin/                   # Admin Portal (Phase 3 + CRUD)
        │   │   │   ├── UserRow.svelte       # User list row + edit/deactivate btns
        │   │   │   ├── AccessModal.svelte   # Grant/revoke modal
        │   │   │   ├── RoleModal.svelte     # Role change modal
        │   │   │   ├── CreateUserModal.svelte  # NEW: Single user creation
        │   │   │   └── BatchImportModal.svelte # NEW: Batch CSV import
        │   │   │   │
        │   │   │   └── charts/              # Phase 3: Nerve Center Charts
        │   │   │       ├── chartTheme.ts    # Cyberpunk Chart.js config
        │   │   │       ├── StatCard.svelte  # Metric display widget
        │   │   │       ├── LineChart.svelte # Time series (queries/hour)
        │   │   │       ├── DoughnutChart.svelte # Category breakdown
        │   │   │       ├── BarChart.svelte  # Department comparison
        │   │   │       └── RealtimeSessions.svelte # Live sessions widget
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
        │   │   ├── admin.ts                 # Admin portal state + CRUD methods
        │   │   ├── credit.ts                # Credit form state
        │   │   ├── websocket.ts             # WS connection
        │   │   ├── session.ts               # Chat session
        │   │   ├── config.ts                # App config
        │   │   ├── theme.ts                 # Dark mode
        │   │   ├── artifacts.ts             # (check if used)
        │   │   ├── panels.ts                # (check if used)
        │   │   └── workspaces.ts            # (check if used)
        │   │
        │   ├── threlte/                     # 3D visualization
        │   │   ├── CoreBrain.svelte
        │   │   ├── Scene.svelte
        │   │   └── archive/                 # Archived 3D components
        │   │
        │   └── CreditAmbientOrbs.svelte     # Credit page decoration
        │
        └── routes/
            ├── +layout.svelte               # Root layout, auth gate
            ├── +page.svelte                 # Main chat page
            │
            ├── admin/                       # Admin Portal (Phase 3 + CRUD)
            │   ├── +layout.svelte           # Admin layout + sidebar
            │   ├── +page.svelte             # Dashboard
            │   ├── users/
            │   │   └── +page.svelte         # User management + CRUD modals
            │   └── audit/
            │       └── +page.svelte         # Audit log (super_user)
            │
            └── credit/
                └── credit_page.svelte       # TODO: Rename to +page.svelte
```

---

## Auth System (3-Tier Permissions)

### Current Architecture (Phase 2-3 Complete)
- **Database:** Azure PostgreSQL (driscoll schema)
- **Auth:** X-User-Email header (trusted proxy mode)
- **No JWT yet** - planned for Phase 4

### Tiers
| Tier | Role | Data Access | Admin Access |
|------|------|-------------|--------------|
| 1 | `user` | Own department only | None |
| 2 | `dept_head` | All data in their department(s) | Manage dept users |
| 3 | `super_user` | Everything | Full admin + audit log |

### Key Active Files
- **Backend:** `auth_service.py` - User CRUD, permissions, audit
- **Backend:** `admin_routes.py` - Admin API endpoints
- **Frontend:** `auth.ts` - Auth store, login/logout
- **Frontend:** `admin.ts` - Admin portal state
- **UI:** `routes/admin/*` - Admin portal pages

---

## Deleted Files (2024-12-16 Cleanup)

### CogTwin Legacy (removed)
- `cog_twin.py` - Full cognitive twin (65KB)
- `cognitive_profiler.py` - Personality modeling (34KB)
- `metacognitive_mirror.py` - Self-reflection system
- `evolution_engine.py` - Learning/evolution
- `cluster_schema.py` - Cluster data models

### Backend Folder (removed - was duplicate)
- `backend/app/main.py` - Stale Supabase version
- `backend/app/admin_routes.py` - Duplicate
- `backend/app/config.py` - Duplicate
- `backend/app/artifacts/*` - Unused artifact system

---

## Future: Memory System Sprint

The following files are retained for a future sprint to enable hive mind memory:

### Memory Pipeline
- `chat_memory.py` - Memory management core
- `memory_pipeline.py` - Embedding pipeline
- `memory_grep.py` - Memory search
- `reasoning_trace.py` - Trace logging
- `read_traces.py` - Trace reader
- `streaming_cluster.py` - Cluster streaming

### Search & Retrieval
- `retrieval.py` - Vector retrieval
- `scoring.py` - Relevance scoring
- `hybrid_search.py` - Hybrid search
- `fast_filter.py` - Fast filtering
- `heuristic_enricher.py` - Result enrichment
- `embedder.py` - Embedding generation

### Planned Architecture
- Parent/child vault architecture
- Sales gets child vault, leadership gets parent vault
- Uses existing memory infrastructure

---

## Known Issues

1. **credit_page.svelte** needs rename to `+page.svelte` for SvelteKit routing
2. **db/*.sql** files reference old Supabase setup (now using Azure PostgreSQL)

---

## Environment Variables

```env
# Azure PostgreSQL
POSTGRES_HOST=...
POSTGRES_DATABASE=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...
POSTGRES_PORT=5432

# OpenAI
OPENAI_API_KEY=...

# Frontend
VITE_API_URL=http://localhost:8000

# Driscoll SQL Server (for credit system)
DRISCOLL_SQL_SERVER=...
DRISCOLL_SQL_DATABASE=...
DRISCOLL_SQL_USERNAME=...
DRISCOLL_SQL_PASSWORD=...
```

---

## Recent Changes (2024-12-16)

### Phase 2: Analytics Engine (Nerve Center) - COMPLETE
Full instrumentation layer - "If they fart, we know about it."

**New Database Tables (`auth_schema.py --init-analytics`):**
- `enterprise.query_log` - Full query storage with auto-classification
- `enterprise.analytics_events` - Non-query events (login, dept_switch, error)
- `enterprise.analytics_daily` - Pre-computed daily aggregates

**New Files:**
- `analytics_service.py` (~400 lines) - The fart detector
  - Query classification into 10 categories (PROCEDURAL, LOOKUP, TROUBLESHOOTING, etc.)
  - Frustration signal detection
  - Repeat question detection (Jaccard similarity)
  - `log_query()`, `log_event()` for all instrumentation
  - Dashboard query methods for frontend
- `analytics_routes.py` (~100 lines) - API at `/api/admin/analytics`
  - `GET /overview` - Active users, total queries, avg response time, error rate
  - `GET /queries` - Query counts by hour (for charts)
  - `GET /categories` - Category breakdown (pie/bar chart)
  - `GET /departments` - Per-department stats
  - `GET /errors` - Recent error events
  - `GET /users/{email}` - User activity stats
  - `GET /realtime` - Currently active sessions

**Instrumented Files:**
- `main.py` - Login events, dept_switch events, error events
- `enterprise_twin.py` - Query logging after each think() response

### Phase 1: User Management CRUD - COMPLETE
Added full CRUD operations to the admin portal:

**Backend (`auth_service.py`):**
- `create_user()` - Admin-driven user creation (no domain restriction)
- `update_user()` - Update email, display_name, employee_id, primary_department
- `deactivate_user()` - Soft delete (sets active=FALSE)
- `reactivate_user()` - Restore deactivated user
- `batch_create_users()` - Bulk create from list

**Backend (`admin_routes.py`):**
- `POST /api/admin/users` - Create single user
- `POST /api/admin/users/batch` - Batch create users
- `PUT /api/admin/users/{user_id}` - Update user
- `DELETE /api/admin/users/{user_id}` - Deactivate user
- `POST /api/admin/users/{user_id}/reactivate` - Reactivate user

**Frontend:**
- `CreateUserModal.svelte` - Single user creation form
- `BatchImportModal.svelte` - CSV/textarea batch import
        │   │   │   │
        │   │   │   └── charts/              # Phase 3: Nerve Center Charts
        │   │   │       ├── chartTheme.ts    # Cyberpunk Chart.js config
        │   │   │       ├── StatCard.svelte  # Metric display widget
        │   │   │       ├── LineChart.svelte # Time series (queries/hour)
        │   │   │       ├── DoughnutChart.svelte # Category breakdown
        │   │   │       ├── BarChart.svelte  # Department comparison
        │   │   │       └── RealtimeSessions.svelte # Live sessions widget
- `UserRow.svelte` - Added edit/deactivate/reactivate action buttons
- `admin.ts` - Added CRUD store methods
- `users/+page.svelte` - Integrated all modals with "+ Add User" and "Batch Import" buttons

---

## Next Steps

### Immediate
1. Rename `credit/credit_page.svelte` → `credit/+page.svelte`

### Future Sprints
- **Phase 3:** Nerve Center Dashboard UI (frontend for analytics)
- **Phase 4:** Department Management CRUD (add/edit departments)
- **Phase 5:** JWT authentication
- **Memory Sprint:** Enable hive mind with retained memory files
- **Voice Sprint:** Evaluate venom_voice.py / enterprise_voice.py
