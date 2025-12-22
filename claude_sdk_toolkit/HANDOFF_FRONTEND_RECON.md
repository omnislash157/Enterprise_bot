# SDK Agent Handoff - Auth Refactor to Match Business Reality

**Date:** 2024-12-21 24:00
**From:** Claude Opus (Architecture Session)
**Priority:** CRITICAL
**Type:** FULL REFACTOR - Read Everything Before Touching Anything

---

## 🛑 STOP AND READ

The previous approach was backwards. We kept trying to patch code to match a messy schema. That's over.

**NEW APPROACH:**
1. Define the tables we ACTUALLY need (done below)
2. Find everything wired to auth_service.py BEFORE changing it
3. Nuke old tables, create new clean ones
4. Refactor auth_service.py to match the new tables
5. Fix any downstream dependencies

**THE TABLES ARE THE MISSION. Everything else serves the tables.**

---

## 📊 THE ONLY TABLES WE NEED

```sql
-- TABLE 1: TENANTS (domain validation only)
CREATE TABLE enterprise.tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug varchar(50) UNIQUE NOT NULL,       -- 'driscoll'
    name varchar(255) NOT NULL,             -- 'Driscoll Foods'
    domain varchar(255) NOT NULL            -- 'driscollfoods.com'
);

-- TABLE 2: USERS (everything about a person)
CREATE TABLE enterprise.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES enterprise.tenants(id),
    email varchar(255) UNIQUE NOT NULL,     -- SSO identity
    display_name varchar(255),              -- From Azure AD
    azure_oid varchar(255) UNIQUE,          -- Azure Object ID
    department_access varchar[] DEFAULT '{}',  -- ['sales','purchasing'] - can query these
    dept_head_for varchar[] DEFAULT '{}',      -- ['sales'] - can grant access to these
    is_super_user boolean DEFAULT false,       -- God mode
    created_at timestamptz DEFAULT now(),
    last_login_at timestamptz
);

-- INDEXES
CREATE INDEX idx_users_email ON enterprise.users(email);
CREATE INDEX idx_users_azure_oid ON enterprise.users(azure_oid);
CREATE INDEX idx_users_dept_access ON enterprise.users USING gin(department_access);
```

**THAT'S IT. TWO TABLES.**

No access_config. No access_audit_log. No departments table. No analytics_events.
No actor_id, target_id, target_user_id, actor_email, or any other slop.

---

## 🔍 PHASE 1: DEPENDENCY AUDIT (DO THIS FIRST)

Before touching ANY code, find everything that imports or uses auth_service:

```bash
# Find all files that import from auth_service
grep -r "from auth.auth_service" --include="*.py" .
grep -r "from auth import" --include="*.py" .
grep -r "import auth_service" --include="*.py" .
grep -r "get_auth_service" --include="*.py" .
grep -r "AuthService" --include="*.py" .

# Find all files that reference the User class
grep -r "from.*auth.*import.*User" --include="*.py" .

# Find all files that reference old tables directly
grep -r "access_config" --include="*.py" .
grep -r "access_audit_log" --include="*.py" .
grep -r "departments" --include="*.py" .
```

**DOCUMENT EVERY FILE THAT COMES UP.**

Expected hits:
- `core/main.py` - FastAPI routes
- `auth/admin_routes.py` - Admin API
- `auth/sso_routes.py` - OAuth callbacks
- `auth/azure_auth.py` - Token validation
- `core/protocols.py` - Exports User, get_auth_service

---

## 🔍 PHASE 2: DOCUMENT CURRENT WIRING

For each file found in Phase 1, document:

1. What does it import from auth_service?
2. What methods does it call?
3. What does it expect back?

Create a table like:

| File | Imports | Methods Called | Expects |
|------|---------|----------------|---------|
| main.py | get_auth_service, User | get_user_by_email() | User object |
| admin_routes.py | AuthService | grant_department_access() | bool |
| sso_routes.py | authenticate_user | get_or_create_user() | User object |

---

## 🗄️ PHASE 3: NUKE AND RECREATE TABLES

Only after Phases 1-2 are documented, run this SQL:

```sql
-- NUKE OLD SLOP
DROP TABLE IF EXISTS enterprise.access_audit_log CASCADE;
DROP TABLE IF EXISTS enterprise.access_config CASCADE;
DROP TABLE IF EXISTS enterprise.analytics_events CASCADE;
DROP TABLE IF EXISTS enterprise.documents CASCADE;
DROP TABLE IF EXISTS enterprise.query_log CASCADE;
DROP TABLE IF EXISTS enterprise.users CASCADE;
DROP TABLE IF EXISTS enterprise.departments CASCADE;
DROP TABLE IF EXISTS enterprise.tenants CASCADE;

-- CREATE CLEAN TABLES
CREATE TABLE enterprise.tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug varchar(50) UNIQUE NOT NULL,
    name varchar(255) NOT NULL,
    domain varchar(255) NOT NULL
);

CREATE TABLE enterprise.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES enterprise.tenants(id),
    email varchar(255) UNIQUE NOT NULL,
    display_name varchar(255),
    azure_oid varchar(255) UNIQUE,
    department_access varchar[] DEFAULT '{}',
    dept_head_for varchar[] DEFAULT '{}',
    is_super_user boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    last_login_at timestamptz
);

CREATE INDEX idx_users_email ON enterprise.users(email);
CREATE INDEX idx_users_azure_oid ON enterprise.users(azure_oid);
CREATE INDEX idx_users_dept_access ON enterprise.users USING gin(department_access);

-- SEED ADMIN
INSERT INTO enterprise.tenants (slug, name, domain) 
VALUES ('driscoll', 'Driscoll Foods', 'driscollfoods.com');

INSERT INTO enterprise.users (tenant_id, email, display_name, department_access, dept_head_for, is_super_user)
SELECT id, 'mhartigan@driscollfoods.com', 'Matt Hartigan', 
       ARRAY['sales','purchasing','warehouse','credit','accounting','it'],
       ARRAY['sales','purchasing','warehouse','credit','accounting','it'],
       true
FROM enterprise.tenants WHERE slug = 'driscoll';
```

---

## 🔧 PHASE 4: REFACTOR auth_service.py

Rewrite auth_service.py to ONLY use these two tables. Here's the spec:

### User Dataclass
```python
@dataclass
class User:
    id: str
    email: str
    display_name: Optional[str]
    tenant_id: str
    azure_oid: Optional[str]
    department_access: List[str]      # ['sales', 'purchasing']
    dept_head_for: List[str]          # ['sales']
    is_super_user: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    def can_access(self, department: str) -> bool:
        return self.is_super_user or department in self.department_access
    
    def can_grant_access(self, department: str) -> bool:
        return self.is_super_user or department in self.dept_head_for
```

### Required Methods
```python
class AuthService:
    def get_user_by_email(self, email: str) -> Optional[User]
    def get_user_by_azure_oid(self, oid: str) -> Optional[User]
    def get_or_create_user(self, email: str, display_name: str = None) -> User
    def update_last_login(self, user_id: str) -> None
    def grant_department_access(self, granter: User, target_email: str, department: str) -> bool
    def revoke_department_access(self, revoker: User, target_email: str, department: str) -> bool
```

### SQL Queries (THE ONLY QUERIES NEEDED)
```python
# Get user by email
SELECT id, email, display_name, tenant_id, azure_oid, 
       department_access, dept_head_for, is_super_user, 
       created_at, last_login_at
FROM enterprise.users 
WHERE email = %s

# Get user by azure_oid
SELECT id, email, display_name, tenant_id, azure_oid,
       department_access, dept_head_for, is_super_user,
       created_at, last_login_at
FROM enterprise.users 
WHERE azure_oid = %s

# Create user
INSERT INTO enterprise.users (tenant_id, email, display_name, azure_oid)
SELECT id, %s, %s, %s FROM enterprise.tenants WHERE domain = %s
RETURNING *

# Update last login
UPDATE enterprise.users SET last_login_at = now() WHERE id = %s

# Grant department access (array append)
UPDATE enterprise.users 
SET department_access = array_append(department_access, %s)
WHERE email = %s AND NOT (%s = ANY(department_access))

# Revoke department access (array remove)
UPDATE enterprise.users 
SET department_access = array_remove(department_access, %s)
WHERE email = %s
```

---

## 🔧 PHASE 5: FIX DOWNSTREAM

After auth_service.py is refactored, fix every file from Phase 1:

- Update imports if User dataclass changed
- Update method calls if signatures changed
- Remove any references to deleted tables (access_config, etc.)

---

## 📋 DELIVERABLES

1. **DEPENDENCY_AUDIT.md** - Every file that touches auth_service
2. **MIGRATION.sql** - Nuke old, create new (provided above)
3. **auth_service.py** - Refactored to use only 2 tables
4. **Fixes to all dependent files**

---

## ❌ DO NOT

- Do NOT add columns that aren't listed above
- Do NOT create tables that aren't listed above
- Do NOT guess column names from training data
- Do NOT patch - REFACTOR
- Do NOT touch anything until Phase 1 audit is complete

---

## ✅ SUCCESS CRITERIA

1. Only 2 tables exist in enterprise schema: tenants, users
2. auth_service.py uses ONLY those 2 tables
3. All dependent files updated
4. SSO login works
5. Matt can login and sees his name

---

## 📝 CHANGELOG

```markdown
## 2024-12-22 00:00 - Auth Full Refactor 🔄
**Priority:** CRITICAL
**Mission:** Rebuild auth around 2-table schema

**Schema (FINAL):**
- enterprise.tenants: id, slug, name, domain
- enterprise.users: id, tenant_id, email, display_name, azure_oid, 
  department_access[], dept_head_for[], is_super_user, created_at, last_login_at

**Deleted Tables:**
- access_config (replaced by department_access array)
- access_audit_log (not needed for MVP)
- departments (just use string slugs)
- analytics_events (not needed for MVP)
- documents (separate concern - RAG)
- query_log (separate concern - analytics)

**Approach:** Tables first. Code serves tables.
```

---

**THIS IS THE FINAL ARCHITECTURE. NO MORE CHANGES TO SCHEMA.**