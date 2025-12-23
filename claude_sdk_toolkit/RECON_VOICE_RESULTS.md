# VOICE TRANSCRIPTION FRONTEND - RECONNAISSANCE RESULTS

**Mission Status:** ✅ COMPLETE
**Date:** 2024-12-23
**Target:** Voice transcription (Deepgram) integration into chat interface

---

## EXECUTIVE SUMMARY

The frontend is a **Svelte + TypeScript** application with a **cyberpunk/neon-green theme**. It uses **inline SVG icons** (no icon library), **custom CSS** with a glass-morphism design system, and a **WebSocket store pattern** for real-time communication. The chat input is a **textarea** with a send button, perfectly positioned to add a microphone button. **No existing audio code detected** - this will be a greenfield implementation.

---

## TASK 1: CHAT INPUT AREA ANALYSIS

### Location & Structure

**File:** `frontend/src/lib/components/ChatOverlay.svelte`
**Lines:** 320-342 (input area), 719-804 (styles)

```svelte
<!-- Input Area (Line 319-342) -->
<div class="input-area">
    <div class="input-wrapper">
        <textarea
            bind:this={inputElement}
            bind:value={inputValue}
            placeholder="Ask about company procedures, policies, or operations..."
            disabled={!$websocket.connected}
            on:keydown={handleKeydown}
            rows="1"
        ></textarea>
        <button
            class="send-button"
            on:click={sendMessage}
            disabled={!$websocket.connected || !inputValue.trim()}
            aria-label="Send message"
        >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" />
            </svg>
        </button>
    </div>
    <p class="input-hint">Press Enter to send, Shift+Enter for new line</p>
</div>
```

### Key Findings

| Property | Value |
|----------|-------|
| **CHAT_INPUT_LOCATION** | `ChatOverlay.svelte` lines 322-329 |
| **INPUT_TYPE** | `<textarea>` with auto-resize (rows="1") |
| **EXISTING_BUTTONS** | Single send button (336px, right side of textarea) |
| **SUBMIT_PATTERN** | `on:click={sendMessage}` + Enter key handler (line 98-101) |
| **STATE_BINDING** | `bind:value={inputValue}` → local component state (line 48) |
| **BUTTON_STYLES** | `.send-button` (lines 762-796) |

### Button CSS Pattern (Send Button)

```css
.send-button {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    background: #00ff41;  /* Neon green */
    border: none;
    color: #000;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    flex-shrink: 0;
}

.send-button:hover:not(:disabled) {
    background: #00ff41;
    box-shadow: 0 0 25px rgba(0, 255, 65, 0.5);
    transform: scale(1.02);
}

.send-button:disabled {
    background: #333;
    color: #666;
    cursor: not-allowed;
}
```

### Input Wrapper Layout

```css
.input-wrapper {
    display: flex;
    gap: 0.75rem;
    align-items: flex-end;
}
```

**Perfect for adding a mic button!** We can insert it between the textarea and send button:
```
[textarea] [mic-button] [send-button]
```

---

## TASK 2: WEBSOCKET ARCHITECTURE

### Connection & Message Handling

**Files:**
- `frontend/src/lib/stores/websocket.ts` (165 lines)
- `frontend/src/lib/stores/session.ts` (442 lines)

### WebSocket URL Pattern

```typescript
// websocket.ts line 11-30
function getWebSocketUrl(sessionId: string): string {
    const apiUrl = import.meta.env.VITE_API_URL;
    if (apiUrl) {
        const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
        const host = new URL(apiUrl).host;
        return `${wsProtocol}://${host}/ws/${sessionId}`;
    }
    // Fallback to current location
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${wsProtocol}://${window.location.host}/ws/${sessionId}`;
}
```

### Existing Message Types

**Handled in `session.ts` lines 176-297:**

| Type | Direction | Purpose | Handler Line |
|------|-----------|---------|--------------|
| `stream_chunk` | ← Server | LLM response streaming | 178 |
| `verified` | ← Server | Auth confirmation | 210 |
| `division_changed` | ← Server | Department switch confirm | 234 |
| `cognitive_state` | ← Server | AI thinking phase updates | 243 |
| `session_analytics` | ← Server | Session metrics | 255 |
| `connected` | ← Server | WS connection established | 279 |
| `error` | ← Server | Error messages | 283 |
| `message` | → Server | User chat message | 425 |
| `verify` | → Server | Auth with email/division | 338 |
| `set_division` | → Server | Change department | 369 |

### Send Pattern

```typescript
// websocket.ts line 138-144
send(data: any) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data));
    } else {
        console.warn('[WS] Cannot send - not connected');
    }
}
```

### Receive Pattern

```typescript
// websocket.ts line 89-101
ws.onmessage = (event) => {
    try {
        const data = JSON.parse(event.data);
        messageHandlers.forEach(handler => handler(data));
        // Auto-handle artifact emissions
        if (data.type === 'artifact_emit' && data.artifact) {
            artifacts.add(data.artifact, data.suggested || false);
        }
    } catch (e) {
        console.error('[WS] Failed to parse message:', e);
    }
};
```

### Binary Support

**Status:** ❌ NOT CURRENTLY SUPPORTED
**Current:** JSON-only (line 91: `JSON.parse(event.data)`)
**Implication:** Audio chunks must be sent as **base64-encoded strings** in JSON payloads

### Reconnection Pattern

```typescript
// websocket.ts line 47-64
function attemptReconnect() {
    if (!currentSessionId || reconnectAttempts >= maxReconnectAttempts) return;
    reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 10000);
    console.log(`[WS] Attempting reconnect in ${delay}ms (attempt ${reconnectAttempts}/${maxReconnectAttempts})`);
    setTimeout(() => {
        if (currentSessionId && !intentionalClose) {
            store.connect(currentSessionId);
        }
    }, delay);
}
```

**Exponential backoff:** 1s, 2s, 4s, 8s, 10s (max 5 attempts)

---

## TASK 3: UI COMPONENT PATTERNS

### Icon Library

**Result:** ❌ **NO ICON LIBRARY**
**Pattern:** Inline SVG elements with `viewBox="0 0 24 24"`

**Examples found:**
```svelte
<!-- Send button icon (line 336) -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" />
</svg>

<!-- Logout icon (line 277) -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
    <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
</svg>

<!-- Empty state icon (line 288) -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
</svg>
```

### Microphone Icon (Proposed)

```svelte
<!-- Recording state: OFF -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/>
    <line x1="8" y1="23" x2="16" y2="23"/>
</svg>

<!-- Recording state: ON (filled red) -->
<svg viewBox="0 0 24 24" fill="#ff0040" stroke="#ff0040" stroke-width="2">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/>
    <line x1="8" y1="23" x2="16" y2="23"/>
</svg>
```

### Button Styling Conventions

**Primary action (send button):**
```css
background: #00ff41;  /* neon-green */
color: #000;
border-radius: 12px;
box-shadow: 0 0 25px rgba(0, 255, 65, 0.5);  /* on hover */
```

**Secondary action (logout button):**
```css
background: rgba(255, 255, 255, 0.05);
border: 1px solid rgba(255, 255, 255, 0.1);
color: #888;
/* Hover: rgba(255, 68, 68, 0.1) for destructive actions */
```

**Proposed mic button (neutral state):**
```css
width: 56px;
height: 56px;
border-radius: 12px;
background: rgba(255, 255, 255, 0.05);
border: 1px solid rgba(0, 255, 65, 0.3);
color: #00ff41;
transition: all 0.2s;
```

**Proposed mic button (recording state):**
```css
background: rgba(255, 0, 64, 0.15);
border-color: #ff0040;
color: #ff0040;
box-shadow: 0 0 20px rgba(255, 0, 64, 0.4);
animation: pulse-recording 1.5s ease-in-out infinite;
```

### Theme Colors (from tailwind.config.js)

```javascript
colors: {
    'neon-green': '#00ff41',    // Primary accent
    'neon-cyan': '#00ffff',     // Secondary accent
    'neon-magenta': '#ff00ff',  // Tertiary
    'neon-yellow': '#ffff00',   // Warning
    'neon-red': '#ff0040',      // Error/danger
    'bg-primary': '#0a0a0a',    // Main background
    'bg-secondary': '#111111',  // Cards
    'bg-tertiary': '#1a1a1a',   // Modals
    'border-dim': '#222222',
    'border-glow': '#00ff4140',
    'text-primary': '#e0e0e0',
    'text-muted': '#808080',
}
```

### Loading/Recording Animation Pattern

**Example from ChatOverlay.svelte:**
```css
@keyframes pulse-glow {
    0%, 100% { opacity: 0.6; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.1); }
}
```

**Proposed for mic recording:**
```css
@keyframes pulse-recording {
    0%, 100% {
        box-shadow: 0 0 20px rgba(255, 0, 64, 0.4);
        transform: scale(1);
    }
    50% {
        box-shadow: 0 0 30px rgba(255, 0, 64, 0.6);
        transform: scale(1.05);
    }
}
```

### Tooltip Pattern

**Status:** ❌ **NO EXISTING TOOLTIP SYSTEM**
**Workaround:** Use `aria-label` for accessibility + custom CSS `:hover::after` pseudo-element

**Proposed tooltip CSS:**
```css
.mic-button[data-tooltip]:hover::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: calc(100% + 0.5rem);
    left: 50%;
    transform: translateX(-50%);
    padding: 0.5rem 0.75rem;
    background: rgba(0, 0, 0, 0.9);
    border: 1px solid rgba(0, 255, 65, 0.3);
    border-radius: 6px;
    font-size: 0.75rem;
    color: #e0e0e0;
    white-space: nowrap;
    pointer-events: none;
    z-index: 1000;
}
```

---

## TASK 4: STORE CREATION PATTERN

### Store Pattern (from auth.ts)

```typescript
// 1. Interface definition
interface StoreState {
    property: Type;
    // ...
}

// 2. Create store with writable
function createCustomStore() {
    const { subscribe, set, update } = writable<StoreState>({
        // initial state
    });

    // 3. Private variables (closures)
    let privateVar: Type | null = null;

    // 4. Public API methods
    const store = {
        subscribe,

        async asyncMethod(param: Type) {
            update(s => ({ ...s, loading: true }));
            try {
                // async operation
                update(s => ({ ...s, data: result, loading: false }));
            } catch (e) {
                update(s => ({ ...s, error: String(e), loading: false }));
            }
        },

        syncMethod() {
            update(s => ({ ...s, property: newValue }));
        }
    };

    return store;
}

// 5. Export singleton
export const customStore = createCustomStore();
```

### Async Pattern (from auth.ts)

```typescript
async refresh(): Promise<boolean> {
    if (!refreshToken) {
        update(s => ({ ...s, initialized: true }));
        return false;
    }

    try {
        const res = await fetch(`${apiBase}/api/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (!res.ok) {
            this.logout();
            return false;
        }

        const tokens = await res.json();
        // Update state
        update(s => ({ ...s, user: tokens.user }));
        return true;
    } catch (e) {
        console.error('Refresh failed:', e);
        return false;
    }
}
```

### Export Pattern (from index.ts)

```typescript
// Barrel exports
export { websocket } from './websocket';
export { session } from './session';
export type { SessionAnalytics } from './session';
export { auth, currentUser, isAuthenticated } from './auth';
```

---

## TASK 5: AUDIO/MEDIA PERMISSIONS

### Search Results

**Command:** `grep -r "mediaDevices|getUserMedia|MediaRecorder|AudioContext" frontend/src/`

**Result:** ❌ **NO MATCHES FOUND**

### Conclusion

- ✅ **No existing audio code**
- ✅ **Greenfield implementation**
- ⚠️ **Permission UX must be designed from scratch**
- ⚠️ **No existing patterns to follow**

---

## DELIVERABLE 1: CHAT INPUT BLUEPRINT

### Exact Integration Point

**File:** `frontend/src/lib/components/ChatOverlay.svelte`
**Line:** 321 (inside `.input-wrapper`)

**Current structure:**
```svelte
<div class="input-wrapper">
    <textarea ... />
    <button class="send-button" ... />
</div>
```

**Modified structure:**
```svelte
<div class="input-wrapper">
    <textarea ... />

    <!-- NEW: Voice button -->
    <button
        class="mic-button"
        class:recording={$voice.isRecording}
        on:click={toggleRecording}
        disabled={!$websocket.connected || $voice.isRecording}
        aria-label={$voice.isRecording ? 'Stop recording' : 'Start voice input'}
        data-tooltip={$voice.isRecording ? 'Recording...' : 'Voice input'}
    >
        <svg viewBox="0 0 24 24" fill={$voice.isRecording ? 'currentColor' : 'none'} stroke="currentColor" stroke-width="2">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
            <line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
    </button>

    <button class="send-button" ... />
</div>
```

### Required CSS Addition

```css
/* Add after .send-button styles (line 797) */

.mic-button {
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

.mic-button:hover:not(:disabled):not(.recording) {
    background: rgba(0, 255, 65, 0.1);
    border-color: #00ff41;
    box-shadow: 0 0 20px rgba(0, 255, 65, 0.3);
    transform: scale(1.02);
}

.mic-button.recording {
    background: rgba(255, 0, 64, 0.15);
    border-color: #ff0040;
    color: #ff0040;
    animation: pulse-recording 1.5s ease-in-out infinite;
}

.mic-button:disabled {
    background: #333;
    color: #666;
    cursor: not-allowed;
}

.mic-button svg {
    width: 22px;
    height: 22px;
}

@keyframes pulse-recording {
    0%, 100% {
        box-shadow: 0 0 20px rgba(255, 0, 64, 0.4);
        transform: scale(1);
    }
    50% {
        box-shadow: 0 0 30px rgba(255, 0, 64, 0.6);
        transform: scale(1.05);
    }
}

/* Tooltip */
.mic-button[data-tooltip]:hover::before {
    content: attr(data-tooltip);
    position: absolute;
    bottom: calc(100% + 0.5rem);
    left: 50%;
    transform: translateX(-50%);
    padding: 0.5rem 0.75rem;
    background: rgba(0, 0, 0, 0.9);
    border: 1px solid rgba(0, 255, 65, 0.3);
    border-radius: 6px;
    font-size: 0.75rem;
    color: #e0e0e0;
    white-space: nowrap;
    pointer-events: none;
    z-index: 1000;
}
```

---

## DELIVERABLE 2: WEBSOCKET INTEGRATION POINTS

### New Message Types to Add

Add to `session.ts` message handler (line 176):

```typescript
case 'voice_transcript':
    // Interim or final transcript from Deepgram
    update(s => ({
        ...s,
        currentStream: data.is_final ? '' : data.transcript,
        inputValue: data.is_final ? data.transcript : s.inputValue,
    }));

    if (data.is_final) {
        // Auto-send the final transcript as a message
        session.sendMessage(data.transcript);
    }
    break;

case 'voice_error':
    console.error('[Voice] Transcription error:', data.error);
    // Show error toast
    update(s => ({
        ...s,
        error: data.error,
    }));
    break;
```

### Backend Expected Message Types

**Reference from RECON_VOICE_FRONTEND.md:**

```typescript
// Client → Server
websocket.send({
    type: 'voice_start',
    timestamp: Date.now()
});

websocket.send({
    type: 'voice_chunk',
    audio: base64EncodedAudioChunk,  // base64 string
    timestamp: Date.now()
});

websocket.send({
    type: 'voice_stop',
    timestamp: Date.now()
});

// Server → Client
{
    type: 'voice_transcript',
    transcript: 'hello world',
    is_final: false,  // true when sentence complete
    confidence: 0.95,
    timestamp: Date.now()
}

{
    type: 'voice_error',
    error: 'Failed to connect to Deepgram',
    timestamp: Date.now()
}
```

---

## DELIVERABLE 3: UI PATTERN GUIDE

### Component Hierarchy

```
ChatOverlay.svelte
├── <textarea> (existing)
├── <MicButton> (NEW)
│   ├── State: idle | recording | processing | error
│   ├── Visual: icon + color + animation
│   └── Tooltip: hover text
└── <SendButton> (existing)
```

### State-Based Styling Matrix

| State | Background | Border | Color | Animation | Cursor |
|-------|------------|--------|-------|-----------|--------|
| **idle** | `rgba(255,255,255,0.05)` | `rgba(0,255,65,0.3)` | `#00ff41` | none | pointer |
| **hover** | `rgba(0,255,65,0.1)` | `#00ff41` | `#00ff41` | scale(1.02) | pointer |
| **recording** | `rgba(255,0,64,0.15)` | `#ff0040` | `#ff0040` | pulse-recording | pointer |
| **disabled** | `#333` | none | `#666` | none | not-allowed |
| **error** | `rgba(255,0,64,0.2)` | `#ff0040` | `#ff0040` | shake | pointer |

### Accessibility Requirements

```svelte
<button
    class="mic-button"
    role="button"
    aria-label="Start voice input"
    aria-pressed={isRecording}
    aria-live="polite"
    aria-describedby="mic-status"
    tabindex="0"
>
    <!-- icon -->
</button>

<span id="mic-status" class="sr-only">
    {isRecording ? 'Recording in progress' : 'Voice input available'}
</span>
```

---

## DELIVERABLE 4: STORE TEMPLATE

### File: `frontend/src/lib/stores/voice.ts`

```typescript
import { writable, derived, get } from 'svelte/store';
import { websocket } from './websocket';

// ============================================================================
// TYPES
// ============================================================================

type RecordingState = 'idle' | 'requesting' | 'recording' | 'processing' | 'error';

interface VoiceState {
    isRecording: boolean;
    state: RecordingState;
    transcript: string;  // Interim transcript
    finalTranscript: string;
    error: string | null;
    permissionGranted: boolean;
    permissionDenied: boolean;
}

// ============================================================================
// STORE CREATION
// ============================================================================

function createVoiceStore() {
    const { subscribe, set, update } = writable<VoiceState>({
        isRecording: false,
        state: 'idle',
        transcript: '',
        finalTranscript: '',
        error: null,
        permissionGranted: false,
        permissionDenied: false,
    });

    // Private variables (closure)
    let mediaRecorder: MediaRecorder | null = null;
    let audioStream: MediaStream | null = null;
    let recordingInterval: number | null = null;

    // ========================================
    // PERMISSION HANDLING
    // ========================================

    async function requestPermission(): Promise<boolean> {
        update(s => ({ ...s, state: 'requesting' }));

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000,  // Deepgram recommended
                }
            });

            update(s => ({
                ...s,
                permissionGranted: true,
                permissionDenied: false,
                state: 'idle',
            }));

            // Store stream for later use
            audioStream = stream;
            return true;

        } catch (error) {
            console.error('[Voice] Permission denied:', error);
            update(s => ({
                ...s,
                permissionGranted: false,
                permissionDenied: true,
                state: 'error',
                error: 'Microphone permission denied',
            }));
            return false;
        }
    }

    // ========================================
    // RECORDING CONTROL
    // ========================================

    async function startRecording() {
        // Check permission
        if (!get({ subscribe }).permissionGranted) {
            const granted = await requestPermission();
            if (!granted) return;
        }

        if (!audioStream) {
            audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        }

        // Create MediaRecorder
        mediaRecorder = new MediaRecorder(audioStream, {
            mimeType: 'audio/webm;codecs=opus',
        });

        // Handle audio data
        mediaRecorder.ondataavailable = async (event) => {
            if (event.data.size > 0) {
                // Convert blob to base64
                const reader = new FileReader();
                reader.onloadend = () => {
                    const base64 = (reader.result as string).split(',')[1];

                    // Send to backend
                    websocket.send({
                        type: 'voice_chunk',
                        audio: base64,
                        timestamp: Date.now(),
                    });
                };
                reader.readAsDataURL(event.data);
            }
        };

        mediaRecorder.onerror = (error) => {
            console.error('[Voice] Recording error:', error);
            stopRecording();
            update(s => ({
                ...s,
                state: 'error',
                error: 'Recording failed',
            }));
        };

        // Start recording
        mediaRecorder.start(100);  // Capture in 100ms chunks

        // Notify backend
        websocket.send({
            type: 'voice_start',
            timestamp: Date.now(),
        });

        update(s => ({
            ...s,
            isRecording: true,
            state: 'recording',
            transcript: '',
            error: null,
        }));

        console.log('[Voice] Recording started');
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }

        if (recordingInterval) {
            clearInterval(recordingInterval);
            recordingInterval = null;
        }

        // Notify backend
        websocket.send({
            type: 'voice_stop',
            timestamp: Date.now(),
        });

        update(s => ({
            ...s,
            isRecording: false,
            state: 'processing',
        }));

        console.log('[Voice] Recording stopped');

        // Reset state after processing
        setTimeout(() => {
            update(s => ({ ...s, state: 'idle' }));
        }, 2000);
    }

    // ========================================
    // MESSAGE HANDLER
    // ========================================

    function initMessageHandler() {
        return websocket.onMessage((data) => {
            if (data.type === 'voice_transcript') {
                if (data.is_final) {
                    update(s => ({
                        ...s,
                        finalTranscript: data.transcript,
                        transcript: '',
                    }));
                } else {
                    update(s => ({
                        ...s,
                        transcript: data.transcript,
                    }));
                }
            }

            if (data.type === 'voice_error') {
                update(s => ({
                    ...s,
                    state: 'error',
                    error: data.error,
                    isRecording: false,
                }));
                if (mediaRecorder) {
                    mediaRecorder.stop();
                }
            }
        });
    }

    // ========================================
    // PUBLIC API
    // ========================================

    const store = {
        subscribe,

        async toggle() {
            const state = get({ subscribe });
            if (state.isRecording) {
                stopRecording();
            } else {
                await startRecording();
            }
        },

        stop() {
            stopRecording();
        },

        clearError() {
            update(s => ({ ...s, error: null, state: 'idle' }));
        },

        cleanup() {
            if (mediaRecorder) {
                mediaRecorder.stop();
                mediaRecorder = null;
            }
            if (audioStream) {
                audioStream.getTracks().forEach(track => track.stop());
                audioStream = null;
            }
            if (recordingInterval) {
                clearInterval(recordingInterval);
            }
        }
    };

    // Initialize message handler
    initMessageHandler();

    return store;
}

// ============================================================================
// EXPORTS
// ============================================================================

export const voice = createVoiceStore();

// Derived stores for convenience
export const isRecording = derived(voice, $voice => $voice.isRecording);
export const hasVoicePermission = derived(voice, $voice => $voice.permissionGranted);
```

### Export in `index.ts`

```typescript
// Add to frontend/src/lib/stores/index.ts
export { voice, isRecording, hasVoicePermission } from './voice';
export type { VoiceState } from './voice';  // if exported from voice.ts
```

---

## DELIVERABLE 5: CODE SNIPPETS

### Snippet 1: Import Voice Store in ChatOverlay

```typescript
// Add to line 7 (after other imports)
import { voice } from '$lib/stores/voice';
```

### Snippet 2: Toggle Recording Handler

```typescript
// Add to ChatOverlay.svelte <script> section (around line 95)
async function toggleRecording() {
    await voice.toggle();
}

// Auto-inject transcript into textarea when finalized
$: if ($voice.finalTranscript) {
    inputValue = $voice.finalTranscript;
    tick().then(() => inputElement?.focus());
}
```

### Snippet 3: Visual Feedback Component

```svelte
<!-- Add below input-hint (line 341) -->
{#if $voice.isRecording}
    <div class="recording-indicator" transition:fade>
        <span class="recording-dot"></span>
        <span class="recording-text">
            {$voice.transcript || 'Listening...'}
        </span>
    </div>
{/if}

{#if $voice.error}
    <div class="voice-error" transition:fade>
        <span class="error-icon">⚠</span>
        <span>{$voice.error}</span>
        <button on:click={() => voice.clearError()}>✕</button>
    </div>
{/if}
```

### Snippet 4: Visual Feedback CSS

```css
/* Add after input-hint styles */

.recording-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: rgba(255, 0, 64, 0.1);
    border: 1px solid rgba(255, 0, 64, 0.3);
    border-radius: 8px;
    margin-top: 0.5rem;
    font-size: 0.85rem;
    color: #ff6b6b;
}

.recording-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ff0040;
    animation: pulse-dot 1s ease-in-out infinite;
}

@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

.recording-text {
    flex: 1;
    font-style: italic;
}

.voice-error {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: rgba(255, 68, 68, 0.1);
    border: 1px solid rgba(255, 68, 68, 0.3);
    border-radius: 8px;
    margin-top: 0.5rem;
    font-size: 0.85rem;
    color: #ff6b6b;
}

.error-icon {
    color: #ff0040;
}

.voice-error button {
    background: none;
    border: none;
    color: #ff6b6b;
    cursor: pointer;
    font-size: 1rem;
    padding: 0;
    line-height: 1;
}
```

---

## DELIVERABLE 6: IMPLEMENTATION RECOMMENDATIONS

### 1. File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| **NEW** `stores/voice.ts` | Create | Voice recording + WebSocket integration |
| `stores/index.ts` | Modify | Export voice store |
| `components/ChatOverlay.svelte` | Modify | Add mic button + visual feedback |
| `stores/session.ts` | Modify | Add voice message handlers (lines 176-297) |

### 2. Implementation Order

1. **Phase 1: Store Creation** (30 min)
   - Create `voice.ts` with state management
   - Add to `index.ts` exports
   - Test permission flow

2. **Phase 2: UI Integration** (30 min)
   - Add mic button to ChatOverlay
   - Add CSS styles
   - Add tooltip

3. **Phase 3: Visual Feedback** (20 min)
   - Recording indicator
   - Error handling UI
   - Transcript preview

4. **Phase 4: WebSocket Handlers** (20 min)
   - Add message types to session.ts
   - Test voice_chunk sending
   - Test transcript receiving

5. **Phase 5: Testing** (30 min)
   - Permission flow
   - Recording start/stop
   - Error scenarios
   - Reconnection handling

**Total:** ~2.5 hours

### 3. Testing Checklist

- [ ] Mic permission request works
- [ ] Mic button disabled when WS disconnected
- [ ] Recording starts/stops cleanly
- [ ] Audio chunks sent to backend (check Network tab)
- [ ] Transcript appears in real-time
- [ ] Final transcript auto-fills textarea
- [ ] Error messages display correctly
- [ ] Button states visually distinct
- [ ] Tooltip appears on hover
- [ ] Keyboard shortcuts work (future: Space to hold)
- [ ] Mobile responsive (56px touch target)

### 4. Edge Cases to Handle

| Scenario | Handling |
|----------|----------|
| **Permission denied** | Show error, disable mic button |
| **WS disconnect during recording** | Auto-stop, show reconnecting state |
| **Backend Deepgram error** | Display error, allow retry |
| **MediaRecorder not supported** | Feature detection, show fallback message |
| **Mic already in use** | NotFoundError - show "Mic unavailable" |
| **User navigates away** | Cleanup audio stream in `onDestroy` |

### 5. Future Enhancements

- [ ] Push-to-talk (hold Spacebar to record)
- [ ] Waveform visualization during recording
- [ ] Language selection (Deepgram supports 30+ languages)
- [ ] Voice activity detection (auto-stop on silence)
- [ ] Keyboard shortcut (Cmd/Ctrl + M)
- [ ] Recording duration limit (prevent runaway costs)
- [ ] Audio level meter (visual feedback)
- [ ] Multi-language transcript confidence indicator

---

## APPENDIX A: FULL STACK FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER ACTION                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    [Click Mic Button]
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND: ChatOverlay.svelte                 │
│  • toggleRecording()                                            │
│  • voice.toggle() → voice.ts startRecording()                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BROWSER API: MediaRecorder                    │
│  • navigator.mediaDevices.getUserMedia()                        │
│  • ondataavailable → base64 encoding                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WEBSOCKET: voice.ts                          │
│  websocket.send({                                               │
│    type: 'voice_chunk',                                         │
│    audio: base64String,                                         │
│    timestamp: Date.now()                                        │
│  })                                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BACKEND: main.py /ws/{session_id}             │
│  • Receive voice_chunk                                          │
│  • Extract audio data                                           │
│  • Forward to Deepgram API                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DEEPGRAM API (External)                      │
│  • Real-time speech-to-text                                     │
│  • Return interim/final transcripts                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BACKEND: main.py (Response)                   │
│  await websocket.send_json({                                    │
│    type: 'voice_transcript',                                    │
│    transcript: 'hello world',                                   │
│    is_final: False,                                             │
│    confidence: 0.95                                             │
│  })                                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FRONTEND: session.ts (Handler)                │
│  case 'voice_transcript':                                       │
│    • Update voice.transcript (interim)                          │
│    • OR update voice.finalTranscript + send message            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UI: ChatOverlay.svelte                       │
│  • Display interim transcript below textarea                   │
│  • On final: inject into inputValue                            │
│  • Auto-send as chat message                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## APPENDIX B: BACKEND MESSAGE CONTRACT

### Expected Backend Implementation

```python
# main.py - Add to WebSocket handler (around line 730)

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # ... existing code ...

    while True:
        data = await websocket.receive_json()
        msg_type = data.get("type", "message")

        # NEW: Voice message handling
        if msg_type == "voice_start":
            # Initialize Deepgram connection
            await handle_voice_start(websocket, session_id)

        elif msg_type == "voice_chunk":
            # Forward audio to Deepgram
            audio_base64 = data.get("audio")
            await handle_voice_chunk(websocket, session_id, audio_base64)

        elif msg_type == "voice_stop":
            # Close Deepgram connection
            await handle_voice_stop(websocket, session_id)
```

### Response Examples

```python
# Interim transcript
await websocket.send_json({
    "type": "voice_transcript",
    "transcript": "hello wor",
    "is_final": False,
    "confidence": 0.85,
    "timestamp": time.time()
})

# Final transcript
await websocket.send_json({
    "type": "voice_transcript",
    "transcript": "hello world",
    "is_final": True,
    "confidence": 0.95,
    "timestamp": time.time()
})

# Error
await websocket.send_json({
    "type": "voice_error",
    "error": "Deepgram connection failed",
    "timestamp": time.time()
})
```

---

## SUCCESS CRITERIA ✅

- [x] Located exact chat input component and line numbers (Line 320-342)
- [x] Documented WebSocket message type pattern (JSON-only, base64 audio)
- [x] Identified icon library and button styles (Inline SVG, cyberpunk theme)
- [x] Found or confirmed no existing audio code (✅ NO AUDIO CODE)
- [x] Created actionable RECON_VOICE_RESULTS.md (THIS FILE)

---

## NEXT STEPS

1. **Backend Team:** Implement Deepgram integration in `main.py`
2. **Frontend Team:** Implement using this recon as blueprint
3. **Testing:** Use checklist in Deliverable 6
4. **Documentation:** Update user docs with voice input instructions

---

**END OF RECONNAISSANCE REPORT**

*Generated: 2024-12-23*
*Agent: Claude (Reconnaissance Specialist)*
*Status: MISSION COMPLETE* ✅
