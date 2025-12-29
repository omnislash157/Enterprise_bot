# Database Expected Schema Documentation

**Generated:** 2025-12-21
**Purpose:** Complete documentation of all database schema expectations found in backend auth files

---

## Overview

This document catalogs every database table, column, and schema expectation found in the backend authentication codebase. Each expectation is documented with exact file locations and line numbers for production debugging.

---

## Table Expectations

### 1. `users` Table

#### Expected from: `claude_sdk_toolkit/database/auth_schema.py`

**Line 8-23: CREATE TABLE statement**
```sql
CREATE TABLE IF NOT EXISTS users (
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
)
```

**Expected Columns:**
- `id` - INTEGER PRIMARY KEY AUTOINCREMENT
- `email` - TEXT UNIQUE NOT NULL
- `azure_oid` - TEXT UNIQUE (Azure Object ID)
- `display_name` - TEXT
- `first_name` - TEXT
- `last_name` - TEXT
- `created_at` - TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- `updated_at` - TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- `last_login` - TIMESTAMP
- `is_active` - BOOLEAN DEFAULT 1
- `is_admin` - BOOLEAN DEFAULT 0
- `department` - TEXT
- `job_title` - TEXT

#### Column Usage in Queries

**File: `claude_sdk_toolkit/services/auth_service.py`**

**Line 42-50: get_or_create_user() - INSERT query**
```python
cursor.execute("""
    INSERT INTO users (email, azure_oid, display_name, first_name, last_name, last_login)
    VALUES (?, ?, ?, ?, ?, ?)
""", (
    email,
    profile.get('oid'),
    profile.get('name'),
    profile.get('given_name'),
    profile.get('family_name'),
    datetime.now()
))
```
**Columns used:** email, azure_oid, display_name, first_name, last_name, last_login

**Line 58-61: get_or_create_user() - UPDATE query**
```python
cursor.execute("""
    UPDATE users
    SET last_login = ?, display_name = ?, first_name = ?, last_name = ?
    WHERE email = ?
""", (datetime.now(), profile.get('name'), profile.get('given_name'),
      profile.get('family_name'), email))
```
**Columns used:** last_login, display_name, first_name, last_name, email

**Line 69-70: get_or_create_user() - SELECT query**
```python
cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
user = cursor.fetchone()
```
**Columns used:** email (WHERE), all columns (SELECT *)

**Line 78-82: get_user_by_id() - SELECT query**
```python
cursor.execute("""
    SELECT id, email, azure_oid, display_name, first_name, last_name,
           created_at, last_login, is_active, is_admin, department, job_title
    FROM users WHERE id = ?
""", (user_id,))
```
**Columns used:** id, email, azure_oid, display_name, first_name, last_name, created_at, last_login, is_active, is_admin, department, job_title

**Line 93-97: get_user_by_email() - SELECT query**
```python
cursor.execute("""
    SELECT id, email, azure_oid, display_name, first_name, last_name,
           created_at, last_login, is_active, is_admin, department, job_title
    FROM users WHERE email = ?
""", (email,))
```
**Columns used:** Same as get_user_by_id()

**Line 108-112: get_user_by_azure_oid() - SELECT query**
```python
cursor.execute("""
    SELECT id, email, azure_oid, display_name, first_name, last_name,
           created_at, last_login, is_active, is_admin, department, job_title
    FROM users WHERE azure_oid = ?
""", (azure_oid,))
```
**Columns used:** Same as get_user_by_id()

**File: `claude_sdk_toolkit/routes/admin_routes.py`**

**Line 29-33: list_users() - SELECT query**
```python
cursor.execute("""
    SELECT id, email, display_name, is_active, is_admin,
           created_at, last_login, department, job_title
    FROM users ORDER BY created_at DESC
""")
```
**Columns used:** id, email, display_name, is_active, is_admin, created_at, last_login, department, job_title

**Line 53-55: get_user() - SELECT query**
```python
cursor.execute("""
    SELECT * FROM users WHERE id = ?
""", (user_id,))
```
**Columns used:** All columns (SELECT *)

**Line 92-94: update_user() - UPDATE query**
```python
cursor.execute(f"""
    UPDATE users SET {', '.join(update_fields)} WHERE id = ?
""", (*values, user_id))
```
**Columns used:** Dynamic - can update any of: is_active, is_admin, department, job_title, display_name

**Line 122-123: delete_user() - DELETE query**
```python
cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
```
**Columns used:** id

---

### 2. `sessions` Table

#### Expected from: `claude_sdk_toolkit/database/auth_schema.py`

**Line 25-34: CREATE TABLE statement**
```sql
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
```

**Expected Columns:**
- `id` - INTEGER PRIMARY KEY AUTOINCREMENT
- `user_id` - INTEGER NOT NULL
- `session_token` - TEXT UNIQUE NOT NULL
- `created_at` - TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- `expires_at` - TIMESTAMP NOT NULL
- `is_active` - BOOLEAN DEFAULT 1

**Foreign Keys:**
- `user_id` → `users(id)` ON DELETE CASCADE

#### Column Usage in Queries

**File: `claude_sdk_toolkit/services/auth_service.py`**

**Line 130-136: create_session() - INSERT query**
```python
cursor.execute("""
    INSERT INTO sessions (user_id, session_token, expires_at)
    VALUES (?, ?, ?)
""", (
    user_id,
    session_token,
    expires_at
))
```
**Columns used:** user_id, session_token, expires_at

**Line 152-156: validate_session() - SELECT query**
```python
cursor.execute("""
    SELECT s.*, u.email, u.is_active, u.is_admin
    FROM sessions s
    JOIN users u ON s.user_id = u.id
    WHERE s.session_token = ? AND s.is_active = 1
""", (session_token,))
```
**Columns used:**
- sessions: all columns (s.*)
- users: email, is_active, is_admin
- JOIN on: s.user_id = u.id
- WHERE on: s.session_token, s.is_active

**Line 167-168: validate_session() - UPDATE query (expiration check)**
```python
cursor.execute("""
    UPDATE sessions SET is_active = 0 WHERE id = ?
""", (session['id'],))
```
**Columns used:** is_active, id

**Line 184-187: invalidate_session() - UPDATE query**
```python
cursor.execute("""
    UPDATE sessions
    SET is_active = 0
    WHERE session_token = ?
""", (session_token,))
```
**Columns used:** is_active, session_token

**Line 199-203: cleanup_expired_sessions() - UPDATE query**
```python
cursor.execute("""
    UPDATE sessions
    SET is_active = 0
    WHERE expires_at < ? AND is_active = 1
""", (datetime.now(),))
```
**Columns used:** is_active, expires_at

---

### 3. `audit_logs` Table

#### Expected from: `claude_sdk_toolkit/database/auth_schema.py`

**Line 36-48: CREATE TABLE statement**
```sql
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id INTEGER,
    details TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
)
```

**Expected Columns:**
- `id` - INTEGER PRIMARY KEY AUTOINCREMENT
- `user_id` - INTEGER (nullable)
- `action` - TEXT NOT NULL
- `resource_type` - TEXT
- `resource_id` - INTEGER
- `details` - TEXT
- `ip_address` - TEXT
- `user_agent` - TEXT
- `created_at` - TIMESTAMP DEFAULT CURRENT_TIMESTAMP

**Foreign Keys:**
- `user_id` → `users(id)` ON DELETE SET NULL

#### Column Usage in Queries

**File: `claude_sdk_toolkit/services/auth_service.py`**

**Line 214-225: log_audit_event() - INSERT query**
```python
cursor.execute("""
    INSERT INTO audit_logs
    (user_id, action, resource_type, resource_id, details, ip_address, user_agent)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (
    user_id,
    action,
    resource_type,
    resource_id,
    json.dumps(details) if details else None,
    ip_address,
    user_agent
))
```
**Columns used:** user_id, action, resource_type, resource_id, details, ip_address, user_agent

**File: `claude_sdk_toolkit/routes/admin_routes.py`**

**Line 147-152: get_audit_logs() - SELECT query**
```python
cursor.execute("""
    SELECT a.*, u.email as user_email, u.display_name
    FROM audit_logs a
    LEFT JOIN users u ON a.user_id = u.id
    ORDER BY a.created_at DESC LIMIT ? OFFSET ?
""", (limit, offset))
```
**Columns used:**
- audit_logs: all columns (a.*)
- users: email (as user_email), display_name
- LEFT JOIN on: a.user_id = u.id
- ORDER BY: a.created_at

**Line 178-183: get_user_audit_logs() - SELECT query**
```python
cursor.execute("""
    SELECT a.*, u.email as user_email, u.display_name
    FROM audit_logs a
    LEFT JOIN users u ON a.user_id = u.id
    WHERE a.user_id = ?
    ORDER BY a.created_at DESC
""", (user_id,))
```
**Columns used:** Same as get_audit_logs() but with WHERE a.user_id filter

---

## Index Expectations

### From: `claude_sdk_toolkit/database/auth_schema.py`

**Line 50-52: Session token index**
```sql
CREATE INDEX IF NOT EXISTS idx_sessions_token
ON sessions(session_token)
```

**Line 54-56: Session user_id index**
```sql
CREATE INDEX IF NOT EXISTS idx_sessions_user_id
ON sessions(user_id)
```

**Line 58-60: Audit logs user_id index**
```sql
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id
ON audit_logs(user_id)
```

**Line 62-64: Audit logs created_at index**
```sql
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at
ON audit_logs(created_at)
```

---

## Schema Initialization

### From: `claude_sdk_toolkit/database/auth_schema.py`

**Line 67-79: init_auth_schema() function**
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

**Database file expected:** `enterprise_bot.db` (line 70)

---

## Critical Schema Dependencies

### Foreign Key Relationships

1. **sessions.user_id → users.id**
   - Type: CASCADE on DELETE
   - Location: auth_schema.py:31
   - Impact: Deleting a user automatically deletes all their sessions

2. **audit_logs.user_id → users.id**
   - Type: SET NULL on DELETE
   - Location: auth_schema.py:46
   - Impact: Deleting a user sets audit log user_id to NULL (preserves audit trail)

### Unique Constraints

1. **users.email** - Must be unique (auth_schema.py:10)
2. **users.azure_oid** - Must be unique (auth_schema.py:11)
3. **sessions.session_token** - Must be unique (auth_schema.py:27)

---

## Schema Expectations Summary

**Total Tables:** 3
- users
- sessions
- audit_logs

**Total Columns:** 36 across all tables

**Total Indexes:** 4
- idx_sessions_token
- idx_sessions_user_id
- idx_audit_logs_user_id
- idx_audit_logs_created_at

**Total Foreign Keys:** 2
- sessions → users
- audit_logs → users

---

## Query Patterns by Operation Type

### INSERT Operations
1. **users table:** auth_service.py:42-50 (user creation)
2. **sessions table:** auth_service.py:130-136 (session creation)
3. **audit_logs table:** auth_service.py:214-225 (audit logging)

### SELECT Operations
1. **users table:**
   - By email: auth_service.py:69-70, 93-97
   - By id: auth_service.py:78-82
   - By azure_oid: auth_service.py:108-112
   - List all: admin_routes.py:29-33
   - Get one: admin_routes.py:53-55

2. **sessions table:**
   - Validate with JOIN: auth_service.py:152-156

3. **audit_logs table:**
   - List with JOIN: admin_routes.py:147-152
   - By user with JOIN: admin_routes.py:178-183

### UPDATE Operations
1. **users table:**
   - Last login: auth_service.py:58-61
   - Admin updates: admin_routes.py:92-94

2. **sessions table:**
   - Deactivate expired: auth_service.py:167-168
   - Invalidate: auth_service.py:184-187
   - Cleanup: auth_service.py:199-203

### DELETE Operations
1. **users table:** admin_routes.py:122-123 (hard delete)

---

## Notes for Production Debugging

1. **Schema Version:** No version tracking found in code
2. **Migration System:** No migration system detected
3. **Schema Validation:** No runtime schema validation found
4. **Database File:** Hardcoded to 'enterprise_bot.db'
5. **Transaction Management:** Individual transactions per operation (no distributed transactions)
6. **Connection Pooling:** Not implemented (new connection per operation)

---

**End of Database Expected Schema Documentation**
