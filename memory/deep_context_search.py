"""
deep_context_search.py - Deep contextual archaeology for conversation exports.

BLOODHOUND: Tracks a term across your entire conversation history,
expanding context by tokens (not chars) and daisy-chaining nearby hits
into coherent narrative chunks.

This replaces grep/glob with something that actually understands context topology.

Usage:
    from deep_context_search import Bloodhound
    
    hound = Bloodhound("/path/to/conversations/")
    results = hound.hunt("datadog", token_radius=200, merge_gap=100)
    print(results.to_markdown())

Output format:
    ---
    # BLOODHOUND Deep Context Search
    Search: datadog (variations: Datadog, DATADOG, data-dog, data dog)
    
    ## conversation-uuid-abc | 2023-03-15
    > [expanded context chunk with all matches]
    
    ## conversation-uuid-def | 2023-06-22  
    > [daisy-chained mega-chunk when matches are close]
    ---
"""

import json
import re
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Iterator
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tokenizer - Simple but effective for context expansion
# ---------------------------------------------------------------------------

def tokenize(text: str) -> List[str]:
    """Split text into tokens (words + punctuation preserved for reconstruction)."""
    # Keep whitespace as separate tokens for reconstruction
    return re.findall(r'\S+|\s+', text)


def detokenize(tokens: List[str]) -> str:
    """Reconstruct text from tokens."""
    return ''.join(tokens)


def token_count(text: str) -> int:
    """Count non-whitespace tokens in text."""
    return len([t for t in tokenize(text) if t.strip()])


# ---------------------------------------------------------------------------
# Fuzzy Pattern Builder
# ---------------------------------------------------------------------------

def build_fuzzy_pattern(term: str, case_insensitive: bool = True) -> re.Pattern:
    """
    Build regex pattern that matches term variations:
    - Case variations: datadog, Datadog, DATADOG, DataDog
    - Separator variations: datadog, data-dog, data_dog, data dog, data.dog
    
    Args:
        term: Search term like "datadog"
        case_insensitive: Whether to match case-insensitively
        
    Returns:
        Compiled regex pattern
    """
    # Strategy: try to intelligently split compound words
    # "datadog" -> we need to detect it might be "data" + "dog"
    # "DataDog" -> ["Data", "Dog"]  
    # "data-dog" -> ["data", "dog"]
    
    # First, normalize by removing existing separators
    normalized = re.sub(r'[-_.\s]+', '', term)
    
    # Handle camelCase: insert marker before caps that follow lowercase
    spaced = re.sub(r'([a-z])([A-Z])', r'\1|\2', normalized)
    
    # Also try to detect common compound words
    # For words like "datadog", we need heuristics or a dictionary
    # Simple approach: try known compounds
    compound_splits = {
        'datadog': ['data', 'dog'],
        'devops': ['dev', 'ops'],
        'kubernetes': ['kubernetes'],  # Don't split
        'frontend': ['front', 'end'],
        'backend': ['back', 'end'],
        'github': ['git', 'hub'],
        'gitlab': ['git', 'lab'],
        'postgresql': ['postgre', 'sql'],
        'mysql': ['my', 'sql'],
        'openai': ['open', 'ai'],
        'chatgpt': ['chat', 'gpt'],
        'cogtwin': ['cog', 'twin'],
    }
    
    lower_term = normalized.lower()
    if lower_term in compound_splits:
        parts = compound_splits[lower_term]
    elif '|' in spaced:
        # CamelCase detected
        parts = spaced.split('|')
        parts = [p for p in parts if p]
    else:
        # Can't split - just use as-is but allow optional separators anywhere
        # Build pattern that optionally matches separators between any chars
        # This is aggressive but catches "data dog" for "datadog"
        chars = list(normalized)
        if len(chars) <= 1:
            pattern = re.escape(normalized)
        else:
            # Allow optional separator between each character
            # But this is too aggressive, let's be smarter
            # Instead: match the word with optional separators at "likely" breaks
            # For now, just escape it as-is (case insensitive will help)
            pattern = re.escape(normalized)
        
        flags = re.IGNORECASE if case_insensitive else 0
        return re.compile(pattern, flags)
    
    if not parts:
        pattern = re.escape(term)
    else:
        # Build pattern that matches parts with optional separators
        escaped_parts = [re.escape(p) for p in parts]
        # Allow optional separator between parts: space, hyphen, underscore, dot, or nothing
        separator = r'[-_.\s]?'
        pattern = separator.join(escaped_parts)
    
    flags = re.IGNORECASE if case_insensitive else 0
    return re.compile(pattern, flags)


def get_term_variations(term: str) -> List[str]:
    """Generate human-readable list of variations being searched."""
    # Normalize
    normalized = re.sub(r'[-_.\s]+', '', term).lower()
    
    # Known compound splits
    compound_splits = {
        'datadog': ['data', 'dog'],
        'devops': ['dev', 'ops'],
        'frontend': ['front', 'end'],
        'backend': ['back', 'end'],
        'github': ['git', 'hub'],
        'gitlab': ['git', 'lab'],
        'postgresql': ['postgre', 'sql'],
        'mysql': ['my', 'sql'],
        'openai': ['open', 'ai'],
        'chatgpt': ['chat', 'gpt'],
        'cogtwin': ['cog', 'twin'],
    }
    
    if normalized in compound_splits:
        parts = compound_splits[normalized]
        joined = ''.join(parts)
        spaced = ' '.join(parts)
        hyphenated = '-'.join(parts)
        
        return [
            joined,                                    # datadog
            joined.capitalize(),                       # Datadog
            ''.join(p.capitalize() for p in parts),   # DataDog
            joined.upper(),                           # DATADOG
            spaced,                                   # data dog
            hyphenated,                               # data-dog
        ]
    
    # Single word - just case variations
    return [
        normalized,
        normalized.capitalize(),
        normalized.upper(),
    ]


# ---------------------------------------------------------------------------
# Match Finding with Token Positions
# ---------------------------------------------------------------------------

@dataclass
class MatchSpan:
    """A single match with its token position."""
    start_token: int
    end_token: int
    matched_text: str
    char_start: int
    char_end: int


def find_matches_with_positions(text: str, pattern: re.Pattern) -> List[MatchSpan]:
    """
    Find all matches in text and return their token positions.
    
    Returns list of MatchSpan with token indices.
    """
    tokens = tokenize(text)
    matches = []
    
    # Build char->token mapping
    char_to_token = []
    current_char = 0
    for i, token in enumerate(tokens):
        for _ in token:
            char_to_token.append(i)
            current_char += 1
    
    # Find all matches
    for match in pattern.finditer(text):
        char_start = match.start()
        char_end = match.end()
        
        # Convert to token positions
        if char_start < len(char_to_token):
            start_token = char_to_token[char_start]
        else:
            start_token = len(tokens) - 1
            
        if char_end - 1 < len(char_to_token):
            end_token = char_to_token[char_end - 1]
        else:
            end_token = len(tokens) - 1
            
        matches.append(MatchSpan(
            start_token=start_token,
            end_token=end_token,
            matched_text=match.group(),
            char_start=char_start,
            char_end=char_end,
        ))
    
    return matches


# ---------------------------------------------------------------------------
# Context Expansion and Daisy Chaining
# ---------------------------------------------------------------------------

@dataclass
class ExpandedChunk:
    """A chunk of text with expanded context around matches."""
    start_token: int
    end_token: int
    text: str
    match_count: int
    is_merged: bool = False
    

def expand_and_merge_matches(
    text: str,
    matches: List[MatchSpan],
    token_radius: int = 200,
    merge_gap: int = 100,
) -> List[ExpandedChunk]:
    """
    Expand context around matches and merge nearby chunks.
    
    Args:
        text: Full text
        matches: List of matches with token positions
        token_radius: Tokens to expand before/after each match
        merge_gap: If gap between chunks is <= this, merge them
        
    Returns:
        List of expanded (and possibly merged) chunks
    """
    if not matches:
        return []
    
    tokens = tokenize(text)
    total_tokens = len(tokens)
    
    # Create initial expanded spans
    expanded_spans = []
    for match in matches:
        start = max(0, match.start_token - token_radius)
        end = min(total_tokens, match.end_token + token_radius + 1)
        expanded_spans.append((start, end, 1))  # (start, end, match_count)
    
    # Sort by start position
    expanded_spans.sort(key=lambda x: x[0])
    
    # Merge overlapping or close spans (daisy chaining)
    merged = []
    current_start, current_end, current_count = expanded_spans[0]
    
    for start, end, count in expanded_spans[1:]:
        # Check if this span should merge with current
        # Merge if: overlapping OR gap <= merge_gap tokens
        gap = start - current_end
        
        if gap <= merge_gap:
            # Merge: extend current span
            current_end = max(current_end, end)
            current_count += count
        else:
            # Gap too large: save current and start new
            merged.append((current_start, current_end, current_count))
            current_start, current_end, current_count = start, end, count
    
    # Don't forget the last span
    merged.append((current_start, current_end, current_count))
    
    # Build chunks
    chunks = []
    for start, end, count in merged:
        chunk_tokens = tokens[start:end]
        chunk_text = detokenize(chunk_tokens)
        
        chunks.append(ExpandedChunk(
            start_token=start,
            end_token=end,
            text=chunk_text.strip(),
            match_count=count,
            is_merged=(count > 1),
        ))
    
    return chunks


# ---------------------------------------------------------------------------
# Conversation Parsing (Anthropic JSON Export Format)
# ---------------------------------------------------------------------------

@dataclass
class ConversationMeta:
    """Metadata for a conversation."""
    uuid: str
    name: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    
@dataclass 
class ConversationContent:
    """Full content of a conversation."""
    meta: ConversationMeta
    full_text: str  # Combined human + assistant messages
    message_count: int


def parse_anthropic_conversation(data: Dict) -> Optional[ConversationContent]:
    """
    Parse Anthropic conversation export format.
    
    Expected structure:
    {
        "uuid": "...",
        "name": "...",
        "created_at": "2023-03-15T...",
        "updated_at": "2023-03-15T...",
        "chat_messages": [
            {"sender": "human", "text": "..."},
            {"sender": "assistant", "text": "..."},
            ...
        ]
    }
    """
    try:
        uuid = data.get('uuid', data.get('id', 'unknown'))
        name = data.get('name', 'Untitled')
        
        # Parse dates
        created_at = None
        updated_at = None
        
        if 'created_at' in data:
            try:
                created_at = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
                
        if 'updated_at' in data:
            try:
                updated_at = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        
        # Extract messages
        messages = data.get('chat_messages', [])
        if not messages:
            # Try alternate structure
            messages = data.get('messages', [])
        
        # Combine all message text
        text_parts = []
        for msg in messages:
            sender = msg.get('sender', msg.get('role', 'unknown'))
            
            # Handle different text field names
            text = msg.get('text', '')
            if not text:
                # Claude exports sometimes have content as list
                content = msg.get('content', [])
                if isinstance(content, list):
                    text = ' '.join(
                        c.get('text', '') for c in content 
                        if isinstance(c, dict) and c.get('type') == 'text'
                    )
                elif isinstance(content, str):
                    text = content
            
            if text:
                prefix = "HUMAN:" if sender in ('human', 'user') else "ASSISTANT:"
                text_parts.append(f"{prefix} {text}")
        
        full_text = "\n\n".join(text_parts)
        
        return ConversationContent(
            meta=ConversationMeta(
                uuid=uuid,
                name=name,
                created_at=created_at,
                updated_at=updated_at,
            ),
            full_text=full_text,
            message_count=len(messages),
        )
        
    except Exception as e:
        logger.warning(f"Failed to parse conversation: {e}")
        return None


def load_conversations(path: str) -> Iterator[ConversationContent]:
    """
    Load conversations from path (file or directory).
    
    Supports:
    - Single JSON file with array of conversations
    - Single JSON file with one conversation
    - Directory of JSON files
    """
    path = Path(path)
    
    if path.is_file():
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if isinstance(data, list):
            # Array of conversations
            for conv_data in data:
                conv = parse_anthropic_conversation(conv_data)
                if conv:
                    yield conv
        else:
            # Single conversation
            conv = parse_anthropic_conversation(data)
            if conv:
                yield conv
                
    elif path.is_dir():
        # Directory of JSON files
        for json_file in path.glob('**/*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                if isinstance(data, list):
                    for conv_data in data:
                        conv = parse_anthropic_conversation(conv_data)
                        if conv:
                            yield conv
                else:
                    conv = parse_anthropic_conversation(data)
                    if conv:
                        yield conv
                        
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to load {json_file}: {e}")


# ---------------------------------------------------------------------------
# Search Result Types
# ---------------------------------------------------------------------------

@dataclass
class ConversationHit:
    """A conversation with matching content."""
    meta: ConversationMeta
    chunks: List[ExpandedChunk]
    total_matches: int
    total_tokens_extracted: int


@dataclass
class BloodhoundResult:
    """Complete search result."""
    term: str
    variations: List[str]
    conversations_searched: int
    conversations_matched: int
    total_matches: int
    hits: List[ConversationHit]
    search_time_ms: float
    
    def to_markdown(self) -> str:
        """Format results as structured markdown for context injection."""
        lines = [
            "",
            "---",
            "# BLOODHOUND Deep Context Search",
            f"**Search term:** `{self.term}`",
            f"**Variations matched:** {', '.join(self.variations[:6])}",
            f"**Stats:** {self.total_matches} matches across {self.conversations_matched}/{self.conversations_searched} conversations",
            f"**Search time:** {self.search_time_ms:.1f}ms",
            "",
        ]
        
        if not self.hits:
            lines.append("*No matches found.*")
            lines.append("---")
            return "\n".join(lines)
        
        # Sort hits chronologically (oldest first)
        sorted_hits = sorted(
            self.hits,
            key=lambda h: h.meta.created_at or datetime.min
        )
        
        for hit in sorted_hits:
            # Format date
            if hit.meta.created_at:
                date_str = hit.meta.created_at.strftime("%Y-%m-%d")
            elif hit.meta.updated_at:
                date_str = hit.meta.updated_at.strftime("%Y-%m-%d")
            else:
                date_str = "unknown date"
            
            # Conversation header
            lines.append(f"## {hit.meta.uuid[:12]}... | {date_str}")
            if hit.meta.name and hit.meta.name != "Untitled":
                lines.append(f"*{hit.meta.name[:80]}*")
            lines.append("")
            
            for i, chunk in enumerate(hit.chunks):
                # Chunk metadata
                token_count = chunk.end_token - chunk.start_token
                if chunk.is_merged:
                    lines.append(f"**[Daisy-chained chunk: {chunk.match_count} matches, ~{token_count} tokens]**")
                else:
                    lines.append(f"**[Context chunk: ~{token_count} tokens]**")
                
                # The actual content (block quote for visual separation)
                # Truncate extremely long chunks for context window sanity
                content = chunk.text
                if len(content) > 4000:
                    content = content[:2000] + "\n\n[... truncated ...]\n\n" + content[-1500:]
                
                lines.append("")
                lines.append(f"> {content}")
                lines.append("")
        
        lines.append("---")
        lines.append("")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "term": self.term,
            "variations": self.variations,
            "conversations_searched": self.conversations_searched,
            "conversations_matched": self.conversations_matched,
            "total_matches": self.total_matches,
            "search_time_ms": self.search_time_ms,
            "hits": [
                {
                    "uuid": hit.meta.uuid,
                    "name": hit.meta.name,
                    "created_at": hit.meta.created_at.isoformat() if hit.meta.created_at else None,
                    "total_matches": hit.total_matches,
                    "chunks": [
                        {
                            "text": chunk.text,
                            "match_count": chunk.match_count,
                            "is_merged": chunk.is_merged,
                            "token_count": chunk.end_token - chunk.start_token,
                        }
                        for chunk in hit.chunks
                    ]
                }
                for hit in self.hits
            ]
        }


# ---------------------------------------------------------------------------
# Main Bloodhound Class
# ---------------------------------------------------------------------------

class Bloodhound:
    """
    Deep context search across conversation exports.
    
    Tracks a term through your entire chat history, expanding context
    by tokens and daisy-chaining nearby matches into coherent narratives.
    
    Example:
        hound = Bloodhound("/path/to/exports/")
        result = hound.hunt("datadog", token_radius=200)
        print(result.to_markdown())
    """
    
    def __init__(self, conversations_path: str):
        """
        Initialize with path to conversations.
        
        Args:
            conversations_path: Path to JSON file or directory of JSON files
        """
        self.path = conversations_path
        self._conversations: Optional[List[ConversationContent]] = None
    
    @property
    def conversations(self) -> List[ConversationContent]:
        """Lazy-load conversations."""
        if self._conversations is None:
            self._conversations = list(load_conversations(self.path))
            logger.info(f"Loaded {len(self._conversations)} conversations from {self.path}")
        return self._conversations
    
    def hunt(
        self,
        term: str,
        token_radius: int = 200,
        merge_gap: int = 100,
        max_conversations: Optional[int] = None,
        max_chunks_per_conversation: int = 10,
    ) -> BloodhoundResult:
        """
        Search for term across all conversations with context expansion.
        
        Args:
            term: Search term (will be fuzzily matched)
            token_radius: Tokens to expand before/after each match
            merge_gap: Merge chunks if gap is <= this many tokens
            max_conversations: Limit results (None = all)
            max_chunks_per_conversation: Max chunks per conversation
            
        Returns:
            BloodhoundResult with all matches and metadata
        """
        import time
        start = time.perf_counter()
        
        pattern = build_fuzzy_pattern(term)
        variations = get_term_variations(term)
        
        hits = []
        total_matches = 0
        
        for conv in self.conversations:
            # Find all matches in this conversation
            matches = find_matches_with_positions(conv.full_text, pattern)
            
            if not matches:
                continue
            
            # Expand and merge
            chunks = expand_and_merge_matches(
                conv.full_text,
                matches,
                token_radius=token_radius,
                merge_gap=merge_gap,
            )
            
            # Limit chunks if needed
            if len(chunks) > max_chunks_per_conversation:
                chunks = chunks[:max_chunks_per_conversation]
            
            match_count = len(matches)
            total_matches += match_count
            
            hits.append(ConversationHit(
                meta=conv.meta,
                chunks=chunks,
                total_matches=match_count,
                total_tokens_extracted=sum(c.end_token - c.start_token for c in chunks),
            ))
        
        # Sort by date (for consistent ordering)
        hits.sort(key=lambda h: h.meta.created_at or datetime.min)
        
        # Limit if requested
        if max_conversations and len(hits) > max_conversations:
            hits = hits[:max_conversations]
        
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        return BloodhoundResult(
            term=term,
            variations=variations,
            conversations_searched=len(self.conversations),
            conversations_matched=len(hits),
            total_matches=total_matches,
            hits=hits,
            search_time_ms=elapsed_ms,
        )
    
    def quick_stats(self, term: str) -> Dict:
        """Quick frequency stats without full context extraction."""
        pattern = build_fuzzy_pattern(term)
        
        matches_by_month = defaultdict(int)
        total = 0
        conv_count = 0
        
        for conv in self.conversations:
            matches = pattern.findall(conv.full_text)
            if matches:
                conv_count += 1
                total += len(matches)
                
                if conv.meta.created_at:
                    month = conv.meta.created_at.strftime("%Y-%m")
                    matches_by_month[month] += len(matches)
        
        return {
            "term": term,
            "total_matches": total,
            "conversations_with_matches": conv_count,
            "by_month": dict(sorted(matches_by_month.items())),
        }


# ---------------------------------------------------------------------------
# Tool Interface (for venom_voice integration)
# ---------------------------------------------------------------------------

class BloodhoundTool:
    """
    Tool interface for integration with venom_voice parallel tool execution.
    
    This provides a clean interface that matches the existing tool pattern.
    """
    
    def __init__(self, conversations_path: str):
        self.hound = Bloodhound(conversations_path)
    
    def execute(
        self,
        term: str,
        token_radius: int = 200,
        merge_gap: int = 100,
    ) -> str:
        """
        Execute search and return markdown for context injection.
        
        Args:
            term: Search term
            token_radius: Context expansion radius
            merge_gap: Gap threshold for daisy chaining
            
        Returns:
            Formatted markdown string
        """
        result = self.hound.hunt(
            term=term,
            token_radius=token_radius,
            merge_gap=merge_gap,
        )
        return result.to_markdown()
    
    def execute_with_result(
        self,
        term: str,
        token_radius: int = 200,
        merge_gap: int = 100,
    ) -> BloodhoundResult:
        """Execute and return full result object."""
        return self.hound.hunt(
            term=term,
            token_radius=token_radius,
            merge_gap=merge_gap,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="BLOODHOUND: Deep context search for conversation exports"
    )
    parser.add_argument("path", help="Path to conversation JSON file or directory")
    parser.add_argument("term", help="Search term")
    parser.add_argument("--radius", type=int, default=200, help="Token expansion radius (default: 200)")
    parser.add_argument("--gap", type=int, default=100, help="Merge gap threshold (default: 100)")
    parser.add_argument("--max-convs", type=int, help="Maximum conversations to return")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of markdown")
    parser.add_argument("--stats", action="store_true", help="Quick stats only (no context)")
    
    args = parser.parse_args()
    
    hound = Bloodhound(args.path)
    
    if args.stats:
        stats = hound.quick_stats(args.term)
        print(json.dumps(stats, indent=2))
    else:
        result = hound.hunt(
            term=args.term,
            token_radius=args.radius,
            merge_gap=args.gap,
            max_conversations=args.max_convs,
        )
        
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.to_markdown())


if __name__ == "__main__":
    main()
