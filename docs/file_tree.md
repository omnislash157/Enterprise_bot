# Enterprise Bot - File Tree

Cold start reference for AI agents. Load `core/protocols.py` for the 37 nuclear exports.

**Last Updated**: 2025-12-23 (Post-Observability Suite & Voice Integration)

```
enterprise_bot/
│
├── core/                              # BRAIN - Start here
│   ├── protocols.py                   # THE NUCLEAR MAP - 37 stable exports, import from here
│   ├── cog_twin.py                    # Main orchestrator, pairs with venom_voice.py
│   ├── venom_voice.py                 # Personality engine, prompt injection, streaming
│   ├── enterprise_twin.py             # Corporate mode twin (policy-first, no personality)
│   ├── enterprise_rag.py              # RAG pipeline - hybrid search (content + questions), threshold-only
│   ├── enterprise_tenant.py           # TenantContext dataclass for multi-tenant
│   ├── model_adapter.py               # LLM factory - Grok/Claude/OpenAI abstraction
│   ├── schemas.py                     # MemoryNode, EpisodicMemory, Enums (Source, IntentType, etc)
│   ├── config_loader.py               # cfg() helper, yaml loading
│   ├── cache.py                       # Redis-backed response cache (1-hour TTL)
│   ├── main.py                        # FastAPI app, WebSocket, route mounting, observability
│   │
│   │── # OBSERVABILITY SUITE (Phase 2 - 2025-12-23) ──────────────────
│   │
│   ├── metrics_collector.py           # MetricsCollector - PostgreSQL + Redis metrics
│   ├── tracing.py                     # Distributed tracing with OpenTelemetry patterns
│   ├── structured_logging.py          # Structured JSON logging with context
│   └── alerting.py                    # Alert engine - threshold monitoring, notifications
│
├── auth/                              # AUTHENTICATION & TENANCY
│   ├── auth_service.py                # User CRUD, authenticate_user() - 2-table design
│   ├── audit_service.py               # AuditLogger - batched writes, compliance tracking
│   ├── tenant_service.py              # Department content, division access control
│   ├── azure_auth.py                  # Azure AD/Entra ID SSO token validation
│   ├── sso_routes.py                  # OAuth callbacks (/api/auth/*)
│   ├── admin_routes.py                # Admin API (/api/admin/*) - user mgmt, batch import
│   │
│   │── # OBSERVABILITY ROUTES ────────────────────────────────────
│   │
│   ├── metrics_routes.py              # Metrics API (/api/admin/metrics)
│   ├── tracing_routes.py              # Traces API (/api/admin/traces)
│   ├── logging_routes.py              # Logs API (/api/admin/logs)
│   ├── alerting_routes.py             # Alerts API (/api/admin/alerts)
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
│   └── ingest/                        # INGESTION SUBPACKAGE (Smart RAG Pipeline)
│       ├── __init__.py                # Exports: IngestPipeline, ChatParserFactory
│       ├── pipeline.py                # Main ingestion orchestrator
│       ├── chat_parser.py             # Parse chat across LLM providers
│       ├── doc_loader.py              # Load documents for RAG
│       ├── docx_to_json_chunks.py     # Convert DOCX manuals to JSON chunks
│       ├── batch_convert_warehouse.py # Batch convert Driscoll manuals
│       ├── ingest_to_postgres.py      # Load chunks into PostgreSQL
│       ├── json_chunk_loader.py       # JSON chunk parsing utilities
│       │
│       │── # SMART RAG PIPELINE (2025-12-22) ────────────────────────
│       │
│       ├── smart_tagger.py            # 4-pass LLM enrichment (tags, questions, scores, concepts)
│       ├── semantic_tagger.py         # Regex/keyword semantic classification (no LLM)
│       ├── relationship_builder.py    # Cross-chunk relationships (prereqs, see_also, contradictions)
│       ├── enrichment_pipeline.py     # Orchestrator for full ingest flow
│       ├── smart_retrieval.py         # Question→Question similarity retrieval
│       └── test_smart_rag.py          # Test harness for smart RAG pipeline
│
├── claude_sdk_toolkit/                # CLAUDE SDK INTEGRATION
│   ├── claude_chat.py                 # SDK agent REPL - interactive sessions
│   ├── claude_run.py                  # One-shot executor for scripts
│   ├── claude_cli.py                  # CLI interface for SDK
│   ├── db_tools.py                    # Database tools exposed to SDK
│   ├── db_tools_sdk.py                # SDK-compatible DB tool wrappers
│   ├── memory_tools.py                # Memory system tools
│   ├── memory_tools_sdk.py            # SDK-compatible memory wrappers
│   ├── railway_tools.py               # Railway deployment tools
│   ├── railway_tools_sdk.py           # SDK-compatible Railway wrappers
│   └── convert_tools.py               # Tool conversion utilities
│
├── db/                                # DATABASE SCHEMAS & MIGRATIONS
│   ├── 003_smart_documents.sql        # Smart RAG schema (47 cols, 17 indexes, 4 functions)
│   ├── 003b_enrichment_columns.sql    # Additional enrichment columns for RAG
│   │
│   └── migrations/                    # SQL MIGRATION FILES
│       └── 004_audit_log.sql          # Audit logging table + indexes
│       # NOTE: Observability migrations (006-010) applied but files not in repo
│       # - 006_observability.sql (metrics + system_health tables)
│       # - 007_audit_log.sql (consolidated audit schema)
│       # - 008_tracing.sql (distributed tracing tables)
│       # - 009_logging.sql (structured logging tables)
│       # - 010_alerting.sql (alert engine tables)
│
├── docs/                              # DOCUMENTATION
│   ├── FILE_TREE.md                   # This file - backend structure
│   ├── FRONTEND_TREE.md               # Frontend SvelteKit structure
│   │
│   └── recon/                         # RECONNAISSANCE DOCS
│       ├── README.md                  # Recon index
│       ├── EXECUTIVE_SUMMARY.md       # High-level system overview
│       ├── BACKEND_AUTH_MAP.md        # Auth system mapping
│       ├── DATABASE_ACTUAL_STATE.md   # Current DB schema
│       ├── DATABASE_EXPECTED_SCHEMA.md # Desired DB schema
│       ├── DATABASE_GAP_ANALYSIS.md   # Schema reconciliation
│       ├── ADMIN_PORTAL_RECON.md      # Admin portal capabilities
│       └── ENVIRONMENT_REQUIREMENTS.md # Env var requirements
│
├── Manuals/                           # SOURCE DOCUMENTS
│   └── Driscoll/                      # Company process manuals
│       ├── *.docx                     # Original Word documents
│       ├── *.json                     # JSON chunks (pre-enriched)
│       ├── Warehouse/                 # Enriched chunks warehouse
│       │   ├── chunks/                # JSON chunk files
│       │   └── *_enriched.json        # LLM-enriched versions
│       └── staging/                   # Pre-processing staging area
│
├── frontend/                          # SVELTEKIT APP (see FRONTEND_TREE.md)
│
├── archive/                           # Deprecated code (don't load)
│
│── # ROOT-LEVEL SCRIPTS ────────────────────────────────────────────
│
├── voice_transcription.py             # Real-time STT with Deepgram WebSocket bridge
├── health_check.py                    # System health check runner
├── ingest_cli.py                      # CLI for ingestion operations
├── embed_and_insert.py                # Batch embed + DB insert for enriched chunks
├── enrich_sales_chunks.py             # Sales manual enrichment script
├── check_embeddings.py                # Verify embeddings in database
├── run_migration.py                   # Database migration runner
├── test_observability.py              # Observability suite test harness
│
│── # CONFIG FILES ────────────────────────────────────────────────
│
├── invariants.md                      # System invariants and constraints
├── requirements.txt                   # Python dependencies
├── pyproject.toml                     # Python project config
├── Procfile                           # Railway/Heroku process file (core.main)
├── email_whitelist.json               # Allowed email domains
├── .gitignore
├── README.md
│
└── .claude/                           # CLAUDE AGENT CONTEXT
    └── CHANGELOG.md                   # Development changelog (2798 lines)
```

## Quick Start

```python
# The one import to rule them all:
from core.protocols import cfg, get_auth_service, CogTwin, MemoryNode, AsyncEmbedder

# Or explicit module imports:
from memory.retrieval import DualRetriever
from memory.embedder import AsyncEmbedder
from memory.ingest.pipeline import IngestPipeline
from memory.ingest.smart_tagger import tag_with_questions
from auth.auth_service import authenticate_user
from core.metrics_collector import MetricsCollector
from core.tracing import trace_span
from core.structured_logging import get_logger
```

## Architecture Flow

```
User Query
    ↓
main.py (FastAPI/WebSocket) + observability middleware
    ↓
cog_twin.py (orchestrator) + cognitive state streaming
    ├── retrieval.py (fetch memories)
    ├── memory_pipeline.py (ingest response)
    ├── cache.py (Redis response cache)
    └── venom_voice.py (format output)
    ↓
LLM API (via model_adapter.py)
    ↓
Response + Memory Ingest + Metrics Collection
```

## Smart RAG Pipeline Flow

```
Source DOCX
    ↓
docx_to_json_chunks.py (chunk + parse)
    ↓
smart_tagger.py (LLM enrichment: questions, tags, concepts)
    ↓
semantic_tagger.py (regex classification: verbs, entities, actors)
    ↓
relationship_builder.py (cross-chunk links: prereqs, see_also)
    ↓
embed_and_insert.py (BGE-M3 embeddings + PostgreSQL insert)
    ↓
enterprise_rag.py (hybrid retrieval: content 30% + questions 50% + tags 20%)
```

## Key Design Patterns

### Dual-Embedding Retrieval (Hybrid RAG)
- **Content embedding**: 30% weight (what the chunk says)
- **Questions embedding**: 50% weight (what questions it answers)
- **Tag bonus**: 20% weight (semantic classification match)

### Threshold-Based Results
- Return EVERYTHING above 0.6 similarity (not arbitrary top-N)
- Pre-filter via GIN indexes before vector search
- Complete context, not filtered glimpse

### Observability Suite Architecture
- **Metrics**: PostgreSQL + Redis storage, real-time aggregation
- **Tracing**: Distributed tracing with span correlation
- **Logging**: Structured JSON logs with context propagation
- **Alerting**: Threshold monitoring with notification hooks

### Session Persistence
- localStorage session management with TTL
- Automatic reconnect with exponential backoff
- Connection status UI with real-time updates

### Security Hardening
- 2-table auth schema (users + division_access)
- Division-based access control with validation
- Audit logging on all auth operations
- Type-safe division IDs across stack

## Recent Major Changes (2025-12-21 to 2025-12-23)

### Phase 2 Observability Suite
- Distributed tracing system (core/tracing.py)
- Structured logging (core/structured_logging.py)
- Alert engine (core/alerting.py)
- Admin UI pages for traces/logs/alerts

### Voice Transcription
- Real-time STT via Deepgram WebSocket
- voice_transcription.py bridge service
- Frontend voice store + mic button UI
- Requires DEEPGRAM_API_KEY env var

### Session Persistence
- localStorage session management
- ConnectionStatus component with reconnect UI
- TTL-based session cleanup

### Audit Logging
- Batched audit writes to PostgreSQL
- Audit trail on all auth operations
- Admin audit log viewer

### Bulk User Import
- CSV upload endpoint in admin_routes.py
- BatchImportModal.svelte component
- User provisioning with division access

### WebSocket Performance
- Connection pool with warmup
- Redis response cache (1-hour TTL)
- Streaming cognitive state updates

### Security Hardening
- Auth bypass vulnerability fixed
- Division validation + race condition fixes
- Type standardization (string division IDs)
- RAG department filtering

### RAG Architecture Lockdown
- Threshold-only retrieval (removed top_k filtering)
- Model adapter API corrections
- Trust barriers for context formatters
