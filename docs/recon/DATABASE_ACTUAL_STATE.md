# Database Actual State - PostgreSQL Azure

**Audit Date:** 2024-12-21
**Database:** cogtwin.postgres.database.azure.com
**Connection:** postgres database, mhartigan user

---

## Schemas

```
✅ cron          - pg_cron extension tasks
✅ enterprise    - Main application schema
✅ personal      - User-specific data (separate from enterprise.users)
✅ public        - Default schema
```

## Tables by Schema

### cron schema (2 tables)
- `cron.job` - Scheduled task definitions
- `cron.job_run_details` - Task execution logs

### enterprise schema (5 tables)
- `enterprise.access_config` - **User-department access mapping**
- `enterprise.analytics_events` - Event tracking
- `enterprise.documents` - RAG document chunks with embeddings
- `enterprise.query_log` - Query logging
- `enterprise.users` - **User accounts**

### personal schema (3 tables)
- `personal.episodes` - User conversation episodes
- `personal.memory_nodes` - User memory graph
- `personal.users` - Personal schema user records (separate from enterprise.users)

---

## Critical Table: enterprise.users

**Purpose:** User authentication and authorization

```sql
CREATE TABLE enterprise.users (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  email character varying NOT NULL,
  display_name character varying NULL,
  oid character varying NULL,                    -- Azure Object ID
  role character varying NULL DEFAULT 'user',     -- user, dept_head, super_user
  is_active boolean NULL DEFAULT true,
  created_at timestamp with time zone NULL DEFAULT now(),
  last_login_at timestamp with time zone NULL,

  PRIMARY KEY (id),
  UNIQUE (email)
);
```

### Columns Present:
- ✅ `id` (uuid, primary key)
- ✅ `email` (varchar, unique, not null)
- ✅ `display_name` (varchar, nullable)
- ✅ `oid` (varchar, nullable) - Azure Object ID
- ✅ `role` (varchar, default 'user')
- ✅ `is_active` (boolean, default true)
- ✅ `created_at` (timestamp with time zone)
- ✅ `last_login_at` (timestamp with time zone, nullable)

### Columns MISSING (expected by code):
- ❌ `employee_id` - Referenced in auth_service.py, auth_schema.py
- ❌ `tenant_id` - Referenced everywhere as FK to enterprise.tenants
- ❌ `primary_department_id` - FK to enterprise.departments
- ❌ `sso_provider` - Track SSO provider type
- ❌ `sso_subject_id` - External SSO ID
- ❌ `email_verified` - Email verification flag
- ❌ `updated_at` - Last update timestamp
- ❌ `azure_oid` - The code uses `azure_oid`, but database has `oid`

**CRITICAL:** Column name mismatch: `azure_oid` (code) vs `oid` (database)

---

## Critical Table: enterprise.access_config

**Purpose:** Map users to departments they can access

```sql
CREATE TABLE enterprise.access_config (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  department character varying NOT NULL,            -- Department slug (string)
  granted_by uuid NULL,
  granted_at timestamp with time zone NULL DEFAULT now(),

  PRIMARY KEY (id),
  UNIQUE (user_id, department)
);
```

### Columns Present:
- ✅ `id` (uuid)
- ✅ `user_id` (uuid, FK to enterprise.users.id)
- ✅ `department` (varchar) - **Stores slug directly**
- ✅ `granted_by` (uuid, nullable)
- ✅ `granted_at` (timestamp)

### Design Note:
**This table stores `department` as a VARCHAR slug (e.g., "warehouse", "sales")**
- NOT a foreign key to enterprise.departments table
- The code expects this exact structure
- Auth service queries: `SELECT department FROM enterprise.access_config WHERE user_id = ?`

---

## Tables MISSING (expected by code)

### ❌ enterprise.tenants
Referenced in:
- `auth_schema.py` lines 117, 285-286, 621-623
- `auth_service.py` lines 285-290
- Expected columns: `id`, `slug`, `name`, `active`

### ❌ enterprise.departments
Referenced in:
- `auth_schema.py` lines 123, 163, 214, 464-467
- `auth_service.py` lines 200, 329-331, 416-417
- `admin_routes.py` lines 256-263, 688-695
- Expected columns: `id`, `slug`, `name`, `description`, `active`

### ❌ enterprise.user_department_access
**NOTE:** This is the OLD schema. The actual implementation uses `enterprise.access_config` instead.
- Code in `auth_schema.py` lines 153-193 defines this table
- But queries use `enterprise.access_config` instead
- This table should NOT be created (deprecated design)

### ❌ enterprise.access_audit_log
Referenced in:
- `auth_schema.py` lines 196-241
- `auth_service.py` lines 303-307, 430-440, 496-506, etc.
- `admin_routes.py` lines 523-583
- Expected columns: `id`, `action`, `actor_id`, `actor_email`, `target_user_id`, `target_email`, `department_slug`, `old_value`, `new_value`, `reason`, `created_at`, `ip_address`, `user_agent`

### ❌ enterprise.analytics_daily
Referenced in:
- `auth_schema.py` lines 377-427
- Expected: Pre-computed daily analytics aggregates

---

## Extensions Installed

```
✅ plpgsql v1.0         - PL/pgSQL language
✅ pgaadauth v1.9       - Azure AD authentication
✅ pg_cron v1.6         - Scheduled jobs
✅ azure v1.1           - Azure-specific functions
✅ vector v0.8.0        - pgvector for embeddings
```

---

## Database Health

| Aspect | Status | Notes |
|--------|--------|-------|
| Connection | ✅ Working | SSL required |
| Vector extension | ✅ Installed | v0.8.0 |
| User table exists | ✅ Yes | But missing columns |
| Access table exists | ✅ Yes | Uses slug-based design |
| Tenant table | ❌ Missing | Required by auth code |
| Department table | ❌ Missing | Required by auth code |
| Audit table | ❌ Missing | Required by admin portal |

---

## Summary

**What Works:**
- Basic user authentication (email + role)
- Azure OID storage (as `oid` column)
- Department access via `access_config` table
- Document storage with vector embeddings
- Query logging and analytics events

**What's Broken:**
- No tenant table → tenant_id FK fails
- No department table → department lookups fail
- Column name mismatch → `azure_oid` vs `oid`
- Missing audit log → admin portal audit views fail
- Missing user fields → profile features incomplete

**Migration Status:**
- Database is using a **simplified schema** compared to code expectations
- Access control works via `enterprise.access_config` (slug-based)
- Missing relational integrity (no FK constraints to tenants/departments)
