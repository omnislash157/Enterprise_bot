"""
Enterprise Bot Backend - Driscoll Foods
Full RAG with CogTwin engine.

CogTwin provides memory pipelines, vector retrieval, and hybrid search.

Version: 2.0.0 (CogTwin RAG)
"""
from __future__ import annotations

# Load environment variables FIRST (before any other imports that need them)
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header, Request, File, UploadFile, Form
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import httpx
from pydantic import BaseModel
from datetime import datetime
from collections import defaultdict
import asyncio
import json
import os
import logging
import time
import uuid
from pathlib import Path
from typing import Optional
from core.metrics_collector import metrics_collector
from auth.metrics_routes import metrics_router
from voice_transcription import start_voice_session, send_voice_chunk, stop_voice_session, text_to_speech

# Setup logging FIRST (before any imports that might reference logger)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Observability imports
try:
    from core.tracing import trace_collector, start_trace, create_span
    from core.structured_logging import setup_structured_logging, shutdown_structured_logging
    from core.alerting import alert_engine
    from auth.tracing_routes import tracing_router
    from auth.logging_routes import logging_router
    from auth.alerting_routes import alerting_router
    OBSERVABILITY_LOADED = True
except ImportError as e:
    logger.warning(f"Observability modules not loaded: {e}")
    OBSERVABILITY_LOADED = False

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
# ENTERPRISE IMPORTS - CogTwin RAG Engine
# =============================================================================

try:
    from .config_loader import (
        load_config,
        cfg,
        memory_enabled,
        is_enterprise_mode,
        get_ui_features,
        get_config,
    )
    from .cog_twin import CogTwin
    from .enterprise_twin import EnterpriseTwin
    from .enterprise_tenant import TenantContext
    CONFIG_LOADED = True
except ImportError as e:
    logger.error(f"Failed to import enterprise modules: {e}")
    CONFIG_LOADED = False


# =============================================================================
# TWIN ROUTER
# =============================================================================

def get_twin():
    """Router: select orchestrator based on deployment mode."""
    from .config_loader import get_config
    mode = cfg('deployment.mode', 'personal')

    if mode == 'enterprise':
        from .enterprise_twin import EnterpriseTwin
        logger.info("[STARTUP] Initializing EnterpriseTwin (enterprise mode)...")
        return EnterpriseTwin(get_config())  # Pass config
    else:
        from .cog_twin import CogTwin
        logger.info("[STARTUP] Initializing CogTwin (personal mode)...")
        return CogTwin()


# Auth imports
try:
    from auth.auth_service import get_auth_service, authenticate_user
    AUTH_LOADED = True
except ImportError as e:
    logger.warning(f"Auth service not loaded: {e}")
    AUTH_LOADED = False

# Tenant service import
try:
    from auth.tenant_service import get_tenant_service
    TENANT_SERVICE_LOADED = True
except ImportError as e:
    logger.warning(f"Tenant service not loaded: {e}")
    TENANT_SERVICE_LOADED = False

# Admin routes import
try:
    from auth.admin_routes import admin_router
    ADMIN_ROUTES_LOADED = True
except ImportError as e:
    logger.warning(f"Admin routes not loaded: {e}")
    ADMIN_ROUTES_LOADED = False

# Analytics service import
try:
    from auth.analytics_engine.analytics_service import get_analytics_service
    from auth.analytics_engine.analytics_routes import analytics_router
    ANALYTICS_LOADED = True
except ImportError as e:
    logger.warning(f"Analytics service not loaded: {e}")
    ANALYTICS_LOADED = False

# SSO routes import
try:
    from auth.sso_routes import router as sso_router
    SSO_ROUTES_LOADED = True
except ImportError as e:
    logger.warning(f"SSO routes not loaded: {e}")
    SSO_ROUTES_LOADED = False

# Azure auth import
try:
    from auth.azure_auth import validate_access_token, is_configured as azure_configured
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
                    return {
                        "id": user.id,
                        "email": user.email,
                        "display_name": user.display_name,
                        "departments": user.department_access,
                        "is_super_user": user.is_super_user,
                        "can_manage_users": len(user.dept_head_for) > 0 or user.is_super_user,
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

        return {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "departments": user.department_access,
            "is_super_user": user.is_super_user,
            "can_manage_users": len(user.dept_head_for) > 0 or user.is_super_user,
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

class UploadChatRequest(BaseModel):
    """Request model for chat upload endpoint."""
    provider: str  # "anthropic", "openai", etc.
    content: str   # JSON content of chat export

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

    # Record to metrics collector
    endpoint = request.url.path
    is_error = response.status_code >= 400
    metrics_collector.record_request(endpoint, elapsed_ms, error=is_error)

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

# Include metrics router
app.include_router(metrics_router, prefix="/api/metrics", tags=["metrics"])
logger.info("[STARTUP] Metrics routes loaded at /api/metrics")

# Include observability routers
if OBSERVABILITY_LOADED:
    app.include_router(tracing_router, prefix="/api/observability/traces", tags=["observability"])
    app.include_router(logging_router, prefix="/api/observability/logs", tags=["observability"])
    app.include_router(alerting_router, prefix="/api/observability/alerts", tags=["observability"])
    logger.info("[STARTUP] Observability routes loaded at /api/observability")

# Global engine instance
engine: Optional[CogTwin] = None

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
    config = get_config()

    # Load email whitelist
    email_whitelist.load()

    # Initialize appropriate twin based on mode
    engine = get_twin()

    # Start async components if needed
    if hasattr(engine, 'start'):
        await engine.start()

    # Log twin info
    logger.info(f"[STARTUP] Twin ready: {type(engine).__name__}")
    if hasattr(engine, 'memory_count'):
        logger.info(f"  Memory count: {engine.memory_count}")
    if hasattr(engine, 'model'):
        logger.info(f"  Model: {engine.model}")

    # Initialize Redis cache
    logger.info("[STARTUP] Initializing Redis cache...")
    try:
        from .cache import init_cache
        cache = await init_cache()
        stats = await cache.get_stats()
        logger.info(f"[STARTUP] Cache status: {stats}")
    except Exception as e:
        logger.warning(f"[STARTUP] Cache init failed (continuing without): {e}")

    # Warm up database connection pool
    if CONFIG_LOADED and is_enterprise_mode():
        logger.info("[STARTUP] Warming database connection pool...")
        try:
            from .database import init_db_pool
            config = get_config()
            await init_db_pool(config)
            logger.info("[STARTUP] Database pool initialized")
        except Exception as e:
            logger.warning(f"[STARTUP] Database pool init failed: {e}")

    # Warm up analytics connection pool and query plan cache
    if ANALYTICS_LOADED:
        logger.info("[STARTUP] Warming analytics connection pool...")
        try:
            analytics = get_analytics_service()
            # Hit the dashboard query to warm pool + plans
            analytics.get_dashboard_data(hours=24)
            logger.info("[STARTUP] Analytics warm-up complete")
        except Exception as e:
            logger.warning(f"[STARTUP] Analytics warm-up failed: {e}")

    # Check psutil availability for system metrics
    try:
        import psutil
        logger.info("[STARTUP] psutil available - system metrics enabled")
    except ImportError:
        logger.warning("[STARTUP] psutil not installed - run: pip install psutil")

    # Initialize observability stack
    if OBSERVABILITY_LOADED:
        logger.info("[STARTUP] Initializing observability stack...")
        try:
            # Get database pool for observability
            from .database import get_db_pool
            config = get_config()
            db_pool = await get_db_pool(config)

            # Setup trace collector
            trace_collector.set_db_pool(db_pool)
            await trace_collector.start()
            logger.info("[STARTUP] Trace collector started")

            # Setup structured logging
            setup_structured_logging(db_pool)
            logger.info("[STARTUP] Structured logging enabled")

            # Setup alert engine
            alert_engine.set_db_pool(db_pool)
            await alert_engine.start()
            logger.info("[STARTUP] Alert engine started")
        except Exception as e:
            logger.error(f"[STARTUP] Observability init failed: {e}")

# =============================================================================
# SHUTDOWN
# =============================================================================

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of observability components."""
    # Close database pool
    try:
        from core.database import close_db_pool
        await close_db_pool()
        logger.info("[SHUTDOWN] Database pool closed")
    except Exception as e:
        logger.error(f"[SHUTDOWN] Database cleanup error: {e}")

    if OBSERVABILITY_LOADED:
        logger.info("[SHUTDOWN] Stopping observability stack...")
        try:
            await trace_collector.stop()
            await alert_engine.stop()
            shutdown_structured_logging()
            logger.info("[SHUTDOWN] Observability stack stopped")
        except Exception as e:
            logger.error(f"[SHUTDOWN] Observability cleanup error: {e}")

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

@app.get("/health/deep")
async def deep_health_check():
    """Comprehensive health check including observability stack."""
    from datetime import datetime

    checks = {}
    overall_status = "healthy"

    # Database check
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = {"status": "healthy"}
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)}
        overall_status = "unhealthy"

    # Redis check
    try:
        from core.cache import get_redis
        redis = await get_redis()
        if redis:
            await redis.ping()
            checks["redis"] = {"status": "healthy"}
        else:
            checks["redis"] = {"status": "warning", "message": "Redis not configured"}
    except Exception as e:
        checks["redis"] = {"status": "error", "message": str(e)}
        if overall_status == "healthy":
            overall_status = "degraded"

    # Observability tables check
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'enterprise'
                AND table_name IN ('traces', 'trace_spans', 'structured_logs', 'alert_rules', 'alerts')
            """)
            table_names = [r['table_name'] for r in tables]
            expected = {'traces', 'trace_spans', 'structured_logs', 'alert_rules', 'alerts'}
            missing = expected - set(table_names)
            if missing:
                checks["observability_tables"] = {"status": "error", "missing": list(missing)}
                overall_status = "unhealthy"
            else:
                checks["observability_tables"] = {"status": "healthy", "count": len(table_names)}
    except Exception as e:
        checks["observability_tables"] = {"status": "error", "message": str(e)}
        overall_status = "unhealthy"

    # Metrics collector check
    try:
        if 'metrics_collector' in dir():
            checks["metrics"] = {"status": "healthy"}
        else:
            checks["metrics"] = {"status": "warning", "message": "Metrics collector not in scope"}
    except Exception as e:
        checks["metrics"] = {"status": "error", "message": str(e)}

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
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
# CHAT UPLOAD ENDPOINT (Phase 4: Extraction Toggle)
# =============================================================================

@app.post("/api/upload/chat")
async def upload_chat(
    request: UploadChatRequest,
    user: dict = Depends(require_auth)
):
    """
    Upload chat export for memory ingestion.

    PHASE 4: This endpoint is gated by features.chat_import config.
    Enterprise accounts cannot import external chat logs - memory builds
    only from bot conversations.
    """
    # Phase 4: Guard with extraction_enabled config
    if not cfg("features.chat_import", True):
        raise HTTPException(
            status_code=403,
            detail="Chat import is disabled. Enterprise accounts build memory from bot conversations only."
        )

    # If we get here, chat import is enabled (personal SaaS mode)
    # TODO: Implement actual ingestion logic
    # For now, return success to indicate the feature is available
    return {
        "status": "accepted",
        "message": "Chat import feature is enabled but ingestion not yet implemented",
        "provider": request.provider,
        "user": user.get("email"),
        "note": "This endpoint will process chat exports when ingest pipeline is integrated"
    }

# =============================================================================
# FILE UPLOAD - Proxy to xAI Files API
# =============================================================================

@app.post("/api/upload/file")
async def upload_file_to_xai(
    file: UploadFile = File(...),
    department: str = Form(None),
    user: dict = Depends(require_auth)
):
    """
    Upload file to xAI Files API for use in chat.

    Supported: PDF, DOCX, XLSX, TXT, CSV, PNG, JPG (max 30MB)
    Returns: file_id to attach to chat messages

    xAI handles extraction and RAG automatically.
    """
    # Validate file type
    allowed_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/csv",
        "image/png",
        "image/jpeg",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            400,
            f"Unsupported file type: {file.content_type}. "
            f"Allowed: PDF, DOCX, XLSX, TXT, CSV, PNG, JPG"
        )

    # Read file content
    contents = await file.read()

    # Validate size (30MB max for xAI)
    if len(contents) > 30 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 30MB)")

    # Upload to xAI Files API
    xai_api_key = os.getenv("XAI_API_KEY")
    if not xai_api_key:
        raise HTTPException(500, "XAI_API_KEY not configured")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.x.ai/v1/files",
                headers={"Authorization": f"Bearer {xai_api_key}"},
                files={"file": (file.filename, contents, file.content_type)},
                data={"purpose": "chat"}  # xAI uses "chat", not "assistants"
            )
            response.raise_for_status()
            xai_response = response.json()
    except httpx.HTTPError as e:
        logger.error(f"xAI file upload failed: {e}")
        raise HTTPException(500, f"File upload to xAI failed: {str(e)}")

    file_id = xai_response.get("id")
    if not file_id:
        raise HTTPException(500, "xAI did not return file_id")

    logger.info(f"File uploaded to xAI: {file_id} by {user.get('email', 'unknown')}")

    return {
        "file_id": file_id,
        "file_name": file.filename,
        "file_size": len(contents),
        "file_type": file.content_type,
    }

# =============================================================================
# TEXT-TO-SPEECH - Deepgram Aura
# =============================================================================

@app.post("/api/tts")
async def tts_endpoint(request: Request):
    """Convert text to speech, return audio bytes."""
    body = await request.json()
    text = body.get("text", "")
    voice = body.get("voice", "professional")

    if not text:
        raise HTTPException(400, "No text provided")

    # Cap length to prevent abuse
    if len(text) > 5000:
        text = text[:5000]

    audio = await text_to_speech(text, voice)

    if audio:
        return Response(
            content=audio,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"}
        )
    else:
        raise HTTPException(500, "TTS generation failed")

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
    """
    List users endpoint - DEPRECATED.

    This endpoint relied on list_all_users() and list_users_in_department()
    which were removed during the 2-table schema migration.
    Use the new admin portal endpoints at /api/admin/users instead.
    """
    raise HTTPException(
        501,
        "This endpoint is deprecated. Use /api/admin/users (admin portal) instead."
    )


@app.get("/api/departments")
async def list_departments(user: dict = Depends(get_current_user)):
    """
    Available departments (static list - no table)
    - Authenticated users see their accessible departments
    - Unauthenticated see all (for login UI dropdown)
    """
    # Static department list - departments table has been removed
    all_depts = [
        {"slug": "sales", "name": "Sales", "description": "Sales Department"},
        {"slug": "purchasing", "name": "Purchasing", "description": "Purchasing Department"},
        {"slug": "warehouse", "name": "Warehouse", "description": "Warehouse Department"},
        {"slug": "credit", "name": "Credit", "description": "Credit Department"},
        {"slug": "accounting", "name": "Accounting", "description": "Accounting Department"},
        {"slug": "it", "name": "IT", "description": "IT Department"},
    ]

    if user and not user.get("is_super_user"):
        # Filter to user's accessible departments
        accessible = set(user.get("departments", []))
        all_depts = [d for d in all_depts if d["slug"] in accessible]

    return {"departments": all_depts}


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
# RATE LIMITER
# =============================================================================

class RateLimiter:
    """Simple rate limiter for WebSocket messages."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, session_id: str) -> bool:
        """Check if session is within rate limits."""
        now = time.time()
        # Clean old requests
        self.requests[session_id] = [
            t for t in self.requests[session_id]
            if now - t < self.window
        ]
        # Check limit
        if len(self.requests[session_id]) >= self.max_requests:
            return False
        self.requests[session_id].append(now)
        return True

rate_limiter = RateLimiter(max_requests=30, window_seconds=60)

# SECURITY: Honeypot divisions - anyone probing these is suspicious
HONEYPOT_DIVISIONS = {"executive", "ceo", "admin", "root", "system", "superuser", "god"}

# SECURITY: Session timeout (30 minutes)
SESSION_TIMEOUT_SECONDS = 1800

# SECURITY: Max message length (10k chars)
MAX_MESSAGE_LENGTH = 10000

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
    metrics_collector.record_ws_connect()  # Record WebSocket connection

    # SECURITY: No default access - must verify before sending messages
    user_email = None  # No default - must verify
    user_verified = False
    request_twin = None  # Will be set on verify
    last_activity = time.time()  # SECURITY: Track for session timeout
    client_ip = websocket.client.host if websocket.client else "unknown"

    tenant = TenantContext(
        tenant_id="driscoll",
        department="none",  # No access until verified
        role="anonymous",
    )

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        while True:
            # SECURITY: Check session timeout
            if time.time() - last_activity > SESSION_TIMEOUT_SECONDS:
                await websocket.send_json({
                    "type": "error",
                    "message": "Session expired due to inactivity",
                    "code": "SESSION_EXPIRED"
                })
                metrics_collector.record_ws_message('out')
                break  # End session
            data = await websocket.receive_json()
            last_activity = time.time()  # SECURITY: Update activity timestamp
            metrics_collector.record_ws_message('in')  # Record incoming message
            msg_type = data.get("type", "message")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                metrics_collector.record_ws_message('out')  # Record outgoing message

            elif msg_type == "verify":
                email = data.get("email", "")
                # Capture auth_method from client (set by frontend during SSO or email login)
                client_auth_method = data.get("auth_method", "email")

                if AUTH_LOADED and email:
                    auth = get_auth_service()
                    user = auth.get_or_create_user(email)

                    if user:
                        user_email = email
                        user_verified = True  # SECURITY: Mark session as verified

                        # Use requested division if user has access
                        requested_division = data.get("division", "warehouse")
                        if requested_division not in user.department_access and not user.is_super_user:
                            requested_division = user.department_access[0] if user.department_access else "warehouse"

                        tenant = TenantContext(
                            tenant_id="driscoll",
                            department=requested_division,
                            role="user",
                            user_email=email,
                        )

                        # Get twin based on deployment mode (config.yaml)
                        request_twin = get_twin()

                        auth.update_last_login(user.id)  # Track login

                        # Log login event to analytics
                        if ANALYTICS_LOADED:
                            try:
                                analytics = get_analytics_service()
                                analytics.log_event(
                                    event_type="login",
                                    user_email=email,
                                    department=tenant.department,
                                    session_id=session_id,
                                    user_id=str(user.id) if hasattr(user, 'id') else None
                                )
                            except Exception as ae:
                                logger.warning(f"Failed to log login event: {ae}")

                        await websocket.send_json({
                            "type": "verified",
                            "email": email,
                            "division": tenant.department,
                            "departments": user.department_access,
                        })
                        metrics_collector.record_ws_message('out')  # Record outgoing message
                    else:
                        # Domain not allowed
                        logger.warning(f"[SECURITY] Failed auth: email={email}, ip={client_ip}, reason=domain_not_authorized")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Email domain not authorized",
                        })
                        metrics_collector.record_ws_message('out')  # Record outgoing message
                elif email:
                    # Fallback to old whitelist behavior
                    if email_whitelist.verify(email):
                        user_email = email
                        user_verified = True  # SECURITY: Mark session as verified
                        tenant = TenantContext(
                            tenant_id="driscoll",
                            department=data.get("division", tenant.department),
                            role="user",
                            user_email=email,
                        )
                        await websocket.send_json({
                            "type": "verified",
                            "email": email,
                            "division": tenant.department,
                        })
                        metrics_collector.record_ws_message('out')  # Record outgoing message
                    else:
                        logger.warning(f"[SECURITY] Failed auth: email={email}, ip={client_ip}, reason=not_in_whitelist")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Email not authorized. Please use SSO login.",
                        })
                        metrics_collector.record_ws_message('out')  # Record outgoing message
                        continue  # Don't proceed with unauthorized email

            elif msg_type == "message":
                # SECURITY: Require verification before processing messages
                if not user_verified:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Authentication required. Please log in.",
                        "code": "AUTH_REQUIRED"
                    })
                    metrics_collector.record_ws_message('out')
                    continue  # Block message

                # SECURITY: Rate limit check
                if not rate_limiter.is_allowed(session_id):
                    await websocket.send_json({
                        "type": "error",
                        "message": "Rate limit exceeded. Please slow down.",
                        "code": "RATE_LIMITED"
                    })
                    metrics_collector.record_ws_message('out')
                    continue

                content = data.get("content", "")
                file_ids = data.get("file_ids", [])  # Extract file IDs for xAI Files API
                
                # DEBUG: Log file_ids for tracing file upload flow
                if file_ids:
                    logger.info(f"[WS] File IDs received: {file_ids}")
                else:
                    logger.debug(f"[WS] No file_ids in message. Keys received: {list(data.keys())}")

                # SECURITY: Max message length check
                if len(content) > MAX_MESSAGE_LENGTH:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Message too long",
                        "code": "MSG_TOO_LONG"
                    })
                    metrics_collector.record_ws_message('out')
                    continue

                # Generate request ID for audit trail
                request_id = str(uuid.uuid4())[:8]
                logger.info(f"[{request_id}] Message from {user_email}: {content[:50]}...")

                # Use request_twin if available (auth-based routing), otherwise use global engine
                active_twin = request_twin if request_twin else engine

                if active_twin is None:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Engine not initialized",
                    })
                    metrics_collector.record_ws_message('out')  # Record outgoing message
                    continue

                # ===== TWIN-SPECIFIC HANDLING =====
                # EnterpriseTwin and CogTwin have different signatures
                # Check twin type by class name
                twin_type = type(active_twin).__name__

                if twin_type == 'EnterpriseTwin':
                    # EnterpriseTwin: streaming response
                    # Read division from message payload first, fallback to session state
                    message_division = data.get("division")
                    user_language = data.get("language", "en")  # Extract language for LLM response
                    effective_division = tenant.department  # Default to session

                    # Track query start time for analytics
                    query_start_time = time.perf_counter()

                    # SECURITY: Honeypot detection
                    if message_division and message_division.lower() in HONEYPOT_DIVISIONS:
                        logger.critical(f"[HONEYPOT] [{request_id}] User {user_email} (IP: {client_ip}) attempted access to honeypot division: {message_division}")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Access denied",
                            "code": "ACCESS_DENIED",
                            "request_id": request_id
                        })
                        metrics_collector.record_ws_message('out')
                        continue

                    if message_division and message_division != tenant.department:
                        # SECURITY: Validate user has access to requested division
                        if AUTH_LOADED and user_email:
                            try:
                                auth = get_auth_service()
                                user = auth.get_user_by_email(user_email)
                                if user:
                                    if user.is_super_user or message_division in user.department_access:
                                        effective_division = message_division
                                        logger.info(f"[WS] Division override allowed: {user_email} -> {message_division}")
                                    else:
                                        logger.warning(f"[WS] Division override BLOCKED: {user_email} attempted {message_division}")
                                        await websocket.send_json({
                                            "type": "error",
                                            "message": f"Access denied to department: {message_division}",
                                            "code": "DIVISION_ACCESS_DENIED"
                                        })
                                        metrics_collector.record_ws_message('out')
                                        continue
                            except Exception as e:
                                logger.error(f"[WS] Division check failed: {e}")
                                # SECURITY: Fail closed - deny access on error
                                await websocket.send_json({
                                    "type": "error",
                                    "message": "Authorization check failed",
                                    "code": "AUTH_ERROR"
                                })
                                metrics_collector.record_ws_message('out')
                                continue

                    # Build content array if files attached, otherwise use string
                    if file_ids:
                        user_content = [
                            {"type": "text", "text": content},
                            *[{"type": "file", "file_id": fid} for fid in file_ids]
                        ]
                    else:
                        user_content = content  # Backward compatible - string

                    # Track response for analytics
                    full_response_text = ""
                    response_metadata = {}
                    tokens_in = 0
                    tokens_out = 0

                    # Stream response chunks as they arrive
                    async for chunk in active_twin.think_streaming(
                        user_input=user_content,
                        user_email=user_email,
                        department=effective_division,
                        session_id=session_id,
                        language=user_language,
                    ):
                        # Check for metadata marker
                        if chunk.startswith("\n__METADATA__:"):
                            # Parse and send as cognitive_state
                            try:
                                metadata = json.loads(chunk.replace("\n__METADATA__:", ""))
                                response_metadata = metadata
                                await websocket.send_json({
                                    "type": "cognitive_state",
                                    "phase": "ready",
                                    "temperature": 0.5,
                                    "query_type": "streamed",
                                    "tools_fired": metadata.get("tools_fired", []),
                                    "retrieval_time_ms": metadata.get("retrieval_ms", 0),
                                    "total_time_ms": metadata.get("total_ms", 0),
                                })
                                metrics_collector.record_ws_message('out')  # Record outgoing message
                            except json.JSONDecodeError:
                                pass
                        else:
                            # Stream content chunk
                            full_response_text += chunk
                            await websocket.send_json({
                                "type": "stream_chunk",
                                "content": chunk,
                                "done": False,
                            })
                            metrics_collector.record_ws_message('out')  # Record outgoing message

                    # Send done signal
                    await websocket.send_json({
                        "type": "stream_chunk",
                        "content": "",
                        "done": True,
                    })
                    metrics_collector.record_ws_message('out')  # Record outgoing message

                    # Calculate response time
                    query_elapsed_ms = int((time.perf_counter() - query_start_time) * 1000)

                    # Estimate token counts (rough approximation: 1 token ~= 4 chars)
                    tokens_in = len(content) // 4 if isinstance(content, str) else len(str(content)) // 4
                    tokens_out = len(full_response_text) // 4

                    # Log query to analytics
                    if ANALYTICS_LOADED:
                        try:
                            analytics = get_analytics_service()
                            query_id = analytics.log_query(
                                user_email=user_email,
                                department=effective_division,
                                query_text=content if isinstance(content, str) else str(content)[:500],
                                session_id=session_id,
                                response_time_ms=query_elapsed_ms,
                                response_length=len(full_response_text),
                                tokens_input=tokens_in,
                                tokens_output=tokens_out,
                                model_used="grok-beta",
                                user_id=None  # Could get from auth context if needed
                            )
                            logger.info(f"[ANALYTICS] Query logged: {query_id}")
                        except Exception as ae:
                            logger.warning(f"[ANALYTICS] Failed to log query: {ae}")

                else:
                    # CogTwin: streams AsyncIterator[str]
                    # Extract auth context for scoped retrieval
                    auth_tenant_id = None
                    auth_user_id = None

                    if tenant and tenant.tenant_id:
                        auth_tenant_id = tenant.tenant_id
                    elif user_email:
                        auth_user_id = user_email

                    # Stream response with auth context
                    response_text = ""
                    async for chunk in active_twin.think(content, user_id=auth_user_id, tenant_id=auth_tenant_id):
                        if isinstance(chunk, str) and chunk:
                            response_text += chunk
                            await websocket.send_json({
                                "type": "stream_chunk",
                                "content": chunk,
                                "done": False,
                            })
                            metrics_collector.record_ws_message('out')  # Record outgoing message

                    # Send done signal
                    await websocket.send_json({
                        "type": "stream_chunk",
                        "content": "",
                        "done": True,
                    })
                    metrics_collector.record_ws_message('out')  # Record outgoing message

                    # Send session stats
                    stats = active_twin.get_session_stats()
                    await websocket.send_json({
                        "type": "cognitive_state",
                        "phase": "ready",
                        "temperature": 0.5,
                        **stats,
                    })
                    metrics_collector.record_ws_message('out')  # Record outgoing message

            elif msg_type == "set_division":
                # Allow changing division mid-session (with authorization check)
                new_division = data.get("division", "warehouse")
                old_division = tenant.department

                # SECURITY: Honeypot detection
                if new_division.lower() in HONEYPOT_DIVISIONS:
                    logger.critical(f"[HONEYPOT] User {user_email} (IP: {client_ip}) attempted set_division to honeypot: {new_division}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Access denied",
                        "code": "ACCESS_DENIED"
                    })
                    metrics_collector.record_ws_message('out')
                    continue

                # Validate user has access to requested division
                if AUTH_LOADED and user_email:
                    try:
                        auth = get_auth_service()
                        user = auth.get_user_by_email(user_email)
                        if user and not user.is_super_user:
                            if new_division not in user.department_access:
                                logger.warning(f"[WS] Division change blocked: {user_email} attempted {new_division}")
                                await websocket.send_json({
                                    "type": "error",
                                    "message": f"No access to department: {new_division}"
                                })
                                metrics_collector.record_ws_message('out')  # Record outgoing message
                                continue  # Reject unauthorized division change
                    except Exception as e:
                        logger.error(f"[WS] Auth check failed during set_division: {e}")
                        # SECURITY: Fail closed - deny on error
                        await websocket.send_json({
                            "type": "error",
                            "message": "Authorization check failed. Please try again.",
                            "code": "AUTH_ERROR"
                        })
                        metrics_collector.record_ws_message('out')
                        continue  # Block the division change

                tenant = TenantContext(
                    tenant_id=tenant.tenant_id,
                    department=new_division,
                    role=tenant.role,
                    user_email=tenant.user_email,
                )

                # Log department switch event
                if ANALYTICS_LOADED and old_division != new_division:
                    try:
                        analytics = get_analytics_service()
                        analytics.log_event(
                            event_type="dept_switch",
                            user_email=tenant.user_email or user_email,
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
                metrics_collector.record_ws_message('out')  # Record outgoing message

            # =============================================
            # VOICE TRANSCRIPTION
            # =============================================
            elif msg_type == "voice_start":
                voice_language = data.get("language", "en")  # Extract language for STT
                logger.info(f"[WS] Voice session starting for {session_id} (lang={voice_language})")

                async def on_transcript(transcript: str, is_final: bool, confidence: float):
                    await websocket.send_json({
                        "type": "voice_transcript",
                        "transcript": transcript,
                        "is_final": is_final,
                        "confidence": confidence,
                        "timestamp": time.time()
                    })
                    metrics_collector.record_ws_message('out')

                async def on_error(error: str):
                    await websocket.send_json({
                        "type": "voice_error",
                        "error": error,
                        "timestamp": time.time()
                    })
                    metrics_collector.record_ws_message('out')

                success = await start_voice_session(session_id, on_transcript, on_error, language=voice_language)

                await websocket.send_json({
                    "type": "voice_started" if success else "voice_error",
                    "success": success,
                    "error": None if success else "Failed to start voice session",
                    "timestamp": time.time()
                })
                metrics_collector.record_ws_message('out')

            elif msg_type == "voice_chunk":
                audio_data = data.get("audio")
                if audio_data:
                    await send_voice_chunk(session_id, audio_data)

            elif msg_type == "voice_stop":
                logger.info(f"[WS] Voice session stopping for {session_id}")
                await stop_voice_session(session_id)
                await websocket.send_json({
                    "type": "voice_stopped",
                    "timestamp": time.time()
                })
                metrics_collector.record_ws_message('out')

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })
                metrics_collector.record_ws_message('out')  # Record outgoing message

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        metrics_collector.record_ws_disconnect()  # Record disconnect
        # Cleanup voice session if active
        await stop_voice_session(session_id)
    except Exception as e:
        # SECURITY: Log full details internally, but don't leak to client
        logger.error(f"[WS] Internal error in session {session_id}: {type(e).__name__}: {e}")

        # Log error event to analytics (with full detail)
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

        # SECURITY: Send generic error to client (no internal details)
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Something went wrong",
                "code": "INTERNAL_ERROR"
            })
            metrics_collector.record_ws_message('out')
        except:
            pass  # Connection may already be closed

        manager.disconnect(session_id)
        metrics_collector.record_ws_disconnect()  # Record disconnect


# =============================================================================
# RUN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)