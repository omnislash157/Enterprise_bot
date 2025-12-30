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
