# Feature Build Sheet: Personal Tier Authentication

## Feature: PERSONAL_AUTH
**Priority:** P0  
**Estimated Complexity:** High  
**Dependencies:** Redis (exists), personal.users table (migrated)

---

## 1. OVERVIEW

### User Story
> As a personal CogTwin user, I want to sign up with Google or email/password so that I can access my cognitive memory system without enterprise SSO.

### Acceptance Criteria
- [ ] User can register with email + password
- [ ] User can login with email + password
- [ ] User can sign in with Google OAuth
- [ ] Sessions stored in Redis (not localStorage JWT)
- [ ] HTTP-only secure cookies for session ID
- [ ] Email verification flow works
- [ ] Password reset flow works
- [ ] Logout actually invalidates session

---

## 2. DATABASE CHANGES

### Already Applied (Confirmed by User)
```sql
-- Migration: personal.users auth columns
ALTER TABLE personal.users 
    ADD COLUMN IF NOT EXISTS password_hash TEXT,
    ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS verification_token VARCHAR(64),
    ADD COLUMN IF NOT EXISTS verification_expires TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reset_token VARCHAR(64),
    ADD COLUMN IF NOT EXISTS reset_expires TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS google_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS display_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512),
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id 
    ON personal.users(google_id) WHERE google_id IS NOT NULL;
```

**Status:** COMPLETE - No action needed.

---

## 3. BACKEND CHANGES

### New Files
| File | Purpose |
|------|---------|
| `auth/personal_auth.py` | Core auth service (password hashing, session management) |
| `auth/personal_auth_routes.py` | API endpoints for register/login/oauth |

### Environment Variables Required
```bash
# Google OAuth (get from console.cloud.google.com)
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx

# Session config
SESSION_SECRET=<generate-64-char-random-string>
SESSION_TTL_DAYS=7

# Email sending (for verification/reset)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=<sendgrid-api-key>
FROM_EMAIL=noreply@cogtwin.dev
```

---

### File: auth/personal_auth.py

```python
"""
Personal Auth Service - Email/Password + Google OAuth

Handles:
- Password hashing (argon2)
- Session management (Redis)
- Google OAuth code exchange
- Email verification tokens
- Password reset tokens

Sessions stored in Redis with format:
    session:{session_id} -> {user_id, email, created_at, ...}
    
Cookie: session_id (HTTP-only, Secure, SameSite=Lax)
"""

import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dataclasses import dataclass
import json

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

logger = logging.getLogger(__name__)

# Password hasher (argon2id - current best practice)
ph = PasswordHasher()

# Config
SESSION_TTL_DAYS = int(os.getenv("SESSION_TTL_DAYS", "7"))
SESSION_TTL_SECONDS = SESSION_TTL_DAYS * 24 * 60 * 60
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")


@dataclass
class SessionData:
    """Data stored in Redis for a session."""
    user_id: str
    email: str
    display_name: Optional[str]
    auth_provider: str  # "email" | "google"
    created_at: str
    
    def to_json(self) -> str:
        return json.dumps({
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "auth_provider": self.auth_provider,
            "created_at": self.created_at,
        })
    
    @classmethod
    def from_json(cls, data: str) -> "SessionData":
        d = json.loads(data)
        return cls(**d)


@dataclass
class AuthResult:
    """Result of an auth operation."""
    success: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    error: Optional[str] = None
    session_id: Optional[str] = None


class PersonalAuthService:
    """
    Authentication service for personal tier users.
    
    Uses Redis for session storage and PostgreSQL (personal.users) for user data.
    """
    
    def __init__(self, redis_client, db_pool):
        """
        Args:
            redis_client: aioredis client instance
            db_pool: asyncpg connection pool
        """
        self.redis = redis_client
        self.db = db_pool
    
    # =========================================================================
    # PASSWORD OPERATIONS
    # =========================================================================
    
    def hash_password(self, password: str) -> str:
        """Hash a password using argon2id."""
        return ph.hash(password)
    
    def verify_password(self, password: str, hash: str) -> bool:
        """Verify a password against its hash."""
        try:
            ph.verify(hash, password)
            return True
        except VerifyMismatchError:
            return False
    
    # =========================================================================
    # SESSION OPERATIONS
    # =========================================================================
    
    async def create_session(
        self,
        user_id: str,
        email: str,
        display_name: Optional[str],
        auth_provider: str,
    ) -> str:
        """
        Create a new session in Redis.
        
        Returns:
            session_id (to be set as cookie)
        """
        session_id = secrets.token_urlsafe(32)
        
        session_data = SessionData(
            user_id=user_id,
            email=email,
            display_name=display_name,
            auth_provider=auth_provider,
            created_at=datetime.utcnow().isoformat(),
        )
        
        await self.redis.setex(
            f"session:{session_id}",
            SESSION_TTL_SECONDS,
            session_data.to_json(),
        )
        
        logger.info(f"Created session for user {email}")
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session data from Redis."""
        data = await self.redis.get(f"session:{session_id}")
        if not data:
            return None
        return SessionData.from_json(data)
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session (logout)."""
        result = await self.redis.delete(f"session:{session_id}")
        return result > 0
    
    async def refresh_session(self, session_id: str) -> bool:
        """Extend session TTL (call on activity)."""
        return await self.redis.expire(f"session:{session_id}", SESSION_TTL_SECONDS)
    
    # =========================================================================
    # EMAIL/PASSWORD AUTH
    # =========================================================================
    
    async def register_email(
        self,
        email: str,
        password: str,
        display_name: Optional[str] = None,
    ) -> AuthResult:
        """
        Register a new user with email/password.
        
        Returns AuthResult with verification token on success.
        """
        email = email.lower().strip()
        
        async with self.db.acquire() as conn:
            # Check if email exists
            existing = await conn.fetchrow(
                "SELECT id, auth_provider FROM personal.users WHERE email = $1",
                email
            )
            
            if existing:
                if existing["auth_provider"] == "google":
                    return AuthResult(
                        success=False,
                        error="This email is registered with Google. Please sign in with Google."
                    )
                return AuthResult(success=False, error="Email already registered")
            
            # Hash password
            password_hash = self.hash_password(password)
            
            # Generate verification token
            verification_token = secrets.token_urlsafe(32)
            verification_expires = datetime.utcnow() + timedelta(hours=24)
            
            # Insert user
            user = await conn.fetchrow(
                """
                INSERT INTO personal.users (
                    email, auth_provider, password_hash, display_name,
                    verification_token, verification_expires, email_verified
                )
                VALUES ($1, 'email', $2, $3, $4, $5, false)
                RETURNING id, email, display_name
                """,
                email, password_hash, display_name,
                verification_token, verification_expires
            )
            
            logger.info(f"Registered new user: {email}")
            
            return AuthResult(
                success=True,
                user_id=str(user["id"]),
                email=user["email"],
                display_name=user["display_name"],
            )
    
    async def login_email(self, email: str, password: str) -> AuthResult:
        """
        Authenticate user with email/password.
        
        Returns AuthResult with session_id on success.
        """
        email = email.lower().strip()
        
        async with self.db.acquire() as conn:
            user = await conn.fetchrow(
                """
                SELECT id, email, display_name, password_hash, 
                       email_verified, is_active, auth_provider
                FROM personal.users 
                WHERE email = $1
                """,
                email
            )
            
            if not user:
                return AuthResult(success=False, error="Invalid email or password")
            
            if user["auth_provider"] == "google":
                return AuthResult(
                    success=False,
                    error="This account uses Google sign-in. Please use 'Sign in with Google'."
                )
            
            if not user["is_active"]:
                return AuthResult(success=False, error="Account is deactivated")
            
            if not user["password_hash"]:
                return AuthResult(success=False, error="Invalid email or password")
            
            if not self.verify_password(password, user["password_hash"]):
                return AuthResult(success=False, error="Invalid email or password")
            
            # Optional: require email verification
            # if not user["email_verified"]:
            #     return AuthResult(success=False, error="Please verify your email first")
            
            # Update last login
            await conn.execute(
                "UPDATE personal.users SET last_login_at = NOW() WHERE id = $1",
                user["id"]
            )
            
            # Create session
            session_id = await self.create_session(
                user_id=str(user["id"]),
                email=user["email"],
                display_name=user["display_name"],
                auth_provider="email",
            )
            
            return AuthResult(
                success=True,
                user_id=str(user["id"]),
                email=user["email"],
                display_name=user["display_name"],
                session_id=session_id,
            )
    
    async def verify_email(self, token: str) -> AuthResult:
        """Verify email with token."""
        async with self.db.acquire() as conn:
            user = await conn.fetchrow(
                """
                UPDATE personal.users 
                SET email_verified = true, 
                    verification_token = NULL, 
                    verification_expires = NULL
                WHERE verification_token = $1 
                  AND verification_expires > NOW()
                RETURNING id, email, display_name
                """,
                token
            )
            
            if not user:
                return AuthResult(success=False, error="Invalid or expired verification link")
            
            return AuthResult(
                success=True,
                user_id=str(user["id"]),
                email=user["email"],
            )
    
    async def request_password_reset(self, email: str) -> Tuple[bool, Optional[str]]:
        """
        Generate password reset token.
        
        Returns (success, token) - token is None if user not found.
        Always returns success=True to prevent email enumeration.
        """
        email = email.lower().strip()
        
        async with self.db.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT id, auth_provider FROM personal.users WHERE email = $1",
                email
            )
            
            if not user or user["auth_provider"] != "email":
                # Don't reveal whether email exists
                return (True, None)
            
            reset_token = secrets.token_urlsafe(32)
            reset_expires = datetime.utcnow() + timedelta(hours=1)
            
            await conn.execute(
                """
                UPDATE personal.users 
                SET reset_token = $1, reset_expires = $2 
                WHERE id = $3
                """,
                reset_token, reset_expires, user["id"]
            )
            
            return (True, reset_token)
    
    async def reset_password(self, token: str, new_password: str) -> AuthResult:
        """Reset password using token."""
        async with self.db.acquire() as conn:
            user = await conn.fetchrow(
                """
                SELECT id, email FROM personal.users
                WHERE reset_token = $1 AND reset_expires > NOW()
                """,
                token
            )
            
            if not user:
                return AuthResult(success=False, error="Invalid or expired reset link")
            
            password_hash = self.hash_password(new_password)
            
            await conn.execute(
                """
                UPDATE personal.users 
                SET password_hash = $1, reset_token = NULL, reset_expires = NULL
                WHERE id = $2
                """,
                password_hash, user["id"]
            )
            
            return AuthResult(success=True, user_id=str(user["id"]), email=user["email"])
    
    # =========================================================================
    # GOOGLE OAUTH
    # =========================================================================
    
    async def google_auth(self, code: str, redirect_uri: str) -> AuthResult:
        """
        Exchange Google auth code for tokens and create/update user.
        
        Args:
            code: Authorization code from Google
            redirect_uri: Must match what was used to get the code
        """
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            return AuthResult(success=False, error="Google OAuth not configured")
        
        try:
            # Exchange code for tokens
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
                
                if token_response.status_code != 200:
                    logger.error(f"Google token exchange failed: {token_response.text}")
                    return AuthResult(success=False, error="Failed to authenticate with Google")
                
                tokens = token_response.json()
                access_token = tokens["access_token"]
                
                # Get user info
                userinfo_response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                
                if userinfo_response.status_code != 200:
                    return AuthResult(success=False, error="Failed to get user info from Google")
                
                userinfo = userinfo_response.json()
            
            google_id = userinfo["id"]
            email = userinfo["email"].lower()
            display_name = userinfo.get("name")
            avatar_url = userinfo.get("picture")
            
            async with self.db.acquire() as conn:
                # Check if user exists by google_id or email
                existing = await conn.fetchrow(
                    """
                    SELECT id, email, google_id, auth_provider 
                    FROM personal.users 
                    WHERE google_id = $1 OR email = $2
                    """,
                    google_id, email
                )
                
                if existing:
                    if existing["auth_provider"] == "email" and not existing["google_id"]:
                        # Link Google to existing email account
                        await conn.execute(
                            """
                            UPDATE personal.users 
                            SET google_id = $1, avatar_url = $2, last_login_at = NOW()
                            WHERE id = $3
                            """,
                            google_id, avatar_url, existing["id"]
                        )
                        user_id = str(existing["id"])
                    else:
                        # Existing Google user - update last login
                        await conn.execute(
                            "UPDATE personal.users SET last_login_at = NOW() WHERE id = $1",
                            existing["id"]
                        )
                        user_id = str(existing["id"])
                else:
                    # New user
                    user = await conn.fetchrow(
                        """
                        INSERT INTO personal.users (
                            email, auth_provider, google_id, display_name, 
                            avatar_url, email_verified, last_login_at
                        )
                        VALUES ($1, 'google', $2, $3, $4, true, NOW())
                        RETURNING id
                        """,
                        email, google_id, display_name, avatar_url
                    )
                    user_id = str(user["id"])
                    logger.info(f"Created new Google user: {email}")
            
            # Create session
            session_id = await self.create_session(
                user_id=user_id,
                email=email,
                display_name=display_name,
                auth_provider="google",
            )
            
            return AuthResult(
                success=True,
                user_id=user_id,
                email=email,
                display_name=display_name,
                session_id=session_id,
            )
            
        except Exception as e:
            logger.exception(f"Google auth error: {e}")
            return AuthResult(success=False, error="Authentication failed")


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_personal_auth_service: Optional[PersonalAuthService] = None


async def get_personal_auth_service(redis_client, db_pool) -> PersonalAuthService:
    """Get or create the personal auth service singleton."""
    global _personal_auth_service
    if _personal_auth_service is None:
        _personal_auth_service = PersonalAuthService(redis_client, db_pool)
    return _personal_auth_service
```

---

### File: auth/personal_auth_routes.py

```python
"""
Personal Auth Routes - Email/Password + Google OAuth

Endpoints:
    POST /api/personal/auth/register     - Email registration
    POST /api/personal/auth/login        - Email login
    POST /api/personal/auth/logout       - Logout (clear session)
    GET  /api/personal/auth/me           - Get current user
    GET  /api/personal/auth/google       - Get Google OAuth URL
    POST /api/personal/auth/google/callback - Google OAuth callback
    POST /api/personal/auth/verify-email - Verify email token
    POST /api/personal/auth/forgot       - Request password reset
    POST /api/personal/auth/reset        - Reset password with token

All session endpoints use HTTP-only cookies, not Authorization headers.
"""

import os
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Response, Request, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
import secrets

from .personal_auth import get_personal_auth_service, PersonalAuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/personal/auth", tags=["personal-auth"])

# Config
COOKIE_NAME = "session_id"
COOKIE_SECURE = os.getenv("ENV", "production") == "production"  # HTTPS only in prod
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", None)  # None = current domain
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleCallbackRequest(BaseModel):
    code: str
    redirect_uri: str

class ForgotRequest(BaseModel):
    email: EmailStr

class ResetRequest(BaseModel):
    token: str
    new_password: str

class VerifyRequest(BaseModel):
    token: str

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    auth_provider: str


# =============================================================================
# DEPENDENCY: Get Auth Service
# =============================================================================

async def get_auth(request: Request) -> PersonalAuthService:
    """Dependency to get auth service with Redis and DB from app state."""
    redis = request.app.state.redis
    db_pool = request.app.state.db_pool
    return await get_personal_auth_service(redis, db_pool)


async def get_current_user(request: Request, auth: PersonalAuthService = Depends(get_auth)):
    """Dependency to get current user from session cookie."""
    session_id = request.cookies.get(COOKIE_NAME)
    if not session_id:
        raise HTTPException(401, "Not authenticated")
    
    session = await auth.get_session(session_id)
    if not session:
        raise HTTPException(401, "Session expired")
    
    # Refresh session TTL on activity
    await auth.refresh_session(session_id)
    
    return session


# =============================================================================
# HELPER: Set Session Cookie
# =============================================================================

def set_session_cookie(response: Response, session_id: str):
    """Set the session cookie with secure defaults."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
        domain=COOKIE_DOMAIN,
        path="/",
    )


def clear_session_cookie(response: Response):
    """Clear the session cookie."""
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        domain=COOKIE_DOMAIN,
        path="/",
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/register")
async def register(
    payload: RegisterRequest,
    response: Response,
    auth: PersonalAuthService = Depends(get_auth),
):
    """
    Register a new user with email/password.
    
    Returns user info. Does NOT auto-login (require email verification first).
    """
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    
    result = await auth.register_email(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
    )
    
    if not result.success:
        raise HTTPException(400, result.error)
    
    # TODO: Send verification email here
    # await send_verification_email(result.email, verification_token)
    
    return {
        "success": True,
        "message": "Registration successful. Please check your email to verify your account.",
        "user": {
            "id": result.user_id,
            "email": result.email,
            "display_name": result.display_name,
        }
    }


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    auth: PersonalAuthService = Depends(get_auth),
):
    """
    Login with email/password.
    
    Sets session cookie on success.
    """
    result = await auth.login_email(payload.email, payload.password)
    
    if not result.success:
        raise HTTPException(401, result.error)
    
    set_session_cookie(response, result.session_id)
    
    return {
        "success": True,
        "user": {
            "id": result.user_id,
            "email": result.email,
            "display_name": result.display_name,
            "auth_provider": "email",
        }
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    auth: PersonalAuthService = Depends(get_auth),
):
    """
    Logout - delete session from Redis and clear cookie.
    """
    session_id = request.cookies.get(COOKIE_NAME)
    if session_id:
        await auth.delete_session(session_id)
    
    clear_session_cookie(response)
    
    return {"success": True}


@router.get("/me")
async def get_me(session = Depends(get_current_user)):
    """
    Get current authenticated user.
    """
    return {
        "id": session.user_id,
        "email": session.email,
        "display_name": session.display_name,
        "auth_provider": session.auth_provider,
    }


# =============================================================================
# GOOGLE OAUTH
# =============================================================================

@router.get("/google")
async def google_login_url(redirect_uri: Optional[str] = None):
    """
    Get Google OAuth URL for frontend redirect.
    
    Frontend calls this, gets URL, redirects user to Google.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google OAuth not configured")
    
    # Use provided redirect_uri or default
    callback_uri = redirect_uri or f"{FRONTEND_URL}/auth/google/callback"
    
    state = secrets.token_urlsafe(32)
    
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": callback_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    
    return {
        "url": url,
        "state": state,  # Frontend should store and validate this
    }


@router.post("/google/callback")
async def google_callback(
    payload: GoogleCallbackRequest,
    response: Response,
    auth: PersonalAuthService = Depends(get_auth),
):
    """
    Exchange Google auth code for session.
    
    Frontend catches ?code=xxx from Google redirect, POSTs it here.
    """
    result = await auth.google_auth(payload.code, payload.redirect_uri)
    
    if not result.success:
        raise HTTPException(401, result.error)
    
    set_session_cookie(response, result.session_id)
    
    return {
        "success": True,
        "user": {
            "id": result.user_id,
            "email": result.email,
            "display_name": result.display_name,
            "auth_provider": "google",
        }
    }


# =============================================================================
# EMAIL VERIFICATION
# =============================================================================

@router.post("/verify-email")
async def verify_email(
    payload: VerifyRequest,
    auth: PersonalAuthService = Depends(get_auth),
):
    """Verify email address with token from email link."""
    result = await auth.verify_email(payload.token)
    
    if not result.success:
        raise HTTPException(400, result.error)
    
    return {"success": True, "message": "Email verified successfully"}


# =============================================================================
# PASSWORD RESET
# =============================================================================

@router.post("/forgot")
async def forgot_password(
    payload: ForgotRequest,
    auth: PersonalAuthService = Depends(get_auth),
):
    """
    Request password reset email.
    
    Always returns success to prevent email enumeration.
    """
    success, token = await auth.request_password_reset(payload.email)
    
    if token:
        # TODO: Send reset email
        # await send_reset_email(payload.email, token)
        pass
    
    return {
        "success": True,
        "message": "If an account exists with this email, you will receive a password reset link."
    }


@router.post("/reset")
async def reset_password(
    payload: ResetRequest,
    auth: PersonalAuthService = Depends(get_auth),
):
    """Reset password using token from email."""
    if len(payload.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    
    result = await auth.reset_password(payload.token, payload.new_password)
    
    if not result.success:
        raise HTTPException(400, result.error)
    
    return {"success": True, "message": "Password reset successfully. You can now login."}
```

---

### Wire into main.py

Add these lines to `core/main.py`:

```python
# === NEAR TOP WITH OTHER IMPORTS ===
# Personal auth imports (for personal deployment mode)
try:
    from auth.personal_auth_routes import router as personal_auth_router
    PERSONAL_AUTH_LOADED = True
except ImportError as e:
    logger.warning(f"Personal auth routes not loaded: {e}")
    PERSONAL_AUTH_LOADED = False


# === IN THE ROUTER REGISTRATION SECTION (around line 400) ===
# Personal auth routes (only in personal deployment mode)
if PERSONAL_AUTH_LOADED and cfg('deployment.mode', 'enterprise') == 'personal':
    app.include_router(personal_auth_router)
    logger.info("[STARTUP] Personal auth routes loaded at /api/personal/auth")


# === IN THE STARTUP EVENT (add Redis + DB pool to app state) ===
@app.on_event("startup")
async def startup():
    # ... existing startup code ...
    
    # Initialize Redis for sessions (personal mode)
    if cfg('deployment.mode', 'enterprise') == 'personal':
        import aioredis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        app.state.redis = aioredis.from_url(redis_url, decode_responses=True)
        logger.info("[STARTUP] Redis connected for personal sessions")
        
        # Initialize DB pool
        from core.database import init_db_pool
        app.state.db_pool = await init_db_pool()
        logger.info("[STARTUP] DB pool initialized for personal auth")
```

---

## 4. FRONTEND CHANGES

### File: src/lib/stores/personalAuth.ts

**NEW FILE** - Personal auth store (separate from enterprise Azure AD auth)

```typescript
/**
 * Personal Auth Store - Email/Password + Google OAuth
 * 
 * Uses HTTP-only cookies for sessions (no localStorage tokens).
 * Backend manages session in Redis.
 */

import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

// =============================================================================
// TYPES
// =============================================================================

interface PersonalUser {
    id: string;
    email: string;
    display_name: string | null;
    auth_provider: 'email' | 'google';
}

interface PersonalAuthState {
    user: PersonalUser | null;
    loading: boolean;
    error: string | null;
    initialized: boolean;
}

// =============================================================================
// STORE
// =============================================================================

const initialState: PersonalAuthState = {
    user: null,
    loading: false,
    error: null,
    initialized: false,
};

function createPersonalAuthStore() {
    const { subscribe, set, update } = writable<PersonalAuthState>(initialState);
    
    const API_URL = import.meta.env.VITE_API_URL || '';
    
    return {
        subscribe,
        
        /**
         * Initialize - check if user has valid session
         */
        async init() {
            if (!browser) return;
            
            update(s => ({ ...s, loading: true }));
            
            try {
                const res = await fetch(`${API_URL}/api/personal/auth/me`, {
                    credentials: 'include',  // Send cookies
                });
                
                if (res.ok) {
                    const user = await res.json();
                    update(s => ({
                        ...s,
                        user,
                        loading: false,
                        initialized: true,
                    }));
                } else {
                    update(s => ({
                        ...s,
                        user: null,
                        loading: false,
                        initialized: true,
                    }));
                }
            } catch (e) {
                update(s => ({
                    ...s,
                    user: null,
                    loading: false,
                    initialized: true,
                    error: 'Failed to check authentication',
                }));
            }
        },
        
        /**
         * Register with email/password
         */
        async register(email: string, password: string, displayName?: string) {
            update(s => ({ ...s, loading: true, error: null }));
            
            try {
                const res = await fetch(`${API_URL}/api/personal/auth/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password, display_name: displayName }),
                    credentials: 'include',
                });
                
                const data = await res.json();
                
                if (!res.ok) {
                    throw new Error(data.detail || 'Registration failed');
                }
                
                update(s => ({ ...s, loading: false }));
                return { success: true, message: data.message };
                
            } catch (e: any) {
                update(s => ({ ...s, loading: false, error: e.message }));
                return { success: false, error: e.message };
            }
        },
        
        /**
         * Login with email/password
         */
        async login(email: string, password: string) {
            update(s => ({ ...s, loading: true, error: null }));
            
            try {
                const res = await fetch(`${API_URL}/api/personal/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password }),
                    credentials: 'include',
                });
                
                const data = await res.json();
                
                if (!res.ok) {
                    throw new Error(data.detail || 'Login failed');
                }
                
                update(s => ({
                    ...s,
                    user: data.user,
                    loading: false,
                }));
                
                return { success: true };
                
            } catch (e: any) {
                update(s => ({ ...s, loading: false, error: e.message }));
                return { success: false, error: e.message };
            }
        },
        
        /**
         * Start Google OAuth flow
         */
        async startGoogleLogin() {
            try {
                const redirectUri = `${window.location.origin}/auth/google/callback`;
                const res = await fetch(
                    `${API_URL}/api/personal/auth/google?redirect_uri=${encodeURIComponent(redirectUri)}`,
                    { credentials: 'include' }
                );
                
                if (!res.ok) throw new Error('Failed to get Google login URL');
                
                const { url, state } = await res.json();
                
                // Store state for validation
                sessionStorage.setItem('google_oauth_state', state);
                
                // Redirect to Google
                window.location.href = url;
                
            } catch (e: any) {
                update(s => ({ ...s, error: e.message }));
            }
        },
        
        /**
         * Complete Google OAuth (called from callback page)
         */
        async completeGoogleLogin(code: string, state: string) {
            update(s => ({ ...s, loading: true, error: null }));
            
            // Validate state
            const storedState = sessionStorage.getItem('google_oauth_state');
            if (state !== storedState) {
                update(s => ({ ...s, loading: false, error: 'Invalid OAuth state' }));
                return { success: false, error: 'Invalid OAuth state' };
            }
            sessionStorage.removeItem('google_oauth_state');
            
            try {
                const redirectUri = `${window.location.origin}/auth/google/callback`;
                const res = await fetch(`${API_URL}/api/personal/auth/google/callback`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code, redirect_uri: redirectUri }),
                    credentials: 'include',
                });
                
                const data = await res.json();
                
                if (!res.ok) {
                    throw new Error(data.detail || 'Google login failed');
                }
                
                update(s => ({
                    ...s,
                    user: data.user,
                    loading: false,
                }));
                
                return { success: true };
                
            } catch (e: any) {
                update(s => ({ ...s, loading: false, error: e.message }));
                return { success: false, error: e.message };
            }
        },
        
        /**
         * Logout
         */
        async logout() {
            try {
                await fetch(`${API_URL}/api/personal/auth/logout`, {
                    method: 'POST',
                    credentials: 'include',
                });
            } catch (e) {
                // Ignore errors, clear local state anyway
            }
            
            set({ ...initialState, initialized: true });
        },
        
        /**
         * Request password reset
         */
        async forgotPassword(email: string) {
            try {
                const res = await fetch(`${API_URL}/api/personal/auth/forgot`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email }),
                    credentials: 'include',
                });
                
                const data = await res.json();
                return { success: true, message: data.message };
                
            } catch (e: any) {
                return { success: false, error: e.message };
            }
        },
        
        /**
         * Reset password with token
         */
        async resetPassword(token: string, newPassword: string) {
            try {
                const res = await fetch(`${API_URL}/api/personal/auth/reset`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token, new_password: newPassword }),
                    credentials: 'include',
                });
                
                const data = await res.json();
                
                if (!res.ok) {
                    throw new Error(data.detail || 'Password reset failed');
                }
                
                return { success: true, message: data.message };
                
            } catch (e: any) {
                return { success: false, error: e.message };
            }
        },
        
        clearError() {
            update(s => ({ ...s, error: null }));
        },
    };
}

export const personalAuthStore = createPersonalAuthStore();

// Derived stores
export const isAuthenticated = derived(
    personalAuthStore,
    $store => $store.user !== null
);

export const currentUser = derived(
    personalAuthStore,
    $store => $store.user
);
```

---

### File: src/routes/auth/google/callback/+page.svelte

**NEW FILE** - Google OAuth callback handler

```svelte
<script lang="ts">
    import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { personalAuthStore } from '$lib/stores/personalAuth';
    
    let error: string | null = null;
    
    onMount(async () => {
        const code = $page.url.searchParams.get('code');
        const state = $page.url.searchParams.get('state');
        const errorParam = $page.url.searchParams.get('error');
        
        if (errorParam) {
            error = `Google login failed: ${errorParam}`;
            return;
        }
        
        if (!code || !state) {
            error = 'Missing authorization code';
            return;
        }
        
        const result = await personalAuthStore.completeGoogleLogin(code, state);
        
        if (result.success) {
            goto('/');
        } else {
            error = result.error || 'Login failed';
        }
    });
</script>

<div class="min-h-screen flex items-center justify-center bg-gray-900">
    <div class="text-center">
        {#if error}
            <div class="bg-red-900/50 border border-red-500 rounded-lg p-6 max-w-md">
                <h2 class="text-xl font-semibold text-red-400 mb-2">Authentication Failed</h2>
                <p class="text-gray-300">{error}</p>
                <a href="/login" class="mt-4 inline-block text-blue-400 hover:underline">
                    Try again
                </a>
            </div>
        {:else}
            <div class="animate-pulse">
                <div class="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                <p class="mt-4 text-gray-400">Completing sign in...</p>
            </div>
        {/if}
    </div>
</div>
```

---

### File: src/routes/login/+page.svelte

**NEW FILE** - Login page with email + Google options

```svelte
<script lang="ts">
    import { goto } from '$app/navigation';
    import { personalAuthStore, isAuthenticated } from '$lib/stores/personalAuth';
    
    let email = '';
    let password = '';
    let isRegister = false;
    let displayName = '';
    let loading = false;
    let message = '';
    let error = '';
    
    // Redirect if already logged in
    $: if ($isAuthenticated) {
        goto('/');
    }
    
    async function handleSubmit() {
        loading = true;
        error = '';
        message = '';
        
        if (isRegister) {
            const result = await personalAuthStore.register(email, password, displayName || undefined);
            if (result.success) {
                message = result.message || 'Registration successful!';
                isRegister = false;  // Switch to login view
            } else {
                error = result.error || 'Registration failed';
            }
        } else {
            const result = await personalAuthStore.login(email, password);
            if (result.success) {
                goto('/');
            } else {
                error = result.error || 'Login failed';
            }
        }
        
        loading = false;
    }
    
    function handleGoogleLogin() {
        personalAuthStore.startGoogleLogin();
    }
</script>

<div class="min-h-screen flex items-center justify-center bg-gray-900 px-4">
    <div class="max-w-md w-full space-y-8">
        <!-- Header -->
        <div class="text-center">
            <h1 class="text-3xl font-bold text-white">CogTwin</h1>
            <p class="mt-2 text-gray-400">Your cognitive memory system</p>
        </div>
        
        <!-- Card -->
        <div class="bg-gray-800 rounded-xl shadow-xl p-8">
            <h2 class="text-xl font-semibold text-white mb-6">
                {isRegister ? 'Create Account' : 'Sign In'}
            </h2>
            
            <!-- Google Button -->
            <button
                on:click={handleGoogleLogin}
                class="w-full flex items-center justify-center gap-3 px-4 py-3 
                       bg-white text-gray-800 rounded-lg font-medium
                       hover:bg-gray-100 transition-colors"
            >
                <svg class="w-5 h-5" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
            </button>
            
            <!-- Divider -->
            <div class="relative my-6">
                <div class="absolute inset-0 flex items-center">
                    <div class="w-full border-t border-gray-700"></div>
                </div>
                <div class="relative flex justify-center text-sm">
                    <span class="px-2 bg-gray-800 text-gray-500">or</span>
                </div>
            </div>
            
            <!-- Email Form -->
            <form on:submit|preventDefault={handleSubmit} class="space-y-4">
                {#if isRegister}
                    <div>
                        <label for="displayName" class="block text-sm font-medium text-gray-300">
                            Name (optional)
                        </label>
                        <input
                            type="text"
                            id="displayName"
                            bind:value={displayName}
                            class="mt-1 block w-full px-4 py-3 bg-gray-700 border border-gray-600 
                                   rounded-lg text-white placeholder-gray-400
                                   focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            placeholder="Your name"
                        />
                    </div>
                {/if}
                
                <div>
                    <label for="email" class="block text-sm font-medium text-gray-300">
                        Email
                    </label>
                    <input
                        type="email"
                        id="email"
                        bind:value={email}
                        required
                        class="mt-1 block w-full px-4 py-3 bg-gray-700 border border-gray-600 
                               rounded-lg text-white placeholder-gray-400
                               focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        placeholder="you@example.com"
                    />
                </div>
                
                <div>
                    <label for="password" class="block text-sm font-medium text-gray-300">
                        Password
                    </label>
                    <input
                        type="password"
                        id="password"
                        bind:value={password}
                        required
                        minlength="8"
                        class="mt-1 block w-full px-4 py-3 bg-gray-700 border border-gray-600 
                               rounded-lg text-white placeholder-gray-400
                               focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        placeholder="Min 8 characters"
                    />
                </div>
                
                {#if error}
                    <div class="bg-red-900/50 border border-red-500 rounded-lg p-3">
                        <p class="text-red-400 text-sm">{error}</p>
                    </div>
                {/if}
                
                {#if message}
                    <div class="bg-green-900/50 border border-green-500 rounded-lg p-3">
                        <p class="text-green-400 text-sm">{message}</p>
                    </div>
                {/if}
                
                <button
                    type="submit"
                    disabled={loading}
                    class="w-full px-4 py-3 bg-blue-600 text-white rounded-lg font-medium
                           hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
                           transition-colors"
                >
                    {#if loading}
                        <span class="inline-flex items-center gap-2">
                            <span class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                            {isRegister ? 'Creating account...' : 'Signing in...'}
                        </span>
                    {:else}
                        {isRegister ? 'Create Account' : 'Sign In'}
                    {/if}
                </button>
            </form>
            
            <!-- Toggle Register/Login -->
            <p class="mt-6 text-center text-sm text-gray-400">
                {#if isRegister}
                    Already have an account?
                    <button 
                        on:click={() => { isRegister = false; error = ''; message = ''; }}
                        class="text-blue-400 hover:underline"
                    >
                        Sign in
                    </button>
                {:else}
                    Don't have an account?
                    <button 
                        on:click={() => { isRegister = true; error = ''; message = ''; }}
                        class="text-blue-400 hover:underline"
                    >
                        Create one
                    </button>
                {/if}
            </p>
            
            {#if !isRegister}
                <p class="mt-2 text-center">
                    <a href="/forgot-password" class="text-sm text-gray-500 hover:text-gray-400">
                        Forgot password?
                    </a>
                </p>
            {/if}
        </div>
    </div>
</div>
```

---

## 5. ENVIRONMENT VARIABLES

### Backend (Railway)
```bash
# Google OAuth
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx

# Session
SESSION_SECRET=<64-char-random-string>
SESSION_TTL_DAYS=7

# Email (later - can stub for now)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=xxx
FROM_EMAIL=noreply@cogtwin.dev

# URLs
FRONTEND_URL=https://cogtwin.dev
COOKIE_DOMAIN=.cogtwin.dev
ENV=production
```

### Frontend
```bash
VITE_API_URL=https://api.cogtwin.dev
```

---

## 6. INTEGRATION CHECKLIST

### Backend
- [ ] Create `auth/personal_auth.py`
- [ ] Create `auth/personal_auth_routes.py`
- [ ] Wire router into `main.py`
- [ ] Add startup code for Redis + DB pool
- [ ] Add `argon2-cffi` to requirements.txt
- [ ] Add `aioredis` to requirements.txt (if not present)
- [ ] Set Railway env vars

### Frontend
- [ ] Create `src/lib/stores/personalAuth.ts`
- [ ] Create `src/routes/login/+page.svelte`
- [ ] Create `src/routes/auth/google/callback/+page.svelte`
- [ ] Update root layout to check auth on mount
- [ ] Set Vercel/frontend env vars

### External Setup
- [ ] Create Google OAuth app at console.cloud.google.com
- [ ] Add authorized redirect URIs to Google app
- [ ] Generate SESSION_SECRET (use `openssl rand -base64 48`)

---

## 7. TESTING COMMANDS

```bash
# Register
curl -X POST http://localhost:8000/api/personal/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"testpass123"}' \
  -c cookies.txt

# Login
curl -X POST http://localhost:8000/api/personal/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"testpass123"}' \
  -c cookies.txt

# Get me (with session cookie)
curl http://localhost:8000/api/personal/auth/me \
  -b cookies.txt

# Logout
curl -X POST http://localhost:8000/api/personal/auth/logout \
  -b cookies.txt
```

---

## 8. SDK AGENT EXECUTION BLOCK

```
FEATURE BUILD: PERSONAL_AUTH

PREREQUISITE CHECK:
- Verify Redis is available on Railway (REDIS_URL env var)
- Database migration already applied (confirmed by user)

TASK 1 - Backend Dependencies:
- Add to requirements.txt: argon2-cffi>=21.0.0, aioredis>=2.0.0, httpx>=0.24.0
- pip install the new deps locally

TASK 2 - Backend Files:
- Create file: auth/personal_auth.py [use code block from section 3]
- Create file: auth/personal_auth_routes.py [use code block from section 3]

TASK 3 - Wire into main.py:
- Add import for personal_auth_routes (with try/except)
- Add router registration (only if deployment.mode == 'personal')
- Add startup code for Redis and DB pool

TASK 4 - Frontend Files:
- Create file: frontend/src/lib/stores/personalAuth.ts
- Create file: frontend/src/routes/login/+page.svelte
- Create directory: frontend/src/routes/auth/google/callback/
- Create file: frontend/src/routes/auth/google/callback/+page.svelte

TASK 5 - Verify:
- Backend: Start server, check routes loaded
- Test registration endpoint with curl
- Test login endpoint with curl
- Frontend: npm run dev, check login page renders

COMPLETION CRITERIA:
- All files created without syntax errors
- Backend starts without import errors
- /api/personal/auth/register responds 400 (missing body) not 404
- Login page renders at /login
```

---

## 9. ROLLBACK PLAN

```bash
# Git rollback
git revert HEAD~N  # N = commits for this feature

# Database rollback (only if needed - schema is additive)
ALTER TABLE personal.users 
  DROP COLUMN IF EXISTS password_hash,
  DROP COLUMN IF EXISTS email_verified,
  DROP COLUMN IF EXISTS verification_token,
  DROP COLUMN IF EXISTS verification_expires,
  DROP COLUMN IF EXISTS reset_token,
  DROP COLUMN IF EXISTS reset_expires,
  DROP COLUMN IF EXISTS google_id,
  DROP COLUMN IF EXISTS display_name,
  DROP COLUMN IF EXISTS avatar_url,
  DROP COLUMN IF EXISTS last_login_at,
  DROP COLUMN IF EXISTS is_active;
```

---

## 10. FUTURE ENHANCEMENTS (Not in this build)

1. **Email sending** - Verification and reset emails (stub endpoints exist)
2. **Rate limiting** - Prevent brute force on login
3. **Magic link auth** - Email-only, no password
4. **Account linking UI** - Connect Google to existing email account
5. **Session management UI** - View/revoke active sessions