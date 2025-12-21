"""
protocols.py - The Nuclear Elements

This is the ONLY file new code should import from for cross-module dependencies.
Everything else is internal implementation detail.

These 37 exports are the stable API surface of enterprise_bot:

CONFIGURATION (5):
    cfg(key, default)           - Get any config value (dot notation)
    load_config(path)           - Load config from yaml
    get_config()                - Get full config object
    memory_enabled()            - Check if memory subsystem enabled
    is_enterprise_mode()        - Check if enterprise mode active

AUTH (3):
    get_auth_service()          - Singleton for all auth operations
    authenticate_user(email)    - SSO -> database user
    User                        - Auth user dataclass

TENANT (2):
    get_tenant_service()        - Singleton for tenant/dept data
    TenantContext               - Request context carrier dataclass

COGNITIVE (3):
    CogTwin                     - The brain (query/response pipeline)
    DualRetriever               - Memory retrieval system
    create_adapter(provider)    - LLM factory (Grok/Claude/etc)

EMBEDDINGS (2):
    AsyncEmbedder               - Multi-provider BGE-M3 embeddings
    create_embedder(provider)   - Embedder factory

COGNITIVE PIPELINE (14):
    MetacognitiveMirror         - Self-monitoring, drift detection
    QueryEvent                  - Query event dataclass
    CognitivePhase              - Enum: cognitive processing phase
    MemoryPipeline              - Ingest loop, CognitiveOutput -> memory
    CognitiveOutput             - Pipeline output dataclass
    ThoughtType                 - Enum: thought classification
    CognitiveTracer             - Debug/audit trace recorder
    StepType                    - Enum: reasoning step type
    ReasoningTrace              - Trace dataclass
    ResponseScore               - Response quality score
    TrainingModeUI              - Training mode interface
    ChatMemoryStore             - Recent exchanges store
    SquirrelTool                - Context retrieval tool
    SquirrelQuery               - Query dataclass for squirrel

DATA SCHEMAS (8):
    MemoryNode                  - Atomic memory chunk dataclass
    EpisodicMemory              - Conversation episode dataclass
    Source                      - Enum: memory source type
    IntentType                  - Enum: intent classification
    Complexity                  - Enum: cognitive complexity
    EmotionalValence            - Enum: emotional tone
    Urgency                     - Enum: priority level
    ConversationMode            - Enum: conversation context

Usage:
    from core.protocols import cfg, get_auth_service, CogTwin, MemoryNode, AsyncEmbedder

Version: 3.0.0
"""

# =============================================================================
# CONFIGURATION
# =============================================================================
from .config_loader import (
    cfg,
    load_config,
    get_config,
    memory_enabled,
    is_enterprise_mode,
)

# =============================================================================
# AUTH
# =============================================================================
from auth.auth_service import (
    get_auth_service,
    authenticate_user,
    User,
)

# =============================================================================
# TENANT
# =============================================================================
from auth.tenant_service import (
    get_tenant_service,
)

from .enterprise_tenant import (
    TenantContext,
)

# =============================================================================
# COGNITIVE ENGINE
# =============================================================================
from .cog_twin import CogTwin
from memory.retrieval import DualRetriever
from .model_adapter import create_adapter

# =============================================================================
# EMBEDDINGS
# =============================================================================
from memory.embedder import (
    AsyncEmbedder,
    create_embedder,
)

# =============================================================================
# COGNITIVE PIPELINE
# =============================================================================
from memory.metacognitive_mirror import (
    MetacognitiveMirror,
    QueryEvent,
    CognitivePhase,
)

from memory.memory_pipeline import (
    MemoryPipeline,
    CognitiveOutput,
    ThoughtType,
)

from memory.reasoning_trace import (
    CognitiveTracer,
    StepType,
    ReasoningTrace,
)

from memory.scoring import (
    ResponseScore,
    TrainingModeUI,
)

from memory.chat_memory import ChatMemoryStore

from memory.squirrel import (
    SquirrelTool,
    SquirrelQuery,
)

# =============================================================================
# DATA SCHEMAS
# =============================================================================
from .schemas import (
    MemoryNode,
    EpisodicMemory,
    # Enums (commonly needed with the dataclasses)
    Source,
    IntentType,
    Complexity,
    EmotionalValence,
    Urgency,
    ConversationMode,
)

# =============================================================================
# PUBLIC API
# =============================================================================
__all__ = [
    # Config (5)
    "cfg",
    "load_config",
    "get_config",
    "memory_enabled",
    "is_enterprise_mode",
    # Auth (3)
    "get_auth_service",
    "authenticate_user",
    "User",
    # Tenant (2)
    "get_tenant_service",
    "TenantContext",
    # Cognitive (3)
    "CogTwin",
    "DualRetriever",
    "create_adapter",
    # Embeddings (2)
    "AsyncEmbedder",
    "create_embedder",
    # Cognitive Pipeline (14)
    "MetacognitiveMirror",
    "QueryEvent",
    "CognitivePhase",
    "MemoryPipeline",
    "CognitiveOutput",
    "ThoughtType",
    "CognitiveTracer",
    "StepType",
    "ReasoningTrace",
    "ResponseScore",
    "TrainingModeUI",
    "ChatMemoryStore",
    "SquirrelTool",
    "SquirrelQuery",
    # Data Schemas (8)
    "MemoryNode",
    "EpisodicMemory",
    "Source",
    "IntentType",
    "Complexity",
    "EmotionalValence",
    "Urgency",
    "ConversationMode",
]
