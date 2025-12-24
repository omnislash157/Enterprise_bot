"""
model_adapter.py - Unified LLM interface for multiple providers.

Provides Anthropic-style interface regardless of backend.
Currently supports: Anthropic (Claude), xAI (Grok)

IMPORTANT: Model names are read from environment variables, not hardcoded.
Set these in Railway / .env:
  - XAI_MODEL (e.g., "grok-4-1-fast-reasoning")
  - XAI_API_KEY
  - ANTHROPIC_API_KEY (if using Claude)

The adapter normalizes:
- Streaming interface (.messages.stream() context manager)
- Response format (.content[0].text, .usage.input_tokens)
- System prompt handling (Grok uses messages, Claude uses system param)

Usage:
    from model_adapter import create_adapter, get_model_name

    adapter = create_adapter(provider="xai")
    # Model name comes from XAI_MODEL env var automatically
"""

import os
import json
import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Iterator, Generator
from contextlib import contextmanager

import requests

from .metrics_collector import metrics_collector

logger = logging.getLogger(__name__)


# =============================================================================
# MODEL NAME - SINGLE SOURCE OF TRUTH
# =============================================================================

def get_model_name(provider: str = "xai") -> str:
    """
    Get model name from environment variable.

    This is the ONLY place model names should be resolved.
    Set XAI_MODEL or ANTHROPIC_MODEL in Railway/env.

    Raises ValueError if not set (fail fast, no silent defaults).
    """
    if provider == "xai":
        model = os.getenv("XAI_MODEL")
        if not model:
            raise ValueError(
                "XAI_MODEL environment variable not set. "
                "Set it in Railway or .env (e.g., XAI_MODEL=grok-4-1-fast-reasoning)"
            )
        return model

    elif provider == "anthropic":
        # Anthropic has a sensible default since it changes less often
        return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    else:
        raise ValueError(f"Unknown provider: {provider}")


# =============================================================================
# LLM PRICING AND COST CALCULATION
# =============================================================================

# LLM pricing (per 1M tokens) - update as needed
LLM_PRICING = {
    'grok-4-1-fast-reasoning': {'input': 3.00, 'output': 15.00},
    'grok-4-1': {'input': 3.00, 'output': 15.00},
    'claude-3-sonnet': {'input': 3.00, 'output': 15.00},
    'claude-sonnet-4-20250514': {'input': 3.00, 'output': 15.00},
}

def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate USD cost for LLM call."""
    pricing = LLM_PRICING.get(model, {'input': 5.00, 'output': 15.00})
    cost = (tokens_in * pricing['input'] + tokens_out * pricing['output']) / 1_000_000
    return cost


# =============================================================================
# Response Dataclasses (match Anthropic SDK structure)
# =============================================================================

@dataclass
class Usage:
    """Token usage - matches anthropic.types.Usage"""
    input_tokens: int
    output_tokens: int


@dataclass
class TextBlock:
    """Content block - matches anthropic.types.TextBlock"""
    type: str = "text"
    text: str = ""


@dataclass
class Message:
    """Response message - matches anthropic.types.Message"""
    id: str
    type: str
    role: str
    content: List[TextBlock]
    model: str
    stop_reason: Optional[str]
    usage: Usage


# =============================================================================
# Streaming Support
# =============================================================================

class StreamManager:
    """
    Context manager for streaming responses.
    Matches Anthropic's client.messages.stream() interface.
    """

    def __init__(self, response_iter: Generator, model: str):
        self._response_iter = response_iter
        self._model = model
        self._collected_text = ""
        self._usage = None
        self._stream_exhausted = False
        self._start_time = time.time()
        self._first_token_time = None
        self._error = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Exhaust stream if not already done
        if not self._stream_exhausted:
            try:
                for _ in self.text_stream:
                    pass
            except Exception:
                self._error = True

        # Record metrics
        elapsed_ms = (time.time() - self._start_time) * 1000
        first_token_ms = (self._first_token_time - self._start_time) * 1000 if self._first_token_time else 0

        if self._error:
            metrics_collector.record_llm_call(latency_ms=elapsed_ms, error=True)
        elif self._usage:
            cost = calculate_cost(self._model, self._usage.input_tokens, self._usage.output_tokens)
            metrics_collector.record_llm_call(
                latency_ms=elapsed_ms,
                first_token_ms=first_token_ms,
                tokens_in=self._usage.input_tokens,
                tokens_out=self._usage.output_tokens,
                cost_usd=cost
            )
        else:
            # No usage data, record with estimated tokens
            estimated_tokens_out = len(self._collected_text) // 4
            cost = calculate_cost(self._model, 0, estimated_tokens_out)
            metrics_collector.record_llm_call(
                latency_ms=elapsed_ms,
                first_token_ms=first_token_ms,
                tokens_in=0,
                tokens_out=estimated_tokens_out,
                cost_usd=cost
            )

    @property
    def text_stream(self) -> Iterator[str]:
        """Iterate over text chunks as they arrive."""
        for chunk_data in self._response_iter:
            if chunk_data.get("choices"):
                delta = chunk_data["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    # Capture first token time
                    if self._first_token_time is None:
                        self._first_token_time = time.time()

                    self._collected_text += content
                    yield content

            # Capture usage from final chunk if present
            if chunk_data.get("usage"):
                self._usage = Usage(
                    input_tokens=chunk_data["usage"].get("prompt_tokens", 0),
                    output_tokens=chunk_data["usage"].get("completion_tokens", 0),
                )

        self._stream_exhausted = True

    def get_final_message(self) -> Message:
        """Get complete message after streaming."""
        # Ensure stream is exhausted
        if not self._stream_exhausted:
            for _ in self.text_stream:
                pass

        # Estimate tokens if not provided
        if not self._usage:
            # Rough estimate: 1 token ~ 4 chars
            self._usage = Usage(
                input_tokens=0,  # Unknown for streamed
                output_tokens=len(self._collected_text) // 4,
            )

        return Message(
            id=f"msg_{int(time.time())}",
            type="message",
            role="assistant",
            content=[TextBlock(text=self._collected_text)],
            model=self._model,
            stop_reason="end_turn",
            usage=self._usage,
        )


# =============================================================================
# Grok (xAI) Adapter
# =============================================================================

class GrokMessages:
    """
    Messages interface for Grok - matches anthropic.Anthropic().messages
    """

    API_BASE = "https://api.x.ai/v1"

    def __init__(self, api_key: str, default_model: str):
        self.api_key = api_key
        self.default_model = default_model
        self.session = self._create_session()
        logger.info(f"[GrokMessages] Initialized with model: {default_model}")

    def _create_session(self) -> requests.Session:
        """Create configured requests session."""
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "CogTwin/2.7.0",
        })
        return session

    def _convert_to_openai_format(
        self,
        system: str,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Convert Anthropic-style (system param + messages) to OpenAI-style (all in messages).
        """
        converted = []

        # System prompt becomes first message
        if system:
            converted.append({"role": "system", "content": system})

        # Add user/assistant messages
        converted.extend(messages)

        return converted

    def create(
        self,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        system: str = "",
        messages: List[Dict[str, Any]] = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> Message:
        """
        Create a message (non-streaming).
        Matches anthropic.Anthropic().messages.create()
        """
        model = model or self.default_model
        messages = messages or []

        # Convert to OpenAI format
        openai_messages = self._convert_to_openai_format(system, messages)

        payload = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        url = f"{self.API_BASE}/chat/completions"

        logger.debug(f"Grok API request: model={model}, {len(openai_messages)} messages")
        start = time.time()

        try:
            response = self.session.post(url, json=payload, timeout=(10, 120))
            response.raise_for_status()

            data = response.json()
            elapsed_ms = (time.time() - start) * 1000
            logger.info(f"Grok API response: {elapsed_ms:.0f}ms")

            # Extract content
            content = data["choices"][0]["message"]["content"]
            usage_data = data.get("usage", {})

            tokens_in = usage_data.get("prompt_tokens", 0)
            tokens_out = usage_data.get("completion_tokens", 0)

            # Record metrics
            cost = calculate_cost(model, tokens_in, tokens_out)
            metrics_collector.record_llm_call(
                latency_ms=elapsed_ms,
                first_token_ms=0,  # Non-streaming doesn't have TTFT
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost
            )

            return Message(
                id=data.get("id", f"msg_{int(time.time())}"),
                type="message",
                role="assistant",
                content=[TextBlock(text=content)],
                model=model,
                stop_reason=data["choices"][0].get("finish_reason", "end_turn"),
                usage=Usage(
                    input_tokens=tokens_in,
                    output_tokens=tokens_out,
                ),
            )

        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            metrics_collector.record_llm_call(latency_ms=elapsed_ms, error=True)
            raise

    @contextmanager
    def stream(
        self,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        system: str = "",
        messages: List[Dict[str, Any]] = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> Generator[StreamManager, None, None]:
        """
        Stream a message response.
        Matches anthropic.Anthropic().messages.stream() context manager.

        Usage:
            with adapter.messages.stream(...) as stream:
                for chunk in stream.text_stream:
                    print(chunk, end="")
            response = stream.get_final_message()
        """
        model = model or self.default_model
        messages = messages or []

        # Convert to OpenAI format
        openai_messages = self._convert_to_openai_format(system, messages)

        payload = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},  # Request usage in stream
        }

        url = f"{self.API_BASE}/chat/completions"

        logger.debug(f"Grok API stream request: model={model}, {len(openai_messages)} messages")

        response = self.session.post(
            url,
            json=payload,
            timeout=(10, 300),  # Longer timeout for streaming
            stream=True,
        )
        response.raise_for_status()

        def chunk_generator():
            """Parse SSE stream into chunk dicts."""
            for line in response.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            yield json.loads(data_str)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse SSE chunk: {data_str}")

        yield StreamManager(chunk_generator(), model)


class GrokAdapter:
    """
    Grok adapter with Anthropic-compatible interface.

    Usage:
        adapter = GrokAdapter(api_key="...", model="grok-4-1-fast-reasoning")
        response = adapter.messages.create(...)
    """

    def __init__(self, api_key: str, model: str):
        if not model:
            raise ValueError("model parameter is required - no hardcoded defaults allowed")
        self.model = model
        self.messages = GrokMessages(api_key, default_model=model)


# =============================================================================
# Anthropic Passthrough (for comparison/fallback)
# =============================================================================

class AnthropicAdapter:
    """
    Thin wrapper around native Anthropic client.
    Exists so we can use the same create_adapter() interface.
    """

    def __init__(self, api_key: str, model: str):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self.messages = self._client.messages
        self.default_model = model


# =============================================================================
# Factory Function
# =============================================================================

def create_adapter(
    provider: str = "xai",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
):
    """
    Create an LLM adapter for the specified provider.

    Model names are read from environment variables if not explicitly passed:
    - XAI_MODEL for xAI/Grok
    - ANTHROPIC_MODEL for Anthropic/Claude

    Args:
        provider: "xai" (Grok) or "anthropic" (Claude)
        api_key: API key (or reads from env)
        model: Model name (or reads from env - REQUIRED for xai)

    Returns:
        Adapter with .messages.create() and .messages.stream() interface
    """
    if provider == "xai":
        api_key = api_key or os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("XAI_API_KEY required for Grok")
        
        # Model from param, then env var, then fail
        model = model or get_model_name("xai")
        logger.info(f"[create_adapter] Creating Grok adapter with model: {model}")
        return GrokAdapter(api_key=api_key, model=model)

    elif provider == "anthropic":
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY required for Claude")
        model = model or get_model_name("anthropic")
        return AnthropicAdapter(api_key=api_key, model=model)

    else:
        raise ValueError(f"Unknown provider: {provider}")