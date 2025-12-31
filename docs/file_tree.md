# Enterprise Bot - File Tree

Cold start reference for AI agents. Load `core/protocols.py` for the 37 nuclear exports.

**Last Updated**: 2025-12-31

```
enterprise_bot/
|
+-- core/                              # BRAIN - Start here
|   +-- protocols.py                   # THE NUCLEAR MAP - 37 stable exports
|   +-- main.py                        # FastAPI app, WebSocket, route mounting
|   +-- cog_twin.py                    # Main orchestrator, pairs with venom_voice.py
|   +-- venom_voice.py                 # Personality engine, prompt injection, streaming
|   +-- enterprise_twin.py             # Corporate mode twin (policy-first, no personality)
|   +-- enterprise_rag.py              # RAG pipeline - hybrid search, threshold-only
|   +-- enterprise_tenant.py           # TenantContext dataclass for multi-tenant
|   +-- tenant_loader.py               # Load tenant configs from clients/*.yaml
|   +-- tenant_middleware.py           # Domain-based tenant routing middleware
|   +-- tenant_routes.py               # Tenant API endpoints
|   +-- model_adapter.py               # LLM factory - Grok/Claude/OpenAI abstraction
|   +-- schemas.py                     # MemoryNode, EpisodicMemory, Enums
|   +-- config_loader.py               # cfg() helper, yaml loading
|   +-- config.yaml                    # Core configuration
|   +-- cache.py                       # Redis-backed response cache
|   +-- database.py                    # Database connection utilities
|   +-- context_stuffing.py            # Load context from docs/driscoll/*.txt
|   |
|   +-- # OBSERVABILITY
|   +-- metrics_collector.py           # MetricsCollector - PostgreSQL + Redis
|   +-- tracing.py                     # Distributed tracing (OpenTelemetry)
|   +-- structured_logging.py          # Structured JSON logging
|   +-- alerting.py                    # Alert engine - threshold monitoring
|   +-- security_logger.py             # Security event logging
|
+-- auth/                              # AUTHENTICATION & ROUTES
|   +-- auth_service.py                # User CRUD, authenticate_user()
|   +-- auth_schema.py                 # Auth Pydantic models
|   +-- audit_service.py               # AuditLogger - batched writes
|   +-- tenant_service.py              # Department content, division access
|   +-- azure_auth.py                  # Azure AD/Entra ID SSO
|   +-- sso_routes.py                  # OAuth callbacks (/api/auth/*)
|   +-- admin_routes.py                # Admin API (/api/admin/*)
|   |
|   +-- # PERSONAL TIER AUTH
|   +-- personal_auth.py               # Email/password + Google OAuth
|   +-- personal_auth_routes.py        # Personal auth endpoints
|   |
|   +-- # OBSERVABILITY ROUTES
|   +-- metrics_routes.py              # /api/admin/metrics
|   +-- tracing_routes.py              # /api/admin/traces
|   +-- logging_routes.py              # /api/admin/logs
|   +-- alerting_routes.py             # /api/admin/alerts
|   +-- query_log_routes.py            # /api/admin/queries
|   |
|   +-- # CREDIT PIPELINE
|   +-- credit_routes.py               # Credit form API
|   +-- credit_docx_generator.js       # DOCX generation for credits
|   |
|   +-- analytics_engine/              # ANALYTICS SUBSYSTEM
|       +-- analytics_service.py       # Analytics data aggregation
|       +-- analytics_routes.py        # /api/admin/analytics
|       +-- query_heuristics.py        # Query pattern analysis
|
+-- memory/                            # MEMORY & RETRIEVAL
|   +-- embedder.py                    # AsyncEmbedder - BGE-M3 via DeepInfra
|   +-- retrieval.py                   # DualRetriever - vector + keyword
|   +-- memory_pipeline.py             # Ingest loop, CognitiveOutput -> memory
|   +-- memory_backend.py              # Abstract backend, FileBackend
|   +-- hybrid_search.py               # Vector + BM25 fusion scoring
|   +-- memory_grep.py                 # BM25 keyword search
|   +-- heuristic_enricher.py          # Auto-tag memories
|   +-- cluster_schema.py              # ClusterSchemaEngine
|   +-- streaming_cluster.py           # Real-time cluster assignment
|   +-- evolution_engine.py            # Memory consolidation
|   +-- metacognitive_mirror.py        # Self-monitoring, drift detection
|   +-- reasoning_trace.py             # CognitiveTracer
|   +-- scoring.py                     # ResponseScore
|   +-- chat_memory.py                 # ChatMemoryStore
|   +-- squirrel.py                    # SquirrelTool
|   +-- llm_tagger.py                  # LLM-based memory tagging
|   +-- fast_filter.py                 # Fast intent classification
|   +-- dedup.py                       # Memory deduplication
|   +-- read_traces.py                 # CLI to read reasoning traces
|   |
|   +-- backends/
|   |   +-- postgres.py                # PostgreSQL + pgvector
|   |
|   +-- ingest/                        # INGESTION PIPELINE
|       +-- pipeline.py                # Main ingestion orchestrator
|       +-- chat_parser.py             # Parse chat across LLM providers
|       +-- doc_loader.py              # Load documents for RAG
|       +-- docx_to_json_chunks.py     # Convert DOCX to JSON chunks
|       +-- batch_convert_warehouse.py # Batch convert Driscoll manuals
|       +-- ingest_to_postgres.py      # Load chunks into PostgreSQL
|       +-- json_chunk_loader.py       # JSON chunk parsing
|       +-- smart_tagger.py            # 4-pass LLM enrichment
|       +-- semantic_tagger.py         # Regex/keyword classification
|       +-- enrichment_pipeline.py     # Full ingest orchestrator
|       +-- smart_retrieval.py         # Question->Question retrieval
|
+-- clients/                           # TENANT CONFIGURATIONS
|   +-- _base.yaml                     # Base tenant config template
|   +-- _personal.yaml                 # Personal tier (Cogzy) config
|   +-- driscoll.yaml                  # Driscoll Intel tenant config
|
+-- claude_sdk_toolkit/                # CLAUDE SDK INTEGRATION
|   +-- claude_chat.py                 # SDK agent REPL
|   +-- claude_run.py                  # One-shot executor
|   +-- claude_cli.py                  # CLI interface
|   +-- db_tools.py                    # Database tools
|   +-- db_tools_sdk.py                # SDK-compatible DB wrappers
|   +-- memory_tools.py                # Memory system tools
|   +-- memory_tools_sdk.py            # SDK-compatible memory wrappers
|   +-- railway_tools.py               # Railway deployment tools
|   +-- railway_tools_sdk.py           # SDK-compatible Railway wrappers
|   +-- convert_tools.py               # Tool conversion utilities
|   +-- sdk_recon.py                   # SDK reconnaissance
|
+-- db/                                # DATABASE MIGRATIONS
|   +-- install_pgvector.py            # pgvector extension installer
|   +-- migrations/
|       +-- run_002_migration.py
|       +-- run_migration_003.py
|       +-- validate_schema.py
|
+-- migrations/                        # SQL MIGRATION FILES
|   +-- *.sql                          # Schema migrations
|
+-- docs/                              # DOCUMENTATION
|   +-- FILE_TREE.md                   # This file - backend structure
|   +-- FRONTEND_TREE.md               # Frontend SvelteKit structure
|   +-- DATABASE_SCHEMA_MAP.md         # Full database schema reference
|   +-- driscoll/                      # Context stuffing source docs
|       +-- all_manuals.txt            # Combined manual text
|       +-- sales_warehouse.txt        # Sales/warehouse context
|
+-- Manuals/                           # SOURCE DOCUMENTS
|   +-- Driscoll/
|       +-- chunks/                    # JSON chunks (enriched)
|       +-- questions_generated/       # LLM-generated questions
|       +-- Purchasing/
|       +-- Sales/
|       +-- Warehouse/
|
+-- data/                              # RUNTIME DATA
|   +-- chat_exchanges/                # Chat session logs
|   +-- reasoning_traces/              # Cognitive traces
|   +-- memory_nodes/                  # Session memory snapshots
|   +-- corpus/                        # Memory corpus
|   +-- indexes/                       # Cluster indexes
|   +-- archive/                       # Archived data
|
+-- RECON_OUTPUT/                      # RECONNAISSANCE OUTPUTS
|   +-- *.yaml                         # System mapping files
|
+-- # ROOT-LEVEL SCRIPTS
|
+-- voice_transcription.py             # Real-time STT (Deepgram WebSocket)
+-- health_check.py                    # System health check
+-- ingest_cli.py                      # CLI for ingestion
+-- embed_and_insert.py                # Batch embed + DB insert
+-- enrich_sales_chunks.py             # Sales manual enrichment
+-- check_embeddings.py                # Verify embeddings
+-- run_migration.py                   # Migration runner
+-- run_heuristics_migration.py        # Heuristics migration
+-- demo_heuristics.py                 # Heuristics demo
+-- test_*.py                          # Test files
|
+-- # CONFIG FILES
|
+-- invariants.md                      # System invariants
+-- requirements.txt                   # Python dependencies
+-- pyproject.toml                     # Python project config
+-- Procfile                           # Railway/Heroku process file
+-- pull_dd_specs.sh                   # DD spec pulling script
+-- SKILL.md                           # Skill definitions
+-- .env                               # Environment variables
+-- .env.example                       # Env template
|
+-- .claude/                           # CLAUDE AGENT CONTEXT
    +-- CHANGELOG.md                   # Development changelog
```

## Quick Start

```python
# The one import to rule them all:
from core.protocols import cfg, get_auth_service, CogTwin, MemoryNode, AsyncEmbedder

# Or explicit module imports:
from memory.retrieval import DualRetriever
from memory.embedder import AsyncEmbedder
from auth.auth_service import authenticate_user
from core.tenant_loader import load_tenant_config
```

## Architecture Flow

```
User Query
    |
main.py (FastAPI/WebSocket) + tenant middleware
    |
tenant_middleware.py (domain -> tenant routing)
    |
cog_twin.py / enterprise_twin.py (orchestrator)
    +-- enterprise_rag.py (fetch context)
    +-- context_stuffing.py (static context)
    +-- cache.py (Redis response cache)
    +-- venom_voice.py (format output)
    |
LLM API (via model_adapter.py)
    |
Response + Metrics Collection
```

## Multi-Tenant Architecture

```
Request (app.cogzy.dev | driscollintel.com)
    |
tenant_middleware.py (extract domain)
    |
tenant_loader.py (load clients/*.yaml)
    |
TenantContext (auth mode, RAG config, branding)
    |
Route to: personal_auth_routes | sso_routes
```

## Key Design Patterns

### Dual-Embedding Retrieval (Hybrid RAG)
- **Content embedding**: 30% weight
- **Questions embedding**: 50% weight
- **Tag bonus**: 20% weight

### Threshold-Based Results
- Return EVERYTHING above 0.6 similarity
- Pre-filter via GIN indexes before vector search

### Multi-Tenant Routing
- Domain-based tenant detection
- YAML-based tenant configuration
- Separate auth flows per tier (enterprise SSO vs personal email)

### Personal vs Enterprise Auth
- **Personal (Cogzy)**: Email/password + Google OAuth
- **Enterprise**: Azure AD SSO + division-based access
