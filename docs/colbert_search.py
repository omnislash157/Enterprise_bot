"""
colbert_search.py - Late Interaction Retrieval with ColBERT

The problem with bi-encoders: one vector per document loses nuance.
"async error handling" as a single vector can't capture that
"async" matches one part and "error handling" matches another.

ColBERT (Contextualized Late Interaction over BERT):
- Keep ALL token embeddings for each document
- At query time: MaxSim between each query token and all doc tokens
- "async" matches the async parts, "error" matches error parts
- Sum the max similarities = document score

This captures fine-grained matching that single-vector misses.

RAGatouille makes ColBERT easy to use with a scikit-learn-like API.

Usage:
    colbert = ColBERTSearch()
    colbert.index(documents)  # One-time indexing
    results = colbert.search("async error handling", top_k=10)

Version: 1.0.0 (cog_twin)
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import json

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)


@dataclass
class ColBERTResult:
    """Single result from ColBERT search."""
    document_id: str
    content: str
    score: float
    rank: int
    metadata: Dict[str, Any] = None


@dataclass
class ColBERTSearchOutput:
    """Full search output."""
    query: str
    results: List[ColBERTResult]
    search_time_ms: float
    index_size: int


class ColBERTSearch:
    """
    ColBERT late-interaction search using RAGatouille.
    
    Provides token-level matching that captures fine-grained
    semantic similarity better than single-vector approaches.
    """
    
    def __init__(
        self,
        index_path: Optional[Path] = None,
        model_name: str = "colbert-ir/colbertv2.0",
    ):
        """
        Initialize ColBERT search.
        
        Args:
            index_path: Path to existing index (None to create new)
            model_name: ColBERT model to use
        """
        self.index_path = Path(index_path) if index_path else None
        self.model_name = model_name
        
        self._rag = None
        self._indexed = False
        self._documents: List[Dict[str, Any]] = []
        self._doc_map: Dict[str, Dict[str, Any]] = {}
    
    def _ensure_initialized(self):
        """Lazy load RAGatouille."""
        if self._rag is not None:
            return
        
        try:
            from ragatouille import RAGPretrainedModel
            
            if self.index_path and self.index_path.exists():
                # Load existing index
                logger.info(f"Loading ColBERT index from {self.index_path}")
                self._rag = RAGPretrainedModel.from_index(str(self.index_path))
                self._indexed = True
                self._load_doc_map()
            else:
                # Create new model
                logger.info(f"Initializing ColBERT model: {self.model_name}")
                self._rag = RAGPretrainedModel.from_pretrained(self.model_name)
            
        except ImportError:
            logger.error(
                "RAGatouille not installed. Run: pip install ragatouille"
            )
            raise
    
    def _load_doc_map(self):
        """Load document metadata from index."""
        if not self.index_path:
            return
        
        meta_path = self.index_path / "doc_metadata.json"
        if meta_path.exists():
            with open(meta_path) as f:
                self._doc_map = json.load(f)
            logger.info(f"Loaded {len(self._doc_map)} document metadata entries")
    
    def _save_doc_map(self):
        """Save document metadata to index."""
        if not self.index_path:
            return
        
        self.index_path.mkdir(parents=True, exist_ok=True)
        meta_path = self.index_path / "doc_metadata.json"
        with open(meta_path, "w") as f:
            json.dump(self._doc_map, f)
    
    def index(
        self,
        documents: List[Dict[str, Any]],
        index_name: str = "cogtwin_colbert",
        doc_id_key: str = "id",
        content_key: str = "content",
        max_document_length: int = 512,
        split_documents: bool = True,
    ) -> str:
        """
        Index documents for ColBERT search.
        
        Args:
            documents: List of dicts with at least 'id' and 'content'
            index_name: Name for the index
            doc_id_key: Key for document ID in dicts
            content_key: Key for document content in dicts
            max_document_length: Max tokens per document
            split_documents: Whether to split long documents
        
        Returns:
            Path to created index
        """
        self._ensure_initialized()
        
        # Extract content and IDs
        doc_contents = []
        doc_ids = []
        
        for doc in documents:
            doc_id = doc.get(doc_id_key, str(len(doc_ids)))
            content = doc.get(content_key, "")
            
            if not content:
                continue
            
            doc_contents.append(content)
            doc_ids.append(doc_id)
            
            # Store full metadata
            self._doc_map[doc_id] = doc
        
        self._documents = documents
        
        logger.info(f"Indexing {len(doc_contents)} documents with ColBERT...")
        
        # Index with RAGatouille
        index_path = self._rag.index(
            collection=doc_contents,
            document_ids=doc_ids,
            index_name=index_name,
            max_document_length=max_document_length,
            split_documents=split_documents,
        )
        
        self.index_path = Path(index_path)
        self._indexed = True
        
        # Save metadata
        self._save_doc_map()
        
        logger.info(f"ColBERT index created at {index_path}")
        return index_path
    
    def index_from_nodes(
        self,
        nodes: List[Any],  # MemoryNode objects
        index_name: str = "cogtwin_colbert",
    ) -> str:
        """
        Index MemoryNode objects.
        
        Convenience wrapper for index() that handles MemoryNode format.
        """
        documents = []
        
        for node in nodes:
            doc = {
                "id": node.id,
                "content": node.combined_content,
                "conversation_id": node.conversation_id,
                "sequence_index": node.sequence_index,
                "created_at": node.created_at.isoformat() if node.created_at else None,
                "cluster_id": node.cluster_id,
                "cluster_label": node.cluster_label,
            }
            documents.append(doc)
        
        return self.index(
            documents,
            index_name=index_name,
            doc_id_key="id",
            content_key="content",
        )
    
    def search_sync(
        self,
        query: str,
        top_k: int = 10,
    ) -> ColBERTSearchOutput:
        """
        Synchronous ColBERT search.
        
        Args:
            query: Search query
            top_k: Number of results
        
        Returns:
            ColBERTSearchOutput with results
        """
        import time
        start = time.time()
        
        self._ensure_initialized()
        
        if not self._indexed:
            logger.warning("No index loaded - call index() first")
            return ColBERTSearchOutput(
                query=query,
                results=[],
                search_time_ms=0,
                index_size=0,
            )
        
        # Search
        raw_results = self._rag.search(query, k=top_k)
        
        # Convert to our format
        results = []
        for i, r in enumerate(raw_results):
            doc_id = r.get("document_id", r.get("id", str(i)))
            content = r.get("content", "")
            score = r.get("score", 0.0)
            
            # Get full metadata if available
            metadata = self._doc_map.get(doc_id, {})
            
            results.append(ColBERTResult(
                document_id=doc_id,
                content=content,
                score=score,
                rank=i,
                metadata=metadata,
            ))
        
        elapsed = (time.time() - start) * 1000
        
        return ColBERTSearchOutput(
            query=query,
            results=results,
            search_time_ms=elapsed,
            index_size=len(self._doc_map),
        )
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> ColBERTSearchOutput:
        """
        Async ColBERT search.
        
        Runs in thread pool to avoid blocking.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            self.search_sync,
            query,
            top_k,
        )
    
    def add_to_index(
        self,
        documents: List[Dict[str, Any]],
        doc_id_key: str = "id",
        content_key: str = "content",
    ):
        """
        Add documents to existing index.
        
        Note: RAGatouille may require re-indexing for optimal performance.
        This is a convenience method for incremental updates.
        """
        self._ensure_initialized()
        
        if not self._indexed:
            raise RuntimeError("No index exists - call index() first")
        
        doc_contents = []
        doc_ids = []
        
        for doc in documents:
            doc_id = doc.get(doc_id_key, str(len(self._doc_map)))
            content = doc.get(content_key, "")
            
            if not content:
                continue
            
            doc_contents.append(content)
            doc_ids.append(doc_id)
            self._doc_map[doc_id] = doc
        
        # Add to index
        self._rag.add_to_index(
            new_collection=doc_contents,
            new_document_ids=doc_ids,
        )
        
        self._save_doc_map()
        logger.info(f"Added {len(doc_contents)} documents to ColBERT index")


# =============================================================================
# Integration with existing retrieval
# =============================================================================

class HybridColBERTRetriever:
    """
    Combines ColBERT with existing FAISS retrieval.
    
    Uses RRF (Reciprocal Rank Fusion) to merge results from both.
    """
    
    def __init__(
        self,
        colbert: ColBERTSearch,
        base_retriever: Any,  # Your existing retriever
        colbert_weight: float = 0.5,
        rrf_k: int = 60,
    ):
        """
        Args:
            colbert: ColBERTSearch instance
            base_retriever: Your existing retriever (FAISS-based)
            colbert_weight: Weight for ColBERT results in fusion
            rrf_k: RRF ranking parameter
        """
        self.colbert = colbert
        self.base = base_retriever
        self.colbert_weight = colbert_weight
        self.rrf_k = rrf_k
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        use_colbert: bool = True,
        **kwargs,
    ) -> Any:
        """
        Hybrid retrieval with ColBERT + FAISS fusion.
        """
        # Get base results
        base_result = await self.base.retrieve(query, top_k=top_k * 2, **kwargs)
        
        if not use_colbert:
            return base_result
        
        # Get ColBERT results
        colbert_result = await self.colbert.search(query, top_k=top_k * 2)
        
        # Fuse with RRF
        fused_ids, fused_scores = self._rrf_fuse(
            base_result,
            colbert_result,
            top_k,
        )
        
        # Rebuild result with fused ranking
        # (Implementation depends on your result format)
        # For now, just return base result with logged ColBERT boost
        logger.debug(
            f"ColBERT fusion: {len(colbert_result.results)} ColBERT hits, "
            f"fused to {len(fused_ids)} results"
        )
        
        return base_result
    
    def _rrf_fuse(
        self,
        base_result: Any,
        colbert_result: ColBERTSearchOutput,
        top_k: int,
    ) -> Tuple[List[str], List[float]]:
        """Fuse results using Reciprocal Rank Fusion."""
        scores = {}
        
        # Score base results
        base_items = getattr(base_result, 'process_memories', [])
        base_weight = 1 - self.colbert_weight
        
        for rank, item in enumerate(base_items):
            item_id = getattr(item, 'id', str(id(item)))
            scores[item_id] = scores.get(item_id, 0) + base_weight / (self.rrf_k + rank + 1)
        
        # Score ColBERT results
        for r in colbert_result.results:
            scores[r.document_id] = scores.get(r.document_id, 0) + \
                self.colbert_weight / (self.rrf_k + r.rank + 1)
        
        # Sort by fused score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        return sorted_ids[:top_k], [scores[i] for i in sorted_ids[:top_k]]


# =============================================================================
# CLI
# =============================================================================

async def main():
    """Test ColBERT search."""
    print("ColBERT Search Test")
    print("=" * 60)
    
    # Check if RAGatouille is available
    try:
        from ragatouille import RAGPretrainedModel
        print("RAGatouille available")
    except ImportError:
        print("RAGatouille not installed. Run: pip install ragatouille")
        return
    
    # Create test documents
    documents = [
        {"id": "1", "content": "FastAPI is a modern web framework for building APIs with Python."},
        {"id": "2", "content": "Async errors in Python often occur when mixing sync and async code."},
        {"id": "3", "content": "The weather is sunny today with clear skies."},
        {"id": "4", "content": "To fix async errors, ensure you await all coroutines properly."},
        {"id": "5", "content": "HDBSCAN clustering groups similar data points together."},
    ]
    
    # Initialize and index
    colbert = ColBERTSearch()
    print("Indexing documents...")
    colbert.index(documents, index_name="test_colbert")
    
    # Search
    query = "How do I fix async errors?"
    print(f"\nSearching: '{query}'")
    
    result = await colbert.search(query, top_k=3)
    
    print(f"\nResults ({result.search_time_ms:.1f}ms):")
    for r in result.results:
        print(f"  {r.rank+1}. [{r.score:.3f}] {r.content[:60]}...")


if __name__ == "__main__":
    asyncio.run(main())
