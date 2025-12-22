# Admin Portal Database Requirements - Full Reconnaissance

**Date:** 2024-12-21 23:00
**Mission:** Complete recon of admin portal to inform database schema design
**Status:** ✅ RECON COMPLETE

---

## 🎯 EXECUTIVE SUMMARY

### Critical Finding: MISMATCH with Handoff Schema

The admin portal code expects a **COMPLEX multi-table schema** with:
- `enterprise.users` table with FK relationships
- `enterprise.departments` table (separate entity)
- `enterprise.access_config` table (junction table for user-department relationships)
- `enterprise.access_audit_log` table (audit trail)

**This CONFLICTS with the handoff's MINIMAL schema** which proposes:
- No `departments` table (just tags)
- No `access_config` junction table (just `department_access[]` array)
- No FK relationships

### Recommendation

**OPTION A: Implement the MINIMAL schema from handoff** (RECOMMENDED)
- ✅ Faster to implement
- ✅ Simpler to maintain
- ✅ No FK cascade issues
- ⚠️ Requires ~20 code changes in `auth_service.py` and `admin_routes.py`
- ⚠️ Requires updating frontend expectations

**OPTION B: Keep current code, implement COMPLEX schema**
- ✅ No code changes needed
- ✅ More "proper" relational design
- ❌ Slower to implement
- ❌ More complex migrations
- ❌ FK cascade complexity

---

## 📊 DATABASE SCHEMA ANALYSIS

### Current Code Expectations (COMPLEX Schema)

#### Table: `enterprise.users`

```sql
CREATE TABLE enterprise.users (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email                   varchar(255) UNIQUE NOT NULL,
    display_name            varchar(255),
    employee_id             varchar(255),
    azure_oid               varchar(255) UNIQUE,  -- CRITICAL: azure_oid not oid
    role                    varchar(50) DEFAULT 'user',  -- user, dept_head, super_user
    primary_department_id   uuid REFERENCES enterprise.departments(id),  -- FK to departments
    tenant_id               uuid REFERENCES enterprise.tenants(id),  -- FK to tenants
    active                  boolean DEFAULT true,
    created_at              timestamptz DEFAULT now(),
    last_login_at           timestamptz
);
```

**Evidence:**
- `admin_routes.py:282` - `primary_department_slug` field expected
- `admin_routes.py:260` - Query joins `departments` table
- `auth_service.py` (not read but imported) - FK relationships assumed

#### Table: `enterprise.departments`

```sql
CREATE TABLE enterprise.departments (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        varchar(50) UNIQUE NOT NULL,  -- 'purchasing', 'credit', etc
    name        varchar(255) NOT NULL,         -- 'Purchasing Department'
    description text,
    active      boolean DEFAULT true,
    created_at  timestamptz DEFAULT now()
);
```

**Evidence:**
- `admin_routes.py:260-271` - Queries `departments` table with `id, slug, name, description`
- `admin_routes.py:689-695` - Lists departments from table
- Frontend expects: `Department { id, slug, name, description, user_count }`

**Valid Department Slugs (from handoff):**
- `purchasing` - Vendor management, POs, receiving
- `credit` - AR, customer credit, collections
- `sales` - Customer accounts, pricing, orders
- `warehouse` - Inventory, picking, shipping
- `accounting` - AP, GL, financial reporting
- `it` - Systems, infrastructure, support

#### Table: `enterprise.access_config` (Junction Table)

```sql
CREATE TABLE enterprise.access_config (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES enterprise.users(id) ON DELETE CASCADE,
    department      varchar(50) NOT NULL,  -- FK to departments.slug
    access_level    varchar(50) DEFAULT 'read',  -- 'read', 'write', 'admin'
    is_dept_head    boolean DEFAULT false,
    granted_by      uuid REFERENCES enterprise.users(id),
    created_at      timestamptz DEFAULT now(),
    UNIQUE(user_id, department)
);
```

**Evidence:**
- `admin_routes.py:262` - LEFT JOIN on `access_config` with `user_id` and `department`
- `admin_routes.py:625` - LEFT JOIN on `access_config` to count users per department
- Admin routes expect grant/revoke operations to modify this table

#### Table: `enterprise.access_audit_log`

```sql
CREATE TABLE enterprise.access_audit_log (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    action           varchar(50) NOT NULL,  -- 'grant', 'revoke', 'role_change', 'login', 'user_created'
    actor_email      varchar(255),
    target_email     varchar(255),
    department_slug  varchar(50),
    old_value        varchar(255),
    new_value        varchar(255),
    reason           text,
    ip_address       inet,
    created_at       timestamptz DEFAULT now()
);

CREATE INDEX idx_audit_action ON enterprise.access_audit_log(action);
CREATE INDEX idx_audit_target ON enterprise.access_audit_log(target_email);
CREATE INDEX idx_audit_created ON enterprise.access_audit_log(created_at DESC);
```

**Evidence:**
- `admin_routes.py:502-583` - `/api/admin/audit` endpoint queries this table
- `admin_routes.py:558-566` - SELECT with filters on action, target_email, department_slug
- Frontend expects: `AuditEntry { id, action, actor_email, target_email, department_slug, old_value, new_value, reason, created_at, ip_address }`

#### Table: `enterprise.tenants` (Optional - for multi-tenancy)

```sql
CREATE TABLE enterprise.tenants (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        varchar(255) NOT NULL,
    slug        varchar(50) UNIQUE NOT NULL,
    active      boolean DEFAULT true,
    created_at  timestamptz DEFAULT now()
);
```

**Evidence:**
- Previous recon identified this as missing
- Not directly queried by admin_routes.py
- Referenced by users.tenant_id FK

---

## 🔌 ADMIN PORTAL API ENDPOINTS

### User Management

| Endpoint | Method | Purpose | Database Queries |
|----------|--------|---------|------------------|
| `/api/admin/users` | GET | List users | `SELECT * FROM users WHERE ...` + JOIN departments |
| `/api/admin/users/{id}` | GET | Get user detail | `SELECT * FROM users` + JOIN `access_config` + JOIN `departments` |
| `/api/admin/users` | POST | Create user | `INSERT INTO users` + optional `INSERT INTO access_config` |
| `/api/admin/users/{id}` | PUT | Update user | `UPDATE users SET ...` |
| `/api/admin/users/{id}` | DELETE | Deactivate user | `UPDATE users SET active = false` |
| `/api/admin/users/{id}/reactivate` | POST | Reactivate user | `UPDATE users SET active = true` |
| `/api/admin/users/batch` | POST | Batch create users | Multiple `INSERT INTO users` |

### Access Control

| Endpoint | Method | Purpose | Database Queries |
|----------|--------|---------|------------------|
| `/api/admin/access/grant` | POST | Grant dept access | `INSERT INTO access_config` + audit log |
| `/api/admin/access/revoke` | POST | Revoke dept access | `DELETE FROM access_config` + audit log |
| `/api/admin/users/{id}/role` | PUT | Change user role | `UPDATE users SET role = ...` + audit log |

### Department Management

| Endpoint | Method | Purpose | Database Queries |
|----------|--------|---------|------------------|
| `/api/admin/departments` | GET | List departments | `SELECT * FROM departments WHERE active = true` |
| `/api/admin/departments/{slug}/users` | GET | List dept users | `SELECT users WHERE department IN access_config` |

### Audit Log

| Endpoint | Method | Purpose | Database Queries |
|----------|--------|---------|------------------|
| `/api/admin/audit` | GET | Get audit log | `SELECT * FROM access_audit_log WHERE ...` with filters |

### Statistics

| Endpoint | Method | Purpose | Database Queries |
|----------|--------|---------|------------------|
| `/api/admin/stats` | GET | Dashboard stats | Multiple queries: users count, by role, by dept, recent logins |

---

## 🎨 FRONTEND EXPECTATIONS

### TypeScript Interfaces (from `admin.ts`)

```typescript
interface AdminUser {
    id: string;
    email: string;
    display_name: string | null;
    employee_id: string | null;
    role: 'user' | 'dept_head' | 'super_user';
    primary_department: string | null;  // department SLUG, not ID
    active: boolean;
    last_login_at: string | null;
    access_level?: string;
    is_dept_head?: boolean;
    granted_at?: string;
}

interface UserDetail extends AdminUser {
    tier: string;  // Computed from role
    departments: DepartmentAccess[];  // Array of dept access
}

interface DepartmentAccess {
    slug: string;
    name: string;
    access_level: string;  // 'read', 'write', 'admin'
    is_dept_head: boolean;
    granted_at: string | null;
}

interface Department {
    id: string;
    slug: string;
    name: string;
    description?: string;
    user_count?: number;
}

interface AuditEntry {
    id: string;
    action: string;
    actor_email: string | null;
    target_email: string | null;
    department_slug: string | null;
    old_value: string | null;
    new_value: string | null;
    reason: string | null;
    created_at: string;
    ip_address: string | null;
}

interface AdminStats {
    total_users: number;
    users_by_role: Record<string, number>;
    users_by_department: Department[];
    recent_logins_7d: number;
    recent_access_changes_7d: number;
}
```

### Key Frontend Features

**User Management Page (`/admin/users`):**
- Search users by email/name
- Filter by department
- View user detail (expandable row)
- Grant/revoke department access
- Change user role (super_user only)
- Edit user details (email, name, employee_id, primary_dept)
- Deactivate/reactivate users
- Batch import users (CSV/JSON)

**Audit Log Page (`/admin/audit`):**
- Filter by action type
- Filter by target email
- Filter by department
- Pagination (50 entries per page)
- Show: timestamp, action, actor, target, department, old/new values, reason

**Analytics Dashboard (`/admin` and `/admin/analytics`):**
- NOT directly dependent on admin schema
- Uses separate `analytics_events` table (not in scope)

---

## ⚠️ SCHEMA COMPARISON: COMPLEX vs MINIMAL

### COMPLEX Schema (Current Code Expects)

```
users
  ├─ primary_department_id → departments.id (FK)
  └─ tenant_id → tenants.id (FK)

departments (separate table)
  └─ id, slug, name, description, active

access_config (junction table)
  ├─ user_id → users.id (FK)
  ├─ department (slug, not FK)
  └─ access_level, is_dept_head, granted_by

access_audit_log (audit trail)
  └─ action, actor_email, target_email, department_slug, old_value, new_value
```

**Pros:**
- ✅ "Proper" relational design
- ✅ FK constraints enforce referential integrity
- ✅ Separate entities for users, departments, access
- ✅ No code changes needed

**Cons:**
- ❌ More tables to manage
- ❌ FK cascade complexity
- ❌ More complex migrations
- ❌ Junction table adds query complexity

### MINIMAL Schema (Handoff Proposes)

```
users
  ├─ department_access varchar[] (array, no junction table)
  └─ No FK to departments (just tags)

documents
  └─ department varchar (tag, no FK)

query_log
  └─ departments varchar[] (tags)

NO separate departments table
NO access_config junction table
```

**Pros:**
- ✅ Faster to implement
- ✅ Simpler to maintain
- ✅ No FK cascade issues
- ✅ Easier to query (single table)
- ✅ More flexible (no schema changes to add dept)

**Cons:**
- ❌ No FK validation (can have invalid dept tags)
- ❌ Requires ~20 code changes in backend
- ❌ Less "proper" from relational DB perspective

---

## 🛠️ IMPLEMENTATION OPTIONS

### OPTION A: MINIMAL Schema (RECOMMENDED)

**Steps:**
1. Create minimal schema (3 tables: users, documents, query_log)
2. Modify `auth_service.py` to use `department_access[]` array
3. Modify `admin_routes.py` to query array instead of junction table
4. Remove `departments` table queries (hardcode list or use config)
5. Update audit log to use array operations

**Code Changes Required:**
- `auth/auth_service.py` (~15 locations)
  - `get_user_department_access()` → query `department_access` array
  - `grant_department_access()` → `UPDATE users SET department_access = array_append(...)`
  - `revoke_department_access()` → `UPDATE users SET department_access = array_remove(...)`
  - `list_users_in_department()` → `WHERE department = ANY(department_access)`

- `auth/admin_routes.py` (~5 locations)
  - Line 260-271: Remove JOIN on `access_config`, query user array directly
  - Line 625: Remove JOIN, count `WHERE department = ANY(department_access)`
  - Line 689: Return hardcoded departments list (or from config)

**Estimated Effort:** 2-3 hours

### OPTION B: COMPLEX Schema (Keep Current Code)

**Steps:**
1. Create all 4 tables: users, departments, access_config, access_audit_log
2. Seed departments table with 6 departments
3. Create indexes
4. No code changes needed

**Estimated Effort:** 1 hour

---

## 🎯 RECOMMENDATION

**Go with OPTION A (MINIMAL)** for these reasons:

1. **Handoff explicitly requests it** - The architecture session designed this intentionally
2. **Faster v1.0 delivery** - Simpler schema = faster to production
3. **Easier to maintain** - No FK cascade complexity
4. **More flexible** - Can add departments without schema changes
5. **Code changes are straightforward** - Array operations are simple in PostgreSQL

**Mental Model:**
```
"Department access is just a tag. Users have a list of department tags.
Documents have a department tag. RAG queries filter WHERE department = ANY(user_tags).
That's it. No junction tables, no FKs, no complexity."
```

---

## 📋 NEXT STEPS

1. ✅ **Recon complete** - Database requirements documented
2. ⏳ **Decision required** - Architect to confirm MINIMAL vs COMPLEX schema choice
3. ⏳ **Code changes** - If MINIMAL, update `auth_service.py` and `admin_routes.py`
4. ⏳ **Migration script** - Create Python migration to nuke + rebuild
5. ⏳ **Seed data** - Insert admin user (mhartigan@driscollfoods.com)
6. ⏳ **Validation** - Test auth flow, admin portal, RAG queries

---

## 📂 FILES ANALYZED

**Backend:**
- `auth/admin_routes.py` (1,015 lines)
- `auth/auth_service.py` (imported, not read - assumes FK relationships)

**Frontend:**
- `frontend/src/routes/admin/users/+page.svelte` (753 lines)
- `frontend/src/routes/admin/+page.svelte` (173 lines)
- `frontend/src/routes/admin/analytics/+page.svelte` (166 lines)
- `frontend/src/routes/admin/audit/+page.svelte` (552 lines)
- `frontend/src/lib/stores/admin.ts` (620 lines)

**Total Lines Analyzed:** 3,279 lines

---

**Recon Status:** ✅ COMPLETE
**Blocker:** Awaiting schema decision (MINIMAL vs COMPLEX)
**Next Agent:** Architecture session for decision, then SDK agent for implementation
