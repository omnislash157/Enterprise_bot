# Feature Build Sheet: Voice Transcription (Deepgram)

## Feature: VOICE_TRANSCRIPTION
**Priority:** P1  
**Estimated Complexity:** Medium  
**Dependencies:** WebSocket infrastructure (exists), Deepgram API key

---

## 1. OVERVIEW

### User Story
> As an ADHD user, I want to speak and see my words appear instantly in the chat input so that I don't have to wait for batch transcription.

### Acceptance Criteria
- [ ] Mic button visible next to send button
- [ ] Click to start/stop recording (toggle)
- [ ] Text streams into input field as user speaks (<300ms latency)
- [ ] Final transcript auto-fills textarea for user review
- [ ] Recording state visually distinct (red pulsing)
- [ ] Works on Chrome/Edge desktop + Android
- [ ] Graceful error handling (permission denied, connection lost)

---

## 2. ENVIRONMENT VARIABLES

### Backend (Railway)
```
DEEPGRAM_API_KEY=your_deepgram_api_key_here
```

### Frontend
```
# No new env vars needed - uses existing VITE_API_URL
```

---

## 3. BACKEND CHANGES

### New File: `voice_transcription.py`

```python
"""
Voice Transcription Service - Deepgram WebSocket Bridge

Bridges browser audio to Deepgram's real-time STT API.
Audio arrives as base64 chunks, transcripts stream back.

Version: 1.0.0
"""

import asyncio
import base64
import json
import logging
import os
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


@dataclass
class DeepgramConfig:
    """Deepgram streaming configuration."""
    model: str = "nova-3"
    language: str = "en-US"
    smart_format: bool = True
    interim_results: bool = True
    punctuate: bool = True
    encoding: str = "webm-opus"
    sample_rate: int = 16000


class DeepgramBridge:
    """
    Manages a single Deepgram WebSocket connection per user session.
    
    Lifecycle:
    1. User clicks mic -> voice_start -> open Deepgram connection
    2. Audio chunks arrive -> forward to Deepgram
    3. Transcripts arrive <- forward to user
    4. User stops -> voice_stop -> close Deepgram connection
    """
    
    def __init__(
        self,
        session_id: str,
        on_transcript: Callable[[str, bool, float], Awaitable[None]],
        on_error: Callable[[str], Awaitable[None]],
        config: Optional[DeepgramConfig] = None
    ):
        self.session_id = session_id
        self.on_transcript = on_transcript
        self.on_error = on_error
        self.config = config or DeepgramConfig()
        
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._connected = False
    
    def _build_url(self) -> str:
        """Build Deepgram WebSocket URL with query params."""
        params = [
            f"model={self.config.model}",
            f"language={self.config.language}",
            f"smart_format={str(self.config.smart_format).lower()}",
            f"interim_results={str(self.config.interim_results).lower()}",
            f"punctuate={str(self.config.punctuate).lower()}",
            f"encoding={self.config.encoding}",
            f"sample_rate={self.config.sample_rate}",
        ]
        return f"{DEEPGRAM_WS_URL}?{'&'.join(params)}"
    
    async def connect(self) -> bool:
        """Open connection to Deepgram."""
        if not DEEPGRAM_API_KEY:
            logger.error("[Voice] DEEPGRAM_API_KEY not configured")
            await self.on_error("Voice transcription not configured")
            return False
        
        try:
            url = self._build_url()
            headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
            
            self._ws = await websockets.connect(
                url,
                extra_headers=headers,
                ping_interval=20,
                ping_timeout=10,
            )
            self._connected = True
            
            # Start receiving transcripts
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            logger.info(f"[Voice] Deepgram connected for session {self.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"[Voice] Deepgram connection failed: {e}")
            await self.on_error(f"Failed to connect: {str(e)}")
            return False
    
    async def _receive_loop(self):
        """Listen for transcripts from Deepgram."""
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                    
                    # Extract transcript from Deepgram response
                    if data.get("type") == "Results":
                        channel = data.get("channel", {})
                        alternatives = channel.get("alternatives", [])
                        
                        if alternatives:
                            transcript = alternatives[0].get("transcript", "")
                            confidence = alternatives[0].get("confidence", 0.0)
                            is_final = data.get("is_final", False)
                            
                            if transcript.strip():
                                await self.on_transcript(transcript, is_final, confidence)
                    
                    elif data.get("type") == "Metadata":
                        logger.debug(f"[Voice] Deepgram metadata: {data}")
                    
                    elif data.get("type") == "Error":
                        error_msg = data.get("message", "Unknown error")
                        logger.error(f"[Voice] Deepgram error: {error_msg}")
                        await self.on_error(error_msg)
                        
                except json.JSONDecodeError:
                    logger.warning(f"[Voice] Non-JSON message from Deepgram")
                    
        except ConnectionClosed as e:
            logger.info(f"[Voice] Deepgram connection closed: {e}")
        except Exception as e:
            logger.error(f"[Voice] Receive loop error: {e}")
            await self.on_error(str(e))
    
    async def send_audio(self, audio_base64: str):
        """Forward audio chunk to Deepgram."""
        if not self._connected or not self._ws:
            logger.warning("[Voice] Cannot send audio - not connected")
            return
        
        try:
            audio_bytes = base64.b64decode(audio_base64)
            await self._ws.send(audio_bytes)
        except Exception as e:
            logger.error(f"[Voice] Failed to send audio: {e}")
    
    async def close(self):
        """Close Deepgram connection."""
        self._connected = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            try:
                # Send close message to Deepgram
                await self._ws.send(json.dumps({"type": "CloseStream"}))
                await self._ws.close()
            except Exception as e:
                logger.debug(f"[Voice] Close error (expected): {e}")
        
        logger.info(f"[Voice] Deepgram disconnected for session {self.session_id}")


# Session management - one bridge per active voice session
_active_bridges: dict[str, DeepgramBridge] = {}


async def start_voice_session(
    session_id: str,
    on_transcript: Callable[[str, bool, float], Awaitable[None]],
    on_error: Callable[[str], Awaitable[None]],
) -> bool:
    """Start a new voice transcription session."""
    # Close existing if any
    if session_id in _active_bridges:
        await stop_voice_session(session_id)
    
    bridge = DeepgramBridge(session_id, on_transcript, on_error)
    success = await bridge.connect()
    
    if success:
        _active_bridges[session_id] = bridge
    
    return success


async def send_voice_chunk(session_id: str, audio_base64: str):
    """Send audio chunk to active voice session."""
    bridge = _active_bridges.get(session_id)
    if bridge:
        await bridge.send_audio(audio_base64)
    else:
        logger.warning(f"[Voice] No active session for {session_id}")


async def stop_voice_session(session_id: str):
    """Stop and cleanup voice transcription session."""
    bridge = _active_bridges.pop(session_id, None)
    if bridge:
        await bridge.close()
```

### Modify: `main.py` - WebSocket Handler

Add to imports (near top):
```python
from voice_transcription import start_voice_session, send_voice_chunk, stop_voice_session
```

Add to WebSocket handler (around line 730, after existing `elif` blocks):

```python
            # =============================================
            # VOICE TRANSCRIPTION
            # =============================================
            elif msg_type == "voice_start":
                logger.info(f"[WS] Voice session starting for {session_id}")
                
                async def on_transcript(transcript: str, is_final: bool, confidence: float):
                    await websocket.send_json({
                        "type": "voice_transcript",
                        "transcript": transcript,
                        "is_final": is_final,
                        "confidence": confidence,
                        "timestamp": time.time()
                    })
                
                async def on_error(error: str):
                    await websocket.send_json({
                        "type": "voice_error",
                        "error": error,
                        "timestamp": time.time()
                    })
                
                success = await start_voice_session(session_id, on_transcript, on_error)
                
                await websocket.send_json({
                    "type": "voice_started" if success else "voice_error",
                    "success": success,
                    "error": None if success else "Failed to start voice session",
                    "timestamp": time.time()
                })
            
            elif msg_type == "voice_chunk":
                audio_data = data.get("audio")
                if audio_data:
                    await send_voice_chunk(session_id, audio_data)
            
            elif msg_type == "voice_stop":
                logger.info(f"[WS] Voice session stopping for {session_id}")
                await stop_voice_session(session_id)
                await websocket.send_json({
                    "type": "voice_stopped",
                    "timestamp": time.time()
                })
```

Add cleanup on disconnect (in the `except WebSocketDisconnect` block):
```python
    except WebSocketDisconnect:
        manager.disconnect(session_id)
        metrics_collector.record_ws_disconnect()
        # NEW: Cleanup voice session if active
        await stop_voice_session(session_id)
        logger.info(f"[WS] WebSocket disconnected: {session_id}")
```

### Add dependency: `requirements.txt`

```
websockets>=12.0
```

---

## 4. FRONTEND CHANGES

### New File: `frontend/src/lib/stores/voice.ts`

```typescript
import { writable, derived, get } from 'svelte/store';
import { websocket } from './websocket';

// ============================================================================
// TYPES
// ============================================================================

type RecordingState = 'idle' | 'requesting' | 'recording' | 'processing' | 'error';

export interface VoiceState {
    isRecording: boolean;
    state: RecordingState;
    transcript: string;
    finalTranscript: string;
    error: string | null;
    permissionGranted: boolean;
    permissionDenied: boolean;
}

// ============================================================================
// STORE
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

    let mediaRecorder: MediaRecorder | null = null;
    let audioStream: MediaStream | null = null;

    async function requestPermission(): Promise<boolean> {
        update(s => ({ ...s, state: 'requesting' }));

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000,
                }
            });

            update(s => ({
                ...s,
                permissionGranted: true,
                permissionDenied: false,
                state: 'idle',
            }));

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

    async function startRecording() {
        const state = get({ subscribe });
        
        if (!state.permissionGranted) {
            const granted = await requestPermission();
            if (!granted) return;
        }

        if (!audioStream) {
            audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        }

        // Notify backend to open Deepgram connection
        websocket.send({
            type: 'voice_start',
            timestamp: Date.now(),
        });

        mediaRecorder = new MediaRecorder(audioStream, {
            mimeType: 'audio/webm;codecs=opus',
        });

        mediaRecorder.ondataavailable = async (event) => {
            if (event.data.size > 0) {
                const reader = new FileReader();
                reader.onloadend = () => {
                    const base64 = (reader.result as string).split(',')[1];
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

        mediaRecorder.start(100); // 100ms chunks

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

        setTimeout(() => {
            update(s => ({ ...s, state: 'idle' }));
        }, 1000);
    }

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

        if (data.type === 'voice_error') {
            update(s => ({
                ...s,
                state: 'error',
                error: data.error,
                isRecording: false,
            }));
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }
        }
    });

    return {
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

        clearTranscript() {
            update(s => ({ ...s, transcript: '', finalTranscript: '' }));
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
        }
    };
}

export const voice = createVoiceStore();
export const isRecording = derived(voice, $voice => $voice.isRecording);
```

### Modify: `frontend/src/lib/stores/index.ts`

Add export:
```typescript
export { voice, isRecording } from './voice';
export type { VoiceState } from './voice';
```

### Modify: `frontend/src/lib/components/ChatOverlay.svelte`

**Add import (near line 7):**
```typescript
import { voice } from '$lib/stores/voice';
```

**Add handler function (around line 95):**
```typescript
async function toggleRecording() {
    await voice.toggle();
}

// Reactive: when finalTranscript updates, append to input
$: if ($voice.finalTranscript && $voice.finalTranscript.trim()) {
    inputValue = (inputValue + ' ' + $voice.finalTranscript).trim();
    voice.clearTranscript();
}
```

**Add mic button in template (line ~334, between textarea and send button):**
```svelte
<!-- Voice Input Button -->
<button
    class="mic-button"
    class:recording={$voice.isRecording}
    on:click={toggleRecording}
    disabled={!$websocket.connected}
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

{#if $voice.transcript}
    <div class="voice-preview">{$voice.transcript}</div>
{/if}
```

**Add styles (after .send-button styles, ~line 797):**
```css
/* Voice Input Button */
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
    border-color: #333;
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

/* Voice Preview (interim transcript) */
.voice-preview {
    position: absolute;
    bottom: 100%;
    left: 0;
    right: 0;
    padding: 0.75rem 1rem;
    background: rgba(0, 0, 0, 0.9);
    border: 1px solid rgba(0, 255, 65, 0.3);
    border-radius: 8px;
    margin-bottom: 0.5rem;
    color: #00ff41;
    font-size: 0.9rem;
    font-style: italic;
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

## 5. INTEGRATION CHECKLIST

### Backend
- [ ] `voice_transcription.py` created
- [ ] `DEEPGRAM_API_KEY` env var set in Railway
- [ ] `websockets` added to requirements.txt
- [ ] Voice handlers added to main.py WebSocket
- [ ] Cleanup added to WebSocketDisconnect handler
- [ ] Test: curl voice_start message works

### Frontend
- [ ] `voice.ts` store created
- [ ] Export added to `stores/index.ts`
- [ ] Voice store imported in ChatOverlay
- [ ] Mic button added to template
- [ ] CSS styles added
- [ ] Reactive transcript → input binding works
- [ ] Test: Button appears and toggles state

### End-to-End
- [ ] Click mic → recording starts
- [ ] Speak → text appears in preview
- [ ] Stop → final text fills input
- [ ] Permission denied → error shown
- [ ] WS disconnect during recording → graceful stop

---

## 6. TESTING COMMANDS

```bash
# Backend - verify Deepgram connection
curl -X GET "https://api.deepgram.com/v1/projects" \
  -H "Authorization: Token YOUR_DEEPGRAM_KEY"

# Should return 200 with project list

# Backend - local WebSocket test (using websocat)
websocat ws://localhost:8000/ws/test-session
# Send: {"type": "voice_start"}
# Should receive: {"type": "voice_started", "success": true}

# Frontend - browser console test
voice.toggle()  // Start recording
voice.toggle()  // Stop recording
$voice          // Check state
```

---

## 7. AGENT EXECUTION BLOCK

```
FEATURE BUILD: VOICE_TRANSCRIPTION

TASK 1 - Backend Setup:
- Create file: voice_transcription.py [paste code block]
- Add to requirements.txt: websockets>=12.0
- Run: pip install websockets

TASK 2 - Backend Integration:
- Edit main.py: Add import for voice_transcription
- Edit main.py: Add voice_start/voice_chunk/voice_stop handlers (~line 730)
- Edit main.py: Add cleanup in WebSocketDisconnect handler

TASK 3 - Frontend Store:
- Create file: src/lib/stores/voice.ts [paste code block]
- Edit src/lib/stores/index.ts: Add voice exports

TASK 4 - Frontend UI:
- Edit ChatOverlay.svelte: Add voice import
- Edit ChatOverlay.svelte: Add toggleRecording handler
- Edit ChatOverlay.svelte: Add mic button template
- Edit ChatOverlay.svelte: Add CSS styles

TASK 5 - Environment:
- Railway: Add DEEPGRAM_API_KEY env var

TASK 6 - Verify:
- Backend: Start server, check no import errors
- Frontend: npm run dev, check mic button visible
- Integration: Click mic, speak, verify text appears

COMPLETION CRITERIA:
- Mic button visible in chat input area
- Recording indicator pulses red when active
- Transcript streams into input field
- No console errors
```

---

## 8. ROLLBACK PLAN

```bash
# Git rollback
git revert HEAD~N  # N = number of commits

# Remove env var
railway variables remove DEEPGRAM_API_KEY

# Frontend - remove voice store import from ChatOverlay if breaking
```

---

## 9. COST ESTIMATE

| Usage | Minutes/Month | Cost |
|-------|---------------|------|
| Light (10 users, 5 min/day) | 1,500 | $11.55 |
| Medium (50 users, 10 min/day) | 15,000 | $115.50 |
| Heavy (100 users, 15 min/day) | 45,000 | $346.50 |

**Deepgram Nova-3 streaming:** $0.0077/minute

---

**END OF BUILD SHEET**
