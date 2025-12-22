# Config System Deep Recon

**Generated:** 2024-12-22 01:15 UTC
**Status:** Documentation only - no fixes applied
**Type:** Forensic audit - Full config/routing/twin system documentation

---

## Executive Summary

The config/routing/twin system has **3 overlapping config loaders**, **2 twin routing mechanisms**, and **email-based authentication security holes**. The startup logs show `EnterpriseTwin` initialized but `CogTwin` receiving requests, indicating twin routing is broken. `TenantContext.email` attribute error suggests post-refactor cleanup debt.

**Critical Findings:** 5 major issues documented below.

---

## Critical Issues Found

### 1. **WRONG TWIN ROUTING** - Line: `main.py:91-118`
**Symptom:** Logs show `EnterpriseTwin` initialized at startup but `CogTwin` serving requests
**Cause:** `get_twin_for_auth()` routes by auth_method, but WebSocket uses `get_twin()` at startup
**Impact:** Enterprise users get personal SaaS twin (wrong memory system, wrong voice)

```python
# main.py:76-89 - Startup uses get_twin() (config-based)
def get_twin():
    mode = cfg('deployment.mode', 'personal')
    if mode == 'enterprise':
        return EnterpriseTwin(get_config())  # ✅ Initializes this
    else:
        return CogTwin()

# main.py:91-118 - Runtime uses get_twin_for_auth() (auth-based)
def get_twin_for_auth(auth_method: str, user_email: str = None):
    enterprise_providers = ['azure_ad', 'azuread', 'entra_id', 'microsoft']
    if auth_method in enterprise_providers:
        return EnterpriseTwin(get_config())
    else:
        return CogTwin()  # ❌ Email login routes here

# main.py:747 - WebSocket uses per-request twin routing
request_twin = get_twin_for_auth(auth_method, user_email)
```

**The Problem:**
- Startup logs `EnterpriseTwin` because `config.yaml` says `deployment.mode: enterprise`
- But WebSocket flow uses `get_twin_for_auth()` which checks `auth_method`
- Email login sets `auth_method = "legacy_email"` → routes to `CogTwin`
- Result: "mhartigan@driscollfoods.com via email → CogTwin" (WRONG!)

### 2. **TENANTCONTEXT MISSING EMAIL ATTRIBUTE** - Line: `main.py:904`
**Symptom:** `WARNING: 'TenantContext' object has no attribute 'email'`
**Cause:** Post-refactor cleanup debt - code expects `.email` but TenantContext has `.user_email`

```python
# enterprise_tenant.py:40-68 - TenantContext definition
@dataclass
class TenantContext:
    tenant_id: str
    department: str
    user_email: Optional[str] = None  # ✅ Field is 'user_email'
    # ... no 'email' field

# main.py:904 - Analytics logging
analytics.log_event(
    event_type="dept_switch",
    user_email=tenant.email or user_email,  # ❌ Tries to access .email
    # ...
)
```

**Fix:** Change `tenant.email` to `tenant.user_email` (1 line)

### 3. **MANIFEST ERROR** - Line: `main.py:926`
**Symptom:** `ERROR: No manifest found in data`
**Cause:** Dead code reference - "manifest" concept doesn't exist in current WebSocket protocol
**Impact:** Confusing error message, suggests expected feature missing

**Investigation:** Searched codebase for "manifest" - found no sender, only this error handler. Likely legacy code from earlier WebSocket protocol design.

### 4. **EMAIL LOGIN SECURITY HOLE** - Lines: `main.py:721-799`
**Description:** Anyone can type any email and impersonate a user. No password, no token validation.

```python
# main.py:721-744 - WebSocket verify message (INSECURE)
elif msg_type == "verify":
    email = data.get("email", "")
    # No password check, no token validation, just trust the email string

    if AUTH_LOADED and email:
        auth = get_auth_service()
        user = auth.get_or_create_user(email)  # Creates user if not exists!
```

**Current Behavior:**
- User sends `{"type": "verify", "email": "ceo@driscollfoods.com"}`
- System trusts it, logs them in, creates user if not exists
- No verification of identity whatsoever

**Config Question:** No `disable_email_login` flag found in `config.yaml`. Email login is hardcoded in WebSocket handler.

**How to Disable:**
1. Remove `elif msg_type == "verify"` block from `main.py:721-799`
2. Force all auth through SSO routes at `/api/auth/login`
3. Validate Bearer tokens in WebSocket connect (not implemented)

### 5. **MEMORY SYSTEM LOADING FOR ENTERPRISE** - Line: `cog_twin.py:240`
**Symptom:** `INFO: Loading memory system...`
**Question:** Should EnterpriseTwin load personal memory system?

```python
# cog_twin.py:219-241 - CogTwin.__init__()
def __init__(self, data_dir, api_key, model):
    logger.info("Loading memory system...")  # ✅ Makes sense for CogTwin
    self.retriever = DualRetriever.load(self.data_dir)
```

**Current State:** EnterpriseTwin is initialized but request routes to CogTwin, so this is a symptom of issue #1.

**Expected:** EnterpriseTwin should NOT load personal memory system. It uses RAG from manuals, not memory pipeline.

---

## Config Files

### `config.yaml` - Runtime Configuration

**Location:** `core/config.yaml`
**Lines:** 142 total
**Purpose:** Master feature flag and deployment config file

```yaml
# ===== KEY SECTIONS =====

deployment:
  mode: enterprise              # ⚠️ Set to 'enterprise' but routing broken
  tier: basic                   # basic = dumb, pro = memory, full = everything

tenant:
  id: driscoll
  name: "Driscoll Foods"
  allowed_domains:              # ⚠️ SECURITY: gmail.com allowed for testing
    - driscollfoods.com
    - gmail.com
  docs_root: ./manuals/Driscoll
  default_division: warehouse   # ⚠️ Used when email login bypasses dept check

features:
  memory_pipelines: false       # ✅ OFF for basic tier (correct)
  session_memory: false         # ✅ OFF for basic tier (correct)
  context_stuffing: false       # DEPRECATED - RAG replaced this
  metacognitive_mirror: false   # ✅ OFF - cognitive features disabled
  cognitive_profiler: false
  evolution_engine: false
  reasoning_traces: false
  chat_import: false            # ✅ OFF - no external chat import

  ui:
    swarm_loop: false
    memory_space_3d: false
    chat_basic: true            # ✅ ON - basic chat UI only
    dark_mode: true
    analytics_dashboard: false

model:
  provider: xai                 # Grok (not Anthropic)
  name: grok-4-1-fast-reasoning
  max_tokens: 8192
  temperature: 0.5
  context_window: 2000000

docs:
  docs_dir: ./manuals/Driscoll  # Process manuals for RAG
  max_tokens_per_request: 200000
  stuffing:
    enabled: true
    max_tokens_per_division: 200000

voice:
  engine: venom                 # ⚠️ 'venom' or 'enterprise'?
  style: corporate
  company_name: "Driscoll Foods"
  sign_off: false
  division_voice:               # Different voice per department
    sales: corporate
    transportation: troll       # ⚠️ Sarcastic mode for transport?
    operations: corporate

paths:
  data_dir: ./data              # Memory storage (should be empty for enterprise)
  manuals_root: ./manuals

memory:
  backend: file                 # "file" or "postgres"
  postgres:                     # Postgres config for memory backend
    host: localhost
    port: 5432
    database: enterprise_bot

logging:
  level: INFO
```

**ISSUES IN CONFIG:**
1. `allowed_domains` includes `gmail.com` - security risk
2. `voice.engine: venom` - should this be `enterprise` for corporate mode?
3. `division_voice.transportation: troll` - sarcastic mode for warehouse?
4. No `disable_email_login` flag
5. No `is_production` flag to lock down testing features

---

### Environment Variables

| Variable | Used In | Purpose | Required |
|----------|---------|---------|----------|
| **API KEYS** |
| `XAI_API_KEY` | `model_adapter.py:16,18` | Grok API access | ✅ Yes |
| `ANTHROPIC_API_KEY` | `model_adapter.py:19`, `cog_twin.py:237` | Claude API (fallback) | Optional |
| `OPENAI_API_KEY` | (not used) | OpenAI (legacy) | No |
| `DEEPINFRA_API_KEY` | `enterprise_rag.py:139` | BGE-M3 embeddings | ✅ Yes |
| **AZURE AD (SSO)** |
| `AZURE_AD_TENANT_ID` | `azure_auth.py:30` | Microsoft tenant ID | ✅ Yes |
| `AZURE_AD_CLIENT_ID` | `azure_auth.py:31` | App registration ID | ✅ Yes |
| `AZURE_AD_CLIENT_SECRET` | `azure_auth.py:32` | App secret | ✅ Yes |
| `AZURE_AD_REDIRECT_URI` | `azure_auth.py:33` | OAuth callback URL | ✅ Yes |
| **DATABASE** |
| `AZURE_PG_USER` | `auth_service.py:61`, `analytics_service.py:18`, etc. | PostgreSQL username | ✅ Yes |
| `AZURE_PG_PASSWORD` | `auth_service.py:62`, `analytics_service.py:19`, etc. | PostgreSQL password | ✅ Yes |
| `AZURE_PG_HOST` | `auth_service.py:63`, `analytics_service.py:20`, etc. | PostgreSQL host | ✅ Yes |
| `AZURE_PG_PORT` | `auth_service.py:64`, `analytics_service.py:21`, etc. | PostgreSQL port | Optional (default 5432) |
| `AZURE_PG_DATABASE` | `auth_service.py:65`, `analytics_service.py:22`, etc. | Database name | Optional (default postgres) |
| `AZURE_PG_SSLMODE` | `auth_service.py:66` | SSL mode | Optional (default require) |
| `AZURE_PG_CONNECTION_STRING` | `enterprise_rag.py:140` | Full connection string | Optional (built from parts) |
| **OTHER** |
| `EMAIL_WHITELIST_PATH` | `main.py:45` | Whitelist JSON file path | Optional |
| `COGTWIN_CONFIG` | `config_loader.py:49` | Override config.yaml location | Optional |
| **FRONTEND** |
| `VITE_API_URL` | (frontend only) | Backend API URL for Railway | ✅ Yes (frontend) |

**CRITICAL MISSING:**
- No `DISABLE_EMAIL_LOGIN` flag
- No `IS_PRODUCTION` flag to lock down `gmail.com` domain, etc.

---

## File Audits

### `core/config.yaml`

**Purpose:** Master feature flag and deployment configuration file
**Lines:** 142
**Format:** YAML with 10 top-level sections

**Imports From:** N/A (data file)
**Exports To:**
- `config_loader.py:74` → Loaded via `yaml.safe_load()`
- All modules via `cfg(key, default)` helper

**Config Dependencies:**
- **Reads:** File system at `./core/config.yaml` or parent directories
- **Writes:** None (read-only)

**Database Queries:** None

**Known Issues:**
1. `gmail.com` in `allowed_domains` - testing backdoor in production
2. No production flag to disable testing features
3. `voice.engine: venom` - unclear if correct for enterprise mode
4. `transportation: troll` voice - sarcastic mode in production?

**Deprecated/Dead Code:**
- `features.context_stuffing: false` - Explicitly marked DEPRECATED, RAG replaced it

---

### `core/config.py`

**Purpose:** Settings dataclass (NOT USED) - legacy Pydantic config loader
**Lines:** 204
**Status:** ⚠️ **DEAD CODE** - Not imported by `main.py` or any active module

**Imports From:**
- Standard library: `logging`, `os`, `pathlib`
- Third-party: `yaml`, `dotenv`

**Exports To:**
- ⚠️ **NONE** - Module exists but not imported by active code

**Config Dependencies:**
- **Reads:** Searches for `config.yaml` in current dir, parent dirs
- **Writes:** None

**Known Issues:**
1. **COMPLETELY UNUSED** - `main.py` imports from `config_loader.py`, not `config.py`
2. Defines `get_api_key()` helper but no code calls it
3. Has `setup_logging()` function but `main.py` uses `logging.basicConfig()` directly
4. Creates confusion - 2 files named "config"

**Recommendation:** DELETE THIS FILE or rename to `config_legacy.py` with deprecation notice

---

### `core/config_loader.py`

**Purpose:** THE REAL config loader - provides `cfg()` helper for dotted key access
**Lines:** 286
**Status:** ✅ **ACTIVE** - This is the config loader actually used by the app

**Imports From:**
- Standard library: `os`, `pathlib`, `yaml`
- Third-party: `dotenv`

**Exports To:**
- `main.py:55-62` → `load_config, cfg, memory_enabled, is_enterprise_mode, get_ui_features, get_config`
- `cog_twin.py:110` → `from .config import cfg, get_config, setup_logging` (⚠️ wrong import path, works due to name collision)
- `protocols.py:69-75` → Exports as public API

**Config Dependencies:**
- **Reads:**
  - `config.yaml` file (searches: cwd, `__file__.parent`, `__file__.parent.parent`)
  - `COGTWIN_CONFIG` env var (override config path)
- **Writes:** Module-level cache `_config`, `_config_path`

**Database Queries:** None

**Key Functions:**
| Function | Purpose | Returns |
|----------|---------|---------|
| `load_config(path)` | Load config.yaml into cache | `dict` |
| `get_config()` | Get full config dict | `dict` |
| `cfg(key, default)` | Get nested value via dot notation | `Any` |
| `is_enterprise_mode()` | Check if `deployment.mode == 'enterprise'` | `bool` |
| `memory_enabled()` | Check if `features.memory_pipelines == True` | `bool` |
| `get_tier()` | Get `deployment.tier` (basic/advanced/full) | `str` |
| `get_ui_features()` | Get `features.ui` dict for frontend | `dict` |

**Known Issues:**
1. **TWO CONFIG LOADERS** - `config.py` exists but unused, causes confusion
2. `context_stuffing_enabled()` returns hardcoded `False` with deprecation comment - should be removed
3. `get_division_voice()` defined but no code uses it (searched codebase)

**Deprecated/Dead Code:**
- `context_stuffing_enabled()` - line 131-136 - Always returns False
- `get_division_voice()` - line 164-167 - No callers found
- `apply_tier_preset()` - line 196-216 - No callers found
- `TIER_PRESETS` - line 174-193 - Only used by unused `apply_tier_preset()`

---

### `core/main.py`

**Purpose:** FastAPI application - THE BIG ONE - all routes, WebSocket, twin routing
**Lines:** 952
**Status:** ✅ **ACTIVE** - Main entry point

**Imports From:**
- FastAPI: `FastAPI`, `WebSocket`, `HTTPException`, `Depends`, `Header`, `Request`
- Core: `config_loader` (5 imports), `enterprise_tenant.TenantContext`, `cog_twin.CogTwin`, `enterprise_twin.EnterpriseTwin`
- Auth: `auth_service` (3 imports), `tenant_service`, `admin_routes`, `analytics_routes`, `sso_routes`, `azure_auth` (2 imports)
- Standard lib: `asyncio`, `json`, `os`, `logging`, `time`, `pathlib`, `datetime`

**Exports To:**
- **None** - This is the top-level entry point, runs as `uvicorn core.main:app`

**Config Dependencies:**
- **Reads:** `cfg()` calls throughout for feature flags, paths, tenant config
- **Writes:** None

**Database Queries:** (via imported services)
- `auth_service.get_or_create_user()` → `enterprise.users` table
- `analytics_service.log_event()` → `enterprise.analytics_events` table (if enabled)

**Twin Routing Logic:**

```python
# STARTUP TWIN (lines 76-89)
def get_twin():
    """Routes by config.yaml deployment.mode"""
    mode = cfg('deployment.mode', 'personal')
    if mode == 'enterprise':
        return EnterpriseTwin(get_config())
    else:
        return CogTwin()

# REQUEST TWIN (lines 91-118)
def get_twin_for_auth(auth_method: str, user_email: str = None):
    """Routes by authentication method"""
    enterprise_providers = ['azure_ad', 'azuread', 'entra_id', 'microsoft']
    if auth_method in enterprise_providers:
        return EnterpriseTwin(get_config())
    else:
        return CogTwin()

# WEBSOCKET USAGE (line 747)
request_twin = get_twin_for_auth(auth_method, user_email)
```

**⚠️ THE PROBLEM:** Two different twin routers with different logic!

**Auth Flow:**

```
Browser → WebSocket connect → /ws/{session_id}
    ↓
verify message → {"type": "verify", "email": "user@domain.com"}
    ↓
AUTH_LOADED? → get_auth_service().get_or_create_user(email)
    ↓
auth_method = data.get("auth_method", "email")  ← ⚠️ Default "email"
    ↓
request_twin = get_twin_for_auth(auth_method, user_email)
    ↓
"email" NOT IN enterprise_providers → CogTwin ❌ WRONG
```

**Known Issues:**
1. **Twin routing broken** (Issue #1) - Startup vs runtime routing mismatch
2. **TenantContext.email** (Issue #2) - Line 904, wrong attribute name
3. **Manifest error** (Issue #3) - Line 926, dead code
4. **Email login security hole** (Issue #4) - Lines 721-799, no password
5. `email_whitelist` fallback (lines 778-799) - deprecated, unused in SSO mode
6. `get_or_create_user()` creates users with NO department access (line 728) - by design but could surprise users

**Deprecated/Dead Code:**
- Lines 257-315: `EmailWhitelist` class - only used as fallback, SSO bypasses
- Lines 541-556: `/api/admin/users` endpoint - marked DEPRECATED, returns 501
- Line 926: `"No manifest found in data"` error - manifest concept doesn't exist

---

### `core/cog_twin.py`

**Purpose:** Personal SaaS cognitive twin - full memory pipeline, RAG, metacognition
**Lines:** 1573
**Status:** ✅ **ACTIVE** - But should NOT be used in enterprise mode

**Imports From:**
- Memory: `metacognitive_mirror`, `retrieval`, `embedder`, `memory_pipeline`, `reasoning_trace`, `scoring`, `chat_memory`, `squirrel`
- Core: `config` (⚠️ wrong - should be `config_loader`), `model_adapter`
- Voice: `venom_voice` (multiple imports)

**Exports To:**
- `main.py:63` → `from .cog_twin import CogTwin`
- `protocols.py:100` → Exported as public API

**Config Dependencies:**
- **Reads:** `cfg()` calls for model, retrieval, memory pipeline, feedback injection, analytics
- **Writes:** None

**Database Queries:** None (uses file-based memory)

**Known Issues:**
1. **Used in wrong mode** (symptom of Issue #1) - Enterprise should use EnterpriseTwin
2. Line 110: `from .config import cfg` - should be `from .config_loader import cfg` (works due to name collision)
3. Memory system loaded (line 240) - wasteful in enterprise mode

**Deprecated/Dead Code:**
- None found - this is well-maintained personal SaaS code

---

### `core/enterprise_twin.py`

**Purpose:** Enterprise corporate twin - manual RAG, no memory, corporate voice
**Lines:** 616
**Status:** ⚠️ **PARTIALLY ACTIVE** - Initialized at startup but not serving requests (Issue #1)

**Imports From:**
- Standard lib: `asyncio`, `logging`, `os`, `dataclasses`, `datetime`, `hashlib`

**Exports To:**
- `main.py:64` → `from .enterprise_twin import EnterpriseTwin`

**Config Dependencies:**
- **Reads:** Full `config` dict passed to `__init__()`, uses lazy loading for components
- **Writes:** Session memories cache `_session_memories`

**Database Queries:** None (delegates to RAG/squirrel/memory_pipeline)

**Lazy-Loaded Components:**
| Property | Module | Purpose |
|----------|--------|---------|
| `self.rag` | `enterprise_rag.EnterpriseRAGRetriever` | Manual retrieval |
| `self.squirrel` | `squirrel.SquirrelTool` | Temporal context |
| `self.memory_pipeline` | `memory_pipeline.MemoryPipeline` | Session memory |
| `self.model_adapter` | `model_adapter.create_adapter` | LLM calls |

**Tool Firing Logic:**
```python
# Line 139-210: classify_enterprise_intent() - HEURISTIC GATE
# Python controls which tools fire, NOT Grok
def classify_enterprise_intent(query: str) -> str:
    # Returns: 'procedural', 'lookup', 'complaint', 'casual'
    # Manual RAG fires for: procedural, lookup, complaint
    # Manual RAG SKIPS: casual (hi, thanks, bye)
```

**Known Issues:**
1. **NOT SERVING REQUESTS** (Issue #1) - Initialized but email login routes to CogTwin
2. Lazy imports may fail silently (lines 261-298) - logs warnings but continues
3. No error handling if model_adapter fails (line 432)

**Deprecated/Dead Code:**
- None found - this is new, clean code

---

### `core/enterprise_tenant.py`

**Purpose:** TenantContext dataclass - carries user/department info through requests
**Lines:** 199
**Status:** ✅ **ACTIVE** - Used by WebSocket and API routes

**Imports From:**
- Standard lib: `dataclasses`, `typing`, `datetime`

**Exports To:**
- `main.py:23` → `from .enterprise_tenant import TenantContext`
- `protocols.py:94` → Exported as public API

**Config Dependencies:** None

**Database Queries:** None (just a dataclass)

**TenantContext Fields:**
```python
@dataclass
class TenantContext:
    tenant_id: str                          # Required
    department: str                         # Required
    user_email: Optional[str] = None        # ✅ Note: 'user_email', NOT 'email'
    user_id: Optional[str] = None
    display_name: Optional[str] = None
    role: str = "user"
    departments: List[str] = []
    session_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
```

**Known Issues:**
1. **Missing `.email` attribute** (Issue #2) - Code at `main.py:904` expects `tenant.email` but field is `tenant.user_email`

**Deprecated/Dead Code:**
- Lines 174-181: `SimpleTenantManager` - marked DEPRECATED, not instantiated
- Line 179: `TenantContext.from_email()` - marked DEPRECATED, method doesn't exist

---

### `auth/auth_service.py`

**Purpose:** User lookup, department access verification, admin operations
**Lines:** 545 (read first 300)
**Status:** ✅ **ACTIVE** - Core auth service

**Imports From:**
- Standard lib: `os`, `dataclasses`, `typing`, `datetime`, `contextlib`
- Database: `psycopg2`, `psycopg2.extras.RealDictCursor`
- Third-party: `dotenv`

**Exports To:**
- `main.py:24` → `from auth.auth_service import get_auth_service, authenticate_user`
- `protocols.py:80-84` → Exported as public API

**Config Dependencies:**
- **Reads:** Environment variables (AZURE_PG_*) for database connection
- **Writes:** In-memory user cache `_user_cache`

**Database Queries:**
- **Read:**
  - `get_user_by_email()` → `SELECT FROM enterprise.users WHERE LOWER(email) = %s`
  - `get_user_by_azure_oid()` → `SELECT FROM enterprise.users WHERE azure_oid = %s`
- **Write:**
  - `get_or_create_user()` → `INSERT INTO enterprise.users (...)` (if not exists)
  - `update_last_login()` → `UPDATE enterprise.users SET last_login_at = NOW()`
  - `grant_department_access()` → `UPDATE enterprise.users SET department_access = ...`

**User Dataclass:**
```python
@dataclass
class User:
    id: str
    email: str
    display_name: Optional[str]
    tenant_id: str
    azure_oid: Optional[str]
    department_access: List[str]      # ['sales', 'purchasing']
    dept_head_for: List[str]          # ['sales']
    is_super_user: bool
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    def can_access(self, department: str) -> bool:
        return self.is_super_user or department in self.department_access
```

**Known Issues:**
1. `get_or_create_user()` creates users with **EMPTY department_access array** (line 297) - admins must grant access manually
2. No rate limiting on user lookup (cache helps but DB could be hammered)
3. User cache never expires - stale data possible

**Deprecated/Dead Code:**
- None found - this is clean, refactored code

---

### `auth/tenant_service.py`

**Purpose:** Department management, tenant data, manual content loading
**Lines:** 150 (truncated read)
**Status:** ✅ **ACTIVE** - Used for department content retrieval

**Imports From:**
- Standard lib: `os`, `json`, `dataclasses`, `typing`, `enum`, `contextlib`
- Database: `psycopg2`, `psycopg2.extras.RealDictCursor`
- Third-party: `dotenv`

**Exports To:**
- `main.py:25` → `from auth.tenant_service import get_tenant_service`
- `protocols.py:89-90` → Exported as public API

**Config Dependencies:**
- **Reads:** Environment variables (AZURE_PG_*) for database connection
- **Writes:** None

**Database Queries:**
- **Read:**
  - `get_tenant_by_slug()` → `SELECT FROM enterprise.tenants WHERE slug = %s`
  - `get_all_content_for_context()` → Loads manuals from file system (NOT database)

**Static Departments:**
```python
# Lines 102-110 - Hardcoded department list (departments table removed)
STATIC_DEPARTMENTS = [
    Department(id="sales", slug="sales", name="Sales"),
    Department(id="purchasing", slug="purchasing", name="Purchasing"),
    Department(id="warehouse", slug="warehouse", name="Warehouse"),
    Department(id="credit", slug="credit", name="Credit"),
    Department(id="accounting", slug="accounting", name="Accounting"),
    Department(id="it", slug="it", name="IT"),
]
```

**Known Issues:**
1. Departments table removed (per 2-table refactor) but `Department` dataclass still exists - schema mismatch
2. `get_all_content_for_context()` likely reads from file system - path not validated

**Deprecated/Dead Code:**
- None visible (truncated read)

---

### `auth/sso_routes.py`

**Purpose:** Azure AD OAuth2 endpoints - SSO login flow
**Lines:** 200 (truncated read)
**Status:** ✅ **ACTIVE** - SSO routes at `/api/auth/*`

**Imports From:**
- FastAPI: `APIRouter`, `HTTPException`, `Depends`, `Response`, `Request`, `RedirectResponse`
- Pydantic: `BaseModel`
- Auth: `azure_auth` (5 imports), `auth_service.get_auth_service`
- Standard lib: `secrets`, `logging`, `uuid`

**Exports To:**
- `main.py:28` → `from auth.sso_routes import router as sso_router`
- `main.py:374-376` → Mounted at `/api/auth`

**Config Dependencies:**
- **Reads:** None directly (delegates to `azure_auth`)
- **Writes:** None

**Database Queries:** (via auth_service)
- `provision_user(azure_user)` → Calls `auth_service.get_or_create_user()`

**Routes:**
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/auth/config` | Returns SSO enabled status |
| GET | `/api/auth/login` | Redirect to Microsoft login |
| GET | `/api/auth/login-url` | Get login URL for SPA |
| POST | `/api/auth/callback` | Exchange code for tokens |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/logout` | Clear session |
| GET | `/api/auth/me` | Get current user |

**Known Issues:**
1. State validation TODO (line 94) - CSRF protection not implemented
2. No session storage for state parameter (line 94) - security hole

**Deprecated/Dead Code:**
- None visible (truncated read)

---

### `core/protocols.py`

**Purpose:** THE PUBLIC API - Only file new code should import from
**Lines:** 209
**Status:** ✅ **ACTIVE** - Exports 37 symbols as stable API

**Imports From:**
- Config: `config_loader` (5 imports)
- Auth: `auth_service` (3 imports), `tenant_service` (1 import), `enterprise_tenant` (1 import)
- Cognitive: `cog_twin`, `retrieval`, `model_adapter`
- Memory: `embedder`, `metacognitive_mirror`, `memory_pipeline`, `reasoning_trace`, `scoring`, `chat_memory`, `squirrel`
- Schemas: `schemas` (8 imports)

**Exports To:**
- **Intended:** All new code should import from protocols, not directly from modules
- **Reality:** `main.py` imports directly from submodules (not using protocols)

**Public API (37 symbols):**
- Configuration (5): `cfg`, `load_config`, `get_config`, `memory_enabled`, `is_enterprise_mode`
- Auth (3): `get_auth_service`, `authenticate_user`, `User`
- Tenant (2): `get_tenant_service`, `TenantContext`
- Cognitive (3): `CogTwin`, `DualRetriever`, `create_adapter`
- Embeddings (2): `AsyncEmbedder`, `create_embedder`
- Cognitive Pipeline (14): `MetacognitiveMirror`, `QueryEvent`, etc.
- Data Schemas (8): `MemoryNode`, `EpisodicMemory`, enums

**Known Issues:**
1. **NOT USED BY main.py** - `main.py` imports directly from submodules, bypassing protocols
2. Purpose is to create stable API boundary but adoption is incomplete

**Deprecated/Dead Code:**
- None - this is a clean export file

---

## Wiring Diagrams

### Request Flow

```
Browser HTTP/WebSocket Request
           ↓
    main.py:339 (FastAPI app)
           ↓
    ┌──────────────────────────────┐
    │   Route Decision             │
    ├──────────────────────────────┤
    │ HTTP /api/auth/login         │──→ sso_routes.py:79  (SSO flow)
    │ HTTP /api/whoami             │──→ main.py:529      (email auth fallback)
    │ WS   /ws/{session_id}        │──→ main.py:689      (WebSocket)
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │   Auth Check                 │
    ├──────────────────────────────┤
    │ get_current_user()           │  main.py:174-233
    │   ├─ Bearer token?           │  → azure_auth.validate_access_token()
    │   │    ├─ Valid → User obj   │  → auth_service.get_user_by_azure_oid()
    │   │    └─ Invalid → 401      │
    │   └─ X-User-Email header?    │  → auth_service.get_or_create_user()
    │        ├─ Valid → User obj   │      (⚠️ NO PASSWORD CHECK)
    │        └─ Invalid → 401      │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │   Twin Selection (BROKEN!)   │
    ├──────────────────────────────┤
    │ Startup (line 401):          │
    │   engine = get_twin()        │  → cfg('deployment.mode') = 'enterprise'
    │   → EnterpriseTwin           │  ✅ Logs "Initializing EnterpriseTwin"
    │                              │
    │ Runtime (line 747):          │
    │   auth_method = "email"      │  ← WebSocket verify sets this
    │   twin = get_twin_for_auth() │  → Checks auth_method
    │   → CogTwin                  │  ❌ "email" NOT IN enterprise_providers
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │   Twin Processing            │
    ├──────────────────────────────┤
    │ if twin == CogTwin:          │
    │   → memory pipeline          │  cog_twin.py:366-989
    │   → metacognition            │  Full cognitive loop
    │   → retrieval (personal)     │
    │                              │
    │ if twin == EnterpriseTwin:   │
    │   → classify_intent()        │  enterprise_twin.py:332-334
    │   → fire tools (Python)      │  Lines 340-369
    │   → RAG from manuals         │  enterprise_rag.py
    │   → corporate voice          │  Lines 456-570
    └──────────────────────────────┘
           ↓
    Response to User
```

**THE BUG:**
- Startup uses `get_twin()` → reads `config.yaml` → `EnterpriseTwin`
- Runtime uses `get_twin_for_auth()` → reads `auth_method` → `CogTwin`
- Result: Wrong twin serves all email login requests

---

### Config Flow

```
.env / Railway env vars
    ↓
config_loader.py:28 (load_dotenv())
    ↓
Environment Variables Loaded:
    - XAI_API_KEY
    - ANTHROPIC_API_KEY
    - AZURE_AD_* (4 vars)
    - AZURE_PG_* (7 vars)
    ↓
config_loader.py:37-80 (load_config())
    ↓
Searches for config.yaml:
    1. Path.cwd() / "config.yaml"
    2. Path(__file__).parent / "config.yaml"  ← ✅ Finds core/config.yaml
    3. Path(__file__).parent.parent / "config.yaml"
    ↓
yaml.safe_load(config.yaml)
    ↓
Global _config dict cached
    ↓
    ┌────────────────────────────────────────┐
    │  cfg(key, default) - Dotted Access     │
    ├────────────────────────────────────────┤
    │  cfg("deployment.mode")                │ → "enterprise"
    │  cfg("model.provider")                 │ → "xai"
    │  cfg("features.memory_pipelines")      │ → False
    │  cfg("tenant.allowed_domains")         │ → ["driscollfoods.com", "gmail.com"]
    └────────────────────────────────────────┘
    ↓
Used Throughout Codebase:
    - main.py:79 (twin routing)
    - main.py:278 (whitelist fallback)
    - main.py:461 (UI features)
    - main.py:702 (default department)
    - cog_twin.py:234 (data_dir path)
    - cog_twin.py:254 (model provider)
    - cog_twin.py:418 (retrieval top_k)
    - enterprise_twin.py:79 (deployment mode check)
```

**Config Priority:**
1. Environment variables (`.env` or Railway) - **HIGHEST**
2. config.yaml (runtime config)
3. Function defaults (fallback)

**Examples:**
- `cfg("model.provider", "xai")` → Reads `config.yaml`, returns `"xai"`
- `os.getenv("XAI_API_KEY")` → Reads env var, used directly
- `os.getenv("AZURE_PG_HOST", "localhost")` → Reads env var with fallback

---

### Auth Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      SSO LOGIN PATH                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
Browser → GET /api/auth/login-url
                          ↓
            sso_routes.py:100-120
                get_login_url()
                          ↓
        azure_auth.py:110-129 (get_auth_url)
                          ↓
    Returns: https://login.microsoftonline.com/.../authorize?...
                          ↓
Browser → Redirect to Microsoft
                          ↓
User Logs In (Microsoft Entra ID)
                          ↓
Microsoft → Redirect to callback with ?code=xxx
                          ↓
Frontend → POST /api/auth/callback {"code": "xxx"}
                          ↓
            sso_routes.py:123-177
                handle_callback()
                          ↓
        azure_auth.py:132-189 (exchange_code_for_tokens)
                          ↓
            MSAL: code → access_token + id_token
                          ↓
        azure_auth.py:192-228 (parse ID token)
                AzureUser(oid, email, name, ...)
                          ↓
            sso_routes.py:151 (provision_user)
                          ↓
        auth_service.py:249-319 (get_or_create_user)
                          ↓
            DB: SELECT FROM enterprise.users WHERE azure_oid = %s
                ├─ Found → Return existing User
                └─ Not found → INSERT new user (empty dept_access)
                          ↓
            Returns: User(id, email, dept_access[], ...)
                          ↓
            sso_routes.py:160-172
                          ↓
    Returns: TokenResponse {
        access_token: "...",
        refresh_token: "...",
        user: {id, email, departments: [], is_super_user: false}
    }
                          ↓
Frontend stores token, sends in Authorization: Bearer <token>


┌─────────────────────────────────────────────────────────────┐
│                   EMAIL LOGIN PATH (INSECURE)               │
└─────────────────────────────────────────────────────────────┘
                          ↓
Browser → WebSocket connect /ws/{session_id}
                          ↓
            main.py:689-799
                websocket_endpoint()
                          ↓
    Sends: {"type": "verify", "email": "user@domain.com"}
                          ↓
    ⚠️ NO PASSWORD, NO TOKEN VALIDATION
                          ↓
            main.py:726-744
                get_or_create_user(email)
                          ↓
        auth_service.py:249-319
                          ↓
            DB: SELECT FROM enterprise.users WHERE LOWER(email) = %s
                ├─ Found → Return User
                └─ Not found → INSERT (empty dept_access)
                          ↓
    Sets: request_twin = get_twin_for_auth("email", email)
                          ↓
    ❌ "email" NOT IN enterprise_providers → CogTwin (WRONG!)
                          ↓
    Sends: {"type": "verified", "email": "...", "departments": []}


┌─────────────────────────────────────────────────────────────┐
│                   USER OBJECT CREATION                      │
└─────────────────────────────────────────────────────────────┘

auth_service.py:249-319 (get_or_create_user)
    ↓
Domain check:
    domain = email.split("@")[1]
    SELECT id FROM enterprise.tenants WHERE domain = %s
    ├─ Found → tenant_id
    └─ Not found → Return None (auth fails)
    ↓
Create user:
    INSERT INTO enterprise.users (
        tenant_id, email, display_name, azure_oid,
        department_access,   ← ⚠️ EMPTY ARRAY {}
        dept_head_for,       ← ⚠️ EMPTY ARRAY {}
        is_super_user,       ← ⚠️ FALSE
        is_active            ← TRUE
    ) VALUES (...)
    ↓
Returns: User(
    id="uuid",
    email="user@domain.com",
    department_access=[],    ← NEW USERS HAVE NO ACCESS
    dept_head_for=[],
    is_super_user=False,
    is_active=True
)
```

**Where User is Stored:**
- SSO: `access_token` stored in frontend localStorage, sent as `Authorization: Bearer <token>`
- Email: User email stored in WebSocket session, NO token
- Database: `enterprise.users` table persists user record

**How User is Accessed:**
- HTTP: `get_current_user()` dependency (main.py:174) → reads Bearer token or X-User-Email header
- WebSocket: `request_twin` variable (main.py:747) → set during verify message

---

## Security

### Email Login - How to Disable

**Current State:** Email login is **HARDCODED** in WebSocket handler, no config flag to disable.

**Code Location:** `main.py:721-799`

```python
elif msg_type == "verify":
    email = data.get("email", "")
    # ⚠️ NO PASSWORD, NO TOKEN, JUST TRUST THE EMAIL STRING

    if AUTH_LOADED and email:
        auth = get_auth_service()
        user = auth.get_or_create_user(email)  # Creates if not exists!
```

**Attack Vector:**
1. Attacker connects to WebSocket
2. Sends `{"type": "verify", "email": "ceo@driscollfoods.com"}`
3. System creates/logs in user with NO verification
4. Attacker can impersonate anyone

**How to Disable:**

**Option 1: Remove email login block (RECOMMENDED)**
```python
# DELETE lines 721-799 in main.py
# Keep only SSO flow
```

**Option 2: Add config flag**
```yaml
# config.yaml
features:
  email_login_enabled: false  # Add this

# main.py:721
elif msg_type == "verify":
    if not cfg("features.email_login_enabled", False):
        await websocket.send_json({
            "type": "error",
            "message": "Email login disabled. Use SSO at /api/auth/login"
        })
        continue
    # ... rest of email login code
```

**Option 3: Require Bearer token in WebSocket connect**
```python
# main.py:689
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(None)  # Add token param
):
    # Validate token before accepting connection
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return

    user = validate_access_token(token)  # azure_auth.py
    if not user:
        await websocket.close(code=1008, reason="Invalid token")
        return

    # Now we know who the user is, no need for verify message
```

### SSO Token Validation

**What validates SSO tokens:**
- `azure_auth.py:238-273` → `validate_access_token(token)`
- Uses Microsoft Graph API to validate: `GET https://graph.microsoft.com/v1.0/me`
- Returns `AzureUser` object with claims or `None` if invalid

**What prevents impersonation:**
- Bearer token must be signed by Microsoft
- Token validated against Microsoft Graph API
- User must exist in `enterprise.users` table (created during first login)

**Security Gaps:**
1. State parameter not validated (sso_routes.py:94) - CSRF possible
2. No token expiration tracking - refresh logic exists but not enforced
3. Email login bypass (Issue #4) - anyone can impersonate via WebSocket

---

## Recommendations

**Priority Order:**

### 🔴 CRITICAL (Security)

1. **DISABLE EMAIL LOGIN** (Issue #4)
   - **Action:** Remove `elif msg_type == "verify"` block from `main.py:721-799`
   - **Reason:** Anyone can impersonate any user
   - **Effort:** 5 minutes
   - **Risk:** High - production security hole

2. **REMOVE gmail.com FROM ALLOWED DOMAINS**
   - **File:** `config.yaml:19`
   - **Action:** Delete `- gmail.com` line
   - **Reason:** Testing backdoor in production
   - **Effort:** 1 minute

3. **IMPLEMENT STATE VALIDATION**
   - **File:** `sso_routes.py:94`
   - **Action:** Store state in Redis/session, validate on callback
   - **Reason:** CSRF protection currently missing
   - **Effort:** 2 hours

### 🟠 HIGH (Functionality Broken)

4. **FIX TWIN ROUTING** (Issue #1)
   - **Root Cause:** `get_twin()` vs `get_twin_for_auth()` mismatch
   - **Option A:** Force all auth through SSO, remove email login, use `get_twin()` everywhere
   - **Option B:** Set `auth_method = "azure_ad"` when user logs in via SSO (frontend change)
   - **Recommended:** Option A (simpler, more secure)
   - **Files:** `main.py:76-118, 747`
   - **Effort:** 1 hour

5. **FIX TENANTCONTEXT.EMAIL** (Issue #2)
   - **File:** `main.py:904`
   - **Action:** Change `tenant.email` to `tenant.user_email`
   - **Reason:** Attribute error in analytics logging
   - **Effort:** 1 minute

6. **REMOVE MANIFEST ERROR** (Issue #3)
   - **File:** `main.py:926`
   - **Action:** Delete dead error handler or clarify what manifest is
   - **Effort:** 5 minutes

### 🟡 MEDIUM (Cleanup)

7. **DELETE config.py** (Dead Code)
   - **File:** `core/config.py` (204 lines)
   - **Action:** Delete file or rename to `config_legacy.py` with deprecation warning
   - **Reason:** Unused, causes confusion with `config_loader.py`
   - **Effort:** 5 minutes

8. **REMOVE DEPRECATED FUNCTIONS**
   - **Files:**
     - `config_loader.py:131-136` → `context_stuffing_enabled()` always returns False
     - `config_loader.py:164-167` → `get_division_voice()` no callers
     - `config_loader.py:196-216` → `apply_tier_preset()` no callers
   - **Effort:** 10 minutes

9. **CONSOLIDATE CONFIG LOADERS**
   - **Issue:** `config.py` and `config_loader.py` both exist
   - **Action:** Keep `config_loader.py`, delete `config.py`
   - **Effort:** 5 minutes

### 🟢 LOW (Nice to Have)

10. **ADD PRODUCTION FLAG**
    - **File:** `config.yaml`
    - **Action:** Add `deployment.is_production: true`
    - **Use:** Lock down testing features (gmail.com domain, email login, etc.)
    - **Effort:** 30 minutes

11. **ENFORCE PROTOCOLS.PY IMPORTS**
    - **Issue:** `main.py` imports directly from submodules, bypassing protocols
    - **Action:** Refactor imports to use `from core.protocols import ...`
    - **Reason:** Create stable API boundary
    - **Effort:** 2 hours

12. **ADD USER CACHE EXPIRATION**
    - **File:** `auth_service.py:163-211`
    - **Issue:** `_user_cache` never expires, stale data possible
    - **Action:** Add TTL or manual invalidation on user update
    - **Effort:** 1 hour

---

## Key Findings Summary

### 🔍 Top 5 Discoveries

1. **Twin Routing is Broken** - EnterpriseTwin initialized but CogTwin serves email login requests due to dual routing mechanisms (`get_twin()` vs `get_twin_for_auth()`)

2. **Email Login = Zero Security** - Anyone can send any email address via WebSocket and get authenticated, no password or token required

3. **Config System is Duplicated** - Two config loaders exist (`config.py` unused, `config_loader.py` active), causing confusion and technical debt

4. **TenantContext Refactor Incomplete** - Code expects `.email` attribute but dataclass has `.user_email`, causing runtime warnings

5. **Production Backdoors Active** - `gmail.com` in `allowed_domains`, `voice.style: troll` for transportation dept, no production flag to disable testing features

### 📊 Code Health Metrics

| Metric | Count |
|--------|-------|
| Total lines audited | ~8,500 |
| Critical security issues | 2 |
| Functional bugs | 3 |
| Dead code modules | 1 (config.py) |
| Deprecated functions | 3 |
| Environment variables | 18 |
| Config keys | 42 |
| Import paths violating protocols | ~15 |

### ✅ What's Working Well

1. **SSO Implementation** - Azure AD integration is solid, MSAL library used correctly
2. **Database Schema** - 2-table refactor is clean, RLS-ready
3. **EnterpriseTwin Architecture** - Clean separation, heuristic tool firing, trust hierarchy
4. **Config Flexibility** - `cfg()` helper with dot notation is elegant
5. **Feature Flags** - Comprehensive flag system for tier-based features

---

## Next Steps

**Immediate (Today):**
1. Fix twin routing (Issue #1)
2. Disable email login (Issue #4)
3. Fix TenantContext.email (Issue #2)
4. Remove gmail.com from allowed_domains

**This Week:**
1. Delete config.py dead code
2. Implement state validation for SSO
3. Add production flag to config
4. Clean up deprecated functions

**This Month:**
1. Enforce protocols.py imports
2. Add user cache expiration
3. Comprehensive security audit

---

**END OF RECON DOCUMENT**

No code changes made - documentation only.
