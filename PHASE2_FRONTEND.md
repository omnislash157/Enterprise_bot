# Azure AD SSO - Phase 2: Frontend Integration

## ✅ Completed

Phase 2 frontend integration for Azure AD SSO is complete. The frontend now supports Microsoft single sign-on with OAuth2 flow, while maintaining backward compatibility with email-based authentication.

### Files Modified
1. **`frontend/src/lib/stores/auth.ts`** - Complete rewrite to support Azure AD
   - Added Azure AD OAuth2 flow support
   - Implemented token management (access + refresh)
   - Automatic token refresh before expiry
   - Backward compatible with email auth
   - New methods: `loginWithMicrosoft()`, `handleCallback()`, `refresh()`, `getAuthHeader()`
   - Smart session restoration based on auth method

2. **`frontend/src/lib/components/Login.svelte`** - Updated with Microsoft button
   - "Sign in with Microsoft" button with official branding
   - Conditionally shown when Azure AD is enabled
   - Toggle to switch between SSO and email login
   - Responsive error handling
   - Professional Microsoft button styling

3. **`frontend/src/routes/+layout.svelte`** - Updated initialization
   - Changed `auth.restore()` to `auth.init()`
   - Now checks Azure AD configuration on startup

### Files Created
1. **`frontend/src/routes/auth/callback/+page.svelte`** - OAuth callback handler
   - Handles Microsoft redirect after login
   - Validates state parameter (CSRF protection)
   - Exchanges authorization code for tokens
   - Professional loading and error states
   - Auto-redirects to main app on success

## 🎯 Key Features Implemented

### OAuth2 Authorization Code Flow
✓ **Login Initiation** - Redirects to Microsoft login page
✓ **State Validation** - CSRF protection via state parameter
✓ **Code Exchange** - Secure token exchange with backend
✓ **Token Storage** - Access + refresh tokens in localStorage
✓ **Auto Refresh** - Tokens refresh 1 minute before expiry
✓ **Session Restore** - Automatic session restoration on page reload

### User Experience
✓ **Microsoft Branding** - Official Microsoft button with logo
✓ **Dual Auth Support** - SSO or email login based on config
✓ **Loading States** - Clear feedback during authentication
✓ **Error Handling** - Friendly error messages
✓ **Smooth Redirects** - Seamless flow from login to app

### Security
✓ **State Parameter** - CSRF protection via sessionStorage
✓ **Token Validation** - Backend validates Microsoft tokens
✓ **Secure Storage** - Tokens isolated in localStorage
✓ **Auth Method Tracking** - Prevents auth method confusion

## 📋 Authentication Flow

### Microsoft SSO Flow

```
1. User clicks "Sign in with Microsoft"
   ↓
2. Frontend calls /api/auth/login-url
   ← Backend returns Microsoft login URL + state
   ↓
3. User redirected to login.microsoftonline.com
   ↓
4. User enters Microsoft credentials
   ↓
5. Microsoft redirects to /auth/callback?code=xxx&state=yyy
   ↓
6. Callback page validates state parameter
   ↓
7. Frontend POSTs code to /api/auth/callback
   ← Backend exchanges code for tokens with Microsoft
   ← Backend returns access_token, refresh_token, user info
   ↓
8. Frontend stores tokens in localStorage
   ↓
9. Frontend schedules token refresh for (expires_in - 60) seconds
   ↓
10. User redirected to main app (authenticated)
```

### Token Refresh Flow

```
1. Timer triggers 1 minute before token expiry
   ↓
2. Frontend POSTs refresh_token to /api/auth/refresh
   ← Backend exchanges refresh token with Microsoft
   ← Backend returns new access_token + refresh_token
   ↓
3. Frontend updates tokens in localStorage
   ↓
4. Frontend schedules next refresh
```

### Session Restoration

```
1. User refreshes page or returns later
   ↓
2. Layout calls auth.init()
   ↓
3. Auth store checks localStorage for auth_method
   ↓
4. If auth_method === 'azure_ad':
   - Loads access_token and refresh_token
   - Calls refresh() to validate/renew tokens
   - If successful: user authenticated
   - If failed: clears session, shows login
   ↓
5. If auth_method === 'email':
   - Falls back to email-based auth
   - Validates with backend
```

## 🔧 How to Use

### Backend Configuration

Ensure Phase 1 backend is configured with Azure AD credentials in `.env`:

```bash
AZURE_AD_TENANT_ID=your-tenant-id
AZURE_AD_CLIENT_ID=your-client-id
AZURE_AD_CLIENT_SECRET=your-client-secret
AZURE_AD_REDIRECT_URI=http://localhost:5173/auth/callback
```

### Frontend Configuration

The frontend automatically detects Azure AD configuration from the backend.

**Development:**
```bash
# .env (optional - defaults work for local dev)
VITE_API_URL=http://localhost:8000
```

**Production:**
```bash
# Railway environment variables
VITE_API_URL=https://your-backend.railway.app
```

### Azure Portal Configuration

Add the frontend callback URL to Azure Portal → App Registration → Authentication:

**Development:**
```
http://localhost:5173/auth/callback
```

**Production:**
```
https://your-frontend.railway.app/auth/callback
```

## 🔄 Auth Store API

### Methods

```typescript
// Initialize auth (check Azure config + restore session)
await auth.init()

// Microsoft SSO login (redirects to Microsoft)
await auth.loginWithMicrosoft()

// Handle OAuth callback (called from /auth/callback page)
const success = await auth.handleCallback(code, state)

// Refresh access token
const success = await auth.refresh()

// Legacy email login
const success = await auth.login(email)

// Logout (clears tokens)
await auth.logout()

// Get auth header for API calls
const headers = auth.getAuthHeader()
// Returns: { 'Authorization': 'Bearer token' } or { 'X-User-Email': 'email' }
```

### Derived Stores

```typescript
$azureEnabled       // boolean - is Azure AD configured?
$authMethod         // 'azure_ad' | 'email' | null
$isAuthenticated    // boolean - is user logged in?
$currentUser        // User object or null
$authLoading        // boolean - is auth in progress?
$authInitialized    // boolean - has auth been initialized?
```

## 🎨 Login Component States

### Azure AD Enabled

Shows Microsoft button with optional email fallback:

```
┌─────────────────────────────┐
│ Sign in with Microsoft      │  ← Primary (white button)
├─────────────────────────────┤
│            or               │  ← Divider
├─────────────────────────────┤
│ Sign in with email instead  │  ← Text link (shows form)
└─────────────────────────────┘
```

### Azure AD Disabled

Shows traditional email login:

```
┌─────────────────────────────┐
│ [Email Input Field]         │
│ [Sign In Button]            │
└─────────────────────────────┘
```

## 🔍 Testing

### Test Azure AD Flow

1. **Start backend with Azure AD configured:**
   ```bash
   python main.py
   ```

2. **Check configuration endpoint:**
   ```bash
   curl http://localhost:8000/api/auth/config
   # Should return: { "azure_ad_enabled": true, ... }
   ```

3. **Start frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

4. **Test login:**
   - Visit `http://localhost:5173`
   - Should see "Sign in with Microsoft" button
   - Click button → redirects to Microsoft login
   - Enter Microsoft credentials
   - Redirects to `/auth/callback`
   - Should show "Completing sign in..." briefly
   - Redirects to main app (authenticated)

5. **Test session persistence:**
   - Refresh page → should stay logged in
   - Check localStorage → should see tokens
   - Wait for token to near expiry → should auto-refresh

6. **Test logout:**
   - Logout from app
   - localStorage should be cleared
   - Should return to login page

### Test Email Fallback

1. Click "Sign in with email instead"
2. Enter email → submit
3. Should authenticate via email header

### Test Without Azure AD

1. Stop backend or remove Azure AD env vars
2. Restart backend
3. Frontend should show email login only

## 🐛 Troubleshooting

### "Sign in with Microsoft" button not showing

**Check:**
- Backend `/api/auth/config` returns `azure_ad_enabled: true`
- Azure AD env vars are set in backend `.env`
- Frontend is fetching from correct API URL

### Redirect URI mismatch error

**Fix:**
- Add exact redirect URI to Azure Portal → App Registration → Authentication
- Include both `http://localhost:5173/auth/callback` and production URL
- URIs must match exactly (no trailing slash differences)

### "Invalid state parameter" error

**Cause:**
- Browser cleared sessionStorage
- State expired (took too long to complete login)

**Fix:**
- Try logging in again
- Don't take more than ~10 minutes to complete Microsoft login

### Token refresh fails

**Check:**
- Refresh token is still valid (Microsoft refresh tokens can expire)
- Backend can reach Microsoft token endpoint
- Network is stable

**Fix:**
- Logout and login again to get fresh tokens

### Session not restoring on page refresh

**Check:**
- localStorage has `refresh_token`, `access_token`, `auth_method`
- Backend is running and accessible
- Network tab shows successful `/api/auth/refresh` call

## 📦 File Summary

| File | Lines | Purpose |
|------|-------|---------|
| `auth.ts` | 369 | Auth store with Azure AD + email support |
| `Login.svelte` | 335 | Login page with Microsoft button |
| `auth/callback/+page.svelte` | 98 | OAuth callback handler |
| `+layout.svelte` | 61 | Root layout (calls auth.init) |

**Total:** ~863 lines of frontend code

## ✨ Phase 2 Complete

Frontend Azure AD SSO integration is complete and ready to use. The application now supports:

- ✅ Microsoft single sign-on
- ✅ Automatic token refresh
- ✅ Session persistence
- ✅ Backward compatible email auth
- ✅ Professional Microsoft branding
- ✅ Secure OAuth2 implementation

**Next Steps:**
- Deploy to Railway with production redirect URI
- Test end-to-end with real Azure AD tenant
- Configure department access for new SSO users
- (Optional) Implement group-based department mapping

See `PHASE1_SETUP.md` for backend configuration details.
