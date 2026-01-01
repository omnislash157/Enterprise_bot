# Feature Build Sheet: Tenant-Based Frontend Architecture

## Feature: TENANT_ROUTING
**Priority:** P0 (BLOCKER - Cogzy launch depends on this)  
**Estimated Complexity:** High  
**Dependencies:** None (foundational)

---

## 1. OVERVIEW

### User Story
> As a user visiting cogzy.ai, I see personal login (Google/Email).
> As an enterprise user visiting sysco.cogzy.ai, I see enterprise login (Azure AD) with Sysco branding.
> As a Driscoll user visiting driscollintel.com, I see only Azure AD with Driscoll branding.

### Acceptance Criteria
- [ ] cogzy.ai shows personal login with Google + Email options
- [ ] *.cogzy.ai subdomains load enterprise mode with tenant from subdomain
- [ ] driscollintel.com loads Driscoll directly (Azure AD only)
- [ ] Each tenant loads branding from their YAML config
- [ ] CSS theme hook works for custom client styling
- [ ] Features not listed in YAML don't appear in UI

---

## 2. FILE STRUCTURE

### New Directories
```
bot/
├── clients/                    # NEW - tenant configurations
│   ├── _base.yaml             # Enterprise defaults
│   ├── _personal.yaml         # Cogzy personal defaults
│   ├── driscoll.yaml          # Driscoll config
│   └── [future_clients].yaml

frontend/
├── cogzy/                     # NEW - personal frontend
│   ├── src/
│   │   ├── routes/
│   │   │   ├── +layout.svelte
│   │   │   ├── +page.svelte
│   │   │   └── login/+page.svelte
│   │   └── lib/
│   │       ├── stores/
│   │       │   └── personalAuth.ts
│   │       └── components/
│   │           └── PersonalLogin.svelte
│   ├── static/
│   └── package.json
│
├── enterprise/                # RENAMED from current frontend
│   ├── src/
│   │   ├── routes/
│   │   │   ├── +layout.svelte  # Tenant-aware
│   │   │   └── login/+page.svelte
│   │   └── lib/
│   │       ├── stores/
│   │       │   ├── tenant.ts   # Loads tenant config
│   │       │   └── auth.ts
│   │       └── components/
│   │           └── EnterpriseLogin.svelte
│   ├── static/
│   │   └── assets/
│   │       └── clients/        # Per-client assets
│   │           ├── driscoll/
│   │           │   ├── logo.svg
│   │           │   └── theme.css
│   │           └── sysco/
│   │               └── logo.svg
│   └── package.json
```

---

## 3. BACKEND CHANGES

### File: bot/clients/_base.yaml
```yaml
# Enterprise Client Base Configuration
# Features NOT listed here do not exist for the client
# No need to set features: false - just omit them

auth:
  azure_ad: true
  google: false
  email: false

branding:
  logo: null
  primary_color: "#6366f1"
  theme_css: null

rls:
  enabled: true
```

### File: bot/clients/_personal.yaml
```yaml
# Cogzy Personal Tier Configuration
mode: personal
name: "Cogzy"

auth:
  google: true
  email: true
  azure_ad: false

features:
  memory_search: true
  voice_mode: true
  chat_export: true
  file_upload: true

branding:
  logo: /assets/cogzy-logo.svg
  primary_color: "#8b5cf6"
  tagline: "Your cognitive companion"
```

### File: bot/clients/driscoll.yaml
```yaml
tenant_id: "REPLACE_WITH_ACTUAL_UUID"
slug: driscoll
name: "Driscoll Intelligence"
domain: driscollintel.com
subdomain: null

auth:
  azure_ad: true
  # google: omitted = disabled
  # email: omitted = disabled

features:
  credit_page: true
  analytics: true
  department_switching: true
  custom_reports: true
  api_access: true

branding:
  logo: /assets/clients/driscoll/logo.svg
  primary_color: "#00ff00"
  theme_css: /assets/clients/driscoll/theme.css

tables:
  - enterprise.documents
  - enterprise.query_log
  - enterprise.users
  - enterprise.analytics_events
  - enterprise.audit_log
```

### File: bot/core/tenant_loader.py
```python
"""
Tenant Configuration Loader

Loads tenant configs from YAML files in bot/clients/
Merges with _base.yaml for enterprise clients.
"""

from pathlib import Path
from typing import Optional
import yaml
from functools import lru_cache

CLIENTS_DIR = Path(__file__).parent.parent / "clients"


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base, override wins."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@lru_cache(maxsize=32)
def load_base() -> dict:
    """Load enterprise base config."""
    base_file = CLIENTS_DIR / "_base.yaml"
    if not base_file.exists():
        return {}
    with open(base_file) as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=32)
def load_personal() -> dict:
    """Load personal tier config."""
    personal_file = CLIENTS_DIR / "_personal.yaml"
    if not personal_file.exists():
        raise FileNotFoundError("_personal.yaml not found")
    with open(personal_file) as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=32)
def load_tenant(slug: str) -> dict:
    """Load tenant config by slug, merged with base."""
    tenant_file = CLIENTS_DIR / f"{slug}.yaml"
    
    if not tenant_file.exists():
        raise ValueError(f"Unknown tenant: {slug}")
    
    with open(tenant_file) as f:
        tenant = yaml.safe_load(f)
    
    base = load_base()
    return deep_merge(base, tenant)


def get_tenant_by_domain(domain: str) -> Optional[dict]:
    """Find tenant by custom domain."""
    for yaml_file in CLIENTS_DIR.glob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue
        with open(yaml_file) as f:
            tenant = yaml.safe_load(f)
            if tenant and tenant.get("domain") == domain:
                return load_tenant(tenant["slug"])
    return None


def get_tenant_by_subdomain(subdomain: str) -> Optional[dict]:
    """Find tenant by subdomain (e.g., 'sysco' from sysco.cogzy.ai)."""
    for yaml_file in CLIENTS_DIR.glob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue
        with open(yaml_file) as f:
            tenant = yaml.safe_load(f)
            if tenant and tenant.get("subdomain") == subdomain:
                return load_tenant(tenant["slug"])
    return None


def resolve_tenant(host: str) -> dict:
    """
    Resolve tenant from request host.
    
    Logic:
    1. cogzy.ai (exact) -> personal config
    2. *.cogzy.ai -> extract subdomain -> enterprise tenant
    3. custom domain -> enterprise tenant by domain
    4. fallback -> personal config
    """
    host = host.lower().split(":")[0]  # Remove port if present
    
    # Exact match: cogzy.ai
    if host == "cogzy.ai":
        return load_personal()
    
    # Subdomain: xxx.cogzy.ai
    if host.endswith(".cogzy.ai"):
        subdomain = host.replace(".cogzy.ai", "")
        tenant = get_tenant_by_subdomain(subdomain)
        if tenant:
            return tenant
        # Unknown subdomain, fall back to personal
        return load_personal()
    
    # Custom domain lookup
    tenant = get_tenant_by_domain(host)
    if tenant:
        return tenant
    
    # Fallback: treat as personal
    return load_personal()


def clear_cache():
    """Clear LRU caches (call after YAML changes in dev)."""
    load_base.cache_clear()
    load_personal.cache_clear()
    load_tenant.cache_clear()
```

### File: bot/core/tenant_routes.py
```python
"""
Tenant API Routes

Provides tenant configuration to frontend.
"""

from fastapi import APIRouter, Request
from core.tenant_loader import resolve_tenant

router = APIRouter(prefix="/api/tenant", tags=["tenant"])


@router.get("/config")
async def get_tenant_config(request: Request):
    """
    Return tenant configuration based on request origin.
    
    Frontend calls this on load to determine:
    - Which auth methods to show
    - What branding to use
    - Which features are enabled
    """
    # Get host from Origin header (CORS) or Host header
    origin = request.headers.get("origin", "")
    if origin:
        # Extract host from origin (https://cogzy.ai -> cogzy.ai)
        host = origin.replace("https://", "").replace("http://", "")
    else:
        host = request.headers.get("host", "cogzy.ai")
    
    tenant = resolve_tenant(host)
    
    # Return safe subset (don't expose tenant_id, tables, etc.)
    return {
        "mode": tenant.get("mode", "enterprise"),
        "name": tenant.get("name"),
        "slug": tenant.get("slug"),
        "auth": tenant.get("auth", {}),
        "features": tenant.get("features", {}),
        "branding": tenant.get("branding", {})
    }
```

### Wire into main.py
```python
# Add import
from core.tenant_routes import router as tenant_router

# Add router (near other router registrations)
app.include_router(tenant_router)
logger.info("[STARTUP] Tenant routes loaded at /api/tenant")
```

---

## 4. FRONTEND CHANGES - ENTERPRISE

### File: frontend/enterprise/src/lib/stores/tenant.ts
```typescript
import { writable, derived } from 'svelte/store';

const API_URL = import.meta.env.VITE_API_URL || '';

export interface TenantConfig {
    mode: 'personal' | 'enterprise';
    name: string;
    slug?: string;
    auth: {
        azure_ad?: boolean;
        google?: boolean;
        email?: boolean;
    };
    features: Record<string, boolean>;
    branding: {
        logo?: string;
        primary_color?: string;
        theme_css?: string;
        tagline?: string;
    };
}

// Default while loading
const defaultTenant: TenantConfig = {
    mode: 'enterprise',
    name: 'Loading...',
    auth: {},
    features: {},
    branding: {}
};

export const tenant = writable<TenantConfig>(defaultTenant);
export const tenantLoaded = writable(false);
export const tenantError = writable<string | null>(null);

// Derived helpers
export const isPersonalMode = derived(tenant, $t => $t.mode === 'personal');
export const isEnterpriseMode = derived(tenant, $t => $t.mode === 'enterprise');

export const hasFeature = (feature: string) => derived(tenant, $t => 
    $t.features[feature] === true
);

export const authMethods = derived(tenant, $t => ({
    azureAd: $t.auth.azure_ad === true,
    google: $t.auth.google === true,
    email: $t.auth.email === true
}));

// Load tenant config from API
export async function loadTenant(): Promise<void> {
    try {
        const res = await fetch(`${API_URL}/api/tenant/config`, {
            credentials: 'include'
        });
        
        if (!res.ok) {
            throw new Error(`Failed to load tenant: ${res.status}`);
        }
        
        const config = await res.json();
        tenant.set(config);
        tenantLoaded.set(true);
        
        // Apply custom CSS if specified
        if (config.branding?.theme_css) {
            applyThemeCSS(config.branding.theme_css);
        }
        
        // Apply primary color as CSS variable
        if (config.branding?.primary_color) {
            document.documentElement.style.setProperty(
                '--color-primary', 
                config.branding.primary_color
            );
        }
        
    } catch (e) {
        tenantError.set(e instanceof Error ? e.message : 'Unknown error');
        console.error('[Tenant] Load failed:', e);
    }
}

// Apply custom theme CSS
function applyThemeCSS(cssPath: string): void {
    const existing = document.getElementById('tenant-theme');
    if (existing) {
        existing.remove();
    }
    
    const link = document.createElement('link');
    link.id = 'tenant-theme';
    link.rel = 'stylesheet';
    link.href = cssPath;
    document.head.appendChild(link);
}
```

### File: frontend/enterprise/src/routes/+layout.svelte
```svelte
<script lang="ts">
    import { onMount } from 'svelte';
    import { tenant, tenantLoaded, loadTenant, authMethods } from '$lib/stores/tenant';
    import { isAuthenticated } from '$lib/stores/auth';
    import EnterpriseLogin from '$lib/components/EnterpriseLogin.svelte';
    import Nav from '$lib/components/Nav.svelte';
    import '../app.css';
    
    onMount(async () => {
        await loadTenant();
    });
</script>

<svelte:head>
    <title>{$tenant.name}</title>
    {#if $tenant.branding?.logo}
        <link rel="icon" href={$tenant.branding.logo} />
    {/if}
</svelte:head>

{#if !$tenantLoaded}
    <!-- Loading state -->
    <div class="loading-container">
        <div class="spinner"></div>
    </div>
{:else if !$isAuthenticated}
    <!-- Show login based on tenant config -->
    <EnterpriseLogin 
        tenantName={$tenant.name}
        logo={$tenant.branding?.logo}
        primaryColor={$tenant.branding?.primary_color}
        showAzureAd={$authMethods.azureAd}
        showGoogle={$authMethods.google}
        showEmail={$authMethods.email}
    />
{:else}
    <!-- Authenticated: show app -->
    <Nav />
    <main>
        <slot />
    </main>
{/if}

<style>
    :global(:root) {
        --color-primary: #6366f1; /* Default, overridden by tenant */
    }
    
    .loading-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100vh;
        background: #0a0a0f;
    }
    
    .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid rgba(255,255,255,0.1);
        border-top-color: var(--color-primary);
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
</style>
```

### File: frontend/enterprise/src/lib/components/EnterpriseLogin.svelte
```svelte
<script lang="ts">
    export let tenantName: string;
    export let logo: string | undefined;
    export let primaryColor: string | undefined;
    export let showAzureAd: boolean = false;
    export let showGoogle: boolean = false;
    export let showEmail: boolean = false;
    
    const API_URL = import.meta.env.VITE_API_URL || '';
    
    function loginAzure() {
        window.location.href = `${API_URL}/api/auth/azure/login`;
    }
    
    function loginGoogle() {
        window.location.href = `${API_URL}/api/auth/google/login`;
    }
</script>

<div class="login-container" style="--primary: {primaryColor || '#6366f1'}">
    <div class="login-card">
        {#if logo}
            <img src={logo} alt="{tenantName} logo" class="logo" />
        {/if}
        
        <h1>{tenantName}</h1>
        <p class="subtitle">Sign in to continue</p>
        
        <div class="auth-buttons">
            {#if showAzureAd}
                <button class="auth-btn azure" on:click={loginAzure}>
                    <svg class="icon" viewBox="0 0 23 23">
                        <path fill="currentColor" d="M11 0H0v11h11V0zm12 0H12v11h11V0zM11 12H0v11h11V12zm12 0H12v11h11V12z"/>
                    </svg>
                    Sign in with Microsoft
                </button>
            {/if}
            
            {#if showGoogle}
                <button class="auth-btn google" on:click={loginGoogle}>
                    <svg class="icon" viewBox="0 0 24 24">
                        <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                        <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                        <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                        <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                    </svg>
                    Sign in with Google
                </button>
            {/if}
            
            {#if showEmail}
                <a href="/login/email" class="auth-btn email">
                    <svg class="icon" viewBox="0 0 24 24">
                        <path fill="currentColor" d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
                    </svg>
                    Sign in with Email
                </a>
            {/if}
        </div>
    </div>
</div>

<style>
    .login-container {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
    }
    
    .login-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px;
        padding: 3rem;
        text-align: center;
        max-width: 400px;
        width: 90%;
    }
    
    .logo {
        width: 64px;
        height: 64px;
        margin-bottom: 1.5rem;
    }
    
    h1 {
        color: white;
        font-size: 1.75rem;
        margin: 0 0 0.5rem;
    }
    
    .subtitle {
        color: rgba(255,255,255,0.6);
        margin: 0 0 2rem;
    }
    
    .auth-buttons {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }
    
    .auth-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        padding: 0.875rem 1.5rem;
        border-radius: 8px;
        font-size: 1rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        text-decoration: none;
        border: none;
    }
    
    .auth-btn .icon {
        width: 20px;
        height: 20px;
    }
    
    .auth-btn.azure {
        background: var(--primary);
        color: white;
    }
    
    .auth-btn.azure:hover {
        filter: brightness(1.1);
    }
    
    .auth-btn.google {
        background: white;
        color: #333;
    }
    
    .auth-btn.google:hover {
        background: #f5f5f5;
    }
    
    .auth-btn.email {
        background: rgba(255,255,255,0.1);
        color: white;
        border: 1px solid rgba(255,255,255,0.2);
    }
    
    .auth-btn.email:hover {
        background: rgba(255,255,255,0.15);
    }
</style>
```

### File: frontend/enterprise/src/lib/components/Nav.svelte (feature-gated)
```svelte
<script lang="ts">
    import { tenant } from '$lib/stores/tenant';
    
    // Feature check helper
    $: features = $tenant.features || {};
</script>

<nav>
    <div class="nav-brand">
        {#if $tenant.branding?.logo}
            <img src={$tenant.branding.logo} alt="" class="nav-logo" />
        {/if}
        <span>{$tenant.name}</span>
    </div>
    
    <div class="nav-links">
        <a href="/chat">Chat</a>
        
        {#if features.department_switching}
            <a href="/departments">Departments</a>
        {/if}
        
        {#if features.analytics}
            <a href="/analytics">Analytics</a>
        {/if}
        
        {#if features.credit_page}
            <a href="/credit">Credit</a>
        {/if}
        
        {#if features.custom_reports}
            <a href="/reports">Reports</a>
        {/if}
        
        <a href="/admin">Admin</a>
    </div>
</nav>

<style>
    nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 2rem;
        background: rgba(0,0,0,0.3);
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }
    
    .nav-brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        color: white;
        font-weight: 600;
    }
    
    .nav-logo {
        width: 32px;
        height: 32px;
    }
    
    .nav-links {
        display: flex;
        gap: 1.5rem;
    }
    
    .nav-links a {
        color: rgba(255,255,255,0.7);
        text-decoration: none;
        transition: color 0.2s;
    }
    
    .nav-links a:hover {
        color: white;
    }
</style>
```

---

## 5. FRONTEND CHANGES - COGZY PERSONAL

### File: frontend/cogzy/src/routes/login/+page.svelte
```svelte
<script lang="ts">
    import { goto } from '$app/navigation';
    
    const API_URL = import.meta.env.VITE_API_URL || '';
    
    let email = '';
    let password = '';
    let isLogin = true;
    let loading = false;
    let error = '';
    
    function loginGoogle() {
        window.location.href = `${API_URL}/api/personal/auth/google`;
    }
    
    async function handleEmailAuth() {
        loading = true;
        error = '';
        
        const endpoint = isLogin ? 'login' : 'register';
        
        try {
            const res = await fetch(`${API_URL}/api/personal/auth/${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ email, password })
            });
            
            const data = await res.json();
            
            if (!res.ok) {
                throw new Error(data.detail || 'Authentication failed');
            }
            
            goto('/');
        } catch (e) {
            error = e instanceof Error ? e.message : 'Something went wrong';
        } finally {
            loading = false;
        }
    }
</script>

<div class="login-container">
    <div class="login-card">
        <div class="logo-section">
            <img src="/cogzy-logo.svg" alt="Cogzy" class="logo" />
            <h1>Cogzy</h1>
            <p class="tagline">Your cognitive companion</p>
        </div>
        
        {#if error}
            <div class="error">{error}</div>
        {/if}
        
        <div class="auth-section">
            <button class="auth-btn google" on:click={loginGoogle}>
                <svg class="icon" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
            </button>
            
            <div class="divider">
                <span>or</span>
            </div>
            
            <form on:submit|preventDefault={handleEmailAuth}>
                <input 
                    type="email" 
                    bind:value={email}
                    placeholder="Email address"
                    required
                />
                <input 
                    type="password" 
                    bind:value={password}
                    placeholder="Password"
                    required
                    minlength="8"
                />
                <button type="submit" class="auth-btn email" disabled={loading}>
                    {loading ? 'Loading...' : (isLogin ? 'Sign In' : 'Create Account')}
                </button>
            </form>
            
            <button class="toggle-mode" on:click={() => isLogin = !isLogin}>
                {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
            </button>
        </div>
        
        <div class="enterprise-link">
            <p>Enterprise SSO?</p>
            <a href="/enterprise">Sign in with your organization</a>
        </div>
    </div>
</div>

<style>
    .login-container {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    }
    
    .login-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 20px;
        padding: 3rem;
        max-width: 420px;
        width: 90%;
    }
    
    .logo-section {
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .logo {
        width: 72px;
        height: 72px;
        margin-bottom: 1rem;
    }
    
    h1 {
        color: white;
        font-size: 2rem;
        margin: 0;
        background: linear-gradient(135deg, #8b5cf6, #6366f1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .tagline {
        color: rgba(255,255,255,0.5);
        margin: 0.5rem 0 0;
    }
    
    .error {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #fca5a5;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        font-size: 0.875rem;
    }
    
    .auth-section {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }
    
    .auth-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        padding: 0.875rem 1.5rem;
        border-radius: 10px;
        font-size: 1rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        border: none;
        width: 100%;
    }
    
    .auth-btn .icon {
        width: 20px;
        height: 20px;
    }
    
    .auth-btn.google {
        background: white;
        color: #333;
    }
    
    .auth-btn.google:hover {
        background: #f5f5f5;
        transform: translateY(-1px);
    }
    
    .auth-btn.email {
        background: linear-gradient(135deg, #8b5cf6, #6366f1);
        color: white;
    }
    
    .auth-btn.email:hover:not(:disabled) {
        filter: brightness(1.1);
        transform: translateY(-1px);
    }
    
    .auth-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }
    
    .divider {
        display: flex;
        align-items: center;
        gap: 1rem;
        color: rgba(255,255,255,0.3);
        font-size: 0.875rem;
    }
    
    .divider::before,
    .divider::after {
        content: '';
        flex: 1;
        height: 1px;
        background: rgba(255,255,255,0.1);
    }
    
    form {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }
    
    input {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 0.875rem 1rem;
        color: white;
        font-size: 1rem;
        transition: border-color 0.2s;
    }
    
    input::placeholder {
        color: rgba(255,255,255,0.4);
    }
    
    input:focus {
        outline: none;
        border-color: #8b5cf6;
    }
    
    .toggle-mode {
        background: none;
        border: none;
        color: rgba(255,255,255,0.5);
        font-size: 0.875rem;
        cursor: pointer;
        padding: 0.5rem;
    }
    
    .toggle-mode:hover {
        color: white;
    }
    
    .enterprise-link {
        margin-top: 2rem;
        padding-top: 1.5rem;
        border-top: 1px solid rgba(255,255,255,0.1);
        text-align: center;
    }
    
    .enterprise-link p {
        color: rgba(255,255,255,0.4);
        font-size: 0.875rem;
        margin: 0 0 0.5rem;
    }
    
    .enterprise-link a {
        color: #8b5cf6;
        text-decoration: none;
        font-size: 0.875rem;
    }
    
    .enterprise-link a:hover {
        text-decoration: underline;
    }
</style>
```

---

## 6. CSS THEMING HOOK

### File: frontend/enterprise/static/assets/clients/driscoll/theme.css
```css
/* Driscoll Custom Theme
 * This file is loaded dynamically based on tenant config
 * Override CSS variables and add custom styles here
 */

:root {
    --color-primary: #00ff00;
    --color-primary-dark: #00cc00;
    --color-background: #0a0f0a;
    --color-surface: rgba(0, 255, 0, 0.03);
    --color-border: rgba(0, 255, 0, 0.15);
}

/* Custom Driscoll styles */
.login-card {
    border-color: rgba(0, 255, 0, 0.2);
}

.nav-brand {
    color: var(--color-primary);
}

/* Add any Driscoll-specific overrides here */
```

### Marketing CSS Preview Page (v2 - just the hook for now)
```
Location: frontend/enterprise/src/routes/admin/theme-preview/+page.svelte
Purpose: Let clients preview CSS changes with live knobs
Status: Future build - just noting the hook exists
```

---

## 7. RAILWAY CONFIGURATION

### cozy-optimism (cogzy.ai)
```
Service: cozy-optimism
Domain: cogzy.ai
Root Directory: /frontend/cogzy
Build Command: npm run build
Start Command: npm run preview -- --host 0.0.0.0 --port $PORT

Environment:
  VITE_API_URL=https://enterprisebot-production.up.railway.app
```

### worthy-imagination (driscollintel.com)  
```
Service: worthy-imagination
Domain: driscollintel.com
Root Directory: /frontend/enterprise
Build Command: npm run build
Start Command: npm run preview -- --host 0.0.0.0 --port $PORT

Environment:
  VITE_API_URL=https://lucky-love-production.up.railway.app
  TENANT_SLUG=driscoll  # Optional: force tenant without API call
```

---

## 8. EXECUTION ORDER

### Phase 1: Backend (do first)
1. Create `bot/clients/` directory
2. Create `_base.yaml`, `_personal.yaml`, `driscoll.yaml`
3. Create `bot/core/tenant_loader.py`
4. Create `bot/core/tenant_routes.py`
5. Wire into `main.py`
6. Test: `curl https://enterprisebot-production.up.railway.app/api/tenant/config`

### Phase 2: Enterprise Frontend
1. Restructure current frontend → `/frontend/enterprise`
2. Create `tenant.ts` store
3. Update `+layout.svelte` to be tenant-aware
4. Create `EnterpriseLogin.svelte` component
5. Update `Nav.svelte` with feature gates
6. Add Driscoll assets and theme.css
7. Deploy to worthy-imagination

### Phase 3: Cogzy Personal Frontend  
1. Create `/frontend/cogzy` (can scaffold from enterprise)
2. Create personal login page with Google + Email
3. Wire to personal auth routes
4. Deploy to cozy-optimism

### Phase 4: Verify
1. Test cogzy.ai → personal login appears
2. Test driscollintel.com → Driscoll branding, Azure AD only
3. Test sysco.cogzy.ai → Sysco branding (once sysco.yaml exists)

---

## 9. ROLLBACK PLAN

Backend is additive (new files, new routes) - rollback = delete files.

Frontend rollback:
```bash
# Keep old frontend in /frontend/legacy for 1 week
git checkout HEAD~N -- frontend/  # Restore old frontend
```

---

## 10. VALIDATION CHECKLIST

- [ ] `GET /api/tenant/config` returns correct config for each domain
- [ ] cogzy.ai shows Google + Email login
- [ ] driscollintel.com shows Azure AD only
- [ ] driscollintel.com shows Driscoll branding
- [ ] Nav only shows features enabled in tenant config
- [ ] CSS theme hook loads custom stylesheet
- [ ] No enterprise features visible on personal tier
- [ ] No personal auth (Google/Email) visible on Driscoll

---

**END OF BUILD SHEET**