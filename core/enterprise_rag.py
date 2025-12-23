"""
Enterprise RAG Retriever - Process Manual Search

Retrieves relevant chunks from documents table using:
1. BGE-M3 dense vectors (semantic similarity)
2. Keyword matching (fallback when embeddings are NULL)

This is the manual RAG that fires for procedural/lookup/complaint queries.
Python fires this tool, not Grok.

Department filtering: Pass department_id to filter results by department.
Valid values: 'sales', 'purchasing', 'warehouse' (or None for all).

Usage:
    from .enterprise_rag import EnterpriseRAGRetriever

    rag = EnterpriseRAGRetriever(config)
    chunks = await rag.search(
        query="how do I process a credit memo",
        department_id="sales",  # Filter by department
        threshold=0.6,  # Returns ALL chunks above this score
    )

Version: 1.1.0
"""

import asyncio
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from .cache import get_cache

logger = logging.getLogger(__name__)

# Try to import database drivers
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logger.warning("asyncpg not available - using sync fallback")

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


# =============================================================================
# EMBEDDING CLIENT
# =============================================================================

class EmbeddingClient:
    """
    Client for generating embeddings via DeepInfra BGE-M3.
    
    Falls back to None if not configured (keyword search only).
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = os.getenv("DEEPINFRA_API_KEY")
        self.model = config.get("embedding", {}).get("model", "BAAI/bge-m3")
        self.endpoint = config.get("embedding", {}).get(
            "endpoint", 
            "https://api.deepinfra.com/v1/inference/BAAI/bge-m3"
        )
        self._http_client = None
    
    @property
    def available(self) -> bool:
        return self.api_key is not None
    
    async def embed(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text.
        
        Returns None if embedding service not available.
        """
        if not self.available:
            return None
        
        try:
            import httpx
            
            if self._http_client is None:
                self._http_client = httpx.AsyncClient(timeout=30.0)
            
            response = await self._http_client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"inputs": [text]},
            )
            response.raise_for_status()
            
            data = response.json()
            # DeepInfra returns {"embeddings": [[...]]}
            embeddings = data.get("embeddings", [[]])[0]
            return embeddings
            
        except Exception as e:
            logger.error(f"[EmbeddingClient] Failed to generate embedding: {e}")
            return None
    
    async def close(self):
        if self._http_client:
            await self._http_client.aclose()


# =============================================================================
# RAG RETRIEVER
# =============================================================================

class EnterpriseRAGRetriever:
    """
    Retrieves process manual chunks from PostgreSQL.

    Search strategy:
    1. If embeddings available: vector similarity search (cosine)
    2. Fallback: keyword search on content + section_title

    Department filtering: Pass department_id to filter results.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Database config
        db_config = config.get("database", {})
        self.connection_string = os.getenv("AZURE_PG_CONNECTION_STRING") or self._build_connection_string(db_config)

        # RAG config (threshold-only, no top_k)
        rag_config = config.get("features", {}).get("enterprise_rag", {})
        self.table_name = rag_config.get("table", "enterprise.documents")
        self.default_threshold = rag_config.get("threshold", 0.6)
        # NOTE: No default_top_k - threshold-only by design

        # Search mode config
        self.search_mode = rag_config.get("search_mode", "hybrid")
        self.content_weight = rag_config.get("content_weight", 0.7)
        self.question_weight = rag_config.get("question_weight", 0.3)

        # Embedding client
        self.embedder = EmbeddingClient(config)

        # Connection pool (lazy init)
        self._pool = None

        logger.info(f"[EnterpriseRAG] Initialized: table={self.table_name}, mode={self.search_mode}, weights={self.content_weight}/{self.question_weight}")
    
    def _build_connection_string(self, db_config: Dict) -> str:
        """Build connection string from config."""
        host = db_config.get("host") or os.getenv("AZURE_PG_HOST", "localhost")
        port = db_config.get("port") or os.getenv("AZURE_PG_PORT", "5432")
        database = db_config.get("database") or os.getenv("AZURE_PG_DATABASE", "postgres")
        user = db_config.get("user") or os.getenv("AZURE_PG_USER", "postgres")
        password = db_config.get("password") or os.getenv("AZURE_PG_PASSWORD", "")
        sslmode = db_config.get("sslmode") or os.getenv("AZURE_PG_SSLMODE", "require")
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}?sslmode={sslmode}"
    
    async def _get_pool(self):
        """Get or create connection pool."""
        if self._pool is None and ASYNCPG_AVAILABLE:
            try:
                self._pool = await asyncpg.create_pool(
                    self.connection_string,
                    min_size=1,
                    max_size=5,
                    command_timeout=30,
                )
                logger.info("[EnterpriseRAG] Connection pool created")
            except Exception as e:
                logger.error(f"[EnterpriseRAG] Failed to create pool: {e}")
                raise
        return self._pool
    
    async def search(
        self,
        query: str,
        department_id: str = None,
        threshold: float = None,
        search_mode: str = "hybrid",  # NEW PARAMETER
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant manual chunks.

        Returns ALL chunks above threshold - no arbitrary cap.
        Filters by department_id when provided.

        Args:
            query: User's query
            department_id: Department filter ('sales', 'purchasing', 'warehouse', or None for all)
            threshold: Minimum similarity threshold
            search_mode: "content", "question", or "hybrid" (default)

        Returns:
            List of chunk dicts with content, metadata, and score
        """
        threshold = threshold or self.default_threshold
        start_time = datetime.now()
        cache = get_cache()

        # Check RAG cache first (include search_mode in cache key)
        if department_id:
            cache_key_suffix = f"{department_id}:{search_mode}"
            cached_results = await cache.get_rag_results(query, cache_key_suffix)
            if cached_results is not None:
                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                logger.info(f"[EnterpriseRAG] CACHE HIT ({search_mode}) - {len(cached_results)} results in {elapsed_ms:.0f}ms")
                return cached_results

        if department_id:
            logger.info(f"[EnterpriseRAG] Filtering by department: {department_id}")

        # Check embedding cache
        query_embedding = await cache.get_embedding(query)

        if query_embedding is None:
            # Cache miss - generate embedding
            query_embedding = await self.embedder.embed(query)
            if query_embedding:
                await cache.set_embedding(query, query_embedding)

        if query_embedding:
            results = await self._vector_search(
                query_embedding=query_embedding,
                department_id=department_id,
                threshold=threshold,
                search_mode=search_mode,  # Pass through
                content_weight=self.content_weight,
                question_weight=self.question_weight,
            )
            search_type = f"vector_{search_mode}"
        else:
            # Fallback to keyword search
            results = await self._keyword_search(
                query=query,
                department_id=department_id,
            )
            search_type = "keyword"

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"[EnterpriseRAG] {search_type} returned {len(results)} results in {elapsed_ms:.0f}ms")

        # Cache results
        if department_id and results:
            cache_key_suffix = f"{department_id}:{search_mode}"
            await cache.set_rag_results(query, cache_key_suffix, results)

        return results
    
    async def _vector_search(
        self,
        query_embedding: List[float],
        department_id: str = None,
        threshold: float = 0.6,
        search_mode: str = "hybrid",  # "content", "question", or "hybrid"
        content_weight: float = 0.7,
        question_weight: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        Vector similarity search using pgvector with hybrid scoring.

        Search modes:
        - "content": Traditional content-only search (current behavior)
        - "question": Search against synthetic questions only
        - "hybrid": Combine both scores (recommended)

        Args:
            query_embedding: Query vector (1024 dims)
            department_id: Filter by department (optional)
            threshold: Minimum similarity threshold
            search_mode: "content", "question", or "hybrid"
            content_weight: Weight for content similarity (default 0.7)
            question_weight: Weight for question similarity (default 0.3)

        Returns:
            List of chunk dicts with content, metadata, and scores
        """
        pool = await self._get_pool()

        # Format embedding for pgvector
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        if search_mode == "content":
            # Original behavior - content only
            if department_id:
                query = f"""
                    SELECT
                        id, content, section_title, source_file, department_id,
                        1 - (embedding <=> $1::vector) as score,
                        1 - (embedding <=> $1::vector) as content_score,
                        NULL as question_score
                    FROM {self.table_name}
                    WHERE department_id = $2
                      AND embedding IS NOT NULL
                      AND 1 - (embedding <=> $1::vector) >= $3
                    ORDER BY score DESC
                """
                params = (embedding_str, department_id, threshold)
            else:
                query = f"""
                    SELECT
                        id, content, section_title, source_file, department_id,
                        1 - (embedding <=> $1::vector) as score,
                        1 - (embedding <=> $1::vector) as content_score,
                        NULL as question_score
                    FROM {self.table_name}
                    WHERE embedding IS NOT NULL
                      AND 1 - (embedding <=> $1::vector) >= $2
                    ORDER BY score DESC
                """
                params = (embedding_str, threshold)

        elif search_mode == "question":
            # Question embedding only
            if department_id:
                query = f"""
                    SELECT
                        id, content, section_title, source_file, department_id,
                        1 - (synthetic_questions_embedding <=> $1::vector) as score,
                        NULL as content_score,
                        1 - (synthetic_questions_embedding <=> $1::vector) as question_score
                    FROM {self.table_name}
                    WHERE department_id = $2
                      AND synthetic_questions_embedding IS NOT NULL
                      AND 1 - (synthetic_questions_embedding <=> $1::vector) >= $3
                    ORDER BY score DESC
                """
                params = (embedding_str, department_id, threshold)
            else:
                query = f"""
                    SELECT
                        id, content, section_title, source_file, department_id,
                        1 - (synthetic_questions_embedding <=> $1::vector) as score,
                        NULL as content_score,
                        1 - (synthetic_questions_embedding <=> $1::vector) as question_score
                    FROM {self.table_name}
                    WHERE synthetic_questions_embedding IS NOT NULL
                      AND 1 - (synthetic_questions_embedding <=> $1::vector) >= $2
                    ORDER BY score DESC
                """
                params = (embedding_str, threshold)

        else:  # hybrid (default)
            # Combined scoring: content_weight * content + question_weight * question
            if department_id:
                query = f"""
                    SELECT
                        id, content, section_title, source_file, department_id,
                        synthetic_questions,
                        1 - (embedding <=> $1::vector) as content_score,
                        COALESCE(1 - (synthetic_questions_embedding <=> $1::vector), 0) as question_score,
                        (
                            $4 * (1 - (embedding <=> $1::vector)) +
                            $5 * COALESCE(1 - (synthetic_questions_embedding <=> $1::vector), 0)
                        ) as score
                    FROM {self.table_name}
                    WHERE department_id = $2
                      AND embedding IS NOT NULL
                      AND (
                          1 - (embedding <=> $1::vector) >= $3
                          OR COALESCE(1 - (synthetic_questions_embedding <=> $1::vector), 0) >= $3
                      )
                    ORDER BY score DESC
                """
                params = (embedding_str, department_id, threshold, content_weight, question_weight)
            else:
                query = f"""
                    SELECT
                        id, content, section_title, source_file, department_id,
                        synthetic_questions,
                        1 - (embedding <=> $1::vector) as content_score,
                        COALESCE(1 - (synthetic_questions_embedding <=> $1::vector), 0) as question_score,
                        (
                            $2 * (1 - (embedding <=> $1::vector)) +
                            $3 * COALESCE(1 - (synthetic_questions_embedding <=> $1::vector), 0)
                        ) as score
                    FROM {self.table_name}
                    WHERE embedding IS NOT NULL
                      AND (
                          1 - (embedding <=> $1::vector) >= $4
                          OR COALESCE(1 - (synthetic_questions_embedding <=> $1::vector), 0) >= $4
                      )
                    ORDER BY score DESC
                """
                params = (embedding_str, content_weight, question_weight, threshold)

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

                results = []
                for row in rows:
                    result = {
                        "id": str(row["id"]),
                        "content": row["content"],
                        "section_title": row["section_title"],
                        "source_file": row["source_file"],
                        "department": row["department_id"],
                        "score": float(row["score"]),
                        "search_type": f"vector_{search_mode}",
                    }

                    # Add component scores for debugging/tuning
                    if row.get("content_score") is not None:
                        result["content_score"] = float(row["content_score"])
                    if row.get("question_score") is not None:
                        result["question_score"] = float(row["question_score"])

                    # Include synthetic questions if available (for debugging)
                    if "synthetic_questions" in row.keys() and row["synthetic_questions"]:
                        result["synthetic_questions"] = row["synthetic_questions"][:3]  # First 3

                    results.append(result)

                return results

        except Exception as e:
            logger.error(f"[EnterpriseRAG] Vector search failed: {e}")
            # Fall back to keyword search
            return await self._keyword_search(
                query=" ".join(str(x) for x in query_embedding[:10]),
                department_id=department_id,
            )
    
    async def _keyword_search(
        self,
        query: str,
        department_id: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Keyword search fallback using PostgreSQL full-text search.

        Uses ts_rank for scoring. Returns all matches (no arbitrary limit).
        Filters by department_id when provided.
        """
        pool = await self._get_pool()

        # Clean query for tsquery
        clean_query = " & ".join(
            word.strip() for word in query.split()
            if len(word.strip()) > 2
        )

        if not clean_query:
            clean_query = query.replace(" ", " & ")

        # Build query with optional department filter
        if department_id:
            sql = f"""
                SELECT
                    id,
                    content,
                    section_title,
                    source_file,
                    department_id,
                    ts_rank(
                        to_tsvector('english', coalesce(content, '') || ' ' || coalesce(section_title, '')),
                        plainto_tsquery('english', $1)
                    ) as score
                FROM {self.table_name}
                WHERE
                    department_id = $2
                    AND (
                        to_tsvector('english', coalesce(content, '') || ' ' || coalesce(section_title, ''))
                        @@ plainto_tsquery('english', $1)
                        OR content ILIKE '%' || $1 || '%'
                        OR section_title ILIKE '%' || $1 || '%'
                    )
                ORDER BY score DESC
            """
            params = (query, department_id)
        else:
            sql = f"""
                SELECT
                    id,
                    content,
                    section_title,
                    source_file,
                    department_id,
                    ts_rank(
                        to_tsvector('english', coalesce(content, '') || ' ' || coalesce(section_title, '')),
                        plainto_tsquery('english', $1)
                    ) as score
                FROM {self.table_name}
                WHERE
                    to_tsvector('english', coalesce(content, '') || ' ' || coalesce(section_title, ''))
                    @@ plainto_tsquery('english', $1)
                    OR content ILIKE '%' || $1 || '%'
                    OR section_title ILIKE '%' || $1 || '%'
                ORDER BY score DESC
            """
            params = (query,)

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)

                return [
                    {
                        "id": str(row["id"]),
                        "content": row["content"],
                        "section_title": row["section_title"],
                        "source_file": row["source_file"],
                        "department": row["department_id"],
                        "score": float(row["score"]) if row["score"] else 0.5,
                        "search_type": "keyword",
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"[EnterpriseRAG] Keyword search failed: {e}")
            return []
    
    async def get_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific chunk by ID."""
        pool = await self._get_pool()

        sql = f"""
            SELECT
                id, content, section_title, source_file
            FROM {self.table_name}
            WHERE id = $1
        """

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(sql, chunk_id)

                if row:
                    return {
                        "id": str(row["id"]),
                        "content": row["content"],
                        "section_title": row["section_title"],
                        "source_file": row["source_file"],
                    }
                return None

        except Exception as e:
            logger.error(f"[EnterpriseRAG] get_by_id failed: {e}")
            return None
    
    async def close(self):
        """Close connections."""
        if self._pool:
            await self._pool.close()
        await self.embedder.close()


# =============================================================================
# SYNC FALLBACK (for non-async contexts)
# =============================================================================

class SyncEnterpriseRAGRetriever:
    """
    Synchronous wrapper for environments without asyncio.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.async_retriever = EnterpriseRAGRetriever(config)
    
    def search(self, **kwargs) -> List[Dict[str, Any]]:
        """Sync search wrapper."""
        return asyncio.run(self.async_retriever.search(**kwargs))


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_rag_retriever(config: Dict[str, Any], sync: bool = False):
    """
    Factory function to create RAG retriever.
    
    Args:
        config: Application config
        sync: Whether to return sync wrapper
        
    Returns:
        EnterpriseRAGRetriever or SyncEnterpriseRAGRetriever
    """
    if sync:
        return SyncEnterpriseRAGRetriever(config)
    return EnterpriseRAGRetriever(config)


# =============================================================================
# QUICK TEST
# =============================================================================

if __name__ == "__main__":
    import json
    
    print("Enterprise RAG Retriever Test")
    print("=" * 50)
    
    # Mock config
    test_config = {
        "database": {
            "host": os.getenv("AZURE_PG_HOST", "localhost"),
            "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
        },
        "features": {
            "enterprise_rag": {
                "table": "enterprise.documents",
                "top_k": 5,
                "threshold": 0.6,
            }
        }
    }
    
    async def test():
        rag = EnterpriseRAGRetriever(test_config)
        
        # Test search
        results = await rag.search(
            query="how to process credit memo",
        )
        
        print(f"\nFound {len(results)} results:")
        for r in results[:3]:
            print(f"  - [{r['score']:.2f}] {r['section_title'][:50]}...")
        
        await rag.close()
    
    if ASYNCPG_AVAILABLE:
        asyncio.run(test())
    else:
        print("[SKIP] asyncpg not available")
    
    print("\n[OK] Enterprise RAG module loaded")
