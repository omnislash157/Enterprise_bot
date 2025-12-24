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
import httpx

logger = logging.getLogger(__name__)

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"
DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak"

# Aura voices - pick your vibe
AURA_VOICES = {
    "default": "aura-2-delia-en",        # Your pick - American female
    "professional": "aura-2-delia-en",   # Alias          
}


@dataclass
class DeepgramConfig:
    """Deepgram streaming configuration."""
    model: str = "nova-2"
    language: str = "en-US"
    smart_format: bool = True
    interim_results: bool = True
    punctuate: bool = True
    encoding: str = "webm-opus"
    sample_rate: int = 48000


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
        """Build Deepgram WebSocket URL - minimal working config.

        Let Deepgram auto-detect encoding/sample_rate from audio stream.
        Adding explicit encoding params causes HTTP 400 errors.
        """
        return f"{DEEPGRAM_WS_URL}?model=nova-2"

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
                additional_headers=headers,  # websockets 10+ uses additional_headers
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


# =============================================================================
# TEXT-TO-SPEECH (Deepgram Aura)
# =============================================================================

async def text_to_speech(
    text: str,
    voice: str = "professional"
) -> Optional[bytes]:
    """
    Convert text to speech via Deepgram Aura.
    Returns raw audio bytes (mp3) or None on failure.
    """
    if not DEEPGRAM_API_KEY:
        logger.error("[TTS] DEEPGRAM_API_KEY not configured")
        return None

    if not text.strip():
        return None

    model = AURA_VOICES.get(voice, AURA_VOICES["professional"])

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                DEEPGRAM_TTS_URL,
                params={"model": model},
                headers={
                    "Authorization": f"Token {DEEPGRAM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"text": text}
            )

            if response.status_code == 200:
                logger.info(f"[TTS] Generated {len(response.content)} bytes for {len(text)} chars")
                return response.content
            else:
                logger.error(f"[TTS] Deepgram error {response.status_code}: {response.text}")
                return None

    except Exception as e:
        logger.error(f"[TTS] Request failed: {e}")
        return None
