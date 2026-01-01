"""
contextual_embeddings.py - Metadata-Enriched Embeddings

The problem: raw content embeddings lose context.
"Fixed the bug" embeds the same whether it was:
- A critical production fix at 3am
- A minor typo fix in a test
- Part of a week-long debugging saga

Contextual embeddings prepend metadata BEFORE embedding:

Raw: "Fixed the bug in the async handler"

Contextual: "This is from a conversation on 2024-03-15 at 2:47 AM 
about debugging async errors in the memory pipeline. The user was 
frustrated after 3 hours of debugging. Cluster: async-debugging.
Content: Fixed the bug in the async handler"

Now the embedding captures WHAT + WHEN + WHY + EMOTIONAL_STATE.

This is Anthropic's "Contextual Retrieval" approach, adapted for CogTwin.

Usage:
    enricher = ContextualEmbedder(base_embedder)
    embedding = await enricher.embed_with_context(node)
    
    # Or batch re-embed entire corpus
    await enricher.reindex_with_context(nodes, data_dir)

Version: 1.0.0 (cog_twin)
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Awaitable
import json

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Context Templates
# =============================================================================

CONTEXT_TEMPLATE_FULL = """This memory is from a conversation on {date} at {time}.
Topic cluster: {cluster_label}
Conversation mode: {conversation_mode}
Technical depth: {technical_depth}/10
Emotional tone: {emotional_valence}
{urgency_note}
{code_note}
{error_note}

Content:
{content}"""

CONTEXT_TEMPLATE_MINIMAL = """[{date} {time}] [{cluster_label}] {content}"""

CONTEXT_TEMPLATE_CONVERSATIONAL = """From a {conversation_mode} conversation on {date}:
The user asked about {intent_summary}.
{emotional_context}

Exchange:
{content}"""


@dataclass
class ContextConfig:
    """Configuration for context generation."""
    include_date: bool = True
    include_time: bool = True
    include_cluster: bool = True
    include_technical_depth: bool = True
    include_emotional: bool = True
    include_urgency: bool = True
    include_code_flag: bool = True
    include_error_flag: bool = True
    include_conversation_mode: bool = True
    template: str = "full"  # "full", "minimal", "conversational"
    
    # LLM-generated context (expensive but powerful)
    use_llm_context: bool = False
    llm_context_prompt: str = ""


# =============================================================================
# Context Generator
# =============================================================================

class ContextGenerator:
    """
    Generates contextual prefixes for content before embedding.
    """
    
    def __init__(
        self,
        config: Optional[ContextConfig] = None,
        llm_generate: Optional[Callable[[str], Awaitable[str]]] = None,
    ):
        """
        Args:
            config: Context configuration
            llm_generate: Optional async LLM function for rich context
        """
        self.config = config or ContextConfig()
        self.llm_generate = llm_generate
    
    def generate_context(self, node: Any) -> str:
        """
        Generate contextual prefix for a memory node.
        
        Args:
            node: MemoryNode or similar object
        
        Returns:
            Contextual string to prepend to content
        """
        # Extract fields with safe defaults
        created_at = getattr(node, 'created_at', None) or datetime.now()
        date_str = created_at.strftime("%Y-%m-%d") if self.config.include_date else ""
        time_str = created_at.strftime("%H:%M") if self.config.include_time else ""
        
        cluster_label = getattr(node, 'cluster_label', None) or "unclustered"
        conversation_mode = getattr(node, 'conversation_mode', None)
        if conversation_mode:
            conversation_mode = conversation_mode.value if hasattr(conversation_mode, 'value') else str(conversation_mode)
        else:
            conversation_mode = "chat"
        
        technical_depth = getattr(node, 'technical_depth', 0)
        
        emotional_valence = getattr(node, 'emotional_valence', None)
        if emotional_valence:
            emotional_valence = emotional_valence.value if hasattr(emotional_valence, 'value') else str(emotional_valence)
        else:
            emotional_valence = "neutral"
        
        urgency = getattr(node, 'urgency', None)
        if urgency:
            urgency = urgency.value if hasattr(urgency, 'value') else str(urgency)
        else:
            urgency = "low"
        
        has_code = getattr(node, 'has_code', False)
        has_error = getattr(node, 'has_error', False)
        
        # Get content
        if hasattr(node, 'combined_content'):
            content = node.combined_content
        elif hasattr(node, 'human_content') and hasattr(node, 'assistant_content'):
            content = f"Human: {node.human_content}\nAssistant: {node.assistant_content}"
        else:
            content = str(node)
        
        # Build context based on template
        if self.config.template == "minimal":
            return CONTEXT_TEMPLATE_MINIMAL.format(
                date=date_str,
                time=time_str,
                cluster_label=cluster_label,
                content=content,
            )
        
        elif self.config.template == "conversational":
            # Infer intent summary from content
            intent_type = getattr(node, 'intent_type', None)
            if intent_type:
                intent_summary = intent_type.value if hasattr(intent_type, 'value') else str(intent_type)
            else:
                intent_summary = "a topic"
            
            emotional_context = ""
            if emotional_valence != "neutral":
                emotional_context = f"The tone was {emotional_valence}."
            
            return CONTEXT_TEMPLATE_CONVERSATIONAL.format(
                conversation_mode=conversation_mode,
                date=date_str,
                intent_summary=intent_summary,
                emotional_context=emotional_context,
                content=content,
            )
        
        else:  # full template
            urgency_note = f"Urgency: {urgency}" if urgency != "low" and self.config.include_urgency else ""
            code_note = "Contains code." if has_code and self.config.include_code_flag else ""
            error_note = "Discusses errors/bugs." if has_error and self.config.include_error_flag else ""
            
            return CONTEXT_TEMPLATE_FULL.format(
                date=date_str,
                time=time_str,
                cluster_label=cluster_label,
                conversation_mode=conversation_mode,
                technical_depth=technical_depth,
                emotional_valence=emotional_valence,
                urgency_note=urgency_note,
                code_note=code_note,
                error_note=error_note,
                content=content,
            )
    
    async def generate_llm_context(self, node: Any) -> str:
        """
        Generate rich context using LLM.
        
        More expensive but captures nuance that templates miss.
        """
        if not self.llm_generate:
            return self.generate_context(node)
        
        # Get basic content
        if hasattr(node, 'combined_content'):
            content = node.combined_content
        else:
            content = str(node)
        
        prompt = f"""Given this conversation exchange, write a brief contextual summary (2-3 sentences) that captures:
1. What the conversation is about
2. The apparent goal or intent
3. Any notable emotional tone or urgency

Exchange:
{content}

Contextual summary:"""
        
        try:
            context = await self.llm_generate(prompt)
            return f"{context.strip()}\n\nContent:\n{content}"
        except Exception as e:
            logger.warning(f"LLM context generation failed: {e}")
            return self.generate_context(node)


# =============================================================================
# Contextual Embedder
# =============================================================================

class ContextualEmbedder:
    """
    Embedder that prepends contextual information before embedding.
    
    Wraps your existing AsyncEmbedder and adds context generation.
    """
    
    def __init__(
        self,
        base_embedder: Any,  # AsyncEmbedder
        context_generator: Optional[ContextGenerator] = None,
        config: Optional[ContextConfig] = None,
    ):
        """
        Args:
            base_embedder: Your existing AsyncEmbedder
            context_generator: Custom context generator (creates default if None)
            config: Context configuration (used if generator not provided)
        """
        self.embedder = base_embedder
        self.context_gen = context_generator or ContextGenerator(config or ContextConfig())
    
    async def embed_single(self, node: Any) -> np.ndarray:
        """
        Embed a single node with context.
        
        Args:
            node: MemoryNode or similar
        
        Returns:
            Contextual embedding
        """
        contextual_text = self.context_gen.generate_context(node)
        return await self.embedder.embed_single(contextual_text)
    
    async def embed_batch(
        self,
        nodes: List[Any],
        batch_size: int = 32,
        show_progress: bool = True,
    ) -> np.ndarray:
        """
        Batch embed nodes with context.
        
        Args:
            nodes: List of MemoryNode objects
            batch_size: Batch size for embedding
            show_progress: Show progress bar
        
        Returns:
            Array of contextual embeddings (N x D)
        """
        # Generate all contextual texts
        contextual_texts = [
            self.context_gen.generate_context(node)
            for node in nodes
        ]
        
        # Batch embed
        return await self.embedder.embed_batch(
            contextual_texts,
            batch_size=batch_size,
            show_progress=show_progress,
        )
    
    async def embed_with_llm_context(self, node: Any) -> np.ndarray:
        """
        Embed with LLM-generated context (expensive).
        
        Use sparingly - maybe for high-value nodes only.
        """
        contextual_text = await self.context_gen.generate_llm_context(node)
        return await self.embedder.embed_single(contextual_text)


# =============================================================================
# Re-indexing Utility
# =============================================================================

async def reindex_with_context(
    nodes: List[Any],
    embedder: Any,  # AsyncEmbedder
    output_path: Path,
    config: Optional[ContextConfig] = None,
    batch_size: int = 32,
) -> np.ndarray:
    """
    Re-embed entire corpus with contextual embeddings.
    
    This is a one-time operation to upgrade your embeddings.
    
    Args:
        nodes: All MemoryNode objects
        embedder: Your AsyncEmbedder
        output_path: Where to save new embeddings
        config: Context configuration
        batch_size: Batch size for embedding
    
    Returns:
        New contextual embeddings array
    """
    output_path = Path(output_path)
    
    logger.info(f"Re-indexing {len(nodes)} nodes with contextual embeddings...")
    
    # Create contextual embedder
    ctx_embedder = ContextualEmbedder(embedder, config=config)
    
    # Embed all nodes
    embeddings = await ctx_embedder.embed_batch(
        nodes,
        batch_size=batch_size,
        show_progress=True,
    )
    
    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, embeddings)
    
    logger.info(f"Saved contextual embeddings to {output_path}")
    logger.info(f"Shape: {embeddings.shape}")
    
    return embeddings


# =============================================================================
# A/B Testing Helper
# =============================================================================

class EmbeddingComparator:
    """
    Compare retrieval quality between raw and contextual embeddings.
    
    Useful for validating that contextual embeddings improve results.
    """
    
    def __init__(
        self,
        raw_embeddings: np.ndarray,
        contextual_embeddings: np.ndarray,
        nodes: List[Any],
        embedder: Any,
    ):
        """
        Args:
            raw_embeddings: Original embeddings
            contextual_embeddings: Contextual embeddings
            nodes: The nodes being compared
            embedder: For embedding queries
        """
        self.raw = raw_embeddings
        self.contextual = contextual_embeddings
        self.nodes = nodes
        self.embedder = embedder
        
        # Normalize for cosine similarity
        self.raw_norm = self.raw / (np.linalg.norm(self.raw, axis=1, keepdims=True) + 1e-8)
        self.ctx_norm = self.contextual / (np.linalg.norm(self.contextual, axis=1, keepdims=True) + 1e-8)
    
    async def compare(
        self,
        query: str,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """
        Compare retrieval results for a query.
        
        Returns dict with results from both embedding types.
        """
        # Embed query
        query_emb = await self.embedder.embed_single(query)
        query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-8)
        
        # Search raw
        raw_sims = self.raw_norm @ query_norm
        raw_indices = np.argsort(raw_sims)[::-1][:top_k]
        raw_scores = raw_sims[raw_indices]
        
        # Search contextual
        ctx_sims = self.ctx_norm @ query_norm
        ctx_indices = np.argsort(ctx_sims)[::-1][:top_k]
        ctx_scores = ctx_sims[ctx_indices]
        
        # Calculate overlap
        raw_set = set(raw_indices.tolist())
        ctx_set = set(ctx_indices.tolist())
        overlap = len(raw_set & ctx_set)
        
        # Find nodes that changed rank significantly
        promotions = []  # Nodes that ranked higher with contextual
        demotions = []   # Nodes that ranked lower with contextual
        
        for i, idx in enumerate(ctx_indices):
            if idx in raw_indices:
                raw_rank = np.where(raw_indices == idx)[0][0]
                if raw_rank - i >= 3:  # Promoted 3+ positions
                    promotions.append({
                        "node": self.nodes[idx],
                        "raw_rank": int(raw_rank),
                        "ctx_rank": i,
                        "change": int(raw_rank - i),
                    })
                elif i - raw_rank >= 3:  # Demoted 3+ positions
                    demotions.append({
                        "node": self.nodes[idx],
                        "raw_rank": int(raw_rank),
                        "ctx_rank": i,
                        "change": int(raw_rank - i),
                    })
        
        return {
            "query": query,
            "overlap": overlap,
            "overlap_pct": overlap / top_k * 100,
            "raw_results": [
                {"idx": int(i), "score": float(s), "preview": self._preview(self.nodes[i])}
                for i, s in zip(raw_indices, raw_scores)
            ],
            "contextual_results": [
                {"idx": int(i), "score": float(s), "preview": self._preview(self.nodes[i])}
                for i, s in zip(ctx_indices, ctx_scores)
            ],
            "promotions": promotions[:5],
            "demotions": demotions[:5],
        }
    
    def _preview(self, node: Any, max_len: int = 80) -> str:
        """Get preview text from node."""
        if hasattr(node, 'human_content'):
            text = node.human_content
        elif hasattr(node, 'combined_content'):
            text = node.combined_content
        else:
            text = str(node)
        
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text


# =============================================================================
# CLI
# =============================================================================

async def main():
    """Test contextual embeddings."""
    print("Contextual Embeddings Test")
    print("=" * 60)
    
    # Create mock nodes
    @dataclass
    class MockNode:
        human_content: str
        assistant_content: str
        created_at: datetime = None
        cluster_label: str = "test-cluster"
        conversation_mode: str = "chat"
        technical_depth: int = 5
        emotional_valence: str = "neutral"
        urgency: str = "low"
        has_code: bool = False
        has_error: bool = False
        
        @property
        def combined_content(self):
            return f"Human: {self.human_content}\nAssistant: {self.assistant_content}"
    
    nodes = [
        MockNode(
            human_content="How do I fix this async error?",
            assistant_content="You need to await the coroutine.",
            created_at=datetime(2024, 3, 15, 2, 47),
            cluster_label="async-debugging",
            technical_depth=7,
            emotional_valence="frustrated",
            has_code=True,
            has_error=True,
        ),
        MockNode(
            human_content="What's the weather like?",
            assistant_content="I don't have access to weather data.",
            created_at=datetime(2024, 3, 16, 14, 30),
            cluster_label="general-chat",
            technical_depth=1,
        ),
    ]
    
    # Test context generation
    gen = ContextGenerator()
    
    print("Full template:")
    print("-" * 40)
    print(gen.generate_context(nodes[0]))
    print()
    
    gen_minimal = ContextGenerator(ContextConfig(template="minimal"))
    print("Minimal template:")
    print("-" * 40)
    print(gen_minimal.generate_context(nodes[0]))
    print()
    
    gen_conv = ContextGenerator(ContextConfig(template="conversational"))
    print("Conversational template:")
    print("-" * 40)
    print(gen_conv.generate_context(nodes[0]))


if __name__ == "__main__":
    asyncio.run(main())
