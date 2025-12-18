"""
Memory Backend Abstraction Layer - Phase 5

Provides pluggable backend support for memory storage:
- FileBackend: Current JSON file-based storage (default)
- PostgresBackend: Future SQL-based storage for enterprise scale

This abstraction layer enables seamless switching between storage backends
via config.yaml without changing retrieval code.

Usage:
    from memory_backend import get_backend
    from config import get_config

    backend = get_backend(get_config())
    nodes = backend.get_nodes(user_id="user123", tenant_id="driscoll")
    results, scores = backend.vector_search(embedding, user_id, tenant_id, top_k=10)

Configuration in config.yaml:
    memory:
      backend: file          # or "postgres"
      postgres:
        host: localhost
        port: 5432
        database: enterprise_bot
        user: postgres
        password: ${POSTGRES_PASSWORD}

Version: 1.0.0 (Phase 5)
"""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Tuple, Any, Dict

import numpy as np

from schemas import MemoryNode

logger = logging.getLogger(__name__)


# =============================================================================
# ABSTRACT BASE CLASS
# =============================================================================

class MemoryBackend(ABC):
    """
    Abstract base class for memory storage backends.

    Defines the interface that all backends must implement.
    This allows the retrieval system to work with any storage layer
    without knowing implementation details.
    """

    @abstractmethod
    def get_nodes(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[MemoryNode]:
        """
        Retrieve memory nodes filtered by auth scope.

        Args:
            user_id: Filter by user_id (personal SaaS mode)
            tenant_id: Filter by tenant_id (enterprise mode)
            limit: Maximum number of nodes to return
            offset: Number of nodes to skip (pagination)

        Returns:
            List of MemoryNode objects matching the filter criteria

        Security:
            MUST enforce auth scoping - never return nodes from
            different users/tenants. Fail secure if no auth provided.
        """
        pass

    @abstractmethod
    def vector_search(
        self,
        query_embedding: np.ndarray,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> Tuple[List[MemoryNode], List[float]]:
        """
        Perform vector similarity search with auth scoping.

        Args:
            query_embedding: Query vector (D,) for cosine similarity search
            user_id: Filter by user_id (personal SaaS mode)
            tenant_id: Filter by tenant_id (enterprise mode)
            top_k: Maximum number of results to return
            min_score: Minimum similarity score threshold

        Returns:
            Tuple of (nodes, scores) where scores are cosine similarities

        Security:
            MUST filter by auth scope BEFORE similarity computation
            to prevent cross-user/tenant information leakage.
        """
        pass

    @abstractmethod
    def insert_node(self, node: MemoryNode) -> None:
        """
        Insert a new memory node into storage.

        Args:
            node: MemoryNode object to store

        Note:
            Embeddings are typically stored separately in vector files.
            This method stores the node metadata and content.
        """
        pass

    @abstractmethod
    def get_embeddings(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> np.ndarray:
        """
        Retrieve embeddings for nodes matching auth scope.

        Args:
            user_id: Filter by user_id
            tenant_id: Filter by tenant_id

        Returns:
            NumPy array of shape (N, D) where N is number of nodes
            and D is embedding dimension (typically 1024 for BGE-M3)
        """
        pass

    @abstractmethod
    def get_cluster_info(self) -> Dict[int, List[int]]:
        """
        Get cluster assignments for all nodes.

        Returns:
            Dict mapping cluster_id to list of node indices
            Cluster ID of -1 indicates noise (unclustered nodes)
        """
        pass


# =============================================================================
# FILE BACKEND (Current Implementation)
# =============================================================================

class FileBackend(MemoryBackend):
    """
    File-based storage backend using JSON and NumPy files.

    This wraps the current file-based storage system:
    - data/corpus/nodes.json: Node metadata
    - data/vectors/nodes.npy: Node embeddings
    - data/indexes/clusters.json: Cluster assignments

    Maintains backward compatibility with existing data.
    """

    def __init__(self, data_dir: Path):
        """
        Initialize file backend.

        Args:
            data_dir: Root directory containing corpus/, vectors/, indexes/
        """
        self.data_dir = Path(data_dir)
        self.nodes_file = self.data_dir / "corpus" / "nodes.json"
        self.embeddings_file = self.data_dir / "vectors" / "nodes.npy"
        self.clusters_file = self.data_dir / "indexes" / "clusters.json"

        # Lazy load - only load when needed
        self._nodes: Optional[List[MemoryNode]] = None
        self._embeddings: Optional[np.ndarray] = None
        self._cluster_info: Optional[Dict[int, List[int]]] = None

        logger.info(f"FileBackend initialized with data_dir={data_dir}")

    def _load_nodes(self) -> List[MemoryNode]:
        """Load nodes from JSON file."""
        if self._nodes is not None:
            return self._nodes

        if not self.nodes_file.exists():
            logger.warning(f"Nodes file not found: {self.nodes_file}")
            self._nodes = []
            return self._nodes

        with open(self.nodes_file) as f:
            nodes_data = json.load(f)

        self._nodes = [MemoryNode.from_dict(d) for d in nodes_data]
        logger.info(f"Loaded {len(self._nodes)} nodes from {self.nodes_file}")
        return self._nodes

    def _load_embeddings(self) -> np.ndarray:
        """Load embeddings from NumPy file."""
        if self._embeddings is not None:
            return self._embeddings

        if not self.embeddings_file.exists():
            logger.warning(f"Embeddings file not found: {self.embeddings_file}")
            self._embeddings = np.array([])
            return self._embeddings

        self._embeddings = np.load(self.embeddings_file)
        logger.info(f"Loaded embeddings: {self._embeddings.shape}")
        return self._embeddings

    def _load_cluster_info(self) -> Dict[int, List[int]]:
        """Load cluster info from JSON file."""
        if self._cluster_info is not None:
            return self._cluster_info

        if not self.clusters_file.exists():
            logger.warning(f"Clusters file not found: {self.clusters_file}")
            self._cluster_info = {}
            return self._cluster_info

        with open(self.clusters_file) as f:
            cluster_data = json.load(f)

        # Convert string keys to int
        self._cluster_info = {int(k): v for k, v in cluster_data.items()}
        logger.info(f"Loaded {len(self._cluster_info)} clusters")
        return self._cluster_info

    def get_nodes(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[MemoryNode]:
        """
        Retrieve memory nodes filtered by auth scope.

        Implementation:
            - Loads nodes from JSON file
            - Filters by user_id/tenant_id if provided
            - Returns empty list if no auth context (fail secure)
        """
        nodes = self._load_nodes()

        # PHASE 5: AUTH SCOPING - FAIL SECURE
        # No auth context = no results
        if not user_id and not tenant_id:
            logger.warning("No auth context provided - returning empty results (fail secure)")
            return []

        # Filter by auth scope
        filtered = []
        for node in nodes:
            if tenant_id:
                # Enterprise mode: filter by tenant_id
                if getattr(node, 'tenant_id', None) == tenant_id:
                    filtered.append(node)
            elif user_id:
                # Personal mode: filter by user_id
                if getattr(node, 'user_id', None) == user_id:
                    filtered.append(node)

        # Apply pagination
        if offset > 0:
            filtered = filtered[offset:]
        if limit is not None:
            filtered = filtered[:limit]

        logger.info(f"get_nodes: {len(filtered)} nodes match scope (user_id={user_id}, tenant_id={tenant_id})")
        return filtered

    def vector_search(
        self,
        query_embedding: np.ndarray,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> Tuple[List[MemoryNode], List[float]]:
        """
        Perform vector similarity search with auth scoping.

        Implementation:
            1. Filter nodes by auth scope first (fail secure)
            2. Load embeddings for those nodes
            3. Compute cosine similarity
            4. Return top-k results above min_score
        """
        nodes = self._load_nodes()
        embeddings = self._load_embeddings()

        # PHASE 5: AUTH SCOPING - FAIL SECURE
        if not user_id and not tenant_id:
            logger.warning("No auth context provided - returning empty results (fail secure)")
            return [], []

        # Filter nodes by auth scope and build index mapping
        filtered_indices = []
        for idx, node in enumerate(nodes):
            if tenant_id:
                if getattr(node, 'tenant_id', None) == tenant_id:
                    filtered_indices.append(idx)
            elif user_id:
                if getattr(node, 'user_id', None) == user_id:
                    filtered_indices.append(idx)

        if not filtered_indices:
            logger.info(f"No nodes match scope (user_id={user_id}, tenant_id={tenant_id})")
            return [], []

        # Extract embeddings for filtered nodes
        filtered_embeddings = embeddings[filtered_indices]

        # Normalize for cosine similarity
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        emb_norms = np.linalg.norm(filtered_embeddings, axis=1, keepdims=True)
        filtered_normalized = filtered_embeddings / (emb_norms + 1e-8)

        # Compute similarities
        similarities = filtered_normalized @ query_norm

        # Get top-k indices above threshold
        sorted_indices = np.argsort(similarities)[::-1]

        results = []
        scores = []

        for local_idx in sorted_indices:
            if len(results) >= top_k:
                break

            sim = float(similarities[local_idx])
            if sim < min_score:
                break

            # Map back to original node index
            original_idx = filtered_indices[local_idx]
            results.append(nodes[original_idx])
            scores.append(sim)

        logger.info(f"vector_search: {len(results)} results (top_k={top_k}, min_score={min_score})")
        return results, scores

    def insert_node(self, node: MemoryNode) -> None:
        """
        Insert a new memory node into storage.

        Note: This is a simplified implementation that appends to the JSON file.
        For production, consider batch inserts and atomic writes.
        """
        # Ensure directory exists
        self.nodes_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing nodes
        if self.nodes_file.exists():
            with open(self.nodes_file) as f:
                nodes_data = json.load(f)
        else:
            nodes_data = []

        # Append new node
        nodes_data.append(node.to_dict())

        # Write back to file
        with open(self.nodes_file, 'w') as f:
            json.dump(nodes_data, f, indent=2, default=str)

        # Invalidate cache to force reload
        self._nodes = None

        logger.info(f"Inserted node {node.id} into {self.nodes_file}")

    def get_embeddings(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> np.ndarray:
        """
        Retrieve embeddings for nodes matching auth scope.

        Returns embeddings in the same order as get_nodes() for the same scope.
        """
        nodes = self._load_nodes()
        embeddings = self._load_embeddings()

        # No auth = empty result (fail secure)
        if not user_id and not tenant_id:
            return np.array([])

        # Filter indices by auth scope
        filtered_indices = []
        for idx, node in enumerate(nodes):
            if tenant_id:
                if getattr(node, 'tenant_id', None) == tenant_id:
                    filtered_indices.append(idx)
            elif user_id:
                if getattr(node, 'user_id', None) == user_id:
                    filtered_indices.append(idx)

        if not filtered_indices:
            return np.array([])

        return embeddings[filtered_indices]

    def get_cluster_info(self) -> Dict[int, List[int]]:
        """Get cluster assignments for all nodes."""
        return self._load_cluster_info()


# =============================================================================
# POSTGRES BACKEND (Future Implementation Stub)
# =============================================================================

class PostgresBackend(MemoryBackend):
    """
    PostgreSQL-based storage backend with pgvector for similarity search.

    Future implementation for Phase 5 that provides:
    - SQL-based filtering and queries
    - pgvector extension for efficient similarity search
    - Better scalability for large deployments
    - Transaction support and ACID guarantees

    Schema:
        memory_nodes:
            id TEXT PRIMARY KEY
            conversation_id TEXT
            user_id TEXT
            tenant_id TEXT
            human_content TEXT
            assistant_content TEXT
            source TEXT
            created_at TIMESTAMP
            cluster_id INTEGER
            metadata JSONB

        memory_embeddings:
            node_id TEXT REFERENCES memory_nodes(id)
            embedding VECTOR(1024)

        CREATE INDEX ON memory_nodes(user_id)
        CREATE INDEX ON memory_nodes(tenant_id)
        CREATE INDEX ON memory_embeddings USING ivfflat(embedding vector_cosine_ops)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PostgreSQL backend.

        Args:
            config: Database configuration with keys:
                - host: Database host
                - port: Database port
                - database: Database name
                - user: Database user
                - password: Database password
        """
        self.config = config
        self.connection = None

        # TODO: Initialize connection pool
        # import psycopg2
        # from psycopg2 import pool
        # self.pool = pool.ThreadedConnectionPool(...)

        logger.warning("PostgresBackend is a stub implementation - not yet functional")
        raise NotImplementedError("PostgresBackend will be implemented in Phase 5")

    def get_nodes(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[MemoryNode]:
        """
        SQL implementation:
            SELECT * FROM memory_nodes
            WHERE (user_id = %s OR tenant_id = %s)
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        raise NotImplementedError("PostgresBackend not yet implemented")

    def vector_search(
        self,
        query_embedding: np.ndarray,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> Tuple[List[MemoryNode], List[float]]:
        """
        SQL implementation with pgvector:
            SELECT n.*, 1 - (e.embedding <=> %s) AS similarity
            FROM memory_nodes n
            JOIN memory_embeddings e ON n.id = e.node_id
            WHERE (n.user_id = %s OR n.tenant_id = %s)
                AND (1 - (e.embedding <=> %s)) >= %s
            ORDER BY similarity DESC
            LIMIT %s
        """
        raise NotImplementedError("PostgresBackend not yet implemented")

    def insert_node(self, node: MemoryNode) -> None:
        """
        SQL implementation:
            INSERT INTO memory_nodes (id, conversation_id, ...)
            VALUES (%s, %s, ...)
        """
        raise NotImplementedError("PostgresBackend not yet implemented")

    def get_embeddings(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> np.ndarray:
        """
        SQL implementation:
            SELECT e.embedding
            FROM memory_embeddings e
            JOIN memory_nodes n ON e.node_id = n.id
            WHERE (n.user_id = %s OR n.tenant_id = %s)
        """
        raise NotImplementedError("PostgresBackend not yet implemented")

    def get_cluster_info(self) -> Dict[int, List[int]]:
        """
        SQL implementation:
            SELECT cluster_id, array_agg(id ORDER BY created_at)
            FROM memory_nodes
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id
        """
        raise NotImplementedError("PostgresBackend not yet implemented")


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_backend(config: Dict[str, Any]) -> MemoryBackend:
    """
    Factory function to create the appropriate backend based on config.

    Configuration in config.yaml:
        memory:
          backend: file          # or "postgres"
          postgres:               # Only needed if backend = postgres
            host: localhost
            port: 5432
            database: enterprise_bot
            user: postgres
            password: ${POSTGRES_PASSWORD}

        paths:
          data_dir: ./data        # Only needed if backend = file

    Args:
        config: Full configuration dict from config.yaml

    Returns:
        MemoryBackend instance (FileBackend or PostgresBackend)

    Raises:
        ValueError: If backend type is unknown
        NotImplementedError: If PostgresBackend is requested (not yet implemented)
    """
    memory_config = config.get("memory", {})
    backend_type = memory_config.get("backend", "file")

    if backend_type == "file":
        # Get data directory from paths config
        paths = config.get("paths", {})
        data_dir = Path(paths.get("data_dir", "./data"))

        # Resolve relative paths
        if not data_dir.is_absolute():
            # Assume relative to project root (where config.yaml lives)
            project_root = Path(__file__).parent
            data_dir = project_root / data_dir

        logger.info(f"Initializing FileBackend with data_dir={data_dir}")
        return FileBackend(data_dir.resolve())

    elif backend_type == "postgres":
        # Get postgres config
        pg_config = memory_config.get("postgres", {})

        if not pg_config:
            raise ValueError("PostgreSQL backend requested but no postgres config provided")

        logger.info("Initializing PostgresBackend")
        return PostgresBackend(pg_config)

    else:
        raise ValueError(f"Unknown backend type: {backend_type}. Must be 'file' or 'postgres'")


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import sys
    from config import load_config

    print("Memory Backend Abstraction Layer - Phase 5")
    print("=" * 60)

    # Load config
    config = load_config()
    print(f"\nConfiguration loaded")

    # Create backend
    try:
        backend = get_backend(config)
        print(f"Backend: {backend.__class__.__name__}")

        # Test get_nodes (should fail secure without auth)
        print("\n--- Test 1: get_nodes without auth (should return empty) ---")
        nodes = backend.get_nodes()
        print(f"Result: {len(nodes)} nodes (expected: 0)")

        # Test get_nodes with tenant_id
        print("\n--- Test 2: get_nodes with tenant_id ---")
        nodes = backend.get_nodes(tenant_id="driscoll")
        print(f"Result: {len(nodes)} nodes for tenant 'driscoll'")

        if nodes:
            print(f"\nFirst node:")
            print(f"  ID: {nodes[0].id}")
            print(f"  User ID: {nodes[0].user_id}")
            print(f"  Tenant ID: {nodes[0].tenant_id}")
            print(f"  Human: {nodes[0].human_content[:100]}...")

        # Test vector_search (requires embeddings)
        print("\n--- Test 3: vector_search ---")
        if nodes:
            embeddings = backend.get_embeddings(tenant_id="driscoll")
            if len(embeddings) > 0:
                # Use first embedding as query
                query_emb = embeddings[0]
                results, scores = backend.vector_search(
                    query_emb,
                    tenant_id="driscoll",
                    top_k=5
                )
                print(f"Result: {len(results)} results")
                for node, score in zip(results[:3], scores[:3]):
                    print(f"  - {node.id}: {score:.3f}")
            else:
                print("No embeddings available")

        print("\n" + "=" * 60)
        print("Backend tests completed successfully")

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
