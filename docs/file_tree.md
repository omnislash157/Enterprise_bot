# Enterprise Bot - File Tree

Cold start reference for AI agents. Load `core/protocols.py` for the 23 nuclear exports.

```
enterprise_bot/
│
├── core/                              # BRAIN - Start here
│   ├── protocols.py                   # THE NUCLEAR MAP - 23 stable exports, import from here
│   ├── cog_twin.py                    # Main orchestrator, pairs with venom_voice.py
│   ├── venom_voice.py                 # Personality engine, prompt injection, streaming
│   ├── enterprise_twin.py             # Corporate mode twin (policy-first, no personality)
│   ├── enterprise_rag.py              # RAG pipeline for enterprise manuals
│   ├── enterprise_tenant.py           # TenantContext dataclass for multi-tenant
│   ├── model_adapter.py               # LLM factory - Grok/Claude/OpenAI abstraction
│   ├── schemas.py                     # MemoryNode, EpisodicMemory, Enums (Source, IntentType, etc)
│   ├── config.py                      # Settings class, env loading
│   ├── config_loader.py               # cfg() helper, yaml loading
│   ├── config.yaml                    # Runtime config (tier, features, model)
│   └── main.py                        # FastAPI app, WebSocket, route mounting
│
├── auth/                              # AUTHENTICATION & TENANCY
│   ├── auth_service.py                # User CRUD, get_auth_service(), authenticate_user()
│   ├── tenant_service.py              # Department content, get_tenant_service()
│   ├── azure_auth.py                  # Azure AD/Entra ID SSO token validation
│   ├── sso_routes.py                  # OAuth callbacks (/api/auth/*)
│   ├── admin_routes.py                # Admin API (/api/admin/*) - user mgmt, roles
│   ├── auth_schema.py                 # DB schema for users table, SOX gating
│   │
│   └── analytics_engine/              # ANALYTICS SUBSYSTEM
│       ├── analytics_service.py       # Analytics data aggregation
│       └── analytics_routes.py        # Analytics API routes (/api/admin/analytics)
│
├── memory/                            # MEMORY & RETRIEVAL
│   ├── __init__.py                    # Exports: AsyncEmbedder, DualRetriever
│   ├── embedder.py                    # AsyncEmbedder - BGE-M3 via DeepInfra/TEI
│   ├── retrieval.py                   # DualRetriever - vector + keyword search
│   ├── memory_pipeline.py             # Ingest loop, CognitiveOutput -> memory
│   ├── memory_backend.py              # Abstract backend, FileBackend
│   ├── hybrid_search.py               # Vector + BM25 fusion scoring
│   ├── memory_grep.py                 # BM25 keyword search over memories
│   ├── heuristic_enricher.py          # Auto-tag memories with metadata
│   ├── cluster_schema.py              # ClusterSchemaEngine for topic clustering
│   ├── streaming_cluster.py           # Real-time cluster assignment
│   ├── evolution_engine.py            # Memory consolidation over time
│   ├── metacognitive_mirror.py        # Self-monitoring, drift detection
│   ├── reasoning_trace.py             # CognitiveTracer for debug/audit
│   ├── scoring.py                     # ResponseScore, training mode UI
│   ├── chat_memory.py                 # ChatMemoryStore - recent exchanges
│   ├── squirrel.py                    # SquirrelTool - context retrieval tool
│   ├── llm_tagger.py                  # LLM-based memory tagging
│   ├── fast_filter.py                 # Fast intent classification
│   ├── dedup.py                       # Memory deduplication
│   ├── read_traces.py                 # CLI to read reasoning traces
│   │
│   ├── backends/                      # STORAGE BACKENDS
│   │   ├── __init__.py                # Exports: PostgresBackend
│   │   └── postgres.py                # PostgreSQL + pgvector implementation
│   │
│   └── ingest/                        # INGESTION SUBPACKAGE
│       ├── __init__.py                # Exports: IngestPipeline, ChatParserFactory
│       ├── pipeline.py                # Main ingestion orchestrator
│       ├── chat_parser.py             # Parse chat across LLM providers
│       ├── doc_loader.py              # Load documents for RAG
│       ├── docx_to_json_chunks.py     # Convert DOCX manuals to JSON chunks
│       ├── batch_convert_warehouse.py # Batch convert Driscoll manuals
│       ├── ingest_to_postgres.py      # Load chunks into PostgreSQL
│       └── json_chunk_loader.py       # JSON chunk parsing utilities
│
├── claude_sdk/                        # CLAUDE SDK INTEGRATION
│   ├── claude_chat.py                 # SDK agent REPL - interactive sessions
│   ├── claude_run.py                  # One-shot executor for scripts
│   ├── db_tools.py                    # Database tools exposed to SDK
│   ├── sdk_recon.py                   # SDK capability detection
│   │
│   └── skills/                        # CLAUDE CODE SKILLS
│       ├── SKILLS_INDEX.md            # Skill registry
│       ├── db.skill.md                # Database operations skill
│       ├── etl.skill.md               # ETL pipeline skill
│       ├── excel.skill.md             # Excel generation skill
│       ├── powerbi.skill.md           # Power BI integration skill
│       ├── profile.skill.md           # User profile skill
│       └── schema.skill.md            # Schema management skill
│
├── db/                                # DATABASE UTILITIES
│   ├── migrations/                    # SQL migration files
│   │   ├── add_analytics_indexes.sql  # Performance indexes
│   │   ├── add_azure_oid.sql          # Azure Object ID column
│   │   └── verify_azure_oid.sql       # Verification query
│   ├── install_pgvector.py            # Install pgvector extension
│   ├── run_migration_002.py           # Run specific migration
│   └── run_migrations_002_003.py      # Run migration range
│
├── docs/                              # DOCUMENTATION
│   ├── FILE_TREE.md                   # This file - backend structure
│   ├── FRONTEND_TREE.md               # Frontend SvelteKit structure
│   └── *.md                           # Various implementation docs
│
├── manuals/                           # SOURCE DOCUMENTS
│   └── Driscoll/                      # Company process manuals + chunks
│
├── frontend/                          # SVELTEKIT APP (see FRONTEND_TREE.md)
│
├── archive/                           # Deprecated code (don't load)
│
│── # CONFIG FILES ────────────────────────────────────────────────
│
├── requirements.txt                   # Python dependencies
├── pyproject.toml                     # Python project config
├── Procfile                           # Railway/Heroku process file
├── runtime.txt                        # Python version spec
├── email_whitelist.json               # Allowed email domains
├── .gitignore
└── README.md
```

## Quick Start

```python
# The one import to rule them all:
from core.protocols import cfg, get_auth_service, CogTwin, MemoryNode, AsyncEmbedder

# Or explicit module imports:
from memory.retrieval import DualRetriever
from memory.embedder import AsyncEmbedder
from memory.ingest.pipeline import IngestPipeline
from auth.auth_service import authenticate_user
```

## Architecture Flow

```
User Query
    ↓
main.py (FastAPI/WebSocket)
    ↓
cog_twin.py (orchestrator)
    ├── retrieval.py (fetch memories)
    ├── memory_pipeline.py (ingest response)
    └── venom_voice.py (format output)
    ↓
LLM API (via model_adapter.py)
    ↓
Response + Memory Ingest
```
