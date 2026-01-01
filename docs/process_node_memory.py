"""
process_node_memory.py - Cluster-Routed Text Rehydration

The missing piece: HDBSCAN clusters are INDEX STRUCTURES, not content.
They tell us WHERE to look, but embeddings lose the WHY.

This module:
1. Uses cluster centroids as routing signals
2. Looks up conversation UUIDs from cluster membership
3. REHYDRATES to actual text (not embeddings)
4. Expands context +/- N tokens around the match

Lane 6 retrieval - "here's the actual workflow with surrounding context"

Usage:
    pnm = ProcessNodeMemory.load("./data")
    results = await pnm.search("async error handling", top_clusters=3)
    for r in results:
        print(r.full_context)  # Actual text Grok can reason over

Version: 1.0.0 (cog_twin)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import hashlib

import numpy as np

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Data Structures
# -----------------------------------------------------------------------------

@dataclass
class PNMResult:
    """
    Process Node Memory result - rehydrated text, not vectors.
    
    This is what the embedding MEANT but couldn't express.
    """
    # Identity
    conversation_id: str
    sequence_index: int
    node_id: str
    
    # Cluster routing info
    cluster_id: int
    cluster_label: str
    cluster_distance: float  # How close query was to this cluster
    
    # THE ACTUAL CONTENT - this is what was missing
    human_content: str
    assistant_content: str
    
    # Expanded context (the +/- 200 tokens)
    context_before: str  # Previous exchanges in same conversation
    context_after: str   # Following exchanges
    
    # Metadata
    timestamp: Optional[datetime] = None
    source: str = "unknown"
    
    @property
    def full_context(self) -> str:
        """
        Rehydrated text blob the model can actually reason over.
        
        Format:
            [context before]
            ---
            Human: [the matched query]
            Assistant: [the matched response]
            ---
            [context after]
        """
        parts = []
        
        if self.context_before:
            parts.append(self.context_before.strip())
            parts.append("")
        
        parts.append("--- MATCHED NODE ---")
        parts.append(f"Human: {self.human_content}")
        parts.append(f"Assistant: {self.assistant_content}")
        parts.append("--- END NODE ---")
        
        if self.context_after:
            parts.append("")
            parts.append(self.context_after.strip())
        
        return "\n".join(parts)
    
    @property
    def brief(self) -> str:
        """Short summary for debugging/logging."""
        human_preview = self.human_content[:60] + "..." if len(self.human_content) > 60 else self.human_content
        return f"[{self.cluster_label}] {human_preview}"


@dataclass
class PNMSearchResult:
    """Aggregated results from a PNM search."""
    query: str
    results: List[PNMResult]
    clusters_searched: List[Tuple[int, str, float]]  # (id, label, distance)
    search_time_ms: float
    
    def format_for_context(self, max_results: int = 5) -> str:
        """
        Format for injection into LLM context.
        
        Groups by cluster for coherent presentation.
        """
        if not self.results:
            return f"PNM SEARCH: '{self.query}' - No process memories found."
        
        lines = [
            "=" * 60,
            "PROCESS NODE MEMORY (rehydrated from clusters)",
            "=" * 60,
            f"Query: {self.query}",
            f"Clusters searched: {len(self.clusters_searched)}",
            f"Results: {len(self.results)} ({self.search_time_ms:.1f}ms)",
            "",
        ]
        
        # Group by cluster
        by_cluster: Dict[int, List[PNMResult]] = {}
        for r in self.results[:max_results]:
            if r.cluster_id not in by_cluster:
                by_cluster[r.cluster_id] = []
            by_cluster[r.cluster_id].append(r)
        
        for cluster_id, cluster_results in by_cluster.items():
            label = cluster_results[0].cluster_label
            dist = cluster_results[0].cluster_distance
            
            lines.append(f"### Cluster: {label} (similarity: {dist:.3f})")
            lines.append("")
            
            for r in cluster_results:
                ts = r.timestamp.strftime("%Y-%m-%d %H:%M") if r.timestamp else "unknown"
                lines.append(f"[{ts}] conv:{r.conversation_id[:8]}... seq:{r.sequence_index}")
                lines.append(r.full_context)
                lines.append("")
            
            lines.append("-" * 40)
        
        return "\n".join(lines)


# -----------------------------------------------------------------------------
# Cluster Index - The Routing Structure
# -----------------------------------------------------------------------------

@dataclass
class ClusterIndex:
    """
    Maps cluster IDs to conversation references.
    
    Built at clustering time, used at retrieval time.
    This is the bridge between geometry and content.
    """
    # cluster_id -> [(conversation_id, sequence_index, node_id), ...]
    cluster_to_refs: Dict[int, List[Tuple[str, int, str]]]
    
    # cluster_id -> centroid embedding
    centroids: Dict[int, np.ndarray]
    
    # cluster_id -> human-readable label
    labels: Dict[int, str]
    
    # Metadata
    total_nodes: int
    noise_count: int  # Nodes in cluster -1
    created_at: datetime = field(default_factory=datetime.now)
    
    def save(self, path: Path):
        """Serialize to disk."""
        data = {
            "cluster_to_refs": {
                str(k): v for k, v in self.cluster_to_refs.items()
            },
            "centroids": {
                str(k): v.tolist() for k, v in self.centroids.items()
            },
            "labels": {str(k): v for k, v in self.labels.items()},
            "total_nodes": self.total_nodes,
            "noise_count": self.noise_count,
            "created_at": self.created_at.isoformat(),
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved cluster index: {len(self.cluster_to_refs)} clusters, {self.total_nodes} nodes")
    
    @classmethod
    def load(cls, path: Path) -> "ClusterIndex":
        """Load from disk."""
        with open(path) as f:
            data = json.load(f)
        
        return cls(
            cluster_to_refs={
                int(k): [tuple(ref) for ref in v] 
                for k, v in data["cluster_to_refs"].items()
            },
            centroids={
                int(k): np.array(v, dtype=np.float32)
                for k, v in data["centroids"].items()
            },
            labels={int(k): v for k, v in data["labels"].items()},
            total_nodes=data["total_nodes"],
            noise_count=data["noise_count"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


# -----------------------------------------------------------------------------
# Conversation Store - The Content
# -----------------------------------------------------------------------------

class ConversationStore:
    """
    Loads and caches conversations for rehydration.
    
    Lazy loading - only fetches conversations when needed.
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        # Find conversation files
        self.conversations_dir = self.data_dir / "parsed"
        if not self.conversations_dir.exists():
            # Try alternate location
            self.conversations_dir = self.data_dir / "conversations"
        
        # Build index of available conversations
        self.available: Dict[str, Path] = {}
        self._index_conversations()
    
    def _index_conversations(self):
        """Build index of conversation_id -> file path."""
        if not self.conversations_dir.exists():
            logger.warning(f"Conversations directory not found: {self.conversations_dir}")
            return
        
        # Check for single JSON with all conversations
        all_convos_path = self.conversations_dir / "all_conversations.json"
        if all_convos_path.exists():
            self._load_all_conversations(all_convos_path)
            return
        
        # Otherwise, look for individual files
        for f in self.conversations_dir.glob("*.json"):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    if isinstance(data, dict) and "uuid" in data:
                        self.available[data["uuid"]] = f
                    elif isinstance(data, list):
                        # File contains multiple conversations
                        for conv in data:
                            if "uuid" in conv:
                                self.available[conv["uuid"]] = f
            except Exception as e:
                logger.debug(f"Skipping {f}: {e}")
        
        logger.info(f"Indexed {len(self.available)} conversations")
    
    def _load_all_conversations(self, path: Path):
        """Load from consolidated conversations file."""
        try:
            with open(path) as f:
                all_convos = json.load(f)
            
            for conv in all_convos:
                if "uuid" in conv:
                    self.cache[conv["uuid"]] = conv
                    self.available[conv["uuid"]] = path
            
            logger.info(f"Loaded {len(self.cache)} conversations from {path}")
        except Exception as e:
            logger.error(f"Failed to load conversations: {e}")
    
    def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation by ID, loading from disk if needed."""
        # Check cache first
        if conversation_id in self.cache:
            return self.cache[conversation_id]
        
        # Load from disk
        if conversation_id not in self.available:
            logger.warning(f"Conversation not found: {conversation_id}")
            return None
        
        try:
            path = self.available[conversation_id]
            with open(path) as f:
                data = json.load(f)
            
            # Handle single vs multi-conversation files
            if isinstance(data, dict) and "uuid" in data:
                self.cache[conversation_id] = data
                return data
            elif isinstance(data, list):
                for conv in data:
                    if conv.get("uuid") == conversation_id:
                        self.cache[conversation_id] = conv
                        return conv
            
            return None
        
        except Exception as e:
            logger.error(f"Failed to load conversation {conversation_id}: {e}")
            return None
    
    def get_node_content(
        self, 
        conversation_id: str, 
        sequence_index: int
    ) -> Optional[Tuple[str, str, datetime]]:
        """
        Get the human/assistant content for a specific node.
        
        Returns: (human_content, assistant_content, timestamp) or None
        """
        conv = self.get(conversation_id)
        if not conv:
            return None
        
        messages = conv.get("chat_messages", conv.get("messages", []))
        
        # Find the exchange at this sequence index
        # Messages alternate human/assistant, so we need to pair them
        exchanges = []
        current_human = None
        
        for msg in messages:
            sender = msg.get("sender", msg.get("role", ""))
            content = msg.get("text", msg.get("content", ""))
            
            # Handle content that might be a list of blocks
            if isinstance(content, list):
                content = " ".join(
                    block.get("text", "") 
                    for block in content 
                    if isinstance(block, dict)
                )
            
            if sender in ("human", "user"):
                current_human = {
                    "content": content,
                    "timestamp": msg.get("created_at", msg.get("timestamp")),
                }
            elif sender in ("assistant", "claude") and current_human:
                exchanges.append({
                    "human": current_human["content"],
                    "assistant": content,
                    "timestamp": current_human.get("timestamp"),
                })
                current_human = None
        
        if sequence_index >= len(exchanges):
            logger.warning(f"Sequence index {sequence_index} out of range for {conversation_id}")
            return None
        
        ex = exchanges[sequence_index]
        
        # Parse timestamp
        ts = None
        if ex.get("timestamp"):
            try:
                ts_str = ex["timestamp"]
                if isinstance(ts_str, str):
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except:
                pass
        
        return (ex["human"], ex["assistant"], ts)
    
    def get_context_window(
        self,
        conversation_id: str,
        sequence_index: int,
        tokens_before: int = 200,
        tokens_after: int = 200,
    ) -> Tuple[str, str]:
        """
        Get surrounding context for a node.
        
        Returns: (context_before, context_after)
        
        Approximates tokens as words * 1.3 for simplicity.
        """
        conv = self.get(conversation_id)
        if not conv:
            return ("", "")
        
        messages = conv.get("chat_messages", conv.get("messages", []))
        
        # Build all exchanges
        exchanges = []
        current_human = None
        
        for msg in messages:
            sender = msg.get("sender", msg.get("role", ""))
            content = msg.get("text", msg.get("content", ""))
            
            if isinstance(content, list):
                content = " ".join(
                    block.get("text", "") 
                    for block in content 
                    if isinstance(block, dict)
                )
            
            if sender in ("human", "user"):
                current_human = content
            elif sender in ("assistant", "claude") and current_human:
                exchanges.append({
                    "human": current_human,
                    "assistant": content,
                })
                current_human = None
        
        # Word to token approximation
        words_before = int(tokens_before / 1.3)
        words_after = int(tokens_after / 1.3)
        
        # Build context before
        context_before_parts = []
        word_count = 0
        
        for i in range(sequence_index - 1, -1, -1):
            ex = exchanges[i]
            text = f"Human: {ex['human']}\nAssistant: {ex['assistant']}"
            words = len(text.split())
            
            if word_count + words > words_before:
                # Truncate this exchange
                remaining = words_before - word_count
                truncated = " ".join(text.split()[-remaining:])
                context_before_parts.insert(0, "..." + truncated)
                break
            
            context_before_parts.insert(0, text)
            word_count += words
        
        # Build context after
        context_after_parts = []
        word_count = 0
        
        for i in range(sequence_index + 1, len(exchanges)):
            ex = exchanges[i]
            text = f"Human: {ex['human']}\nAssistant: {ex['assistant']}"
            words = len(text.split())
            
            if word_count + words > words_after:
                remaining = words_after - word_count
                truncated = " ".join(text.split()[:remaining])
                context_after_parts.append(truncated + "...")
                break
            
            context_after_parts.append(text)
            word_count += words
        
        return (
            "\n\n".join(context_before_parts),
            "\n\n".join(context_after_parts),
        )


# -----------------------------------------------------------------------------
# Main Engine
# -----------------------------------------------------------------------------

class ProcessNodeMemory:
    """
    Cluster-routed text rehydration engine.
    
    The key insight: embeddings are ROUTING structures, not content.
    We use cluster geometry to find WHERE to look, then rehydrate
    actual text for the model to reason over.
    
    This is Lane 6 retrieval.
    """
    
    def __init__(
        self,
        cluster_index: ClusterIndex,
        conversation_store: ConversationStore,
        embedder: Any,  # AsyncEmbedder
    ):
        self.cluster_index = cluster_index
        self.conversations = conversation_store
        self.embedder = embedder
        
        # Pre-normalize centroids for fast cosine similarity
        self.centroid_matrix: Optional[np.ndarray] = None
        self.centroid_ids: List[int] = []
        self._build_centroid_matrix()
        
        logger.info(
            f"ProcessNodeMemory initialized: "
            f"{len(self.cluster_index.cluster_to_refs)} clusters, "
            f"{self.cluster_index.total_nodes} nodes"
        )
    
    def _build_centroid_matrix(self):
        """Build matrix of normalized centroids for batch similarity."""
        if not self.cluster_index.centroids:
            return
        
        self.centroid_ids = sorted(self.cluster_index.centroids.keys())
        
        # Stack into matrix
        centroids = [self.cluster_index.centroids[cid] for cid in self.centroid_ids]
        self.centroid_matrix = np.vstack(centroids).astype(np.float32)
        
        # Normalize
        norms = np.linalg.norm(self.centroid_matrix, axis=1, keepdims=True)
        self.centroid_matrix = self.centroid_matrix / (norms + 1e-8)
    
    async def search(
        self,
        query: str,
        top_clusters: int = 3,
        nodes_per_cluster: int = 2,
        context_tokens: int = 200,
        min_cluster_similarity: float = 0.3,
    ) -> PNMSearchResult:
        """
        Search process memory with text rehydration.
        
        1. Embed query
        2. Find nearest cluster centroids (geometric routing)
        3. For each cluster: grab representative node refs
        4. Rehydrate: load actual conversation text
        5. Expand context: +/- N tokens
        6. Return TEXT, not math
        
        Args:
            query: Search query
            top_clusters: Number of clusters to search
            nodes_per_cluster: Nodes to retrieve per cluster
            context_tokens: Tokens of context to include on each side
            min_cluster_similarity: Minimum centroid similarity to consider
        
        Returns:
            PNMSearchResult with rehydrated text
        """
        import time
        start = time.time()
        
        # 1. Embed query
        query_embedding = await self.embedder.embed_single(query)
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        
        # 2. Find nearest clusters
        nearest_clusters = self._find_nearest_clusters(
            query_norm, 
            top_k=top_clusters,
            min_similarity=min_cluster_similarity,
        )
        
        if not nearest_clusters:
            elapsed = (time.time() - start) * 1000
            return PNMSearchResult(
                query=query,
                results=[],
                clusters_searched=[],
                search_time_ms=elapsed,
            )
        
        # 3. Get node refs from each cluster
        results = []
        clusters_searched = []
        
        for cluster_id, similarity in nearest_clusters:
            label = self.cluster_index.labels.get(cluster_id, f"cluster_{cluster_id}")
            clusters_searched.append((cluster_id, label, similarity))
            
            refs = self.cluster_index.cluster_to_refs.get(cluster_id, [])
            if not refs:
                continue
            
            # Sample nodes - for now just take first N
            # TODO: Could rank by proximity to query within cluster
            sampled = refs[:nodes_per_cluster]
            
            # 4. Rehydrate each node
            for conv_id, seq_idx, node_id in sampled:
                result = self._rehydrate_node(
                    conv_id, 
                    seq_idx, 
                    node_id,
                    cluster_id,
                    label,
                    similarity,
                    context_tokens,
                )
                if result:
                    results.append(result)
        
        elapsed = (time.time() - start) * 1000
        
        return PNMSearchResult(
            query=query,
            results=results,
            clusters_searched=clusters_searched,
            search_time_ms=elapsed,
        )
    
    def _find_nearest_clusters(
        self,
        query_norm: np.ndarray,
        top_k: int,
        min_similarity: float,
    ) -> List[Tuple[int, float]]:
        """Find clusters with centroids most similar to query."""
        if self.centroid_matrix is None:
            return []
        
        # Compute similarities
        similarities = self.centroid_matrix @ query_norm
        
        # Get top-k above threshold
        sorted_indices = np.argsort(similarities)[::-1]
        
        results = []
        for idx in sorted_indices[:top_k]:
            sim = float(similarities[idx])
            if sim < min_similarity:
                break
            results.append((self.centroid_ids[idx], sim))
        
        return results
    
    def _rehydrate_node(
        self,
        conversation_id: str,
        sequence_index: int,
        node_id: str,
        cluster_id: int,
        cluster_label: str,
        cluster_distance: float,
        context_tokens: int,
    ) -> Optional[PNMResult]:
        """Load actual text for a node reference."""
        # Get node content
        content = self.conversations.get_node_content(conversation_id, sequence_index)
        if not content:
            return None
        
        human_content, assistant_content, timestamp = content
        
        # Get surrounding context
        context_before, context_after = self.conversations.get_context_window(
            conversation_id,
            sequence_index,
            tokens_before=context_tokens,
            tokens_after=context_tokens,
        )
        
        return PNMResult(
            conversation_id=conversation_id,
            sequence_index=sequence_index,
            node_id=node_id,
            cluster_id=cluster_id,
            cluster_label=cluster_label,
            cluster_distance=cluster_distance,
            human_content=human_content,
            assistant_content=assistant_content,
            context_before=context_before,
            context_after=context_after,
            timestamp=timestamp,
        )
    
    @classmethod
    def load(cls, data_dir: Path, embedder: Any) -> "ProcessNodeMemory":
        """
        Load ProcessNodeMemory from data directory.
        
        Expects:
            - data_dir/indexes/cluster_index.json (built by build_cluster_index)
            - data_dir/parsed/ or data_dir/conversations/ for conversation data
        """
        data_dir = Path(data_dir)
        
        # Load cluster index
        index_path = data_dir / "indexes" / "cluster_index.json"
        if not index_path.exists():
            raise FileNotFoundError(
                f"Cluster index not found at {index_path}. "
                f"Run build_cluster_index() first."
            )
        
        cluster_index = ClusterIndex.load(index_path)
        
        # Initialize conversation store
        conversation_store = ConversationStore(data_dir)
        
        return cls(cluster_index, conversation_store, embedder)


# -----------------------------------------------------------------------------
# Index Builder - Run after HDBSCAN clustering
# -----------------------------------------------------------------------------

def build_cluster_index(
    data_dir: Path,
    nodes: List[Any],  # MemoryNode objects
    cluster_labels: np.ndarray,
    embeddings: np.ndarray,
    cluster_names: Optional[Dict[int, str]] = None,
) -> ClusterIndex:
    """
    Build the cluster index from HDBSCAN results.
    
    Call this after running HDBSCAN clustering to create the
    routing structure for PNM retrieval.
    
    Args:
        data_dir: Where to save the index
        nodes: List of MemoryNode objects
        cluster_labels: HDBSCAN cluster assignments (N,)
        embeddings: Node embeddings (N x D)
        cluster_names: Optional human-readable cluster names
    
    Returns:
        ClusterIndex ready for use
    """
    data_dir = Path(data_dir)
    
    # Build cluster -> refs mapping
    cluster_to_refs: Dict[int, List[Tuple[str, int, str]]] = {}
    
    for i, node in enumerate(nodes):
        cluster_id = int(cluster_labels[i])
        
        if cluster_id not in cluster_to_refs:
            cluster_to_refs[cluster_id] = []
        
        cluster_to_refs[cluster_id].append((
            node.conversation_id,
            node.sequence_index,
            node.id,
        ))
    
    # Compute centroids
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / (norms + 1e-8)
    
    centroids: Dict[int, np.ndarray] = {}
    for cluster_id in cluster_to_refs:
        if cluster_id == -1:  # Skip noise
            continue
        
        indices = [i for i, l in enumerate(cluster_labels) if l == cluster_id]
        cluster_vectors = normalized[indices]
        centroid = cluster_vectors.mean(axis=0)
        centroid = centroid / (np.linalg.norm(centroid) + 1e-8)
        centroids[cluster_id] = centroid
    
    # Generate default labels if not provided
    labels: Dict[int, str] = {}
    if cluster_names:
        labels = {int(k): v for k, v in cluster_names.items()}
    else:
        for cluster_id in cluster_to_refs:
            if cluster_id == -1:
                labels[cluster_id] = "noise"
            else:
                labels[cluster_id] = f"cluster_{cluster_id}"
    
    # Count noise
    noise_count = len(cluster_to_refs.get(-1, []))
    
    # Build index
    index = ClusterIndex(
        cluster_to_refs=cluster_to_refs,
        centroids=centroids,
        labels=labels,
        total_nodes=len(nodes),
        noise_count=noise_count,
    )
    
    # Save
    index_dir = data_dir / "indexes"
    index_dir.mkdir(parents=True, exist_ok=True)
    index.save(index_dir / "cluster_index.json")
    
    logger.info(
        f"Built cluster index: {len(centroids)} clusters, "
        f"{len(nodes)} nodes, {noise_count} noise"
    )
    
    return index


# -----------------------------------------------------------------------------
# Tool Wrapper for Grok
# -----------------------------------------------------------------------------

class PNMTool:
    """
    Tool wrapper for model invocation.
    
    The model calls this when it needs process memory with context.
    Unlike raw embedding search, this returns readable text.
    
    Usage by model:
        [PNM query="async error handling" clusters=3 context=200]
    """
    
    def __init__(self, pnm: ProcessNodeMemory):
        self.pnm = pnm
    
    async def execute(
        self,
        query: str,
        top_clusters: int = 3,
        nodes_per_cluster: int = 2,
        context_tokens: int = 200,
    ) -> str:
        """
        Execute PNM search and return formatted results.
        
        Returns formatted text ready for context injection.
        """
        result = await self.pnm.search(
            query=query,
            top_clusters=top_clusters,
            nodes_per_cluster=nodes_per_cluster,
            context_tokens=context_tokens,
        )
        
        return result.format_for_context()


# -----------------------------------------------------------------------------
# CLI / Testing
# -----------------------------------------------------------------------------

async def main():
    """Test the ProcessNodeMemory system."""
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    
    # Import embedder
    try:
        from embedder import AsyncEmbedder
    except ImportError:
        print("Run from project root with: python -m core.process_node_memory")
        return
    
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data")
    
    print("Process Node Memory - Cluster Rehydration")
    print("=" * 60)
    
    # Initialize
    embedder = AsyncEmbedder()
    
    try:
        pnm = ProcessNodeMemory.load(data_dir, embedder)
        print(f"Loaded from {data_dir}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nTo build the cluster index, run clustering first then:")
        print("  build_cluster_index(data_dir, nodes, labels, embeddings)")
        return
    
    print("\nEnter queries (Ctrl+C to exit):\n")
    
    while True:
        try:
            query = input("PNM> ").strip()
            if not query:
                continue
            
            result = await pnm.search(query)
            print(result.format_for_context())
            print()
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
