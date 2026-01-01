"""
reranker.py - Cross-Encoder Reranking for CogTwin

The cheap trick that beats everything: bi-encoders embed query and doc 
separately, cross-encoders see them TOGETHER and score directly.

Flow:
    FAISS: 3000 docs -> 100 candidates (5ms)
    Reranker: 100 candidates -> top 10 (50ms)

The reranker sees (query, document) pairs and outputs relevance scores.
Way more accurate than cosine similarity alone.

Models:
    - BAAI/bge-reranker-v2-m3 (best quality, ~300MB)
    - cross-encoder/ms-marco-MiniLM-L-12-v2 (fast, ~120MB)
    - BAAI/bge-reranker-base (balanced)

Usage:
    reranker = Reranker()
    scored = await reranker.rerank(query, candidates, top_k=10)
    
Version: 1.0.0 (cog_twin)
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Tuple, Any, Optional, Union
from concurrent.futures import ThreadPoolExecutor

import numpy as np

logger = logging.getLogger(__name__)

# Lazy load to avoid import overhead
_reranker_model = None
_reranker_tokenizer = None
_executor = ThreadPoolExecutor(max_workers=2)


@dataclass
class RerankResult:
    """Single reranked item with score."""
    item: Any  # Original object (MemoryNode, etc.)
    score: float  # Cross-encoder relevance score (higher = better)
    original_rank: int  # Position before reranking
    original_score: float  # Score before reranking (e.g., cosine sim)
    new_rank: int = 0  # Position after reranking
    
    @property
    def rank_change(self) -> int:
        """How much this item moved. Positive = promoted."""
        return self.original_rank - self.new_rank


@dataclass 
class RerankOutput:
    """Full reranking output with diagnostics."""
    query: str
    results: List[RerankResult]
    rerank_time_ms: float
    candidates_scored: int
    model_name: str
    
    def top_k(self, k: int) -> List[RerankResult]:
        """Get top k results."""
        return self.results[:k]
    
    def get_items(self) -> List[Any]:
        """Extract just the items in reranked order."""
        return [r.item for r in self.results]
    
    def get_scores(self) -> List[float]:
        """Extract just the scores in reranked order."""
        return [r.score for r in self.results]


class Reranker:
    """
    Cross-encoder reranker for second-stage retrieval.
    
    Takes candidates from FAISS/BM25 and rescores with a cross-encoder
    that sees query and document together.
    
    Thread-safe, lazy-loads model on first use.
    """
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "auto",
        batch_size: int = 32,
        max_length: int = 512,
    ):
        """
        Initialize reranker.
        
        Args:
            model_name: HuggingFace model name
            device: "auto", "cuda", "cpu", or "mps"
            batch_size: Batch size for scoring
            max_length: Max token length for inputs
        """
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.max_length = max_length
        
        self._model = None
        self._tokenizer = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy load model on first use."""
        if self._initialized:
            return
        
        global _reranker_model, _reranker_tokenizer
        
        # Check if already loaded globally (shared across instances)
        if _reranker_model is not None and self.model_name in str(type(_reranker_model)):
            self._model = _reranker_model
            self._tokenizer = _reranker_tokenizer
            self._initialized = True
            return
        
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch
            
            logger.info(f"Loading reranker model: {self.model_name}")
            
            # Determine device
            if self.device == "auto":
                if torch.cuda.is_available():
                    device = "cuda"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    device = "mps"
                else:
                    device = "cpu"
            else:
                device = self.device
            
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if device != "cpu" else torch.float32,
            )
            self._model.to(device)
            self._model.eval()
            
            # Cache globally
            _reranker_model = self._model
            _reranker_tokenizer = self._tokenizer
            
            self._initialized = True
            logger.info(f"Reranker loaded on {device}")
            
        except ImportError:
            logger.error("transformers not installed. Run: pip install transformers torch")
            raise
        except Exception as e:
            logger.error(f"Failed to load reranker: {e}")
            raise
    
    def _extract_text(self, item: Any) -> str:
        """Extract searchable text from various item types."""
        # MemoryNode
        if hasattr(item, 'combined_content'):
            return item.combined_content
        
        # EpisodicMemory
        if hasattr(item, 'full_text'):
            return item.full_text
        
        # Dict with content
        if isinstance(item, dict):
            if 'content' in item:
                return item['content']
            if 'text' in item:
                return item['text']
            if 'human_content' in item and 'assistant_content' in item:
                return f"{item['human_content']}\n{item['assistant_content']}"
        
        # String
        if isinstance(item, str):
            return item
        
        # Fallback to str representation
        return str(item)
    
    def _score_batch(
        self, 
        query: str, 
        texts: List[str]
    ) -> List[float]:
        """Score a batch of query-document pairs."""
        import torch
        
        device = next(self._model.parameters()).device
        
        # Create pairs
        pairs = [[query, text] for text in texts]
        
        # Tokenize
        inputs = self._tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Score
        with torch.no_grad():
            outputs = self._model(**inputs)
            # BGE reranker outputs logits, take first column or squeeze
            scores = outputs.logits.squeeze(-1)
            if len(scores.shape) > 1:
                scores = scores[:, 0]
            scores = scores.cpu().numpy().tolist()
        
        return scores
    
    def rerank_sync(
        self,
        query: str,
        candidates: List[Tuple[Any, float]],  # (item, original_score)
        top_k: Optional[int] = None,
    ) -> RerankOutput:
        """
        Synchronous reranking.
        
        Args:
            query: Search query
            candidates: List of (item, original_score) tuples
            top_k: Return top k results (None = all)
        
        Returns:
            RerankOutput with reranked results
        """
        import time
        start = time.time()
        
        self._ensure_initialized()
        
        if not candidates:
            return RerankOutput(
                query=query,
                results=[],
                rerank_time_ms=0,
                candidates_scored=0,
                model_name=self.model_name,
            )
        
        # Extract texts
        items = [c[0] for c in candidates]
        original_scores = [c[1] for c in candidates]
        texts = [self._extract_text(item) for item in items]
        
        # Score in batches
        all_scores = []
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            batch_scores = self._score_batch(query, batch_texts)
            all_scores.extend(batch_scores)
        
        # Build results
        results = [
            RerankResult(
                item=items[i],
                score=all_scores[i],
                original_rank=i,
                original_score=original_scores[i],
            )
            for i in range(len(items))
        ]
        
        # Sort by reranker score
        results.sort(key=lambda r: r.score, reverse=True)
        
        # Assign new ranks
        for i, r in enumerate(results):
            r.new_rank = i
        
        # Trim to top_k
        if top_k:
            results = results[:top_k]
        
        elapsed = (time.time() - start) * 1000
        
        return RerankOutput(
            query=query,
            results=results,
            rerank_time_ms=elapsed,
            candidates_scored=len(candidates),
            model_name=self.model_name,
        )
    
    async def rerank(
        self,
        query: str,
        candidates: List[Tuple[Any, float]],
        top_k: Optional[int] = None,
    ) -> RerankOutput:
        """
        Async reranking (runs in thread pool).
        
        Args:
            query: Search query
            candidates: List of (item, original_score) tuples
            top_k: Return top k results (None = all)
        
        Returns:
            RerankOutput with reranked results
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            self.rerank_sync,
            query,
            candidates,
            top_k,
        )


# =============================================================================
# Integration Helper
# =============================================================================

class RerankedRetriever:
    """
    Wrapper that adds reranking to any retriever.
    
    Usage:
        base_retriever = DualRetriever.load(...)
        reranked = RerankedRetriever(base_retriever)
        results = await reranked.retrieve(query, top_k=10, rerank_top=50)
    """
    
    def __init__(
        self,
        base_retriever: Any,
        reranker: Optional[Reranker] = None,
        rerank_candidates: int = 50,
    ):
        """
        Args:
            base_retriever: Your existing retriever
            reranker: Reranker instance (creates default if None)
            rerank_candidates: How many candidates to fetch for reranking
        """
        self.base = base_retriever
        self.reranker = reranker or Reranker()
        self.rerank_candidates = rerank_candidates
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        rerank: bool = True,
        **kwargs
    ) -> Any:
        """
        Retrieve with optional reranking.
        
        Fetches rerank_candidates from base, reranks, returns top_k.
        """
        # Get more candidates than needed
        fetch_k = self.rerank_candidates if rerank else top_k
        
        # Call base retriever
        result = await self.base.retrieve(query, top_k=fetch_k, **kwargs)
        
        if not rerank:
            return result
        
        # Rerank process memories
        if hasattr(result, 'process_memories') and result.process_memories:
            candidates = list(zip(result.process_memories, result.process_scores))
            reranked = await self.reranker.rerank(query, candidates, top_k=top_k)
            result.process_memories = reranked.get_items()
            result.process_scores = reranked.get_scores()
        
        # Rerank episodic memories
        if hasattr(result, 'episodic_memories') and result.episodic_memories:
            candidates = list(zip(result.episodic_memories, result.episodic_scores))
            reranked = await self.reranker.rerank(query, candidates, top_k=top_k)
            result.episodic_memories = reranked.get_items()
            result.episodic_scores = reranked.get_scores()
        
        # Rebuild context
        if hasattr(result, 'build_venom_context'):
            result.build_venom_context()
        
        return result


# =============================================================================
# CLI
# =============================================================================

async def main():
    """Test reranker."""
    print("Reranker Test")
    print("=" * 60)
    
    # Test with dummy data
    reranker = Reranker()
    
    query = "How do I fix async errors in FastAPI?"
    
    candidates = [
        ("FastAPI is a web framework for Python.", 0.7),
        ("To fix async errors, ensure you're using await correctly.", 0.65),
        ("I like pizza and beer.", 0.6),
        ("Async/await in Python requires proper event loop handling.", 0.55),
        ("The weather is nice today.", 0.5),
    ]
    
    print(f"Query: {query}")
    print(f"Candidates: {len(candidates)}")
    print()
    
    result = await reranker.rerank(query, candidates)
    
    print(f"Reranked in {result.rerank_time_ms:.1f}ms:")
    for i, r in enumerate(result.results):
        print(f"  {i+1}. [{r.score:.3f}] (was #{r.original_rank+1}, {r.original_score:.2f})")
        text = r.item[:60] + "..." if len(r.item) > 60 else r.item
        print(f"     {text}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
