# WIRING_MAP.md - Enterprise Bot Architecture

**Generated:** 2025-12-18
**System Version:** Enterprise Bot v1.0.0 (Driscoll Foods)
**Fork Source:** CogTwin (Advanced cognitive architecture - intentionally disabled for enterprise simplicity)

---

## 1. ARCHITECTURE OVERVIEW

### ASCII System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FRONTEND (SvelteKit + TypeScript)                │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐              │
│  │ ChatOverlay  │  │ Login / SSO  │  │ Admin Portal│              │
│  │  (WebSocket) │  │ (Azure AD)   │  │ (Nerve Ctr) │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘              │
│         │                  │                  │                      │
│    ┌────┴──────────────────┴──────────────────┴─────┐              │
│    │         State Management (Svelte Stores)        │              │
│    │  auth | websocket | session | admin | analytics│              │
│    └────────────────────┬────────────────────────────┘              │
└─────────────────────────┼───────────────────────────────────────────┘
                          │
                    HTTPS / WSS
                          │
┌─────────────────────────┼───────────────────────────────────────────┐
│                BACKEND (FastAPI + Python)                            │
│                                                                      │
│  ┌──────────────────────┴─────────────────────────┐                │
│  │              main.py (FastAPI app)             │                │
│  │   /health  /ws/{session}  /api/*  /api/admin/* │                │
│  └──────┬────────────────────────┬──────────────┬─┘                │
│         │                        │              │                   │
│    ┌────┴────┐         ┌─────────┴──────┐  ┌───┴────────┐         │
│    │  Auth   │         │ EnterpriseTwin │  │   Admin    │         │
│    │ Service │         │  (Chat Engine) │  │   Routes   │         │
│    │  (SSO)  │         │                │  │            │         │
│    └────┬────┘         └────────┬───────┘  └───┬────────┘         │
│         │                       │              │                   │
│    ┌────┴────────┐    ┌─────────┴──────────┐  │                  │
│    │  tenant_    │    │   doc_loader.py    │  │                  │
│    │  service.py │    │  (Context Stuff)   │  │                  │
│    │  (Perms)    │    │                    │  │                  │
│    └────┬────────┘    └────────┬───────────┘  │                  │
│         │                      │               │                  │
│    ┌────┴──────────────────────┴───────────────┴────┐            │
│    │           Azure PostgreSQL Database             │            │
│    │  enterprise.users | departments | analytics    │            │
│    └─────────────────────────────────────────────────┘            │
│                                                                    │
│  ┌──────────────────────────────────────────────────┐            │
│  │          model_adapter.py (LLM Client)           │            │
│  │       xAI (Grok) | Anthropic (Claude)            │            │
│  └──────────────────────────────────────────────────┘            │
└────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

**Enterprise Bot Philosophy:**
- **"Dumb Bot" Mode:** No embeddings, no FAISS, no memory pipelines
- **Context Stuffing:** Loads department manuals directly into LLM context window
- **Fast Startup:** No ML model loading, just file reads and API calls
- **Clean Fork:** CogTwin cognitive architecture retained but disabled (see cog_twin.py)

**The Fork Story:**
- **Parent:** CogTwin - sophisticated cognitive architecture with dual-retrieval memory, metacognitive monitoring, and recursive memory pipelines
- **This Project:** Enterprise Bot - stripped down to essentials for Driscoll Foods deployment
- **Why Fork?** Client needed production-ready chatbot within 2 weeks, not R&D prototype
- **Future Path:** Memory pipeline can be re-enabled for "Pro tier" if customer wants advanced features

---

## 2. DATA FLOW PATTERNS

### Pattern 1: User Authentication Flow

```
User loads page
  → Frontend checks auth.ts store
  → If no token → Show Login component
  → User clicks "Sign in with Microsoft"
  → /api/auth/login-url (azure_auth.py)
  → Redirect to Microsoft OAuth
  → User authenticates
  → Microsoft redirects to /auth/callback
  → Frontend calls /api/auth/callback (sso_routes.py)
  → Backend validates token with Microsoft Graph
  → auth_service.py: get_or_create_user()
  → Check email domain (driscollfoods.com)
  → Auto-provision if domain valid
  → Return JWT + user permissions
  → Frontend stores in auth.ts
  → User logged in, chat enabled
```

### Pattern 2: Chat Message Flow (WebSocket)

```
User types message in ChatOverlay.svelte
  → websocket.send({type: "message", content: "..."})
  → main.py: websocket_endpoint()
  → Verify user session (optional for demo, required for prod)
  → auth_service: get_user_department_access()
  → tenant_service: get_all_content_for_context(department)
    → doc_loader: Loads .docx/.json/.csv files
    → Reads Manuals/Driscoll/{department}/*.docx
    → Returns concatenated text (stuffed context)
  → enterprise_twin.py: think(user_input, tenant)
    → Builds Venom-style system prompt
    → Injects department docs as context
    → model_adapter: calls Grok or Claude API
    → Streams response chunks
  → WebSocket sends back: {"type": "stream_chunk", "content": "..."}
  → Frontend appends to session.currentStream
  → analytics_service: log_query() - async, doesn't block response
  → Done
```

### Pattern 3: Admin User Management Flow

```
Admin clicks "Grant Access" in Admin Portal
  → Frontend: admin.ts.grantAccess(userId, department)
  → POST /api/admin/users/{user_id}/grant-access
  → admin_routes.py: grant_access_to_department()
  → auth_service: require_admin dependency
    → Check user.tier >= DEPT_HEAD
  → auth_service.grant_department_access()
    → INSERT into user_department_access table
    → Record audit log entry
  → Return success
  → Frontend refetches user list
  → UI updates with new permissions
```

### Pattern 4: Analytics Dashboard Flow

```
Admin opens Nerve Center (/admin)
  → Frontend calls /api/admin/analytics/dashboard?hours=24
  → analytics_routes.py: get_dashboard()
  → analytics_service.get_dashboard_data(hours)
    → Connection pool (2-10 connections, warm on startup)
    → Prepared queries with indexes on (department, timestamp)
    → Aggregate: total queries, avg response time, top users
    → Classify queries: 10 categories (PROCEDURAL, LOOKUP, etc.)
    → Detect frustration patterns (repeated queries, error messages)
  → Return JSON
  → Frontend renders Chart.js cyberpunk-themed charts
  → 3D neural network viz (Threlte/Three.js)
```

---

## 3. ENTRY POINTS IN main.py

**File:** `main.py` (822 lines)

### HTTP Endpoints

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/health` | GET | None | Health check |
| `/` | GET | None | API info |
| `/api/config` | GET | None | UI feature flags |
| `/api/verify-email` | POST | None | Email whitelist check (legacy) |
| `/api/whoami` | GET | Optional | Current user identity |
| `/api/departments` | GET | Optional | List departments (filtered by access) |
| `/api/content` | GET | Required | Get department docs for context |
| `/api/admin/*` | Various | Admin | User management (see admin_routes.py) |
| `/api/admin/analytics/*` | Various | Admin | Analytics queries (see analytics_routes.py) |
| `/api/auth/login-url` | GET | None | Azure AD SSO URL |
| `/api/auth/callback` | POST | None | Azure AD callback handler |

### WebSocket Endpoint

**Route:** `/ws/{session_id}`

**Message Types:**

1. **`ping`** → responds with `pong` (keepalive)
2. **`verify`** → user authentication with email
   - Checks auth_service.get_or_create_user()
   - Returns department access list
   - Logs login event to analytics
3. **`message`** → chat query
   - Calls engine.think(content, tenant)
   - Streams response chunks
   - Logs query to analytics
4. **`set_division`** → change department mid-session
   - Updates tenant context
   - Logs dept_switch event

### Startup Sequence (main.py:334)

```python
@app.on_event("startup")
async def startup_event():
    1. load_config()                    # config_loader.py
    2. email_whitelist.load()           # Legacy fallback auth
    3. engine = EnterpriseTwin()        # Chat engine initialization
    4. await engine.start()
    5. Warm analytics connection pool   # Pre-connect to PostgreSQL
```

### Middleware Stack

1. **CORSMiddleware** - Allow * origins (Railway handles CORS)
2. **GZipMiddleware** - Compress responses > 500 bytes
3. **add_timing_header** - Add `X-Response-Time` for perf tracking

---

## 4. INTEGRATION POINTS

### Frontend ↔ Backend Integration

**WebSocket Connection:**
- **File:** `frontend/src/lib/stores/websocket.ts`
- **URL:** `wss://{host}/ws/{session_id}`
- **Protocol:** JSON messages with `type` field
- **Reconnect:** Exponential backoff (1s, 2s, 4s, 8s, max 30s)

**API Shape Expected by ChatOverlay.svelte:**

**Outbound (Frontend → Backend):**
```typescript
// Verify user
{ type: "verify", email: string, division?: string }

// Send chat message
{ type: "message", content: string }

// Change department
{ type: "set_division", division: string }

// Keepalive
{ type: "ping" }
```

**Inbound (Backend → Frontend):**
```typescript
// Connection established
{ type: "connected", session_id: string, timestamp: string }

// Auth success
{ type: "verified", email: string, division: string, role: string, departments: string[] }

// Chat response chunk (streaming)
{ type: "stream_chunk", content: string, done: boolean }

// Cognitive state update (after response)
{ type: "cognitive_state", phase: string, temperature: number, ...sessionStats }

// Department changed
{ type: "division_changed", division: string }

// Error
{ type: "error", message: string }
```

### Database Integration (Azure PostgreSQL)

**Connection Details:**
- **Host:** `enterprisebot.postgres.database.azure.com`
- **Database:** `postgres`
- **Schema:** `enterprise` (primary), `cogtwin` (legacy, unused)
- **SSL:** Required
- **Credentials:** Environment variables (`AZURE_PG_USER`, `AZURE_PG_PASSWORD`)

**Key Tables:**

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `enterprise.tenants` | Tenant config (Driscoll) | id, name, slug, config |
| `enterprise.departments` | Department definitions | id, tenant_id, slug, name |
| `enterprise.users` | User accounts | id, email, role, primary_department_id |
| `enterprise.user_department_access` | Permissions matrix | user_id, department_id, access_level |
| `enterprise.audit_log` | Action audit trail | user_id, action, details, timestamp |
| `enterprise.analytics_queries` | Query logs | user_email, department, query_text, category |
| `enterprise.analytics_events` | Event logs | event_type (login, dept_switch, error) |
| `enterprise.analytics_sessions` | Session tracking | session_id, user_email, start_time |

**Connection Patterns:**
- **auth_service.py**: Direct psycopg2 with context managers
- **tenant_service.py**: Direct psycopg2 with context managers
- **analytics_service.py**: Connection pool (ThreadedConnectionPool, 2-10 conns)

### External Services

**1. xAI Grok API (Primary LLM)**
- **Endpoint:** `https://api.x.ai/v1/chat/completions`
- **Key:** `XAI_API_KEY` env var
- **Model:** `grok-4-fast-reasoning` (default)
- **Streaming:** Yes (SSE-style)
- **Adapter:** `model_adapter.py` normalizes to Anthropic-like interface

**2. Anthropic Claude API (Optional)**
- **Endpoint:** `https://api.anthropic.com/v1/messages`
- **Key:** `ANTHROPIC_API_KEY` env var
- **Model:** `claude-sonnet-4-5-20250929`
- **Streaming:** Yes (native)
- **Adapter:** `model_adapter.py` pass-through

**3. Microsoft Azure AD (SSO)**
- **Provider:** Microsoft Identity Platform (MSAL)
- **Scopes:** `User.Read`, `openid`, `profile`, `offline_access`
- **Flow:** OAuth2 authorization code
- **File:** `azure_auth.py`
- **Token Validation:** Microsoft Graph API (`https://graph.microsoft.com/v1.0/me`)

**4. Railway (Deployment)**
- **Platform:** Railway.app
- **URL:** `lucky-love-production.up.railway.app`
- **Auto-deploy:** GitHub main branch
- **Procfile:** `web: uvicorn main:app --host 0.0.0.0 --port $PORT`

---

## 5. DEEP DIVE: KEY FILES

### enterprise_twin.py (344 lines)

**Purpose:** Core chat engine - "dumb bot" that stuffs manuals into context

**Public Interface:**
```python
class EnterpriseTwin:
    def __init__(config_path=None, data_dir=None)
    async def start()
    async def stop()
    async def think(user_input, tenant, stream=True, context_content=None) -> AsyncIterator[str]
    def get_session_stats() -> Dict[str, Any]
```

**Key Imports:**
- `config_loader` - cfg(), memory_enabled(), context_stuffing_enabled()
- `enterprise_tenant.TenantContext` - Division/role context
- `model_adapter.create_adapter` - LLM client factory
- `doc_loader.DocLoader, DivisionContextBuilder` - Manual loading
- `analytics_service.get_analytics_service` - Query logging

**Config Dependencies (via cfg()):**
- `paths.data_dir` - Data directory (default: `./data`)
- `model.name` - LLM model (default: `grok-4-fast-reasoning`)
- `model.provider` - Provider (default: `xai`)
- `model.max_tokens` - Max output tokens (default: 8192)
- `tenant.default_division` - Fallback department (default: `warehouse`)
- `retrieval.process_top_k`, `retrieval.episodic_top_k`, `retrieval.session_top_k` - Unused in enterprise mode

**Key Method: `_build_venom_prompt(tenant, context_docs)`**
- Builds system prompt with Venom-style voice
- Hard grounding rules: ONLY use provided docs, no external knowledge
- Department-specific instructions
- Includes full doc context via parameter

**Context Stuffing Mechanism:**
1. Get division from tenant context
2. If `context_content` provided (Supabase override): use that
3. Else: `doc_loader.DivisionContextBuilder.get_context_for_division()`
   - Reads Manuals/Driscoll/{division}/*.docx
   - Loads .json chunk files if present
   - Concatenates with separators
4. Inject full context into system prompt
5. Stream LLM response
6. Log to analytics (async, non-blocking)

**Memory Pipeline Status:** DORMANT
- Code references memory_pipeline imports but never uses them
- `_memory_mode = False` hardcoded
- `_twin = None` (would be CogTwin instance if enabled)
- Memory count always 0 in enterprise mode

---

### enterprise_voice.py (307 lines)

**Purpose:** Voice templates for prompt injection (unused in current implementation)

**Public Interface:**
```python
class EnterpriseVoice:
    def __init__(division="default", voice_name="corporate", config=None)
    @property injection_block -> str
    def build_system_prompt(memory_count, user_zone, user_role, doc_context) -> str

# Helper functions
def get_voice_for_division(division, config) -> EnterpriseVoice
def detect_division_from_email(email, patterns) -> str
```

**Key Imports:** `yaml` (optional)

**Config Dependencies:** Reads `config["voice"]` dict for voice mappings

**Built-in Voice Templates:**
- `VOICE_CORPORATE` - Standard professional tone
- `VOICE_TROLL` - Sarcastic dispatcher persona (for operations)
- `VOICE_HELPFUL` - Friendly assistant

**Current Status:** UNUSED
- `enterprise_twin.py` builds prompts directly with `_build_venom_prompt()`
- This file provides infrastructure for config-driven voices
- Could be re-integrated for tenant-specific personality customization

---

### cog_twin.py (1567 lines)

**Purpose:** Advanced cognitive architecture - PARENT SYSTEM (disabled in enterprise fork)

**Public Interface:**
```python
class CogTwin:
    def __init__(data_dir=None, api_key=None, model=None)
    async def start()
    async def stop()
    async def think(user_input, stream=True) -> AsyncIterator[str]
    def get_cognitive_state() -> Dict[str, Any]
    def get_session_stats() -> Dict[str, Any]
    async def run_health_check() -> List[Dict[str, Any]]
```

**Key Imports (MASSIVE dependency tree):**
- `metacognitive_mirror.MetacognitiveMirror` - Cognitive state monitoring
- `retrieval.DualRetriever` - Dual-pipeline memory (process + episodic)
- `memory_pipeline.MemoryPipeline` - Recursive memory loop
- `venom_voice.VenomVoice` - System prompt builder
- `reasoning_trace.CognitiveTracer` - Reasoning provenance
- `chat_memory.ChatMemoryStore` - Persistent chat history
- `squirrel.SquirrelTool` - Temporal recall tool
- `hybrid_search.HybridSearch` - Semantic + keyword search

**Config Dependencies:** Reads from `config.yaml` (NOT config_loader.py)

**Architecture Highlights:**
1. **MetacognitiveMirror**: Monitors query patterns, detects semantic drift, predicts next memories
2. **DualRetriever**: Retrieves from process memory (what/how) and episodic memory (why/when)
3. **MemoryPipeline**: Every LLM output becomes embedded and searchable
4. **Tool System**: [GREP], [VECTOR], [EPISODIC], [SQUIRREL] - on-demand memory search
5. **Feedback Learning**: Scores responses (accuracy, temporal, tone), injects high-scored past traces into prompts
6. **Hybrid Search**: Combines semantic (FAISS) + keyword (BM25) search

**Why It's Here:**
- EnterpriseTwin was forked from this
- Code retained as "pro tier" upgrade path
- Demonstrates what's possible beyond simple context stuffing
- All advanced features disabled via `memory_enabled() -> False`

**Complexity Note:**
- CogTwin: 1567 lines, 10+ dependencies, dual memory systems, metacognitive monitoring
- EnterpriseTwin: 344 lines, 3 dependencies, direct context stuffing
- This is the difference between "ship in 2 weeks" and "ship in 6 months"

---

### venom_voice.py (1057 lines)

**Purpose:** System prompt builder and output parser for CogTwin (unused in enterprise)

**Public Interface:**
```python
class VenomVoice:
    def __init__(memory_count=0)
    def build_system_prompt(context: VoiceContext, retrieval_mode="inject") -> str
    def parse_output(raw_content: str) -> ParsedOutput

class StreamingVoice:
    def __init__(voice: VenomVoice)
    def process_chunk(chunk: str) -> str
    def finalize() -> ParsedOutput

# Enums
class OutputAction(Enum):
    RESPOND, REMEMBER, REFLECT, CODE_PROPOSAL, GREP, SQUIRREL, VECTOR, EPISODIC, ...
```

**Key Imports:** None (standalone)

**Config Dependencies:** None

**System Prompt Features:**
1. **Trust Hierarchy**: User statements > SQUIRREL > EPISODIC > VECTOR > GREP
2. **Tool Protocol**: Unified synthesis (all tools fire in parallel, one synthesis call)
3. **Artifact Generation**: Memory cards, timelines, code blocks, comparisons
4. **Retrieval Modes**: "inject" (pre-load) vs "tools" (on-demand)
5. **Analytics Block**: Visible AI self-awareness (phase, stability, patterns)

**Output Actions:**
- `[REMEMBER]` - Explicit memory storage
- `[REFLECT]` - Metacognitive observation
- `[GREP term="..."]` - Keyword search
- `[VECTOR query="..."]` - Semantic search
- `[EPISODIC query="..."]` - Conversation arc search
- `[SQUIRREL timeframe="..." search="..."]` - Temporal recall

**Usage in Enterprise:** NONE
- EnterpriseTwin uses simpler inline prompt building
- VenomVoice is CogTwin-specific
- File retained for upgrade path

---

### schemas.py (592 lines)

**Purpose:** Data models for dual-pipeline memory system (CogTwin)

**Public Interface:**
```python
# Enums
class Source(Enum): ANTHROPIC, OPENAI, GROK, GEMINI
class Role(Enum): HUMAN, ASSISTANT
class IntentType, Complexity, Urgency, EmotionalValence, ConversationMode

# Core schemas
@dataclass class MemoryNode:
    # 1:1 Q/A pair, clustered, process-focused
    id, conversation_id, sequence_index, human_content, assistant_content, ...

@dataclass class EpisodicMemory:
    # Full conversation, preserved whole
    id, title, messages, source, created_at, llm_tags, ...

@dataclass class RetrievalResult:
    # Combined result from dual-pipeline retrieval
    query, process_memories, episodic_memories, merged_context, ...

@dataclass class ClusterInfo:
    # Metadata about a process memory cluster
    cluster_id, label, description, member_count, ...

# Factory functions
def conversation_to_nodes(conversation, source) -> List[MemoryNode]
def conversation_to_episode(conversation, source) -> EpisodicMemory
```

**Key Imports:** None (pure data models)

**Config Dependencies:** None

**Answer: Is schemas.py actually used or dead code?**

**VERDICT: DEAD CODE in Enterprise Bot, ACTIVE in CogTwin**

**Usage Analysis:**
- **Used by:** `retrieval.py`, `cog_twin.py`, `memory_pipeline.py`, `ingest.py`
- **NOT used by:** `main.py`, `enterprise_twin.py`, any enterprise-specific code
- **Why it exists:** CogTwin requires dual memory pipelines
- **Enterprise status:** Imported but never instantiated

**Evidence:**
```python
# enterprise_twin.py line 92
self._memory_mode = False  # No CogTwin in this fork
self._twin = None
self.memory_count = 0
```

EnterpriseTwin has no memory nodes, no retrieval, no clustering. All of schemas.py is inert.

**Should it be deleted?** NO
- Required for upgrade path to Pro tier
- Removing it breaks import chain (retrieval.py → schemas.py)
- File is documentation of what's possible

---

### retrieval.py (919 lines)

**Purpose:** Dual retrieval engine (process + episodic memory) for CogTwin

**Public Interface:**
```python
class ProcessMemoryRetriever:
    def retrieve(query_embedding, top_k=10) -> Tuple[List[MemoryNode], List[float]]
    def retrieve_by_cluster(...) -> ...

class EpisodicMemoryRetriever:
    def retrieve(query, query_embedding, top_k=5) -> Tuple[List[EpisodicMemory], List[float]]

class DualRetriever:
    @classmethod
    def load(data_dir, manifest_file=None) -> DualRetriever
    async def retrieve(query, process_top_k=50, episodic_top_k=20) -> RetrievalResult
    def keyword_search(term) -> GrepResult
    def keyword_bm25_search(query, top_k=20) -> list
    # Cluster navigation methods
    def get_cluster_map(top_n=30) -> str
    async def find_relevant_clusters(...) -> ...
```

**Key Imports:**
- `numpy`, `faiss` (optional)
- `schemas` - MemoryNode, EpisodicMemory, RetrievalResult
- `embedder.AsyncEmbedder` - BGE-M3 embeddings
- `memory_grep.MemoryGrep` - BM25 keyword search
- `hybrid_search.HybridSearch` - Semantic + keyword combined

**Config Dependencies:** None (loads from manifest.json in data_dir)

**How it Works (CogTwin only):**
1. **Load:** Read nodes.json, episodes.json, embeddings.npy, FAISS index
2. **Process Retrieval:** NumPy cosine similarity on clustered nodes, cluster-aware boosting
3. **Episodic Retrieval:** FAISS index + heuristic pre-filter
4. **Grep:** BM25 inverted index for exact keyword matching
5. **Hybrid:** Combines semantic (FAISS) + keyword (BM25) with reciprocal rank fusion

**Enterprise Usage:** NONE
- EnterpriseTwin has no memory nodes
- No FAISS index
- No retrieval calls
- File imported but never instantiated

---

### memory_pipeline.py (516 lines)

**Purpose:** Async recursive memory ingestion for CogTwin

**Public Interface:**
```python
class ThoughtType(Enum):
    RESPONSE, REMEMBER, REFLECT, INSIGHT, DECISION, CODE_PROPOSAL, ...

@dataclass class CognitiveOutput:
    id, timestamp, thought_type, content, reasoning, ...

class MemoryPipeline:
    def __init__(embedder, data_dir, batch_interval=5.0, max_batch_size=10)
    async def start()
    async def stop()
    async def ingest(output: CognitiveOutput)
    def search_session(query_embedding, top_k=5) -> List[tuple[CognitiveOutput, float]]
    def get_session_context(last_n=5) -> List[CognitiveOutput]
```

**Key Imports:**
- `schemas.MemoryNode`
- `embedder.AsyncEmbedder`
- `streaming_cluster.StreamingClusterEngine` - Real-time cluster assignment

**Config Dependencies:** None

**How it Works (CogTwin only):**
1. LLM generates response
2. CogTwin calls `pipeline.ingest(CognitiveOutput(...))`
3. Pipeline embeds content asynchronously
4. Assigns to clusters via streaming HDBSCAN
5. Adds to session buffer (immediately searchable)
6. Batches writes to disk every 5s or 10 items
7. Next query can retrieve from session buffer

**Answer: Is memory_pipeline.py active or stubbed?**

**VERDICT: STUBBED in Enterprise Bot, ACTIVE in CogTwin**

**Enterprise Evidence:**
```python
# enterprise_twin.py line 96-98
self._memory_mode = False  # No CogTwin in this fork
self._twin = None
self.memory_count = 0
```

EnterpriseTwin never instantiates MemoryPipeline. The file is imported by cog_twin.py but unused in production.

**Why It Exists:**
- Core innovation of CogTwin: every thought becomes memory
- "The snake eating its tail" - recursive cognitive loop
- Enterprise fork disabled for simplicity
- Can be re-enabled for Pro tier

---

### doc_loader.py (605 lines)

**Purpose:** Multi-format document loader for context stuffing

**Public Interface:**
```python
class DocLoader:
    CHARS_PER_TOKEN = 4  # Approximation

    def __init__(docs_dir: Path)
    def get_docs_for_division(division: str) -> List[LoadedDoc]
    def get_all_docs() -> List[LoadedDoc]
    def get_stats() -> DocStats

class DivisionContextBuilder:
    def __init__(docs_dir_or_loader)
    def get_context_for_division(division: str, max_tokens=200000, include_shared=True) -> str
    def get_context_for_divisions(divisions: List[str], max_tokens=200000) -> str
```

**Key Imports:**
- `docx.Document` (python-docx, optional)
- `pandas` (optional)

**Config Dependencies:** None (takes docs_dir as constructor argument)

**Supported Formats:**
- `.docx` - Microsoft Word (via python-docx)
- `.json` - Chunk arrays or plain objects
- `.csv` - CSV files (via pandas or fallback)
- `.xlsx` - Excel spreadsheets (via pandas)
- `.md`, `.txt` - Plain text

**How Doc_Loader Context Stuffing Works:**

**1. File Discovery (doc_loader.py:279)**
```python
def _load_all(self):
    # Find all supported files recursively
    for ext in SUPPORTED_EXTENSIONS:
        all_files.extend(self.docs_dir.rglob(f"*{ext}"))

    # Filter temp files (start with ~)
    all_files = [f for f in all_files if not f.name.startswith("~")]
```

**2. Division Detection (doc_loader.py:249)**
```python
def _detect_division(self, docx_path: Path) -> str:
    # Get path relative to docs_dir
    # Example: Manuals/Driscoll/Warehouse/foo.docx
    #   → parts = ["Warehouse", "foo.docx"]
    #   → division = "warehouse"
    rel_path = docx_path.relative_to(self.docs_dir)
    if len(parts) >= 2:
        return parts[0].lower()  # First folder = division
```

**3. Content Extraction (doc_loader.py:119-247)**
```python
def _extract_text(self, docx_path: Path) -> str:
    doc = Document(docx_path)
    paragraphs = []

    # Extract paragraphs
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text.strip())

    # Extract tables
    for table in doc.tables:
        for row in table.rows:
            row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_text:
                paragraphs.append(" | ".join(row_text))

    return "\n\n".join(paragraphs)
```

**4. Context Building (doc_loader.py:414)**
```python
def get_context_for_division(self, division: str, max_tokens=200000):
    # Get division docs
    docs = self.loader.get_docs_for_division(division)

    # Add shared docs
    if include_shared:
        docs.extend(self.loader.get_docs_for_division("shared"))

    # Sort by token count (smaller first for better fit)
    docs.sort(key=lambda d: d.approx_tokens)

    # Build context respecting token limit
    sections = [header]
    tokens_used = 0

    for doc in docs:
        if tokens_used + doc.approx_tokens > max_tokens:
            # Truncate last doc if it doesn't fit
            remaining_tokens = max_tokens - tokens_used
            if remaining_tokens > 500:
                truncated = doc.content[:remaining_tokens * 4]
                truncated += "\n[DOCUMENT TRUNCATED]"
                sections.append(f"--- {doc.name} ---\n{truncated}")
            break

        sections.append(f"--- {doc.name} ---\n{doc.content}\n")
        tokens_used += doc.approx_tokens

    sections.append(footer)
    return "".join(sections)
```

**5. Prompt Injection (enterprise_twin.py:217-243)**
```python
async def think(self, user_input, tenant, ...):
    division = tenant.division

    # Build doc context
    doc_context = self._doc_builder.get_context_for_division(
        division,
        max_tokens=get_max_stuffing_tokens()  # Default 200k
    )

    # Build system prompt with docs
    system_prompt = self._build_venom_prompt(tenant, doc_context)

    # Generate response
    response = self.client.messages.stream(
        model=self.model,
        system=system_prompt,  # ← Docs stuffed here
        messages=[{"role": "user", "content": user_input}]
    )
```

**Token Budget:**
- Default: 200,000 tokens (~800KB text)
- Grok 4 Fast Reasoning: 256K context window
- Claude Sonnet 4.5: 200K context window
- Typical Driscoll manual: 5K-20K tokens
- Result: Can fit 10-40 manuals depending on size

**Performance:**
- File reads: ~5ms per .docx
- Total startup: ~50-100ms for full manual set
- Cached after first load
- No embedding overhead
- No vector search latency

---

### auth_service.py (300+ lines, truncated in read)

**Purpose:** User authentication, department access, permission checks

**Public Interface:**
```python
class PermissionTier(Enum):
    USER = 1
    DEPT_HEAD = 2
    SUPER_USER = 3

@dataclass class User:
    id, email, display_name, employee_id, tenant_id, role, primary_department_id, ...
    @property tier -> PermissionTier
    @property is_super_user -> bool
    @property can_manage_users -> bool

@dataclass class DepartmentAccess:
    department_id, department_slug, access_level, is_dept_head, granted_at, ...

class AuthService:
    def get_user_by_email(email) -> Optional[User]
    def get_user_by_id(user_id) -> Optional[User]
    def get_or_create_user(email, display_name, tenant_slug, default_department) -> Optional[User]
    def get_user_department_access(user) -> List[DepartmentAccess]
    def can_access_department(user, department_slug) -> bool
    def grant_department_access(actor, target_user, department_slug)
    def revoke_department_access(actor, target_user, department_slug)
    # ... many more methods
```

**Key Imports:**
- `psycopg2` - PostgreSQL driver
- `dotenv` - Environment variables

**Config Dependencies:**
- `AZURE_PG_USER`, `AZURE_PG_PASSWORD`, `AZURE_PG_HOST` - Database credentials
- `GATED_DEPARTMENTS`, `OPEN_DEPARTMENTS`, `ALLOWED_DOMAINS` - Constants

**Permission Model:**

**3-Tier System:**
1. **USER (Tier 1):**
   - Sees only their department
   - Data filtered by employee_id
   - Cannot manage users

2. **DEPT_HEAD (Tier 2):**
   - Sees all data in their department
   - Can manage users in their department
   - Can grant access to open departments

3. **SUPER_USER (Tier 3):**
   - Full access across all departments
   - Can manage all users
   - Can grant access to gated departments

**Gated vs Open Departments:**
- **Gated:** `purchasing`, `executive`, `hr` - require explicit access grant
- **Open:** `warehouse`, `sales`, `credit`, `transportation` - auto-join for verified domain

**Auto-Provisioning:**
1. User logs in via Azure AD
2. Token validated with Microsoft Graph
3. Email domain checked (`driscollfoods.com`)
4. If domain valid → create user account
5. Detect department from email (e.g., `warehouse@driscoll` → warehouse)
6. If detected dept is open → auto-grant access
7. If detected dept is gated → no access until admin grants

---

## 6. SPECIFIC QUESTIONS ANSWERED

### Q1: Is schemas.py actually used or dead code?

**ANSWER: DEAD CODE in Enterprise Bot, ACTIVE in CogTwin**

**Evidence:**
- **Imported by:** retrieval.py, cog_twin.py, memory_pipeline.py
- **Used by EnterpriseTwin:** NO - never instantiates MemoryNode or retrieves memories
- **Proof:**
  ```python
  # enterprise_twin.py lines 91-98
  self._memory_mode = False  # No CogTwin in this fork
  self._twin = None
  self.memory_count = 0
  ```

**What schemas.py Contains:**
- `MemoryNode` - 1:1 Q/A pairs for process memory (what/how)
- `EpisodicMemory` - Full conversations for episodic memory (why/when)
- `RetrievalResult` - Combined retrieval from dual pipelines
- `ClusterInfo` - HDBSCAN cluster metadata

**Why It Exists:**
- Required by CogTwin parent system
- Retained for upgrade path to Pro tier
- Removing it would break import chain
- Acts as documentation of advanced features

**Recommendation:** KEEP
- Does not bloat production (not instantiated)
- Enables future upgrades without refactor
- Documents CogTwin architecture

---

### Q2: Does enterprise_twin.py share code with cog_twin.py or parallel?

**ANSWER: FORKED, not shared. They are parallel implementations.**

**Relationship:**
- **Parent:** `cog_twin.py` - 1567 lines, full cognitive architecture
- **Child:** `enterprise_twin.py` - 344 lines, simplified fork
- **Shared Code:** NONE at runtime
- **Shared Interfaces:** Similar method signatures for compatibility

**Code Comparison:**

| Feature | CogTwin | EnterpriseTwin |
|---------|---------|----------------|
| **Memory Retrieval** | DualRetriever (process + episodic) | None - context stuffing only |
| **Embeddings** | BGE-M3 async embedder | None |
| **Memory Pipeline** | Recursive ingestion loop | Disabled |
| **Metacognitive Mirror** | Monitors cognitive state | None |
| **Tool System** | [GREP], [VECTOR], [EPISODIC], [SQUIRREL] | None |
| **Cluster Navigation** | HDBSCAN clusters, schema engine | None |
| **Feedback Learning** | Scores traces, injects exemplars | None |
| **Streaming** | Yes (Anthropic SDK) | Yes (Anthropic SDK) |
| **LLM Adapter** | model_adapter.py | model_adapter.py ← ONLY shared code |
| **Analytics** | Optional | Required |
| **Config Source** | config.yaml (config.py) | config.yaml (config_loader.py) |

**Architectural Difference:**

**CogTwin Think Loop:**
```python
async def think(user_input):
    1. Get cognitive state from MetacognitiveMirror
    2. Embed query
    3. Retrieve from DualRetriever (process + episodic)
    4. Detect context gaps
    5. Decide response mode (exploration vs direct)
    6. Explore memory chains if needed
    7. Build voice context with memories
    8. Generate via LLM with tool protocol
    9. Handle tool calls ([GREP], [VECTOR], etc.)
    10. Synthesize tool results
    11. Parse output for actions
    12. Ingest to memory pipeline
    13. Record to chat memory
    14. Update metacognitive mirror
    15. Return response
```

**EnterpriseTwin Think Loop:**
```python
async def think(user_input, tenant):
    1. Get division from tenant
    2. Load docs from doc_loader (context stuffing)
    3. Build Venom prompt with docs
    4. Generate via LLM (stream)
    5. Log to analytics
    6. Return response
```

**Simplification Factor: 15 steps → 5 steps**

**Why Fork Instead of Flags?**
- **Startup Time:** CogTwin requires loading 22K memories + FAISS index (~5-10s), EnterpriseTwin starts instantly
- **Dependencies:** CogTwin needs numpy, faiss, hdbscan, scikit-learn - EnterpriseTwin needs none
- **Maintenance:** Two codebases easier than if/else spaghetti
- **Clarity:** Enterprise customers don't see unused advanced features
- **Upgrades:** Can offer Pro tier without code changes (just enable memory_mode flag)

---

### Q3: List all cfg() calls

**cfg() is from config_loader.py - used by EnterpriseTwin**

**All cfg() Calls in Enterprise Codebase:**

**main.py (5 calls):**
```python
line 52:  cfg("tenant.default_division", "warehouse")
line 232: cfg("tenant.allowed_domains", settings.allowed_domains)
line 405: cfg("deployment.tier", "basic")
line 406: cfg("deployment.mode", "enterprise")
line 569: cfg("deployment.tier", "basic")
line 618: cfg("tenant.default_division", "warehouse")
```

**enterprise_twin.py (9 calls):**
```python
line 32-39: imports from config_loader
line 87: cfg("paths.data_dir", "./data")
line 88: cfg("model.name", "grok-4-fast-reasoning")
line 101: cfg("model.provider", "xai")
line 214: cfg("tenant.default_division", "warehouse")
line 225-226: get_division_categories(), get_max_stuffing_tokens()
line 253: cfg("model.max_tokens", 8192)
line 268: cfg("model.max_tokens", 8192)
```

**config_loader.py itself (13+ cfg() definitions):**
```python
# Config keys defined in config.yaml:
paths.data_dir
model.name
model.provider
model.max_tokens
tenant.default_division
tenant.allowed_domains
deployment.tier
deployment.mode
memory.enabled
context_stuffing.enabled
context_stuffing.max_tokens
division_categories.{division}
```

**cog_twin.py (100+ calls):**
- Uses `config.py` (different config system!)
- Calls `cfg("cognitive.query_window_size", 100)` etc.
- Separate config.yaml parser
- NOT used in production

**Total cfg() calls in production:** ~14 (main.py + enterprise_twin.py)

**Key Config Values:**
- `model.name`: `grok-4-fast-reasoning` (default)
- `model.provider`: `xai` (default)
- `model.max_tokens`: `8192` (default)
- `paths.data_dir`: `./data` (default)
- `tenant.default_division`: `warehouse` (default)
- `deployment.tier`: `basic` (always in enterprise)
- `deployment.mode`: `enterprise` (always)
- `memory.enabled`: `False` (hardcoded in enterprise)
- `context_stuffing.enabled`: `True` (default)
- `context_stuffing.max_tokens`: `200000` (default)

---

### Q4: How does doc_loader context stuffing work?

**SEE SECTION 5: doc_loader.py Deep Dive above (already answered in detail)**

**Summary:**
1. **Discovery:** Recursively find all .docx/.json/.csv/.xlsx/.md/.txt in Manuals/Driscoll/
2. **Division Detection:** Parse folder structure (Warehouse/foo.docx → warehouse)
3. **Extraction:** Read files, parse formats, concatenate text
4. **Caching:** Store in memory after first load
5. **Context Building:** Sort by size, fit within token limit (200K default)
6. **Prompt Injection:** Concatenate with headers/footers, inject into system prompt
7. **LLM Call:** Send full context to Grok/Claude, stream response

**Performance:** ~50-100ms startup, zero latency after cache, no embeddings

---

### Q5: Is memory_pipeline.py active or stubbed?

**ANSWER: STUBBED in Enterprise Bot, ACTIVE in CogTwin**

**Evidence:**
```python
# enterprise_twin.py lines 91-98
self._memory_mode = False  # No CogTwin in this fork
self._twin = None
self.memory_count = 0

# No MemoryPipeline instantiation
# No ingest() calls
# No session memory search
```

**What memory_pipeline.py Does (in CogTwin):**
1. LLM generates response
2. Create `CognitiveOutput` with content + metadata
3. Call `pipeline.ingest(output)` - non-blocking
4. Pipeline embeds content asynchronously
5. Assigns to cluster via streaming HDBSCAN
6. Adds to session buffer (immediately searchable)
7. Batches to disk every 5s or 10 items
8. Next query can retrieve from session

**Why It's Stubbed in Enterprise:**
- No embeddings means no memory pipeline
- Context stuffing doesn't require memory retrieval
- Simplifies architecture to meet deadline
- Can be re-enabled for Pro tier

**Status:** DORMANT, not deleted
- Code is complete and working
- Just not called in production
- Retained for upgrade path

---

## 7. FRONTEND API SHAPE

### What ChatOverlay.svelte Expects

**File:** `frontend/src/lib/components/ChatOverlay.svelte` (lines 1-200 shown)

**WebSocket Messages (Frontend → Backend):**

```typescript
// 1. Verify user
{
  type: "verify",
  email: string,
  division?: string  // Optional department override
}

// 2. Send chat message
{
  type: "message",
  content: string
}

// 3. Change department
{
  type: "set_division",
  division: string
}

// 4. Keepalive
{
  type: "ping"
}
```

**WebSocket Messages (Backend → Frontend):**

```typescript
// 1. Connection established
{
  type: "connected",
  session_id: string,
  timestamp: string  // ISO 8601
}

// 2. Authentication success
{
  type: "verified",
  email: string,
  division: string,
  role: string,  // "user" | "dept_head" | "super_user"
  departments: string[]  // Accessible departments
}

// 3. Authentication failure
{
  type: "error",
  message: string
}

// 4. Chat response chunk (streaming)
{
  type: "stream_chunk",
  content: string,  // Incremental text
  done: boolean     // True on last chunk
}

// 5. Cognitive state update (after response completes)
{
  type: "cognitive_state",
  phase: string,  // "ready" (enterprise always returns this)
  temperature: number,  // 0.5 default
  session_id: string,
  query_count: number,
  memory_mode: boolean,  // Always false in enterprise
  context_stuffing_mode: boolean,  // Always true in enterprise
  memory_count: number  // Always 0 in enterprise
}

// 6. Department changed
{
  type: "division_changed",
  division: string
}

// 7. Keepalive response
{
  type: "pong"
}
```

**State Management (Svelte Stores):**

**session.ts:**
```typescript
interface SessionState {
  messages: Array<{
    role: 'user' | 'assistant',
    content: string,
    timestamp: Date
  }>,
  currentStream: string,  // Accumulated streaming text
  isStreaming: boolean,
  cognitiveState: {
    phase: string,
    temperature: number,
    ...stats
  }
}

// Methods
session.sendMessage(content: string)
session.clearMessages()
```

**websocket.ts:**
```typescript
interface WebSocketState {
  connected: boolean,
  reconnecting: boolean,
  error: string | null
}

// Methods
websocket.connect(sessionId: string)
websocket.disconnect()
websocket.send(message: object)
```

**auth.ts:**
```typescript
interface AuthState {
  user: User | null,
  token: string | null,
  departments: string[],
  currentDepartment: string | null,
  loading: boolean
}

interface User {
  id: string,
  email: string,
  displayName: string,
  role: 'user' | 'dept_head' | 'super_user',
  tier: string,
  primaryDepartment: string | null
}

// Methods
auth.login(email: string)
auth.loginWithMicrosoft()
auth.logout()
auth.switchDepartment(slug: string)
```

**Rendering Pipeline:**

```typescript
// 1. Receive stream_chunk
session.currentStream += chunk.content

// 2. Convert markdown to HTML
import { marked } from 'marked'
const html = marked.parse(session.currentStream)

// 3. Render with syntax highlighting
<div class="prose">{@html html}</div>

// 4. Auto-scroll to bottom
messagesContainer.scrollTo({ top: scrollHeight, behavior: 'smooth' })

// 5. On done=true, move to messages array
session.messages.push({
  role: 'assistant',
  content: session.currentStream,
  timestamp: new Date()
})
session.currentStream = ''
```

**CheekyLoader Integration:**

```typescript
// Map cognitive phase to cheeky category
function mapPhaseToCategory(phase: string): PhraseCategory {
  switch (phase) {
    case 'searching': return 'searching'
    case 'thinking': return 'thinking'
    case 'generating': return 'creating'
    case 'executing': return 'executing'
    default: return 'searching'
  }
}

// Show loader while streaming
{#if isStreaming}
  <CheekyLoader category={cheekyCategory} />
{/if}
```

---

## 8. DEAD CODE FILES

**Files in Repository but Unused in Production:**

### Confirmed Dead (CogTwin-specific, never called):

1. **cog_twin.py** (1567 lines)
   - Advanced cognitive architecture
   - Purpose: Parent system, retained for Pro tier
   - Status: Imported nowhere in production

2. **venom_voice.py** (1057 lines)
   - System prompt builder for CogTwin
   - Purpose: Tool protocol, artifact generation, feedback learning
   - Status: Unused - EnterpriseTwin builds prompts inline

3. **enterprise_voice.py** (307 lines)
   - Voice template system
   - Purpose: Config-driven personality customization
   - Status: Unused - EnterpriseTwin uses hardcoded Venom prompt

4. **schemas.py** (592 lines)
   - MemoryNode, EpisodicMemory data models
   - Purpose: Dual-pipeline memory system
   - Status: Imported by retrieval.py but never instantiated

5. **retrieval.py** (919 lines)
   - DualRetriever (process + episodic memory)
   - Purpose: NumPy/FAISS hybrid retrieval
   - Status: Imported by cog_twin.py only

6. **memory_pipeline.py** (516 lines)
   - Recursive memory ingestion
   - Purpose: Every LLM output becomes searchable memory
   - Status: Imported by cog_twin.py only

7. **metacognitive_mirror.py** (filename in untracked files)
   - Cognitive state monitoring
   - Purpose: Detect semantic drift, predict next memories
   - Status: CogTwin dependency only

8. **reasoning_trace.py** (filename in untracked files)
   - Provenance tracking for reasoning chains
   - Purpose: Feedback learning, trace scoring
   - Status: CogTwin dependency only

9. **chat_memory.py** (filename in untracked files)
   - Persistent chat history store
   - Purpose: Temporal recall, SQUIRREL tool
   - Status: CogTwin dependency only

10. **squirrel.py** (filename in untracked files)
    - Temporal recall tool
    - Purpose: "What did we discuss 1 hour ago?"
    - Status: CogTwin dependency only

11. **hybrid_search.py** (filename in untracked files)
    - Semantic + keyword search fusion
    - Purpose: [GREP] tool with semantic expansion
    - Status: CogTwin dependency only

12. **memory_grep.py** (filename in untracked files)
    - BM25 inverted index
    - Purpose: Exact keyword matching
    - Status: CogTwin dependency only

13. **cluster_schema.py** (filename in untracked files)
    - HDBSCAN cluster profiling
    - Purpose: Semantic cluster navigation
    - Status: CogTwin dependency only

14. **streaming_cluster.py** (filename in untracked files)
    - Online HDBSCAN clustering
    - Purpose: Real-time memory cluster assignment
    - Status: CogTwin dependency only

15. **embedder.py** (filename in untracked files)
    - AsyncEmbedder with BGE-M3
    - Purpose: Generate embeddings for memory nodes
    - Status: CogTwin dependency only

16. **heuristic_enricher.py** (filename in untracked files)
    - Zero-LLM signal extraction
    - Purpose: Intent, complexity, urgency detection
    - Status: CogTwin dependency only

17. **scoring.py** (filename in untracked files)
    - Response scoring system
    - Purpose: Accuracy, temporal, tone dimensions
    - Status: CogTwin dependency only

### Maybe Dead (Test/Debug files):

18. **test_setup.py**
    - Database setup test
    - Status: Dev tool, not production

19. **debug_pipeline.py**
    - Memory pipeline debug script
    - Status: Dev tool, not production

20. **test_integration_quick.py**
    - Integration test
    - Status: Dev tool, not production

21. **verify_chat_integration.py**
    - Chat memory test
    - Status: Dev tool, not production

22. **read_traces.py**
    - Reasoning trace viewer
    - Status: Dev tool, not production

23. **init_sandbox.py**
    - Sandbox initialization
    - Status: Dev tool, not production

24. **db_diagnostic.py**
    - Database diagnostics
    - Status: Dev tool, not production

### Definitely Active (Used in Production):

- **main.py** ✓ - FastAPI app entry point
- **enterprise_twin.py** ✓ - Chat engine
- **doc_loader.py** ✓ - Document loading
- **config_loader.py** ✓ - Configuration
- **model_adapter.py** ✓ - LLM client
- **auth_service.py** ✓ - Authentication
- **tenant_service.py** ✓ - Department permissions
- **analytics_service.py** ✓ - Query logging
- **analytics_routes.py** ✓ - Analytics API
- **admin_routes.py** ✓ - Admin API
- **sso_routes.py** ✓ - Azure AD SSO
- **azure_auth.py** ✓ - Azure AD integration
- **auth_schema.py** ✓ - Database schema
- **db_setup.py** ✓ - Database initialization
- **enterprise_tenant.py** ✓ - Tenant context
- **chat_parser_agnostic.py** ✓ - (possibly used by ingest.py)
- **ingest.py** ✓ - (possibly used for data import)
- **upload_manuals.py** ✓ - Manual upload script
- **run_migration.py** ✓ - Database migrations

### Untracked New Files (git status shows):

25. **cluster_schema.py** (untracked)
26. **cog_twin.py** (untracked)
27. **evolution_engine.py** (untracked)
28. **metacognitive_mirror.py** (untracked)
29. **sdk_recon.py** (untracked)

Status: Likely CogTwin experiments, not production code

---

## SUMMARY

**This is a CLEAN FORK architecture:**
- **Production:** Enterprise Bot (simple, fast, context stuffing)
- **Research:** CogTwin (advanced, slow, dual memory)
- **Strategy:** Ship now, upgrade later

**Key Insights:**
1. EnterpriseTwin is NOT a wrapper around CogTwin - it's a parallel implementation
2. All CogTwin files are retained for upgrade path, not production use
3. Context stuffing with doc_loader.py is the ONLY memory mechanism in production
4. memory_pipeline.py is complete but dormant - can be enabled with one flag
5. schemas.py is technically dead code but serves as architecture documentation

**File Saved:** `C:\Users\mthar\projects\enterprise_bot\WIRING_MAP.md`

Total size: ~50KB of pure architecture knowledge.
