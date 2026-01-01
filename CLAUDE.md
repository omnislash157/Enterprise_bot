# Enterprise Bot - Claude Code Project Configuration

## Project Overview

Multi-tenant AI assistant platform with dual modes:
- **EnterpriseTwin**: Policy-first corporate assistant for Driscoll Foods
- **CogTwin/Cogzy**: Cognitive personal tier with metacognition

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI + WebSocket (Python 3.10+) |
| Frontend | SvelteKit 1.30 + Threlte (3D) |
| Database | Azure PostgreSQL + pgvector |
| Cache | Redis |
| LLM | Grok 4.1 Fast Reasoning (2M token window) |
| Auth | Azure AD SSO (enterprise), Email/Google OAuth (personal) |

## Critical Architecture Rules

### 1. Protocol Imports (MANDATORY)
All cross-module imports MUST go through `core/protocols.py`:
```python
# CORRECT
from core.protocols import cfg, get_auth_service, CogTwin, MemoryNode

# WRONG - never import directly from internal modules
from core.auth_service import get_auth_service
```

### 2. Twin Selection
Use `get_twin()` from `core/main.py` - never instantiate twins directly:
```python
from core.main import get_twin
twin = get_twin()  # Routes based on cfg('deployment.mode')
```

### 3. TenantContext Field Names
The user email field is `.user_email` NOT `.email`:
```python
context.user_email  # CORRECT
context.email       # WRONG - will fail
```

### 4. Config Access
Use `cfg()` with dot notation, never access config dict directly:
```python
tier = cfg('deployment.tier')
enabled = cfg('features.context_stuffing.enabled', True)
```

### 5. Enterprise Schema
Only 2 tables for auth:
- `enterprise.tenants` - Multi-tenant config
- `enterprise.users` - Users with `department_access[]` array

NO separate departments table - use the array.

## Directory Structure

```
enterprise_bot/
├── core/              # Backend brain: FastAPI, twins, config
├── auth/              # Authentication & authorization
├── memory/            # Cognitive memory system (CogTwin only)
├── db/migrations/     # PostgreSQL migrations
├── clients/           # Tenant YAML configs
├── frontend/          # Enterprise SvelteKit app
├── frontend-cogzy/    # Personal tier SvelteKit app
├── docs/              # Documentation
└── data/              # Runtime data (traces, sessions)
```

## Key Files

| File | Purpose |
|------|---------|
| `core/main.py` | FastAPI app, WebSocket handler |
| `core/protocols.py` | Nuclear elements - only import file |
| `core/config_loader.py` | Config helper (cfg function) |
| `core/enterprise_twin.py` | Policy-first corporate mode |
| `core/cog_twin.py` | Cognitive orchestrator |
| `auth/auth_service.py` | Auth operations singleton |
| `.claude/CHANGELOG.md` | Full development history |
| `.claude/CHANGELOG_COMPACT.md` | Quick session reference |

## Development Workflow

1. **RECON** - Understand before touching
2. **SPEC** - Build sheet before coding
3. **BUILD** - Implement from spec
4. **VALIDATE** - Test before commit
5. **SHIP** - Update changelog

## Run Commands

```bash
# Backend
uvicorn core.main:app --host 0.0.0.0 --port 8000

# Frontend (enterprise)
cd frontend && npm run dev

# Frontend (personal)
cd frontend-cogzy && npm run dev

# Python tests
pytest -xvs tests/test_file.py

# Type check frontend
cd frontend && npm run check
```

## Environment Variables

**Required:**
- `XAI_API_KEY` - Grok API
- `AZURE_PG_CONNECTION_STRING` - Database
- `AZURE_AD_TENANT_ID`, `AZURE_AD_CLIENT_ID`, `AZURE_AD_CLIENT_SECRET` - SSO

**Optional:**
- `DEEPGRAM_API_KEY` - Voice transcription
- `DEEPINFRA_API_KEY` - BGE-M3 embeddings
- `ANTHROPIC_API_KEY` - Claude fallback

## WebSocket Protocol

```json
// Client -> Server
{"action": "query", "user_input": "...", "session_id": "uuid", "department": "warehouse"}

// Server -> Client (streaming)
{"type": "status", "phase": "searching"}
{"type": "chunk", "content": "text..."}
{"type": "done"}
```

## Changelog Location

Session history in `.claude/CHANGELOG.md` and `.claude/CHANGELOG_COMPACT.md`

Update changelog with every shipped feature:
```markdown
## [YYYY-MM-DD HH:MM] - Feature Name
### Files Modified
- file1.py - Description
### Summary
Brief description of what was done.
```
