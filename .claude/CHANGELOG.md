# CogTwin Development Changelog

## [2025-12-23 18:30] - Documentation Update
- **Modified**: `docs/FILE_TREE.md` - Complete backend structure update with observability suite
- **Modified**: `docs/FRONTEND_TREE.md` - Complete frontend structure with voice & observability
- **Added**: Notes on recent changes (2025-12-21 to 2025-12-23 sprint)
- **Added**: Store dependencies diagram, performance optimizations
- **Summary**: Comprehensive documentation refresh to reflect 3-day development sprint

## [2025-12-23] - Voice Transcription (Deepgram)
- **Added**: `voice_transcription.py` - Real-time STT with Deepgram WebSocket bridge
- **Modified**: `core/main.py` - voice_start/chunk/stop handlers + cleanup on disconnect
- **Modified**: Frontend voice.ts store + ChatOverlay.svelte mic button UI
- **Status**: Complete, requires DEEPGRAM_API_KEY env var to activate
- **Commits**: (pending commit)

## [2025-12-23] - Phase 2 Observability Suite
- **Added**: Distributed tracing (migrations/008, core/tracing.py, frontend traces UI)
- **Added**: Structured logging (migrations/009, core/structured_logging.py, frontend logs UI)
- **Added**: Alert engine (migrations/010, core/alerting.py, frontend alerts UI)
- **Added**: Admin navigation for Traces/Logs/Alerts pages
- **Modified**: core/main.py - observability routers + startup/shutdown handlers
- **Commits**: a36558d, 957bd66, b332dd7

## [2025-12-23] - Session Persistence & Reconnect
- **Added**: localStorage session persistence (sessionId, messages, department, TTL)
- **Added**: ConnectionStatus component with reconnect UI
- **Modified**: session store with connectionState tracking
- **Modified**: +layout.svelte - integrated ConnectionStatus banner
- **Commits**: 99cadad, 8f14cbf

## [2025-12-23] - Audit Logging System
- **Added**: migrations/007_audit_log.sql - audit_log table with indexes
- **Added**: core/audit.py - AuditLogger with batched writes
- **Modified**: auth_service.py - audit trail on all auth operations
- **Commits**: 89a7fac, d97db89

## [2025-12-23] - Bulk User Import
- **Added**: auth/bulk_import_routes.py - CSV upload + user provisioning
- **Added**: Frontend bulk import UI in admin/users page
- **Commits**: 87082f5, dc65469

## [2025-12-23] - Observability Suite Phase 1
- **Added**: migrations/006_observability.sql - metrics + system_health tables
- **Added**: core/metrics.py - MetricsCollector with PostgreSQL + Redis
- **Added**: core/health.py - HealthMonitor with /health endpoints
- **Added**: Frontend admin/system page with real-time metrics + health checks
- **Modified**: core/main.py - metrics middleware + health routes
- **Commits**: 3c21d48, 0b7fb2b

## [2025-12-23] - WebSocket Performance Upgrades
- **Added**: WebSocket connection pool + warmup on startup
- **Added**: Redis-backed response cache (1-hour TTL)
- **Added**: Streaming response with cognitive state updates
- **Modified**: createWebSocketStore() - added missing return statement
- **Commits**: 90ee566, 2dd48b8, fd52856

## [2025-12-23] - Hybrid RAG Search
- **Added**: Question embedding-based search (dual vector search)
- **Modified**: enterprise_rag.py - query + synthetic questions as search vectors
- **Commits**: fe07345

## [2025-12-23] - Security Hardening
- **Fixed**: Auth bypass vulnerability - division-based access control
- **Fixed**: Message division validation + zero-chunk guard
- **Fixed**: Type standardization across backend/frontend (string division IDs)
- **Fixed**: Division race condition - queue set_division until verified
- **Fixed**: RAG department filter + permission hierarchy
- **Commits**: b0dbfa7, 2f6f1a0, f02939a, e7340c5, 7fca20e

## [2025-12-22] - Model Configuration
- **Fixed**: grok-4-1-fast → grok-4-1-fast-reasoning (400 error)
- **Added**: model_adapter reads from XAI_MODEL env var
- **Commits**: ea65566, c187c90

## [2025-12-22] - RAG Architecture Lockdown
- **Fixed**: Threshold-only RAG (removed top_k SQL filtering)
- **Fixed**: Model adapter API corrections
- **Added**: Trust barriers for context formatters (Grok LAW vs context awareness)
- **Commits**: 74bf694, 38d6f7a, b8249f4

## [2025-12-22] - Smart RAG Pipeline
- **Added**: Synthetic question generation during ingestion
- **Added**: Dual embedding strategy (content + questions)
- **Modified**: semantic_tagger.py + smart_tagger.py
- **Commits**: 12b1b0a

## [2025-12-22] - Twin Routing & Security
- **Fixed**: Twin routing logic + security hardening
- **Added**: Dev governance + stub departments endpoint
- **Commits**: 9f8e2db, 50270be

## [2025-12-22] - Auth Schema Consolidation (2-Table Design)
- **Refactor**: 2-table auth (users + division_access) - eliminated 7 legacy tables
- **Fixed**: All imports for new core/ structure
- **Fixed**: Procfile path (main → core.main)
- **Fixed**: Null bytes in __init__ files
- **Commits**: b90cc85, ab22a8a, 35883a7, 400a763, 38f524c, 6e205be, da7b1d9

## [2025-12-22] - Memory Architecture Consolidation
- **Added**: protocols.py - nuclear elements map (core knowledge framework)
- **Refactor**: Memory architecture + protocol enforcement
- **Fixed**: Old table references (auth_service, tenant_service, enterprise_rag)
- **Commits**: 81f2fae, 466d4de, 76d8b10, f26d4db, 3bf678d

## [2025-12-21] - Frontend Store Fixes
- **Fixed**: Duplicate azureEnabled export in auth store
- **Fixed**: localStorage SSR compatibility (browser check wrapper)
- **Fixed**: Restore clean state + re-apply table fixes
- **Commits**: ace1721, 653d1e8, 6cc8ca1

## [2025-12-21] - Azure DB Migration
- **Fixed**: DB host → cogtwin.postgres.database.azure.com
- **Commits**: a90f2ba

## [2025-12-21] - Auth & Twin Router
- **Added**: User login guide documentation
- **Fixed**: Auth-based twin router (select orchestrator by deployment mode)
- **Fixed**: Remove redundant domain/dept checks (trust Azure AD)
- **Fixed**: EnterpriseTwin config
- **Commits**: 1bbd2b1, c5c2e55, 2cd60d2, 6ceb6ea

---

## Archive Note
Previous CHANGELOG was 2798 lines covering a major sprint. Consolidated to match git history for ongoing maintenance. Major features from sprint:
- Voice transcription (Deepgram integration)
- Phase 1 & 2 Observability (metrics, tracing, logging, alerting)
- Session persistence + reconnect UX
- Audit logging
- Bulk user import
- WebSocket performance upgrades
- Hybrid RAG with question embeddings
- Security hardening (auth bypass, division validation, type safety)
- RAG architecture lockdown (threshold-only)
- Smart RAG pipeline (synthetic questions)
- 2-table auth schema refactor
- Memory architecture consolidation
- Azure migration

Total commits: 139
Sprint dates: 2025-12-21 to 2025-12-23
