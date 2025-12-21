"""
Memory subsystem - retrieval, embeddings, search, and ingestion.

This module provides:
- AsyncEmbedder: Multi-provider embedding pipeline (BGE-M3)
- DualRetriever: Combined process + episodic memory retrieval
- Ingest subpackage: Chat parsing and batch processing
"""
from .embedder import AsyncEmbedder, create_embedder, embed_episodes, embed_memory_nodes
from .retrieval import DualRetriever, EpisodicMemoryRetriever
