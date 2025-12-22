# Enterprise Schema Testing Guide

**For:** Matt Hartigan (mhartigan@driscollfoods.com)
**Date:** 2024-12-21
**Status:** Ready for Testing

---

## 🎯 What Was Fixed

**CRITICAL BLOCKER RESOLVED:** The `users` table had a column named `oid` but the code expected `azure_oid`. This prevented SSO login from working.

**MIGRATION COMPLETED:**
- ✅ Nuked old tables
- ✅ Created 7 new tables with correct structure
- ✅ Your admin account is ready: mhartigan@driscollfoods.com
- ✅ You have access to all 6 departments: purchasing, credit, sales, warehouse, accounting, it

---

## 🧪 Test Plan

### Test 1: Azure SSO Login ✅ READY TO TEST

**What to test:** Can you log in with your Microsoft account?

**Steps:**
1. Open browser (incognito/private mode recommended)
2. Go to: https://worthy-imagination-production.up.railway.app
3. Click "Sign in with Microsoft" (if button is visible)
   - **If button is NOT visible:** This is the VITE_API_URL issue (see Test 2)
4. Azure will redirect you to Microsoft login
5. Sign in with: mhartigan@driscollfoods.com + your Microsoft password
6. Azure will redirect back to the app
7. You should see the dashboard

**Expected Result:**
- ✅ You're logged in
- ✅ Your name appears in the top right: "Matt Hartigan"
- ✅ You see admin navigation options

**If it fails:**
- Check browser console (F12) for errors
- Check backend logs in Railway
- Look for database errors (azure_oid lookup)

**What happens behind the scenes:**
```sql
-- First login: Backend receives azure_oid from Microsoft token
-- Backend finds your user by EMAIL, then UPDATES azure_oid:
UPDATE enterprise.users
SET azure_oid = '<value-from-microsoft>'
WHERE email = 'mhartigan@driscollfoods.com';

-- Subsequent logins: Backend looks up by azure_oid directly:
SELECT * FROM enterprise.users WHERE azure_oid = '<value>';
```

---

### Test 2: Frontend-Backend Connection ⚠️ MAY NEED FIX

**What to test:** Can the frontend reach the backend API?

**Problem:** Railway has TWO separate services:
- Frontend service (SvelteKit) - Has its own URL
- Backend service (FastAPI) - Has its own URL

The frontend needs to know the backend's URL via environment variable.

**Steps to verify:**
1. Go to Railway dashboard
2. Find your **frontend service** (SvelteKit)
3. Go to **Variables** tab
4. Look for `VITE_API_URL`

**Expected Value:**
```
VITE_API_URL=https://worthy-imagination-production.up.railway.app
```
(This should be your **backend service** URL)

**If missing or wrong:**
1. Add/update the variable
2. Redeploy frontend service
3. Test again

**How to test if it's working:**
1. Open browser console (F12)
2. Go to Network tab
3. Visit the login page
4. Look for a request to `/api/auth/config`
5. Should return: `{ "azure_sso_enabled": true }`

**If broken:**
- SSO button won't appear
- You'll only see "Email login" option
- Console will show CORS errors or 404s

---

### Test 3: Admin Portal ✅ READY TO TEST

**What to test:** Can you manage users and department access?

**Prerequisites:**
- ✅ You're logged in (Test 1 passed)
- ✅ Your role is "admin" (seeded in migration)

**Steps:**
1. Navigate to `/admin` or `/admin/users`
2. You should see the admin portal

**Test 3a: View Users**
- You should see yourself in the user list
- Email: mhartigan@driscollfoods.com
- Role: admin
- Departments: All 6 (accounting, credit, it, purchasing, sales, warehouse)

**Test 3b: Create a Test User**
1. Click "Add User" or similar button
2. Fill in:
   - Email: `test@driscollfoods.com`
   - Name: `Test User`
   - Role: `user` (not admin)
3. Save
4. User should appear in the list

**Test 3c: Assign Department Access**
1. Find the test user you just created
2. Click "Edit Access" or similar
3. Assign access to: `purchasing` department
4. Save
5. Verify test user now shows "purchasing" in their departments

**Expected Database State After Test 3c:**
```sql
-- New user record
SELECT * FROM enterprise.users WHERE email = 'test@driscollfoods.com';
-- Should show: role='user', no azure_oid yet

-- New access grant
SELECT * FROM enterprise.access_config WHERE user_id = <test-user-id>;
-- Should show: department='purchasing', access_level='read'

-- Audit trail
SELECT * FROM enterprise.access_audit_log ORDER BY created_at DESC LIMIT 1;
-- Should show: action='grant', actor_id=<your-id>, target_id=<test-user-id>
```

**Test 3d: View Audit Log**
1. Navigate to `/admin/audit` (if it exists)
2. You should see the access grant you just made
3. Details should show:
   - Action: "grant"
   - Actor: "Matt Hartigan"
   - Target: "Test User"
   - Department: "purchasing"

---

### Test 4: Department Head Constraints 🔐 AUTHORIZATION TEST

**What to test:** Dept heads can only manage their own departments

**Setup:**
1. Create a test dept head user (via admin portal)
   - Email: `purchasing_head@driscollfoods.com`
   - Role: `dept_head` (not admin!)
2. Assign them access to `purchasing` with `is_dept_head=true`

**Manual SQL (use Azure Data Studio or psql):**
```sql
-- Insert dept head user
INSERT INTO enterprise.users (tenant_id, email, display_name, role)
SELECT t.id, 'purchasing_head@driscollfoods.com', 'Purchasing Head', 'dept_head'
FROM enterprise.tenants t WHERE t.slug = 'driscoll';

-- Grant them purchasing access as dept head
INSERT INTO enterprise.access_config (user_id, department, access_level, is_dept_head, granted_by)
SELECT u.id, 'purchasing', 'admin', true, m.id
FROM enterprise.users u
CROSS JOIN enterprise.users m
WHERE u.email = 'purchasing_head@driscollfoods.com'
  AND m.email = 'mhartigan@driscollfoods.com';
```

**Test:**
1. Log out as Matt
2. Log in as `purchasing_head@driscollfoods.com` (if SSO is set up, otherwise use email login)
3. Navigate to `/admin/users`
4. Try to assign a user to `purchasing` department
   - ✅ Should WORK
5. Try to assign a user to `sales` department
   - ❌ Should FAIL (403 Forbidden or UI disables the option)

**Expected Behavior:**
- Dept heads see a LIMITED admin interface
- They can only manage users for THEIR departments
- UI should hide departments they don't manage
- Backend should reject attempts to grant access to other depts

---

### Test 5: RAG Query with Department Filtering 📄 NEEDS DOCUMENTS

**What to test:** Users only see documents from their departments

**Prerequisites:**
- ⚠️ No documents exist yet (need to upload)
- ⚠️ Document upload endpoint needs to be available

**Steps to set up:**
1. Find the document upload endpoint (check `auth/admin_routes.py`)
2. Upload a test document:
   - Title: "Vendor Policy 2024"
   - Content: "Our vendor payment terms are NET30..."
   - Department: `purchasing`
   - Source: "vendor_policy.pdf"

**Manual SQL (if no upload endpoint yet):**
```sql
-- Insert a test document
INSERT INTO enterprise.documents (department_id, title, content, metadata, source_file)
SELECT
    d.id,
    'Vendor Policy 2024',
    'Our vendor payment terms are NET30. All vendors must provide proof of insurance...',
    '{"type": "policy", "year": 2024}'::jsonb,
    'purchasing/vendor_policy.pdf'
FROM enterprise.departments d
WHERE d.slug = 'purchasing';
```

**Test Query:**
1. Log in as the test user (test@driscollfoods.com)
   - Has access to: `purchasing` only
2. Ask a question: "What are our vendor terms?"
3. System should:
   - Generate embedding for query
   - Search documents WHERE user has dept access
   - Only return purchasing documents
4. Response should cite: "purchasing/vendor_policy.pdf"

**Verification SQL:**
```sql
-- What documents CAN test@driscollfoods.com see?
SELECT
    d.title,
    dept.name as department
FROM enterprise.documents d
JOIN enterprise.departments dept ON d.department_id = dept.id
JOIN enterprise.access_config ac ON ac.department = dept.slug
JOIN enterprise.users u ON u.id = ac.user_id
WHERE u.email = 'test@driscollfoods.com';

-- Should return: Only documents from 'purchasing' department
```

**Advanced Test:**
1. Grant test user access to `sales` department too
2. Upload a document to `sales` department
3. Ask the same question again
4. System should now return documents from BOTH purchasing AND sales

---

## 🐛 Troubleshooting

### Issue: SSO Button Not Visible

**Symptoms:**
- Only see "Email login" option
- No "Sign in with Microsoft" button

**Causes:**
1. `VITE_API_URL` not set in Railway frontend service
2. Frontend can't reach backend `/api/auth/config` endpoint
3. CORS blocking the request

**Fix:**
1. Add `VITE_API_URL` to Railway frontend service
2. Check backend CORS settings allow frontend origin
3. Redeploy frontend

---

### Issue: SSO Login Fails with 500 Error

**Symptoms:**
- Click SSO button
- Redirect to Microsoft
- Redirect back to app
- Get 500 Internal Server Error

**Causes:**
1. Database query error (unlikely after migration)
2. `azure_oid` column missing (FIXED by migration)
3. Backend can't connect to database

**Debug:**
1. Check Railway backend logs
2. Look for SQL errors
3. Verify database connection string in backend env vars

**Test database connection:**
```bash
# From local machine with .env file
python db/migrations/validate_schema.py
```

---

### Issue: Can't Access Admin Portal

**Symptoms:**
- Navigate to `/admin`
- Get redirected to login or see 403 Forbidden

**Causes:**
1. Not logged in
2. Role is not 'admin' or 'dept_head'
3. Frontend route guard rejecting you

**Fix:**
1. Verify you're logged in (check top-right corner for name)
2. Verify your role in database:
```sql
SELECT role FROM enterprise.users WHERE email = 'mhartigan@driscollfoods.com';
-- Should return: 'admin'
```
3. Check browser console for errors

---

### Issue: Department Access Not Saving

**Symptoms:**
- Assign department access to a user
- Click save
- Access doesn't appear in the list

**Causes:**
1. Backend API error (check logs)
2. Missing permissions (unlikely for admin)
3. Frontend bug (not sending request)

**Debug:**
1. Open browser Network tab (F12)
2. Watch for POST request to `/api/admin/users/{id}/access`
3. Check response:
   - 200 OK → Should work
   - 403 Forbidden → Permission issue
   - 500 Error → Backend bug, check logs

**Manual verification:**
```sql
-- Check if access_config record was created
SELECT * FROM enterprise.access_config
WHERE user_id = <user-id>
ORDER BY granted_at DESC;
```

---

## 📊 Verification Queries

### Check Your Admin Status
```sql
SELECT
    u.email,
    u.display_name,
    u.role,
    u.azure_oid,
    array_agg(ac.department ORDER BY ac.department) as departments,
    array_agg(ac.is_dept_head) as is_dept_head_flags
FROM enterprise.users u
LEFT JOIN enterprise.access_config ac ON u.id = ac.user_id
WHERE u.email = 'mhartigan@driscollfoods.com'
GROUP BY u.id;

-- Expected:
-- role: admin
-- departments: [accounting, credit, it, purchasing, sales, warehouse]
-- is_dept_head_flags: [true, true, true, true, true, true]
```

### Check All Users
```sql
SELECT
    u.email,
    u.display_name,
    u.role,
    COUNT(ac.id) as dept_count
FROM enterprise.users u
LEFT JOIN enterprise.access_config ac ON u.id = ac.user_id
GROUP BY u.id
ORDER BY u.created_at;
```

### Check Audit Trail
```sql
SELECT
    aal.created_at,
    aal.action,
    actor.email as actor_email,
    target.email as target_email,
    aal.department_slug,
    aal.new_value
FROM enterprise.access_audit_log aal
LEFT JOIN enterprise.users actor ON aal.actor_id = actor.id
LEFT JOIN enterprise.users target ON aal.target_id = target.id
ORDER BY aal.created_at DESC
LIMIT 10;
```

### Check Document Count by Department
```sql
SELECT
    dept.name,
    COUNT(d.id) as document_count
FROM enterprise.departments dept
LEFT JOIN enterprise.documents d ON d.department_id = dept.id
GROUP BY dept.id, dept.name
ORDER BY dept.name;

-- Currently all should be 0 (no documents uploaded yet)
```

---

## ✅ Success Criteria

### Minimum Viable Test (Must Pass)
- [ ] Test 1: You can log in via Azure SSO
- [ ] Test 3a: You see yourself in admin portal user list
- [ ] Test 3b: You can create a new test user
- [ ] Test 3c: You can assign department access

### Full Test Suite (Should Pass)
- [ ] Test 1: Azure SSO login works
- [ ] Test 2: VITE_API_URL is set correctly
- [ ] Test 3: All admin portal features work (users, access, audit)
- [ ] Test 4: Dept head constraints enforced
- [ ] Test 5: RAG queries filtered by department (after uploading docs)

### Known Limitations (Expected)
- ⚠️ No documents exist yet (enterprise.documents is empty)
- ⚠️ Only one user exists (you - Matt)
- ⚠️ Query log is empty (will populate as users query)
- ⚠️ No analytics yet (need query history)

---

## 🚀 Next Steps After Testing

### If Tests Pass ✅
1. **Upload Production Documents**
   - Organize by department
   - Tag with metadata (type, date, source)
   - Generate embeddings (BGE-M3)

2. **Create Real Users**
   - Sales team members
   - Purchasing team members
   - Credit team members
   - Etc.

3. **Set Up Department Heads**
   - Assign `role='dept_head'`
   - Grant `is_dept_head=true` for their department
   - Let them manage their own team

4. **Monitor Audit Log**
   - Watch who grants what access
   - Review compliance periodically

### If Tests Fail ❌
1. **Check Railway Logs**
   - Backend service logs
   - Frontend service logs
   - Look for errors

2. **Verify Database State**
   - Run validation script: `python db/migrations/validate_schema.py`
   - Check for schema drift

3. **Review Environment Variables**
   - Frontend: `VITE_API_URL`
   - Backend: All `AZURE_AD_*` and `AZURE_PG_*` vars

4. **Contact Support**
   - Share error logs
   - Share browser console errors
   - Share SQL query results

---

## 📞 Getting Help

**For Database Issues:**
- Run validation: `python db/migrations/validate_schema.py`
- Check `.claude/CHANGELOG_COMPACT.md` for recent changes
- Review `docs/MIGRATION_001_SUMMARY.md` for full details

**For Auth Issues:**
- Check `docs/FRONTEND_AUTH_RECON.md` (from previous session)
- Verify Azure AD credentials in Railway backend
- Verify VITE_API_URL in Railway frontend

**For General Questions:**
- Schema diagram: `docs/SCHEMA_DIAGRAM.md`
- Architecture decisions: `docs/recon/ADMIN_PORTAL_RECON.md`
- Database gap analysis: `docs/recon/DATABASE_GAP_ANALYSIS.md`

---

**Good luck with testing! 🎉**

**Expected Timeline:**
- Test 1 (SSO): 5 minutes
- Test 2 (Frontend): 10 minutes (if fix needed)
- Test 3 (Admin Portal): 15 minutes
- Test 4 (Dept Head): 20 minutes (manual setup needed)
- Test 5 (RAG): 30 minutes (document upload needed)

**Total:** ~1.5 hours for comprehensive testing
