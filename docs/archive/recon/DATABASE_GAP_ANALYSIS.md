# Database Gap Analysis

**Generated:** 2025-12-21
**Purpose:** Detailed comparison between expected schema and actual database state

---

## Executive Summary

This analysis compares the expected database schema (documented in `DATABASE_EXPECTED_SCHEMA.md`) against the actual database state discovered during authentication debugging. Critical gaps have been identified that prevent the authentication system from functioning.

---

## Actual Database State

### Discovered Tables

From database inspection and error analysis:

1. **users table** - EXISTS
2. **sessions table** - Status unknown (likely exists based on schema init)
3. **audit_logs table** - Status unknown (likely exists based on schema init)

---

## Critical Schema Mismatches

### 1. CRITICAL: Column Name Mismatch - `azure_oid` vs `oid`

**Severity:** BLOCKER - Prevents Azure SSO authentication

#### Expected Schema
```sql
-- auth_schema.py:11
azure_oid TEXT UNIQUE
```

#### Actual Schema
```sql
-- Actual database has:
oid TEXT UNIQUE
```

#### Impact Analysis

**File: `claude_sdk_toolkit/services/auth_service.py`**

**Line 42-50: INSERT fails**
```python
cursor.execute("""
    INSERT INTO users (email, azure_oid, display_name, first_name, last_name, last_login)
    VALUES (?, ?, ?, ?, ?, ?)
""", (
    email,
    profile.get('oid'),  # Value is correct
    profile.get('name'),
    profile.get('given_name'),
    profile.get('family_name'),
    datetime.now()
))
```
**Error:** Column `azure_oid` does not exist (actual column is `oid`)

**Line 78-82: SELECT fails**
```python
cursor.execute("""
    SELECT id, email, azure_oid, display_name, first_name, last_name,
           created_at, last_login, is_active, is_admin, department, job_title
    FROM users WHERE id = ?
""", (user_id,))
```
**Error:** Column `azure_oid` does not exist

**Line 93-97: SELECT fails**
```python
cursor.execute("""
    SELECT id, email, azure_oid, display_name, first_name, last_name,
           created_at, last_login, is_active, is_admin, department, job_title
    FROM users WHERE email = ?
""", (email,))
```
**Error:** Column `azure_oid` does not exist

**Line 108-112: SELECT fails**
```python
cursor.execute("""
    SELECT id, email, azure_oid, display_name, first_name, last_name,
           created_at, last_login, is_active, is_admin, department, job_title
    FROM users WHERE azure_oid = ?
""", (azure_oid,))
```
**Error:** Column `azure_oid` does not exist in WHERE clause

#### Affected Operations
- User creation during SSO callback: BLOCKED
- User lookup by ID: BROKEN
- User lookup by email: BROKEN
- User lookup by Azure OID: BROKEN
- All admin user management: BROKEN

#### Root Cause
Schema file (`auth_schema.py`) defines column as `azure_oid`, but database was created with column named `oid`. Either:
1. Database was created from different schema version
2. Manual database creation used shortened name
3. Migration was performed that renamed column incorrectly

---

## Missing Tables Analysis

### Expected but Not Verified

The following tables are expected by the schema but have not been verified to exist in the actual database:

#### 1. sessions table
**Defined in:** auth_schema.py:25-34
**Status:** UNVERIFIED
**Risk:** HIGH - Authentication will fail if missing
**Queries that will fail:**
- auth_service.py:130-136 (create_session)
- auth_service.py:152-156 (validate_session)
- auth_service.py:184-187 (invalidate_session)
- auth_service.py:199-203 (cleanup_expired_sessions)

#### 2. audit_logs table
**Defined in:** auth_schema.py:36-48
**Status:** UNVERIFIED
**Risk:** MEDIUM - Audit trail will fail but auth might work
**Queries that will fail:**
- auth_service.py:214-225 (log_audit_event)
- admin_routes.py:147-152 (get_audit_logs)
- admin_routes.py:178-183 (get_user_audit_logs)

---

## Missing Columns Analysis

### users Table

#### Columns That May Be Missing

Based on the `azure_oid`/`oid` mismatch, the actual database schema is inconsistent with expectations. The following columns need verification:

| Column Name | Expected Type | Defined In | Status | Queries Affected |
|-------------|---------------|------------|--------|------------------|
| id | INTEGER PK | auth_schema.py:9 | ASSUMED OK | All user queries |
| email | TEXT UNIQUE | auth_schema.py:10 | ASSUMED OK | All user queries |
| azure_oid | TEXT UNIQUE | auth_schema.py:11 | MISSING (is 'oid') | All user queries |
| display_name | TEXT | auth_schema.py:12 | UNKNOWN | Insert/Update/Select queries |
| first_name | TEXT | auth_schema.py:13 | UNKNOWN | Insert/Update queries |
| last_name | TEXT | auth_schema.py:14 | UNKNOWN | Insert/Update queries |
| created_at | TIMESTAMP | auth_schema.py:15 | UNKNOWN | List users, admin queries |
| updated_at | TIMESTAMP | auth_schema.py:16 | UNKNOWN | Not actively used |
| last_login | TIMESTAMP | auth_schema.py:17 | UNKNOWN | Insert/Update queries |
| is_active | BOOLEAN | auth_schema.py:18 | UNKNOWN | Admin routes, session validation |
| is_admin | BOOLEAN | auth_schema.py:19 | UNKNOWN | Session validation, admin checks |
| department | TEXT | auth_schema.py:20 | UNKNOWN | Admin routes |
| job_title | TEXT | auth_schema.py:21 | UNKNOWN | Admin routes |

**Recommendation:** Run `PRAGMA table_info(users);` to get actual schema

---

## Missing Indexes Analysis

### Expected Indexes

| Index Name | Table | Column(s) | Defined In | Status | Impact if Missing |
|------------|-------|-----------|------------|--------|-------------------|
| idx_sessions_token | sessions | session_token | auth_schema.py:50 | UNVERIFIED | Slow session validation |
| idx_sessions_user_id | sessions | user_id | auth_schema.py:54 | UNVERIFIED | Slow user session lookups |
| idx_audit_logs_user_id | audit_logs | user_id | auth_schema.py:58 | UNVERIFIED | Slow audit queries by user |
| idx_audit_logs_created_at | audit_logs | created_at | auth_schema.py:62 | UNVERIFIED | Slow chronological audit queries |

**Performance Impact:** If missing, queries will still work but will be slower. Not a blocker for functionality.

---

## Foreign Key Constraints Analysis

### Expected Foreign Keys

| FK Name | From Table | From Column | To Table | To Column | On Delete | Defined In | Status |
|---------|------------|-------------|----------|-----------|-----------|------------|--------|
| (unnamed) | sessions | user_id | users | id | CASCADE | auth_schema.py:31 | UNVERIFIED |
| (unnamed) | audit_logs | user_id | users | id | SET NULL | auth_schema.py:46 | UNVERIFIED |

**Risk Analysis:**
- If foreign keys are missing, referential integrity is not enforced
- Deleting a user won't automatically delete their sessions (security risk)
- Orphaned records may accumulate

**Note:** SQLite foreign keys must be explicitly enabled with `PRAGMA foreign_keys = ON;` - not found in codebase

---

## Schema Validation Gaps

### No Runtime Validation

**Finding:** No code found that validates database schema matches expectations

**Impact:**
- Schema drift can occur silently
- Deployment to new environment may fail mysteriously
- No warning if schema is outdated

**Missing Capabilities:**
1. Schema version tracking
2. Automatic schema validation on startup
3. Migration system
4. Schema compatibility checks

---

## Database Initialization Analysis

### Schema Init Function

**File:** auth_schema.py:67-79

```python
def init_auth_schema():
    """Initialize authentication schema"""
    conn = sqlite3.connect('enterprise_bot.db')
    cursor = conn.cursor()

    # Execute all schema statements
    cursor.executescript(AUTH_SCHEMA)

    conn.commit()
    conn.close()

    print("Auth schema initialized successfully")
```

### Problems Identified

1. **Hardcoded Database Name:** 'enterprise_bot.db'
2. **No Error Handling:** Will silently fail on errors
3. **No Idempotency Check:** Uses `IF NOT EXISTS` but doesn't verify column schemas
4. **No Return Value:** Can't check if init succeeded
5. **No Foreign Key Enable:** Doesn't enable foreign key constraints

### When is init_auth_schema() Called?

**Search Required:** Need to find where this function is invoked
- Not found in main.py import analysis
- May be called manually or in separate initialization script
- **GAP:** May never be called automatically

---

## Comparison Table: Expected vs Actual

### users Table Detailed Comparison

| Column | Expected Type | Expected Constraints | Actual Type | Actual Constraints | Status | Priority |
|--------|---------------|---------------------|-------------|-------------------|--------|----------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | UNKNOWN | UNKNOWN | UNVERIFIED | P0 |
| email | TEXT | UNIQUE NOT NULL | UNKNOWN | UNKNOWN | UNVERIFIED | P0 |
| azure_oid | TEXT | UNIQUE | N/A | N/A | MISSING | P0 |
| oid | N/A | N/A | TEXT | UNIQUE (presumed) | EXTRA COLUMN | P0 |
| display_name | TEXT | nullable | UNKNOWN | UNKNOWN | UNVERIFIED | P1 |
| first_name | TEXT | nullable | UNKNOWN | UNKNOWN | UNVERIFIED | P1 |
| last_name | TEXT | nullable | UNKNOWN | UNKNOWN | UNVERIFIED | P1 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | UNKNOWN | UNKNOWN | UNVERIFIED | P1 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | UNKNOWN | UNKNOWN | UNVERIFIED | P2 |
| last_login | TIMESTAMP | nullable | UNKNOWN | UNKNOWN | UNVERIFIED | P1 |
| is_active | BOOLEAN | DEFAULT 1 | UNKNOWN | UNKNOWN | UNVERIFIED | P0 |
| is_admin | BOOLEAN | DEFAULT 0 | UNKNOWN | UNKNOWN | UNVERIFIED | P0 |
| department | TEXT | nullable | UNKNOWN | UNKNOWN | UNVERIFIED | P2 |
| job_title | TEXT | nullable | UNKNOWN | UNKNOWN | UNVERIFIED | P2 |

**Legend:**
- P0: Blocking - System won't work without this
- P1: High - Core functionality affected
- P2: Medium - Nice-to-have features affected

---

## Resolution Strategies

### Strategy 1: Fix Backend Code (Recommended)

Change all `azure_oid` references to `oid` in backend code.

**Files to modify:**
1. auth_schema.py:11 - Schema definition
2. auth_service.py:42-50 - INSERT query
3. auth_service.py:78-82 - SELECT by id
4. auth_service.py:93-97 - SELECT by email
5. auth_service.py:108-112 - SELECT by azure_oid

**Pros:**
- No data loss
- No database downtime
- Simpler migration

**Cons:**
- Code is less descriptive ('oid' is ambiguous)
- Requires code changes in multiple places

### Strategy 2: Fix Database Schema

Rename `oid` column to `azure_oid` in database.

**SQL Migration:**
```sql
-- SQLite doesn't support RENAME COLUMN directly (older versions)
-- Need to recreate table

-- 1. Create new table with correct schema
CREATE TABLE users_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    azure_oid TEXT UNIQUE,
    display_name TEXT,
    first_name TEXT,
    last_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    is_admin BOOLEAN DEFAULT 0,
    department TEXT,
    job_title TEXT
);

-- 2. Copy data
INSERT INTO users_new
SELECT id, email, oid as azure_oid, display_name, first_name, last_name,
       created_at, updated_at, last_login, is_active, is_admin, department, job_title
FROM users;

-- 3. Drop old table
DROP TABLE users;

-- 4. Rename new table
ALTER TABLE users_new RENAME TO users;

-- 5. Recreate indexes and foreign keys
-- (recreate all dependent objects)
```

**Pros:**
- Code becomes more descriptive
- Matches intended design

**Cons:**
- Requires database downtime
- Risk of data loss if migration fails
- Must recreate all foreign keys and indexes
- More complex deployment

### Strategy 3: Add Compatibility Layer

Create database views or add both columns.

**Not Recommended:** Adds complexity without solving root cause

---

## Action Items for Production

### Immediate (P0)
1. [ ] Run `PRAGMA table_info(users);` to get actual schema
2. [ ] Run `PRAGMA table_info(sessions);` to verify sessions table
3. [ ] Run `PRAGMA table_info(audit_logs);` to verify audit_logs table
4. [ ] Decide on Strategy 1 vs Strategy 2 for azure_oid/oid mismatch
5. [ ] Enable foreign key constraints: `PRAGMA foreign_keys = ON;`

### Short Term (P1)
1. [ ] Add schema version tracking to database
2. [ ] Add schema validation on application startup
3. [ ] Create database initialization script that's actually called
4. [ ] Add error handling to init_auth_schema()
5. [ ] Document database setup procedure

### Long Term (P2)
1. [ ] Implement proper migration system (Alembic or similar)
2. [ ] Add integration tests that verify schema expectations
3. [ ] Create database backup/restore procedures
4. [ ] Add monitoring for schema drift
5. [ ] Document all manual database operations

---

## Testing Recommendations

### Schema Verification Script

```python
import sqlite3

def verify_schema():
    """Verify actual database schema matches expectations"""
    conn = sqlite3.connect('enterprise_bot.db')
    cursor = conn.cursor()

    # Check users table columns
    cursor.execute("PRAGMA table_info(users);")
    users_columns = {row[1]: row[2] for row in cursor.fetchall()}

    print("users table columns:", users_columns)

    # Check for azure_oid vs oid
    if 'azure_oid' in users_columns:
        print("✓ azure_oid column exists")
    elif 'oid' in users_columns:
        print("✗ MISMATCH: Found 'oid' instead of 'azure_oid'")
    else:
        print("✗ ERROR: Neither azure_oid nor oid found")

    # Check foreign keys
    cursor.execute("PRAGMA foreign_key_list(sessions);")
    fks = cursor.fetchall()
    print("sessions foreign keys:", fks)

    # Check indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='sessions';")
    indexes = cursor.fetchall()
    print("sessions indexes:", indexes)

    conn.close()

if __name__ == '__main__':
    verify_schema()
```

---

## Summary of Critical Gaps

| Gap | Severity | Impact | Files Affected | Resolution Priority |
|-----|----------|--------|----------------|---------------------|
| azure_oid vs oid mismatch | BLOCKER | All auth operations fail | auth_service.py (5 locations), auth_schema.py | P0 - IMMEDIATE |
| sessions table unverified | HIGH | Session management may fail | auth_service.py (4 functions) | P0 - IMMEDIATE |
| audit_logs table unverified | MEDIUM | Audit trail may fail | admin_routes.py, auth_service.py | P1 - SOON |
| No foreign key enforcement | MEDIUM | Data integrity risks | All tables with FKs | P1 - SOON |
| No schema validation | MEDIUM | Silent failures possible | All database operations | P1 - SOON |
| Missing indexes | LOW | Performance degradation | sessions, audit_logs queries | P2 - LATER |
| No migration system | LOW | Manual schema management | All future schema changes | P2 - LATER |

---

**End of Database Gap Analysis**
