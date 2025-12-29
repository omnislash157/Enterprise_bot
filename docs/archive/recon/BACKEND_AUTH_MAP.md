# Backend Authentication Flow Map

**Generated:** 2025-12-21
**Purpose:** Complete documentation of backend authentication routes, services, and flows

---

## Overview

This document maps the entire backend authentication system including:
- All HTTP routes and their handlers
- Authentication service methods and database queries
- Azure SSO integration flow
- Environment variables and configuration
- Error handling and security measures

---

## Table of Contents

1. [SSO Routes (Public Endpoints)](#sso-routes-public-endpoints)
2. [Admin Routes (Protected Endpoints)](#admin-routes-protected-endpoints)
3. [Authentication Service Layer](#authentication-service-layer)
4. [Azure SSO Flow](#azure-sso-flow)
5. [Environment Variables](#environment-variables)
6. [Security Mechanisms](#security-mechanisms)

---

## SSO Routes (Public Endpoints)

**File:** `claude_sdk_toolkit/routes/sso_routes.py`

### Route 1: GET /api/auth/login

**Line:** 18-32

**Purpose:** Initiates Azure SSO login flow

**Handler Function:** `login()`

**Request:**
```
GET /api/auth/login
No parameters required
```

**Response:**
```python
# Success (302 Redirect)
{
    "Location": "<Azure authorization URL>"
}

# Includes state parameter for CSRF protection
```

**Implementation:**
```python
@router.get("/login")
async def login():
    """Initiate Azure AD login"""
    try:
        # Get Azure AD OAuth2 flow
        flow = get_authorization_flow()

        # Get authorization URL
        auth_url = flow.get_authorization_request_url(
            scopes=["User.Read"],
            state=None,  # TODO: Add CSRF state
            redirect_uri=os.getenv('AZURE_REDIRECT_URI')
        )

        return {"auth_url": auth_url}

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Security Notes:**
- Line 28: TODO comment indicates CSRF state not implemented
- Uses AZURE_REDIRECT_URI environment variable
- Requests "User.Read" scope from Microsoft Graph

**Dependencies:**
- `get_authorization_flow()` (imported from auth_service)
- Environment: AZURE_REDIRECT_URI

---

### Route 2: GET /api/auth/callback

**Line:** 35-76

**Purpose:** Handles Azure SSO callback after user authentication

**Handler Function:** `callback(request: Request)`

**Request:**
```
GET /api/auth/callback?code=<auth_code>&state=<state>

Query Parameters:
- code: Authorization code from Azure (required)
- state: CSRF protection state (currently unused)
```

**Response:**
```python
# Success (302 Redirect)
{
    "Location": "/"  # Frontend root
}
# Sets cookie: session_token=<token>; HttpOnly; Secure; SameSite=Lax

# Error (400/500)
{
    "detail": "No authorization code received" | "<error message>"
}
```

**Implementation Flow:**

1. **Extract authorization code** (line 39-42)
```python
code = request.query_params.get('code')
if not code:
    raise HTTPException(status_code=400, detail="No authorization code received")
```

2. **Exchange code for token** (line 46-47)
```python
flow = get_authorization_flow()
token_response = flow.fetch_token(authorization_response=str(request.url))
```

3. **Get user profile from Microsoft Graph** (line 50-56)
```python
graph_client = msal.ConfidentialClientApplication(
    client_id=os.getenv('AZURE_CLIENT_ID'),
    client_credential=os.getenv('AZURE_CLIENT_SECRET'),
    authority=f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID')}"
)

result = graph_client.acquire_token_silent(["User.Read"], account=None)
if not result:
    result = graph_client.acquire_token_for_client(scopes=["User.Read"])
```

4. **Fetch user info from Graph API** (line 58-60)
```python
graph_data = requests.get(
    'https://graph.microsoft.com/v1.0/me',
    headers={'Authorization': f"Bearer {result['access_token']}"}
).json()
```

5. **Create or update user in database** (line 63)
```python
user = auth_service.get_or_create_user(graph_data)
```

6. **Create session** (line 66)
```python
session_token = auth_service.create_session(user['id'])
```

7. **Set secure cookie and redirect** (line 69-70)
```python
response = RedirectResponse(url="/", status_code=302)
response.set_cookie(
    key="session_token",
    value=session_token,
    httponly=True,
    secure=True,
    samesite="lax"
)
```

**Error Handling:**
```python
except Exception as e:
    logger.error(f"Callback error: {str(e)}")
    raise HTTPException(status_code=500, detail=str(e))
```

**Dependencies:**
- `get_authorization_flow()` (auth_service)
- `get_or_create_user()` (auth_service)
- `create_session()` (auth_service)
- Environment: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
- External: Microsoft Graph API

**Security Features:**
- HttpOnly cookie (prevents XSS)
- Secure flag (HTTPS only)
- SameSite=Lax (CSRF protection)

**Security Gaps:**
- State parameter not validated (line 28 in login)
- Token stored in cookie without encryption
- No token expiration validation before use

---

### Route 3: POST /api/auth/logout

**Line:** 79-96

**Purpose:** Logs out user by invalidating session

**Handler Function:** `logout(request: Request)`

**Request:**
```
POST /api/auth/logout
Cookie: session_token=<token>
```

**Response:**
```python
# Success (200)
{
    "message": "Logged out successfully"
}

# Also clears session_token cookie
```

**Implementation:**
```python
@router.post("/logout")
async def logout(request: Request):
    """Logout user"""
    try:
        # Get session token from cookie
        session_token = request.cookies.get('session_token')

        if session_token:
            # Invalidate session
            auth_service.invalidate_session(session_token)

        # Clear cookie
        response = JSONResponse({"message": "Logged out successfully"})
        response.delete_cookie(key="session_token")

        return response

    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Dependencies:**
- `invalidate_session()` (auth_service)

**Behavior Notes:**
- Always returns success even if no session token present
- Clears cookie even if session invalidation fails
- Graceful handling of missing session

---

### Route 4: GET /api/auth/me

**Line:** 99-117

**Purpose:** Get current authenticated user info

**Handler Function:** `get_current_user(request: Request)`

**Request:**
```
GET /api/auth/me
Cookie: session_token=<token>
```

**Response:**
```python
# Success (200)
{
    "id": 1,
    "email": "user@example.com",
    "display_name": "John Doe",
    "is_admin": false
}

# Unauthorized (401)
{
    "detail": "Not authenticated"
}
```

**Implementation:**
```python
@router.get("/me")
async def get_current_user(request: Request):
    """Get current user info"""
    try:
        session_token = request.cookies.get('session_token')

        if not session_token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Validate session
        session = auth_service.validate_session(session_token)

        if not session:
            raise HTTPException(status_code=401, detail="Invalid session")

        # Return user info
        return {
            "id": session['user_id'],
            "email": session.get('email'),
            "display_name": session.get('display_name'),
            "is_admin": session.get('is_admin', False)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get current user error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Dependencies:**
- `validate_session()` (auth_service)

**Security:**
- Requires valid session token
- Returns 401 for missing/invalid sessions
- Limited user info exposure (no sensitive data)

---

## Admin Routes (Protected Endpoints)

**File:** `claude_sdk_toolkit/routes/admin_routes.py`

**Global Dependency:** All routes require admin authentication via `verify_admin_access()` dependency

### Authentication Dependency

**Line:** 200-213

```python
async def verify_admin_access(request: Request):
    """Verify admin access for protected routes"""
    session_token = request.cookies.get('session_token')

    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = auth_service.validate_session(session_token)

    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    if not session.get('is_admin'):
        raise HTTPException(status_code=403, detail="Admin access required")

    return session
```

**Usage:** Applied to all admin routes via `dependencies=[Depends(verify_admin_access)]`

---

### Route 1: GET /api/admin/users

**Line:** 23-43

**Purpose:** List all users (admin only)

**Handler Function:** `list_users()`

**Request:**
```
GET /api/admin/users
Cookie: session_token=<admin_token>
```

**Response:**
```python
# Success (200)
{
    "users": [
        {
            "id": 1,
            "email": "user@example.com",
            "display_name": "John Doe",
            "is_active": true,
            "is_admin": false,
            "created_at": "2025-01-15T10:30:00",
            "last_login": "2025-01-20T14:22:00",
            "department": "Engineering",
            "job_title": "Developer"
        },
        // ... more users
    ]
}
```

**Implementation:**
```python
@router.get("/users")
async def list_users():
    """List all users (admin only)"""
    try:
        conn = sqlite3.connect('enterprise_bot.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, email, display_name, is_active, is_admin,
                   created_at, last_login, department, job_title
            FROM users ORDER BY created_at DESC
        """)

        users = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {"users": users}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Database Query:**
- Table: users
- Columns: id, email, display_name, is_active, is_admin, created_at, last_login, department, job_title
- Order: created_at DESC (newest first)

**Security:**
- Requires admin access (via verify_admin_access dependency)
- Returns all user data including sensitive fields

---

### Route 2: GET /api/admin/users/{user_id}

**Line:** 46-66

**Purpose:** Get specific user details (admin only)

**Handler Function:** `get_user(user_id: int)`

**Request:**
```
GET /api/admin/users/123
Cookie: session_token=<admin_token>
```

**Response:**
```python
# Success (200)
{
    "id": 123,
    "email": "user@example.com",
    "azure_oid": "abc-123-def-456",
    "display_name": "John Doe",
    "first_name": "John",
    "last_name": "Doe",
    "created_at": "2025-01-15T10:30:00",
    "updated_at": "2025-01-15T10:30:00",
    "last_login": "2025-01-20T14:22:00",
    "is_active": true,
    "is_admin": false,
    "department": "Engineering",
    "job_title": "Developer"
}

# Not Found (404)
{
    "detail": "User not found"
}
```

**Implementation:**
```python
@router.get("/users/{user_id}")
async def get_user(user_id: int):
    """Get user details (admin only)"""
    try:
        conn = sqlite3.connect('enterprise_bot.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM users WHERE id = ?
        """, (user_id,))

        user = cursor.fetchone()
        conn.close()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return dict(user)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Database Query:**
- Table: users
- Columns: All (SELECT *)
- Filter: id = user_id

---

### Route 3: PUT /api/admin/users/{user_id}

**Line:** 69-108

**Purpose:** Update user details (admin only)

**Handler Function:** `update_user(user_id: int, user_update: UserUpdate)`

**Request:**
```
PUT /api/admin/users/123
Cookie: session_token=<admin_token>
Content-Type: application/json

{
    "is_active": true,
    "is_admin": false,
    "department": "Engineering",
    "job_title": "Senior Developer",
    "display_name": "John A. Doe"
}
```

**Request Model (Line 11-16):**
```python
class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    display_name: Optional[str] = None
```

**Response:**
```python
# Success (200)
{
    "message": "User updated successfully"
}

# Not Found (404)
{
    "detail": "User not found"
}

# Bad Request (400)
{
    "detail": "No fields to update"
}
```

**Implementation:**
```python
@router.put("/users/{user_id}")
async def update_user(user_id: int, user_update: UserUpdate):
    """Update user (admin only)"""
    try:
        update_data = user_update.model_dump(exclude_unset=True)

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        conn = sqlite3.connect('enterprise_bot.db')
        cursor = conn.cursor()

        # Build dynamic UPDATE query
        update_fields = [f"{k} = ?" for k in update_data.keys()]
        values = list(update_data.values())

        cursor.execute(f"""
            UPDATE users SET {', '.join(update_fields)} WHERE id = ?
        """, (*values, user_id))

        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="User not found")

        conn.commit()
        conn.close()

        return {"message": "User updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Database Query:**
- Table: users
- Operation: UPDATE (dynamic fields)
- Allowed fields: is_active, is_admin, department, job_title, display_name
- Filter: id = user_id

**Security:**
- Cannot update email or azure_oid (prevents identity changes)
- Cannot update created_at or id (immutable fields)
- Validates user exists before updating

---

### Route 4: DELETE /api/admin/users/{user_id}

**Line:** 111-133

**Purpose:** Delete user (admin only)

**Handler Function:** `delete_user(user_id: int)`

**Request:**
```
DELETE /api/admin/users/123
Cookie: session_token=<admin_token>
```

**Response:**
```python
# Success (200)
{
    "message": "User deleted successfully"
}

# Not Found (404)
{
    "detail": "User not found"
}
```

**Implementation:**
```python
@router.delete("/users/{user_id}")
async def delete_user(user_id: int):
    """Delete user (admin only)"""
    try:
        conn = sqlite3.connect('enterprise_bot.db')
        cursor = conn.cursor()

        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="User not found")

        conn.commit()
        conn.close()

        return {"message": "User deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Database Query:**
- Table: users
- Operation: DELETE
- Filter: id = user_id

**Cascade Effects:**
- If foreign keys enabled: Automatically deletes user's sessions (CASCADE)
- If foreign keys enabled: Sets audit_logs.user_id to NULL (SET NULL)
- If foreign keys disabled: Orphaned records remain

---

### Route 5: GET /api/admin/audit-logs

**Line:** 136-165

**Purpose:** Get audit logs with pagination (admin only)

**Handler Function:** `get_audit_logs(limit: int = 100, offset: int = 0)`

**Request:**
```
GET /api/admin/audit-logs?limit=50&offset=0
Cookie: session_token=<admin_token>
```

**Response:**
```python
# Success (200)
{
    "logs": [
        {
            "id": 1,
            "user_id": 123,
            "action": "user_login",
            "resource_type": "session",
            "resource_id": 456,
            "details": "{\"ip\": \"192.168.1.1\"}",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0...",
            "created_at": "2025-01-20T14:22:00",
            "user_email": "user@example.com",
            "display_name": "John Doe"
        },
        // ... more logs
    ],
    "total": 1500,
    "limit": 50,
    "offset": 0
}
```

**Implementation:**
```python
@router.get("/audit-logs")
async def get_audit_logs(limit: int = 100, offset: int = 0):
    """Get audit logs (admin only)"""
    try:
        conn = sqlite3.connect('enterprise_bot.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.*, u.email as user_email, u.display_name
            FROM audit_logs a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.created_at DESC LIMIT ? OFFSET ?
        """, (limit, offset))

        logs = [dict(row) for row in cursor.fetchall()]

        # Get total count
        cursor.execute("SELECT COUNT(*) FROM audit_logs")
        total = cursor.fetchone()[0]

        conn.close()

        return {
            "logs": logs,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Database Query:**
- Tables: audit_logs (LEFT JOIN users)
- Columns: All from audit_logs + email, display_name from users
- Order: created_at DESC
- Pagination: LIMIT/OFFSET

---

### Route 6: GET /api/admin/users/{user_id}/audit-logs

**Line:** 168-194

**Purpose:** Get audit logs for specific user (admin only)

**Handler Function:** `get_user_audit_logs(user_id: int)`

**Request:**
```
GET /api/admin/users/123/audit-logs
Cookie: session_token=<admin_token>
```

**Response:**
```python
# Success (200)
{
    "logs": [
        {
            "id": 1,
            "user_id": 123,
            "action": "user_login",
            "resource_type": "session",
            "resource_id": 456,
            "details": "{\"ip\": \"192.168.1.1\"}",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0...",
            "created_at": "2025-01-20T14:22:00",
            "user_email": "user@example.com",
            "display_name": "John Doe"
        },
        // ... more logs for this user
    ]
}
```

**Implementation:**
```python
@router.get("/users/{user_id}/audit-logs")
async def get_user_audit_logs(user_id: int):
    """Get audit logs for specific user (admin only)"""
    try:
        conn = sqlite3.connect('enterprise_bot.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.*, u.email as user_email, u.display_name
            FROM audit_logs a
            LEFT JOIN users u ON a.user_id = u.id
            WHERE a.user_id = ?
            ORDER BY a.created_at DESC
        """, (user_id,))

        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {"logs": logs}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Database Query:**
- Tables: audit_logs (LEFT JOIN users)
- Columns: All from audit_logs + email, display_name from users
- Filter: user_id = user_id
- Order: created_at DESC
- No pagination (returns all logs for user)

---

## Authentication Service Layer

**File:** `claude_sdk_toolkit/services/auth_service.py`

### Function 1: get_authorization_flow()

**Line:** 13-24

**Purpose:** Create MSAL OAuth2 flow for Azure AD

**Signature:**
```python
def get_authorization_flow() -> OAuth2Session
```

**Returns:** OAuth2Session configured for Azure AD

**Implementation:**
```python
def get_authorization_flow():
    """Get Azure AD OAuth2 flow"""
    return OAuth2Session(
        client_id=os.getenv('AZURE_CLIENT_ID'),
        client_secret=os.getenv('AZURE_CLIENT_SECRET'),
        authorization_endpoint=f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID')}/oauth2/v2.0/authorize",
        token_endpoint=f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID')}/oauth2/v2.0/token",
        redirect_uri=os.getenv('AZURE_REDIRECT_URI'),
        scope=["User.Read"]
    )
```

**Dependencies:**
- Environment: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, AZURE_REDIRECT_URI
- External: MSAL library

**Azure Endpoints Used:**
- Authorization: `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize`
- Token: `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token`

**Scope:** User.Read (Microsoft Graph permission)

---

### Function 2: get_or_create_user()

**Line:** 27-73

**Purpose:** Create new user or update existing user from Azure profile

**Signature:**
```python
def get_or_create_user(profile: dict) -> dict
```

**Parameters:**
- `profile` - Azure AD user profile from Microsoft Graph

**Returns:** User dictionary from database

**Expected Profile Structure:**
```python
{
    "mail": "user@example.com",
    "oid": "azure-object-id-123",
    "name": "John Doe",
    "given_name": "John",
    "family_name": "Doe"
}
```

**Implementation Flow:**

1. **Extract email** (line 29-35)
```python
email = profile.get('mail') or profile.get('userPrincipalName')

if not email:
    raise ValueError("No email found in profile")
```

2. **Check if user exists** (line 37-39)
```python
conn = sqlite3.connect('enterprise_bot.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
```

3. **Create new user if not exists** (line 42-50)
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

4. **Update existing user** (line 58-61)
```python
cursor.execute("""
    UPDATE users
    SET last_login = ?, display_name = ?, first_name = ?, last_name = ?
    WHERE email = ?
""", (datetime.now(), profile.get('name'), profile.get('given_name'),
      profile.get('family_name'), email))
```

5. **Fetch and return user** (line 69-72)
```python
cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
user = cursor.fetchone()
conn.close()
return dict(user)
```

**Database Operations:**
- INSERT into users (if new)
- UPDATE users (if existing)
- SELECT users by email

**Error Handling:**
- Raises ValueError if no email in profile
- Database errors bubble up as exceptions

---

### Function 3: get_user_by_id()

**Line:** 76-89

**Purpose:** Fetch user by database ID

**Signature:**
```python
def get_user_by_id(user_id: int) -> Optional[dict]
```

**Parameters:**
- `user_id` - Database user ID

**Returns:** User dictionary or None

**Implementation:**
```python
def get_user_by_id(user_id: int):
    """Get user by ID"""
    conn = sqlite3.connect('enterprise_bot.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, email, azure_oid, display_name, first_name, last_name,
               created_at, last_login, is_active, is_admin, department, job_title
        FROM users WHERE id = ?
    """, (user_id,))

    user = cursor.fetchone()
    conn.close()

    return dict(user) if user else None
```

**Database Query:**
- Table: users
- Columns: id, email, azure_oid, display_name, first_name, last_name, created_at, last_login, is_active, is_admin, department, job_title
- Filter: id = user_id

---

### Function 4: get_user_by_email()

**Line:** 91-104

**Purpose:** Fetch user by email address

**Signature:**
```python
def get_user_by_email(email: str) -> Optional[dict]
```

**Implementation:** Same pattern as get_user_by_id() but filters by email

---

### Function 5: get_user_by_azure_oid()

**Line:** 106-119

**Purpose:** Fetch user by Azure Object ID

**Signature:**
```python
def get_user_by_azure_oid(azure_oid: str) -> Optional[dict]
```

**Implementation:** Same pattern as get_user_by_id() but filters by azure_oid

---

### Function 6: create_session()

**Line:** 122-144

**Purpose:** Create new session token for user

**Signature:**
```python
def create_session(user_id: int, expires_in_days: int = 7) -> str
```

**Parameters:**
- `user_id` - Database user ID
- `expires_in_days` - Session lifetime (default: 7 days)

**Returns:** Session token string

**Implementation:**
```python
def create_session(user_id: int, expires_in_days: int = 7):
    """Create a new session for user"""
    # Generate secure token
    session_token = secrets.token_urlsafe(32)

    # Calculate expiration
    expires_at = datetime.now() + timedelta(days=expires_in_days)

    conn = sqlite3.connect('enterprise_bot.db')
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sessions (user_id, session_token, expires_at)
        VALUES (?, ?, ?)
    """, (
        user_id,
        session_token,
        expires_at
    ))

    conn.commit()
    conn.close()

    return session_token
```

**Security:**
- Uses `secrets.token_urlsafe(32)` for cryptographically secure tokens
- Token length: 32 bytes (256 bits) URL-safe encoded

**Database Operation:**
- INSERT into sessions

---

### Function 7: validate_session()

**Line:** 147-175

**Purpose:** Validate session token and return session data with user info

**Signature:**
```python
def validate_session(session_token: str) -> Optional[dict]
```

**Parameters:**
- `session_token` - Session token to validate

**Returns:** Session dict with user data, or None if invalid

**Return Structure:**
```python
{
    "id": 1,
    "user_id": 123,
    "session_token": "token...",
    "created_at": "2025-01-20T10:00:00",
    "expires_at": "2025-01-27T10:00:00",
    "is_active": 1,
    "email": "user@example.com",
    "is_active": true,  # from users table
    "is_admin": false   # from users table
}
```

**Implementation:**
```python
def validate_session(session_token: str):
    """Validate session token"""
    conn = sqlite3.connect('enterprise_bot.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get session with user info
    cursor.execute("""
        SELECT s.*, u.email, u.is_active, u.is_admin
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.session_token = ? AND s.is_active = 1
    """, (session_token,))

    session = cursor.fetchone()

    if not session:
        conn.close()
        return None

    # Check expiration
    if datetime.fromisoformat(session['expires_at']) < datetime.now():
        # Deactivate expired session
        cursor.execute("""
            UPDATE sessions SET is_active = 0 WHERE id = ?
        """, (session['id'],))
        conn.commit()
        conn.close()
        return None

    conn.close()
    return dict(session)
```

**Database Operations:**
- SELECT sessions JOIN users
- UPDATE sessions (if expired)

**Validation Logic:**
1. Check token exists and is_active = 1
2. Check expiration timestamp
3. Deactivate if expired

---

### Function 8: invalidate_session()

**Line:** 178-192

**Purpose:** Invalidate (logout) a session

**Signature:**
```python
def invalidate_session(session_token: str) -> bool
```

**Parameters:**
- `session_token` - Token to invalidate

**Returns:** True if invalidated, False if not found

**Implementation:**
```python
def invalidate_session(session_token: str):
    """Invalidate session (logout)"""
    conn = sqlite3.connect('enterprise_bot.db')
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sessions
        SET is_active = 0
        WHERE session_token = ?
    """, (session_token,))

    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_affected > 0
```

**Database Operation:**
- UPDATE sessions (set is_active = 0)

**Note:** Soft delete (doesn't remove session record)

---

### Function 9: cleanup_expired_sessions()

**Line:** 195-208

**Purpose:** Deactivate all expired sessions (maintenance task)

**Signature:**
```python
def cleanup_expired_sessions() -> int
```

**Returns:** Number of sessions cleaned up

**Implementation:**
```python
def cleanup_expired_sessions():
    """Cleanup expired sessions"""
    conn = sqlite3.connect('enterprise_bot.db')
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sessions
        SET is_active = 0
        WHERE expires_at < ? AND is_active = 1
    """, (datetime.now(),))

    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_affected
```

**Database Operation:**
- UPDATE sessions (batch deactivation)

**Usage:** Should be called periodically (cron job or scheduler)

---

### Function 10: log_audit_event()

**Line:** 211-231

**Purpose:** Log audit event for security/compliance

**Signature:**
```python
def log_audit_event(
    user_id: Optional[int],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None
```

**Parameters:**
- `user_id` - User who performed action (nullable)
- `action` - Action name (e.g., "user_login", "user_updated")
- `resource_type` - Type of resource affected (e.g., "user", "session")
- `resource_id` - ID of affected resource
- `details` - Additional JSON details
- `ip_address` - Client IP
- `user_agent` - Client user agent

**Implementation:**
```python
def log_audit_event(user_id, action, resource_type=None, resource_id=None,
                   details=None, ip_address=None, user_agent=None):
    """Log audit event"""
    conn = sqlite3.connect('enterprise_bot.db')
    cursor = conn.cursor()

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

    conn.commit()
    conn.close()
```

**Database Operation:**
- INSERT into audit_logs

**Details Serialization:** JSON encodes details dict

**Note:** Currently not called anywhere in the codebase (TODO: integrate)

---

## Azure SSO Flow

### Complete Flow Diagram

```
1. User clicks "Login with Microsoft"
   ↓
2. Frontend redirects to GET /api/auth/login
   ↓
3. Backend generates Azure authorization URL
   - Uses AZURE_CLIENT_ID, AZURE_TENANT_ID
   - Requests User.Read scope
   - Sets redirect_uri to AZURE_REDIRECT_URI
   ↓
4. User redirected to Azure AD login page
   - login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize
   ↓
5. User authenticates with Microsoft credentials
   ↓
6. Azure AD redirects to GET /api/auth/callback?code=...
   ↓
7. Backend exchanges code for tokens
   - POST to login.microsoftonline.com/{tenant}/oauth2/v2.0/token
   - Uses AZURE_CLIENT_SECRET
   ↓
8. Backend fetches user profile from Microsoft Graph
   - GET https://graph.microsoft.com/v1.0/me
   - Uses access_token from step 7
   ↓
9. Backend creates/updates user in database
   - Calls get_or_create_user(graph_data)
   - Updates last_login timestamp
   ↓
10. Backend creates session
    - Calls create_session(user_id)
    - Generates secure token
    - Sets 7-day expiration
   ↓
11. Backend sets session cookie and redirects to "/"
    - Cookie: session_token, HttpOnly, Secure, SameSite=Lax
   ↓
12. Frontend loads, cookie is automatically sent
   ↓
13. Protected routes validate session
    - Extract session_token from cookie
    - Call validate_session(token)
    - Check expiration and is_active
```

### Azure AD Configuration Requirements

**Required App Registration Settings:**

1. **Redirect URI:** Must match AZURE_REDIRECT_URI exactly
   - Example: `https://yourapp.com/api/auth/callback`
   - Must be registered in Azure portal

2. **API Permissions:**
   - Microsoft Graph: User.Read (Delegated)
   - Admin consent may be required

3. **Authentication Settings:**
   - Platform: Web
   - ID tokens: Not required (using auth code flow)
   - Access tokens: Required

4. **Client Secret:**
   - Must generate and copy to AZURE_CLIENT_SECRET
   - Set expiration appropriately

---

## Environment Variables

### Required Variables

| Variable | Used In | Purpose | Example Value |
|----------|---------|---------|---------------|
| AZURE_CLIENT_ID | auth_service.py:15, sso_routes.py:51 | Azure app client ID | "abc123-456def-789ghi" |
| AZURE_CLIENT_SECRET | auth_service.py:16, sso_routes.py:52 | Azure app secret | "secret_value_here" |
| AZURE_TENANT_ID | auth_service.py:17, sso_routes.py:53 | Azure tenant ID | "common" or specific tenant GUID |
| AZURE_REDIRECT_URI | auth_service.py:20, sso_routes.py:29 | OAuth callback URL | "http://localhost:8000/api/auth/callback" |

### Optional Variables

| Variable | Used In | Purpose | Default |
|----------|---------|---------|---------|
| SESSION_EXPIRY_DAYS | auth_service.py:122 | Session lifetime | 7 days |

### Environment File Location

Not explicitly documented in code. Typically:
- `.env` in project root
- Loaded via python-dotenv or similar

---

## Security Mechanisms

### 1. Session Token Security

**Generation:**
- Uses `secrets.token_urlsafe(32)` - cryptographically secure
- 256-bit entropy (32 bytes)
- URL-safe base64 encoding

**Storage:**
- HttpOnly cookie (prevents XSS access)
- Secure flag (HTTPS only in production)
- SameSite=Lax (CSRF protection)

**Validation:**
- Checks is_active flag
- Validates expiration timestamp
- Auto-deactivates expired sessions

### 2. Authentication Flow Security

**Strengths:**
- Uses OAuth 2.0 Authorization Code flow (secure)
- Client secret never exposed to frontend
- Tokens exchanged server-side only
- Session tokens are separate from OAuth tokens

**Weaknesses:**
- TODO: State parameter not implemented (CSRF risk) - sso_routes.py:28
- No token refresh mechanism
- No remember-me / extended session option

### 3. Authorization Checks

**Admin Routes:**
- Protected by `verify_admin_access()` dependency
- Validates session exists and is valid
- Checks is_admin flag from database
- Returns 403 for non-admin users

**Regular Routes:**
- `/api/auth/me` validates session
- Other routes should validate but many don't

### 4. Database Security

**Connection Security:**
- No connection pooling (creates new connection each time)
- No prepared statement caching
- Vulnerable to connection exhaustion under load

**Query Security:**
- Uses parameterized queries (safe from SQL injection)
- No dynamic table/column names (good)

**Data Protection:**
- Passwords: N/A (using Azure AD SSO)
- Session tokens: Stored in plain text in database (risk)
- No encryption at rest

### 5. Audit Trail

**Implementation:**
- `log_audit_event()` function exists
- Captures: user_id, action, resource, details, IP, user agent
- Stores in audit_logs table

**Coverage:**
- Currently NOT called anywhere (TODO)
- Should log: login, logout, admin actions, user changes

---

## Security Recommendations

### High Priority

1. **Implement CSRF state validation** (sso_routes.py:28)
2. **Enable foreign key constraints** (`PRAGMA foreign_keys = ON;`)
3. **Encrypt session tokens** at rest
4. **Implement audit logging** for all sensitive operations
5. **Add rate limiting** to prevent brute force

### Medium Priority

1. **Add token refresh mechanism**
2. **Implement connection pooling**
3. **Add session cleanup scheduler**
4. **Add IP-based session validation**
5. **Implement device tracking**

### Low Priority

1. **Add remember-me functionality**
2. **Implement multi-factor authentication**
3. **Add session management UI** (view active sessions, logout all)
4. **Add password reset flow** (if adding local auth)

---

## Error Handling Patterns

### HTTP Exceptions

All routes use FastAPI HTTPException:

```python
# Authentication errors
raise HTTPException(status_code=401, detail="Not authenticated")
raise HTTPException(status_code=401, detail="Invalid session")

# Authorization errors
raise HTTPException(status_code=403, detail="Admin access required")

# Not found errors
raise HTTPException(status_code=404, detail="User not found")

# Validation errors
raise HTTPException(status_code=400, detail="No fields to update")

# Server errors
raise HTTPException(status_code=500, detail=str(e))
```

### Database Errors

- No explicit error handling for database errors
- Errors bubble up as 500 Internal Server Error
- No transaction rollback logic
- No connection cleanup in error cases

---

## Missing Implementations

### Features Referenced But Not Implemented

1. **CSRF State Protection**
   - Location: sso_routes.py:28
   - Comment: `# TODO: Add CSRF state`

2. **Audit Logging Integration**
   - Function exists: auth_service.py:211-231
   - Never called in any route

3. **Session Cleanup Scheduler**
   - Function exists: auth_service.py:195-208
   - No cron job or scheduler configured

4. **Foreign Key Enforcement**
   - Schema defines foreign keys
   - Never enabled with `PRAGMA foreign_keys = ON;`

5. **Schema Initialization Integration**
   - Function exists: auth_schema.py:67-79
   - Not called from main.py or startup hooks

---

**End of Backend Authentication Flow Map**
