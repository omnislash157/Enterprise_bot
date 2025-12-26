"""
Redis Cache Client - Embedding caching

Cache Keys:
- emb:{query_hash}         -> embedding vector (24h TTL)

Note: RAG caching removed - using context stuffing instead.
The RAG cache methods are commented out but preserved for reference.

Usage:
    from .cache import get_cache
    cache = get_cache()

    # Embedding cache
    embedding = await cache.get_embedding(query)
    if not embedding:
        embedding = await generate_embedding(query)
        await cache.set_embedding(query, embedding)

Version: 1.0.0
"""

import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Global cache instance
_cache_instance = None


class RedisCache:
    """Async Redis cache for embeddings."""

    # TTLs
    EMBEDDING_TTL = 86400  # 24 hours
    # RAG_TTL = 300        # RAG removed - using context stuffing

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._client = None
        self._connected = False

    async def connect(self):
        """Initialize Redis connection."""
        if self._connected:
            return

        try:
            import redis.asyncio as redis
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # We handle encoding ourselves
            )
            # Test connection
            await self._client.ping()
            self._connected = True
            logger.info("[Cache] Redis connected")
        except Exception as e:
            logger.warning(f"[Cache] Redis connection failed: {e}. Running without cache.")
            self._client = None
            self._connected = False

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._connected = False

    def _hash_query(self, query: str) -> str:
        """Generate consistent hash for query."""
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]

    # =========================================================================
    # EMBEDDING CACHE
    # =========================================================================

    async def get_embedding(self, query: str) -> Optional[List[float]]:
        """Get cached embedding for query."""
        if not self._client:
            return None

        try:
            key = f"emb:{self._hash_query(query)}"
            data = await self._client.get(key)
            if data:
                logger.debug(f"[Cache] Embedding HIT: {key}")
                return json.loads(data)
            logger.debug(f"[Cache] Embedding MISS: {key}")
            return None
        except Exception as e:
            logger.warning(f"[Cache] Embedding get failed: {e}")
            return None

    async def set_embedding(self, query: str, embedding: List[float]) -> bool:
        """Cache embedding for query."""
        if not self._client:
            return False

        try:
            key = f"emb:{self._hash_query(query)}"
            await self._client.setex(
                key,
                self.EMBEDDING_TTL,
                json.dumps(embedding)
            )
            logger.debug(f"[Cache] Embedding SET: {key}")
            return True
        except Exception as e:
            logger.warning(f"[Cache] Embedding set failed: {e}")
            return False

    # =========================================================================
    # RAG RESULTS CACHE - REMOVED (using context stuffing instead)
    # =========================================================================
    # async def get_rag_results(self, query: str, department: str) -> Optional[List[Dict]]:
    #     """Get cached RAG results for query + department."""
    #     if not self._client:
    #         return None
    #
    #     try:
    #         key = f"rag:{self._hash_query(query)}:{department}"
    #         data = await self._client.get(key)
    #         if data:
    #             logger.info(f"[Cache] RAG HIT: {key}")
    #             return json.loads(data)
    #         logger.debug(f"[Cache] RAG MISS: {key}")
    #         return None
    #     except Exception as e:
    #         logger.warning(f"[Cache] RAG get failed: {e}")
    #         return None
    #
    # async def set_rag_results(self, query: str, department: str, results: List[Dict]) -> bool:
    #     """Cache RAG results for query + department."""
    #     if not self._client:
    #         return False
    #
    #     try:
    #         key = f"rag:{self._hash_query(query)}:{department}"
    #         await self._client.setex(
    #             key,
    #             self.RAG_TTL,
    #             json.dumps(results)
    #         )
    #         logger.info(f"[Cache] RAG SET: {key} ({len(results)} chunks)")
    #         return True
    #     except Exception as e:
    #         logger.warning(f"[Cache] RAG set failed: {e}")
    #         return False

    # =========================================================================
    # STATS
    # =========================================================================

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._client:
            return {"connected": False}

        try:
            info = await self._client.info("stats")
            return {
                "connected": True,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}


class NoOpCache:
    """Fallback when Redis is unavailable."""

    async def connect(self): pass
    async def close(self): pass
    async def get_embedding(self, query: str) -> None: return None
    async def set_embedding(self, query: str, embedding: List[float]) -> bool: return False
    # RAG cache methods removed - using context stuffing
    # async def get_rag_results(self, query: str, department: str) -> None: return None
    # async def set_rag_results(self, query: str, department: str, results: List[Dict]) -> bool: return False
    async def get_stats(self) -> Dict: return {"connected": False, "type": "noop"}


def get_cache() -> RedisCache:
    """Get or create cache singleton."""
    global _cache_instance

    if _cache_instance is None:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            _cache_instance = RedisCache(redis_url)
        else:
            logger.warning("[Cache] REDIS_URL not set, using NoOpCache")
            _cache_instance = NoOpCache()

    return _cache_instance


async def init_cache():
    """Initialize cache connection (call on startup)."""
    cache = get_cache()
    await cache.connect()
    return cache
