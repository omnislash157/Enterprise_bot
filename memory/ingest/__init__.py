"""
Ingestion pipeline - chat parsing, document loading, batch processing.

Supports multiple chat export formats:
- Anthropic (Claude)
- OpenAI (ChatGPT)
- Grok
- Gemini
"""
from .pipeline import IngestPipeline
from .chat_parser import ChatParserFactory, AnthropicParser
