# COGTWIN MEMORY ARCHITECTURE MAP
## Complete Reconnaissance Report - Generated 2024

---

## EXECUTIVE SUMMARY

**Mission Status**: ✅ COMPLETE
**Files Analyzed**: 30+ core memory system files
**Agents Deployed**: 6 parallel reconnaissance agents
**Architecture Discovered**: 5-lane hybrid retrieval system with recursive memory pipeline

### Key Discoveries

1. **Dual Memory System**: Process memory (What/How) + Episodic memory (Why/When)
2. **5-Lane Hybrid Retrieval**: Semantic (FAISS/NumPy) + BM25 Keyword + Heuristic Pre-filter + Cluster Navigation + RRF Fusion
3. **Recursive Memory Loop**: Reasoning traces → Memory pipeline → Immediately searchable (snake eats tail)
4. **Zero-Cost Enrichment**: Heuristic signals (17+ fields) extracted in <1ms without LLM calls
5. **Enterprise vs Personal Split**: Separate orchestrators, different trust hierarchies, different memory sources

---

## 1. WIRING DIAGRAM

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          USER QUERY ENTRY POINT                           │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  MODE DETECTION         │
                    │  (config.deployment)    │
                    └─────┬──────────┬────────┘
                          │          │
            ┌─────────────┘          └─────────────┐
            │                                      │
   ┌────────▼────────┐                   ┌────────▼────────┐
   │  PERSONAL MODE  │                   │ ENTERPRISE MODE │
   │  cog_twin.py    │                   │enterprise_twin.py│
   │ + venom_voice   │                   │ (basic tier)     │
   └────────┬────────┘                   └────────┬─────────┘
            │                                      │
            │ ┌────────────────────────────────────┘
            │ │ Intent: procedural/lookup/complaint
            │ │
┌───────────▼─▼────────────┐
│    MEMORY RETRIEVAL      │
│    DualRetriever.load()  │
└───────────┬──────────────┘
            │
            │ Query Embedding
            │ AsyncEmbedder.embed_single()
            │ Provider: DeepInfra BGE-M3
            │ Dimension: 1024
            │
   ┌────────▼────────────────────────────────────────────────┐
   │            5-LANE PARALLEL RETRIEVAL                     │
   │                                                           │
   │  ┌──────────────────────────────────────────────────┐   │
   │  │ LANE 0: HEURISTIC PRE-FILTER (FastFilter)       │   │
   │  │ ─────────────────────────────────────────────   │   │
   │  │ • Eliminates 60-80% of search space in <2ms    │   │
   │  │ • Dict lookups on pre-computed signals         │   │
   │  │ • Domain + technical depth + complexity match  │   │
   │  │ • Weight: N/A (boolean gate)                   │   │
   │  └──────────────────────────────────────────────────┘   │
   │                           │                              │
   │  ┌────────────────────────▼──────────────────────────┐  │
   │  │ LANE 1: SEMANTIC VECTOR (ProcessMemoryRetriever) │  │
   │  │ ────────────────────────────────────────────────  │  │
   │  │ • NumPy cosine similarity on normalized vectors  │  │
   │  │ • Cluster-aware boosting (0.1 multiplier)        │  │
   │  │ • Auth-scoped filtering (user_id OR tenant_id)   │  │
   │  │ • Weight: cosine (0.0-1.0)                       │  │
   │  │ • Threshold: 0.5 (default)                       │  │
   │  │ • Latency: <10ms for 20k nodes                   │  │
   │  └──────────────────────────────────────────────────┘  │
   │                           │                             │
   │  ┌────────────────────────▼──────────────────────────┐ │
   │  │ LANE 2: EPISODIC MEMORY (EpisodicRetriever)      │ │
   │  │ ────────────────────────────────────────────────  │ │
   │  │ • FAISS IndexFlatIP (NumPy fallback)             │ │
   │  │ • Heuristic post-filter (intent/domain/urgency)  │ │
   │  │ • Full conversation context                      │ │
   │  │ • Weight: cosine (0.0-1.0)                       │ │
   │  │ • Threshold: 0.3 (lower for episodes)            │ │
   │  │ • Latency: <5ms FAISS + <1ms heuristic           │ │
   │  └──────────────────────────────────────────────────┘ │
   │                           │                            │
   │  ┌────────────────────────▼──────────────────────────┐│
   │  │ LANE 3: KEYWORD BM25 (MemoryGrep)                ││
   │  │ ────────────────────────────────────────────────  ││
   │  │ • Inverted index with BM25 scoring               ││
   │  │ • Exact term matching, phrase search             ││
   │  │ • Position tracking, temporal distribution       ││
   │  │ • Weight: BM25 score (normalized 0-1)            ││
   │  │ • Latency: <2ms index lookup                     ││
   │  └──────────────────────────────────────────────────┘│
   │                           │                            │
   │  ┌────────────────────────▼──────────────────────────┐│
   │  │ LANE 4: HYBRID RRF FUSION (HybridSearch)         ││
   │  │ ────────────────────────────────────────────────  ││
   │  │ • Reciprocal Rank Fusion (semantic + keyword)    ││
   │  │ • keyword_boost: 1.5x (50% higher weight)        ││
   │  │ • rrf_k: 60 (standard parameter)                 ││
   │  │ • Provenance tracking (source tagging)           ││
   │  │ • Weight: 1/(k+rank_sem) + 1.5/(k+rank_kw)       ││
   │  │ • Latency: ~15ms (parallel execution)            ││
   │  └──────────────────────────────────────────────────┘│
   │                           │                            │
   │  ┌────────────────────────▼──────────────────────────┐│
   │  │ LANE 5: CLUSTER NAVIGATION (StreamingCluster)    ││
   │  │ ────────────────────────────────────────────────  ││
   │  │ • HDBSCAN soft prediction + River DBSTREAM       ││
   │  │ • Centroid similarity fallback (>0.7)            ││
   │  │ • New cluster detection (confidence >0.6)        ││
   │  │ • Weight: cluster confidence (0.0-1.0)           ││
   │  │ • Latency: <5ms soft predict                     ││
   │  └──────────────────────────────────────────────────┘│
   └───────────────────────────┬──────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ SCORING & RANKING   │
                    │ scoring.py          │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │ CONTEXT ASSEMBLY            │
                    │ VenomVoice.format_memories()│
                    │ Trust Hierarchy Applied:    │
                    │ 1. User THIS session        │
                    │ 2. Squirrel (temporal)      │
                    │ 3. Episodic (old convos)    │
                    │ 4. Vector (similar topics)  │
                    │ 5. GREP (frequency only)    │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  LLM CALL           │
                    │  Grok/Claude/Gemini │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┴────────────────────┐
          │                                         │
   ┌──────▼───────┐                      ┌─────────▼─────────┐
   │   RESPONSE   │                      │  MEMORY WRITES    │
   │   STREAM     │                      │  (Personal Only)  │
   └──────────────┘                      └─────────┬─────────┘
                                                   │
                                    ┌──────────────┼──────────────┐
                                    │              │              │
                         ┌──────────▼───┐  ┌──────▼─────┐  ┌────▼─────┐
                         │MemoryPipeline│  │ChatMemory  │  │ Tracer   │
                         │   .ingest()  │  │.record()   │  │.finalize()│
                         └──────────────┘  └────────────┘  └──────────┘
                                    │
                                    │ RECURSIVE LOOP
                         ┌──────────▼───────────┐
                         │  Reasoning traces    │
                         │  become memories     │
                         │  (snake eats tail)   │
                         └──────────────────────┘
```

### TOOL-DRIVEN RETRIEVAL (Personal Mode Only)

When `retrieval_mode: "tools"`, the LLM can invoke these markers in its output:

- `[VECTOR: "term"]` → ProcessMemoryRetriever.retrieve()
- `[GREP: "term"]` → MemoryGrep.grep()
- `[EPISODIC: "query"]` → EpisodicMemoryRetriever.retrieve()
- `[SQUIRREL: timeframe="-60min"]` → SquirrelTool.execute()

When `retrieval_mode: "inject"`, all memories are pre-loaded into system prompt.

---

## 2. DATA FLOW MAPS

### 2.1 Memory Node Creation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ ORIGIN: User-Agent Exchange                                     │
│ Input: user_query (str) + model_response (str)                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │ CognitiveOutput     │
              │ ─────────────────   │
              │ content: str        │
              │ thought_type: enum  │
              │ reasoning: str      │
              │ confidence: float   │
              └──────────┬──────────┘
                         │
                         │ memory_pipeline.ingest(output)
                         │ Queued (async.Queue)
                         │
              ┌──────────▼────────────┐
              │ PROCESSING PIPELINE   │
              └──────────┬────────────┘
                         │
      ┌──────────────────┼──────────────────┐
      │                  │                  │
┌─────▼─────┐   ┌────────▼────────┐   ┌────▼────┐
│ Embed     │   │ Enrich          │   │ Dedup   │
│ (async)   │   │ (sync, <1ms)    │   │ (sync)  │
└─────┬─────┘   └────────┬────────┘   └────┬────┘
      │                  │                  │
      │ BGE-M3 1024-dim  │ 17+ signals     │ SHA256
      │ DeepInfra        │ HeuristicEnrich │ check
      │                  │                  │
      └──────────────────┴──────────────────┘
                         │
              ┌──────────▼──────────┐
              │ Cluster Assignment  │
              │ StreamingCluster    │
              │ ─────────────────   │
              │ • HDBSCAN soft pred │
              │ • River DBSTREAM    │
              │ • Centroid fallback │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────────┐
              │ MemoryNode Created      │
              │ ──────────────────────  │
              │ id: UUID                │
              │ embedding: [1024]       │
              │ cluster_id: int         │
              │ heuristic signals: {...}│
              │ user_id/tenant_id: UUID │
              └──────────┬──────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
   ┌──────▼───────┐            ┌────────▼────────┐
   │ IMMEDIATE    │            │ PERIODIC FLUSH  │
   │ SESSION      │            │ TO DISK         │
   │ BUFFER       │            │ ─────────────── │
   │ ──────────   │            │ nodes.json      │
   │ searchable   │            │ nodes.npy       │
   │ in 0.3ms     │            │ clusters.json   │
   └──────────────┘            └─────────────────┘
```

### 2.2 Reasoning Trace Lifecycle (Phase 5 - Recursive)

```
┌─────────────────────────────────────────────────────────────┐
│ TRACE START: tracer.start_trace(query, retrieved_ids)      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Records:
                         │ • Query text
                         │ • Memories retrieved (IDs)
                         │ • Retrieval scores
                         │ • Timestamp
                         │
              ┌──────────▼──────────┐
              │ REASONING STEPS     │
              │ ─────────────────   │
              │ tracer.record_step()│
              └──────────┬──────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐    ┌─────▼─────┐   ┌────▼────┐
    │ RETRIEVE│    │ REFLECT   │   │SYNTHESIZE│
    └─────────┘    └───────────┘   └─────────┘
         │               │               │
         └───────────────┴───────────────┘
                         │
                         │ Each step records:
                         │ • memories_touched[]
                         │ • clusters_touched[]
                         │ • duration_ms
                         │
              ┌──────────▼──────────────┐
              │ RESPONSE GENERATION     │
              │ Model produces response │
              └──────────┬──────────────┘
                         │
              ┌──────────▼─────────────────────┐
              │ FINALIZATION                   │
              │ tracer.finalize_trace()        │
              │ ───────────────────────────    │
              │ • Saves to JSON file           │
              │ • Computes metrics             │
              │ • Updates touch counts         │
              └──────────┬─────────────────────┘
                         │
                         │ Phase 5 Innovation:
                         │ STREAM TO MEMORY PIPELINE
                         │
              ┌──────────▼──────────────────────┐
              │ _stream_to_memory()             │
              │ ────────────────────────────    │
              │ Convert ReasoningTrace →        │
              │ CognitiveOutput (REFLECT type)  │
              └──────────┬──────────────────────┘
                         │
                         │ memory_pipeline.ingest()
                         │
              ┌──────────▼──────────────────┐
              │ TRACE BECOMES MEMORY        │
              │ ─────────────────────────   │
              │ • Embedded like any node    │
              │ • Clustered                 │
              │ • Immediately searchable    │
              │ • Future queries can        │
              │   retrieve past reasoning   │
              └─────────────────────────────┘

🔁 RECURSIVE LOOP COMPLETE: Model can now see its own reasoning history
```

### 2.3 Enterprise RAG Flow (Basic Tier)

```
┌─────────────────────────────────────────────────────────────┐
│ USER QUERY + AUTH (email, department, session_id)          │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────▼──────────────┐
              │ INTENT CLASSIFICATION   │
              │ classify_enterprise_    │
              │ intent() - HEURISTICS   │
              │ ─────────────────────   │
              │ • casual → Skip RAG     │
              │ • procedural → Fire RAG │
              │ • lookup → Fire RAG     │
              │ • complaint → Fire RAG  │
              └──────────┬──────────────┘
                         │
                         │ if RAG needed:
                         │
              ┌──────────▼──────────────────────┐
              │ EnterpriseRAGRetriever.search() │
              │ ──────────────────────────────  │
              │ Inputs:                         │
              │ • query (str)                   │
              │ • department_id (filter)        │
              │ • threshold (0.6)               │
              └──────────┬──────────────────────┘
                         │
                         │ PostgreSQL Query:
                         │ SELECT * FROM enterprise.documents
                         │ WHERE :dept_id = ANY(department_access)
                         │   AND embedding <=> :query_vec >= 0.6
                         │ ORDER BY embedding <=> :query_vec
                         │
              ┌──────────▼────────────────┐
              │ Manual Chunks Retrieved   │
              │ (threshold-based, no k)   │
              └──────────┬────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │ Found chunks                │ No chunks found
          │                             │
   ┌──────▼──────┐            ┌─────────▼────────┐
   │ TRUST:      │            │ GUARDRAIL:       │
   │ ABSOLUTE    │            │ "No manual found"│
   │             │            │ "Cannot answer"  │
   │ Inject into │            │                  │
   │ system      │            │                  │
   │ prompt with │            │                  │
   │ highest     │            │                  │
   │ trust label │            │                  │
   └──────┬──────┘            └─────────┬────────┘
          │                             │
          └──────────────┬──────────────┘
                         │
              ┌──────────▼──────────┐
              │ Squirrel Context    │
              │ (last 60min session)│
              │ HIGH TRUST          │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │ Session Context     │
              │ (in-memory buffer)  │
              │ MEDIUM TRUST        │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │ LLM CALL            │
              │ (Grok default)      │
              └──────────┬──────────┘
                         │
              ┌──────────▼────────────────┐
              │ Response + Session Update │
              │ ───────────────────────── │
              │ • NO persistent memory    │
              │ • In-memory session dict  │
              │ • Cleared on restart      │
              └───────────────────────────┘

TRUST HIERARCHY (Inverted from Personal):
  1. Manual chunks (ABSOLUTE - overrides user)
  2. Squirrel (recent session)
  3. Session context
  4. User statements (lowest trust)
```

---

## 3. PER-FILE ANALYSIS SUMMARIES

### ORCHESTRATORS

#### cog_twin.py
- **Role**: Personal mode cognitive twin orchestrator
- **Memory Imports**: DualRetriever, MemoryPipeline, ChatMemoryStore, SquirrelTool, MetacognitiveMirror, CognitiveTracer
- **Memory Reads**:
  - DualRetriever.retrieve() → Process + Episodic memories
  - memory_pipeline.search_session() → Recent outputs
  - squirrel.execute() → Temporal recall (last 1h)
  - tracer.search_traces() → Past reasoning exemplars
- **Memory Writes**:
  - memory_pipeline.ingest() → Every response
  - chat_memory.record_exchange() → Every turn
  - tracer.finalize_trace() → Reasoning traces
- **Config**: Loaded from config.yaml + environment variables
- **Mode Switch**: `cfg('voice.engine')` selects VenomVoice or EnterpriseVoice

#### venom_voice.py
- **Role**: Formatting layer for personal mode prompts
- **Memory Reads**: Formats memories from VoiceContext
- **Memory Writes**: None (read-only)
- **Trust Hierarchy**: User > Squirrel > Episodic > Vector > GREP
- **Retrieval Modes**: "inject" (pre-load) vs "tools" (on-demand)

#### enterprise_twin.py
- **Role**: Enterprise basic tier orchestrator
- **Memory Imports**: EnterpriseRAGRetriever only (NO MemoryPipeline)
- **Memory Reads**:
  - rag.search() → Manual chunks (department-filtered)
  - _session_memories[session_id] → In-memory buffer
- **Memory Writes**: In-memory session dict only (non-persistent)
- **Config**: Dict passed to __init__
- **Mode Switch**: Separate class, heuristic intent classifier

---

### MEMORY PIPELINE FILES

#### memory_pipeline.py
- **Purpose**: Async recursive memory ingestion with streaming clustering
- **Stage**: Orchestrate + Ingest + Process + Store
- **Inputs**: CognitiveOutput objects from agent
- **Outputs**: MemoryNode objects (session buffer + disk)
- **DB Tables**: File-based (JSON nodes + NPY embeddings)
- **Vector Ops**: AsyncEmbedder batch, NumPy cosine, StreamingCluster assign
- **Dependencies**: embedder, streaming_cluster, schemas

#### memory_backend.py
- **Purpose**: Pluggable backend abstraction (file/postgres)
- **Stage**: Store + Retrieve
- **Inputs**: MemoryNode objects, query embeddings, auth context
- **Outputs**: List[MemoryNode], embeddings, cluster info
- **DB Tables**:
  - File: nodes.json, nodes.npy, clusters.json
  - Postgres: memory_nodes, vectors (pgvector)
- **Vector Ops**: NumPy cosine (file), pgvector cosine (postgres)
- **Auth**: FAIL SECURE - filters by user_id/tenant_id BEFORE similarity
- **Dependencies**: backends.postgres (optional)

#### chat_memory.py
- **Purpose**: JSON-backed chat exchange storage (SQUIRREL Lane 4)
- **Stage**: Store + Retrieve (temporal/keyword search)
- **Inputs**: ChatExchange data (user/model/trace triplets)
- **Outputs**: List[ChatExchange], formatted context strings
- **DB Tables**: File-based (exchange_{id}.json per exchange)
- **Vector Ops**: None (pure keyword + temporal filtering)
- **Dependencies**: None (standalone)

#### retrieval.py
- **Purpose**: Dual retrieval engine (process + episodic)
- **Stage**: Retrieve (main orchestrator)
- **Inputs**: Query strings, embeddings, auth context, cluster IDs
- **Outputs**: RetrievalResult with process/episodic memories
- **DB Tables**: Delegates to FileBackend/PostgresBackend
- **Vector Ops**:
  - ProcessMemoryRetriever: NumPy cosine + cluster boosting
  - EpisodicMemoryRetriever: FAISS IndexFlatIP
  - HybridSearch: FAISS + BM25 fusion
- **Dependencies**: embedder, enricher, cluster_schema, memory_grep, hybrid_search

---

### RETRIEVAL LANES

#### hybrid_search.py (Lane 4)
- **Purpose**: Combine semantic + keyword via RRF fusion
- **Algorithm**: Reciprocal Rank Fusion
- **Inputs**: Query string (embedded + tokenized)
- **Outputs**: HybridResult with provenance tracking
- **Weights**: keyword_boost=1.5, rrf_k=60
- **Thresholds**: min_semantic=0.3, semantic_k=20, keyword_k=20
- **Performance**: ~15ms (parallel execution)

#### fast_filter.py (Lane 0 - Pre-filter)
- **Purpose**: Eliminate 60-80% of search space in <2ms
- **Algorithm**: Dict lookups on pre-computed heuristics
- **Inputs**: Query signals + candidate nodes
- **Outputs**: Filtered node list
- **Weights**: Boolean gates (pass/fail)
- **Thresholds**: domain_boost=0.2, max_tech_depth_diff=6
- **Performance**: <2ms for 5000 nodes

#### scoring.py
- **Purpose**: Multi-dimensional response scoring
- **Algorithm**: Weighted average of 10 dimensions
- **Inputs**: User feedback (1-10 scale)
- **Outputs**: ResponseScore object
- **Weights**: personality=0.25, usefulness=0.20, accuracy=0.15, depth=0.10
- **Modes**: Quick (3 questions) vs Full (10 dimensions)

#### embedder.py
- **Purpose**: Multi-provider embedding pipeline
- **Algorithm**: BGE-M3 via DeepInfra/TEI/Cloudflare
- **Inputs**: Text strings (up to 8192 tokens)
- **Outputs**: 1024-dim float32 vectors
- **Performance**:
  - DeepInfra: 180 RPM (rate limited)
  - TEI: Unlimited, ~2-3min for 22k embeddings
  - Cloudflare: 300 RPM
- **Cache**: Local .npy cache

#### streaming_cluster.py (Lane 5)
- **Purpose**: Real-time cluster assignment
- **Algorithm**: HDBSCAN (batch) + River DBSTREAM (streaming)
- **Inputs**: Embedding vector
- **Outputs**: ClusterAssignment (id, confidence, is_new)
- **Weights**: Centroid similarity (cosine)
- **Thresholds**: soft_prediction=0.5, nearest_centroid=0.7, new_cluster=0.6
- **Performance**: <5ms soft predict

---

### SPECIALIZED MEMORY SYSTEMS

#### squirrel.py
- **Unique Purpose**: Pure temporal navigation ("what was said 60 min ago")
- **Trigger**: Model invokes [SQUIRREL] tags OR system auto-fires for hot context
- **Data Structure**: ChatMemoryStore backend, datetime-based filtering
- **Integration**: Initialized in CognitiveTablet, called during context building

#### memory_grep.py (Lane 3)
- **Unique Purpose**: Exact keyword search with BM25 + frequency analysis
- **Trigger**: Exact term matching requests, frequency analysis
- **Data Structure**: Inverted index (dict), BM25Okapi, GrepResult/GrepHit
- **Integration**: Built during DualRetriever init, used by HybridSearch

#### metacognitive_mirror.py
- **Unique Purpose**: Meta-analysis of cognitive architecture (system watching itself)
- **Trigger**: Continuous background tracking + periodic snapshots (15min)
- **Data Structure**: QueryArchaeologist (deque), MemoryThermodynamics (dicts), CognitiveSeismograph (snapshots), PredictivePrefetcher (Markov chains)
- **Integration**: Imported by cog_twin, records QueryEvents, provides cognitive state

#### reasoning_trace.py
- **Unique Purpose**: Records complete reasoning chains (model's thought process)
- **Trigger**: start_trace() → record_step() → finalize_trace() per query
- **Data Structure**: ReasoningTrace dataclass, ReasoningStep dataclass, persisted as JSON
- **Integration**: Phase 5 breakthrough - streams traces to memory_pipeline (recursive)

#### read_traces.py
- **Unique Purpose**: Command-line viewer for traces/exchanges (debugging tool)
- **Trigger**: Manual invocation by developers
- **Data Structure**: Reads JSON files, formats terminal output
- **Integration**: Standalone CLI, NOT imported by other modules

---

### PROCESSING & ENRICHMENT

#### llm_tagger.py
- **Processor**: LLM-based tagging (Grok)
- **Stage**: post-store (batch episodic enrichment)
- **Input**: EpisodicMemory objects
- **Output**: llm_tags dict (summary, primary_intent, outcome, etc.)
- **Metadata Added**: 8 semantic fields (summary, intent, outcome, emotional_arc, domains, etc.)
- **Triggers**: batch/async, rate limited (60 RPM), concurrent (5 requests)

#### heuristic_enricher.py
- **Processor**: Zero-cost signal extraction
- **Stage**: pre-store (inline)
- **Input**: Raw text content
- **Output**: 17+ signal fields
- **Metadata Added**: intent_type, complexity, technical_depth, domain_signals, urgency, emotional_valence, has_code, has_error, keyword_set, etc.
- **Triggers**: sync (<1ms per node), NO API calls

#### cluster_schema.py
- **Processor**: Semantic labels for clusters
- **Stage**: post-store (periodic)
- **Input**: Cluster assignments + nodes + embeddings
- **Output**: ClusterProfile objects
- **Metadata Added**: label, description, domain_distribution, top_keywords, sample_contents, centroid
- **Triggers**: batch/periodic, manual rebuild

#### dedup.py
- **Processor**: Duplicate blocking
- **Stage**: pre-store (inline check)
- **Input**: item_id + optional content
- **Output**: Boolean (is_duplicate)
- **Metadata Added**: None (prevents storage)
- **Triggers**: sync, DedupBatch context manager for bulk

#### evolution_engine.py
- **Processor**: HITL self-improvement
- **Stage**: periodic (triggered by metacognitive insights)
- **Input**: MetacognitiveInsight objects
- **Output**: EvolutionProposal objects (code patches)
- **Metadata Added**: None (proposes changes, not metadata)
- **Triggers**: async/event-driven, HITL gate (never auto-applies)

#### streaming_cluster.py
- **Processor**: Real-time cluster assignment
- **Stage**: pre-store (during ingestion)
- **Input**: Embedding vector
- **Output**: ClusterAssignment (cluster_id, confidence, is_new)
- **Metadata Added**: cluster_id, confidence, is_new_cluster, nearest_clusters
- **Triggers**: sync/streaming during memory ingestion

#### memory_pipeline.py (Recursive Loop)
- **Processor**: Continuous ingestion pipeline
- **Stage**: continuous (background async loop)
- **Input**: CognitiveOutput objects
- **Output**: MemoryNode objects
- **Metadata Added**: id, timestamp, thought_type, reasoning, source_memory_ids, cognitive_phase, confidence, cluster_id, user_id/tenant_id
- **Triggers**: async/continuous, batch processing (5s or 10 items)

---

### CONFIGURATION & DATABASE SCHEMA

#### config.yaml
- **Sections**: deployment, tenant, features, memory, retrieval, memory_pipeline
- **Personal vs Enterprise**:
  - `deployment.mode`: enterprise | personal
  - `deployment.tier`: basic | advanced | full
  - Enterprise has tenant config, personal doesn't
  - Enterprise basic: memory_pipeline DORMANT (ready for pro tier)
  - Personal: memory_pipeline ENABLED by default

#### config_loader.py
- **Functions**: cfg(), load_config(), memory_enabled(), is_enterprise_mode(), get_tier()
- **Tier Presets**: basic (no memory), advanced (memory enabled), full (all features)

#### postgres.py
- **Tables**: personal.memory_nodes, personal.episodes
- **Columns (memory_nodes)**: 24+ columns including embeddings, heuristic signals, cluster metadata, auth scoping
- **Vector Columns**: embedding (1024-dim), cluster_centroid (1024-dim)
- **Indexes**: ivfflat on embeddings (lists=100), B-tree on user_id/tenant_id
- **Security**: FAIL SECURE - all queries require user_id OR tenant_id

#### schemas.py
- **MemoryNode**: 30+ fields (identity, content, source, auth, embedding, heuristics, cluster, retrieval)
- **EpisodicMemory**: Full conversation + LLM tags + heuristic aggregates
- **Personal vs Enterprise**: user_id vs tenant_id scoping

#### 003_smart_documents.sql
- **Table**: enterprise.documents
- **Columns**: 40+ fields (content, embedding, query_types, verbs, entities, actors, conditions, process metadata, relationships, cluster metadata, enrichment fields, access control)
- **Vector Columns**: embedding (1024-dim), cluster_centroid (1024-dim), synthetic_questions_embedding (1024-dim)
- **Indexes**: 20+ indexes (ivfflat, GIN, B-tree, GiST, partial)
- **Enterprise Only**: No equivalent in personal schema

---

## 4. CONFIG SEPARATION MATRIX

| Config Key | Personal Mode | Enterprise Mode | Notes |
|------------|---------------|-----------------|-------|
| `deployment.mode` | personal | enterprise | Core mode switch |
| `deployment.tier` | full (default) | basic (current) | Feature gate |
| `tenant.*` | N/A | Driscoll config | Multi-tenant setup |
| `features.memory_pipeline` | enabled | DORMANT | Personal always on, enterprise pro tier |
| `features.enterprise_rag` | N/A | enabled | Manual search only |
| `features.squirrel` | enabled | enabled | Both have session continuity |
| `features.metacognitive_mirror` | enabled | disabled | Personal only |
| `features.evolution_engine` | enabled | disabled | Personal only |
| `features.reasoning_traces` | enabled | disabled | Personal only |
| `memory.backend` | file (default) | file (current) | Can use postgres for both |
| `retrieval.process_top_k` | 10 | 10 | Same retrieval params |
| `retrieval.episodic_top_k` | 5 | N/A | Enterprise has no episodes |
| `voice.engine` | venom | enterprise | Different personalities |
| Tool Control | LLM-driven | Python heuristics | Who decides retrieval |
| Trust Hierarchy | User > Time > Context | Manual > Time > User | Inverted priority |
| Memory Persistence | Full (traces, chat, nodes) | Session only | Enterprise is stateless |

---

## 5. DATABASE SCHEMA SUMMARY

### Personal Schema (personal.*)

#### personal.memory_nodes
- **Purpose**: Individual memory nodes (process memory)
- **Key Columns**: id, user_id, conversation_id, human_content, assistant_content, embedding (1024-dim)
- **Enrichment**: 17+ heuristic signals (intent, complexity, technical_depth, etc.)
- **Clustering**: cluster_id, cluster_label, cluster_confidence
- **Auth**: user_id scoping (FAIL SECURE)
- **Indexes**: ivfflat (embedding), B-tree (user_id)

#### personal.episodes
- **Purpose**: Full conversation episodes (episodic memory)
- **Key Columns**: id, user_id, messages (JSONB), embedding (1024-dim)
- **LLM Tags**: summary, primary_intent, outcome, emotional_arc, domains
- **Auth**: user_id scoping
- **Indexes**: ivfflat (embedding), B-tree (user_id)

### Enterprise Schema (enterprise.*)

#### enterprise.documents
- **Purpose**: Process manuals (RAG chunks)
- **Key Columns**: id, department_id, content, embedding (1024-dim), 40+ metadata fields
- **Process Metadata**: query_types[], verbs[], entities[], actors[], conditions[], process_name, process_step
- **Relationships**: parent_id (hierarchy), sibling_ids[], prerequisite_ids[], see_also_ids[], follows_ids[], supersedes_id
- **Enrichment**: synthetic_questions[], synthetic_questions_embedding (1024-dim), completeness_score, actionability_score, acronyms{}, jargon{}, numeric_thresholds{}
- **Access Control**: department_access[] (slug-based, NOT FK)
- **Indexes**: 20+ indexes (ivfflat, GIN, B-tree, GiST, partial)

#### enterprise.audit_log
- **Purpose**: Compliance audit trail
- **Key Columns**: id, action, actor_email, target_email, department_slug, old_value, new_value, reason, ip_address, created_at
- **Indexes**: B-tree on action, actor, target, department, created_at

### Missing Tables (Referenced but Not Created)

- ❌ `enterprise.tenants` - Multi-tenant config (referenced everywhere)
- ❌ `enterprise.departments` - Department definitions (referenced in admin routes)

### Vector Search Strategy

- **Embedding Model**: BGE-M3 (DeepInfra)
- **Dimension**: 1024
- **Index**: ivfflat (upgrading to HNSW when pgvector 0.5+)
- **Distance**: Cosine (`<=>` operator, converted to similarity: 1 - distance/2)
- **Retrieval**: Threshold-based (>= 0.6), NOT top-k limited

---

## 6. GAPS & OPPORTUNITIES

### GAPS IDENTIFIED

#### 1. Missing Infrastructure
- **Gap**: `enterprise.tenants` and `enterprise.departments` tables not created
- **Impact**: Code references non-existent tables, potential runtime errors
- **Opportunity**: Create migration scripts for missing tables

#### 2. Column Name Mismatch
- **Gap**: Code expects `azure_oid`, DB has `oid`
- **Impact**: Azure SSO integration broken
- **Opportunity**: Align schema with Azure AD integration requirements

#### 3. Enterprise Memory Dormancy
- **Gap**: Enterprise basic tier has no persistent memory (by design, but users may expect it)
- **Impact**: No learning across sessions, purely reactive
- **Opportunity**: Clear upgrade path to Pro tier with memory enabled

#### 4. No Temporal Lane Separation
- **Gap**: Temporal signals integrated into heuristic filtering, not a standalone lane
- **Impact**: Time-based retrieval mixed with semantic/keyword
- **Opportunity**: Extract temporal as 6th lane with dedicated weight/threshold

#### 5. Auth Scoping Incomplete
- **Gap**: Only ProcessMemoryRetriever has auth filtering, EpisodicRetriever doesn't
- **Impact**: Potential data leakage in episodic retrieval
- **Opportunity**: Add auth scoping to ALL retrieval paths

#### 6. No Memory Decay/Aging
- **Gap**: All memories persist indefinitely with equal weight
- **Impact**: Old irrelevant memories pollute results
- **Opportunity**: Implement access-based recency boost or time decay

### REDUNDANCIES IDENTIFIED

#### 1. Dual Cluster Systems
- **Redundancy**: HDBSCAN (batch) + River DBSTREAM (streaming) overlap
- **Impact**: Complexity, potential inconsistency
- **Opportunity**: Unify into single streaming approach or clarify use cases

#### 2. Multiple Embedding Providers
- **Redundancy**: DeepInfra, TEI, Cloudflare all for BGE-M3
- **Impact**: Configuration complexity, testing burden
- **Opportunity**: Pick one primary, keep others as fallbacks only

#### 3. File vs Postgres Backends
- **Redundancy**: Both backends implemented, file used by default
- **Impact**: Code maintenance for both paths
- **Opportunity**: Deprecate file backend for production, keep for dev/testing

### OPTIMIZATION OPPORTUNITIES

#### 1. Pre-filter Everything
- **Current**: FastFilter is optional
- **Opportunity**: Make heuristic pre-filtering mandatory for all queries >5k nodes
- **Impact**: 60-80% reduction in vector ops, 2-5x speedup

#### 2. Cluster-First Retrieval
- **Current**: Cluster boosting is additive (0.1 multiplier)
- **Opportunity**: Cluster-first strategy (search within top-k clusters only)
- **Impact**: 10-100x speedup for large corpuses, potential recall loss

#### 3. HNSW Index Migration
- **Current**: ivfflat with lists=100
- **Opportunity**: Upgrade to HNSW when pgvector 0.5+ available
- **Impact**: 10x faster vector search, better recall

#### 4. Async Everywhere
- **Current**: Some sync operations block (enrichment, dedup)
- **Opportunity**: Convert all processing to async with worker pools
- **Impact**: Higher throughput, better concurrency

#### 5. Batch LLM Tagging
- **Current**: LLM tagging is manual batch operation
- **Opportunity**: Auto-trigger nightly batch on new episodes
- **Impact**: Always-fresh semantic tags, ~$0.30 per 2200 episodes

### WEAKEST LANE

**LANE 5: Cluster Navigation** is the weakest:

- **Low Usage**: Rarely used compared to semantic/keyword
- **Inconsistency**: Two cluster systems (HDBSCAN + River) with unclear boundaries
- **Poor Labeling**: Cluster labels are domain + keyword (not semantic)
- **No Dynamic Adjustment**: Clusters formed once, no re-clustering based on usage
- **Opportunity**:
  - Unify clustering approach
  - Add LLM-generated cluster descriptions
  - Implement usage-based cluster evolution
  - Promote cluster navigation in UI (currently hidden)

### STRONGEST LANE

**LANE 4: Hybrid RRF Fusion** is the strongest:

- **Best Recall**: Combines semantic + keyword (best of both)
- **Proven Algorithm**: RRF is well-studied, production-ready
- **Provenance Tracking**: Shows which lane found each result
- **Tunable**: keyword_boost adjustable based on corpus
- **Fast**: 15ms parallel execution
- **Opportunity**: Make this the default retrieval path for all queries

---

## 7. ARCHITECTURAL INSIGHTS

### Key Findings

1. **Recursive Memory Loop (Phase 5)**: Reasoning traces → Memory pipeline → Immediately searchable. "The snake eats its tail." This enables the model to learn from its own past reasoning.

2. **Zero-Cost Enrichment MVP**: Heuristic enrichment (<1ms, no API calls) eliminates 60-80% of search space before expensive vector operations. This is the secret to performance.

3. **Dual Trust Hierarchies**: Personal mode trusts user first, enterprise mode trusts manuals first. Inverted priority reflects different use cases (personal assistant vs corporate compliance).

4. **Fail-Secure Auth**: All retrieval operations enforce user_id/tenant_id filtering BEFORE similarity computation to prevent data leakage. No auth = empty results, never all data.

5. **File-First, DB-Optional**: Default uses JSON+NPY for simplicity, can swap to Postgres without code changes. Prioritizes developer experience.

6. **Cluster-Aware Retrieval**: Not just individual similarity, but cluster-level boosting. Memories in semantically similar clusters get a bonus.

7. **Tool-Driven vs Inject Modes**: Personal mode can let LLM decide when to retrieve ([SQUIRREL]/[GREP] tags), or pre-load all context. Flexibility for different models.

8. **Phase Gates**: Enterprise basic tier has all memory infrastructure dormant (not removed). Pro tier = flip feature flags, instant upgrade.

9. **Metacognitive Layer**: System watches itself think (query patterns, memory temperature, drift signals). Foundation for self-optimization.

10. **Hybrid Streaming Clustering**: Batch HDBSCAN for corpus, River DBSTREAM for session. Real-time cluster formation without re-clustering entire corpus.

---

## 8. RECOMMENDED NEXT STEPS

### Immediate (Phase 6 Prep)

1. **Create Missing Tables**: enterprise.tenants, enterprise.departments with proper FKs
2. **Fix Column Mismatch**: Rename `oid` → `azure_oid` or update code
3. **Add Auth to Episodic**: Extend FAIL SECURE filtering to EpisodicMemoryRetriever
4. **Document Upgrade Path**: Clear docs for basic → pro tier transition

### Short-term (Next Sprint)

1. **Promote Hybrid Search**: Make RRF fusion the default retrieval path
2. **Make Pre-filter Mandatory**: Force FastFilter for all queries >5k nodes
3. **Unify Cluster Systems**: Pick HDBSCAN or River, deprecate the other
4. **Auto-batch LLM Tagging**: Nightly cron job for new episodes

### Medium-term (Next Quarter)

1. **HNSW Migration**: Upgrade pgvector, benchmark vs ivfflat
2. **Cluster-First Retrieval**: Experiment with top-k cluster pre-selection
3. **Memory Decay**: Implement access-based recency boost
4. **LLM Cluster Labels**: Replace domain+keyword with semantic descriptions

### Long-term (Phase 7+)

1. **Evolution Engine HITL Loop**: Integrate with metacognitive insights
2. **Multi-modal Memory**: Images, audio, video in memory nodes
3. **Federated Memory**: Cross-tenant knowledge sharing (with privacy controls)
4. **Adaptive Lane Weighting**: Learn optimal RRF weights per corpus

---

## APPENDIX: FILE MANIFEST

### Core Orchestrators
- `core/cog_twin.py` - Personal cognitive twin
- `core/venom_voice.py` - Personal voice/personality
- `core/enterprise_twin.py` - Enterprise basic tier

### Memory Pipeline
- `memory/memory_pipeline.py` - Recursive ingestion pipeline
- `memory/memory_backend.py` - Pluggable storage backend
- `memory/chat_memory.py` - Chat exchange storage
- `memory/retrieval.py` - Dual retrieval engine

### Retrieval Lanes
- `memory/hybrid_search.py` - RRF semantic+keyword fusion
- `memory/fast_filter.py` - Heuristic pre-filter
- `memory/scoring.py` - Response feedback
- `memory/embedder.py` - BGE-M3 embedding provider
- `memory/streaming_cluster.py` - Real-time clustering
- `memory/memory_grep.py` - BM25 keyword search

### Specialized Systems
- `memory/squirrel.py` - Temporal recall tool
- `memory/metacognitive_mirror.py` - Self-monitoring cognition
- `memory/reasoning_trace.py` - Reasoning chain recorder
- `memory/read_traces.py` - CLI trace viewer

### Processing & Enrichment
- `memory/llm_tagger.py` - Grok-based tagging
- `memory/heuristic_enricher.py` - Zero-cost signal extraction
- `memory/cluster_schema.py` - Cluster semantic labels
- `memory/dedup.py` - Duplicate blocking
- `memory/evolution_engine.py` - HITL self-improvement

### Configuration & Schema
- `core/config.yaml` - Main configuration
- `core/config_loader.py` - Config parser
- `memory/backends/postgres.py` - PostgreSQL backend
- `core/protocols.py` - Nuclear elements (not analyzed)
- `core/schemas.py` - Pydantic models
- `db/003_smart_documents.sql` - Enterprise documents table
- `db/003b_enrichment_columns.sql` - Enrichment extensions
- `db/migrations/004_audit_log.sql` - Audit trail

---

**END OF RECONNAISSANCE REPORT**

Generated: 2024
Mission: RECON_MEMORY_ARCHITECTURE.md
Agents: 6 parallel reconnaissance agents
Status: ✅ COMPLETE

Next Phase: Battle Plan + Spec Sheet
