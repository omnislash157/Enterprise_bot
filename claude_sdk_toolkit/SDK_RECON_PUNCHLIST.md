# SDK RECON MISSION: Enterprise Punchlist Features

**Agent:** Claude Code (via SDK)  
**Mode:** Parallel Multi-File Reconnaissance  
**Output:** Integration map per feature  

---

## MISSION OVERVIEW

Recon four features to map integration points before build sheets are written:

1. **Session Timeout/Reconnect** - WebSocket state persistence
2. **Audit Logging** - Department access tracking
3. **Voice Transcription** - Cognitive pattern capture
4. **Bulk User Import** - CSV onboarding

For each feature, identify:
- Existing code that's relevant
- Integration points (where new code plugs in)
- Database changes needed
- Frontend/backend contract (API shape)
- Dependencies or blockers

---

## TASK 1: Session Timeout/Reconnect

**Goal:** Map WebSocket lifecycle and state that needs persisting.

### Backend Files to Examine
```
main.py:
- Find `async def websocket_endpoint` 
- Document: connection state, session ID handling, auth validation
- Find: How is user context established? Token validation?
- Find: Any existing heartbeat/ping logic?
- Find: What state is in-memory only vs persisted?

auth_service.py:
- Find: Session token management
- Find: Token refresh patterns
- Find: `get_current_user_ws` or similar

chat_memory.py:
- Find: ChatMemoryStore class
- Document: What gets stored? How is it keyed (session ID? user ID?)
- Find: Is there a "restore session" pattern?
```

### Frontend Files to Examine
```
src/lib/stores/websocket.ts:
- Document: Connection state machine
- Find: Reconnection logic (existing or stub)
- Find: How is connection loss detected?
- Find: What events trigger reconnect?

src/lib/stores/session.ts:
- Document: What session state exists?
- Find: Messages array, context, department
- Find: Is state localStorage backed?

src/lib/stores/auth.ts:
- Find: Token refresh handling
- Find: Token expiry detection
```

### Output Format
```yaml
websocket_recon:
  backend:
    endpoint_location: "main.py:L{line}"
    connection_state: {list what's tracked}
    auth_method: "description"
    heartbeat: "exists/none"
    persistence: "redis/none/postgres"
  
  frontend:
    reconnect_logic: "exists/none"
    state_persistence: "localStorage/sessionStorage/none"
    reconnect_trigger: "description"
    
  gaps:
    - description of missing pieces
    
  integration_points:
    - where to add reconnect logic
    - where to add state snapshot
    - where to add restore
```

---

## TASK 2: Audit Logging

**Goal:** Map existing logging and find insertion points for audit trail.

### Backend Files to Examine
```
main.py:
- Find: Request logging middleware
- Find: WebSocket message logging
- Document: Current logging format

admin_routes.py:
- Find: Any existing audit endpoints (/api/admin/audit/*)
- Find: How are admin actions logged?

auth_service.py:
- Find: Login/logout events
- Find: Permission check logging

tenant_service.py:
- Find: Department access events
- Find: set_division or department change logging

enterprise_rag.py:
- Find: Document retrieval events
- Find: Search query logging

schemas.py:
- Find: Any AuditLog or similar model
```

### Database Check
```sql
-- Check if audit table exists
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'enterprise' AND table_name LIKE '%audit%';

-- Check for logging columns on users
SELECT column_name FROM information_schema.columns 
WHERE table_schema = 'enterprise' AND table_name = 'users'
AND column_name LIKE '%log%' OR column_name LIKE '%audit%';
```

### Frontend Files to Examine
```
src/routes/admin/audit/+page.svelte:
- Document: Current UI (placeholder or functional?)
- Find: API calls made
- Find: Data shape expected

src/lib/stores/admin.ts:
- Find: Audit data store if exists
```

### Output Format
```yaml
audit_recon:
  backend:
    current_logging: "description of what's logged"
    audit_table: "exists/none"
    audit_endpoints: [list]
    
  events_to_track:
    - login: "location"
    - logout: "location"
    - department_change: "location"
    - document_access: "location"
    - search_query: "location"
    - admin_action: "location"
    
  frontend:
    audit_page_status: "placeholder/functional"
    expected_api: "endpoint shape"
    
  integration_points:
    - where to insert audit writes
    - recommended table schema
```

---

## TASK 3: Voice Transcription

**Goal:** Map existing voice infrastructure and identify integration pattern.

### Backend Files to Examine
```
venom_voice.py (41K - MAIN TARGET):
- Document: Class structure
- Find: Any audio handling code
- Find: Text-to-speech logic (if exists)
- Find: Where voice output is generated
- Find: Any Whisper/Deepgram/Azure Speech imports

main.py:
- Find: Any audio/voice endpoints
- Find: Media upload handling

config.yaml:
- Find: Voice config section
- Find: API keys for speech services

model_adapter.py:
- Find: Audio model support
```

### External Service Check
```python
# Check for speech SDKs in requirements.txt or imports
import re
speech_libs = ['whisper', 'deepgram', 'azure.cognitiveservices.speech', 
               'openai.audio', 'google.cloud.speech']
```

### Frontend Files to Examine
```
src/lib/components/:
- Find: Any microphone/audio components
- Find: Voice input UI elements

src/lib/stores/:
- Find: Audio state stores
```

### Output Format
```yaml
voice_recon:
  backend:
    venom_voice_purpose: "description"
    tts_exists: true/false
    stt_exists: true/false
    audio_endpoints: [list]
    speech_service: "whisper/deepgram/azure/none"
    
  frontend:
    audio_capture: "exists/none"
    microphone_ui: "exists/none"
    
  integration_pattern:
    - how audio would flow
    - where transcription plugs in
    - how transcripts become memories
    
  decision_needed:
    - transcription provider
    - real-time vs batch
```

---

## TASK 4: Bulk User Import

**Goal:** Map existing import infrastructure and CSV handling.

### Backend Files to Examine
```
admin_routes.py:
- Find: Any bulk import endpoints
- Find: CSV parsing code
- Find: User creation batch logic

auth_service.py:
- Find: create_user method signature
- Find: Batch user creation support
- Find: Email validation

tenant_service.py:
- Find: Department validation
- Find: Bulk department assignment

schemas.py:
- Find: UserCreate model
- Find: BulkImportRequest or similar
```

### Frontend Files to Examine
```
src/lib/components/admin/BatchImportModal.svelte:
- Document: Current implementation
- Find: CSV parsing logic
- Find: API endpoint called
- Find: Error handling

src/routes/admin/users/+page.svelte:
- Find: Import button/trigger
- Find: How BatchImportModal is used
```

### Output Format
```yaml
bulk_import_recon:
  backend:
    import_endpoint: "exists/none"
    csv_parsing: "backend/frontend"
    batch_create: "exists/none"
    validation: [list of validations]
    
  frontend:
    modal_status: "placeholder/functional"
    csv_parsing: "papaparse/native/none"
    preview_ui: "exists/none"
    error_display: "exists/none"
    
  expected_csv_format:
    columns: [email, display_name, departments, role]
    
  integration_points:
    - backend endpoint path
    - validation logic location
    - success/error handling
```

---

## EXECUTION COMMANDS

Run each task in sequence:

```bash
# Task 1: WebSocket/Session
python claude_sdk_toolkit/claude_cli.py run -f SDK_RECON_PUNCHLIST.md --task 1

# Task 2: Audit Logging
python claude_sdk_toolkit/claude_cli.py run -f SDK_RECON_PUNCHLIST.md --task 2

# Task 3: Voice Transcription
python claude_sdk_toolkit/claude_cli.py run -f SDK_RECON_PUNCHLIST.md --task 3

# Task 4: Bulk User Import
python claude_sdk_toolkit/claude_cli.py run -f SDK_RECON_PUNCHLIST.md --task 4
```

Or run all in parallel:
```bash
python claude_sdk_toolkit/claude_cli.py run -f SDK_RECON_PUNCHLIST.md --parallel
```

---

## OUTPUT FILES

Create these files with findings:

```
RECON_OUTPUT/
├── session_reconnect_map.yaml
├── audit_logging_map.yaml
├── voice_transcription_map.yaml
└── bulk_import_map.yaml
```

---

## SUCCESS CRITERIA

Each output file must contain:
1. ✅ File locations with line numbers for integration points
2. ✅ Existing code that can be reused
3. ✅ Gaps requiring new code
4. ✅ Database changes needed
5. ✅ API contract (request/response shape)
6. ✅ Frontend/backend wiring points

After recon, we build feature sheets with exact code placement.
