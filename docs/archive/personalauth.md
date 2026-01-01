# SDK MISSION: Complete Cogzy Frontend Scaffolding

**Agent Mode:** SINGLE AGENT - NO PARALLEL EXECUTION
**Priority:** P0 - Blocker for Cogzy launch
**Estimated Time:** 10 minutes

---

## CONTEXT

Claude Code parallel agents created the tenant routing system but left cogzy frontend incomplete:
- Missing SvelteKit config files
- Syntax error in login page
- Wrong path in tenant_loader.py

This mission completes the scaffolding with sequential, verified steps.

---

## PRE-FLIGHT CHECK

```bash
# Confirm you're in the right directory
pwd
# Should be: C:\Users\mthar\projects\enterprise_bot

# Confirm cogzy exists but is incomplete
ls frontend/cogzy/
ls frontend/enterprise/

# Confirm clients/ exists at root
ls clients/
```

---

## TASK 1: Fix tenant_loader.py Path

**File:** `core/tenant_loader.py`
**Line 11**

**Find:**
```python
CLIENTS_DIR = Path(__file__).parent.parent / "bot" / "clients"
```

**Replace with:**
```python
CLIENTS_DIR = Path(__file__).parent.parent / "clients"
```

**Verify:**
```bash
grep "CLIENTS_DIR" core/tenant_loader.py
```

---

## TASK 2: Fix Login Page Syntax Error

**File:** `frontend/cogzy/src/routes/login/+page.svelte`
**Around line 17**

**Find:**
```javascript
const res = await fetch`${API_URL}/api/personal/auth/${endpoint}`, {
```

**Replace with:**
```javascript
const res = await fetch(`${API_URL}/api/personal/auth/${endpoint}`, {
```

Note: Adding parentheses around the template literal.

---

## TASK 3: Copy SvelteKit Config Files

Copy these files from `frontend/enterprise/` to `frontend/cogzy/`:

```bash
cp frontend/enterprise/svelte.config.js frontend/cogzy/
cp frontend/enterprise/vite.config.ts frontend/cogzy/
cp frontend/enterprise/tsconfig.json frontend/cogzy/
cp frontend/enterprise/tailwind.config.js frontend/cogzy/
cp frontend/enterprise/postcss.config.js frontend/cogzy/
cp frontend/enterprise/src/app.html frontend/cogzy/src/
cp frontend/enterprise/src/app.css frontend/cogzy/src/
```

---

## TASK 4: Create Cogzy +layout.svelte

**Create file:** `frontend/cogzy/src/routes/+layout.svelte`

```svelte
<script lang="ts">
    import '../app.css';
</script>

<div class="app">
    <slot />
</div>

<style>
    .app {
        min-height: 100vh;
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    }
</style>
```

---

## TASK 5: Create Cogzy +page.svelte (Home/Redirect)

**Create file:** `frontend/cogzy/src/routes/+page.svelte`

```svelte
<script lang="ts">
    import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
    
    let checking = true;
    
    onMount(async () => {
        // Check if user is authenticated
        try {
            const API_URL = import.meta.env.VITE_API_URL || '';
            const res = await fetch(`${API_URL}/api/personal/auth/me`, {
                credentials: 'include'
            });
            
            if (res.ok) {
                // User is authenticated, go to chat
                goto('/chat');
            } else {
                // Not authenticated, go to login
                goto('/login');
            }
        } catch {
            // Error checking auth, go to login
            goto('/login');
        }
    });
</script>

{#if checking}
<div class="loading">
    <div class="spinner"></div>
    <p>Loading Cogzy...</p>
</div>
{/if}

<style>
    .loading {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100vh;
        color: white;
        gap: 1rem;
    }
    
    .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid rgba(255,255,255,0.1);
        border-top-color: #8b5cf6;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
</style>
```

---

## TASK 6: Create lib Directory Structure

```bash
mkdir -p frontend/cogzy/src/lib/stores
mkdir -p frontend/cogzy/src/lib/components
```

**Create file:** `frontend/cogzy/src/lib/stores/auth.ts`

```typescript
import { writable, derived } from 'svelte/store';

const API_URL = import.meta.env.VITE_API_URL || '';

export interface User {
    id: string;
    email: string;
    display_name?: string;
    avatar_url?: string;
}

export const user = writable<User | null>(null);
export const authLoading = writable(true);
export const isAuthenticated = derived(user, $user => $user !== null);

export async function checkAuth(): Promise<boolean> {
    authLoading.set(true);
    try {
        const res = await fetch(`${API_URL}/api/personal/auth/me`, {
            credentials: 'include'
        });
        
        if (res.ok) {
            const data = await res.json();
            user.set(data.user);
            return true;
        } else {
            user.set(null);
            return false;
        }
    } catch {
        user.set(null);
        return false;
    } finally {
        authLoading.set(false);
    }
}

export async function logout(): Promise<void> {
    try {
        await fetch(`${API_URL}/api/personal/auth/logout`, {
            method: 'POST',
            credentials: 'include'
        });
    } finally {
        user.set(null);
    }
}
```

---

## TASK 7: Add Static Assets

**Create file:** `frontend/cogzy/static/cogzy-logo.svg`

```svg
<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#8b5cf6;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#6366f1;stop-opacity:1" />
    </linearGradient>
  </defs>
  <circle cx="50" cy="50" r="45" fill="url(#grad)"/>
  <text x="50" y="62" font-family="Arial, sans-serif" font-size="36" font-weight="bold" fill="white" text-anchor="middle">C</text>
</svg>
```

---

## TASK 8: Verify Build

```bash
cd frontend/cogzy
npm install
npm run build
```

**Expected:** Build succeeds with no errors.

If TypeScript errors occur, check:
1. tsconfig.json was copied correctly
2. All imports resolve

---

## TASK 9: Verify File Structure

```bash
ls -la frontend/cogzy/
ls -la frontend/cogzy/src/
ls -la frontend/cogzy/src/routes/
ls -la frontend/cogzy/src/lib/
```

**Expected structure:**
```
frontend/cogzy/
├── package.json
├── svelte.config.js
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
├── static/
│   └── cogzy-logo.svg
└── src/
    ├── app.html
    ├── app.css
    ├── routes/
    │   ├── +layout.svelte
    │   ├── +page.svelte
    │   └── login/
    │       └── +page.svelte
    └── lib/
        ├── stores/
        │   └── auth.ts
        └── components/
```

---

## COMPLETION CHECKLIST

- [ ] tenant_loader.py path fixed (no "bot" in path)
- [ ] Login page fetch() syntax fixed
- [ ] SvelteKit config files copied
- [ ] +layout.svelte created
- [ ] +page.svelte created (with auth redirect)
- [ ] lib/stores/auth.ts created
- [ ] cogzy-logo.svg created
- [ ] npm install succeeds
- [ ] npm run build succeeds

---

## ROLLBACK

If something breaks:
```bash
# Remove cogzy and start fresh
rm -rf frontend/cogzy
# Re-run this mission from Task 3
```

---

**END OF MISSION**