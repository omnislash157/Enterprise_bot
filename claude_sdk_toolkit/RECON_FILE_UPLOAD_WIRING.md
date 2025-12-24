# RECON: File Upload Wiring Map

## MISSION OBJECTIVE
Map all integration points for adding file upload to CogTwin chat interface.
Grok 4.1 handles extraction/RAG via Files API - we're building a thin proxy.

**READ ONLY - NO CODE CHANGES**

---

## CONTEXT: What We're Building

```
User Flow:
1. User clicks upload button in chat
2. File uploads via REST to /api/upload
3. Backend proxies to xAI /v1/files, gets file_id
4. User sends chat message, file_id attached
5. Grok processes with automatic document_search
6. Response streams back with citations
```

xAI API Pattern:
```python
# Step 1: Upload file
uploaded_file = client.files.upload(file=open("doc.pdf", "rb"), purpose="chat")
file_id = uploaded_file.id  # "file_abc123"

# Step 2: Chat with file reference
# Content array format:
{
  "messages": [{
    "role": "user", 
    "content": [
      {"type": "text", "text": "Summarize this"},
      {"type": "file", "file_id": "file_abc123"}
    ]
  }]
}
```

---

## RECON TARGET 1: Backend - model_adapter.py

**File:** `/mnt/project/model_adapter.py`

**Analyze:**
1. Find `GrokMessages` class
2. Map `_convert_to_openai_format()` method - this builds the messages array
3. Find `create()` and `stream()` methods - where payload is built
4. Check current message format: `{"role": "user", "content": "string"}`
5. Identify what changes to support: `{"role": "user", "content": [array]}`

**Questions to Answer:**
- Line numbers for payload construction
- Does it currently support content as array or only string?
- Where would file_ids inject into the payload?
- Any existing handling for content types?

**Deliverable:** `MODEL_ADAPTER_WIRING.md`

---

## RECON TARGET 2: Backend - main.py (REST Upload Endpoint)

**File:** `/mnt/project/main.py`

**Analyze:**
1. Find where other REST routes are defined (not WebSocket)
2. Look for existing file upload patterns (bulk_import references?)
3. Find router registrations section
4. Identify auth patterns for REST endpoints
5. Check imports section for what's available

**Questions to Answer:**
- Where do REST routes get registered? (line numbers)
- Is there UploadFile from FastAPI already imported?
- Auth decorator pattern for REST endpoints?
- Any existing /api/* REST endpoints as reference?

**Deliverable:** `REST_ENDPOINT_WIRING.md`

---

## RECON TARGET 3: Backend - WebSocket Handler

**File:** `/mnt/project/main.py`

**Analyze:**
1. Find main WebSocket endpoint function
2. Map all current message type handlers (chat, voice_start, voice_chunk, etc.)
3. Find where chat messages get passed to the LLM
4. Trace: message received → processed → sent to model_adapter
5. Identify message format expected from frontend

**Questions to Answer:**
- WebSocket handler function name and line numbers
- Current message type switch/dispatch pattern
- Where does user message content get extracted?
- How would file_ids attach to existing chat flow?
- Does enterprise_twin or cog_twin handle the actual LLM call?

**Deliverable:** `WEBSOCKET_WIRING.md`

---

## RECON TARGET 4: Backend - Twin/RAG Integration

**Files:** 
- `/mnt/project/enterprise_twin.py`
- `/mnt/project/enterprise_rag.py`

**Analyze:**
1. Find where LLM calls are made (model_adapter usage)
2. Map how context gets built before LLM call
3. Check if messages are modified before sending to model
4. Find where response streams back

**Questions to Answer:**
- Which file actually calls model_adapter.messages.stream()?
- Line numbers for LLM invocation
- Is there a messages builder or formatter?
- Where would file_ids need to pass through?

**Deliverable:** `TWIN_INTEGRATION_WIRING.md`

---

## RECON TARGET 5: Frontend - Chat Input Component

**Directory:** Check frontend structure first

**Analyze:**
1. Find chat input/overlay component (ChatOverlay.svelte or similar)
2. Map current button layout (send button, mic button)
3. Find WebSocket send patterns
4. Check for existing file input anywhere (bulk import page)
5. Identify message format sent via WebSocket

**Questions to Answer:**
- Exact file path for chat input component
- Current buttons and their positions
- WebSocket store/send function used
- Message payload format to backend
- Any existing <input type="file"> patterns to copy?

**Deliverable:** `FRONTEND_CHAT_WIRING.md`

---

## RECON TARGET 6: Frontend - Stores

**Directory:** `frontend/src/lib/stores/`

**Analyze:**
1. Find session or message store
2. Map how messages are structured
3. Find WebSocket store/connection
4. Check for file-related state anywhere

**Questions to Answer:**
- Store file paths
- Message type definitions
- Where would file attachments go in message state?
- WebSocket send function signature

**Deliverable:** `FRONTEND_STORES_WIRING.md`

---

## RECON TARGET 7: Reference Patterns

**Voice Transcription (successful recent feature):**
- `/mnt/project/venom_voice.py` - backend voice handling
- Find voice WebSocket message types
- Map the voice_start → voice_chunk → voice_stop flow
- This is our template for file_upload flow

**Bulk Import (has file upload):**
- Find bulk import routes
- Check how files are received
- FastAPI UploadFile pattern

**Deliverable:** `REFERENCE_PATTERNS.md`

---

## DELIVERABLE FORMAT

For each target, create a section with:

```markdown
## [TARGET NAME]

### File: [path]

### Key Locations
| What | Line Numbers | Current Code |
|------|--------------|--------------|
| Function X | 150-180 | def function_x(): |
| Payload build | 200-210 | payload = {...} |

### Integration Point
[Describe exactly where new code would go]

### Dependencies
[List any imports or other files involved]

### Notes
[Any concerns, blockers, or observations]
```

---

## FINAL DELIVERABLE

Combine all findings into: `FILE_UPLOAD_WIRING_MAP.md`

Structure:
1. Executive Summary (1 paragraph)
2. Backend Wiring
   - model_adapter.py changes needed
   - main.py REST endpoint location
   - WebSocket handler changes
   - Twin integration points
3. Frontend Wiring
   - Chat component location
   - Store changes needed
   - Message format updates
4. Reference Patterns
   - Voice flow to copy
   - File upload pattern from bulk import
5. Dependency Check
   - xai-sdk already in requirements.txt ✓
   - Any other packages needed?
6. Recommended Implementation Order
   - Phase 1: [what first]
   - Phase 2: [what second]
   - Phase 3: [what third]

---

## CONSTRAINTS

- **READ ONLY** - Do not modify any files
- Focus on WIRING, not implementation details
- Note exact line numbers for surgical edits
- Flag any blockers or missing pieces
- If frontend structure unclear, map it first

---

## SUCCESS CRITERIA

Recon complete when we can answer:
1. ✓ Exact file + line number for model_adapter file_id support
2. ✓ Exact location for new /api/upload REST endpoint
3. ✓ Exact WebSocket handler location for file_id pass-through
4. ✓ Exact frontend component for upload button
5. ✓ Complete message flow from button click to LLM response
