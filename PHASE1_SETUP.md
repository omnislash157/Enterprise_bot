# Azure AD SSO - Phase 1 Backend Setup

## ✅ Completed

Phase 1 backend implementation for Azure AD SSO authentication is complete. The following changes have been made:

### Files Added
1. **`azure_auth.py`** - Azure AD authentication service using MSAL
   - OAuth2 authorization URL generation
   - Token exchange (auth code → tokens)
   - ID token validation
   - User info extraction from claims
   - Access token refresh
   - Graph API helpers

2. **`sso_routes.py`** - FastAPI routes for SSO endpoints
   - `GET /api/auth/config` - Check if Azure AD is enabled
   - `GET /api/auth/login-url` - Get Microsoft login URL
   - `POST /api/auth/callback` - Exchange code for tokens
   - `POST /api/auth/refresh` - Refresh access tokens
   - `POST /api/auth/logout` - Logout endpoint
   - User provisioning/linking logic

3. **`run_migration.py`** - Database migration script
   - Adds `azure_oid` column to `enterprise.users` table
   - Creates index for Azure AD lookups

4. **`migrations/add_azure_oid.sql`** - SQL migration
   - ALTER TABLE statement for azure_oid column
   - Index creation

5. **`.env.azure-template`** - Environment variables template
   - Azure AD configuration placeholders
   - Setup instructions

### Files Modified
1. **`requirements.txt`**
   - Added: `msal>=1.24.0`
   - Added: `PyJWT>=2.8.0`
   - Added: `cryptography>=41.0.0`

2. **`auth_service.py`**
   - Added `get_user_by_azure_oid()` - Look up user by Azure Object ID
   - Added `create_user_from_azure()` - Auto-provision new users from SSO
   - Added `link_user_to_azure()` - Link existing users to Azure AD
   - Added `update_user_from_azure()` - Sync user info on each login

3. **`main.py`**
   - Imported SSO router and Azure auth modules
   - Updated `get_current_user()` dependency to handle Bearer tokens
   - Added Azure AD token validation via Microsoft Graph API
   - Included SSO router at `/api/auth`
   - Maintains backward compatibility with email header auth

## 🔧 Setup Required

### 1. Azure Portal Configuration

Before you can use Azure AD SSO, you must register an app in Azure:

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **App registrations** → **New registration**
3. Fill in:
   - **Name:** `Enterprise Bot`
   - **Supported account types:** Single tenant (your org only)
   - **Redirect URI:** `http://localhost:5173/auth/callback`
4. Click **Register**
5. Note your **Application (client) ID**
6. Note your **Directory (tenant) ID**
7. Go to **Certificates & secrets** → **New client secret**
   - Description: `Backend Secret`
   - Expiry: 24 months
   - **COPY THE VALUE IMMEDIATELY** (you won't see it again!)
8. Go to **Authentication** → Add platform → **Web**
   - Add production redirect URI: `https://your-frontend.railway.app/auth/callback`

### 2. Environment Variables

Copy the template and fill in your values:

```bash
cp .env.azure-template .env
```

Edit `.env` and add your Azure AD credentials:

```bash
AZURE_AD_TENANT_ID=your-tenant-id-here
AZURE_AD_CLIENT_ID=your-client-id-here
AZURE_AD_CLIENT_SECRET=your-client-secret-here
AZURE_AD_REDIRECT_URI=http://localhost:5173/auth/callback
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install Azure AD dependencies specifically:

```bash
pip install msal>=1.24.0 PyJWT>=2.8.0 cryptography>=41.0.0
```

### 4. Run Database Migration

```bash
python run_migration.py
```

This will:
- Add `azure_oid` column to `enterprise.users` table
- Create index for fast Azure AD lookups
- Verify the migration completed successfully

**Note:** If you see a connection error, ensure your database credentials in `.env` are correct and you have network access to the Azure PostgreSQL database.

### 5. Test the Backend

Start the server:

```bash
uvicorn main:app --reload
```

Test the SSO configuration:

```bash
curl http://localhost:8000/api/auth/config
```

Expected response:
```json
{
  "azure_ad_enabled": true,
  "login_url": "/api/auth/login"
}
```

Test getting the login URL:

```bash
curl http://localhost:8000/api/auth/login-url
```

Expected response:
```json
{
  "url": "https://login.microsoftonline.com/.../oauth2/v2.0/authorize?...",
  "state": "random-state-string"
}
```

## 🔄 How It Works

### Authentication Flow

1. **Frontend** calls `GET /api/auth/login-url` to get Microsoft login URL
2. **User** is redirected to Microsoft login page
3. **User** enters Microsoft credentials (your app never sees the password)
4. **Microsoft** redirects back with authorization code
5. **Frontend** sends code to `POST /api/auth/callback`
6. **Backend** exchanges code for tokens with Microsoft
7. **Backend** validates ID token, extracts user info (email, name, Azure OID)
8. **Backend** creates or updates user in database
9. **Backend** returns access token and user info to frontend
10. **Frontend** uses Bearer token for all subsequent API calls

### User Provisioning

On first login, a new user is automatically created:
- **Role:** `user` (default)
- **Department:** None (admin must assign later)
- **Azure OID:** Stored for future logins
- **Email & Name:** Synced from Azure AD

On subsequent logins:
- User info (email, name) is updated from Azure AD
- Existing department access is preserved

### Token Validation

When frontend sends API requests with `Authorization: Bearer <token>` header:
1. Backend validates token against Microsoft Graph API
2. Looks up user by Azure OID
3. Returns user info with permissions
4. Backward compatible - email header auth still works

## 📋 What's Next - Phase 2

Frontend integration:
1. Update auth store to support Azure AD
2. Create callback page to handle Microsoft redirect
3. Add "Sign in with Microsoft" button
4. Implement token refresh logic
5. Update API client to send Bearer tokens

See handoff document for Phase 2 details.

## 🐛 Troubleshooting

### "Azure AD not configured"
- Check that `.env` has all four Azure AD variables set
- Restart the backend after adding environment variables

### "Invalid or expired token"
- Token validation failed - check that TENANT_ID and CLIENT_ID match Azure Portal
- Access token may have expired - frontend should refresh

### "User not found" after successful login
- Database migration not run - execute `python run_migration.py`
- User was created but azure_oid column doesn't exist

### Database connection errors
- Check AZURE_PG_* variables in `.env`
- Verify network access to Azure PostgreSQL
- Ensure IP is whitelisted in Azure PostgreSQL firewall

## 📝 Files Summary

| File | Purpose |
|------|---------|
| `azure_auth.py` | MSAL integration, token exchange, validation |
| `sso_routes.py` | FastAPI endpoints for OAuth2 flow |
| `run_migration.py` | Database migration runner |
| `migrations/add_azure_oid.sql` | SQL to add azure_oid column |
| `.env.azure-template` | Environment variables template |
| `PHASE1_SETUP.md` | This file - setup instructions |

## ✅ Phase 1 Complete

Backend is ready for Azure AD SSO. Once environment variables are configured and migration is run, the `/api/auth` endpoints will be fully functional and ready for frontend integration.

Next step: Begin Phase 2 (Frontend Integration) when ready.
