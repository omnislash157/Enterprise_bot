# Voice Mode Critical Bug Analysis
**Date**: 2025-12-24
**Issue**: Microphone records (shows waveform), but transcriptions never appear anywhere
**Severity**: 🔴 **CRITICAL** - Feature completely non-functional

---

## The Smoking Gun

### User's Observed Behavior
✅ Mic button clicked → Recording indicator shows (red pulsing button)
✅ Permission popup appears → Microphone access granted
✅ Waveform visible in browser permission indicator
✅ Audio is being captured
❌ **Nothing appears in chat window**
❌ **Send button stays greyed out (no text in input)**
❌ **No error messages visible**

### What This Tells Us

**The audio is being captured locally** (waveform proves this), but the transcriptions from Deepgram are **never reaching the UI**.

---

## Root Cause: Message Handler Registration Bug

### The Problem (Lines 157-184 in voice.ts)

```typescript
function createVoiceStore() {
    // ... store initialization ...

    // Message handler for transcripts
    websocket.onMessage((data: any) => {
        if (data.type === 'voice_transcript') {
            if (data.is_final) {
                update(s => ({
                    ...s,
                    finalTranscript: s.finalTranscript + ' ' + data.transcript,
                    transcript: '',
                }));
            } else {
                update(s => ({
                    ...s,
                    transcript: data.transcript,
                }));
            }
        }
        // ... error handling ...
    });

    return {
        subscribe,
        toggle() { ... },
        stop() { ... },
        // ... other methods ...
    };
}

export const voice = createVoiceStore();  // Line 223
```

### Why This Breaks Everything

**The `websocket.onMessage()` handler is registered IMMEDIATELY when the voice store is created** (line 157), which happens at module load time (line 223).

**HOWEVER**: This creates a **race condition** with multiple potential failure modes:

---

## Failure Mode Analysis

### Issue #1: Handler Registration Timing

**Problem**: The WebSocket message handler is registered at **store creation time**, not at recording start time.

**Timeline**:
```
1. App loads → voice.ts imported
2. createVoiceStore() runs → Line 157 executes
3. websocket.onMessage() registers handler
4. BUT: WebSocket might not be connected yet!
5. User navigates to chat → WebSocket connects
6. User clicks mic → Recording starts
7. Deepgram sends voice_transcript messages
8. Handler receives messages... but where does the data go?
```

**The Critical Question**: Does the `update()` function at line 160-164 still reference the correct store instance after WebSocket reconnection?

---

### Issue #2: Multiple Handler Registration

Looking at `websocket.ts` line 146-151:

```typescript
onMessage(handler: (data: any) => void) {
    messageHandlers.push(handler);
    return () => {
        messageHandlers = messageHandlers.filter(h => h !== handler);
    };
}
```

**This returns an unsubscribe function**, but **voice.ts never calls it!**

**Problem**: The handler registration at line 157 has **no cleanup**. This means:
- Handler stays registered even if not needed
- No way to unregister or re-register
- If WebSocket disconnects/reconnects, old handler might be dead

---

### Issue #3: Store Update Closure Problem

The `update()` function used at lines 160 and 167 is a **closure** over the writable store created at line 25.

**Potential Issue**: If the WebSocket handler is called AFTER the store is imported elsewhere, the closure might be stale.

**JavaScript Closure Trap**:
```typescript
// At module load time (before websocket connects):
const { update } = writable({ ... });  // Line 25-33

// Later, websocket.onMessage handler fires:
update(s => ({ ...s, finalTranscript: ... }))  // Line 160

// Question: Does this update affect the exported `voice` store?
// Or is it updating a dead closure?
```

---

### Issue #4: Handler Never Fires (Most Likely)

Given that **nothing appears anywhere** (not in input, not in chat, not even errors), the most likely scenario is:

**The `websocket.onMessage()` handler is never being called for `voice_transcript` messages.**

**Possible Causes**:

1. **Handler Registration Race**: Handler registered before WebSocket connection exists
2. **Session Store Handler Override**: `session.ts` also uses `websocket.onMessage()` (line 176), might be intercepting messages
3. **Message Type Mismatch**: Backend sends slightly different message type
4. **WebSocket Not Connected During Recording**: Connection drops between voice_start and transcript delivery

---

## Evidence from Multiple Message Handlers

### session.ts Also Registers a Handler (Line 176)

```typescript
unsubscribe = websocket.onMessage((data) => {
    switch (data.type) {
        case 'stream_chunk':
            // ... handle streaming ...
        case 'cognitive_state':
            // ... handle cognitive state ...
        // ... other cases ...
    }
});
```

**CRITICAL OBSERVATION**:
- `session.ts` registers a handler with `switch/case` for specific message types
- `voice.ts` registers a handler with `if` statements for voice message types
- **Both handlers run on EVERY WebSocket message**
- websocket.ts line 92: `messageHandlers.forEach(handler => handler(data));`

**This should work**, but only if:
1. The voice.ts handler is actually registered
2. The WebSocket connection exists when messages arrive
3. The `update()` closure is still valid

---

## Diagnostic Questions

### Question 1: Is the Handler Even Registered?

**Test**: Add logging to voice.ts line 157:
```typescript
websocket.onMessage((data: any) => {
    console.log('[VOICE DEBUG] Received message type:', data.type);  // ADD THIS
    if (data.type === 'voice_transcript') {
        console.log('[VOICE DEBUG] Processing voice_transcript:', data);  // ADD THIS
        // ... rest of code ...
    }
});
```

**Expected Output** (if working):
- On ANY WebSocket message: `[VOICE DEBUG] Received message type: connected`
- On transcript: `[VOICE DEBUG] Received message type: voice_transcript`
- On transcript: `[VOICE DEBUG] Processing voice_transcript: {...}`

**If you see NOTHING**: Handler was never registered or WebSocket not connected

---

### Question 2: Is Backend Sending Transcripts?

**Check Backend Logs**: Look for this in your backend console/logs:

```
[Voice] Deepgram connected for session {session_id}
```

And when speaking:
```
(Should see transcript being sent back)
```

**If missing**: Deepgram connection failing (API key issue or network)

---

### Question 3: Are WebSocket Messages Arriving?

**Open Browser DevTools → Network → WS tab**

1. Click on the WebSocket connection
2. Click "Messages" tab
3. Start recording and speak
4. Check for messages:

**Expected to see**:
```
→ {type: "voice_start", timestamp: ...}
→ {type: "voice_chunk", audio: "UklGR...", timestamp: ...}
→ {type: "voice_chunk", audio: "UklGR...", timestamp: ...}
← {type: "voice_transcript", transcript: "hello", is_final: false, ...}
← {type: "voice_transcript", transcript: "hello world", is_final: true, ...}
→ {type: "voice_stop", timestamp: ...}
```

**If you see `voice_start` and `voice_chunk` but NO `voice_transcript`**: Backend/Deepgram issue
**If you see `voice_transcript` coming back**: Frontend handler issue (handler not running or update() broken)

---

## Most Likely Scenario (Based on Symptoms)

Given:
- ✅ Waveform shows (audio capture works)
- ✅ Recording indicator works (UI state updates work)
- ❌ No text appears anywhere
- ❌ No errors visible

**Hypothesis**: One of these is true:

### Scenario A: Backend Not Sending Transcripts
- Deepgram API key missing or invalid
- Deepgram connection failing silently
- Backend error handler not triggered
- **Check**: Backend logs for `[Voice] Deepgram connected` message

### Scenario B: WebSocket Messages Not Arriving at Frontend
- Network issue between browser and backend
- WebSocket dropped during recording
- Firewall blocking bidirectional WebSocket traffic
- **Check**: Browser DevTools → Network → WS tab for incoming messages

### Scenario C: Handler Not Processing Messages
- voice.ts handler never registered (module load order issue)
- handler registered but update() closure is dead
- handler registered but WebSocket instance changed (reconnection)
- **Check**: Add console.log to line 157 and see if it fires

---

## Step-by-Step Diagnostic Protocol

### Step 1: Verify Backend Connection
1. Open backend logs/console
2. Start the app
3. Click mic button
4. **Look for**: `[Voice] Deepgram connected for session {id}`
5. **If missing**: Check `DEEPGRAM_API_KEY` environment variable

### Step 2: Verify WebSocket Messages
1. Open Browser DevTools (F12)
2. Go to Network tab → WS (WebSocket filter)
3. Click on the active WebSocket connection
4. Go to "Messages" sub-tab
5. Start recording and speak
6. **Look for**: Incoming messages with `type: "voice_transcript"`
7. **If missing**: Backend is not sending (Deepgram issue)
8. **If present**: Frontend handler issue

### Step 3: Verify Handler Execution
1. Open `frontend/src/lib/stores/voice.ts`
2. Add logging at line 157:
   ```typescript
   websocket.onMessage((data: any) => {
       console.log('[VOICE] Handler called with:', data.type);
       // ... rest of handler
   });
   ```
3. Reload app and test recording
4. **Check console for**: `[VOICE] Handler called with: ...`
5. **If missing**: Handler never registered or WebSocket not connected
6. **If present but no 'voice_transcript'**: Messages not arriving or type mismatch

### Step 4: Verify Store Update
1. After adding logging to handler, also log the update:
   ```typescript
   if (data.type === 'voice_transcript') {
       console.log('[VOICE] Updating store with transcript:', data.transcript);
       update(s => {
           console.log('[VOICE] Current state:', s);
           return {
               ...s,
               finalTranscript: s.finalTranscript + ' ' + data.transcript,
               transcript: '',
           };
       });
   }
   ```
2. Check console to see if store is actually updating
3. **If updating but UI not reflecting**: Reactive statement issue in ChatOverlay.svelte

---

## The Fix Direction (For Implementation Phase)

Based on the architecture, the proper fix would be:

### Option A: Move Handler Registration to Recording Start
Instead of registering at module load, register when recording starts:

```typescript
async function startRecording() {
    // ... existing code ...

    // Register handler for this recording session
    const unsubscribe = websocket.onMessage((data: any) => {
        // ... handle transcripts ...
    });

    // Store unsubscribe function to call on stop
}

function stopRecording() {
    // ... existing code ...

    // Unsubscribe from messages
    unsubscribe?.();
}
```

### Option B: Use a Dedicated Voice WebSocket
Create a separate WebSocket connection just for voice:

```typescript
let voiceWs: WebSocket | null = null;

async function startRecording() {
    // Open dedicated voice WebSocket
    voiceWs = new WebSocket(voiceWsUrl);
    voiceWs.onmessage = (event) => {
        // Handle transcripts directly
    };
}
```

### Option C: Fix the Handler Lifecycle
Ensure handler is properly registered and cleaned up:

```typescript
let voiceMessageUnsubscribe: (() => void) | null = null;

// Register handler on first use
function ensureHandlerRegistered() {
    if (!voiceMessageUnsubscribe) {
        voiceMessageUnsubscribe = websocket.onMessage((data: any) => {
            // ... handle transcripts ...
        });
    }
}

// Call in startRecording
async function startRecording() {
    ensureHandlerRegistered();
    // ... rest of recording logic ...
}
```

---

## Immediate Action Items

**For Troubleshooting** (in order of priority):

1. ✅ **Check Backend Logs**
   - Look for: `[Voice] Deepgram connected for session {id}`
   - Look for: `DEEPGRAM_API_KEY not configured` error
   - Look for: Any errors during voice session

2. ✅ **Check Browser Network Tab**
   - Open DevTools → Network → WS
   - Record and speak
   - Verify `voice_transcript` messages are arriving

3. ✅ **Add Debug Logging to voice.ts**
   - Line 157: Log every message received
   - Line 158: Log when voice_transcript detected
   - Line 160: Log store update

4. ✅ **Verify Environment Variable**
   ```bash
   # Check if Deepgram API key is set
   echo $DEEPGRAM_API_KEY
   # or
   printenv | grep DEEPGRAM
   ```

---

## Prediction

Based on the symptoms (waveform visible but no transcripts), I predict:

**80% Probability**: Backend is not connected to Deepgram
- Missing or invalid `DEEPGRAM_API_KEY`
- Backend logs will show: `[Voice] DEEPGRAM_API_KEY not configured`
- WebSocket messages tab will show `voice_start` and `voice_chunk` going out
- But **no** `voice_transcript` messages coming back

**15% Probability**: Frontend handler not receiving messages
- Handler registered too early (before WebSocket connected)
- Messages arrive but handler never fires
- Adding console.log at line 157 will show nothing

**5% Probability**: Handler fires but update() broken
- Closure issue with store update
- Messages logged in console but store state never changes

---

## Conclusion

The voice mode implementation is **architecturally sound** but has a **critical runtime bug** preventing transcriptions from appearing.

Most likely culprit: **Deepgram API key not configured** or **handler registration race condition**.

Follow the diagnostic protocol above to pinpoint the exact failure point, then the fix will be straightforward.

**Next Step**: Run the 4-step diagnostic protocol and report what you see in:
1. Backend logs
2. Browser Network → WS messages
3. Browser console (after adding debug logs)

---

**Report Status**: 🔴 Critical Bug Identified
**Confidence**: 🟢 High - Failure modes clearly defined
**Action Required**: Diagnostics to determine which failure mode is active
