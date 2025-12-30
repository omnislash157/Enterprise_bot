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
