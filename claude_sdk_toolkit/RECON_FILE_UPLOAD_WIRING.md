# STT HTTP 400 Debug - SDK Recon Mission

## Mission Objective
Diagnose and fix Deepgram WebSocket connection rejection (HTTP 400) for voice input (STT)

## Error Signature
```
ERROR:voice_transcription:[Voice] Deepgram connection failed: server rejected WebSocket connection: HTTP 400
WARNING:voice_transcription:[Voice] No active session for {session_id}
```

## Context
- TTS (voice output) now works - Delia voice playing correctly
- STT (voice input) fails on WebSocket handshake
- HTTP 400 = bad request parameters (not auth - that would be 401/403)

---

## Current Implementation

### File: `voice_transcription.py`

**Constants:**
```python
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"
```

**Config (lines 36-44):**
```python
@dataclass
class DeepgramConfig:
    model: str = "nova-2"
    language: str = "en-US"
    smart_format: bool = True
    interim_results: bool = True
    punctuate: bool = True
    encoding: str = "webm-opus"
    sample_rate: int = 16000  # MAY NEED TO BE 48000
```

**URL Builder (lines 69-81):**
```python
def _build_url(self) -> str:
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
```

**Connection (lines 83-103):**
```python
async def connect(self) -> bool:
    if not DEEPGRAM_API_KEY:
        logger.error("[Voice] DEEPGRAM_API_KEY not configured")
        await self.on_error("Voice transcription not configured")
        return False

    try:
        url = self._build_url()
        headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}

        self._ws = await websockets.connect(
            url,
            additional_headers=headers,  # Changed from extra_headers
            ping_interval=20,
            ping_timeout=10,
        )
        # ...
```

---

## What We've Already Tried
| Fix | Status | Result |
|-----|--------|--------|
| Model `nova-3` → `nova-2` | ✅ Applied | Still 400 |
| `extra_headers` → `additional_headers` | ✅ Applied | Still 400 |
| Sample rate `16000` → `48000` | ❓ Unclear if deployed | Still 400 |

---

## Investigation Tasks

### 1. Add Debug Logging
Add these lines in `connect()` method BEFORE the websockets.connect call:

```python
async def connect(self) -> bool:
    if not DEEPGRAM_API_KEY:
        logger.error("[Voice] DEEPGRAM_API_KEY not configured")
        await self.on_error("Voice transcription not configured")
        return False

    try:
        url = self._build_url()
        headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
        
        # DEBUG: Log what we're sending
        logger.info(f"[Voice] Full URL: {url}")
        logger.info(f"[Voice] API key length: {len(DEEPGRAM_API_KEY)}")
        logger.info(f"[Voice] API key prefix: {DEEPGRAM_API_KEY[:8]}...")
```

### 2. Check Sample Rate
Verify current value and test both:
```bash
grep -n "sample_rate" voice_transcription.py
```

Browser MediaRecorder with opus typically outputs 48000Hz. Try:
- `sample_rate: int = 48000`
- Or remove sample_rate entirely (let Deepgram auto-detect)

### 3. Test Minimal Connection
Create test script to isolate the issue:

```python
# test_deepgram.py
import asyncio
import os
import websockets

async def test():
    api_key = os.getenv("DEEPGRAM_API_KEY")
    
    # Minimal params - just model
    url = "wss://api.deepgram.com/v1/listen?model=nova-2"
    headers = {"Authorization": f"Token {api_key}"}
    
    print(f"Connecting to: {url}")
    print(f"API key: {api_key[:8]}...")
    
    try:
        ws = await websockets.connect(url, additional_headers=headers)
        print("SUCCESS - Connected!")
        await ws.close()
    except Exception as e:
        print(f"FAILED: {e}")

asyncio.run(test())
```

Run with: `python test_deepgram.py`

### 4. Check Deepgram Dashboard
- Log into Deepgram console
- Check API usage/errors section
- Look for failed requests with details

### 5. Verify Frontend Audio Format
Check what MediaRecorder is actually sending:

**File:** `frontend/src/lib/stores/voice.ts` (or wherever voice input is handled)

Look for MediaRecorder config:
```typescript
const mediaRecorder = new MediaRecorder(stream, {
    mimeType: 'audio/webm;codecs=opus'  // Should match backend encoding
});
```

If frontend sends different format than backend expects → 400

---

## Deepgram Parameter Reference

### Valid Models (as of Dec 2024)
- `nova-2` ✅ (recommended)
- `nova-2-general`
- `nova-2-meeting`
- `nova-2-phonecall`
- `enhanced`
- `base`

### Valid Encodings
- `linear16` - PCM 16-bit
- `flac`
- `mulaw`
- `amr-nb`
- `amr-wb`
- `opus` - Raw opus
- `webm-opus` - WebM container with opus ← Browser default
- `mp3`
- `mp4`
- `webm`

### Sample Rates
- `8000` - Telephony
- `16000` - Wideband
- `44100` - CD quality
- `48000` - Standard for opus/webm ← Likely correct for browser

---

## Hypothesis Priority

| # | Hypothesis | Likelihood | Test |
|---|------------|------------|------|
| 1 | Sample rate mismatch (16000 vs 48000) | HIGH | Change to 48000 or remove param |
| 2 | Encoding mismatch | MEDIUM | Check frontend MediaRecorder mimeType |
| 3 | URL encoding issue | LOW | Log full URL, check for special chars |
| 4 | websockets version still wrong | LOW | Verify `additional_headers` is used |
| 5 | API key format issue | LOW | Check for whitespace/quotes |

---

## Quick Fixes to Try (In Order)

### Fix 1: Remove sample_rate entirely
```python
def _build_url(self) -> str:
    params = [
        f"model={self.config.model}",
        f"language={self.config.language}",
        f"smart_format={str(self.config.smart_format).lower()}",
        f"interim_results={str(self.config.interim_results).lower()}",
        f"punctuate={str(self.config.punctuate).lower()}",
        f"encoding={self.config.encoding}",
        # REMOVED: f"sample_rate={self.config.sample_rate}",
    ]
    return f"{DEEPGRAM_WS_URL}?{'&'.join(params)}"
```

### Fix 2: Change encoding to match raw opus
If browser sends raw opus (not webm container):
```python
encoding: str = "opus"
```

### Fix 3: Minimal params
Strip down to absolute minimum:
```python
def _build_url(self) -> str:
    return f"{DEEPGRAM_WS_URL}?model=nova-2&encoding=webm-opus"
```

---

## Success Criteria
1. `[Voice] Deepgram connected for session {id}` in logs
2. No HTTP 400 errors
3. `voice_transcript` messages flowing back to frontend
4. User speaks → text appears

---

## Files to Modify
- `voice_transcription.py` - Backend WebSocket logic
- `frontend/src/lib/stores/voice.ts` - Check MediaRecorder config

## Reference Docs
- https://developers.deepgram.com/docs/streaming
- https://developers.deepgram.com/docs/encoding
- https://developers.deepgram.com/docs/model