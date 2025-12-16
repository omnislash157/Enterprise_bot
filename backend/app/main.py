"""
Enterprise Bot Backend - Driscoll Foods
Clean fork with CogTwin dependencies removed.

This is a "dumb bot" that stuffs manuals into context window.
No memory pipelines, no FAISS, no embeddings.

Version: 1.0.0 (Enterprise Fork)
"""

import sys
from pathlib import Path

# Add project root to path so we can import root-level modules
# (config_loader, enterprise_twin, enterprise_tenant)
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import asyncio
import json
import os
import logging
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
    from tenant_service import get_driscoll_content
    CONFIG_LOADED = True
except ImportError as e:
    logger.error(f"Failed to import enterprise modules: {e}")
    CONFIG_LOADED = False
    get_driscoll_content = None

# =============================================================================
# AUTH IMPORTS - Supabase 3-Tier System
# =============================================================================

try:
    from tenant_service_v2 import (
        get_user_context,
        get_tenant_service,
        UserContext,
        PermissionTier,
    )
    AUTH_ENABLED = True
    logger.info("[AUTH] tenant_service_v2 loaded successfully")
except ImportError as e:
    logger.warning(f"[AUTH] tenant_service_v2 not available: {e}")
    AUTH_ENABLED = False
    UserContext = None
    PermissionTier = None

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
)

# Global engine instance (type hint as string to avoid import-time errors)
engine: Optional["EnterpriseTwin"] = None

# =============================================================================
# AUTH DEPENDENCY
# =============================================================================

async def get_auth_context(
    authorization: str = Header(None),
    x_tenant_slug: str = Header(None, alias="X-Tenant-Slug")
) -> Optional["UserContext"]:
    """
    FastAPI dependency to get authenticated user context.
    Returns None if auth is disabled or token is invalid (for graceful fallback).
    Raise HTTPException for strict auth enforcement.
    """
    if not AUTH_ENABLED:
        return None

    if not authorization:
        return None

    try:
        ctx = await get_user_context(authorization, x_tenant_slug)
        return ctx
    except PermissionError as e:
        logger.warning(f"[AUTH] Permission denied: {e}")
        return None
    except Exception as e:
        logger.error(f"[AUTH] Error getting user context: {e}")
        return None


async def require_auth(
    authorization: str = Header(...),
    x_tenant_slug: str = Header(None, alias="X-Tenant-Slug")
) -> "UserContext":
    """
    FastAPI dependency that REQUIRES authentication.
    Use this for protected endpoints.
    """
    if not AUTH_ENABLED:
        raise HTTPException(503, "Authentication system not available")

    if not authorization:
        raise HTTPException(401, "Authorization header required")

    try:
        ctx = await get_user_context(authorization, x_tenant_slug)
        return ctx
    except PermissionError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        logger.error(f"[AUTH] Error: {e}")
        raise HTTPException(500, "Authentication error")

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
async def get_client_config(ctx: Optional["UserContext"] = Depends(get_auth_context)):
    """Return UI feature flags to frontend, with user context if authenticated."""
    base_config = {
        "features": {"chat_basic": True, "dark_mode": True},
        "tier": "basic",
        "mode": "enterprise",
        "memory_enabled": False,
        "auth_enabled": AUTH_ENABLED,
    }

    if CONFIG_LOADED:
        base_config.update({
            "features": get_ui_features(),
            "tier": cfg("deployment.tier", "basic"),
            "mode": cfg("deployment.mode", "enterprise"),
            "memory_enabled": memory_enabled(),
        })

    # Add user context if authenticated
    if ctx:
        base_config["user"] = {
            "email": ctx.user.email,
            "tier": ctx.tier.name if ctx.tier else "USER",
            "department": ctx.department.slug if ctx.department else None,
            "tenant": ctx.tenant.slug if ctx.tenant else None,
        }
        base_config["features"].update({
            "credit_lookup": ctx.has_feature("credit_lookup"),
            "credit_pipeline": ctx.has_feature("credit_pipeline"),
            "admin_portal": ctx.can_access_admin_portal,
        })

    return base_config

# =============================================================================
# AUTH ENDPOINTS
# =============================================================================

@app.get("/api/whoami")
async def whoami(ctx: "UserContext" = Depends(require_auth)):
    """Debug endpoint to check current user context."""
    return {
        "user": {
            "id": ctx.user.id,
            "email": ctx.user.email,
        },
        "tenant": {
            "id": ctx.tenant.id,
            "slug": ctx.tenant.slug,
            "name": ctx.tenant.name,
        } if ctx.tenant else None,
        "department": {
            "id": ctx.department.id,
            "slug": ctx.department.slug,
            "name": ctx.department.name,
        } if ctx.department else None,
        "tier": ctx.tier.name if ctx.tier else "USER",
        "role": ctx.role,
        "employee_id": ctx.employee_id,
        "permissions": {
            "can_view_all_department_data": ctx.can_view_all_department_data,
            "can_manage_department_users": ctx.can_manage_department_users,
            "can_manage_all_users": ctx.can_manage_all_users,
            "can_access_admin_portal": ctx.can_access_admin_portal,
        },
        "data_filter": ctx.get_data_filter(),
        "context_content_count": len(ctx.context_content),
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
# ADMIN PORTAL ENDPOINTS
# =============================================================================

class AddUserRequest(BaseModel):
    email: str
    department_slug: str
    role: str = "user"
    employee_id: Optional[str] = None

class RemoveUserRequest(BaseModel):
    email: str

class UpdateRoleRequest(BaseModel):
    email: str
    new_role: str


@app.get("/api/admin/users")
async def list_users(
    ctx: "UserContext" = Depends(require_auth),
    department: Optional[str] = None
):
    """
    List users in tenant.
    - Dept heads: see only their department's users
    - Super users: see all users, optionally filter by department
    """
    if not ctx.can_manage_department_users:
        raise HTTPException(403, "Insufficient permissions")

    svc = get_tenant_service()
    try:
        users = await svc.list_tenant_users(ctx, department_slug=department)
        return {"users": users, "count": len(users)}
    except PermissionError as e:
        raise HTTPException(403, str(e))


@app.get("/api/admin/departments")
async def list_departments(ctx: "UserContext" = Depends(require_auth)):
    """
    List departments in tenant.
    - Dept heads: see only their department
    - Super users: see all departments
    """
    if not ctx.can_manage_department_users:
        raise HTTPException(403, "Insufficient permissions")

    svc = get_tenant_service()

    if ctx.is_super_user:
        # Super users see all departments
        response = svc.supabase.table("tenant_departments").select(
            "id, slug, name"
        ).eq("tenant_id", ctx.tenant.id).execute()
        departments = response.data
    else:
        # Dept heads see only their department
        departments = [{"id": ctx.department.id, "slug": ctx.department.slug, "name": ctx.department.name}] if ctx.department else []

    return {"departments": departments}


@app.post("/api/admin/users")
async def add_user(
    request: AddUserRequest,
    ctx: "UserContext" = Depends(require_auth)
):
    """
    Add a user to the tenant.
    - Super users: can add to any department with any role
    - Dept heads: can add to their department only, role='user' only, @driscollfoods.com only
    """
    if not ctx.can_manage_department_users:
        raise HTTPException(403, "Insufficient permissions")

    svc = get_tenant_service()
    try:
        await svc.add_user_to_tenant(
            ctx,
            user_email=request.email,
            department_slug=request.department_slug,
            role=request.role,
            employee_id=request.employee_id,
        )
        return {"success": True, "message": f"Added {request.email} to {request.department_slug}"}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/admin/users")
async def remove_user(
    request: RemoveUserRequest,
    ctx: "UserContext" = Depends(require_auth)
):
    """
    Remove a user from the tenant.
    - Super users: can remove anyone
    - Dept heads: can remove users from their department (not dept_heads/admins)
    """
    if not ctx.can_manage_department_users:
        raise HTTPException(403, "Insufficient permissions")

    svc = get_tenant_service()
    try:
        await svc.remove_user_from_tenant(ctx, user_email=request.email)
        return {"success": True, "message": f"Removed {request.email}"}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.patch("/api/admin/users/role")
async def update_user_role(
    request: UpdateRoleRequest,
    ctx: "UserContext" = Depends(require_auth)
):
    """
    Update a user's role. Super users only.
    Valid roles: 'user', 'dept_head', 'super_user'
    """
    if not ctx.can_manage_all_users:
        raise HTTPException(403, "Only super users can change roles")

    svc = get_tenant_service()
    try:
        await svc.update_user_role(ctx, user_email=request.email, new_role=request.new_role)
        return {"success": True, "message": f"Updated {request.email} to {request.new_role}"}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


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

    # Track authenticated user context (if they send auth token)
    user_context: Optional["UserContext"] = None

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

            elif msg_type == "auth":
                # Authenticate via Supabase JWT and load context_content
                if not AUTH_ENABLED:
                    await websocket.send_json({
                        "type": "auth_error",
                        "message": "Authentication system not available",
                    })
                    continue

                token = data.get("token", "")
                tenant_slug = data.get("tenant_slug")

                try:
                    user_context = await get_user_context(f"Bearer {token}", tenant_slug)
                    user_email = user_context.user.email

                    # Update tenant context with auth info
                    tenant = TenantContext(
                        tenant_id=user_context.tenant.slug if user_context.tenant else "driscoll",
                        division=user_context.department.slug if user_context.department else tenant.division,
                        zone=None,
                        role=user_context.role,
                        email=user_email,
                    )

                    await websocket.send_json({
                        "type": "authenticated",
                        "email": user_email,
                        "division": tenant.division,
                        "tier": user_context.tier.name if user_context.tier else "USER",
                        "context_docs_count": len(user_context.context_content),
                    })
                    logger.info(f"[WS] Authenticated: {user_email}, {len(user_context.context_content)} context docs")
                except PermissionError as e:
                    await websocket.send_json({
                        "type": "auth_error",
                        "message": str(e),
                    })
                except Exception as e:
                    logger.error(f"[WS] Auth error: {e}")
                    await websocket.send_json({
                        "type": "auth_error",
                        "message": "Authentication failed",
                    })

            elif msg_type == "verify":
                # Optional email verification handshake
                email = data.get("email", "")
                if email and email_whitelist.verify(email):
                    user_email = email
                    # Update tenant context with verified email
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
                elif email:
                    # Email provided but not in whitelist - warn but allow demo
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

                # Get context_content from authenticated user OR fall back to Driscoll content
                if user_context:
                    ctx_content = user_context.context_content
                elif get_driscoll_content:
                    # No auth - use Driscoll content for the current division
                    department_content = get_driscoll_content(tenant.division)
                    ctx_content = [department_content] if department_content else None
                else:
                    ctx_content = None

                # Stream response
                response_text = ""
                async for chunk in engine.think(content, tenant=tenant, context_content=ctx_content):
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
                tenant = TenantContext(
                    tenant_id=tenant.tenant_id,
                    division=new_division,
                    zone=tenant.zone,
                    role=tenant.role,
                    email=tenant.email,
                )
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
        manager.disconnect(session_id)


# =============================================================================
# RUN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)