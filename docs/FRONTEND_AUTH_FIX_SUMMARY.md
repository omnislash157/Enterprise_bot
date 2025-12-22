# Frontend Auth Fix - Quick Summary

**Date:** 2024-12-21
**Status:** Root cause identified, fix ready to deploy

---

## Problem
Azure SSO button not showing on login page. Users see only email login form.

---

## Root Cause
Missing environment variable: `VITE_API_URL` in Railway deployment.

Without this, frontend cannot reach backend to check if Azure AD is enabled.

---

## The Fix (5 minutes)

### Step 1: Add Environment Variable to Railway
1. Open Railway dashboard
2. Go to project settings → Variables
3. Add new variable:
   ```
   VITE_API_URL=https://worthy-imagination-production.up.railway.app
   ```
4. Save and trigger new deployment

### Step 2: Verify It Works
After deployment completes:
1. Open login page
2. Should see "Sign in with Microsoft" button
3. Click it → redirects to Microsoft login
4. Complete auth → redirected back to app

---

## Why This Fixes It

**Current (broken) flow:**
```
Frontend loads → tries to call http://localhost:8000/api/auth/config
                 ↓ FAILS (localhost doesn't exist in Railway)
                 ↓
                azureEnabled stays false
                 ↓
                SSO button doesn't render
```

**After fix:**
```
Frontend loads → calls https://worthy-imagination-production.up.railway.app/api/auth/config
                 ↓ SUCCESS
                 ↓
                Backend returns: { "azure_ad_enabled": true }
                 ↓
                azureEnabled = true
                 ↓
                SSO button renders ✅
```

---

## Technical Details

### How Vite Env Vars Work
- Vite only exposes variables prefixed with `VITE_` to frontend code
- Variables are replaced at BUILD time (not runtime)
- `import.meta.env.VITE_API_URL` becomes the literal string value in built JS

### Why It Fell Back to Email
- Frontend auth code has defensive programming
- If Azure config fetch fails, falls back to email login
- No error shown to user (silent fallback)
- This prevented a complete auth failure, but hid the issue

---

## Additional Improvements (Optional)

After the urgent fix, consider these:

### 1. Add Error Handling (10 min)
Show user feedback if backend unreachable:
```typescript
// frontend/src/lib/stores/auth.ts line 82
if (!configRes.ok) {
    console.warn('[Auth] Config fetch failed:', configRes.status);
    // Could show toast notification here
}
```

### 2. Create Frontend .env File (5 min)
For local development:
```bash
# frontend/.env
VITE_API_URL=http://localhost:8000
```

### 3. Add Loading State (15 min)
Show spinner while checking Azure config:
```svelte
{#if !$authInitialized}
    <div class="loading">Initializing...</div>
{:else if $azureEnabled}
    <!-- SSO button -->
```

---

## Full Report

See `docs/FRONTEND_AUTH_RECON.md` for:
- Complete code flow analysis
- All 5 issues identified
- Detailed fix recommendations
- Validation checklist
- Architecture diagrams

---

## Confidence Level
**95%** - All evidence points to this single issue. The code is correct, credentials are correct, only the environment variable is missing.
