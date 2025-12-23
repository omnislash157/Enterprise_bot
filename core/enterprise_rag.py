"""
Enterprise RAG Retriever - Process Manual Search

Retrieves relevant chunks from documents table using:
1. BGE-M3 dense vectors (semantic similarity)
2. Keyword matching (fallback when embeddings are NULL)

This is the manual RAG that fires for procedural/lookup/complaint queries.
Python fires this tool, not Grok.

NOTE: Single-tenant MVP - no tenant_id/department filtering yet.

Usage:
    from .enterprise_rag import EnterpriseRAGRetriever

    rag = EnterpriseRAGRetriever(config)
    chunks = await rag.search(
        query="how do I process a credit memo",
        threshold=0.6,  # Returns ALL chunks above this score
    )

Version: 1.0.0
"""

import asyncio
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

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

    NOTE: Single-tenant MVP - no tenant_id/department filtering yet.
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
        
        # Embedding client
        self.embedder = EmbeddingClient(config)
        
        # Connection pool (lazy init)
        self._pool = None
        
        logger.info(f"[EnterpriseRAG] Initialized with table: {self.table_name}")
    
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
        threshold: float = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant manual chunks.

        Returns ALL chunks above threshold - no arbitrary cap.
        NOTE: No department filtering - all manuals are company-wide knowledge.

        Args:
            query: User's query
            threshold: Minimum similarity threshold

        Returns:
            List of chunk dicts with content, metadata, and score
        """
        threshold = threshold or self.default_threshold

        start_time = datetime.now()

        # Try vector search first
        query_embedding = await self.embedder.embed(query)

        if query_embedding:
            results = await self._vector_search(
                query_embedding=query_embedding,
                threshold=threshold,
            )
            search_type = "vector"
        else:
            # Fallback to keyword search
            results = await self._keyword_search(
                query=query,
            )
            search_type = "keyword"
        
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"[EnterpriseRAG] {search_type} search returned {len(results)} results in {elapsed_ms:.0f}ms")
        
        return results
    
    async def _vector_search(
        self,
        query_embedding: List[float],
        threshold: float,
    ) -> List[Dict[str, Any]]:
        """
        Vector similarity search using pgvector.

        Uses cosine distance: 1 - (embedding <=> query) as similarity.
        Returns ALL results above threshold - no arbitrary cap.
        NOTE: No department filtering - all manuals are company-wide knowledge.
        """
        pool = await self._get_pool()

        # Convert embedding to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        query = f"""
            SELECT
                id,
                content,
                section_title,
                source_file,
                1 - (embedding <=> $1::vector) as score
            FROM {self.table_name}
            WHERE
                embedding IS NOT NULL
                AND 1 - (embedding <=> $1::vector) >= $2
            ORDER BY embedding <=> $1::vector
        """

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    query,
                    embedding_str,
                    threshold,
                )

                return [
                    {
                        "id": str(row["id"]),
                        "content": row["content"],
                        "section_title": row["section_title"],
                        "source_file": row["source_file"],
                        "score": float(row["score"]),
                        "search_type": "vector",
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"[EnterpriseRAG] Vector search failed: {e}")
            # Fall back to keyword search
            return await self._keyword_search(
                query=" ".join(str(x) for x in query_embedding[:10]),  # Dummy
            )
    
    async def _keyword_search(
        self,
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Keyword search fallback using PostgreSQL full-text search.

        Uses ts_rank for scoring. Returns all matches (no arbitrary limit).
        NOTE: No department filtering - all manuals are company-wide knowledge.
        """
        pool = await self._get_pool()

        # Clean query for tsquery
        clean_query = " & ".join(
            word.strip() for word in query.split()
            if len(word.strip()) > 2
        )

        if not clean_query:
            clean_query = query.replace(" ", " & ")

        sql = f"""
            SELECT
                id,
                content,
                section_title,
                source_file,
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

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(sql, query)

                return [
                    {
                        "id": str(row["id"]),
                        "content": row["content"],
                        "section_title": row["section_title"],
                        "source_file": row["source_file"],
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
