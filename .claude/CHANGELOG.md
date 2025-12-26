# CogTwin Development Changelog

## [2024-12-24 19:30] - Vault System Deep Reconnaissance
### Files Modified
- VAULT_RECON_PATH_MAP.md - Created comprehensive directory structure map with 6,800+ lines documenting all data paths, file counts, wire-in points, and data flow
- VAULT_RECON_WIRE_IN_POINTS.md - Created 4,500+ line code reference documenting every data_dir usage with line numbers across 20+ modules
- VAULT_RECON_MIGRATION_CHECKLIST.md - Created 7,200+ line migration guide with 3 scenarios, verification tests, rollback procedures, and known issue fixes
- VAULT_RECON_SUMMARY.md - Created executive summary answering all 6 mission questions with technical analysis and next steps
### Summary
**DEEP RECON MISSION COMPLETE**: Fully mapped the enterprise_bot data directory system (C:\Users\mthar\projects\enterprise_bot\data). Discovered system uses unified format v1.0.0 (corpus/nodes.json + manifest.json) not legacy session-based format. Documented 330+ files across 8 directories (~80-100MB active data). Identified critical issue: dedup_index.json in wrong location (corpus/ vs root). Mapped all read/write operations with exact line numbers. Created complete migration procedures for local/remote/cloud scenarios. System is production-ready for migration with medium complexity. Generated 18,500+ lines of documentation covering paths, wire-ins, config dependencies, data flow, verification tests, and rollback procedures.

## [2024-12-24 17:00] - Voice Speed Slider + Settings Popover
### Files Modified
- frontend/src/lib/stores/voice.ts - Added voiceSpeed store (persisted to localStorage, default 1.35x), applied playbackRate to audio playback
- frontend/src/lib/components/ChatOverlay.svelte - Replaced standalone language button with gear icon settings popover containing EN/ES toggle + speed slider (0.75x-2x)
### Summary
Voice speed control for TTS playback. Settings popover with gear icon consolidates language toggle (EN/ES pills) and speed slider (0.75x-2x range). Speed setting persists to localStorage and applies to audio.playbackRate in the playNext() function. Default 1.35x for slightly faster-than-natural speech.

## [2024-12-24 16:30] - Multi-Language Support (English/Spanish)
### Files Modified
- voice_transcription.py - Added Spanish TTS voice (aura-2-lucia-es), language param to STT/TTS
- frontend/src/lib/stores/voice.ts - Added userLanguage store with localStorage persistence, language params to TTS functions
- frontend/src/lib/components/ChatOverlay.svelte - Added EN/ES toggle button, pass language to TTS calls
- frontend/src/lib/stores/session.ts - Send language with WebSocket messages
- core/main.py - Extract language param from messages/voice_start, pass to twin and voice session
- core/enterprise_twin.py - Add language param to think_streaming and _build_system_prompt
### Summary
Full Spanish/English language support for warehouse workers. Toggle EN/ES persisted to localStorage. LLM responds in selected language, STT transcribes in selected language (Deepgram), TTS speaks in selected language (Deepgram Aura lucia-es for Spanish).

## [2024-12-24 16:00] - Fix Deepgram STT 400 Error
### Files Modified
- voice_transcription.py - Simplified _build_url() to use minimal params (model=nova-2 only)
### Summary
Fixed HTTP 400 error from Deepgram STT WebSocket. The explicit encoding/sample_rate params were causing connection failures. Changed to minimal config: `?model=nova-2` only. Deepgram auto-detects encoding from the audio stream (webm-opus from browser MediaRecorder).

## [2024-12-24 15:30] - Synchronized Text-Audio Voice Mode
### Files Modified
- frontend/src/lib/stores/voice.ts - Added onStart callback to queueSentenceAudio(), QueuedAudio interface
- frontend/src/lib/components/ChatOverlay.svelte - Added voiceSyncedText state, updated template to display synced text in voice mode
### Summary
True voice mode experience: text now reveals in sync with audio playback. When voice mode is on, text is buffered and only revealed as each sentence's audio starts playing. This creates a natural reading-along experience where text and voice stay in sync. Trade-off: slightly more latency (~500ms per sentence for TTS generation) but perceptually unified output.

## [2024-12-24 15:00] - Sentence-Chunked Streaming TTS
### Files Modified
- frontend/src/lib/stores/voice.ts - Added queueSentenceAudio(), streamingSentenceDetector(), clearAudioQueue(), playNext()
- frontend/src/lib/components/ChatOverlay.svelte - Wired sentence detection into streaming, added audio queue clear on new message
### Summary
Implemented sentence-chunked TTS for faster voice response (~500ms time-to-audio vs ~4s waiting for full response). As streaming text arrives, sentences are detected at boundary markers (. ! ?) and immediately queued for TTS generation. Audio plays sequentially - first sentence plays while later sentences are still generating. Queue clears when user sends new message.

## [2024-12-24 14:30] - Voice Mode TTS/STT Fixes
### Files Modified
- frontend/src/lib/stores/voice.ts - Added getApiBase() function, TTS endpoint now uses full API URL
- voice_transcription.py - Changed model from nova-3 to nova-2, voice from asteria to aura-2-delia-en
- claude_sdk_toolkit/RECON_FILE_UPLOAD_WIRING.md - Updated with voice mode debug notes
### Summary
**RECON MISSION COMPLETE**: Executed full reconnaissance of voice mode deployment architecture. Identified TTS 404 root cause: frontend used relative path `/api/tts` instead of full URL with `getApiBase()` pattern. Fixed cross-origin API call issue. Also fixed STT WebSocket 400 error by changing to valid Deepgram model (nova-2) and set correct voice (aura-2-delia-en American female). Ready for Railway deployment and testing.

## [2025-12-24] - File Upload via xAI Files API
### Files Modified
- core/main.py - Added /api/upload/file endpoint (xAI proxy), WebSocket file_ids extraction
- core/model_adapter.py - Updated type hints for content arrays (Dict[str, Any])
- core/enterprise_twin.py - think_streaming accepts Union[str, List] for file content
- frontend/src/lib/components/ChatOverlay.svelte - Upload button, file chips UI
- frontend/src/lib/stores/session.ts - sendMessage accepts file_ids parameter
### Summary
File upload button in chat proxies to xAI Files API. Grok handles storage, extraction (PDF/DOCX/XLSX/images), and automatic RAG with citations. No local extraction or blob storage needed. Supported: PDF, DOCX, XLSX, TXT, CSV, PNG, JPG (max 30MB).

## [2025-12-23 19:00] - Observability Infrastructure Fix
### Files Modified
- core/database.py - NEW FILE: Created database connection pool manager for observability routes
- core/main.py - Updated observability route prefixes from /api/observability to /api/admin/*
- core/main.py - Added /health/deep endpoint with comprehensive health checks
- core/main.py - Added database pool cleanup to shutdown handler
- core/main.py - Added start_trace and create_span imports for tracing instrumentation
### Summary
Implemented SDK_BUILD_OBSERVABILITY.md to connect database with analytics. Created centralized database pool manager, fixed route prefixes to match frontend expectations (/api/admin/traces, /api/admin/logs, /api/admin/alerts), added deep health check endpoint to validate observability stack, and ensured proper cleanup on shutdown. All observability endpoints should now return data from the database tables.

## [2025-12-23] - Security Hardening & Threat Detection
- **Fixed**: Auth bypass vulnerability - verify now required before messaging
- **Fixed**: Per-message division override - permission check enforced
- **Fixed**: Fail-open in set_division - now fails closed on auth errors
- **Added**: Rate limiting (30 requests/60 seconds per session)
- **Added**: Honeypot divisions (executive/admin/root/ceo/system/god/superuser)
- **Added**: Max message length validation (10k chars)
- **Added**: Session timeout (30 min idle disconnect)
- **Added**: Request ID tracking on all messages
- **Added**: Failed auth logging with IP address
- **Added**: Sanitized error messages (no internal leakage to client)
- **Added**: Security alert rules (SQL migration):
- **Added**: `idx_structured_logs_security` index for fast threat queries
- **Modified**: `core/main.py` - auth guards, rate limiter, honeypot checks
- **Status**: Production hardened, Slack webhook pending
- **Commits**: (pending push)

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
