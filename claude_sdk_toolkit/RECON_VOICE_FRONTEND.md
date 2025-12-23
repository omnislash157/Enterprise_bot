# RECON MISSION: Voice Transcription Frontend Integration

## OBJECTIVE
Map the frontend architecture for adding real-time voice transcription (Deepgram) to the chat interface. We need to understand the chat input area, WebSocket patterns, and UI component conventions before building.

---

## TASK 1: Chat Input Area Analysis

**Files to examine:**
- `frontend/src/lib/components/ChatOverlay.svelte`
- `frontend/src/routes/+page.svelte`

**Questions to answer:**
1. Where is the chat input field defined? (textarea? input? contenteditable?)
2. What is the current input area structure/layout?
3. Are there existing buttons near the input (send, attach, etc.)?
4. What's the form submission pattern? (on:submit? button click? Enter key?)
5. How does the input value bind to state?
6. Any existing icons/button patterns we should match?

**Output format:**
```
CHAT_INPUT_LOCATION: [file path + line numbers]
INPUT_TYPE: [textarea/input/other]
EXISTING_BUTTONS: [list with positions]
SUBMIT_PATTERN: [description]
STATE_BINDING: [how input connects to store]
BUTTON_STYLES: [CSS classes used for existing buttons]
```

---

## TASK 2: WebSocket Architecture

**Files to examine:**
- `frontend/src/lib/stores/websocket.ts`
- `frontend/src/lib/stores/session.ts`

**Questions to answer:**
1. How is the WebSocket connection established?
2. What message types already exist? (chat, system, etc.)
3. How are incoming messages handled/dispatched?
4. Is there binary data support or just JSON?
5. What's the reconnection pattern?
6. How do we add a new message type?

**Output format:**
```
WS_ENDPOINT: [URL pattern]
MESSAGE_TYPES: [list existing types]
SEND_PATTERN: [how to send messages]
RECEIVE_PATTERN: [how incoming handled]
BINARY_SUPPORT: [yes/no]
ADD_TYPE_LOCATION: [where to add new message type]
```

---

## TASK 3: UI Component Patterns

**Files to examine:**
- `frontend/src/lib/components/ribbon/` (any file)
- `frontend/src/lib/components/admin/` (any modal)
- `frontend/tailwind.config.js`

**Questions to answer:**
1. What icon library is used? (heroicons? lucide? custom SVGs?)
2. Button styling patterns (primary, secondary, icon-only)
3. Color scheme variables (cyberpunk theme colors)
4. Any existing microphone or audio-related icons?
5. Tooltip/hover state patterns
6. Loading state patterns (spinners, animations)

**Output format:**
```
ICON_LIBRARY: [name + import pattern]
BUTTON_CLASSES: [common button CSS classes]
THEME_COLORS: [key color variables]
EXISTING_AUDIO: [any audio-related code found]
TOOLTIP_PATTERN: [how tooltips implemented]
LOADING_PATTERN: [spinner/animation approach]
```

---

## TASK 4: Store Creation Pattern

**Files to examine:**
- `frontend/src/lib/stores/auth.ts` (as reference)
- `frontend/src/lib/stores/index.ts`

**Questions to answer:**
1. What's the store creation pattern? (writable, derived, custom?)
2. How are TypeScript interfaces defined for store state?
3. How are async actions structured?
4. Export pattern (barrel file? direct?)

**Output format:**
```
STORE_PATTERN: [example code snippet]
INTERFACE_PATTERN: [TypeScript structure]
ASYNC_PATTERN: [how async operations handled]
EXPORT_PATTERN: [how stores exported]
```

---

## TASK 5: Audio/Media Permissions

**Search across frontend:**
- Any use of `navigator.mediaDevices`
- Any use of `getUserMedia`
- Any existing audio recording code
- MediaRecorder usage

**Output format:**
```
EXISTING_AUDIO_CODE: [yes/no + locations]
PERMISSION_HANDLING: [any existing patterns]
MEDIARECORDER_USAGE: [yes/no + details]
```

---

## DELIVERABLE

Create a summary file: `RECON_VOICE_RESULTS.md` with:

1. **Chat Input Blueprint** - Exact location and structure
2. **WebSocket Integration Points** - Where to add voice message handling
3. **UI Pattern Guide** - How to style mic button to match
4. **Store Template** - Skeleton for new voice.ts store
5. **Code Snippets** - Relevant existing code to reference
6. **Recommendations** - Suggested file changes for implementation

---

## EXECUTION

```bash
# Run from project root
cd frontend

# Examine files in order
cat src/lib/components/ChatOverlay.svelte
cat src/routes/+page.svelte
cat src/lib/stores/websocket.ts
cat src/lib/stores/session.ts
cat src/lib/stores/auth.ts
cat tailwind.config.js

# Search for audio-related code
grep -r "mediaDevices\|getUserMedia\|MediaRecorder\|audio" src/ --include="*.svelte" --include="*.ts"

# Check icon usage
grep -r "icon\|Icon\|svg" src/lib/components/ --include="*.svelte" | head -30
```

---

## TASK 6: Backend WebSocket Context (Reference Only)

**Already known from main.py:**
```python
# WebSocket endpoint: /ws/{session_id}
# Message type dispatch pattern (line ~730):
msg_type = data.get("type", "message")

# Existing types:
# - "ping" → pong response
# - "verify" → auth verification  
# - "message" → chat message to LLM
# - "set_division" → change department

# Response pattern:
await websocket.send_json({
    "type": "response_type",
    "data": {...}
})
```

**Voice types we'll add:**
- `voice_start` - Client starting voice capture
- `voice_chunk` - Audio chunk from client (binary or base64)
- `voice_transcript` - Interim/final transcript back to client
- `voice_stop` - Client stopping voice capture
- `voice_error` - Error in transcription

---

## SUCCESS CRITERIA

- [ ] Located exact chat input component and line numbers
- [ ] Documented WebSocket message type pattern
- [ ] Identified icon library and button styles
- [ ] Found or confirmed no existing audio code
- [ ] Created actionable RECON_VOICE_RESULTS.md
