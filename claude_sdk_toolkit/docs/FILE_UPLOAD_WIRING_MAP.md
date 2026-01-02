# FILE UPLOAD WIRING MAP - CogTwin Chat Interface
## Comprehensive Reconnaissance Report

**Mission Status**: COMPLETE
**Date**: 2024-12-24
**Objective**: Map all integration points for adding file upload to CogTwin chat interface
**Mode**: READ-ONLY RECONNAISSANCE

---

## EXECUTIVE SUMMARY

### Current Architecture
- **Backend**: FastAPI with WebSocket support (main.py)
- **LLM Adapter**: Unified interface via model_adapter.py (Grok/Anthropic)
- **Frontend**: Svelte with WebSocket store + session store
- **Message Format**: Currently string-only (Dict[str, str])
- **Existing Upload Pattern**: Batch CSV import for admin users (reference available)

### Key Findings
✅ **WebSocket handler is clean** - message type handlers well separated
✅ **Model adapter is extensible** - Dict[str, str] can become Dict[str, Any]
✅ **Frontend has button space** - voice button pattern is perfect template
⚠️ **No file storage layer yet** - need Azure Blob or S3 integration
⚠️ **Message format is string-only** - needs content array support

### Complexity Assessment
- **Backend changes**: MEDIUM (4-6 locations)
- **Frontend changes**: LOW (2-3 files)
- **Model adapter**: LOW (1 change + validation)
- **Overall risk**: LOW - clean separation of concerns

---

## 1. BACKEND WIRING

### 1.1 Model Adapter - File ID Injection Point

**File**: `C:\Users\mthar\projects\enterprise_bot\core\model_adapter.py`

#### Target: GrokMessages Class

**Location**: Lines 232-273 (class definition and _convert_to_openai_format)

**Current Signature**:
```python
def _convert_to_openai_format(
    self,
    system: str,
    messages: List[Dict[str, str]],  # ← CURRENT: string content only
) -> List[Dict[str, str]]:
```

**Change Required**:
```python
def _convert_to_openai_format(
    self,
    system: str,
    messages: List[Dict[str, Any]],  # ← NEW: support content arrays
) -> List[Dict[str, Any]]:
    """
    Convert Anthropic-style to OpenAI-style.

    Now supports:
    - String content: {"role": "user", "content": "text"}
    - Array content: {"role": "user", "content": [
        {"type": "text", "text": "..."},
        {"type": "file", "file_id": "..."}
      ]}
    """
    converted = []

    if system:
        converted.append({"role": "system", "content": system})

    # Add user/assistant messages (pass through as-is)
    # OpenAI API already supports content arrays
    converted.extend(messages)

    return converted
```

**Line 258-270 Changes**:
- Change type hint from `List[Dict[str, str]]` to `List[Dict[str, Any]]`
- No logic change needed - OpenAI API supports both formats natively

**Impact**:
- Lines 258, 259, 270: Type signature changes
- Lines 279, 355: Update type hints in `create()` and `stream()` method signatures
- No runtime logic change - backward compatible

#### Injection Point for file_ids

**Location**: Lines 1115-1120 in main.py (WebSocket message handler)

Where user message is sent to model:
```python
async for chunk in active_twin.think_streaming(
    user_input=content,  # ← Currently string
    user_email=user_email,
    department=effective_division,
    session_id=session_id,
):
```

**New Flow with File IDs**:
```python
# Extract file_ids from WebSocket message
file_ids = data.get("file_ids", [])

# Build content array if files present
if file_ids:
    content_array = [
        {"type": "text", "text": content},
        *[{"type": "file", "file_id": fid} for fid in file_ids]
    ]
else:
    content_array = content  # Backward compatible

# Pass to twin
async for chunk in active_twin.think_streaming(
    user_input=content_array,  # ← Can be string OR array
    ...
):
```

---

### 1.2 REST Endpoints - File Upload

**File**: `C:\Users\mthar\projects\enterprise_bot\core\main.py`

#### Location for New Endpoint

**Insert After**: Line 680 (after `/api/upload/chat` endpoint)

**Recommended Location**: Lines 682-720 (new section)

**Endpoint Structure**:
```python
from fastapi import File, UploadFile
from typing import List

@app.post("/api/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    department: str = None,
    user: dict = Depends(require_auth)
):
    """
    Upload file for chat context.

    Returns:
        file_id: Unique identifier for referencing in messages
        file_name: Original filename
        file_size: Size in bytes
        file_type: MIME type
    """
    # Validate file type
    allowed_types = ["application/pdf", "text/plain", "image/png", "image/jpeg"]
    if file.content_type not in allowed_types:
        raise HTTPException(400, f"File type {file.content_type} not supported")

    # Validate file size (e.g., 10MB max)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 10MB)")

    # Generate unique file_id
    import uuid
    file_id = f"file_{uuid.uuid4().hex[:16]}"

    # TODO: Store in Azure Blob or S3
    # storage_path = await blob_storage.upload(
    #     file_id=file_id,
    #     contents=contents,
    #     metadata={
    #         "user_email": user["email"],
    #         "department": department,
    #         "original_name": file.filename,
    #         "content_type": file.content_type,
    #     }
    # )

    # For now, store metadata in database
    # TODO: Add files table to database schema

    return {
        "file_id": file_id,
        "file_name": file.filename,
        "file_size": len(contents),
        "file_type": file.content_type,
        "uploaded_at": datetime.utcnow().isoformat(),
    }
```

**Import Additions** (add to line 11 area):
```python
from fastapi import File, UploadFile  # Add to existing import
from typing import List  # Already present
```

**Dependencies**:
- Azure Blob Storage SDK: `azure-storage-blob`
- OR AWS S3: `boto3`

---

### 1.3 WebSocket Handler - File ID Pass-through

**File**: `C:\Users\mthar\projects\enterprise_bot\core\main.py`

#### Message Type Handler

**Location**: Lines 1013-1153 (WebSocket message handler - "message" type)

**Current Code** (Line 1034):
```python
content = data.get("content", "")
```

**Change to** (Lines 1034-1045):
```python
content = data.get("content", "")
file_ids = data.get("file_ids", [])  # ← NEW: Extract file IDs

# SECURITY: Validate file ownership
if file_ids:
    # TODO: Verify user has access to these file_ids
    # auth = get_auth_service()
    # for file_id in file_ids:
    #     if not auth.verify_file_access(user_email, file_id):
    #         await websocket.send_json({
    #             "type": "error",
    #             "message": "Access denied to file",
    #             "code": "FILE_ACCESS_DENIED"
    #         })
    #         continue
```

**Injection Point** (Lines 1115-1120):
```python
# Stream response chunks as they arrive
async for chunk in active_twin.think_streaming(
    user_input=content,           # ← Keep as string
    file_ids=file_ids,            # ← NEW: Pass file_ids separately
    user_email=user_email,
    department=effective_division,
    session_id=session_id,
):
```

**WebSocket Message Format** (Frontend → Backend):
```json
{
  "type": "message",
  "content": "What does this document say about...",
  "file_ids": ["file_abc123...", "file_def456..."],
  "division": "warehouse"
}
```

---

### 1.4 Twin Integration - File Context Building

**File**: `C:\Users\mthar\projects\enterprise_bot\core\enterprise_twin.py`

#### Method Signature Update

**Location**: Lines 509-598 (think_streaming method)

**Current Signature** (Line 509):
```python
async def think_streaming(
    self,
    user_input: str,
    user_email: str,
    department: str,
    session_id: str,
) -> AsyncIterator[str]:
```

**New Signature**:
```python
async def think_streaming(
    self,
    user_input: str,
    file_ids: List[str] = None,  # ← NEW parameter
    user_email: str,
    department: str,
    session_id: str,
) -> AsyncIterator[str]:
```

#### File Context Injection

**Location**: Lines 567-568 (system prompt building)

**Current**:
```python
system_prompt = self._build_system_prompt(context)
```

**New Flow** (add before line 567):
```python
# ===== FILE CONTEXT =====
file_contexts = []
if file_ids:
    for file_id in file_ids:
        # TODO: Retrieve file from storage
        # file_data = await storage.get_file(file_id)
        # file_contexts.append({
        #     "file_id": file_id,
        #     "file_name": file_data["name"],
        #     "content_preview": file_data["content"][:500],
        # })
        pass

# Pass to context builder
context.file_contexts = file_contexts  # Add to EnterpriseContext dataclass
```

**EnterpriseContext Update** (Lines 98-125):
```python
@dataclass
class EnterpriseContext:
    # ... existing fields ...

    # File attachments (NEW)
    file_contexts: List[Dict[str, Any]] = field(default_factory=list)
```

#### System Prompt Injection

**Location**: Lines 599-650 (_build_system_prompt method)

**Add After Manual Chunks Section** (around line 634):
```python
# File attachments (if present)
if context.file_contexts:
    sections.append(self._format_file_contexts(context.file_contexts))
```

**New Method** (add after line 738):
```python
def _format_file_contexts(self, files: List[Dict[str, Any]]) -> str:
    """Format uploaded files for prompt injection."""
    if not files:
        return ""

    lines = [
        "",
        "=" * 60,
        "UPLOADED FILES (USER PROVIDED)",
        "=" * 60,
        "Trust: HIGH - user explicitly attached these",
        "",
    ]

    for file in files:
        file_name = file.get("file_name", "unknown")
        file_id = file.get("file_id", "")
        content = file.get("content_preview", "")

        lines.append(f"File: {file_name} (ID: {file_id})")
        lines.append(f"Content preview: {content}...")
        lines.append("")

    return "\n".join(lines)
```

---

### 1.5 RAG Integration - No Changes Needed

**File**: `C:\Users\mthar\projects\enterprise_bot\core\enterprise_rag.py`

**Assessment**: ✅ No changes required

Files are passed via model adapter, not RAG. RAG continues to search documents table independently.

**Potential Future Enhancement** (NOT required for MVP):
- Store uploaded files as chunks in documents table
- Enable semantic search across user uploads
- Location: EnterpriseRAGRetriever.search() method (lines 186-299)

---

## 2. FRONTEND WIRING

### 2.1 Chat Input Component - Upload Button

**File**: `C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\components\ChatOverlay.svelte`

#### Button Location

**Insert After**: Line 357 (after mic button, before send button)

**Current Layout** (Lines 331-368):
```html
<div class="input-wrapper">
    <textarea ...></textarea>

    <!-- Voice Input Button (lines 343-357) -->
    <button class="mic-button" ...>
        <svg>...</svg>
    </button>

    <!-- NEW: File Upload Button HERE -->

    <!-- Send Button (lines 359-368) -->
    <button class="send-button" ...>
        <svg>...</svg>
    </button>
</div>
```

**New Code** (insert at line 358):
```html
<!-- File Upload Button -->
<button
    class="file-button"
    class:has-files={attachedFiles.length > 0}
    on:click={openFileDialog}
    disabled={!$websocket.connected}
    aria-label="Attach files"
    data-tooltip="Attach files"
>
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
    </svg>
    {#if attachedFiles.length > 0}
        <span class="file-count">{attachedFiles.length}</span>
    {/if}
</button>

<!-- Hidden file input -->
<input
    type="file"
    bind:this={fileInput}
    on:change={handleFileSelect}
    accept=".pdf,.txt,.png,.jpg,.jpeg"
    multiple
    style="display: none;"
/>
```

#### Script Additions

**Add to Script Section** (after line 51):
```typescript
// File upload state
let attachedFiles: Array<{file_id: string, file_name: string, file_size: number}> = [];
let fileInput: HTMLInputElement;
let uploadingFile = false;

function openFileDialog() {
    fileInput?.click();
}

async function handleFileSelect(event: Event) {
    const target = event.target as HTMLInputElement;
    const files = target.files;

    if (!files || files.length === 0) return;

    uploadingFile = true;

    for (const file of Array.from(files)) {
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('department', $session.currentDivision || 'warehouse');

            const response = await fetch('/api/upload/file', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-User-Email': $currentUser?.email || '',
                }
            });

            if (!response.ok) throw new Error('Upload failed');

            const result = await response.json();
            attachedFiles = [...attachedFiles, result];
        } catch (err) {
            console.error('File upload failed:', err);
            // TODO: Show error toast
        }
    }

    uploadingFile = false;
    target.value = ''; // Clear input
}

function removeFile(file_id: string) {
    attachedFiles = attachedFiles.filter(f => f.file_id !== file_id);
}
```

#### Send Message Update

**Update sendMessage()** (Lines 90-96):
```typescript
function sendMessage() {
    if (!inputValue.trim() || !$websocket.connected) return;

    // Extract file_ids
    const file_ids = attachedFiles.map(f => f.file_id);

    session.sendMessage(inputValue.trim(), file_ids);  // ← Pass file_ids
    inputValue = '';
    attachedFiles = [];  // Clear after sending
    tick().then(() => inputElement?.focus());
}
```

#### File Preview UI

**Add Before Input Wrapper** (line 331):
```html
{#if attachedFiles.length > 0}
    <div class="attached-files">
        {#each attachedFiles as file}
            <div class="file-chip">
                <svg class="file-icon" viewBox="0 0 24 24" fill="currentColor" width="14" height="14">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z"/>
                </svg>
                <span class="file-name">{file.file_name}</span>
                <button
                    class="remove-file"
                    on:click={() => removeFile(file.file_id)}
                    aria-label="Remove file"
                >×</button>
            </div>
        {/each}
    </div>
{/if}
```

#### Styles

**Add to Style Section** (after line 883):
```css
/* File Upload Button */
.file-button {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(0, 255, 65, 0.3);
    color: #00ff41;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    flex-shrink: 0;
    position: relative;
}

.file-button:hover:not(:disabled) {
    background: rgba(0, 255, 65, 0.1);
    border-color: #00ff41;
    box-shadow: 0 0 20px rgba(0, 255, 65, 0.3);
    transform: scale(1.02);
}

.file-button.has-files {
    border-color: #00ff41;
    background: rgba(0, 255, 65, 0.15);
}

.file-button svg {
    width: 22px;
    height: 22px;
}

.file-count {
    position: absolute;
    top: -4px;
    right: -4px;
    background: #00ff41;
    color: #000;
    font-size: 0.7rem;
    font-weight: 600;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
}

/* Attached Files Preview */
.attached-files {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: rgba(0, 0, 0, 0.3);
    border-bottom: 1px solid rgba(0, 255, 65, 0.15);
}

.file-chip {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.75rem;
    background: rgba(0, 255, 65, 0.1);
    border: 1px solid rgba(0, 255, 65, 0.3);
    border-radius: 8px;
    font-size: 0.85rem;
    color: #e0e0e0;
}

.file-icon {
    color: #00ff41;
}

.file-name {
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.remove-file {
    background: none;
    border: none;
    color: #ff4444;
    font-size: 1.2rem;
    cursor: pointer;
    padding: 0;
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.1s;
}

.remove-file:hover {
    transform: scale(1.2);
}
```

---

### 2.2 Session Store - File ID Handling

**File**: `C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\stores\session.ts`

#### sendMessage Method Update

**Location**: Lines 391-430 (sendMessage method)

**Current Signature** (Line 391):
```typescript
sendMessage(content?: string) {
```

**New Signature**:
```typescript
sendMessage(content?: string, file_ids?: string[]) {
```

**Update WebSocket Send** (Lines 420-429):
```typescript
// Get current division to include in message
const state = get(store);

// Send to backend WITH division and file_ids
websocket.send({
    type: 'message',
    content: messageContent,
    division: state.currentDivision,
    file_ids: file_ids || [],  // ← NEW: Include file_ids
});
```

#### Message Interface Update

**Location**: Lines 9-14 (Message interface)

**Add Field**:
```typescript
interface Message {
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    traceId?: string;
    file_ids?: string[];  // ← NEW: Track attached files
}
```

#### User Message Creation Update

**Location**: Lines 398-402 (user message creation)

**Update**:
```typescript
const userMsg: Message = {
    role: 'user',
    content: messageContent,
    timestamp: new Date(),
    file_ids: file_ids || [],  // ← NEW: Store file_ids
};
```

---

### 2.3 WebSocket Store - No Changes Needed

**File**: `C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\stores\websocket.ts`

**Assessment**: ✅ No changes required

WebSocket store's `send()` method (line 138) already accepts `any` and JSON-stringifies it. File IDs pass through automatically.

---

## 3. REFERENCE PATTERNS

### 3.1 Voice Input Pattern (Template for File Upload)

**File**: `C:\Users\mthar\projects\enterprise_bot\core\venom_voice.py`

**Pattern**: NOT APPLICABLE - This is CogTwin personal twin pattern, not Enterprise

**Better Reference**: Admin batch import (below)

---

### 3.2 Admin Batch Import (File Upload Pattern)

**Backend File**: `C:\Users\mthar\projects\enterprise_bot\auth\admin_routes.py`

**Endpoint**: Lines 958-1050 (batch_create_users)

**Pattern**:
```python
@admin_router.post("/users/batch", response_model=APIResponse)
async def batch_create_users(
    request: BatchCreateRequest,  # ← Pydantic model, not File upload
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """Batch create multiple users from CSV import."""
    # Validate requester
    # Validate departments
    # Create users
    # Return summary
```

**Note**: This uses JSON body, not multipart/form-data. For file uploads, use:

```python
from fastapi import File, UploadFile

@app.post("/api/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    department: str = Form(None),  # Form fields with file upload
):
    contents = await file.read()
    # ... process file
```

**Frontend File**: `C:\Users\mthar\projects\enterprise_bot\frontend\src\lib\components\admin\BatchImportModal.svelte`

**Pattern**: Lines 71-88 (submit function)

**Key Takeaway**: Uses `fetch()` with JSON body, not FormData. For file uploads:

```typescript
const formData = new FormData();
formData.append('file', file);
formData.append('department', department);

const response = await fetch('/api/upload/file', {
    method: 'POST',
    body: formData,  // ← No JSON.stringify, no Content-Type header
    headers: {
        'X-User-Email': email,
        // DO NOT set Content-Type - browser sets it with boundary
    }
});
```

---

## 4. DEPENDENCY CHECK

### 4.1 Python Dependencies

**File**: `C:\Users\mthar\projects\enterprise_bot\requirements.txt`

**Current Status**:
- ✅ FastAPI supports File/UploadFile natively
- ⚠️ No blob storage SDK

**Add to requirements.txt**:
```
# File storage (choose one)
azure-storage-blob==12.19.0  # Azure Blob Storage
# OR
boto3==1.34.0  # AWS S3
```

**Import Additions to main.py** (line 11):
```python
from fastapi import File, UploadFile  # Add to existing import
```

**Import Additions to model_adapter.py** (line 30):
```python
from typing import List, Dict, Any, Optional  # Change Any to include Any
```

---

### 4.2 Frontend Dependencies

**File**: `C:\Users\mthar\projects\enterprise_bot\frontend\package.json`

**Status**: ✅ No new dependencies needed

Browser native APIs:
- `FormData` - native
- `fetch` - native
- File input - native HTML

---

### 4.3 Database Schema

**Status**: ⚠️ New table required

**Migration Required**: Add files table

```sql
CREATE TABLE IF NOT EXISTS enterprise.files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id VARCHAR(255) UNIQUE NOT NULL,
    user_email VARCHAR(255) NOT NULL,
    department_id VARCHAR(100),
    original_name VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,  -- Optional: auto-delete old files

    INDEX idx_file_id (file_id),
    INDEX idx_user_email (user_email),
    INDEX idx_created_at (created_at)
);
```

**Alternative**: Store in documents table as chunks (enables RAG search)

---

## 5. RECOMMENDED IMPLEMENTATION ORDER

### Phase 1: Backend Foundation (Day 1)
1. **Add files table to database** (schema migration)
2. **Set up Azure Blob Storage** (or S3) connection
3. **Create `/api/upload/file` endpoint** (main.py lines 682-720)
4. **Test with curl/Postman**

**Success Criteria**: Can upload file via REST API, get file_id back

### Phase 2: Model Adapter (Day 1-2)
1. **Update type hints in model_adapter.py** (lines 258, 259, 279, 355)
2. **Update GrokMessages._convert_to_openai_format()** (line 255-272)
3. **Add validation for content array format**
4. **Test with mock messages**

**Success Criteria**: Model adapter accepts both string and array content

### Phase 3: WebSocket Integration (Day 2)
1. **Extract file_ids from WebSocket message** (main.py line 1034)
2. **Add file access validation** (security check)
3. **Pass file_ids to think_streaming()** (line 1115)
4. **Test WebSocket with mock file_ids**

**Success Criteria**: WebSocket accepts file_ids, no errors

### Phase 4: Twin Integration (Day 2-3)
1. **Update think_streaming() signature** (enterprise_twin.py line 509)
2. **Add file_contexts to EnterpriseContext** (line 98)
3. **Create _format_file_contexts() method** (after line 738)
4. **Inject file context into system prompt** (line 634)
5. **Test with uploaded files**

**Success Criteria**: Files appear in LLM prompt, responses reference them

### Phase 5: Frontend (Day 3)
1. **Add file upload button to ChatOverlay.svelte** (line 358)
2. **Implement file select and upload handlers** (script section)
3. **Add file preview UI** (line 331)
4. **Update session.sendMessage()** to include file_ids (session.ts line 391)
5. **Style file components** (styles section)
6. **Test end-to-end flow**

**Success Criteria**: User can attach files, see them in UI, send with message

### Phase 6: Polish & Security (Day 4)
1. **Add file type validation** (backend + frontend)
2. **Add file size limits** (10MB default)
3. **Implement file access control** (verify user owns file_ids)
4. **Add error handling and user feedback**
5. **Add loading states during upload**
6. **Test edge cases** (large files, invalid types, unauthorized access)

**Success Criteria**: Robust error handling, secure access control

### Phase 7: RAG Enhancement (Optional, Day 5+)
1. **Extract text from PDFs** (PyPDF2 or similar)
2. **Chunk file content**
3. **Generate embeddings for file chunks**
4. **Store in documents table**
5. **Enable RAG search across uploaded files**

**Success Criteria**: Can search uploaded file content semantically

---

## 6. BLOCKERS AND CONCERNS

### Critical Blockers
1. **❌ No blob storage configured** - Need Azure Blob or S3 setup
   - **Impact**: Cannot store uploaded files
   - **Solution**: Add Azure Storage Account or AWS S3 bucket
   - **Estimate**: 2-4 hours setup + credentials

2. **❌ No files table in database** - Schema migration required
   - **Impact**: Cannot track file metadata
   - **Solution**: Create migration script, run on production DB
   - **Estimate**: 1-2 hours

### Medium Concerns
3. **⚠️ File access control** - Need to verify user owns file_ids
   - **Impact**: Security vulnerability if not implemented
   - **Solution**: Add file_access check in WebSocket handler
   - **Estimate**: 2-3 hours

4. **⚠️ File expiration** - Old files will accumulate
   - **Impact**: Storage costs increase
   - **Solution**: Add expires_at field, background cleanup job
   - **Estimate**: 3-4 hours

### Low Priority
5. **⚠️ File size limits** - Could exceed memory/timeout limits
   - **Impact**: Large files may cause crashes
   - **Solution**: Enforce 10MB limit (already in plan)
   - **Estimate**: 30 minutes

6. **⚠️ MIME type validation** - Users could upload malicious files
   - **Impact**: Security risk
   - **Solution**: Whitelist: PDF, TXT, PNG, JPG only
   - **Estimate**: 30 minutes

---

## 7. MESSAGE FLOW DIAGRAM

### Current Flow (String Content)
```
Frontend ChatOverlay
  └─ sendMessage("What is the policy?")
     └─ session.sendMessage(content)
        └─ websocket.send({ type: "message", content: "..." })
           └─ Backend WebSocket Handler (main.py:1013)
              └─ EnterpriseTwin.think_streaming(user_input=content)
                 └─ EnterpriseContext built (no files)
                    └─ System prompt + RAG context
                       └─ model_adapter.messages.stream(messages=[...])
                          └─ Grok API (OpenAI format)
                             └─ Response chunks stream back
```

### New Flow (With Files)
```
Frontend ChatOverlay
  ├─ User clicks file button
  │  └─ openFileDialog()
  │     └─ <input type="file"> opens
  │        └─ User selects file(s)
  │           └─ handleFileSelect(event)
  │              └─ FormData upload to /api/upload/file
  │                 └─ Backend stores in Azure Blob
  │                    └─ Returns { file_id, file_name, ... }
  │                       └─ attachedFiles.push(result)
  │                          └─ UI shows file chip
  │
  └─ User types message and clicks send
     └─ sendMessage("What does this say?")
        └─ Extract file_ids from attachedFiles
           └─ session.sendMessage(content, file_ids)
              └─ websocket.send({
                   type: "message",
                   content: "...",
                   file_ids: ["file_abc123..."]
                 })
                 └─ Backend WebSocket Handler (main.py:1013)
                    ├─ Validate file access (user owns these file_ids)
                    └─ EnterpriseTwin.think_streaming(
                         user_input=content,
                         file_ids=file_ids  ← NEW
                       )
                       └─ Retrieve file content from storage
                          └─ EnterpriseContext built (WITH file_contexts)
                             └─ System prompt + RAG + FILE CONTEXTS
                                └─ model_adapter.messages.stream(
                                     messages=[{
                                       role: "user",
                                       content: [
                                         {type: "text", text: "..."},
                                         {type: "file", file_id: "..."}
                                       ]
                                     }]
                                   )
                                   └─ Grok API receives content array
                                      └─ Response chunks reference file content
```

---

## 8. EXACT LOCATIONS SUMMARY

### Backend Changes
| File | Line Range | Change | Type |
|------|-----------|---------|------|
| `model_adapter.py` | 258-259 | Change `List[Dict[str, str]]` to `List[Dict[str, Any]]` | Type hint |
| `model_adapter.py` | 279, 355 | Update method signatures | Type hint |
| `main.py` | 11 | Add `from fastapi import File, UploadFile` | Import |
| `main.py` | 682-720 | Add `/api/upload/file` endpoint | New code |
| `main.py` | 1034 | Add `file_ids = data.get("file_ids", [])` | New line |
| `main.py` | 1115 | Add `file_ids=file_ids` parameter | Parameter |
| `enterprise_twin.py` | 98-125 | Add `file_contexts` to EnterpriseContext | Dataclass field |
| `enterprise_twin.py` | 509 | Add `file_ids: List[str] = None` parameter | Parameter |
| `enterprise_twin.py` | 634 | Add file context formatting call | New line |
| `enterprise_twin.py` | 738+ | Add `_format_file_contexts()` method | New method |

### Frontend Changes
| File | Line Range | Change | Type |
|------|-----------|---------|------|
| `ChatOverlay.svelte` | 51 | Add file upload state variables | Script |
| `ChatOverlay.svelte` | 90-96 | Update `sendMessage()` to extract file_ids | Logic |
| `ChatOverlay.svelte` | 331 | Add attached files preview UI | Template |
| `ChatOverlay.svelte` | 358 | Add file upload button | Template |
| `ChatOverlay.svelte` | 883+ | Add file upload styles | Styles |
| `session.ts` | 9-14 | Add `file_ids?: string[]` to Message interface | Type |
| `session.ts` | 391 | Update `sendMessage()` signature | Parameter |
| `session.ts` | 402 | Add `file_ids` to user message | Field |
| `session.ts` | 428 | Add `file_ids` to WebSocket payload | Field |

### Database Changes
| File | Change | Type |
|------|--------|------|
| Migration script | Create `enterprise.files` table | Schema |

### Dependencies
| File | Change | Type |
|------|--------|------|
| `requirements.txt` | Add `azure-storage-blob==12.19.0` | Python package |

---

## 9. TESTING CHECKLIST

### Unit Tests
- [ ] model_adapter accepts content arrays
- [ ] model_adapter handles mixed string/array messages
- [ ] File upload validates MIME types
- [ ] File upload enforces size limits
- [ ] File access control validates ownership

### Integration Tests
- [ ] Upload file via REST API
- [ ] Send message with file_ids via WebSocket
- [ ] Retrieve file content in twin
- [ ] Format file context in system prompt
- [ ] LLM references file content in response

### E2E Tests
- [ ] User uploads PDF
- [ ] User attaches file to chat
- [ ] User sends message with file
- [ ] Response includes file insights
- [ ] User can remove attached file before sending
- [ ] Multiple files can be attached
- [ ] Files persist across page refresh (session storage)

### Security Tests
- [ ] Cannot access other users' file_ids
- [ ] Invalid file types rejected
- [ ] Oversized files rejected
- [ ] File access requires authentication
- [ ] SQL injection in file_id parameter blocked

### Edge Cases
- [ ] Empty file upload
- [ ] Duplicate file upload
- [ ] File upload during message send
- [ ] WebSocket disconnect during upload
- [ ] Expired file_id in message
- [ ] Malformed file_id format

---

## 10. SUCCESS CRITERIA

✅ **Milestone 1: Backend Ready**
- REST endpoint accepts file uploads
- Files stored in blob storage
- File metadata in database
- Returns valid file_id

✅ **Milestone 2: WebSocket Integration**
- WebSocket accepts file_ids in message payload
- File access validation works
- file_ids pass through to twin

✅ **Milestone 3: Model Integration**
- Model adapter accepts content arrays
- Files appear in system prompt
- LLM responses reference files

✅ **Milestone 4: Frontend Complete**
- User can click upload button
- File select dialog works
- Files upload and show in UI
- Files attach to messages
- Messages send with file_ids

✅ **Milestone 5: End-to-End**
- Full flow: Upload → Attach → Send → LLM processes → Response
- No errors in console
- Response quality validates file understanding
- Multiple files work
- Error states handled gracefully

---

## APPENDIX A: CODE SNIPPETS

### A.1 Complete Upload Endpoint

```python
# main.py (insert at line 682)

from fastapi import File, UploadFile
from azure.storage.blob import BlobServiceClient
import uuid

# Azure Blob Storage client (initialize at startup)
blob_service_client = BlobServiceClient.from_connection_string(
    os.getenv("AZURE_STORAGE_CONNECTION_STRING")
)
container_name = "chat-uploads"

@app.post("/api/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    department: str = None,
    user: dict = Depends(require_auth)
):
    """
    Upload file for chat context.

    Supported types: PDF, TXT, PNG, JPG (max 10MB)
    Returns file_id for use in chat messages.
    """
    # Validate file type
    allowed_types = {
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "image/png": ".png",
        "image/jpeg": ".jpg",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            400,
            f"File type {file.content_type} not supported. "
            f"Allowed: {', '.join(allowed_types.values())}"
        )

    # Read file
    contents = await file.read()

    # Validate size (10MB)
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 10MB)")

    # Generate unique file_id
    file_id = f"file_{uuid.uuid4().hex[:16]}"

    # Upload to Azure Blob Storage
    try:
        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=f"{user['email']}/{file_id}"
        )

        blob_client.upload_blob(
            contents,
            overwrite=True,
            metadata={
                "user_email": user["email"],
                "department": department or "unknown",
                "original_name": file.filename,
                "content_type": file.content_type,
            }
        )

        storage_path = blob_client.url

    except Exception as e:
        logger.error(f"Blob upload failed: {e}")
        raise HTTPException(500, "File storage failed")

    # Store metadata in database
    # TODO: Add to files table
    # conn.execute("""
    #     INSERT INTO enterprise.files
    #     (file_id, user_email, department_id, original_name,
    #      file_size, content_type, storage_path, created_at)
    #     VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
    # """, file_id, user["email"], department, file.filename,
    #      len(contents), file.content_type, storage_path)

    logger.info(f"File uploaded: {file_id} by {user['email']}")

    return {
        "file_id": file_id,
        "file_name": file.filename,
        "file_size": len(contents),
        "file_type": file.content_type,
        "uploaded_at": datetime.utcnow().isoformat(),
    }
```

### A.2 File Retrieval Helper

```python
# enterprise_twin.py (add as method)

async def _retrieve_file_content(self, file_id: str, user_email: str) -> Dict[str, Any]:
    """
    Retrieve file content from blob storage.

    Returns:
        {
            "file_id": str,
            "file_name": str,
            "content": str (text preview),
            "full_content": bytes (optional),
        }
    """
    try:
        # Get file metadata from database
        # file_meta = await db.fetchrow(
        #     "SELECT * FROM enterprise.files WHERE file_id = $1", file_id
        # )
        # if not file_meta:
        #     logger.error(f"File not found: {file_id}")
        #     return None
        #
        # # Verify user owns this file
        # if file_meta["user_email"] != user_email:
        #     logger.warning(f"File access denied: {file_id} for {user_email}")
        #     return None

        # Retrieve from blob storage
        blob_client = blob_service_client.get_blob_client(
            container="chat-uploads",
            blob=f"{user_email}/{file_id}"
        )

        blob_data = blob_client.download_blob().readall()

        # Extract text preview (first 500 chars)
        content_type = blob_client.get_blob_properties().content_settings.content_type

        if content_type == "text/plain":
            preview = blob_data.decode("utf-8")[:500]
        elif content_type == "application/pdf":
            # TODO: Extract text from PDF
            preview = "[PDF content - extraction not yet implemented]"
        elif content_type.startswith("image/"):
            preview = "[Image file - OCR not yet implemented]"
        else:
            preview = "[Binary file]"

        return {
            "file_id": file_id,
            "file_name": "unknown",  # Get from metadata
            "content_preview": preview,
            "file_size": len(blob_data),
        }

    except Exception as e:
        logger.error(f"File retrieval failed: {file_id}, {e}")
        return None
```

---

## APPENDIX B: SECURITY CONSIDERATIONS

### Authentication
- ✅ All endpoints require `require_auth` dependency
- ✅ File uploads scoped to user email
- ✅ WebSocket messages require verification

### Authorization
- ⚠️ **BLOCKER**: Need file access validation
- Users should only access their own file_ids
- Department-scoped files need additional checks

### Input Validation
- ✅ MIME type whitelist
- ✅ File size limits
- ⚠️ Need filename sanitization (prevent path traversal)
- ⚠️ Need file_id format validation (prevent SQL injection)

### Storage Security
- ✅ Azure Blob Storage has built-in encryption at rest
- ⚠️ Need to set container access to private (no anonymous access)
- ⚠️ Consider SAS tokens for temporary access URLs

### Rate Limiting
- ⚠️ No rate limiting on file uploads currently
- Recommendation: 10 uploads per user per hour
- Add to existing RateLimiter class (main.py:822)

---

## APPENDIX C: PERFORMANCE CONSIDERATIONS

### File Upload Performance
- 10MB file ≈ 2-5 seconds upload time (depends on network)
- Add progress indicator in frontend
- Consider chunked uploads for large files (future)

### Storage Costs
- Azure Blob Storage: ~$0.018/GB/month
- 1000 users × 10 files × 5MB = 50GB = $0.90/month
- Add auto-deletion after 30 days to control costs

### LLM Context Length
- Current: 4096 max_tokens in model_adapter
- Files add to context length
- May need to increase or truncate file content
- Monitor token usage in metrics

### Database Load
- Files table adds ~1KB per file metadata
- 10K files = 10MB metadata
- Indexes on file_id and user_email keep queries fast

---

## END OF RECONNAISSANCE REPORT

**Report Compiled**: 2024-12-24
**Total Integration Points**: 23 locations
**Estimated Implementation Time**: 3-5 days
**Risk Level**: LOW (clean architecture, well-separated concerns)

**Next Steps**:
1. Get approval for Azure Blob Storage setup
2. Run database migration for files table
3. Begin Phase 1 implementation

---
