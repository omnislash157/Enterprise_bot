"""
PostgreSQL Backend for CogTwin Memory System

Phase 5: Production-grade memory storage with pgvector for similarity search.
Implements async connection pool, scoped retrieval, and proper VECTOR type handling.

Requirements:
- asyncpg for async PostgreSQL operations
- pgvector for VECTOR type registration
- All queries MUST respect user_id/tenant_id scoping (FAIL SECURE)
- Connection string from AZURE_PG_CONNECTION_STRING environment variable

Usage:
    backend = PostgresBackend(connection_string)
    await backend.connect()
    nodes = await backend.get_nodes(user_id="user123")
    results = await backend.vector_search(embedding, user_id="user123", top_k=50)
"""

import asyncpg
import logging
import os
from typing import List, Optional, Dict, Any, Tuple
import numpy as np

# pgvector support for proper VECTOR type handling
try:
    from pgvector.asyncpg import register_vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    logging.warning("pgvector not installed - VECTOR type support disabled")

from schemas import MemoryNode, Source, IntentType, Complexity, EmotionalValence, Urgency, ConversationMode
from datetime import datetime

logger = logging.getLogger(__name__)


class PostgresBackend:
    """
    PostgreSQL backend with pgvector for memory storage and similarity search.

    All operations are scoped by user_id (personal) or tenant_id (enterprise).
    No scope provided = no results (FAIL SECURE).
    """

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize PostgreSQL backend.

        Args:
            connection_string: PostgreSQL connection string.
                              Defaults to AZURE_PG_CONNECTION_STRING env var.
        """
        self.connection_string = connection_string or os.getenv("AZURE_PG_CONNECTION_STRING")
        if not self.connection_string:
            raise ValueError(
                "No PostgreSQL connection string provided. "
                "Set AZURE_PG_CONNECTION_STRING environment variable or pass connection_string parameter."
            )

        self.pool: Optional[asyncpg.Pool] = None
        logger.info("PostgresBackend initialized (not connected)")

    async def connect(self) -> None:
        """
        Establish connection pool and register pgvector type.

        This must be called before any other operations.
        Creates connection pool with min_size=5, max_size=20.
        """
        if self.pool is not None:
            logger.warning("Connection pool already exists")
            return

        try:
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=5,
                max_size=20,
                command_timeout=60,
            )

            # Register pgvector extension for proper VECTOR type handling
            if PGVECTOR_AVAILABLE:
                async with self.pool.acquire() as conn:
                    await register_vector(conn)
                    logger.info("pgvector registered successfully")
            else:
                logger.warning("pgvector not available - VECTOR queries may fail")

            logger.info(f"PostgreSQL connection pool created (min=5, max=20)")

            # Verify connection
            async with self.pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info(f"Connected to: {version[:60]}...")

        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    async def close(self) -> None:
        """Close connection pool gracefully."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("PostgreSQL connection pool closed")

    async def get_nodes(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 10000,
    ) -> List[MemoryNode]:
        """
        Fetch memory nodes by user_id or tenant_id scope.

        FAIL SECURE: If neither user_id nor tenant_id provided, returns empty list.

        Args:
            user_id: Personal user ID UUID as string (for personal SaaS)
            tenant_id: Tenant ID UUID as string (for enterprise)
            limit: Max nodes to return (default 10000)

        Returns:
            List of MemoryNode objects matching scope
        """
        if not self.pool:
            raise RuntimeError("Not connected. Call connect() first.")

        # FAIL SECURE: No auth = no results
        if not user_id and not tenant_id:
            logger.warning("get_nodes called without user_id or tenant_id - returning empty list (FAIL SECURE)")
            return []

        try:
            async with self.pool.acquire() as conn:
                if tenant_id:
                    # Enterprise mode: filter by tenant_id
                    # Cast to UUID if needed (handles both UUID and string input)
                    query = """
                        SELECT id, user_id, tenant_id, conversation_id, sequence_index,
                               human_content, assistant_content, source, created_at,
                               intent_type, complexity, technical_depth, emotional_valence,
                               urgency, conversation_mode, action_required, has_code, has_error,
                               tags, cluster_id, cluster_label, cluster_confidence,
                               access_count, last_accessed
                        FROM memory_nodes
                        WHERE tenant_id::text = $1::text
                        ORDER BY created_at DESC
                        LIMIT $2
                    """
                    rows = await conn.fetch(query, tenant_id, limit)
                    logger.info(f"Fetched {len(rows)} nodes for tenant_id={tenant_id}")

                else:
                    # Personal mode: filter by user_id
                    # Cast to UUID if needed (handles both UUID and string input)
                    query = """
                        SELECT id, user_id, tenant_id, conversation_id, sequence_index,
                               human_content, assistant_content, source, created_at,
                               intent_type, complexity, technical_depth, emotional_valence,
                               urgency, conversation_mode, action_required, has_code, has_error,
                               tags, cluster_id, cluster_label, cluster_confidence,
                               access_count, last_accessed
                        FROM memory_nodes
                        WHERE user_id::text = $1::text
                        ORDER BY created_at DESC
                        LIMIT $2
                    """
                    rows = await conn.fetch(query, user_id, limit)
                    logger.info(f"Fetched {len(rows)} nodes for user_id={user_id}")

                # Convert rows to MemoryNode objects
                nodes = []
                for row in rows:
                    node = self._row_to_memory_node(row)
                    nodes.append(node)

                return nodes

        except Exception as e:
            logger.error(f"Error fetching nodes: {e}")
            raise

    async def vector_search(
        self,
        embedding: np.ndarray,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        top_k: int = 50,
        min_similarity: float = 0.5,
    ) -> Tuple[List[MemoryNode], List[float]]:
        """
        Similarity search using pgvector cosine distance.

        FAIL SECURE: If neither user_id nor tenant_id provided, returns empty results.

        Args:
            embedding: Query embedding vector (1024-dim for BGE-M3)
            user_id: Personal user ID UUID as string (for personal SaaS)
            tenant_id: Tenant ID UUID as string (for enterprise)
            top_k: Max results to return
            min_similarity: Minimum cosine similarity threshold (0-1)

        Returns:
            Tuple of (nodes, similarity_scores)
        """
        if not self.pool:
            raise RuntimeError("Not connected. Call connect() first.")

        # FAIL SECURE: No auth = no results
        if not user_id and not tenant_id:
            logger.warning("vector_search called without user_id or tenant_id - returning empty results (FAIL SECURE)")
            return [], []

        try:
            # Convert numpy array to list for pgvector
            if isinstance(embedding, np.ndarray):
                embedding_list = embedding.tolist()
            else:
                embedding_list = embedding

            async with self.pool.acquire() as conn:
                if tenant_id:
                    # Enterprise mode: filter by tenant_id
                    # Note: <=> is cosine distance operator (0 = identical, 2 = opposite)
                    # We convert to similarity: similarity = 1 - (distance / 2)
                    # Cast UUIDs to text for comparison (handles both UUID and string input)
                    query = """
                        SELECT id, user_id, tenant_id, conversation_id, sequence_index,
                               human_content, assistant_content, source, created_at,
                               intent_type, complexity, technical_depth, emotional_valence,
                               urgency, conversation_mode, action_required, has_code, has_error,
                               tags, cluster_id, cluster_label, cluster_confidence,
                               access_count, last_accessed,
                               1 - (embedding <=> $1::vector) / 2 as similarity
                        FROM memory_nodes
                        WHERE tenant_id::text = $2::text
                          AND 1 - (embedding <=> $1::vector) / 2 >= $3
                        ORDER BY embedding <=> $1::vector
                        LIMIT $4
                    """
                    rows = await conn.fetch(query, embedding_list, tenant_id, min_similarity, top_k)
                    logger.info(f"Vector search returned {len(rows)} results for tenant_id={tenant_id}")

                else:
                    # Personal mode: filter by user_id
                    # Cast UUIDs to text for comparison (handles both UUID and string input)
                    query = """
                        SELECT id, user_id, tenant_id, conversation_id, sequence_index,
                               human_content, assistant_content, source, created_at,
                               intent_type, complexity, technical_depth, emotional_valence,
                               urgency, conversation_mode, action_required, has_code, has_error,
                               tags, cluster_id, cluster_label, cluster_confidence,
                               access_count, last_accessed,
                               1 - (embedding <=> $1::vector) / 2 as similarity
                        FROM memory_nodes
                        WHERE user_id::text = $2::text
                          AND 1 - (embedding <=> $1::vector) / 2 >= $3
                        ORDER BY embedding <=> $1::vector
                        LIMIT $4
                    """
                    rows = await conn.fetch(query, embedding_list, user_id, min_similarity, top_k)
                    logger.info(f"Vector search returned {len(rows)} results for user_id={user_id}")

                # Convert rows to MemoryNode objects and extract similarity scores
                nodes = []
                scores = []
                for row in rows:
                    node = self._row_to_memory_node(row)
                    nodes.append(node)
                    scores.append(float(row['similarity']))

                return nodes, scores

        except Exception as e:
            logger.error(f"Error in vector_search: {e}")
            raise

    async def insert_node(self, node: MemoryNode) -> str:
        """
        Insert a new memory node.

        Args:
            node: MemoryNode to insert (must have user_id or tenant_id set)

        Returns:
            Inserted node ID (UUID as string)

        Raises:
            ValueError: If neither user_id nor tenant_id is set (FAIL SECURE)
        """
        if not self.pool:
            raise RuntimeError("Not connected. Call connect() first.")

        # FAIL SECURE: Require auth context for new memories
        if not node.user_id and not node.tenant_id:
            raise ValueError("Cannot insert node without user_id or tenant_id (FAIL SECURE)")

        try:
            # Convert embedding to list if it's numpy array
            embedding_list = None
            if node.embedding is not None:
                if isinstance(node.embedding, np.ndarray):
                    embedding_list = node.embedding.tolist()
                else:
                    embedding_list = node.embedding

            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO memory_nodes (
                        user_id, tenant_id, conversation_id, sequence_index,
                        human_content, assistant_content, source, created_at,
                        embedding, intent_type, complexity, technical_depth,
                        emotional_valence, urgency, conversation_mode,
                        action_required, has_code, has_error, tags,
                        cluster_id, cluster_label, cluster_confidence,
                        access_count, last_accessed
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18, $19,
                        $20, $21, $22, $23, $24
                    )
                    RETURNING id
                """

                node_id = await conn.fetchval(
                    query,
                    node.user_id,
                    node.tenant_id,
                    node.conversation_id,
                    node.sequence_index,
                    node.human_content,
                    node.assistant_content,
                    node.source.value if isinstance(node.source, Source) else node.source,
                    node.created_at,
                    embedding_list,
                    node.intent_type.value if isinstance(node.intent_type, IntentType) else node.intent_type,
                    node.complexity.value if isinstance(node.complexity, Complexity) else node.complexity,
                    node.technical_depth,
                    node.emotional_valence.value if isinstance(node.emotional_valence, EmotionalValence) else node.emotional_valence,
                    node.urgency.value if isinstance(node.urgency, Urgency) else node.urgency,
                    node.conversation_mode.value if isinstance(node.conversation_mode, ConversationMode) else node.conversation_mode,
                    node.action_required,
                    node.has_code,
                    node.has_error,
                    node.tags,  # JSONB field
                    node.cluster_id,
                    node.cluster_label,
                    node.cluster_confidence,
                    node.access_count,
                    node.last_accessed,
                )

                logger.info(f"Inserted node {node_id} for user_id={node.user_id}, tenant_id={node.tenant_id}")
                return str(node_id)

        except Exception as e:
            logger.error(f"Error inserting node: {e}")
            raise

    async def update_node_access(self, node_id: str) -> None:
        """
        Update access count and last_accessed timestamp for a node.

        Called by retrieval system to track memory usage.

        Args:
            node_id: Node ID to update
        """
        if not self.pool:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            async with self.pool.acquire() as conn:
                query = """
                    UPDATE memory_nodes
                    SET access_count = access_count + 1,
                        last_accessed = NOW()
                    WHERE id = $1
                """
                await conn.execute(query, node_id)

        except Exception as e:
            logger.warning(f"Error updating node access: {e}")
            # Non-critical error, don't raise

    def _row_to_memory_node(self, row: asyncpg.Record) -> MemoryNode:
        """
        Convert database row to MemoryNode object.

        Args:
            row: asyncpg Record from query

        Returns:
            MemoryNode object
        """
        # Handle datetime fields
        created_at = row['created_at']
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        last_accessed = row.get('last_accessed')
        if last_accessed and isinstance(last_accessed, str):
            last_accessed = datetime.fromisoformat(last_accessed)

        # Handle enum fields
        source = Source(row['source']) if row.get('source') else Source.ANTHROPIC
        intent_type = IntentType(row['intent_type']) if row.get('intent_type') else IntentType.STATEMENT
        complexity = Complexity(row['complexity']) if row.get('complexity') else Complexity.SIMPLE
        emotional_valence = EmotionalValence(row['emotional_valence']) if row.get('emotional_valence') else EmotionalValence.NEUTRAL
        urgency = Urgency(row['urgency']) if row.get('urgency') else Urgency.LOW
        conversation_mode = ConversationMode(row['conversation_mode']) if row.get('conversation_mode') else ConversationMode.CHAT

        return MemoryNode(
            id=str(row['id']),
            user_id=row.get('user_id'),
            tenant_id=row.get('tenant_id'),
            conversation_id=row['conversation_id'],
            sequence_index=row['sequence_index'],
            human_content=row['human_content'],
            assistant_content=row['assistant_content'],
            source=source,
            created_at=created_at,
            embedding=None,  # Don't load embedding into memory unless needed
            intent_type=intent_type,
            complexity=complexity,
            technical_depth=row.get('technical_depth', 0),
            emotional_valence=emotional_valence,
            urgency=urgency,
            conversation_mode=conversation_mode,
            action_required=row.get('action_required', False),
            has_code=row.get('has_code', False),
            has_error=row.get('has_error', False),
            tags=row.get('tags', {"domains": [], "topics": [], "entities": [], "processes": []}),
            cluster_id=row.get('cluster_id'),
            cluster_label=row.get('cluster_label'),
            cluster_confidence=row.get('cluster_confidence', 0.0),
            access_count=row.get('access_count', 0),
            last_accessed=last_accessed,
        )

    async def health_check(self) -> Dict[str, Any]:
        """
        Check backend health and return statistics.

        Returns:
            Dict with connection status, total nodes, etc.
        """
        if not self.pool:
            return {
                "status": "disconnected",
                "error": "Connection pool not initialized"
            }

        try:
            async with self.pool.acquire() as conn:
                # Check connection
                version = await conn.fetchval("SELECT version()")

                # Get node counts
                total_nodes = await conn.fetchval("SELECT COUNT(*) FROM memory_nodes")

                # Get memory by scope
                user_counts = await conn.fetch("""
                    SELECT user_id, COUNT(*) as count
                    FROM memory_nodes
                    WHERE user_id IS NOT NULL
                    GROUP BY user_id
                """)

                tenant_counts = await conn.fetch("""
                    SELECT tenant_id, COUNT(*) as count
                    FROM memory_nodes
                    WHERE tenant_id IS NOT NULL
                    GROUP BY tenant_id
                """)

                return {
                    "status": "connected",
                    "database_version": version[:60],
                    "pool_size": self.pool.get_size(),
                    "total_nodes": total_nodes,
                    "users": len(user_counts),
                    "tenants": len(tenant_counts),
                    "pgvector_available": PGVECTOR_AVAILABLE,
                }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# ═══════════════════════════════════════════════════════════════════════════
# CLI TEST
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    """Test PostgresBackend connection and basic operations."""
    from dotenv import load_dotenv
    load_dotenv()

    print("PostgresBackend Test")
    print("=" * 60)

    # Initialize backend
    try:
        backend = PostgresBackend()
        print(f"✓ Backend initialized")
    except ValueError as e:
        print(f"✗ Failed to initialize: {e}")
        print("\nSet AZURE_PG_CONNECTION_STRING environment variable:")
        print("  export AZURE_PG_CONNECTION_STRING='postgresql://user:pass@host:port/db'")
        return

    # Connect
    try:
        await backend.connect()
        print(f"✓ Connected to PostgreSQL")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return

    # Health check
    try:
        health = await backend.health_check()
        print(f"✓ Health check passed:")
        print(f"  - Status: {health['status']}")
        print(f"  - Total nodes: {health.get('total_nodes', 0)}")
        print(f"  - Pool size: {health.get('pool_size', 0)}")
        print(f"  - pgvector: {health.get('pgvector_available', False)}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")

    # Test get_nodes with no auth (should return empty - FAIL SECURE)
    try:
        nodes = await backend.get_nodes()
        if len(nodes) == 0:
            print(f"✓ FAIL SECURE: get_nodes() with no auth returned 0 nodes")
        else:
            print(f"✗ SECURITY VIOLATION: get_nodes() with no auth returned {len(nodes)} nodes")
    except Exception as e:
        print(f"✗ get_nodes test failed: {e}")

    # Close
    await backend.close()
    print(f"✓ Connection closed")

    print("\nTest complete!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
