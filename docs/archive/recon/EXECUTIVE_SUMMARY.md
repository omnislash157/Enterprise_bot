# Auth System Recon - Executive Summary

**Date:** 2024-12-21
**Status:** 🔴 CRITICAL BLOCKERS IDENTIFIED
**Priority:** HIGH - Blocking production SSO login

---

## Current State

The auth system is experiencing a **database schema mismatch** between code expectations and actual database structure. The application code expects a full multi-tenant schema with audit trails, but the database has a simplified implementation.

### Key Finding
**ROOT CAUSE:** Missing tables and column name mismatches are causing auth features to fail silently. The Azure SSO button doesn't render because the backend can't query non-existent tables.

---

## Critical Blockers

### 🔴 BLOCKER 1: Missing Tables
**Impact:** Backend routes fail when querying non-existent tables

| Table | Expected By | Status | Impact |
|-------|-------------|--------|--------|
| `enterprise.tenants` | auth_schema.py:117,285<br>auth_service.py:285-290 | ❌ MISSING | Tenant lookups fail, can't create users |
| `enterprise.departments` | auth_schema.py:123,163<br>auth_service.py:329-331<br>admin_routes.py:688-695 | ❌ MISSING | Department name lookups fail, admin portal breaks |
| `enterprise.access_audit_log` | auth_service.py:303-307<br>admin_routes.py:523-583 | ❌ MISSING | No audit trail, admin audit view 500s |

**Consequence:**
- User creation fails (no tenant to assign)
- Admin portal department dropdowns empty
- Audit log endpoint returns 500 error
- SSO login partially works but features break

### 🔴 BLOCKER 2: Column Name Mismatch
**Impact:** Azure SSO users can't be found after login

```
CODE EXPECTS:     enterprise.users.azure_oid
DATABASE HAS:     enterprise.users.oid
```

**Locations:**
- `auth_service.py:1035` - `WHERE u.azure_oid = %s`
- `auth_service.py:1089` - `INSERT ... azure_oid, ...`
- Database schema uses `oid` column

**Consequence:**
- Azure SSO login succeeds but user lookup fails
- Every login creates duplicate user records
- User is created but immediately "not found"

### 🔴 BLOCKER 3: Missing User Columns
**Impact:** Profile features and advanced auth don't work

| Column | Expected By | Status | Impact |
|--------|-------------|--------|--------|
| `employee_id` | auth_schema.py:114<br>auth_service.py:94 | ❌ MISSING | Can't filter by sales rep ID |
| `tenant_id` | auth_schema.py:117<br>auth_service.py:96,213 | ❌ MISSING | Can't assign users to tenants |
| `primary_department_id` | auth_schema.py:123<br>auth_service.py:97,215 | ❌ MISSING | No default department |
| `sso_provider` | auth_schema.py:130 | ❌ MISSING | Can't distinguish SSO types |
| `updated_at` | auth_schema.py:135 | ❌ MISSING | No update tracking |

---

## Database Status

### What Exists ✅
| Table | Purpose | Health |
|-------|---------|--------|
| `enterprise.users` | User accounts | ⚠️ Partial - missing columns |
| `enterprise.access_config` | User→department mapping | ✅ Working - slug-based |
| `enterprise.documents` | RAG document chunks | ✅ Working |
| `enterprise.query_log` | Query logging | ✅ Working |
| `enterprise.analytics_events` | Event tracking | ✅ Working |

### What's Missing ❌
| Table | Priority | Blocking |
|-------|----------|----------|
| `enterprise.tenants` | HIGH | User creation, multi-tenancy |
| `enterprise.departments` | HIGH | Admin portal, dept names |
| `enterprise.access_audit_log` | MEDIUM | Audit compliance, admin logs |
| `enterprise.analytics_daily` | LOW | Pre-computed analytics |

---

## Auth Flow Status

### Azure SSO: 🟡 PARTIAL
- ✅ OAuth2 flow works (redirect → code exchange)
- ✅ Token validation works
- ✅ Basic user creation works (with missing columns)
- ❌ User lookup fails (`azure_oid` vs `oid`)
- ❌ Department assignment fails (no departments table)
- ❌ Tenant assignment fails (no tenants table)

### Email Fallback: 🟢 WORKING
- ✅ Simple email lookup works
- ✅ Department access via `access_config` works
- ⚠️ Missing user profile fields

### Admin Portal: 🔴 BROKEN
- ❌ User list partially works (missing tenant/dept names)
- ❌ Department dropdown empty (no departments table)
- ❌ Audit log 500 error (no audit_log table)
- ❌ Stats page breaks (queries non-existent tables)

---

## Recommended Sequence

### Phase 1: Emergency Fixes (< 1 hour)
**Goal:** Make SSO login work end-to-end

1. **Fix column name mismatch**
   ```sql
   ALTER TABLE enterprise.users RENAME COLUMN oid TO azure_oid;
   ```
   - OR: Update code to use `oid` consistently
   - Files: `auth_service.py` lines 1035, 1089, 1125, 1161

2. **Create tenants table + seed Driscoll**
   ```sql
   CREATE TABLE enterprise.tenants (
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     slug varchar UNIQUE NOT NULL,
     name varchar NOT NULL,
     active boolean DEFAULT TRUE
   );
   INSERT INTO enterprise.tenants (slug, name) VALUES ('driscoll', 'Driscoll Foods');
   ```

3. **Add tenant_id to users**
   ```sql
   ALTER TABLE enterprise.users ADD COLUMN tenant_id uuid;
   UPDATE enterprise.users SET tenant_id = (SELECT id FROM enterprise.tenants WHERE slug = 'driscoll');
   ```

**Test:** SSO login should now work without errors

### Phase 2: Core Features (2-3 hours)
**Goal:** Restore admin portal functionality

4. **Create departments table + seed data**
   - Use existing department slugs from `access_config` table
   - Populate: warehouse, sales, credit, purchasing, transportation, hr, executive

5. **Create access_audit_log table**
   - Enable audit logging for compliance
   - Fix admin portal audit view

6. **Add missing user columns**
   - `employee_id`, `primary_department_id`, `sso_provider`, `updated_at`

**Test:** Admin portal should work fully

### Phase 3: Enhancements (4-6 hours)
**Goal:** Production-ready multi-tenant system

7. **Add foreign key constraints**
   - `users.tenant_id → tenants.id`
   - `users.primary_department_id → departments.id`
   - `access_config.user_id → users.id`

8. **Create analytics_daily table**
   - Enable pre-computed analytics

9. **Migration script for existing data**
   - Backfill tenant_id for existing users
   - Create audit log entries for historical changes

**Test:** Full regression test of auth system

---

## Estimated Effort

| Phase | Complexity | Time | Priority |
|-------|------------|------|----------|
| Phase 1: Emergency Fixes | LOW | 1 hour | 🔴 CRITICAL |
| Phase 2: Core Features | MEDIUM | 2-3 hours | 🟠 HIGH |
| Phase 3: Enhancements | HIGH | 4-6 hours | 🟡 MEDIUM |

**Total:** 7-10 hours to full production readiness

---

## Risks

### 🔴 HIGH: Production Data Integrity
- **Issue:** No FK constraints means orphaned records possible
- **Mitigation:** Add constraints in Phase 3
- **Timeline:** Current system works without them, but should add before scaling

### 🟠 MEDIUM: Existing User Data
- **Issue:** Existing users in database may have incomplete data
- **Mitigation:** Backfill script in Phase 3
- **Timeline:** Won't break existing logins, but profiles incomplete

### 🟡 LOW: Audit Log Gap
- **Issue:** No historical audit data
- **Mitigation:** Start logging after table creation
- **Timeline:** Compliance may require explanation of gap

---

## Files That Need Changes

### Backend (Python)
| File | Change Type | Priority | Details |
|------|-------------|----------|---------|
| `auth_service.py` | CODE | 🔴 CRITICAL | Lines 1035,1089,1125,1161 - change `azure_oid` to `oid` OR rename DB column |
| `auth_schema.py` | RUN SCRIPT | 🔴 CRITICAL | Run `--init` to create missing tables |
| `auth_service.py` | FIX | 🟠 HIGH | Handle missing tenant gracefully (lines 285-290) |
| `admin_routes.py` | FIX | 🟠 HIGH | Add null checks for departments (lines 256-263) |

### Database (SQL)
| Change | Priority | Command |
|--------|----------|---------|
| Rename column | 🔴 CRITICAL | `ALTER TABLE users RENAME COLUMN oid TO azure_oid` |
| Create tenants | 🔴 CRITICAL | Run `auth_schema.py --init` (partial) |
| Create departments | 🟠 HIGH | Run migration script |
| Create audit_log | 🟠 HIGH | Run `auth_schema.py --init` (partial) |
| Add user columns | 🟠 HIGH | Run migration script |

### Frontend (TypeScript/Svelte)
| File | Change Type | Priority | Details |
|------|-------------|----------|---------|
| ✅ NONE | - | - | Frontend code is correct, issues are backend |

---

## Decision Points

### Option A: Rename Database Column ✅ RECOMMENDED
**Pros:**
- Code is more complete than DB
- Other code may reference `azure_oid`
- Future-proof for multiple SSO providers

**Cons:**
- Requires DB migration
- Need to update existing `oid` data

**Command:**
```sql
ALTER TABLE enterprise.users RENAME COLUMN oid TO azure_oid;
```

### Option B: Update Code to Use `oid`
**Pros:**
- No DB migration needed
- Faster immediate fix

**Cons:**
- Code expects `azure_oid` everywhere
- Less clear for future SSO types
- 4+ file locations to change

**Not Recommended**

---

## Next Steps

1. ✅ **Review this summary** - Confirm findings align with symptoms
2. 🔄 **Choose approach** - Option A (rename column) or B (update code)
3. 📋 **Run Phase 1 fixes** - Execute emergency SQL + code changes
4. ✅ **Test SSO login** - Verify end-to-end flow works
5. 📋 **Plan Phase 2** - Schedule admin portal restoration
6. 📊 **Monitor** - Watch logs for remaining issues

---

## Contact Points for Questions

- **Schema Design:** `auth_schema.py` has complete ideal schema
- **Access Logic:** `auth_service.py` has all business logic
- **API Routes:** `sso_routes.py` and `admin_routes.py`
- **Frontend Flow:** `auth.ts` store (line 78-93 for init logic)
- **Database State:** This recon's `DATABASE_ACTUAL_STATE.md`

---

**END OF EXECUTIVE SUMMARY**
