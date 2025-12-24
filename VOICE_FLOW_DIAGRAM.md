# Voice Transcription Data Flow - Current vs Fixed

## 🔴 CURRENT BROKEN STATE (HTTP 400)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BROWSER (Frontend)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. User clicks Mic Button                                         │
│     ↓                                                               │
│  2. getUserMedia({ audio: { sampleRate: 16000 }})                  │
│     ↓                                                               │
│  3. MediaRecorder captures at ~16kHz                               │
│     ↓                                                               │
│  4. Encodes to: audio/webm;codecs=opus (16kHz)                     │
│     ↓                                                               │
│  5. Base64 encode chunks                                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket: voice_chunk
                              │ { type: "voice_chunk", audio: "base64..." }
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND (Python/FastAPI)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  6. Receives voice_start message                                   │
│     ↓                                                               │
│  7. Opens WebSocket to Deepgram with params:                       │
│     wss://api.deepgram.com/v1/listen?                              │
│       model=nova-2                                                  │
│       encoding=webm-opus                                            │
│       sample_rate=48000  ⚠️  EXPECTS 48kHz                         │
│     ↓                                                               │
│  8. Receives voice_chunk, decodes base64                           │
│     ↓                                                               │
│  9. Forwards raw audio bytes to Deepgram                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket to Deepgram
                              │ Raw audio bytes (16kHz webm-opus)
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    DEEPGRAM API (External)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  10. Receives audio stream                                         │
│      ↓                                                              │
│  11. Expects: 48kHz webm-opus                                      │
│      Receives: 16kHz webm-opus                                     │
│      ↓                                                              │
│  12. ❌ MISMATCH DETECTED                                          │
│      ↓                                                              │
│  13. Rejects WebSocket handshake                                   │
│      Returns: HTTP 400 Bad Request                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP 400 Error
                              ↓
                    ❌ Connection Failed
                    User sees: "Failed to connect"
```

---

## ✅ FIXED STATE (Working Transcription)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BROWSER (Frontend)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. User clicks Mic Button                                         │
│     ↓                                                               │
│  2. getUserMedia({ audio: { sampleRate: 48000 }})  ✅ FIXED        │
│     ↓                                                               │
│  3. MediaRecorder captures at ~48kHz                               │
│     ↓                                                               │
│  4. Encodes to: audio/webm;codecs=opus (48kHz)                     │
│     ↓                                                               │
│  5. Base64 encode chunks                                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket: voice_chunk
                              │ { type: "voice_chunk", audio: "base64..." }
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND (Python/FastAPI)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  6. Receives voice_start message                                   │
│     ↓                                                               │
│  7. Opens WebSocket to Deepgram with params:                       │
│     wss://api.deepgram.com/v1/listen?                              │
│       model=nova-2                                                  │
│       encoding=webm-opus                                            │
│       sample_rate=48000  ✅ MATCHES                                │
│     ↓                                                               │
│  8. ✅ CONNECTION ACCEPTED                                         │
│     ↓                                                               │
│  9. Receives voice_chunk, decodes base64                           │
│     ↓                                                               │
│  10. Forwards raw audio bytes to Deepgram                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket to Deepgram
                              │ Raw audio bytes (48kHz webm-opus)
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    DEEPGRAM API (External)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  11. Receives audio stream                                         │
│      ↓                                                              │
│  12. Expects: 48kHz webm-opus                                      │
│      Receives: 48kHz webm-opus                                     │
│      ↓                                                              │
│  13. ✅ MATCH - Begin transcription                                │
│      ↓                                                              │
│  14. Processes audio with Nova-2 model                             │
│      ↓                                                              │
│  15. Returns interim results (type: Results, is_final: false)     │
│      ↓                                                              │
│  16. Returns final transcript (type: Results, is_final: true)     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket: transcript data
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND (Python/FastAPI)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  17. Receives Deepgram response                                    │
│      ↓                                                              │
│  18. Extracts transcript, confidence, is_final                     │
│      ↓                                                              │
│  19. Sends to frontend via WebSocket                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket: voice_transcript
                              │ { type: "voice_transcript", transcript: "...",
                              │   is_final: true, confidence: 0.95 }
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         BROWSER (Frontend)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  20. Receives voice_transcript message                             │
│      ↓                                                              │
│  21. Updates UI with text                                          │
│      - Interim: shows in transcript field (gray)                   │
│      - Final: appends to finalTranscript (black)                   │
│      ↓                                                              │
│  22. ✅ User sees transcription in real-time                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 The Fix Visualized

### BEFORE (Broken)
```
Frontend:  16kHz ──┐
                   ├──❌ MISMATCH ──> HTTP 400
Backend:   48kHz ──┘
```

### AFTER (Fixed)
```
Frontend:  48kHz ──┐
                   ├──✅ MATCH ──> Connection Success
Backend:   48kHz ──┘
```

---

## 📊 Message Flow (Successful Session)

```
Time  Frontend                Backend                 Deepgram
─────────────────────────────────────────────────────────────────
T+0   User clicks mic
T+1   → voice_start
T+2                           Receives voice_start
T+3                           → WebSocket connect     Accepts
T+4                           ✅ Connected            ← Metadata
T+5   MediaRecorder.start()
T+6   → voice_chunk (100ms)
T+7   → voice_chunk (100ms)
T+8   → voice_chunk (100ms)   Forward chunks →
T+9                                                   ← "Hell..."
T+10  ← voice_transcript       ← Interim result
T+11  → voice_chunk
T+12  → voice_chunk                                   ← "Hello"
T+13  ← voice_transcript       ← Final result
T+14  User clicks stop
T+15  → voice_stop
T+16                           Close Deepgram WS      Closes
T+17  ← voice_stopped          ← Confirmation
```

---

## 🎯 Critical Parameters

| Parameter | Frontend | Backend | Deepgram | Status |
|-----------|----------|---------|----------|--------|
| **Sample Rate** | ~~16000~~ → **48000** | 48000 | 48000 | ✅ After fix |
| **Encoding** | webm-opus | webm-opus | webm-opus | ✅ Matches |
| **Codec** | opus | opus | opus | ✅ Matches |
| **Model** | N/A | nova-2 | nova-2 | ✅ Valid |
| **Language** | N/A | en-US | en-US | ✅ Valid |
| **Auth** | N/A | Token {key} | Valid key | ✅ TTS proves it |

---

## 🚨 Error Propagation (Current Broken Flow)

```
Deepgram: HTTP 400
    ↓
Backend: Exception in connect()
    ↓
Backend: logger.error("[Voice] Deepgram connection failed: {e}")
    ↓
Backend: await self.on_error("Failed to connect: {str(e)}")
    ↓
Backend: websocket.send_json({ type: "voice_error", error: "..." })
    ↓
Frontend: voice_error message received
    ↓
Frontend: Update state { state: 'error', error: data.error }
    ↓
Frontend: mediaRecorder.stop()
    ↓
User sees: "Failed to connect" error message
```

---

## 📈 Expected Performance (After Fix)

| Metric | Value | Notes |
|--------|-------|-------|
| **Connection Time** | 200-500ms | WebSocket handshake |
| **First Transcript** | 500-1000ms | After speaking starts |
| **Interim Results** | Every ~500ms | While speaking |
| **Final Result Delay** | 200-300ms | After silence detected |
| **Audio Chunk Size** | 100ms | Configurable (line 128 voice.ts) |
| **Network Bandwidth** | ~8 KB/s | 48kHz opus compressed |

---

## 🔄 Session Lifecycle

```
┌─────────────┐
│    IDLE     │
└─────────────┘
       │
       │ User clicks mic
       ↓
┌─────────────┐
│ REQUESTING  │ ← Permission prompt
└─────────────┘
       │
       │ Permission granted
       ↓
┌─────────────┐
│ RECORDING   │ ← Active transcription
└─────────────┘
       │
       │ User clicks stop / voice_stop
       ↓
┌─────────────┐
│ PROCESSING  │ ← Finalizing last chunks
└─────────────┘
       │
       │ After 1s timeout
       ↓
┌─────────────┐
│    IDLE     │
└─────────────┘
```

---

## 🛠️ Debug Points (If Fix Doesn't Work)

### Frontend (voice.ts)
- Line 100: Check mimeType is supported by browser
- Line 128: Verify chunks are being generated (ondataavailable firing)
- Line 107: Confirm base64 encoding successful

### Backend (voice_transcription.py)
- Line 95: Log the full URL being connected to
- Line 161: Verify audio_bytes length > 0 before sending
- Line 122: Check data structure from Deepgram responses

### Network
- Browser DevTools → Network → WS tab → Check handshake
- Check for HTTP 101 Switching Protocols (success)
- Check for HTTP 400 (parameter rejection)

---

**Visual Aid Complete**
**Status:** Ready for implementation
**One line change fixes entire flow** ✨
