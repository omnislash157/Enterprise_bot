"""
hyde.py - Hypothetical Document Embeddings

The insight: user queries and documents speak different languages.
Query: "that websocket thing"
Document: "WebSocket streaming implementation using FastAPI..."

HyDE bridges this gap:
1. Take vague query
2. Ask LLM: "Write a document that would answer this"
3. Embed THAT hypothetical document
4. Search for similar real documents

Works especially well for:
- Vague queries ("that thing we talked about")
- Conceptual searches ("how did we handle the problem")
- Memory-style retrieval ("what was that approach")

Usage:
    hyde = HyDE(embedder, llm_client)
    results = await hyde.search(
        query="that websocket streaming thing",
        retriever=your_retriever,
    )

Version: 1.0.0 (cog_twin)
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Any, Optional, Callable, Awaitable
import re

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

HYDE_PROMPT_TEMPLATE = """You are a helpful assistant that writes hypothetical documents.

Given a user's search query, write a short document (2-3 paragraphs) that would perfectly answer or match their query. Write as if this document already exists in a knowledge base of past conversations.

Be specific and detailed. Include technical terms, concrete examples, and the kind of language that would appear in a real conversation about this topic.

User query: {query}

Write the hypothetical document that would answer this:"""

HYDE_PROMPT_CONVERSATIONAL = """Given this search query from a user looking through their past conversations, write what the relevant conversation excerpt would look like.

Write it as a realistic Human/Assistant exchange that would match this query. Be specific and use concrete details.

Query: {query}

Hypothetical conversation excerpt:"""


@dataclass
class HyDEResult:
    """Result from HyDE search."""
    original_query: str
    hypothetical_doc: str
    search_results: List[Any]
    search_scores: List[float]
    generation_time_ms: float
    search_time_ms: float
    
    @property
    def total_time_ms(self) -> float:
        return self.generation_time_ms + self.search_time_ms


# =============================================================================
# HyDE Engine
# =============================================================================

class HyDE:
    """
    Hypothetical Document Embeddings for improved retrieval.
    
    Generates a hypothetical document that would answer the query,
    then searches for real documents similar to that hypothetical.
    """
    
    def __init__(
        self,
        embedder: Any,  # AsyncEmbedder
        llm_generate: Callable[[str], Awaitable[str]],
        prompt_template: str = HYDE_PROMPT_CONVERSATIONAL,
        max_hypothetical_length: int = 500,
    ):
        """
        Initialize HyDE.
        
        Args:
            embedder: Your AsyncEmbedder instance
            llm_generate: Async function that generates text from prompt
            prompt_template: Template for generating hypotheticals
            max_hypothetical_length: Truncate generated doc to this length
        """
        self.embedder = embedder
        self.llm_generate = llm_generate
        self.prompt_template = prompt_template
        self.max_hypothetical_length = max_hypothetical_length
    
    async def generate_hypothetical(self, query: str) -> str:
        """
        Generate a hypothetical document for the query.
        
        Args:
            query: User's search query
        
        Returns:
            Generated hypothetical document
        """
        prompt = self.prompt_template.format(query=query)
        
        hypothetical = await self.llm_generate(prompt)
        
        # Clean up
        hypothetical = hypothetical.strip()
        
        # Truncate if too long
        if len(hypothetical) > self.max_hypothetical_length:
            hypothetical = hypothetical[:self.max_hypothetical_length] + "..."
        
        return hypothetical
    
    async def search(
        self,
        query: str,
        retriever: Any,  # DualRetriever or similar
        top_k: int = 10,
        also_search_original: bool = True,
        blend_weight: float = 0.7,  # Weight for hypothetical vs original
        **retriever_kwargs,
    ) -> HyDEResult:
        """
        Search using hypothetical document embedding.
        
        Args:
            query: User's search query
            retriever: Your retriever with retrieve() method
            top_k: Number of results to return
            also_search_original: Also search with original query and blend
            blend_weight: Weight for hypothetical results (0-1)
            **retriever_kwargs: Passed to retriever
        
        Returns:
            HyDEResult with search results
        """
        import time
        
        # Generate hypothetical
        gen_start = time.time()
        hypothetical = await self.generate_hypothetical(query)
        gen_time = (time.time() - gen_start) * 1000
        
        logger.debug(f"HyDE generated ({gen_time:.0f}ms): {hypothetical[:100]}...")
        
        # Search with hypothetical
        search_start = time.time()
        
        if also_search_original:
            # Search with both and blend
            hyde_results = await retriever.retrieve(
                hypothetical, 
                top_k=top_k * 2,  # Get more for merging
                **retriever_kwargs
            )
            orig_results = await retriever.retrieve(
                query,
                top_k=top_k * 2,
                **retriever_kwargs
            )
            
            # Blend results (simple: weighted score merge)
            results, scores = self._blend_results(
                hyde_results, orig_results,
                blend_weight=blend_weight,
                top_k=top_k,
            )
        else:
            # Search only with hypothetical
            result = await retriever.retrieve(
                hypothetical,
                top_k=top_k,
                **retriever_kwargs
            )
            results = getattr(result, 'process_memories', [])
            scores = getattr(result, 'process_scores', [])
        
        search_time = (time.time() - search_start) * 1000
        
        return HyDEResult(
            original_query=query,
            hypothetical_doc=hypothetical,
            search_results=results,
            search_scores=scores,
            generation_time_ms=gen_time,
            search_time_ms=search_time,
        )
    
    def _blend_results(
        self,
        hyde_result: Any,
        orig_result: Any,
        blend_weight: float,
        top_k: int,
    ) -> tuple:
        """Blend results from hypothetical and original queries."""
        # Extract results and scores
        hyde_items = getattr(hyde_result, 'process_memories', [])
        hyde_scores = getattr(hyde_result, 'process_scores', [])
        orig_items = getattr(orig_result, 'process_memories', [])
        orig_scores = getattr(orig_result, 'process_scores', [])
        
        # Build score dict by item ID
        scores_by_id = {}
        items_by_id = {}
        
        for item, score in zip(hyde_items, hyde_scores):
            item_id = getattr(item, 'id', id(item))
            scores_by_id[item_id] = blend_weight * score
            items_by_id[item_id] = item
        
        for item, score in zip(orig_items, orig_scores):
            item_id = getattr(item, 'id', id(item))
            if item_id in scores_by_id:
                # Found in both - boost!
                scores_by_id[item_id] += (1 - blend_weight) * score
            else:
                scores_by_id[item_id] = (1 - blend_weight) * score
                items_by_id[item_id] = item
        
        # Sort by blended score
        sorted_ids = sorted(scores_by_id.keys(), key=lambda x: scores_by_id[x], reverse=True)
        
        results = [items_by_id[i] for i in sorted_ids[:top_k]]
        scores = [scores_by_id[i] for i in sorted_ids[:top_k]]
        
        return results, scores
    
    async def embed_hypothetical(self, query: str) -> tuple:
        """
        Generate hypothetical and return its embedding.
        
        Useful for custom search pipelines.
        
        Returns:
            (hypothetical_text, embedding)
        """
        hypothetical = await self.generate_hypothetical(query)
        embedding = await self.embedder.embed_single(hypothetical)
        return hypothetical, embedding


# =============================================================================
# Query Classification
# =============================================================================

class QueryClassifier:
    """
    Classify queries to decide whether to use HyDE.
    
    HyDE helps most with vague/conceptual queries, less with
    specific keyword queries.
    """
    
    VAGUE_PATTERNS = [
        r'\bthat\s+thing\b',
        r'\bwhat\s+was\b',
        r'\bhow\s+did\s+we\b',
        r'\bremember\s+when\b',
        r'\bsomething\s+about\b',
        r'\bthe\s+\w+\s+stuff\b',
        r'\bthat\s+\w+\s+issue\b',
        r'\bwhat\s+about\b',
    ]
    
    SPECIFIC_PATTERNS = [
        r'error:\s*\w+',  # Error messages
        r'\b\d{4}-\d{2}-\d{2}\b',  # Dates
        r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b',  # CamelCase
        r'\b\w+\.\w+\(\)',  # Function calls
        r'"[^"]{10,}"',  # Quoted strings
    ]
    
    @classmethod
    def should_use_hyde(cls, query: str) -> tuple:
        """
        Classify whether HyDE would help with this query.
        
        Returns:
            (should_use: bool, confidence: float, reason: str)
        """
        query_lower = query.lower()
        
        # Check for vague patterns
        vague_matches = sum(
            1 for p in cls.VAGUE_PATTERNS 
            if re.search(p, query_lower)
        )
        
        # Check for specific patterns
        specific_matches = sum(
            1 for p in cls.SPECIFIC_PATTERNS 
            if re.search(p, query)
        )
        
        # Short queries are often vague
        is_short = len(query.split()) <= 4
        
        # Calculate score
        vague_score = vague_matches * 0.3 + (0.2 if is_short else 0)
        specific_score = specific_matches * 0.3
        
        if vague_score > specific_score:
            confidence = min(0.9, 0.5 + vague_score)
            return (True, confidence, f"Vague query detected ({vague_matches} patterns)")
        elif specific_score > 0.3:
            confidence = min(0.9, 0.5 + specific_score)
            return (False, confidence, f"Specific query detected ({specific_matches} patterns)")
        else:
            # Ambiguous - default to using HyDE with low confidence
            return (True, 0.4, "Ambiguous query, defaulting to HyDE")


# =============================================================================
# Adaptive HyDE
# =============================================================================

class AdaptiveHyDE(HyDE):
    """
    HyDE that automatically decides when to use hypothetical generation.
    
    Uses QueryClassifier to skip HyDE for specific queries where
    it would add latency without benefit.
    """
    
    def __init__(
        self,
        embedder: Any,
        llm_generate: Callable[[str], Awaitable[str]],
        min_confidence_for_hyde: float = 0.5,
        **kwargs,
    ):
        super().__init__(embedder, llm_generate, **kwargs)
        self.min_confidence = min_confidence_for_hyde
    
    async def search(
        self,
        query: str,
        retriever: Any,
        top_k: int = 10,
        force_hyde: Optional[bool] = None,
        **retriever_kwargs,
    ) -> HyDEResult:
        """
        Search with automatic HyDE decision.
        
        Args:
            query: Search query
            retriever: Your retriever
            top_k: Results to return
            force_hyde: Override automatic decision
            **retriever_kwargs: Passed to retriever
        """
        import time
        
        # Decide whether to use HyDE
        if force_hyde is not None:
            use_hyde = force_hyde
        else:
            use_hyde, confidence, reason = QueryClassifier.should_use_hyde(query)
            use_hyde = use_hyde and confidence >= self.min_confidence
            logger.debug(f"HyDE decision: {use_hyde} ({confidence:.2f}) - {reason}")
        
        if not use_hyde:
            # Skip HyDE, search directly
            search_start = time.time()
            result = await retriever.retrieve(query, top_k=top_k, **retriever_kwargs)
            search_time = (time.time() - search_start) * 1000
            
            return HyDEResult(
                original_query=query,
                hypothetical_doc="[HyDE skipped - specific query]",
                search_results=getattr(result, 'process_memories', []),
                search_scores=getattr(result, 'process_scores', []),
                generation_time_ms=0,
                search_time_ms=search_time,
            )
        
        # Use HyDE
        return await super().search(query, retriever, top_k, **retriever_kwargs)


# =============================================================================
# Factory
# =============================================================================

def create_hyde_with_grok(
    embedder: Any,
    grok_api_key: str,
    model: str = "grok-3-mini",
) -> HyDE:
    """
    Create HyDE instance using Grok for generation.
    
    Args:
        embedder: Your AsyncEmbedder
        grok_api_key: xAI API key
        model: Grok model to use
    
    Returns:
        Configured HyDE instance
    """
    import httpx
    
    async def grok_generate(prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {grok_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.7,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    return HyDE(embedder, grok_generate)


def create_hyde_with_claude(
    embedder: Any,
    anthropic_api_key: str,
    model: str = "claude-3-haiku-20240307",
) -> HyDE:
    """
    Create HyDE instance using Claude for generation.
    """
    import httpx
    
    async def claude_generate(prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
    
    return HyDE(embedder, claude_generate)


# =============================================================================
# CLI
# =============================================================================

async def main():
    """Test HyDE."""
    print("HyDE Test")
    print("=" * 60)
    
    # Test query classification
    test_queries = [
        "that websocket thing we talked about",
        "error: ECONNREFUSED in async handler",
        "how did we handle the streaming issue",
        "AsyncEmbedder.embed_batch() timeout",
        "what was that approach for caching",
        "2024-03-15 deployment logs",
    ]
    
    print("Query Classification:")
    for q in test_queries:
        use_hyde, conf, reason = QueryClassifier.should_use_hyde(q)
        status = "HYDE" if use_hyde else "DIRECT"
        print(f"  [{status}] ({conf:.2f}) {q}")
        print(f"         {reason}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
