"""
SSO Routes - Azure AD OAuth2 endpoints

GET  /api/auth/login      - Redirect to Microsoft login
GET  /api/auth/callback   - Handle Microsoft redirect (for SPA, returns JSON)
POST /api/auth/callback   - Exchange code for tokens (called by frontend)
POST /api/auth/refresh    - Refresh tokens
POST /api/auth/logout     - Clear session
GET  /api/auth/me         - Get current user
"""

from fastapi import APIRouter, HTTPException, Depends, Response, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
import secrets
import logging

from azure_auth import (
    is_configured,
    get_auth_url,
    exchange_code_for_tokens,
    refresh_tokens,
    AzureUser,
)
from auth_service import get_auth_service
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    user: dict

class RefreshRequest(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    role: str
    departments: list
    is_super_user: bool
    can_manage_users: bool
    azure_oid: Optional[str] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/config")
async def get_auth_config():
    """
    Return auth configuration for frontend.

    Frontend can use this to know whether to show Microsoft login button.
    """
    return {
        "azure_ad_enabled": is_configured(),
        "login_url": "/api/auth/login" if is_configured() else None,
    }


@router.get("/login")
async def login_redirect():
    """
    Redirect user to Microsoft login page.

    For SPAs, frontend typically handles the redirect itself.
    This endpoint is for traditional server-rendered apps.
    """
    if not is_configured():
        raise HTTPException(503, "Azure AD not configured")

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # TODO: Store state in session/cache for validation on callback
    # For now, frontend handles state validation

    auth_url = get_auth_url(state=state)
    return RedirectResponse(url=auth_url)


@router.get("/login-url")
async def get_login_url(redirect_uri: Optional[str] = None):
    """
    Get Microsoft login URL for frontend redirect.

    Frontend calls this, gets URL, then does window.location = url
    """
    if not is_configured():
        raise HTTPException(503, "Azure AD not configured")

    try:
        state = secrets.token_urlsafe(32)
        auth_url = get_auth_url(state=state)

        return {
            "url": auth_url,
            "state": state,  # Frontend should store this and validate on callback
        }
    except Exception as e:
        logger.error(f"Failed to generate login URL: {e}")
        raise HTTPException(500, f"Failed to generate login URL: {str(e)}")


@router.post("/callback", response_model=TokenResponse)
async def handle_callback(request: CallbackRequest):
    """
    Exchange authorization code for tokens.

    Frontend catches the ?code=xxx from Microsoft redirect,
    then POST it here to exchange for tokens.
    """
    if not is_configured():
        raise HTTPException(503, "Azure AD not configured")

    # TODO: Validate state parameter matches what we stored
    # if request.state != stored_state:
    #     raise HTTPException(400, "Invalid state parameter")

    # Exchange code for tokens
    result = exchange_code_for_tokens(request.code)

    if not result.success:
        logger.error(f"Auth callback failed: {result.error}")
        raise HTTPException(401, result.error_description or result.error)

    azure_user = result.user

    # Provision/update user in our database
    user = await provision_user(azure_user)

    # Calculate expires_in from expires_at
    from datetime import datetime
    now = datetime.utcnow()
    expires_in = int((azure_user.expires_at - now).total_seconds()) if azure_user.expires_at else 3600

    return TokenResponse(
        access_token=azure_user.access_token,
        refresh_token=azure_user.refresh_token,
        expires_in=expires_in,
        user={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "departments": [a.department_slug for a in user.access_list],
            "is_super_user": user.is_super_user,
            "can_manage_users": user.can_manage_users,
        },
    )


@router.post("/refresh", response_model=TokenResponse)
async def handle_refresh(request: RefreshRequest):
    """
    Refresh access token using refresh token.
    """
    if not is_configured():
        raise HTTPException(503, "Azure AD not configured")

    result = refresh_tokens(request.refresh_token)

    if not result.success:
        raise HTTPException(401, result.error_description or "Token refresh failed")

    azure_user = result.user

    # Get user from our database
    auth = get_auth_service()
    user = auth.get_user_by_azure_oid(azure_user.oid)

    if not user:
        raise HTTPException(401, "User not found")

    access_list = auth.get_user_department_access(user)

    from datetime import datetime
    now = datetime.utcnow()
    expires_in = int((azure_user.expires_at - now).total_seconds()) if azure_user.expires_at else 3600

    return TokenResponse(
        access_token=azure_user.access_token,
        refresh_token=azure_user.refresh_token,
        expires_in=expires_in,
        user={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "departments": [a.department_slug for a in access_list],
            "is_super_user": user.is_super_user,
            "can_manage_users": user.can_manage_users,
        },
    )


@router.post("/logout")
async def logout():
    """
    Logout user.

    Note: This only clears our session. To fully logout from Microsoft,
    redirect to: https://login.microsoftonline.com/common/oauth2/v2.0/logout
    """
    # For stateless JWT auth, logout is mostly client-side
    # Could add token to revocation list here if needed
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    # Will add proper token validation dependency
):
    """Get current user info."""
    # TODO: Extract user from token
    raise HTTPException(501, "Not implemented yet")


# =============================================================================
# USER PROVISIONING
# =============================================================================

async def provision_user(azure_user: AzureUser):
    """
    Create or update user in our database from Azure AD info.

    Called on every login to keep user info in sync.
    """
    auth = get_auth_service()

    # Try to find existing user by Azure OID
    user = auth.get_user_by_azure_oid(azure_user.oid)

    if user:
        # Update existing user
        user = auth.update_user_from_azure(
            user_id=user.id,
            email=azure_user.email,
            display_name=azure_user.name,
            azure_oid=azure_user.oid,
        )
    else:
        # Try to find by email (might exist from manual creation)
        user = auth.get_user_by_email(azure_user.email)

        if user:
            # Link existing user to Azure
            user = auth.link_user_to_azure(user.id, azure_user.oid)
        else:
            # Create new user
            user = auth.create_user_from_azure(
                email=azure_user.email,
                display_name=azure_user.name,
                azure_oid=azure_user.oid,
            )

    # Get department access
    access_list = auth.get_user_department_access(user)
    user.access_list = access_list

    return user
