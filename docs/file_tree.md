# Enterprise Bot - File Tree

Cold start reference for AI agents. Load `core/protocols.py` for the 37 nuclear exports.

```
enterprise_bot/
│
├── core/                              # BRAIN - Start here
│   ├── protocols.py                   # THE NUCLEAR MAP - 37 stable exports, import from here
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
│       │── # SMART RAG PIPELINE (2024-12-22) ────────────────────────
│       │
│       ├── smart_tagger.py            # 4-pass LLM enrichment (tags, questions, scores, concepts)
│       ├── semantic_tagger.py         # Regex/keyword semantic classification (no LLM)
│       ├── relationship_builder.py    # Cross-chunk relationships (prereqs, see_also, contradictions)
│       ├── enrichment_pipeline.py     # Orchestrator for full ingest flow
│       ├── smart_retrieval.py         # Question→Question similarity retrieval
│       └── test_smart_rag.py          # Test harness for smart RAG pipeline
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
│   ├── 003_smart_documents.sql        # Smart RAG schema (47 cols, 17 indexes, 4 functions)
│   ├── 003b_enrichment_columns.sql    # Additional enrichment columns for RAG
│   │
│   └── migrations/                    # SQL migration files (legacy)
│       ├── add_analytics_indexes.sql  # Performance indexes
│       ├── add_azure_oid.sql          # Azure Object ID column
│       └── verify_azure_oid.sql       # Verification query
│
├── docs/                              # DOCUMENTATION
│   ├── FILE_TREE.md                   # This file - backend structure
│   ├── FRONTEND_TREE.md               # Frontend SvelteKit structure
│   ├── EMBEDDER_RAG_RECON.md          # Embedder/RAG forensic audit
│   ├── CONFIG_DEEP_RECON.md           # Config system deep recon
│   ├── INGESTION_MAPPING.md           # JSON → Schema field mapping
│   ├── SMART_RAG_QUERY.sql            # Retrieval pattern examples
│   ├── SMART_RAG_DESIGN_SUMMARY.md    # Architecture overview
│   └── *.md                           # Various implementation docs
│
├── Manuals/                           # SOURCE DOCUMENTS
│   └── Driscoll/                      # Company process manuals
│       ├── *.docx                     # Original Word documents
│       ├── *.json                     # JSON chunks (pre-enriched)
│       └── questions_generated/       # LLM-generated synthetic questions
│
├── frontend/                          # SVELTEKIT APP (see FRONTEND_TREE.md)
│
├── archive/                           # Deprecated code (don't load)
│
│── # ROOT-LEVEL SCRIPTS ────────────────────────────────────────────
│
├── health_check.py                    # System health check runner
├── ingest_cli.py                      # CLI for ingestion operations
├── embed_and_insert.py                # Batch embed + DB insert for enriched chunks
├── enrich_sales_chunks.py             # Sales manual enrichment script
│
│── # CONFIG FILES ────────────────────────────────────────────────
│
├── invariants.md                      # System invariants and constraints
├── requirements.txt                   # Python dependencies
├── pyproject.toml                     # Python project config
├── Procfile                           # Railway/Heroku process file
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
from memory.ingest.smart_tagger import tag_with_questions
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
smart_retrieval.py (dual-embedding retrieval: content 30% + questions 50% + tags 20%)
```

## Key Design Patterns

### Dual-Embedding Retrieval
- **Content embedding**: 30% weight (what the chunk says)
- **Questions embedding**: 50% weight (what questions it answers)
- **Tag bonus**: 20% weight (semantic classification match)

### Threshold-Based Results
- Return EVERYTHING above 0.6 similarity (not arbitrary top-N)
- Pre-filter via GIN indexes before vector search
- Complete context, not filtered glimpse
