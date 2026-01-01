"""
RETRIEVAL UPGRADE SUMMARY
=========================

4 new modules that augment your existing FAISS + BM25 stack.
Drop-in, no architecture changes needed.

INSTALLATION:
    pip install transformers torch ragatouille

YOUR STACK NOW:
                                                    
    ┌─────────────────────────────────────────────────────────────┐
    │                        QUERY                                │
    │                          │                                  │
    │              ┌───────────┼───────────┐                      │
    │              ▼           ▼           ▼                      │
    │         ┌────────┐  ┌────────┐  ┌────────┐                  │
    │         │  BM25  │  │ FAISS  │  │ColBERT │  ◄── NEW         │
    │         │ (GREP) │  │(cosine)│  │(token) │                  │
    │         └────┬───┘  └────┬───┘  └────┬───┘                  │
    │              │           │           │                      │
    │              └─────┬─────┴─────┬─────┘                      │
    │                    │           │                            │
    │                    ▼           ▼                            │
    │              ┌──────────────────────┐                       │
    │              │    RRF FUSION        │                       │
    │              └──────────┬───────────┘                       │
    │                         │                                   │
    │                         ▼                                   │
    │              ┌──────────────────────┐                       │
    │              │     RERANKER         │  ◄── NEW              │
    │              │  (cross-encoder)     │                       │
    │              └──────────┬───────────┘                       │
    │                         │                                   │
    │                         ▼                                   │
    │                    TOP K RESULTS                            │
    └─────────────────────────────────────────────────────────────┘

    OPTIONAL QUERY PREPROCESSING:
    
    ┌─────────────────────────────────────────────────────────────┐
    │  "that websocket thing"                                     │
    │           │                                                 │
    │           ▼                                                 │
    │  ┌─────────────────┐                                        │
    │  │  HYDE (vague?)  │  ◄── NEW                               │
    │  │  Generate hypo- │                                        │
    │  │  thetical doc   │                                        │
    │  └────────┬────────┘                                        │
    │           │                                                 │
    │           ▼                                                 │
    │  "WebSocket streaming implementation using FastAPI..."      │
    │           │                                                 │
    │           └──────────────► [search with this instead]       │
    └─────────────────────────────────────────────────────────────┘

    EMBEDDING UPGRADE (one-time re-index):
    
    ┌─────────────────────────────────────────────────────────────┐
    │  BEFORE: "Fixed the bug"                                    │
    │                                                             │
    │  AFTER:  "[2024-03-15 02:47] [async-debugging]              │
    │          Technical: 7/10, Frustrated, Has errors            │
    │          Content: Fixed the bug"                            │
    │                                                             │
    │  CONTEXTUAL EMBEDDINGS capture WHAT + WHEN + WHY  ◄── NEW   │
    └─────────────────────────────────────────────────────────────┘


QUICK START:
============

1. RERANKER (easiest win):
   
   from reranker import Reranker, RerankedRetriever
   
   reranker = Reranker()  # Loads BGE-reranker-v2-m3
   
   # Wrap your existing retriever
   retriever = RerankedRetriever(your_dual_retriever, reranker)
   results = await retriever.retrieve(query, top_k=10)

2. HYDE (for vague queries):
   
   from hyde import AdaptiveHyDE, create_hyde_with_grok
   
   hyde = create_hyde_with_grok(embedder, GROK_API_KEY)
   
   # Auto-detects when to use HyDE
   adaptive = AdaptiveHyDE(embedder, hyde.llm_generate)
   results = await adaptive.search("that thing we talked about", retriever)

3. COLBERT (token-level matching):
   
   from colbert_search import ColBERTSearch
   
   colbert = ColBERTSearch()
   colbert.index_from_nodes(your_memory_nodes)
   results = await colbert.search("async error handling", top_k=10)

4. CONTEXTUAL EMBEDDINGS (one-time upgrade):
   
   from contextual_embeddings import reindex_with_context, ContextConfig
   
   config = ContextConfig(template="full")
   new_embeddings = await reindex_with_context(
       nodes=your_nodes,
       embedder=your_embedder,
       output_path=Path("./data/vectors/contextual_embeddings.npy"),
       config=config,
   )
   # Then rebuild FAISS index with new embeddings


COMBINED PIPELINE:
==================

async def search(query: str, top_k: int = 10):
    '''Full retrieval pipeline with all upgrades.'''
    
    # 1. Check if query needs HyDE
    use_hyde, confidence, _ = QueryClassifier.should_use_hyde(query)
    
    if use_hyde and confidence > 0.6:
        # Generate hypothetical doc
        hypothetical = await hyde.generate_hypothetical(query)
        search_query = hypothetical
    else:
        search_query = query
    
    # 2. Multi-source retrieval
    faiss_results = await faiss_search(search_query, top_k=50)
    bm25_results = grep.search(search_query, top_k=50)
    colbert_results = await colbert.search(search_query, top_k=50)
    
    # 3. RRF fusion
    fused = rrf_merge(faiss_results, bm25_results, colbert_results)
    
    # 4. Rerank top candidates
    candidates = [(item, score) for item, score in fused[:50]]
    reranked = await reranker.rerank(query, candidates, top_k=top_k)  # Use ORIGINAL query
    
    return reranked.get_items()


EXPECTED IMPROVEMENTS:
======================

| Upgrade              | Latency | Quality Gain | When It Helps Most           |
|---------------------|---------|--------------|------------------------------|
| Reranker            | +50ms   | +20-30%      | Always (especially long docs)|
| HyDE                | +200ms  | +15-25%      | Vague/conceptual queries     |
| ColBERT             | +30ms   | +10-20%      | Multi-term queries           |
| Contextual Embed    | 0ms*    | +10-15%      | Time/context-sensitive search|

*One-time re-indexing cost, no runtime overhead


FILES CREATED:
==============

1. reranker.py           - Cross-encoder reranking
2. hyde.py               - Hypothetical document embeddings  
3. colbert_search.py     - Late interaction retrieval
4. contextual_embeddings.py - Metadata-enriched embeddings

Plus from earlier:
5. process_node_memory.py - Cluster-to-text rehydration (Lane 6)
6. pnm_integration_guide.py - Integration docs


DEPENDENCY INSTALL:
===================

# Core (reranker + contextual)
pip install transformers torch

# ColBERT
pip install ragatouille

# Optional: faster inference
pip install accelerate


NEXT STEPS:
===========

1. [ ] Add reranker as post-processing step in DualRetriever
2. [ ] Add HyDE query preprocessing with auto-detection
3. [ ] Build ColBERT index alongside FAISS
4. [ ] Re-embed corpus with contextual embeddings
5. [ ] A/B test retrieval quality improvements
6. [ ] Wire up PNM (cluster rehydration) as Lane 6
7. [ ] Break fourth wall with Grok to see what actually arrives
"""
