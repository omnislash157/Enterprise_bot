"""
Enterprise Bot Backend - Driscoll Foods
Clean fork with CogTwin dependencies removed.

This is a "dumb bot" that stuffs manuals into context window.
No memory pipelines, no FAISS, no embeddings.

Version: 1.0.0 (Enterprise Fork)
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import asyncio
import json
import os
import logging
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