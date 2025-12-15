# Enterprise Bot - Source of Truth File Tree

**Last Updated:** 2025-01-15
**Repo:** enterprise_bot
**Deploy:** Railway (Supabase for auth, SQL Server for Driscoll data)

---

## Project Structure

```
enterprise_bot/
├── .claude/
│   └── settings.local.json
│
├── Config (Root)
│   ├── .env
│   ├── .gitignore
│   ├── config.yaml
│   ├── email_whitelist.json
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── runtime.txt
│   └── Procfile
│
├── Docs
│   ├── README.md
│   ├── QUICKSTART.md
│   ├── CHANGELOG.md
│   └── RAILWAY_SPEC_SHEET.md
│
├── Core Python (Root)
│   ├── main.py
│   ├── config.py
│   ├── config_loader.py
│   ├── schemas.py
│   │
│   ├── Document Processing
│   │   ├── ingest.py
│   │   ├── doc_loader.py
│   │   ├── embedder.py
│   │   ├── dedup.py
│   │   └── llm_tagger.py
│   │
│   ├── Search & Retrieval
│   │   ├── retrieval.py
│   │   ├── scoring.py
│   │   ├── hybrid_search.py
│   │   ├── fast_filter.py
│   │   └── heuristic_enricher.py
│   │
│   ├── Cognitive Systems
│   │   ├── cognitive_profiler.py
│   │   ├── cog_twin.py
│   │   ├── enterprise_twin.py
│   │   ├── metacognitive_mirror.py
│   │   └── evolution_engine.py
│   │
│   ├── Auth & Tenancy  ← NEW
│   │   ├── tenant_service_v2.py     ← 3-tier permission system
│   │   ├── tenant_service.py        ← Legacy (pre-Supabase)
│   │   └── enterprise_tenant.py.bak ← Archived
│   │
│   ├── Voice
│   │   ├── venom_voice.py
│   │   └── enterprise_voice.py
│   │
│   ├── Memory & Chat  ← Future hive mind infrastructure
│   │   ├── chat_memory.py
│   │   ├── chat_parser_agnostic.py
│   │   ├── memory_pipeline.py
│   │   ├── memory_grep.py
│   │   ├── streaming_cluster.py
│   │   ├── cluster_schema.py
│   │   ├── reasoning_trace.py
│   │   └── read_traces.py
│   │
│   ├── Utilities
│   │   ├── model_adapter.py
│   │   ├── squirrel.py
│   │   └── init_sandbox.py
│   │
│   └── Testing
│       ├── debug_pipeline.py
│       ├── test_setup.py
│       ├── test_integration_quick.py
│       └── verify_chat_integration.py
│
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py              ← FastAPI app (needs auth integration)
│       └── artifacts/
│           ├── __init__.py
│           ├── actions.py
│           ├── chat.py
│           ├── memory.py
│           ├── parser.py
│           ├── synthesis.py
│           └── viz.py
│
├── db/  ← NEW
│   ├── supabase_3tier_complete.sql   ← Run in Supabase SQL Editor
│   └── supabase_auth_setup.sql       ← Earlier draft (reference only)
│
├── data/
│   ├── memory_index.json
│   ├── corpus/
│   └── vectors/
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
    ├── src/
    │   ├── app.html
    │   ├── app.css
    │   │
    │   ├── lib/
    │   │   ├── artifacts/
    │   │   │   └── registry.ts
    │   │   │
    │   │   ├── components/
    │   │   │   ├── ChatOverlay.svelte
    │   │   │   ├── Login.svelte       ← NEW: Auth UI
    │   │   │   └── archive/
    │   │   │
    │   │   ├── stores/
    │   │   │   ├── index.ts
    │   │   │   ├── auth.ts            ← NEW: Supabase auth store
    │   │   │   ├── artifacts.ts
    │   │   │   ├── config.ts
    │   │   │   ├── panels.ts
    │   │   │   ├── session.ts
    │   │   │   ├── theme.ts
    │   │   │   ├── websocket.ts
    │   │   │   └── workspaces.ts
    │   │   │
    │   │   └── threlte/
    │   │       ├── CoreBrain.svelte
    │   │       ├── Scene.svelte
    │   │       └── archive/
    │   │
    │   └── routes/
    │       ├── +layout.svelte         ← Needs auth init (see integration)
    │       ├── +page.svelte           ← Chat bot UI
    │       └── credit/
    │           └── +page.svelte
    │
    └── static/
```

---

## Auth System (3-Tier Permissions)

### Tiers
| Tier | Role | Data Access | Admin Access |
|------|------|-------------|--------------|
| 1 | `user` | Filtered by employee_id (e.g., sales rep sees only their customers) | None |
| 2 | `dept_head` | All data in their department | View users in dept |
| 3 | `super_user` | Everything | Full admin |

### Key Files
- **Backend:** `tenant_service_v2.py` - JWT verification, UserContext, permission checks
- **Frontend:** `auth.ts` - Supabase client, session management, tenant switching
- **UI:** `Login.svelte` - Login/signup/magic link forms
- **Schema:** `db/supabase_3tier_complete.sql` - Tables, RLS policies, seed data

### Integration Status
- [x] Auth files in place
- [x] `+layout.svelte` - Auth init and login gate
- [x] `backend/app/main.py` - Auth dependency + `/api/whoami` endpoint
- [x] `stores/index.ts` - Auth exports
- [ ] `frontend/package.json` - Add `@supabase/supabase-js`
- [ ] Environment variables configured
- [ ] SQL migration run in Supabase

---

## Database Connections

### Supabase (Auth & Tenancy)
```
Tables: tenants, tenant_departments, user_tenants, department_content
```

### SQL Server - Driscoll (BID1)
```
Tables: InvoiceHeader, InvoiceDetail, CreditRequests, CreditRequestItems
Views:  vw_UniqueCustomers, vw_CustomerInvoices, vw_InvoiceLineItems, vw_SalesmanLookup
```

---

## Environment Variables Required

```env
# Supabase Auth
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJ...                    # anon/public key
SUPABASE_JWT_SECRET=your-jwt-secret

# Frontend (Vite)
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...

# Driscoll SQL Server
DRISCOLL_SQL_SERVER=...
DRISCOLL_SQL_DATABASE=...
DRISCOLL_SQL_USERNAME=...
DRISCOLL_SQL_PASSWORD=...
```

---

## Key Patterns

- **Auth Flow:** Supabase JWT → `tenant_service_v2.get_user_context()` → `UserContext`
- **Data Filtering:** `ctx.get_data_filter()` returns `{"sales_rep_id": "JA"}` for tier 1 users
- **Context Stuffing:** `ctx.context_content` contains department manuals for AI prompt injection
- **Frontend Routes:** SvelteKit file-based (`/routes/X/+page.svelte` = `/X`)
- **Backend API:** FastAPI in `backend/app/main.py`

---

## Next Steps

### Remaining Setup
1. **Install Supabase client:** `cd frontend && npm install @supabase/supabase-js`
2. **Run SQL migration** in Supabase SQL Editor (`db/supabase_3tier_complete.sql`)
3. **Configure env vars** (see above)
4. **Sign up** and run `SELECT admin_add_user_to_tenant(...)` to get super_user access

### TODO: Manual Loading Pipeline
Wire `ctx.context_content` into chat endpoint and add JSON support to manual uploader:
- Add `.json` file handling to `upload_manuals.py`
- Verify chat endpoint uses `ctx.context_content` for prompt injection
- Test with `/api/whoami` → should show `context_content_count > 0`

### Future: Hive Mind Memory
Parent/child vault architecture using existing memory infrastructure:
- `chat_memory.py`, `memory_pipeline.py`, `reasoning_trace.py`
- Sales gets child vault, leadership gets parent vault
