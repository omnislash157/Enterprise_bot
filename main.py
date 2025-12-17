"""
Enterprise Bot Backend - Driscoll Foods
Clean fork with CogTwin dependencies removed.

This is a "dumb bot" that stuffs manuals into context window.
No memory pipelines, no FAISS, no embeddings.

Version: 1.0.0 (Enterprise Fork)
"""
from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
from datetime import datetime
import asyncio
import json
import os
import logging
import time
from pathlib import Path
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIG - Load settings from environment or defaults
# =============================================================================

class Settings:
    app_name: str = "Driscoll Enterprise Bot"
    cors_origins: list = ["*"]  # Railway will handle CORS
    data_dir: Path = Path("./data")

    # Email whitelist - loaded from JSON or env
    email_whitelist_path: str = os.getenv("EMAIL_WHITELIST_PATH", "./email_whitelist.json")
    allowed_domains: list = ["driscollfoods.com", "gmail.com"]  # Fallback

settings = Settings()

# =============================================================================
# ENTERPRISE IMPORTS - No CogTwin!
# =============================================================================

try:
    from config_loader import (
        load_config,
        cfg,
        memory_enabled,
        is_enterprise_mode,
        get_ui_features,
    )
    from enterprise_twin import EnterpriseTwin
    from enterprise_tenant import TenantContext
    CONFIG_LOADED = True
except ImportError as e:
    logger.error(f"Failed to import enterprise modules: {e}")
    CONFIG_LOADED = False

# Auth imports
try:
    from auth_service import get_auth_service, authenticate_user
    AUTH_LOADED = True
except ImportError as e:
    logger.warning(f"Auth service not loaded: {e}")
    AUTH_LOADED = False

# Tenant service import
try:
    from tenant_service import get_tenant_service
    TENANT_SERVICE_LOADED = True
except ImportError as e:
    logger.warning(f"Tenant service not loaded: {e}")
    TENANT_SERVICE_LOADED = False

# Admin routes import
try:
    from admin_routes import admin_router
    ADMIN_ROUTES_LOADED = True
except ImportError as e:
    logger.warning(f"Admin routes not loaded: {e}")
    ADMIN_ROUTES_LOADED = False

# Analytics service import
try:
    from analytics_service import get_analytics_service
    from analytics_routes import analytics_router
    ANALYTICS_LOADED = True
except ImportError as e:
    logger.warning(f"Analytics service not loaded: {e}")
    ANALYTICS_LOADED = False

# SSO routes import
try:
    from sso_routes import router as sso_router
    SSO_ROUTES_LOADED = True
except ImportError as e:
    logger.warning(f"SSO routes not loaded: {e}")
    SSO_ROUTES_LOADED = False

# Azure auth import
try:
    from azure_auth import validate_access_token, is_configured as azure_configured
    AZURE_AUTH_LOADED = True
except ImportError as e:
    logger.warning(f"Azure auth not loaded: {e}")
    AZURE_AUTH_LOADED = False

# =============================================================================
# AUTH DEPENDENCIES
# =============================================================================

async def get_current_user(
    authorization: str = Header(None, alias="Authorization"),
    x_user_email: str = Header(None, alias="X-User-Email")
) -> Optional[dict]:
    """
    FastAPI dependency to get current user from Azure AD token or email header.
    Returns None if no auth header (allows optional auth).
    Raises 401 if header present but user not found/allowed.
    """
    # Try Azure AD token first (Bearer token)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]

        if AZURE_AUTH_LOADED and azure_configured():
            # Validate against Microsoft Graph
            graph_user = validate_access_token(token)

            if graph_user:
                # Look up in our DB
                auth = get_auth_service()
                user = auth.get_user_by_azure_oid(graph_user.get("id"))

                if user:
                    access_list = auth.get_user_department_access(user)
                    return {
                        "id": user.id,
                        "email": user.email,
                        "display_name": user.display_name,
                        "role": user.role,
                        "tier": user.tier.name,
                        "employee_id": user.employee_id,
                        "primary_department": user.primary_department_slug,
                        "departments": [a.department_slug for a in access_list],
                        "is_super_user": user.is_super_user,
                        "can_manage_users": user.can_manage_users,
                        "auth_method": "azure_ad",
                    }

        raise HTTPException(401, "Invalid or expired token")

    # Legacy email header fallback
    if x_user_email:
        if not AUTH_LOADED:
            # Fallback to whitelist check only
            if email_whitelist.verify(x_user_email):
                return {"email": x_user_email, "role": "user", "fallback": True}
            raise HTTPException(401, "Email not authorized")

        auth = get_auth_service()
        user = auth.get_or_create_user(x_user_email)

        if not user:
            raise HTTPException(401, "Email domain not authorized")

        # Get department access
        access_list = auth.get_user_department_access(user)

        return {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "tier": user.tier.name,
            "employee_id": user.employee_id,
            "primary_department": user.primary_department_slug,
            "departments": [a.department_slug for a in access_list],
            "is_super_user": user.is_super_user,
            "can_manage_users": user.can_manage_users,
            "auth_method": "legacy_email",
        }

    return None


async def require_auth(
    user: dict = Depends(get_current_user)
) -> dict:
    """Dependency that REQUIRES authentication (raises 401 if not present)."""
    if not user:
        raise HTTPException(401, "Authentication required. Send X-User-Email header.")
    return user


async def require_admin(
    user: dict = Depends(require_auth)
) -> dict:
    """Dependency that requires dept_head or super_user role."""
    if not user.get("can_manage_users"):
        raise HTTPException(403, "Admin access required")
    return user

# =============================================================================
# EMAIL WHITELIST VERIFICATION
# =============================================================================

class EmailWhitelist:
    """Simple email whitelist manager."""

    def __init__(self):
        self._whitelist: set = set()
        self._allowed_domains: list = []
        self._loaded = False

    def load(self, path: str = None):
        """Load whitelist from JSON file."""
        path = path or settings.email_whitelist_path

        try:
            if Path(path).exists():
                with open(path) as f:
                    data = json.load(f)
                    self._whitelist = set(data.get("emails", []))
                    self._allowed_domains = data.get("allowed_domains", settings.allowed_domains)
                    logger.info(f"Loaded {len(self._whitelist)} whitelisted emails, {len(self._allowed_domains)} domains")
            else:
                # Use config fallback
                self._allowed_domains = cfg("tenant.allowed_domains", settings.allowed_domains)
                logger.info(f"No whitelist file, using config domains: {self._allowed_domains}")
        except Exception as e:
            logger.error(f"Error loading whitelist: {e}")
            self._allowed_domains = settings.allowed_domains

        self._loaded = True

    def verify(self, email: str) -> bool:
        """Check if email is allowed."""
        if not self._loaded:
            self.load()

        email_lower = email.lower().strip()

        # Check exact match first
        if email_lower in self._whitelist:
            return True

        # Check domain
        if "@" in email_lower:
            domain = email_lower.split("@")[1]
            if domain in self._allowed_domains:
                return True

        return False

    def add_email(self, email: str):
        """Add email to whitelist (runtime only, not persisted)."""
        self._whitelist.add(email.lower().strip())

    def get_stats(self) -> dict:
        """Get whitelist stats."""
        return {
            "whitelisted_emails": len(self._whitelist),
            "allowed_domains": self._allowed_domains,
        }

email_whitelist = EmailWhitelist()

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class VerifyEmailRequest(BaseModel):
    email: str

class VerifyEmailResponse(BaseModel):
    email: str
    allowed: bool
    domain: Optional[str] = None

# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Response-Time"],
)

# Gzip compression for responses > 500 bytes
app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    """Add X-Response-Time header to all responses for performance tracking."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"
    return response

# Include admin router
if ADMIN_ROUTES_LOADED:
    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
    logger.info("[STARTUP] Admin routes loaded at /api/admin")

# Include analytics router
if ANALYTICS_LOADED:
    app.include_router(analytics_router, prefix="/api/admin/analytics", tags=["analytics"])
    logger.info("[STARTUP] Analytics routes loaded at /api/admin/analytics")

# Include SSO router
if SSO_ROUTES_LOADED:
    app.include_router(sso_router)
    logger.info("[STARTUP] SSO routes loaded at /api/auth")

# Global engine instance
engine: Optional[EnterpriseTwin] = None

# =============================================================================
# STARTUP
# =============================================================================

@app.on_event("startup")
async def startup_event():
    global engine

    if not CONFIG_LOADED:
        logger.error("Enterprise modules not loaded, cannot start")
        return

    # Load config
    load_config()

    # Load email whitelist
    email_whitelist.load()

    # Initialize enterprise twin (always enterprise mode in this fork)
    logger.info("[STARTUP] Initializing EnterpriseTwin...")
    engine = EnterpriseTwin()
    await engine.start()

    logger.info(f"[STARTUP] EnterpriseTwin ready")
    logger.info(f"  Memory mode: {engine._memory_mode}")
    logger.info(f"  Context stuffing: {engine._context_stuffing_mode}")
    logger.info(f"  Model: {engine.model}")

# =============================================================================
# HEALTH + CONFIG ENDPOINTS
# =============================================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "timestamp": datetime.utcnow().isoformat(),
        "engine_ready": engine is not None,
    }

@app.get("/")
async def root():
    return {
        "message": "Driscoll Enterprise Bot",
        "docs": "/docs",
        "health": "/health",
        "websocket": "/ws/{session_id}",
        "verify": "/api/verify-email",
    }

@app.get("/api/config")
async def get_client_config():
    """Return UI feature flags to frontend."""
    if not CONFIG_LOADED:
        return {
            "features": {"chat_basic": True, "dark_mode": True},
            "tier": "basic",
            "mode": "enterprise",
            "memory_enabled": False,
        }

    return {
        "features": get_ui_features(),
        "tier": cfg("deployment.tier", "basic"),
        "mode": cfg("deployment.mode", "enterprise"),
        "memory_enabled": memory_enabled(),
    }

# =============================================================================
# EMAIL VERIFICATION ENDPOINT
# =============================================================================

@app.post("/api/verify-email", response_model=VerifyEmailResponse)
async def verify_email(request: VerifyEmailRequest):
    """Verify if an email is allowed to access the system."""
    email = request.email.lower().strip()
    allowed = email_whitelist.verify(email)

    domain = None
    if "@" in email:
        domain = email.split("@")[1]

    return VerifyEmailResponse(
        email=email,
        allowed=allowed,
        domain=domain,
    )

@app.get("/api/whitelist/stats")
async def get_whitelist_stats():
    """Get whitelist statistics (admin endpoint)."""
    return email_whitelist.get_stats()

# =============================================================================
# AUTH ENDPOINTS
# =============================================================================

@app.get("/api/whoami")
async def whoami(user: dict = Depends(get_current_user)):
    """Return current user's identity and permissions."""
    if not user:
        return {"authenticated": False, "message": "No auth header provided"}

    return {
        "authenticated": True,
        "user": user,
    }


@app.get("/api/admin/users")
async def list_users(
    department: str = None,
    user: dict = Depends(require_admin)
):
    """List users. Dept heads see their dept, super users see all."""
    auth = get_auth_service()

    # Get the actual User object for auth operations
    actor = auth.get_user_by_email(user["email"])

    try:
        if user["is_super_user"] and not department:
            users = auth.list_all_users(actor)
        elif department:
            users = auth.list_users_in_department(actor, department)
        elif user["primary_department"]:
            users = auth.list_users_in_department(actor, user["primary_department"])
        else:
            users = []

        return {"users": users, "count": len(users)}
    except PermissionError as e:
        raise HTTPException(403, str(e))


@app.get("/api/departments")
async def list_departments(user: dict = Depends(get_current_user)):
    """
    List departments.
    - Authenticated users see their accessible departments
    - Unauthenticated see all (for login UI dropdown)
    """
    if not TENANT_SERVICE_LOADED:
        raise HTTPException(503, "Tenant service not loaded")

    tenant_svc = get_tenant_service()
    all_depts = tenant_svc.list_departments()

    if user and not user.get("is_super_user"):
        # Filter to user's accessible departments
        accessible = set(user.get("departments", []))
        all_depts = [d for d in all_depts if d.slug in accessible]

    return {
        "departments": [
            {"slug": d.slug, "name": d.name, "description": d.description}
            for d in all_depts
        ]
    }


@app.get("/api/content")
async def get_department_content(
    department: str = None,
    user: dict = Depends(require_auth)
):
    """
    Get department content for context stuffing.
    - Regular users: Only their accessible departments
    - Super users: Can request any department or all
    """
    if not TENANT_SERVICE_LOADED:
        raise HTTPException(503, "Tenant service not loaded")

    tenant_svc = get_tenant_service()

    # Validate department access
    if department:
        if not user["is_super_user"] and department not in user["departments"]:
            raise HTTPException(403, f"No access to department: {department}")
        content = tenant_svc.get_all_content_for_context(department)
    else:
        # No department specified
        if user["is_super_user"]:
            # Super users get everything
            content = tenant_svc.get_all_content_for_context(None)
        elif user["departments"]:
            # Regular users get their primary or first accessible dept
            dept = user["primary_department"] or user["departments"][0]
            content = tenant_svc.get_all_content_for_context(dept)
        else:
            content = ""

    return {
        "department": department,
        "content_length": len(content),
        "content": content,
    }

# =============================================================================
# ANALYTICS ENDPOINTS (Stubbed for Enterprise)
# =============================================================================

@app.get("/api/analytics")
async def get_analytics():
    """Session analytics - simplified for enterprise mode."""
    if engine is None:
        raise HTTPException(503, "Engine not initialized")

    return engine.get_session_stats()

@app.get("/api/analytics/cognitive-state")
async def get_cognitive_state():
    """Cognitive state - stubbed for enterprise."""
    return {
        "phase": "ready",
        "temperature": 0.5,
        "mode": "enterprise",
        "message": "Full cognitive analytics available in Pro tier",
    }

@app.get("/api/analytics/health-check")
async def get_health_check():
    """Health check - simplified for enterprise."""
    return {
        "status": "healthy",
        "engine_ready": engine is not None,
        "tier": cfg("deployment.tier", "basic") if CONFIG_LOADED else "basic",
    }

@app.get("/api/analytics/session-stats")
async def get_session_stats():
    """Get session statistics."""
    if engine is None:
        raise HTTPException(503, "Engine not initialized")

    return engine.get_session_stats()

# =============================================================================
# WEBSOCKET CONNECTION MANAGER
# =============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"[WS] Session {session_id} connected. Active: {len(self.active_connections)}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"[WS] Session {session_id} disconnected. Active: {len(self.active_connections)}")

    async def send_json(self, session_id: str, data: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(data)

manager = ConnectionManager()

# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)

    # Default tenant - verification is OPTIONAL for demo
    # If verify message comes, we use that email
    # If not, we use default tenant (warehouse division)
    user_email = "demo@driscollfoods.com"  # Default for unverified sessions
    tenant = TenantContext(
        tenant_id="driscoll",
        division=cfg("tenant.default_division", "warehouse") if CONFIG_LOADED else "warehouse",
        zone=None,
        role="user",
    )

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "verify":
                email = data.get("email", "")

                if AUTH_LOADED and email:
                    auth = get_auth_service()
                    user = auth.get_or_create_user(email)

                    if user:
                        user_email = email
                        # Get user's departments
                        access_list = auth.get_user_department_access(user)
                        dept_slugs = [a.department_slug for a in access_list]

                        # Use requested division if user has access, else primary
                        requested_division = data.get("division", user.primary_department_slug or "warehouse")
                        if requested_division not in dept_slugs and not user.is_super_user:
                            requested_division = user.primary_department_slug or (dept_slugs[0] if dept_slugs else "warehouse")

                        tenant = TenantContext(
                            tenant_id="driscoll",
                            division=requested_division,
                            zone=None,
                            role=user.role,
                            email=email,
                        )

                        auth.record_login(user)  # Track login

                        # Log login event to analytics
                        if ANALYTICS_LOADED:
                            try:
                                analytics = get_analytics_service()
                                analytics.log_event(
                                    event_type="login",
                                    user_email=email,
                                    department=tenant.division,
                                    session_id=session_id,
                                    user_id=str(user.id) if hasattr(user, 'id') else None
                                )
                            except Exception as ae:
                                logger.warning(f"Failed to log login event: {ae}")

                        await websocket.send_json({
                            "type": "verified",
                            "email": email,
                            "division": tenant.division,
                            "role": user.role,
                            "departments": dept_slugs,
                        })
                    else:
                        # Domain not allowed
                        await websocket.send_json({
                            "type": "error",
                            "message": "Email domain not authorized",
                        })
                elif email:
                    # Fallback to old whitelist behavior
                    if email_whitelist.verify(email):
                        user_email = email
                        tenant = TenantContext(
                            tenant_id="driscoll",
                            division=data.get("division", tenant.division),
                            zone=None,
                            role="user",
                            email=email,
                        )
                        await websocket.send_json({
                            "type": "verified",
                            "email": email,
                            "division": tenant.division,
                        })
                    else:
                        logger.warning(f"Email not in whitelist: {email}")
                        await websocket.send_json({
                            "type": "verified",
                            "email": email,
                            "division": tenant.division,
                            "warning": "Email not in whitelist, using demo mode",
                        })

            elif msg_type == "message":
                content = data.get("content", "")

                if engine is None:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Engine not initialized",
                    })
                    continue

                # Stream response (no verification required for demo)
                response_text = ""
                async for chunk in engine.think(content, tenant=tenant):
                    if isinstance(chunk, str) and chunk:
                        response_text += chunk
                        await websocket.send_json({
                            "type": "stream_chunk",
                            "content": chunk,
                            "done": False,
                        })

                # Send done signal
                await websocket.send_json({
                    "type": "stream_chunk",
                    "content": "",
                    "done": True,
                })

                # Send session stats (compatible with frontend's cognitive_state)
                stats = engine.get_session_stats()
                await websocket.send_json({
                    "type": "cognitive_state",
                    "phase": "ready",
                    "temperature": 0.5,
                    **stats,
                })

            elif msg_type == "set_division":
                # Allow changing division mid-session
                new_division = data.get("division", "warehouse")
                old_division = tenant.division  # Capture before change

                tenant = TenantContext(
                    tenant_id=tenant.tenant_id,
                    division=new_division,
                    zone=tenant.zone,
                    role=tenant.role,
                    email=tenant.email,
                )

                # Log department switch event
                if ANALYTICS_LOADED and old_division != new_division:
                    try:
                        analytics = get_analytics_service()
                        analytics.log_event(
                            event_type="dept_switch",
                            user_email=tenant.email or user_email,
                            session_id=session_id,
                            from_department=old_division,
                            to_department=new_division
                        )
                    except Exception as ae:
                        logger.warning(f"Failed to log dept_switch event: {ae}")

                await websocket.send_json({
                    "type": "division_changed",
                    "division": new_division,
                })

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"[WS] Error in session {session_id}: {e}")

        # Log error event to analytics
        if ANALYTICS_LOADED:
            try:
                analytics = get_analytics_service()
                analytics.log_event(
                    event_type="error",
                    user_email=user_email,
                    session_id=session_id,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
            except:
                pass  # Don't let analytics errors crash the handler

        manager.disconnect(session_id)


# =============================================================================
# RUN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
