# Azure AD SSO - Phase 3: Testing & Deployment

## ✅ Status: Ready for Testing

All code for Azure AD SSO has been implemented and committed. Phase 3 focuses on testing, verification, and production deployment.

---

## 🧪 Testing Checklist

### Backend Testing

#### 1. Database Migration

**Check if migration is needed:**
```sql
-- Run this query in your Azure PostgreSQL:
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'enterprise'
  AND table_name = 'users'
  AND column_name = 'azure_oid';
```

**If column doesn't exist, run migration:**
```bash
# Option A: Use migration script
python run_migration.py

# Option B: Run SQL directly
psql -h enterprisebot.postgres.database.azure.com \
     -U Mhartigan \
     -d postgres \
     -f migrations/add_azure_oid.sql
```

**Verify migration:**
```bash
# Use verification script
psql -h enterprisebot.postgres.database.azure.com \
     -U Mhartigan \
     -d postgres \
     -f migrations/verify_azure_oid.sql
```

Expected output:
```
column_name | data_type | character_maximum_length | is_nullable
------------+-----------+-------------------------+------------
azure_oid   | varchar   | 36                      | YES

indexname             | indexdef
----------------------+------------------------------------------
idx_users_azure_oid   | CREATE INDEX ... WHERE azure_oid IS NOT NULL
```

#### 2. Backend Environment Variables

Ensure `.env` file has all Azure AD credentials:

```bash
# Azure AD Configuration
AZURE_AD_TENANT_ID=your-tenant-id-here
AZURE_AD_CLIENT_ID=your-client-id-here
AZURE_AD_CLIENT_SECRET=your-secret-here
AZURE_AD_REDIRECT_URI=https://worthy-imagination-production.up.railway.app/auth/callback

# Database Configuration (existing)
AZURE_PG_USER=Mhartigan
AZURE_PG_PASSWORD=Lalamoney3!
AZURE_PG_HOST=enterprisebot.postgres.database.azure.com
AZURE_PG_PORT=5432
AZURE_PG_DATABASE=postgres
```

#### 3. Backend API Tests

**Start backend:**
```bash
uvicorn main:app --reload
# Or
python main.py
```

**Run test script:**
```bash
./test_azure_sso.sh
```

**Manual endpoint tests:**

```bash
# Test 1: Health check
curl http://localhost:8000/health

# Test 2: Auth configuration
curl http://localhost:8000/api/auth/config
# Expected: {"azure_ad_enabled": true, "login_url": "/api/auth/login"}

# Test 3: Login URL generation
curl http://localhost:8000/api/auth/login-url
# Expected: {"url": "https://login.microsoftonline.com/...", "state": "..."}
```

**Verify successful responses:**
- ✅ Health endpoint returns status: ok
- ✅ Auth config shows `azure_ad_enabled: true`
- ✅ Login URL contains `login.microsoftonline.com`
- ✅ No errors in backend logs

### Frontend Testing

#### 1. Frontend Environment

**Development (.env.local or .env):**
```bash
VITE_API_URL=http://localhost:8000
```

**Production (Railway):**
```bash
VITE_API_URL=https://your-backend-url.railway.app
```

#### 2. Frontend Build & Start

```bash
cd frontend
npm install
npm run dev
```

Visit: `http://localhost:5173`

#### 3. Visual Tests

**Login Page:**
- ✅ "Sign in with Microsoft" button appears (white button with Microsoft logo)
- ✅ "or" divider shown
- ✅ "Sign in with email instead" link shown
- ✅ Hint text shows "Enterprise SSO enabled"

**Click Microsoft Button:**
- ✅ Redirects to `login.microsoftonline.com`
- ✅ URL contains your tenant ID
- ✅ URL contains your client ID
- ✅ URL contains redirect_uri pointing to /auth/callback

**After Microsoft Login:**
- ✅ Redirects to `/auth/callback?code=...&state=...`
- ✅ Shows "Completing sign in..." spinner
- ✅ Redirects to main app (/) when complete
- ✅ User is authenticated (shows main interface)

**Session Persistence:**
- ✅ Refresh page → stays logged in
- ✅ Check localStorage → should have tokens
  - `refresh_token`
  - `access_token`
  - `auth_method` = 'azure_ad'
- ✅ Close tab, reopen → still logged in

**Token Refresh:**
- ✅ Wait ~1 hour (or check Network tab)
- ✅ Should see automatic `/api/auth/refresh` call
- ✅ Should stay logged in after refresh

**Logout:**
- ✅ Logout button clears session
- ✅ localStorage cleared
- ✅ Returns to login page

### End-to-End Integration Test

**Complete flow:**

1. Start backend: `uvicorn main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open browser: `http://localhost:5173`
4. Click "Sign in with Microsoft"
5. Enter Microsoft credentials
6. Should redirect back and log you in
7. Check Network tab for `/api/auth/callback` call
8. Verify user created in database:
   ```sql
   SELECT id, email, display_name, azure_oid, role, created_at
   FROM enterprise.users
   WHERE azure_oid IS NOT NULL
   ORDER BY created_at DESC
   LIMIT 5;
   ```

---

## 🚀 Production Deployment

### Azure Portal Configuration

#### 1. Update Redirect URIs

Go to: Azure Portal → App Registrations → Your App → Authentication

**Add production redirect URI:**
```
https://worthy-imagination-production.up.railway.app/auth/callback
```

**Your redirect URIs should include:**
- `http://localhost:5173/auth/callback` (development)
- `https://worthy-imagination-production.up.railway.app/auth/callback` (production)

#### 2. Verify Token Configuration

Go to: Token configuration

**Ensure these claims are included in ID token:**
- ✅ email
- ✅ preferred_username
- ✅ name

### Railway Deployment

#### Backend Service

**Environment Variables (add these to Railway backend service):**

```bash
# Azure AD SSO
AZURE_AD_TENANT_ID=your-tenant-id
AZURE_AD_CLIENT_ID=your-client-id
AZURE_AD_CLIENT_SECRET=your-client-secret
AZURE_AD_REDIRECT_URI=https://worthy-imagination-production.up.railway.app/auth/callback

# Database (should already be configured)
AZURE_PG_USER=Mhartigan
AZURE_PG_PASSWORD=Lalamoney3!
AZURE_PG_HOST=enterprisebot.postgres.database.azure.com
AZURE_PG_PORT=5432
AZURE_PG_DATABASE=postgres
```

**Deploy:**
```bash
git push origin claude/azure-ad-backend-phase1-P0VPE
```

Railway should auto-deploy.

**Verify backend deployment:**
```bash
curl https://your-backend.railway.app/api/auth/config
# Should return: {"azure_ad_enabled": true, ...}
```

#### Frontend Service

**Environment Variables (add these to Railway frontend service):**

```bash
VITE_API_URL=https://your-backend-url.railway.app
```

**Deploy:**

Frontend should auto-build and deploy.

**Verify frontend deployment:**

Visit: `https://worthy-imagination-production.up.railway.app`

Should see login page with "Sign in with Microsoft" button.

### Post-Deployment Verification

#### 1. Test Production Login Flow

```
1. Visit production frontend URL
2. Click "Sign in with Microsoft"
3. Should redirect to Microsoft login
4. Enter Microsoft credentials
5. Should redirect back to your app
6. Should be logged in
```

#### 2. Check Backend Logs

**Railway backend logs should show:**
```
[INFO] SSO routes loaded at /api/auth
[INFO] Azure AD login successful: user@domain.com
```

#### 3. Verify User in Database

```sql
-- Connect to your Azure PostgreSQL
SELECT
    id,
    email,
    display_name,
    azure_oid,
    role,
    created_at
FROM enterprise.users
WHERE azure_oid IS NOT NULL
ORDER BY created_at DESC;
```

**Expected:** New users created with Azure OID populated.

#### 4. Test All Auth Methods

**Azure AD SSO:**
- ✅ Microsoft login works
- ✅ Token refresh works
- ✅ Session persistence works

**Email Fallback:**
- ✅ Click "Sign in with email instead"
- ✅ Email login still works
- ✅ Existing email users can still login

---

## 📋 Production Checklist

### Before Going Live

- [ ] Azure App Registration complete
  - [ ] Tenant ID, Client ID, Client Secret obtained
  - [ ] Production redirect URI added
  - [ ] Token claims configured (email, name)
  - [ ] Client secret has sufficient expiry time

- [ ] Database Migration
  - [ ] `azure_oid` column added to `enterprise.users`
  - [ ] Index `idx_users_azure_oid` created
  - [ ] Migration verified with SQL query

- [ ] Backend Configuration
  - [ ] All 4 Azure AD env vars set in Railway
  - [ ] Backend deployed successfully
  - [ ] `/api/auth/config` returns `azure_ad_enabled: true`
  - [ ] `/api/auth/login-url` generates Microsoft URL

- [ ] Frontend Configuration
  - [ ] `VITE_API_URL` set to backend URL
  - [ ] Frontend deployed successfully
  - [ ] Login page shows Microsoft button
  - [ ] Callback route exists at `/auth/callback`

### First User Login

- [ ] Test Microsoft login flow end-to-end
- [ ] Verify user created in database with `azure_oid`
- [ ] Check user has correct email and display name
- [ ] Assign department access to new user (if needed)
- [ ] Test token refresh (wait or check Network tab)
- [ ] Test logout and re-login

### Ongoing Monitoring

- [ ] Monitor backend logs for auth errors
- [ ] Check Azure AD sign-in logs for issues
- [ ] Monitor token refresh success rate
- [ ] Track user provisioning (new users auto-created)
- [ ] Review department access assignments

---

## 🐛 Troubleshooting

### "Azure AD not configured" Error

**Symptoms:**
- Login page shows email input only
- Backend `/api/auth/config` returns `azure_ad_enabled: false`

**Fix:**
```bash
# Check backend environment variables
curl https://your-backend.railway.app/api/auth/config

# In Railway backend service, verify all 4 variables are set:
AZURE_AD_TENANT_ID
AZURE_AD_CLIENT_ID
AZURE_AD_CLIENT_SECRET
AZURE_AD_REDIRECT_URI

# Redeploy backend after adding variables
```

### "AADSTS50011: Reply URL mismatch"

**Symptoms:**
- Microsoft login redirects to error page
- Error mentions "reply URL does not match"

**Fix:**
1. Go to Azure Portal → App Registrations → Authentication
2. Verify redirect URI exactly matches (including https/http, trailing slash)
3. Add: `https://worthy-imagination-production.up.railway.app/auth/callback`
4. Wait 5-10 minutes for Azure to sync
5. Try login again

### "Invalid state parameter"

**Symptoms:**
- Callback page shows error
- State validation fails

**Fix:**
- This is usually a timing issue (took too long to complete login)
- Try logging in again (should work)
- If persistent, check sessionStorage in browser DevTools

### Database Migration Not Applied

**Symptoms:**
- Backend crashes on login
- Error: `column "azure_oid" does not exist`

**Fix:**
```bash
# Connect to database and run:
ALTER TABLE enterprise.users
ADD COLUMN IF NOT EXISTS azure_oid VARCHAR(36) UNIQUE;

CREATE INDEX IF NOT EXISTS idx_users_azure_oid
ON enterprise.users(azure_oid)
WHERE azure_oid IS NOT NULL;
```

### Token Refresh Fails

**Symptoms:**
- User logged out after ~1 hour
- Network tab shows 401 on `/api/auth/refresh`

**Fix:**
1. Check backend can reach Microsoft token endpoint
2. Verify refresh token hasn't expired
3. Check backend logs for detailed error
4. User may need to login again to get fresh tokens

### User Created Without Departments

**Symptoms:**
- User logs in successfully
- Has no access to any departments
- Can't see any content

**Expected Behavior:**
- Auto-provisioned users start with `role = 'user'` and no departments
- Admin must assign department access

**Fix:**
```sql
-- Grant department access to new user
-- (This is usually done via admin UI)
INSERT INTO enterprise.user_department_access
    (user_id, department_id, access_level, is_dept_head)
SELECT
    u.id,
    d.id,
    'read',
    FALSE
FROM enterprise.users u
CROSS JOIN enterprise.departments d
WHERE u.email = 'newuser@domain.com'
  AND d.slug = 'warehouse';
```

---

## 📊 Success Metrics

### Technical Metrics

- ✅ `/api/auth/config` returns `azure_ad_enabled: true`
- ✅ `/api/auth/login-url` generates valid Microsoft URL
- ✅ `/api/auth/callback` successfully exchanges codes for tokens
- ✅ Token refresh rate > 95%
- ✅ Login success rate > 98%
- ✅ Zero crashes related to Azure AD authentication

### User Experience Metrics

- ✅ Users can login with Microsoft credentials
- ✅ No password management needed
- ✅ Session persists across page refreshes
- ✅ Tokens refresh automatically without user action
- ✅ Email fallback available if needed

### Business Metrics

- ✅ New users auto-provisioned on first login
- ✅ User emails and names synced from Azure AD
- ✅ Department access properly managed
- ✅ Audit logs capture Azure AD logins
- ✅ No security incidents related to authentication

---

## 🎉 Success Criteria

Phase 3 is complete when:

1. ✅ **Database Migration Applied**
   - `azure_oid` column exists in `enterprise.users`
   - Index created for fast lookups

2. ✅ **Backend Tests Pass**
   - `/api/auth/config` shows Azure AD enabled
   - `/api/auth/login-url` generates Microsoft URL
   - No errors in backend logs

3. ✅ **Frontend Shows Microsoft Button**
   - "Sign in with Microsoft" button visible
   - Proper Microsoft branding
   - Email fallback available

4. ✅ **End-to-End Login Works**
   - User can click Microsoft button
   - Redirects to Microsoft login
   - Completes authentication
   - Returns to app logged in

5. ✅ **Production Deployment Verified**
   - Backend deployed with Azure AD env vars
   - Frontend deployed with correct API URL
   - Production redirect URI added to Azure Portal
   - First user successfully logs in via SSO

---

## 📚 Documentation Links

- **Phase 1 (Backend):** `PHASE1_SETUP.md`
- **Phase 2 (Frontend):** `PHASE2_FRONTEND.md`
- **Phase 3 (Deployment):** This file
- **Sprint Overview:** Handoff document

---

## 🚦 Current Status

**Ready for:**
- ✅ Local testing (backend + frontend)
- ✅ Database migration
- ✅ Production deployment
- ✅ First user login

**Next Actions:**
1. Run database migration (if not already done)
2. Deploy to Railway (both services)
3. Add production redirect URI to Azure Portal
4. Test first Microsoft login
5. Assign department access to new users

---

*Generated: 2024-12-17*
*Sprint: Azure AD SSO - Phase 3*
*Status: Testing & Deployment*
