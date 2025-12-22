# Environment Variables - Complete Requirements

**Date:** 2024-12-21
**Purpose:** Comprehensive catalog of all environment variables used across the application

---

## Azure AD / Microsoft SSO Configuration

### AZURE_AD_TENANT_ID
- **Type:** String (UUID)
- **Required:** Yes (for Azure SSO)
- **Used By:** `auth/azure_auth.py` (lines 30, 36, 251, 315)
- **Purpose:** Microsoft Azure AD tenant identifier
- **Example:** `a1b2c3d4-1234-5678-90ab-cdef12345678`
- **Current Value:** ✅ Configured in Railway (from previous sessions)

### AZURE_AD_CLIENT_ID
- **Type:** String (UUID)
- **Required:** Yes (for Azure SSO)
- **Used By:** `auth/azure_auth.py` (lines 31, 50, 70, 314)
- **Purpose:** Azure AD application (client) ID
- **Example:** `e4f5g6h7-2345-6789-01bc-def123456789`
- **Current Value:** ✅ Configured in Railway

### AZURE_AD_CLIENT_SECRET
- **Type:** String (secret)
- **Required:** Yes (for Azure SSO)
- **Used By:** `auth/azure_auth.py` (lines 32, 51, 71)
- **Purpose:** Azure AD application client secret
- **Example:** `xyz123~AbCdEfGhIjKlMnOpQrStUvWxYz.1234`
- **Current Value:** ✅ Configured in Railway
- **Security:** NEVER commit to git

### AZURE_AD_REDIRECT_URI
- **Type:** URL
- **Required:** No (has default)
- **Default:** `http://localhost:5173/auth/callback`
- **Used By:** `auth/azure_auth.py` (lines 33, 125, 150)
- **Purpose:** OAuth callback URL after Microsoft login
- **Example Production:** `https://your-domain.com/auth/callback`
- **Notes:** Must match Azure AD app registration exactly

---

## Database Configuration (PostgreSQL Azure)

### AZURE_PG_HOST
- **Type:** Hostname
- **Required:** Yes
- **Default:** `localhost` (fallback)
- **Used By:**
  - `auth/auth_schema.py:37`
  - `auth/auth_service.py:58`
  - `auth/tenant_service.py:52`
  - `core/enterprise_rag.py:153`
  - `db/install_pgvector.py:15`
  - `db/run_migration_002.py:22`
- **Purpose:** PostgreSQL server hostname
- **Example:** `cogtwin.postgres.database.azure.com`
- **Current Value:** `cogtwin.postgres.database.azure.com`

### AZURE_PG_PORT
- **Type:** Integer
- **Required:** No
- **Default:** `5432`
- **Used By:** Same files as AZURE_PG_HOST
- **Purpose:** PostgreSQL server port
- **Current Value:** `5432` (standard)

### AZURE_PG_DATABASE
- **Type:** String
- **Required:** No
- **Default:** `postgres`
- **Used By:** Same files as AZURE_PG_HOST
- **Purpose:** PostgreSQL database name
- **Current Value:** `postgres`

### AZURE_PG_USER
- **Type:** String
- **Required:** Yes
- **Default:** `mhartigan` (in code, but shouldn't have default)
- **Used By:** Same files as AZURE_PG_HOST
- **Purpose:** PostgreSQL username
- **Current Value:** `mhartigan`
- **Security:** Sensitive credential

### AZURE_PG_PASSWORD
- **Type:** String (secret)
- **Required:** Yes
- **Default:** `Lalamoney3!` (in code - **CRITICAL SECURITY ISSUE**)
- **Used By:** Same files as AZURE_PG_HOST
- **Purpose:** PostgreSQL password
- **Current Value:** `Lalamoney3!`
- **Security:** ⚠️ **NEVER commit to git** - hardcoded in multiple files (security risk)

### AZURE_PG_SSLMODE
- **Type:** String
- **Required:** No
- **Default:** `require`
- **Used By:** `core/enterprise_rag.py:158`
- **Purpose:** PostgreSQL SSL connection mode
- **Options:** `disable`, `allow`, `prefer`, `require`, `verify-ca`, `verify-full`
- **Current Value:** `require`

### AZURE_PG_CONNECTION_STRING
- **Type:** Connection String
- **Required:** No (alternative to individual params)
- **Used By:**
  - `core/enterprise_rag.py:135`
  - `memory/backends/postgres.py` (referenced in comments)
- **Purpose:** Full PostgreSQL connection string
- **Format:** `postgresql://user:password@host:port/database?sslmode=require`
- **Notes:** If set, overrides individual connection params

---

## Frontend Configuration (Vite)

### VITE_API_URL
- **Type:** URL
- **Required:** **YES for production**
- **Default:** `http://localhost:8000` (development fallback)
- **Used By:**
  - `frontend/src/lib/stores/auth.ts:46`
  - `frontend/src/lib/stores/admin.ts`
  - `frontend/src/lib/stores/analytics.ts`
  - `frontend/src/lib/stores/websocket.ts`
- **Purpose:** Backend API base URL
- **Production Value:** `https://worthy-imagination-production.up.railway.app`
- **Status:** ❌ **MISSING in Railway** (causing SSO button to not render)
- **Impact:** Frontend can't detect Azure SSO enabled, falls back to email login
- **Fix:** Add to Railway environment variables and rebuild frontend

### How VITE_* Variables Work
1. **Build-time replacement:** Vite replaces `import.meta.env.VITE_*` with string literals during build
2. **Prefix requirement:** MUST start with `VITE_` to be exposed to frontend code
3. **Source:** Read from environment (Railway env vars) during `npm run build`
4. **Not runtime:** Baked into compiled JavaScript, not fetched at runtime
5. **Rebuild required:** Changes require re-running `npm run build`

---

## Application Configuration

### PORT (Backend)
- **Type:** Integer
- **Required:** No
- **Default:** `8000`
- **Used By:** `core/main.py` (FastAPI server)
- **Purpose:** Backend HTTP server port
- **Railway:** Auto-assigned via `$PORT` environment variable

### NODE_ENV (Frontend)
- **Type:** String
- **Required:** No
- **Default:** `development`
- **Used By:** Vite build process
- **Purpose:** Environment mode
- **Values:** `development`, `production`
- **Railway:** Automatically set to `production` during builds

---

## OpenAI / LLM Configuration

### OPENAI_API_KEY
- **Type:** String (secret)
- **Required:** Yes (for AI features)
- **Used By:**
  - `core/model_adapter.py`
  - `memory/embedder.py`
  - `memory/llm_tagger.py`
  - `memory/evolution_engine.py`
- **Purpose:** OpenAI API authentication
- **Security:** NEVER commit to git
- **Notes:** Used for embeddings and LLM completions

---

## Environment Variables Summary

### By Priority

| Variable | Priority | Status | Impact if Missing |
|----------|----------|--------|-------------------|
| `VITE_API_URL` | 🔴 CRITICAL | ❌ MISSING | SSO button doesn't render |
| `AZURE_AD_TENANT_ID` | 🔴 CRITICAL | ✅ SET | Azure SSO fails |
| `AZURE_AD_CLIENT_ID` | 🔴 CRITICAL | ✅ SET | Azure SSO fails |
| `AZURE_AD_CLIENT_SECRET` | 🔴 CRITICAL | ✅ SET | Azure SSO fails |
| `AZURE_PG_HOST` | 🔴 CRITICAL | ✅ SET | Database connection fails |
| `AZURE_PG_USER` | 🔴 CRITICAL | ✅ SET | Database auth fails |
| `AZURE_PG_PASSWORD` | 🔴 CRITICAL | ✅ SET | Database auth fails |
| `OPENAI_API_KEY` | 🟠 HIGH | ✅ SET | AI features fail |
| `AZURE_AD_REDIRECT_URI` | 🟡 MEDIUM | ⚠️ DEFAULT | Works with default |
| `AZURE_PG_DATABASE` | 🟡 MEDIUM | ⚠️ DEFAULT | Uses 'postgres' |
| `AZURE_PG_PORT` | 🟢 LOW | ⚠️ DEFAULT | Uses 5432 |
| `AZURE_PG_SSLMODE` | 🟢 LOW | ⚠️ DEFAULT | Uses 'require' |

### By Component

#### Backend (Python)
```bash
# Azure AD
AZURE_AD_TENANT_ID=...
AZURE_AD_CLIENT_ID=...
AZURE_AD_CLIENT_SECRET=...
AZURE_AD_REDIRECT_URI=https://your-domain.com/auth/callback

# Database
AZURE_PG_HOST=cogtwin.postgres.database.azure.com
AZURE_PG_PORT=5432
AZURE_PG_DATABASE=postgres
AZURE_PG_USER=mhartigan
AZURE_PG_PASSWORD=<secret>
AZURE_PG_SSLMODE=require

# AI
OPENAI_API_KEY=<secret>
```

#### Frontend (Vite/Svelte)
```bash
# API Connection
VITE_API_URL=https://worthy-imagination-production.up.railway.app
```

---

## Security Issues Found

### 🔴 CRITICAL: Hardcoded Credentials
**Location:** Multiple database config files
**Issue:** Default password `Lalamoney3!` hardcoded in:
- `auth/auth_schema.py:36`
- `auth/auth_service.py:57`
- `auth/tenant_service.py:51`
- `core/enterprise_rag.py:157`
- `db/install_pgvector.py:14`
- `db/run_migration_002.py:21`

**Risk:** If code is committed without env var override, password is exposed
**Recommendation:** Remove all default values for passwords

### 🟠 HIGH: Default Username
**Location:** Same files as password
**Issue:** Default username `mhartigan` hardcoded
**Risk:** Production systems might accidentally use default user
**Recommendation:** Make required, no default

---

## Railway Configuration

### Current Status
| Variable | Railway Backend | Railway Frontend | Status |
|----------|----------------|------------------|--------|
| `AZURE_AD_TENANT_ID` | ✅ Set | N/A | Working |
| `AZURE_AD_CLIENT_ID` | ✅ Set | N/A | Working |
| `AZURE_AD_CLIENT_SECRET` | ✅ Set | N/A | Working |
| `AZURE_AD_REDIRECT_URI` | ⚠️ Default? | N/A | Check |
| `AZURE_PG_*` | ✅ Set | N/A | Working |
| `OPENAI_API_KEY` | ✅ Set | N/A | Working |
| **`VITE_API_URL`** | N/A | ❌ **MISSING** | **BROKEN** |

### Immediate Fix Required
```bash
# Add to Railway Frontend Environment Variables:
VITE_API_URL=https://worthy-imagination-production.up.railway.app

# Then trigger rebuild:
railway up frontend
```

---

## Development vs Production

### Development (.env)
```bash
# Backend runs on localhost:8000
# Frontend runs on localhost:5173

VITE_API_URL=http://localhost:8000
AZURE_AD_REDIRECT_URI=http://localhost:5173/auth/callback
```

### Production (Railway)
```bash
# Backend on Railway-assigned domain
# Frontend on Railway-assigned domain or custom domain

VITE_API_URL=https://worthy-imagination-production.up.railway.app
AZURE_AD_REDIRECT_URI=https://worthy-imagination-production.up.railway.app/auth/callback
```

---

## Validation Checklist

### Before Deploying
- [ ] `VITE_API_URL` points to correct backend URL
- [ ] `AZURE_AD_REDIRECT_URI` matches frontend callback URL
- [ ] `AZURE_AD_REDIRECT_URI` is registered in Azure AD app
- [ ] All Azure AD credentials are set
- [ ] All database credentials are set
- [ ] No passwords in git history
- [ ] OpenAI API key is set (if using AI features)

### After Deploying
- [ ] Frontend can fetch `/api/auth/config` successfully
- [ ] SSO button renders on login page
- [ ] Microsoft login redirects correctly
- [ ] Callback URL matches Azure app registration
- [ ] Database connections work
- [ ] No CORS errors in browser console

---

**END OF ENVIRONMENT REQUIREMENTS**
