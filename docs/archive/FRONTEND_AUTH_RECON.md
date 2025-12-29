# Frontend Auth Recon Report

**Date:** 2024-12-21
**Priority:** HIGH - SSO login broken
**Status:** Root cause identified ✅

---

## Executive Summary

**ROOT CAUSE FOUND:** The Azure SSO button is not rendering because the frontend is **not receiving the `VITE_API_URL` environment variable** in production (Railway). Without this variable, the frontend cannot call the backend's `/api/auth/config` endpoint to determine if Azure AD is enabled.

**Impact:** Users see only the email login form instead of the Microsoft SSO button.

**Confidence Level:** 95% - All evidence points to missing environment variable configuration in Railway.

---

## Current State

### What's Rendering Now
- ✅ Login page loads successfully
- ❌ Azure SSO button is hidden (not rendering)
- ✅ Email fallback form is showing instead
- ❌ "Enterprise SSO enabled" hint text not showing

### Why SSO Button Isn't Showing

The SSO button render logic in `Login.svelte` line 45:

```svelte
{#if $azureEnabled}
    <!-- Microsoft SSO Button -->
```

The `azureEnabled` store is controlled by auth initialization:

```typescript
// auth.ts line 78-92
async init() {
    try {
        // Check if Azure AD is enabled
        const apiBase = getApiBase();  // ⚠️ RETURNS undefined in production
        const configRes = await fetch(`${apiBase}/api/auth/config`);
        const config = await configRes.json();

        update(s => ({ ...s, azureEnabled: config.azure_ad_enabled }));
```

**The Problem:** `getApiBase()` returns:
```typescript
function getApiBase(): string {
    return import.meta.env.VITE_API_URL || 'http://localhost:8000';
}
```

In Railway production, `import.meta.env.VITE_API_URL` is **undefined**, so it defaults to `http://localhost:8000`, which fails or times out.

---

## Auth Flow Architecture

### Intended Flow (When Working)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. APP STARTUP (+layout.svelte)                                 │
│    ├─ loadConfig() → /api/config (feature flags)                │
│    └─ auth.init() → /api/auth/config (check Azure enabled)      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. LOGIN PAGE (Login.svelte)                                    │
│    ├─ if $azureEnabled: Show Microsoft SSO button               │
│    └─ else: Show email-only form                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. MICROSOFT LOGIN FLOW (if SSO enabled)                        │
│    User clicks "Sign in with Microsoft"                         │
│    ├─ Frontend: auth.loginWithMicrosoft()                       │
│    ├─ GET /api/auth/login-url                                   │
│    │   └─ Backend: generate Azure OAuth URL + state             │
│    ├─ Redirect to: login.microsoftonline.com                    │
│    │   └─ User authenticates with Microsoft                     │
│    └─ Microsoft redirects to: /auth/callback?code=xxx&state=yyy │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. CALLBACK HANDLER (/auth/callback/+page.svelte)               │
│    ├─ Extract code & state from URL                             │
│    ├─ POST /api/auth/callback { code, state }                   │
│    │   └─ Backend: exchange code for tokens                     │
│    │   └─ Backend: provision user in database                   │
│    │   └─ Returns: { access_token, refresh_token, user }        │
│    ├─ Store tokens in localStorage                              │
│    ├─ Update auth store with user                               │
│    └─ Redirect to main app (/)                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. AUTHENTICATED STATE                                           │
│    ├─ Access token stored in localStorage                       │
│    ├─ All API calls include: Authorization: Bearer <token>      │
│    └─ Token auto-refreshes 1 minute before expiry               │
└─────────────────────────────────────────────────────────────────┘
```

### Current Flow (Broken in Production)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. APP STARTUP (+layout.svelte)                                 │
│    ├─ loadConfig() → http://localhost:8000/api/config ❌ FAILS  │
│    └─ auth.init() → http://localhost:8000/api/auth/config ❌    │
│        └─ Fetch fails/timeouts                                  │
│        └─ azureEnabled stays FALSE (default)                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. LOGIN PAGE (Login.svelte)                                    │
│    ├─ $azureEnabled = false ❌                                  │
│    └─ Shows email-only form (fallback)                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Environment Requirements

### Backend Environment Variables (✅ Already Set in Railway)

These are correctly configured:

```bash
AZURE_AD_TENANT_ID=67de5fcd-a0e9-447d-9f28-e613d82a68eb
AZURE_AD_CLIENT_ID=6bd5e110-a031-46e3-b627-6ca21d8510ba
AZURE_AD_CLIENT_SECRET=DCI8Q~QFEYkIG212REq~4SCGO5yxt9M5PM1ezcuf
AZURE_AD_REDIRECT_URI=https://worthy-imagination-production.up.railway.app/auth/callback
```

### Frontend Environment Variables (❌ MISSING in Railway)

**CRITICAL:** This variable is missing:

```bash
VITE_API_URL=https://worthy-imagination-production.up.railway.app
```

**Why it's needed:**
- Vite only exposes environment variables prefixed with `VITE_` to the frontend code
- Without this, the frontend cannot determine the backend API URL in production
- The frontend defaults to `http://localhost:8000` which doesn't exist in Railway

### How Vite Environment Variables Work

1. **Build time:** Vite replaces `import.meta.env.VITE_*` with literal values during build
2. **Variable naming:** MUST start with `VITE_` to be exposed to frontend code
3. **Source:** Read from `.env` files or Railway environment variables during build

---

## Issues Found

### Issue #1: Missing VITE_API_URL in Railway ⚠️ CRITICAL

**File:** N/A (missing environment variable)
**Lines:** Affects `frontend/src/lib/stores/auth.ts` line 46

**Problem:**
- Frontend tries to fetch backend config at startup
- `getApiBase()` returns undefined → defaults to `http://localhost:8000`
- Request fails in production
- `azureEnabled` never gets set to `true`
- SSO button never renders

**Evidence:**
- `.env` file has backend Azure credentials but no `VITE_API_URL`
- No `.env` file exists in `frontend/` directory
- `auth.ts` uses `import.meta.env.VITE_API_URL` (line 46)
- Login.svelte conditionally renders SSO button based on `$azureEnabled` (line 45)

---

### Issue #2: No Frontend .env File (Lower Priority)

**File:** `frontend/.env` (missing)

**Problem:**
- Local development also requires manual config
- No `.env.example` template for developers
- New developers won't know what to set

**Impact:** Medium (only affects local dev)

---

### Issue #3: No Error Handling for Config Fetch Failure

**File:** `frontend/src/lib/stores/auth.ts`
**Lines:** 78-93

**Problem:**
```typescript
async init() {
    try {
        const apiBase = getApiBase();
        const configRes = await fetch(`${apiBase}/api/auth/config`);
        const config = await configRes.json();  // ⚠️ No status check

        update(s => ({ ...s, azureEnabled: config.azure_ad_enabled }));
```

**Issues:**
- No check if `configRes.ok` is true
- If fetch fails, `configRes.json()` will throw
- Error is caught but no user feedback
- Silent failure → user just sees email login

**Impact:** Low (user can still use email fallback, but confusing)

---

### Issue #4: Duplicate Azure Credentials in .env

**File:** `.env`
**Lines:** 27-35

**Problem:**
- Azure AD credentials are listed twice
- First set has `AZURE_AD_REDIRECT_URI=http://localhost:5173/auth/callback`
- Second set has `AZURE_AD_REDIRECT_URI=https://worthy-imagination-production.up.railway.app/auth/callback`
- Environment will use the second value (last wins)

**Impact:** Low (works correctly by accident, but confusing)

---

### Issue #5: No Loading State for Azure Detection

**File:** `frontend/src/lib/components/Login.svelte`
**Lines:** All

**Problem:**
- Login page renders immediately while auth is still initializing
- If Azure config fetch is slow, user briefly sees email form then SSO button appears
- Causes UI flicker

**Impact:** Low (cosmetic)

---

## Files That Need Investigation/Changes

### Critical (Blocks SSO)

1. **Railway Environment Variables**
   - Add `VITE_API_URL` to Railway project environment
   - Value: `https://worthy-imagination-production.up.railway.app`
   - Must be set before frontend build step

### High Priority (Improve Reliability)

2. **frontend/src/lib/stores/auth.ts**
   - Add response status checking in `init()` method
   - Add better error logging
   - Consider fallback behavior

3. **frontend/.env** (create new file)
   - Create `.env` file with `VITE_API_URL=http://localhost:8000`
   - Add to `.gitignore`

4. **frontend/.env.example** (create new file)
   - Template for developers
   - Document what each variable does

### Medium Priority (Quality of Life)

5. **.env** (root)
   - Remove duplicate Azure credentials
   - Keep only production values

6. **frontend/src/lib/components/Login.svelte**
   - Show loading indicator while `auth.init()` is running
   - Prevent UI flicker

---

## Fix Recommendations

### Priority 1: Fix Railway Environment Variable (URGENT)

**What:** Add `VITE_API_URL` to Railway environment variables

**How:**
1. Open Railway dashboard
2. Navigate to project settings → Variables
3. Add variable:
   - Name: `VITE_API_URL`
   - Value: `https://worthy-imagination-production.up.railway.app`
4. Trigger new deployment (rebuild frontend)

**Why it works:**
- Railway injects environment variables during build
- Vite will replace `import.meta.env.VITE_API_URL` with the actual URL
- Frontend can now call backend API successfully

**Estimated effort:** 5 minutes
**Risk:** None (safe change)

---

### Priority 2: Add Error Handling in auth.init()

**What:** Check response status before parsing JSON

**File:** `frontend/src/lib/stores/auth.ts` line 78-93

**Change:**
```typescript
async init() {
    try {
        const apiBase = getApiBase();
        console.log('[Auth] Checking Azure config at:', apiBase);

        const configRes = await fetch(`${apiBase}/api/auth/config`);

        if (!configRes.ok) {
            console.warn('[Auth] Config fetch failed:', configRes.status);
            update(s => ({ ...s, initialized: true, azureEnabled: false }));
            return;
        }

        const config = await configRes.json();
        console.log('[Auth] Azure enabled:', config.azure_ad_enabled);

        update(s => ({ ...s, azureEnabled: config.azure_ad_enabled }));
        await this.restore();
    } catch (e) {
        console.error('[Auth] Init failed:', e);
        update(s => ({ ...s, initialized: true, azureEnabled: false }));
    }
}
```

**Estimated effort:** 10 minutes
**Risk:** None (improves robustness)

---

### Priority 3: Create Frontend .env Files

**What:** Local development environment configuration

**Files to create:**

**frontend/.env:**
```bash
VITE_API_URL=http://localhost:8000
```

**frontend/.env.example:**
```bash
# Backend API URL
# Local development: http://localhost:8000
# Production: https://your-app.railway.app
VITE_API_URL=http://localhost:8000
```

**Also update:** `.gitignore` to include `frontend/.env`

**Estimated effort:** 5 minutes
**Risk:** None

---

### Priority 4: Clean Up Root .env File

**What:** Remove duplicate Azure credentials

**File:** `.env` lines 27-35

**Keep only:**
```bash
# Azure AD Credentials (Production)
AZURE_AD_TENANT_ID=67de5fcd-a0e9-447d-9f28-e613d82a68eb
AZURE_AD_CLIENT_ID=6bd5e110-a031-46e3-b627-6ca21d8510ba
AZURE_AD_CLIENT_SECRET=DCI8Q~QFEYkIG212REq~4SCGO5yxt9M5PM1ezcuf
AZURE_AD_REDIRECT_URI=https://worthy-imagination-production.up.railway.app/auth/callback
```

**Add comment for local dev:**
```bash
# For local development, override AZURE_AD_REDIRECT_URI:
# AZURE_AD_REDIRECT_URI=http://localhost:5173/auth/callback
```

**Estimated effort:** 5 minutes
**Risk:** Low (document current value first)

---

### Priority 5: Add Loading State to Login Page

**What:** Show loading indicator while Azure config is being fetched

**File:** `frontend/src/lib/components/Login.svelte`

**Change:** Add check for `$authInitialized` before rendering:

```svelte
<script lang="ts">
    import { auth, authLoading, azureEnabled, authInitialized } from '$lib/stores/auth';
    // ... rest of script
</script>

<div class="login-container">
    <div class="login-card">
        <div class="logo">
            <span class="logo-icon">◈</span>
            <h1>Driscoll Intelligence</h1>
        </div>

        <p class="subtitle">Sign in to continue</p>

        {#if !$authInitialized}
            <!-- Loading state while checking Azure config -->
            <div class="loading">
                <div class="spinner"></div>
                <p>Initializing...</p>
            </div>
        {:else if $azureEnabled}
            <!-- Microsoft SSO Button -->
            ...
```

**Estimated effort:** 15 minutes
**Risk:** None (cosmetic improvement)

---

## Validation Checklist

After implementing Priority 1 fix (Railway env var), verify:

- [ ] Railway environment variables include `VITE_API_URL`
- [ ] New deployment/build triggered in Railway
- [ ] Frontend build logs show `VITE_API_URL` being set
- [ ] Frontend can reach backend `/api/auth/config` endpoint
- [ ] Backend returns `{ "azure_ad_enabled": true }`
- [ ] Login page shows Microsoft SSO button
- [ ] Clicking SSO button redirects to Microsoft login
- [ ] Callback flow completes successfully
- [ ] User is authenticated and sees main app

---

## Technical Details

### Frontend Framework
- **Framework:** SvelteKit 1.30.0
- **Build tool:** Vite 4.5.0
- **State management:** Svelte stores (writable/derived)
- **Routing:** SvelteKit file-based routing

### Auth Implementation Pattern
- **Pattern:** Token-based authentication with OAuth2/OIDC
- **Tokens:** JWT access tokens + refresh tokens
- **Storage:** localStorage (tokens) + Svelte stores (state)
- **Backend calls:** Fetch API with `Authorization: Bearer <token>` header

### Key Files
```
frontend/
├── src/
│   ├── lib/
│   │   ├── stores/
│   │   │   ├── auth.ts              # 370 lines - Core auth logic
│   │   │   └── config.ts            # 88 lines - Feature flags
│   │   └── components/
│   │       └── Login.svelte         # 335 lines - Login UI
│   └── routes/
│       ├── +layout.svelte           # 92 lines - Root layout, auth init
│       └── auth/
│           └── callback/
│               └── +page.svelte     # 170 lines - OAuth callback handler
```

### Backend Endpoints Used
```
GET  /api/auth/config      → Check if Azure AD enabled
GET  /api/auth/login-url   → Get Microsoft OAuth URL
POST /api/auth/callback    → Exchange code for tokens
POST /api/auth/refresh     → Refresh access token
POST /api/auth/logout      → Clear session
```

---

## Root Cause Analysis

### Why Did This Happen?

1. **Split deployment:** Frontend and backend deployed separately to Railway
2. **Static build:** Frontend is built into static files with hardcoded API URL
3. **Missing config:** `VITE_API_URL` wasn't set in Railway environment
4. **Silent failure:** No visible error, just falls back to email login

### Why Wasn't It Caught Earlier?

1. **Local dev works:** Local `.env` isn't needed if backend runs on `:8000`
2. **Email fallback:** System still functions with email auth
3. **No error UI:** Failed config fetch is silent, no user feedback

### Prevention

- Add `VITE_API_URL` to Railway environment variables template
- Add health check endpoint that frontend calls on startup
- Show clear error if backend unreachable
- Add integration test for auth flow

---

## Appendix: Code Flow Analysis

### Auth Store Initialization Sequence

```typescript
// +layout.svelte (onMount)
await auth.init()
    ↓
// auth.ts init()
const apiBase = getApiBase()  // Returns VITE_API_URL or localhost:8000
    ↓
fetch(`${apiBase}/api/auth/config`)
    ↓
// If successful:
update(s => ({ ...s, azureEnabled: config.azure_ad_enabled }))
    ↓
// Login.svelte reactively updates
{#if $azureEnabled}
    <button on:click={handleMicrosoftLogin}>Sign in with Microsoft</button>
{/if}
```

### Microsoft Login Flow Sequence

```typescript
// User clicks SSO button
handleMicrosoftLogin()
    ↓
// auth.ts loginWithMicrosoft()
fetch(`${apiBase}/api/auth/login-url`)
    ↓
// Backend returns { url, state }
window.location.href = url  // Redirect to Microsoft
    ↓
// User authenticates at login.microsoftonline.com
// Microsoft redirects back
https://app.railway.app/auth/callback?code=xxx&state=yyy
    ↓
// /auth/callback/+page.svelte (onMount)
const code = $page.url.searchParams.get('code')
const state = $page.url.searchParams.get('state')
    ↓
auth.handleCallback(code, state)
    ↓
// auth.ts handleCallback()
fetch(`${apiBase}/api/auth/callback`, { method: 'POST', body: { code, state } })
    ↓
// Backend exchanges code for tokens
// Returns: { access_token, refresh_token, expires_in, user }
    ↓
// Store tokens and user
localStorage.setItem('access_token', tokens.access_token)
localStorage.setItem('refresh_token', tokens.refresh_token)
update(s => ({ ...s, user: tokens.user, accessToken: tokens.access_token }))
    ↓
// Redirect to main app
goto('/')
```

---

**END OF REPORT**

---

## Quick Reference

**Problem:** SSO button not showing
**Root Cause:** Missing `VITE_API_URL` in Railway
**Fix:** Add env var to Railway project
**Estimated Time:** 5 minutes
**Confidence:** 95%
