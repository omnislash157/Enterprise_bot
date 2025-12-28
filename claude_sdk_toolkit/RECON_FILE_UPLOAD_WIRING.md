# Multi-Tenant Domain Routing Implementation

AZURE_PG_USER=mhartigan
AZURE_PG_PASSWORD=Lalamoney3!  
AZURE_PG_HOST=cogtwin.postgres.database.azure.com
AZURE_PG_PORT=5432
AZURE_PG_DATABASE=postgres
AZURE_PG_SSLMODE=require
AZURE_PG_CONNECTION_STRING=postgresql://mhartigan:Lalamoney3%21@enterprisebot.postgres.database.azure.com:5432/postgres?sslmode=require

**Handoff Document for Claude Code SDK Agent**  
**Priority:** Medium (backlog until domain setup complete)  
**Estimated Effort:** 4-6 hours  
**Date:** 2025-12-28

---

## Executive Summary

Implement domain-based multi-tenancy so the same Railway deployment serves multiple customers:
- `driscollintel.com` → Driscoll Foods tenant
- `acme.entintel.com` → Acme Corp tenant (subdomain model)
- `entintel.com` → Platform landing/login

**Good news:** Database schema already supports this. `enterprise.tenants` table exists with `domain` column, and `users.tenant_id` FK is in place.

---

## Current State

### Database (READY ✅)

```sql
-- enterprise.tenants (already exists)
CREATE TABLE enterprise.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(50) UNIQUE NOT NULL,      -- 'driscoll', 'acme'
    name VARCHAR(255) NOT NULL,            -- 'Driscoll Foods'
    domain VARCHAR(255) NOT NULL,          -- 'driscollintel.com'
    created_at TIMESTAMPTZ DEFAULT now()
);

-- enterprise.users.tenant_id (already exists)
ALTER TABLE enterprise.users 
ADD COLUMN tenant_id UUID REFERENCES enterprise.tenants(id);
```

### Backend Files (EXIST, NEED EXTENSION)

| File | Current State | Needs |
|------|---------------|-------|
| `core/enterprise_tenant.py` | TenantContext dataclass exists | Extend with azure_tenant_id |
| `auth/tenant_service.py` | Department/division logic | Add domain lookup |
| `auth/azure_auth.py` | Single Azure AD tenant | Multi-tenant validation |
| `auth/sso_routes.py` | OAuth flow | Dynamic redirect URIs |
| `core/main.py` | FastAPI app | Add tenant middleware |

### Frontend Files (NEED NEW STORE)

| File | Needs |
|------|-------|
| `lib/stores/tenant.ts` | NEW - tenant context store |
| `lib/stores/auth.ts` | Include tenant_id in user |
| `src/routes/+layout.svelte` | Fetch tenant on load |

---

## Implementation Plan

### Phase 1: Database Schema Extension

Add Azure AD tenant ID to tenants table:

```sql
-- Migration: Add azure_tenant_id for per-tenant SSO
ALTER TABLE enterprise.tenants 
ADD COLUMN azure_tenant_id VARCHAR(100),
ADD COLUMN azure_client_id VARCHAR(100),
ADD COLUMN azure_client_secret_ref VARCHAR(255),  -- Secret manager ref, not raw secret
ADD COLUMN branding JSONB DEFAULT '{}',           -- {logo_url, primary_color, etc}
ADD COLUMN is_active BOOLEAN DEFAULT true;

-- Add unique index on domain
CREATE UNIQUE INDEX idx_tenants_domain ON enterprise.tenants(domain);

-- Insert Driscoll as first tenant
INSERT INTO enterprise.tenants (slug, name, domain, azure_tenant_id, azure_client_id)
VALUES (
    'driscoll',
    'Driscoll Foods',
    'driscollintel.com',
    '67de5fcd-a0e9-447d-9f28-e613d82a68eb',  -- From current env
    '6bd5e110-a031-46e3-b62...'               -- From current env
);

-- Link existing users to Driscoll tenant
UPDATE enterprise.users 
SET tenant_id = (SELECT id FROM enterprise.tenants WHERE slug = 'driscoll')
WHERE tenant_id IS NULL;
```

---

### Phase 2: Backend Middleware

#### 2.1 Create `core/tenant_middleware.py`

```python
"""
Tenant Resolution Middleware
Resolves domain -> tenant on every request, injects into request.state
"""
from fastapi import Request, HTTPException
from typing import Optional
import asyncpg

from core.enterprise_tenant import TenantContext
from core.config_loader import cfg


async def get_tenant_by_domain(domain: str, pool: asyncpg.Pool) -> Optional[dict]:
    """Lookup tenant by domain (exact match or wildcard subdomain)."""
    # Try exact match first
    row = await pool.fetchrow(
        """
        SELECT id, slug, name, domain, azure_tenant_id, azure_client_id, 
               azure_client_secret_ref, branding, is_active
        FROM enterprise.tenants 
        WHERE domain = $1 AND is_active = true
        """,
        domain
    )
    
    if row:
        return dict(row)
    
    # Try subdomain match (*.entintel.com)
    if '.' in domain:
        parts = domain.split('.')
        if len(parts) >= 2:
            base_domain = '.'.join(parts[-2:])  # entintel.com
            row = await pool.fetchrow(
                """
                SELECT id, slug, name, domain, azure_tenant_id, azure_client_id,
                       azure_client_secret_ref, branding, is_active
                FROM enterprise.tenants 
                WHERE domain = $1 AND is_active = true
                """,
                f"*.{base_domain}"
            )
            if row:
                result = dict(row)
                # Override slug with subdomain
                result['slug'] = parts[0]
                return result
    
    return None


async def tenant_middleware(request: Request, call_next):
    """
    Middleware to resolve tenant from Host header.
    Sets request.state.tenant with TenantContext or None.
    """
    host = request.headers.get("host", "").split(":")[0]  # Remove port
    
    # Skip for health checks
    if request.url.path in ["/health", "/api/health"]:
        return await call_next(request)
    
    # Get DB pool from app state
    pool = request.app.state.db_pool
    
    tenant_data = await get_tenant_by_domain(host, pool)
    
    if tenant_data:
        request.state.tenant = TenantContext(
            tenant_id=str(tenant_data['id']),
            slug=tenant_data['slug'],
            name=tenant_data['name'],
            domain=tenant_data['domain'],
            azure_tenant_id=tenant_data.get('azure_tenant_id'),
            azure_client_id=tenant_data.get('azure_client_id'),
            branding=tenant_data.get('branding', {}),
        )
    else:
        # No tenant found - could be platform domain or unknown
        request.state.tenant = None
    
    return await call_next(request)


def get_current_tenant(request: Request) -> TenantContext:
    """Dependency to get current tenant, raises if not found."""
    tenant = getattr(request.state, 'tenant', None)
    if not tenant:
        raise HTTPException(status_code=400, detail="Unknown tenant domain")
    return tenant


def get_optional_tenant(request: Request) -> Optional[TenantContext]:
    """Dependency to get tenant, returns None if not found."""
    return getattr(request.state, 'tenant', None)
```

#### 2.2 Update `core/enterprise_tenant.py`

```python
"""
Extended TenantContext with Azure AD config
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class TenantContext:
    tenant_id: str
    slug: str
    name: str
    domain: str
    azure_tenant_id: Optional[str] = None
    azure_client_id: Optional[str] = None
    branding: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_azure_sso(self) -> bool:
        return bool(self.azure_tenant_id and self.azure_client_id)
```

#### 2.3 Update `core/main.py`

Add middleware registration:

```python
# In main.py, after app creation

from core.tenant_middleware import tenant_middleware

# Add tenant middleware (before auth middleware)
app.middleware("http")(tenant_middleware)
```

---

### Phase 3: Auth Integration

#### 3.1 Update `auth/azure_auth.py`

Modify to use tenant-specific Azure config:

```python
# Current: Uses single env vars
# AZURE_AD_TENANT_ID, AZURE_AD_CLIENT_ID, AZURE_AD_CLIENT_SECRET

# New: Accept tenant context, fall back to env for backward compat

def get_azure_config(tenant: Optional[TenantContext] = None) -> dict:
    """Get Azure AD config for tenant, or default from env."""
    if tenant and tenant.has_azure_sso:
        # Get secret from secret manager using tenant.azure_client_secret_ref
        client_secret = get_secret(tenant.azure_client_secret_ref)  # Implement this
        return {
            'tenant_id': tenant.azure_tenant_id,
            'client_id': tenant.azure_client_id,
            'client_secret': client_secret,
        }
    
    # Fall back to env vars (backward compat)
    return {
        'tenant_id': os.getenv('AZURE_AD_TENANT_ID'),
        'client_id': os.getenv('AZURE_AD_CLIENT_ID'),
        'client_secret': os.getenv('AZURE_AD_CLIENT_SECRET'),
    }


def build_auth_url(tenant: Optional[TenantContext], redirect_uri: str) -> str:
    """Build Microsoft auth URL for tenant."""
    config = get_azure_config(tenant)
    
    # Use tenant-specific or common endpoint
    authority = f"https://login.microsoftonline.com/{config['tenant_id']}"
    
    params = {
        'client_id': config['client_id'],
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': 'openid profile email',
        'state': generate_state(),
    }
    
    return f"{authority}/oauth2/v2.0/authorize?{urlencode(params)}"
```

#### 3.2 Update `auth/sso_routes.py`

Dynamic redirect URI based on request host:

```python
@router.get("/api/auth/login-url")
async def get_login_url(request: Request):
    tenant = get_optional_tenant(request)
    
    # Build redirect URI from current host
    host = request.headers.get("host")
    scheme = "https" if request.url.scheme == "https" else "http"
    redirect_uri = f"{scheme}://{host}/auth/callback"
    
    url = build_auth_url(tenant, redirect_uri)
    state = extract_state_from_url(url)
    
    return {"url": url, "state": state}


@router.post("/api/auth/callback")
async def auth_callback(request: Request, data: CallbackData):
    tenant = get_optional_tenant(request)
    
    # Validate with tenant-specific Azure config
    config = get_azure_config(tenant)
    
    # ... rest of callback logic, using config
```

---

### Phase 4: Query Scoping

All data queries need tenant filtering:

#### 4.1 Update `auth/auth_service.py`

```python
async def get_user_by_email(email: str, tenant_id: Optional[str] = None) -> Optional[User]:
    """Get user, optionally scoped to tenant."""
    query = "SELECT * FROM enterprise.users WHERE email = $1"
    params = [email]
    
    if tenant_id:
        query += " AND tenant_id = $2"
        params.append(tenant_id)
    
    row = await pool.fetchrow(query, *params)
    return User(**row) if row else None


async def list_users(tenant_id: str, department: Optional[str] = None) -> List[User]:
    """List users for tenant."""
    query = "SELECT * FROM enterprise.users WHERE tenant_id = $1"
    params = [tenant_id]
    
    if department:
        query += " AND $2 = ANY(department_access)"
        params.append(department)
    
    rows = await pool.fetch(query, *params)
    return [User(**r) for r in rows]
```

#### 4.2 Update RAG queries in `core/enterprise_rag.py`

```python
async def search_documents(
    query: str, 
    tenant_id: str,  # NEW required param
    departments: List[str],
    limit: int = 10
) -> List[Document]:
    """Search documents scoped to tenant."""
    # Add tenant filter to all document queries
    # Note: May need to add tenant_id to documents table if not already scoped
```

---

### Phase 5: Frontend Integration

#### 5.1 Create `lib/stores/tenant.ts`

```typescript
/**
 * Tenant Store - Current tenant context from domain
 */
import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

interface Tenant {
    tenant_id: string;
    slug: string;
    name: string;
    domain: string;
    branding: {
        logo_url?: string;
        primary_color?: string;
        accent_color?: string;
    };
    has_azure_sso: boolean;
}

interface TenantState {
    tenant: Tenant | null;
    loading: boolean;
    error: string | null;
}

function createTenantStore() {
    const { subscribe, set, update } = writable<TenantState>({
        tenant: null,
        loading: true,
        error: null,
    });

    return {
        subscribe,

        async load() {
            if (!browser) return;

            try {
                const apiBase = import.meta.env.VITE_API_URL || '';
                const res = await fetch(`${apiBase}/api/tenant`);

                if (res.ok) {
                    const tenant = await res.json();
                    set({ tenant, loading: false, error: null });
                } else if (res.status === 400) {
                    // Unknown domain
                    set({ tenant: null, loading: false, error: 'Unknown domain' });
                } else {
                    set({ tenant: null, loading: false, error: 'Failed to load tenant' });
                }
            } catch (e) {
                set({ tenant: null, loading: false, error: String(e) });
            }
        },
    };
}

export const tenant = createTenantStore();

// Derived stores
export const currentTenant = derived(tenant, $t => $t.tenant);
export const tenantLoading = derived(tenant, $t => $t.loading);
export const tenantBranding = derived(tenant, $t => $t.tenant?.branding || {});
```

#### 5.2 Update `src/routes/+layout.svelte`

```svelte
<script lang="ts">
    import { onMount } from 'svelte';
    import { tenant } from '$lib/stores/tenant';
    import { auth } from '$lib/stores/auth';

    onMount(async () => {
        // Load tenant first (determines auth config)
        await tenant.load();
        
        // Then init auth
        await auth.init();
    });
</script>
```

#### 5.3 Add tenant endpoint in backend

```python
# In auth/sso_routes.py or new tenant_routes.py

@router.get("/api/tenant")
async def get_tenant(request: Request):
    """Return current tenant info based on domain."""
    tenant = get_optional_tenant(request)
    
    if not tenant:
        raise HTTPException(status_code=400, detail="Unknown domain")
    
    return {
        "tenant_id": tenant.tenant_id,
        "slug": tenant.slug,
        "name": tenant.name,
        "domain": tenant.domain,
        "branding": tenant.branding,
        "has_azure_sso": tenant.has_azure_sso,
    }
```

---

## Azure Portal Setup Per Tenant

For each new tenant with custom Azure AD:

1. **Register App in their Azure AD:**
   - App registrations → New registration
   - Name: "EntIntel - {TenantName}"
   - Redirect URIs: `https://{domain}/auth/callback`

2. **Store credentials securely:**
   - Client ID → `tenants.azure_client_id`
   - Client Secret → Azure Key Vault → `tenants.azure_client_secret_ref`
   - Tenant ID → `tenants.azure_tenant_id`

3. **Update tenants table:**
   ```sql
   INSERT INTO enterprise.tenants (slug, name, domain, azure_tenant_id, azure_client_id, azure_client_secret_ref)
   VALUES ('acme', 'Acme Corp', 'acme.entintel.com', '...', '...', 'keyvault://acme-client-secret');
   ```

---

## Testing Checklist

- [ ] Domain resolution: `driscollintel.com` → correct tenant
- [ ] Subdomain resolution: `acme.entintel.com` → correct tenant  
- [ ] Unknown domain → graceful error
- [ ] Auth flow with tenant-specific Azure AD
- [ ] User queries scoped to tenant
- [ ] Document queries scoped to tenant
- [ ] WebSocket connections include tenant context
- [ ] Admin panel shows only tenant users

---

## Rollback Plan

If issues arise:
1. Remove tenant middleware from `main.py`
2. Auth falls back to env vars (existing behavior)
3. No data migration needed (tenant_id nullable)

---

## Files to Modify Summary

### Backend (enterprise_bot/)
| File | Action |
|------|--------|
| `core/tenant_middleware.py` | CREATE |
| `core/enterprise_tenant.py` | EXTEND |
| `core/main.py` | ADD middleware |
| `auth/azure_auth.py` | EXTEND for multi-tenant |
| `auth/sso_routes.py` | Dynamic redirect URIs |
| `auth/auth_service.py` | Tenant-scoped queries |
| `core/enterprise_rag.py` | Tenant-scoped search |

### Frontend (cogtwin-frontend/)
| File | Action |
|------|--------|
| `lib/stores/tenant.ts` | CREATE |
| `lib/stores/auth.ts` | Include tenant context |
| `routes/+layout.svelte` | Load tenant on mount |

### Database
| Change | SQL |
|--------|-----|
| Extend tenants table | See Phase 1 migration |
| Insert Driscoll tenant | See Phase 1 |

---

## Notes for SDK Agent

1. **Start with database migration** - everything else depends on it
2. **Middleware must be early** - before auth middleware
3. **Backward compatible** - env vars still work if no tenant found
4. **Test with current domain first** - `driscollintel.com` before adding others
5. **Secret management** - don't store raw client secrets in DB, use Key Vault refs

---

**END OF HANDOFF**