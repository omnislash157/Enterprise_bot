"""
Memory Backend Abstraction Layer - Phase 5

Provides pluggable backend support for memory storage:
- FileBackend: Current JSON file-based storage (default)
- PostgresBackend: SQL-based storage with pgvector (see postgres_backend.py)

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
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Tuple, Any, Dict

import numpy as np

from schemas import MemoryNode

# Import real PostgresBackend from postgres_backend.py
try:
    from postgres_backend import PostgresBackend as AsyncPostgresBackend
    POSTGRES_BACKEND_AVAILABLE = True
except ImportError:
    POSTGRES_BACKEND_AVAILABLE = False

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
        # NOTE: AsyncPostgresBackend requires await backend.connect() before use
        # and all operations are async. CogTwin integration needs async handling.

        if not POSTGRES_BACKEND_AVAILABLE:
            raise ImportError(
                "PostgresBackend requested but postgres_backend.py not available. "
                "Ensure asyncpg and pgvector are installed."
            )

        # Build connection string from config OR use env var
        pg_config = memory_config.get("postgres", {})

        # Check for direct connection string first
        conn_string = pg_config.get("connection_string") or os.getenv("AZURE_PG_CONNECTION_STRING")

        if not conn_string and pg_config:
            # Build from components
            host = pg_config.get("host", "localhost")
            port = pg_config.get("port", 5432)
            database = pg_config.get("database", "cogtwin")
            user = pg_config.get("user", "postgres")
            password = pg_config.get("password", "")

            # Handle env var substitution in password
            if password.startswith("${") and password.endswith("}"):
                env_var = password[2:-1]
                password = os.getenv(env_var, "")

            conn_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"

        if not conn_string:
            raise ValueError(
                "PostgreSQL backend requested but no connection info provided. "
                "Set memory.postgres config or AZURE_PG_CONNECTION_STRING env var."
            )

        logger.info("Initializing AsyncPostgresBackend")
        return AsyncPostgresBackend(conn_string)

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
