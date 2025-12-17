# Azure AD SSO Integration - Complete Guide

## 🎯 Overview

Microsoft Entra ID (Azure AD) single sign-on has been fully integrated into the Enterprise Bot application. Users can now authenticate using their existing Microsoft credentials, eliminating password management and leveraging enterprise-grade security.

## 📦 What Was Built

### Phase 1: Backend Implementation
- OAuth2 authorization code flow
- Token exchange and validation
- Automatic user provisioning
- Token refresh mechanism
- Database schema updates

### Phase 2: Frontend Integration
- Microsoft login button
- OAuth callback handler
- Token management
- Session persistence
- Backward compatible with email auth

### Phase 3: Testing & Deployment
- Test scripts and verification tools
- Production deployment guide
- Troubleshooting documentation
- Success metrics and monitoring

## 🚀 Quick Start

### Prerequisites

1. **Azure App Registration**
   - Tenant ID
   - Client ID
   - Client Secret
   - Redirect URIs configured

2. **Environment Variables**
   ```bash
   AZURE_AD_TENANT_ID=your-tenant-id
   AZURE_AD_CLIENT_ID=your-client-id
   AZURE_AD_CLIENT_SECRET=your-client-secret
   AZURE_AD_REDIRECT_URI=https://your-frontend/auth/callback
   ```

3. **Database Migration**
   ```bash
   python run_migration.py
   # Adds azure_oid column to enterprise.users table
   ```

### Local Development

**Backend:**
```bash
# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn main:app --reload

# Verify Azure AD is enabled
curl http://localhost:8000/api/auth/config
```

**Frontend:**
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev

# Visit http://localhost:5173
# Should see "Sign in with Microsoft" button
```

### Production Deployment

**Railway:**

1. Add Azure AD env vars to backend service
2. Add `VITE_API_URL` to frontend service
3. Add production redirect URI to Azure Portal
4. Deploy both services
5. Test Microsoft login

## 📖 Documentation

| Document | Purpose |
|----------|---------|
| `PHASE1_SETUP.md` | Backend implementation guide |
| `PHASE2_FRONTEND.md` | Frontend integration guide |
| `PHASE3_DEPLOYMENT.md` | Testing & deployment guide |
| `AZURE_SSO_README.md` | This file - quick reference |

## 🔄 Authentication Flow

```
1. User clicks "Sign in with Microsoft"
        ↓
2. Redirects to login.microsoftonline.com
        ↓
3. User enters Microsoft credentials
        ↓
4. Microsoft redirects to /auth/callback?code=xxx
        ↓
5. Frontend exchanges code for tokens
        ↓
6. Backend validates with Microsoft
        ↓
7. User auto-provisioned in database
        ↓
8. User authenticated → Main app
```

## 🧪 Testing

**Run test suite:**
```bash
./test_azure_sso.sh
```

**Manual tests:**
```bash
# Backend config
curl http://localhost:8000/api/auth/config

# Login URL generation
curl http://localhost:8000/api/auth/login-url

# Database verification
psql -h enterprisebot.postgres.database.azure.com \
     -U Mhartigan \
     -d postgres \
     -f migrations/verify_azure_oid.sql
```

## 🔐 Security Features

- ✅ OAuth2 authorization code flow (industry standard)
- ✅ State parameter validation (CSRF protection)
- ✅ Token validation via Microsoft Graph API
- ✅ Secure token storage
- ✅ Automatic token refresh
- ✅ Audit logging for all auth events
- ✅ No passwords stored or managed

## 👥 User Management

**Auto-Provisioning:**
- New users automatically created on first login
- Email and name synced from Azure AD
- Default role: `user`
- No departments assigned initially

**Department Access:**
- Admin must assign department access after first login
- Can be done via admin UI
- Or via SQL:
  ```sql
  INSERT INTO enterprise.user_department_access
      (user_id, department_id, access_level, is_dept_head)
  VALUES (user_id, dept_id, 'read', FALSE);
  ```

## 🐛 Common Issues

### Microsoft Button Not Showing

**Check:**
- Backend `/api/auth/config` returns `azure_ad_enabled: true`
- All 4 Azure AD env vars are set
- Frontend can reach backend

### Reply URL Mismatch

**Fix:**
- Add exact redirect URI to Azure Portal
- Include both development and production URLs
- Must match exactly (https/http, trailing slash)

### Token Refresh Fails

**Fix:**
- Check backend can reach Microsoft endpoints
- Verify refresh token hasn't expired
- Check backend logs for detailed error

### User Has No Departments

**Expected:**
- Auto-provisioned users start with no access
- Admin assigns departments via UI or SQL

## 📊 Monitoring

**Key Metrics:**
- Login success rate
- Token refresh success rate
- User provisioning rate
- Auth-related errors

**Check Logs:**
```bash
# Backend logs should show:
[INFO] Azure AD login successful: user@domain.com
[INFO] User created from Azure AD: user@domain.com
```

## 🎉 Success Criteria

Azure AD SSO is working when:

1. ✅ Microsoft button appears on login page
2. ✅ Users can login with Microsoft credentials
3. ✅ Tokens refresh automatically
4. ✅ Sessions persist across page refreshes
5. ✅ New users auto-provisioned in database
6. ✅ No authentication-related errors

## 📝 Files Modified

**Backend:**
- `azure_auth.py` - Azure AD service (NEW)
- `sso_routes.py` - OAuth endpoints (NEW)
- `auth_service.py` - Azure user methods (MODIFIED)
- `main.py` - SSO router integration (MODIFIED)
- `requirements.txt` - Azure dependencies (MODIFIED)

**Frontend:**
- `auth.ts` - Auth store with SSO (MODIFIED - 369 lines)
- `Login.svelte` - Microsoft button (MODIFIED - 335 lines)
- `auth/callback/+page.svelte` - OAuth handler (NEW - 98 lines)
- `+layout.svelte` - Auth initialization (MODIFIED)

**Database:**
- `migrations/add_azure_oid.sql` - Schema update (NEW)
- `migrations/verify_azure_oid.sql` - Verification (NEW)

**Scripts:**
- `run_migration.py` - Migration runner (NEW)
- `test_azure_sso.sh` - Test suite (NEW)

**Documentation:**
- `PHASE1_SETUP.md` - Backend guide (NEW)
- `PHASE2_FRONTEND.md` - Frontend guide (NEW)
- `PHASE3_DEPLOYMENT.md` - Deployment guide (NEW)
- `AZURE_SSO_README.md` - This file (NEW)
- `.env.azure-template` - Config template (NEW)

## 💡 Tips

**Development:**
- Use email fallback for quick testing
- Check browser console for frontend errors
- Monitor backend logs for auth issues
- Use browser DevTools → Application → Local Storage to check tokens

**Production:**
- Monitor Azure AD sign-in logs
- Check token refresh rates
- Track new user provisioning
- Set up alerts for auth failures

**Maintenance:**
- Client secrets expire - set reminders
- Review audit logs regularly
- Monitor token refresh success
- Update redirect URIs when changing domains

## 🔗 Useful Links

- [Azure Portal](https://portal.azure.com)
- [Microsoft Identity Platform Docs](https://docs.microsoft.com/en-us/azure/active-directory/develop/)
- [MSAL Python Docs](https://msal-python.readthedocs.io/)

---

## 🎓 Architecture

```
┌─────────────────────────────────────────────────┐
│                  USER BROWSER                    │
│                                                  │
│  ┌────────────┐         ┌──────────────┐       │
│  │  Frontend  │ ◄────► │   Backend    │       │
│  │  (Svelte)  │         │   (FastAPI)  │       │
│  └────────────┘         └──────────────┘       │
│         │                       │               │
└─────────┼───────────────────────┼───────────────┘
          │                       │
          │                       │
          ▼                       ▼
   ┌─────────────┐         ┌──────────────┐
   │  Microsoft  │ ◄────► │  PostgreSQL  │
   │  Azure AD   │         │   Database   │
   └─────────────┘         └──────────────┘
```

**Flow:**
1. Frontend → Azure AD (redirect to Microsoft login)
2. Azure AD → Frontend (callback with auth code)
3. Frontend → Backend (exchange code for tokens)
4. Backend → Azure AD (validate and exchange)
5. Backend → Database (create/update user)
6. Backend → Frontend (return tokens + user info)

---

*Last Updated: 2024-12-17*
*Status: Production Ready*
*Version: 1.0.0*
