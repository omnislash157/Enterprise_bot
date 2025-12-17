"""
Azure AD Authentication Service

Handles:
- OAuth2 authorization URL generation
- Token exchange (auth code → tokens)
- ID token validation
- User info extraction from claims
- Access token refresh

Uses MSAL (Microsoft Authentication Library) for the heavy lifting.
"""

import os
import msal
import jwt
import requests
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

AZURE_AD_TENANT_ID = os.getenv("AZURE_AD_TENANT_ID")
AZURE_AD_CLIENT_ID = os.getenv("AZURE_AD_CLIENT_ID")
AZURE_AD_CLIENT_SECRET = os.getenv("AZURE_AD_CLIENT_SECRET")
AZURE_AD_REDIRECT_URI = os.getenv("AZURE_AD_REDIRECT_URI", "http://localhost:5173/auth/callback")

# Microsoft endpoints
AUTHORITY = f"https://login.microsoftonline.com/{AZURE_AD_TENANT_ID}"
GRAPH_API = "https://graph.microsoft.com/v1.0"

# Scopes we request
SCOPES = [
    "openid",           # Required for OIDC
    "profile",          # Get user profile info
    "email",            # Get email address
    "offline_access",   # Get refresh token
    "User.Read",        # Read user's own profile from Graph API
]


def is_configured() -> bool:
    """Check if Azure AD is configured."""
    return all([
        AZURE_AD_TENANT_ID,
        AZURE_AD_CLIENT_ID,
        AZURE_AD_CLIENT_SECRET,
    ])


# =============================================================================
# MSAL CLIENT
# =============================================================================

@lru_cache(maxsize=1)
def get_msal_app() -> msal.ConfidentialClientApplication:
    """
    Get MSAL confidential client application.

    Cached because MSAL maintains token cache internally.
    """
    if not is_configured():
        raise RuntimeError("Azure AD not configured - check environment variables")

    return msal.ConfidentialClientApplication(
        client_id=AZURE_AD_CLIENT_ID,
        client_credential=AZURE_AD_CLIENT_SECRET,
        authority=AUTHORITY,
    )


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AzureUser:
    """User info extracted from Azure AD tokens/claims."""
    oid: str                    # Object ID (Azure's user ID)
    email: str
    name: str
    preferred_username: str     # Usually email or UPN
    tenant_id: str
    groups: list = None         # If group claims configured

    # Raw tokens for API calls
    access_token: str = None
    refresh_token: str = None
    id_token: str = None
    expires_at: datetime = None


@dataclass
class AuthResult:
    """Result of authentication flow."""
    success: bool
    user: Optional[AzureUser] = None
    error: Optional[str] = None
    error_description: Optional[str] = None


# =============================================================================
# AUTHORIZATION FLOW
# =============================================================================

def get_auth_url(state: str = None) -> str:
    """
    Generate the Microsoft login URL.

    Args:
        state: Optional state parameter for CSRF protection
               (should be random string stored in session)

    Returns:
        Full URL to redirect user to Microsoft login
    """
    app = get_msal_app()

    auth_url = app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=AZURE_AD_REDIRECT_URI,
        state=state,
    )

    return auth_url


def exchange_code_for_tokens(code: str) -> AuthResult:
    """
    Exchange authorization code for tokens.

    This is called after Microsoft redirects back with ?code=xxx

    Args:
        code: The authorization code from Microsoft

    Returns:
        AuthResult with user info or error
    """
    app = get_msal_app()

    try:
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=SCOPES,
            redirect_uri=AZURE_AD_REDIRECT_URI,
        )
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return AuthResult(
            success=False,
            error="token_exchange_failed",
            error_description=str(e),
        )

    # Check for errors
    if "error" in result:
        logger.error(f"Azure AD error: {result.get('error_description')}")
        return AuthResult(
            success=False,
            error=result.get("error"),
            error_description=result.get("error_description"),
        )

    # Extract user info from ID token claims
    id_token_claims = result.get("id_token_claims", {})

    # Calculate token expiry
    expires_in = result.get("expires_in", 3600)
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    user = AzureUser(
        oid=id_token_claims.get("oid"),
        email=id_token_claims.get("email") or id_token_claims.get("preferred_username"),
        name=id_token_claims.get("name", ""),
        preferred_username=id_token_claims.get("preferred_username", ""),
        tenant_id=id_token_claims.get("tid"),
        groups=id_token_claims.get("groups", []),
        access_token=result.get("access_token"),
        refresh_token=result.get("refresh_token"),
        id_token=result.get("id_token"),
        expires_at=expires_at,
    )

    logger.info(f"Azure AD login successful: {user.email}")

    return AuthResult(success=True, user=user)


def refresh_tokens(refresh_token: str) -> AuthResult:
    """
    Refresh access token using refresh token.

    Args:
        refresh_token: The refresh token from previous auth

    Returns:
        AuthResult with new tokens or error
    """
    app = get_msal_app()

    try:
        result = app.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=SCOPES,
        )
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        return AuthResult(
            success=False,
            error="refresh_failed",
            error_description=str(e),
        )

    if "error" in result:
        return AuthResult(
            success=False,
            error=result.get("error"),
            error_description=result.get("error_description"),
        )

    id_token_claims = result.get("id_token_claims", {})
    expires_in = result.get("expires_in", 3600)
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    user = AzureUser(
        oid=id_token_claims.get("oid"),
        email=id_token_claims.get("email") or id_token_claims.get("preferred_username"),
        name=id_token_claims.get("name", ""),
        preferred_username=id_token_claims.get("preferred_username", ""),
        tenant_id=id_token_claims.get("tid"),
        groups=id_token_claims.get("groups", []),
        access_token=result.get("access_token"),
        refresh_token=result.get("refresh_token", refresh_token),  # May not return new one
        id_token=result.get("id_token"),
        expires_at=expires_at,
    )

    return AuthResult(success=True, user=user)


# =============================================================================
# TOKEN VALIDATION (for API requests)
# =============================================================================

# Microsoft's public keys for token validation
JWKS_URL = f"https://login.microsoftonline.com/{AZURE_AD_TENANT_ID}/discovery/v2.0/keys"

@lru_cache(maxsize=1)
def get_microsoft_public_keys() -> Dict[str, Any]:
    """Fetch Microsoft's public keys for JWT validation."""
    response = requests.get(JWKS_URL)
    response.raise_for_status()
    return response.json()


def validate_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate a Microsoft access token.

    Note: Microsoft access tokens are opaque by default.
    For full validation, you may need to call /me endpoint instead.

    For ID tokens, use validate_id_token() instead.
    """
    # For access tokens, simplest approach is to call Graph API
    # If token is valid, we get user info. If not, we get 401.
    try:
        response = requests.get(
            f"{GRAPH_API}/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def validate_id_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate a Microsoft ID token (JWT).

    Returns decoded claims if valid, None if invalid.
    """
    try:
        # Get public keys
        jwks = get_microsoft_public_keys()

        # Decode header to get key ID
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        # Find matching key
        key = None
        for k in jwks.get("keys", []):
            if k.get("kid") == kid:
                key = jwt.algorithms.RSAAlgorithm.from_jwk(k)
                break

        if not key:
            logger.error("No matching key found for token")
            return None

        # Validate token
        claims = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=AZURE_AD_CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{AZURE_AD_TENANT_ID}/v2.0",
        )

        return claims

    except jwt.ExpiredSignatureError:
        logger.warning("ID token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid ID token: {e}")
        return None


# =============================================================================
# GRAPH API HELPERS
# =============================================================================

def get_user_photo(access_token: str) -> Optional[bytes]:
    """Fetch user's profile photo from Graph API."""
    try:
        response = requests.get(
            f"{GRAPH_API}/me/photo/$value",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code == 200:
            return response.content
        return None
    except Exception:
        return None


def get_user_groups(access_token: str) -> list:
    """Fetch user's group memberships from Graph API."""
    try:
        response = requests.get(
            f"{GRAPH_API}/me/memberOf",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code == 200:
            data = response.json()
            return [
                g.get("displayName")
                for g in data.get("value", [])
                if g.get("@odata.type") == "#microsoft.graph.group"
            ]
        return []
    except Exception:
        return []
