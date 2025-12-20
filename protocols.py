"""
protocols.py - The Nuclear Elements

This is the ONLY file new code should import from for cross-module dependencies.
Everything else is internal implementation detail.

These 12 exports are the stable API surface of enterprise_bot:

CONFIGURATION:
    cfg(key, default)           - Get any config value (dot notation)
    load_config(path)           - Load config from yaml

AUTH:
    get_auth_service()          - Singleton for all auth operations
    authenticate_user(email)    - SSO -> database user
    User                        - Auth user dataclass

TENANT:
    get_tenant_service()        - Singleton for tenant/dept data
    TenantContext               - Request context carrier dataclass

COGNITIVE:
    CogTwin                     - The brain (query/response pipeline)
    DualRetriever               - Memory retrieval system
    create_adapter(provider)    - LLM factory (Grok/Claude/etc)

DATA:
    MemoryNode                  - Atomic memory chunk dataclass
    EpisodicMemory              - Conversation episode dataclass

Usage:
    from protocols import cfg, get_auth_service, CogTwin, MemoryNode

    # That's it. Don't import from 50 different files.
    # Everything else is implementation detail.

Version: 1.0.0
"""

# =============================================================================
# CONFIGURATION
# =============================================================================
from config_loader import (
    cfg,
    load_config,
    get_config,
    memory_enabled,
    is_enterprise_mode,
)

# =============================================================================
# AUTH
# =============================================================================
from auth_service import (
    get_auth_service,
    authenticate_user,
    User,
)

# =============================================================================
# TENANT
# =============================================================================
from tenant_service import (
    get_tenant_service,
)

from enterprise_tenant import (
    TenantContext,
)

# =============================================================================
# COGNITIVE ENGINE
# =============================================================================
from cog_twin import CogTwin
from retrieval import DualRetriever
from model_adapter import create_adapter

# =============================================================================
# DATA SCHEMAS
# =============================================================================
from schemas import (
    MemoryNode,
    EpisodicMemory,
    # Enums (commonly needed with the dataclasses)
    Source,
    IntentType,
)

# =============================================================================
# PUBLIC API
# =============================================================================
__all__ = [
    # Config
    "cfg",
    "load_config",
    "get_config",
    "memory_enabled",
    "is_enterprise_mode",
    # Auth
    "get_auth_service",
    "authenticate_user",
    "User",
    # Tenant
    "get_tenant_service",
    "TenantContext",
    # Cognitive
    "CogTwin",
    "DualRetriever",
    "create_adapter",
    # Data
    "MemoryNode",
    "EpisodicMemory",
    "Source",
    "IntentType",
]
