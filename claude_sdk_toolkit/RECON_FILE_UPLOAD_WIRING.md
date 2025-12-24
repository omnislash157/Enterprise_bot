# Voice Mode Debug Handoff

## Session Summary (2024-12-24)
Added voice mode with STT (Deepgram) and TTS (Deepgram Aura). Both have issues in production.

## What Was Built

### STT (Speech-to-Text) - Voice Input
- **File**: `voice_transcription.py` - DeepgramBridge class
- **Trigger**: Mic button → WebSocket `voice_start` message
- **Flow**: Browser audio → base64 chunks → Deepgram WebSocket → transcripts back

### TTS (Text-to-Speech) - Voice Output  
- **File**: `voice_transcription.py` - `text_to_speech()` function added
- **Endpoint**: `POST /api/tts` in `core/main.py` (line 767)
- **Frontend**: `speakText()` in `frontend/src/lib/stores/voice.ts`
- **Trigger**: Speaker button toggle → auto-speaks when response finishes streaming
- **Flow**: Response text → `/api/tts` → Deepgram Aura → audio bytes → browser playback
- **Fallback**: Browser native `speechSynthesis` (robot voice) if TTS fails

## Current Issues

### Issue 1: TTS 404 (Critical)
**Symptom**: `POST /api/tts` returns 404, falls back to robot voice

**Diagnosis**:
- Route EXISTS in code: `core/main.py` line 767
- Route REGISTERS locally: `python -c "from core.main import app; print([r.path for r in app.routes if 'tts' in r.path])"` returns `['/api/tts']`
- curl to production returns **SvelteKit HTML 404**, not FastAPI 404
- This means requests aren't reaching FastAPI at all

**Root Cause Theory**: Frontend proxy isn't forwarding `/api/tts` to backend

**Investigation Needed**:
1. Check Railway service configuration
2. Check frontend proxy/routing config (vite.config.ts? svelte.config.js?)
3. Check if other `/api/*` routes work (they do - `/api/departments` returns 200)
4. Compare working `/api/departments` vs non-working `/api/tts`

### Issue 2: STT HTTP 400
**Symptom**: `[Voice] Deepgram connection failed: server rejected WebSocket connection: HTTP 400`

**Likely Cause**: Invalid model name
```python
# voice_transcription.py - DeepgramConfig
model: str = "nova-3"  # May not exist
```

**Fix**: Change to `nova-2` (current production model)

### Issue 3: Wrong TTS Voice (Minor - fix after 404 resolved)
**Current**: AURA_VOICES doesn't include user's choice
**Wanted**: `aura-2-delia-en` (American female)

**Fix** in `voice_transcription.py`:
```python
AURA_VOICES = {
    "default": "aura-2-delia-en",
    "professional": "aura-2-delia-en",
    # ... rest
}
```

## Files to Investigate

### Backend
- `voice_transcription.py` - All voice logic (STT + TTS)
- `core/main.py` - Line 40 (imports), Line 767 (`/api/tts` endpoint)

### Frontend  
- `frontend/src/lib/stores/voice.ts` - `speakText()` function
- `frontend/src/lib/components/ChatOverlay.svelte` - Voice UI buttons
- `frontend/vite.config.ts` or `svelte.config.js` - Proxy configuration?

### Deployment
- `Procfile` - Start commands
- Railway dashboard - Service configuration, environment variables
- Check if Railway has separate frontend/backend services or combined

## Environment Variables Needed
```
DEEPGRAM_API_KEY=9953e5xxx  (confirmed set in Railway)
```

## Quick Verification Commands

```bash
# Check route registers
python -c "from core.main import app; print([r.path for r in app.routes if 'tts' in r.path])"

# Check imports work
python -c "from voice_transcription import text_to_speech; print('OK')"

# Test endpoint locally
curl -X POST http://localhost:8000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "hello world"}' \
  --output test.mp3 && file test.mp3

# Compare with working endpoint
curl https://worthy-imagination-production.up.railway.app/api/departments
```

## Hypothesis

The `/api/tts` endpoint was added AFTER the frontend proxy configuration was set up. Other `/api/*` routes work because they were defined when proxy rules were created.

**Check for**:
- Explicit route whitelist in frontend config
- Catch-all `/api/*` proxy that should work but isn't
- Railway routing rules that might need updating

## Success Criteria
1. `POST /api/tts` returns `audio/mpeg` bytes (not 404)
2. `speakText()` plays Delia voice (not robot)
3. STT connects without HTTP 400
4. Full loop: Speak → Transcribe → LLM → Speak response