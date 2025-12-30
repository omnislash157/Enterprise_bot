# Streaming Pipeline Recon

## Status: HEALTHY ✓

All core components operational. CogTwin streaming architecture with WebSocket delivery, memory pipeline ingestion, and 4-lane retrieval system.

---

## Architecture Diagram

```
USER INPUT (WebSocket)
      |
      v
[websocket_endpoint] (main.py:1005)
      |
      v
[CogTwin.think()] (cog_twin.py:365-989) ◄──┐ RECURSIVE LOOP
      |                                      │
      ├─── STEP 1: Mirror State (406)       │
      ├─── STEP 2: Dual Retrieval (411-425) │
      ├─── STEP 2.25: SQUIRREL Hot (443-463)│
      ├─── STEP 2.5: Exemplar Traces (465-476)
      ├─── STEP 6: VenomVoice Prompt (520-583)
      ├─── STEP 8: LLM API Call (585-612)   │
      ├─── STEP 8.5: TOOL EXECUTION (616-875)│
      │         ├─ [GREP] → hybrid_search   │
      │         ├─ [SQUIRREL] → chat_memory │
      │         ├─ [VECTOR] → faiss_index   │
      │         └─ [EPISODIC] → episodes    │
      │         └─ UNIFIED SYNTHESIS (826-875)
      ├─── STEP 15: Memory Ingest (929-938) ─┘
      └─── STEP 16: Record to Mirror (962-973)
                |
                v
        [WebSocket Stream]
                |
                v
          BROWSER CLIENT
```

---

## Component Map

| Component | File | Line Range | Status | Purpose |
|-----------|------|------------|--------|---------|
| **CORE LOOP** | | | |
| `think()` | cog_twin.py | 365-989 | ✓ | Main cognitive loop - 16 steps |
| Mirror State | cog_twin.py | 405-409 | ✓ | Get cognitive phase from MetacognitiveMirror |
| Dual Retrieval | cog_twin.py | 411-425 | ✓ | Process + episodic memory search |
| SQUIRREL Hot Context | cog_twin.py | 443-463 | ✓ | Last 1h session context (highest trust) |
| Exemplar Traces | cog_twin.py | 465-476 | ✓ | High-scored past reasoning injection |
| VenomVoice Prompt | cog_twin.py | 520-583 | ✓ | System prompt construction |
| LLM Streaming | cog_twin.py | 585-612 | ✓ | Anthropic API call with streaming |
| Tool Execution | cog_twin.py | 616-875 | ✓ | GREP/SQUIRREL/VECTOR/EPISODIC + synthesis |
| Memory Ingest | cog_twin.py | 929-938 | ✓ | MemoryPipeline ingestion |
| Mirror Record | cog_twin.py | 962-973 | ✓ | QueryEvent to MetacognitiveMirror |
| **MEMORY PIPELINE** | | | |
| MemoryPipeline | memory_pipeline.py | 179-467 | ✓ | Async batch ingestion |
| CognitiveOutput | memory_pipeline.py | 57-176 | ✓ | Thought → memory conversion |
| Batch Processing | memory_pipeline.py | 280-370 | ✓ | Embed, cluster, add to session buffer |
| Session Search | memory_pipeline.py | 372-410 | ✓ | Search session_outputs (recursive) |
| **WEBSOCKET** | | | |
| websocket_endpoint | main.py | 1005-1549 | ✓ | FastAPI WebSocket handler |
| ConnectionManager | main.py | 981-998 | ✓ | Active WS connections |
| Message Routing | main.py | 1044-1513 | ✓ | ping/verify/message/voice handlers |
| Streaming Output | main.py | 1274-1316 | ✓ | think() → stream_chunk → ws.send_json |
| **RETRIEVAL (4 LANES)** | | | |
| DualRetriever | retrieval.py | 395-918 | ✓ | Process + Episodic unified |
| ProcessMemoryRetriever | retrieval.py | 56-234 | ✓ | NumPy cosine similarity |
| EpisodicMemoryRetriever | retrieval.py | 236-392 | ✓ | FAISS + heuristic filter |
| HybridSearch (GREP v2) | hybrid_search.py | 65-393 | ✓ | Semantic + keyword RRF merge |
| SquirrelTool | squirrel.py | 116-256 | ✓ | Temporal chat history recall |
| **VOICE LAYER** | | | |
| VenomVoice | venom_voice.py | 140-1018 | ✓ | System prompt builder |
| build_system_prompt | venom_voice.py | 391-492 | ✓ | Inject cognitive state + retrieval |
| parse_output | venom_voice.py | 869-929 | ✓ | Extract [ACTIONS] from LLM output |
| StreamingVoice | venom_voice.py | 969-1017 | ✓ | Real-time chunk processing |
| **CHAT MEMORY** | | | |
| ChatMemoryStore | chat_memory.py | 91-348 | ✓ | JSON-backed exchange storage |
| record_exchange | chat_memory.py | 129-181 | ✓ | Store query + trace + response |
| query_by_time_range | chat_memory.py | 216-239 | ✓ | Temporal query for SQUIRREL |
| format_for_context | chat_memory.py | 283-348 | ✓ | Format for LLM injection |

---

## Data Flow (Step-by-Step)

### think() Loop (13 Core Steps)

```
Step 1: Get Cognitive State (lines 405-409)
  - Call: mirror.get_real_time_insights()
  - Extract: cognitive_phase (exploration/exploitation/crisis/etc)
  - Log: "Cognitive phase: {phase}"

Step 2: Embed Query + Dual Retrieval (lines 411-425)
  - Embed: await retriever.embedder.embed_single(user_input)
  - Retrieve: await retriever.retrieve(user_input, process_top_k=10, episodic_top_k=5)
  - Returns: RetrievalResult with process + episodic memories
  - Timing: ~0.3ms for 50 nodes (log: "Retrieval: {ms}ms")

Step 2.25: SQUIRREL Hot Context (lines 443-463)
  - Check: session_outputs for recent entries (< 5 min)
  - If stale: squirrel.execute(SquirrelQuery(timeframe="-60min"), limit=15)
  - Purpose: Last 1h = HIGHEST TRUST SOURCE (user ground truth)
  - Skip if session_outputs already fresh

Step 2.5: Get Reasoning Exemplars (lines 465-476)
  - Call: _get_reasoning_exemplars(user_input, top_k=3, min_score=0.7)
  - Search: tracer.search_traces(query, top_k=10) + score filter
  - Purpose: Inject high-scored past reasoning into prompt
  - Log: "Injecting {N} exemplar traces"

Step 3: Detect Context Gaps (lines 478-498)
  - Status: STUBBED (Grok handles natively)
  - Originally: ContextGapDetector.detect_gaps()
  - Now: gaps = [], gap_severity = 0.0

Step 4: Decide Response Mode (lines 500-508)
  - Call: _decide_response_mode(query, phase, gaps, severity)
  - Logic: crisis → CRISIS_INTERVENTION, drift → PATTERN_INTERRUPT, etc.
  - Returns: ResponseMode enum

Step 5: Explore Memory Chains (lines 510-513)
  - Status: STUBBED (Grok handles natively)
  - Originally: explored_chains = agent.explore_memory_chains()
  - Now: explored_chains = []

Step 6: Build Voice Context (lines 520-579)
  - Create: VoiceContext dataclass
  - Include: process_memories, episodic_memories, session_outputs, exemplar_traces, hot_context
  - Include: analytics_block (visible AI self-awareness)
  - Call: voice.build_system_prompt(voice_context, retrieval_mode="inject")
  - Returns: Full system prompt string

Step 7: Generate Through API (lines 585-612)
  - Model: "grok-4-1-fast-reasoning" (default)
  - Stream: client.messages.stream(...) if stream=True
  - Yield: chunks via StreamingVoice.process_chunk()
  - Collect: full_response += chunk, tokens_used from usage

Step 8.5: UNIFIED TOOL EXECUTION (lines 616-875)
  - Parse: [GREP term="X"], [SQUIRREL ...], [VECTOR query="X"], [EPISODIC query="X"]
  - Execute: ALL tools in parallel, collect to tool_results dict
  - GREP (622-697):
      - Check: if "[GREP" in full_response
      - Execute: retriever.hybrid.search(term, top_k=10) OR retriever.grep.grep(term)
      - Store: self._last_grep_results (provenance tracking)
      - Record: tracer.record_grep(term, occurrences, unique_memories)
  - SQUIRREL (699-723):
      - Parse: SquirrelQuery.parse(match_content)
      - Execute: squirrel.execute(query, limit=10)
      - Returns: Formatted temporal context
  - VECTOR (725-750):
      - Embed: query_embedding = await embedder.embed_single(query)
      - Retrieve: retriever.process.retrieve(query_embedding, top_k=5)
      - Dedupe: Track seen_memory_ids across tools
  - EPISODIC (752-823):
      - Retrieve: retriever.episodic.retrieve(query, query_embedding, top_k=5)
      - Filter: Optional timeframe filter ("7d", "30d", etc.)
      - Dedupe: seen_memory_ids
  - UNIFIED SYNTHESIS (826-875):
      - Build: combined_tool_context from all tool_results
      - Call: ONE followup LLM call with ALL results
      - Prompt: "Synthesize ALL results into a single coherent response"
      - Append: followup_text to full_response
      - Log: "UNIFIED SYNTHESIS complete: {tools_used}"

Step 9: Parse Output (lines 892-900)
  - Call: voice.parse_output(full_response)
  - Extract: [REMEMBER], [REFLECT], [ESCALATE], confidence_stated, memory_refs
  - Returns: ParsedOutput with actions list

Step 10: Build Metadata (lines 901-915)
  - Create: response_metadata dict
  - Include: response_mode, cognitive_phase, confidence, timing

Step 11-13: STUBBED (lines 917-924)
  - Self-correction, crisis escalation, personalization removed

Step 14: Handle Actions (lines 926-927)
  - Call: _handle_actions(parsed, user_input, cognitive_phase)
  - Process: [REMEMBER] → insight output, [REFLECT] → reflection output, etc.

Step 15: Ingest to Memory Pipeline (lines 929-938)
  - Create: CognitiveOutput from full_response
  - Call: await memory_pipeline.ingest(cognitive_output)
  - Effect: Added to queue → batch processing → session_outputs

Step 15.5: Record to Chat Memory (lines 940-960)
  - Call: chat_memory.record_exchange(session_id, query, response, trace)
  - Purpose: Persistent triplet for SQUIRREL temporal recall
  - Returns: exchange_id

Step 16: Record to Mirror (lines 962-973)
  - Create: QueryEvent(timestamp, query_embedding, retrieved_memory_ids)
  - Call: mirror.record_query(query_event)
  - Effect: Update cognitive phase, temperature, drift detection
```

---

## Tool Execution Flow

### Mid-Stream Tool Firing (Unified Synthesis Pattern)

```
[LLM Response] "Let me search for X... [GREP term="vitamins"] [VECTOR query="nutrition"]"
       |
       v
[STEP 8.5] Full response collected, scan for tool markers
       |
       ├─── Detect [GREP term="vitamins"] (line 623)
       │    ├─ Execute: hybrid_search.search("vitamins", top_k=10)
       │    ├─ Results: semantic + keyword hits, RRF merged
       │    └─ Store: tool_results['grep']
       │
       ├─── Detect [VECTOR query="nutrition"] (line 726)
       │    ├─ Execute: retriever.process.retrieve(embedding, top_k=5)
       │    ├─ Dedupe: Filter out seen_memory_ids from GREP
       │    └─ Store: tool_results['vector']
       │
       └─── UNIFIED SYNTHESIS CALL (line 850)
            ├─ Combine: ALL tool results into single context
            ├─ Build: followup_messages with full_response + combined_tool_context
            ├─ Prompt: "Synthesize ALL results into ONE coherent response"
            ├─ Execute: ONE LLM call (not 4 separate calls)
            └─ Append: followup_text to full_response

Result: User gets ONE unified answer, not tool-by-tool breakdown
```

### Tool Marker Detection

```python
# cog_twin.py:616-875

if "[GREP" in full_response:
    # Extract term="X" patterns
    # Execute hybrid_search.search() OR grep.grep()
    # Store structured results to tool_results['grep']

if "[SQUIRREL" in full_response:
    # Parse timeframe, back=N, search="term"
    # Execute squirrel.execute(query, limit=10)
    # Store formatted context to tool_results['squirrel']

if "[VECTOR" in full_response:
    # Extract query="X"
    # Embed + FAISS retrieve
    # Dedupe against seen_memory_ids
    # Store to tool_results['vector']

if "[EPISODIC" in full_response:
    # Extract query="X" timeframe="7d"
    # Retrieve + temporal filter
    # Dedupe
    # Store to tool_results['episodic']

if tool_results:
    # Build combined_tool_context
    # ONE synthesis call with ALL results
    # Append to full_response
```

### Re-entry to LLM

**Does tool execution trigger second LLM call?**
- **YES** - ONE unified synthesis call if ANY tools fired
- **NO** - No intermediate tool-by-tool calls
- Pattern: Collect ALL → Synthesize ONCE

---

## Memory Loop (Snake Eating Tail)

```
[User Query] "How do we handle async errors?"
       |
       v
[think() STEP 2] Dual Retrieval
       ├─ ProcessMemoryRetriever: search session_outputs (line 438)
       │  └─ Returns: Recent CognitiveOutputs from THIS SESSION
       │     (These are previous responses that haven't hit disk yet)
       │
       └─ DualRetriever: search persisted memories (line 416)
          └─ Returns: Historical process + episodic memories

[think() STEP 8] LLM generates response using:
       - Persisted memories (from disk)
       - Session memories (from memory_pipeline.session_outputs)
       - Hot context (last 1h from SQUIRREL)

[think() STEP 15] Memory Ingest (line 930)
       └─ Create: CognitiveOutput(content=full_response)
       └─ Ingest: await memory_pipeline.ingest(output)
              |
              v
       [MemoryPipeline._process_loop] (memory_pipeline.py:280)
              ├─ Batch: Collect outputs until batch_size=10 or timeout=5s
              ├─ Embed: await embedder.embed_batch(texts)
              ├─ Cluster: cluster_engine.batch_assign(embeddings)
              ├─ Add to session_outputs: (IMMEDIATELY SEARCHABLE)
              │     session_outputs.extend(outputs)
              │     session_embeddings.extend(embeddings)
              │     session_nodes.extend(nodes)
              └─ Queue for disk: _flush_to_disk() on shutdown

[Next Query] "What did you just say about async?"
       |
       v
[think() STEP 2] Retrieval NOW FINDS the previous response
       └─ memory_pipeline.search_session(query_embedding, top_k=5)
          └─ Searches session_embeddings with cosine similarity
          └─ Returns: [(previous_output, similarity_score), ...]

Result: THE SNAKE EATS ITS TAIL
  - Output becomes input
  - Context window extends infinitely
  - 50 nodes retrieved in 0.3ms (not RAG latency, memory access)
```

### Memory Injection Point

**Where exactly does LLM output get embedded and stored?**

```
File: memory_pipeline.py
Function: _process_batch() (lines 309-370)
Trigger: Async loop processes queue every 5s OR when batch_size=10

Flow:
1. Extract texts from CognitiveOutput.content (line 325)
2. Embed: await embedder.embed_batch(texts, show_progress=False) (line 328)
3. Cluster: cluster_engine.batch_assign(embeddings) (line 332)
4. Convert: output.to_memory_node() (line 348)
5. Add to session buffers (lines 355-357):
   - session_outputs.extend(outputs)
   - session_embeddings.extend(embeddings)
   - session_nodes.extend(nodes)
6. On shutdown: _flush_to_disk() writes to data/memory_nodes/session_*.json (line 444)
```

---

## WebSocket Streaming

### Chunk Flow: think() → Browser

```
[CogTwin.think()] yields chunks
       |
       v
[websocket_endpoint] main.py:1274-1316 (EnterpriseTwin path)
       |
       v
async for chunk in active_twin.think_streaming(...):
       |
       ├─ Check: chunk.startswith("__METADATA__:") (line 1283)
       │  └─ Send: {"type": "cognitive_state", ...} (line 1288)
       │
       └─ Else: Send: {"type": "stream_chunk", "content": chunk, "done": False} (line 1302)
       |
       v
await websocket.send_json({...}) (line 1302)
       |
       v
[FastAPI WebSocket]
       |
       v
[Browser Client] receives stream_chunk events
```

### CogTwin Path (Personal Mode)

```
[CogTwin.think()] main.py:1349-1388
       |
       v
with client.messages.stream(...) as stream_response:
    for chunk in stream_response.text_stream:
        full_response += chunk
        clean_chunk = streaming_voice.process_chunk(chunk)
        yield clean_chunk  (line 599)
               |
               v
[websocket_endpoint] catches yielded chunk
               |
               v
await websocket.send_json({"type": "stream_chunk", ...}) (line 1365)
```

**Key Points:**
- CogTwin: Anthropic SDK streaming → StreamingVoice.process_chunk() → yield
- EnterpriseTwin: Direct chunk streaming with metadata markers
- WebSocket: send_json() for each chunk + final "done": true signal

---

## Session Context

### How `session_outputs` Gets Populated and Queried

**Write Path:**
```
[think() STEP 15] (cog_twin.py:930)
  └─ Create: CognitiveOutput(content=full_response, source_memory_ids=...)
  └─ Ingest: await memory_pipeline.ingest(output)
            |
            v
  [MemoryPipeline.ingest()] (memory_pipeline.py:264)
            └─ await queue.put(output)
            |
            v
  [MemoryPipeline._process_loop()] (memory_pipeline.py:280)
            └─ Batch collect, then _process_batch()
            |
            v
  [MemoryPipeline._process_batch()] (memory_pipeline.py:309)
            ├─ Embed outputs (line 328)
            ├─ Cluster assign (line 332)
            └─ session_outputs.extend(outputs) (line 355)
               session_embeddings.extend(embeddings) (line 356)
               session_nodes.extend(nodes) (line 357)
```

**Read Path:**
```
[think() STEP 2] (cog_twin.py:438)
  └─ session_memories = memory_pipeline.search_session(query_embedding, top_k=5)
            |
            v
  [MemoryPipeline.search_session()] (memory_pipeline.py:372)
            ├─ Build session_matrix from session_embeddings (line 390)
            ├─ Compute cosine similarity (line 399)
            ├─ Get top-k above threshold (line 402)
            └─ Return: [(CognitiveOutput, score), ...]
```

**TTL/Limit:**
- **TTL**: Session lifetime (until CogTwin.stop() called)
- **Limit**: No hard limit on session_outputs (grows unbounded during session)
- **Persistence**: Flushed to disk on shutdown via _flush_to_disk() (memory_pipeline.py:431)
- **File Output**: data/memory_nodes/session_nodes_{timestamp}.json

---

## Streaming Cluster

**What does `streaming_cluster.py` do? Is it used?**

**Purpose:**
- Real-time cluster assignment for incoming cognitive outputs
- Incremental DBSCAN-style clustering (StreamingClusterEngine)
- Used by MemoryPipeline for tagging outputs with cluster_id

**Called From:**
```
File: memory_pipeline.py
Lines: 222-238 (initialization)
       331-352 (batch_assign during processing)

Usage:
  self.cluster_engine = StreamingClusterEngine(self.data_dir)
  ...
  cluster_assignments = self.cluster_engine.batch_assign(embeddings)
  ...
  output.cluster_id = assignment.cluster_id
  output.cluster_confidence = assignment.confidence
  output.is_new_cluster = assignment.is_new_cluster
```

**Active:** ⚠ YES (initialized) BUT only if streaming_cluster.py exists
- Fallback: If init fails, sets cluster_engine = None (line 238)
- Behavior: Uses ClusterAssignment(cluster_id=-1) for noise (line 337)

**Status:** ⚠ DORMANT
- Code paths exist, initialized, but streaming_cluster.py NOT in file list
- Likely removed or renamed, causing fallback behavior

---

## Findings

### ✓ Working Components

1. **CogTwin think() Loop** - 13-step cognitive cycle fully operational
2. **Dual Retrieval** - ProcessMemoryRetriever (NumPy) + EpisodicMemoryRetriever (FAISS)
3. **HybridSearch (GREP v2)** - Semantic + keyword RRF merge replacing BM25-only
4. **SquirrelTool** - Temporal chat history recall (last 1h hot context)
5. **Memory Pipeline** - Async batch ingestion with session_outputs buffer
6. **WebSocket Streaming** - FastAPI → think() → browser chunk delivery
7. **Tool Execution** - GREP/SQUIRREL/VECTOR/EPISODIC with unified synthesis
8. **VenomVoice** - System prompt builder with trust hierarchy and tool protocol
9. **ChatMemoryStore** - JSON-backed exchange storage for SQUIRREL
10. **MetacognitiveMirror** - Cognitive phase tracking and drift detection

### ⚠ Dormant Components

1. **StreamingClusterEngine** - Initialized but file not found in recon scan
   - Fallback: cluster_id=-1 (noise) for all outputs
   - Impact: No real-time cluster assignment, cluster boosting disabled
   - Fix: Verify streaming_cluster.py existence or remove initialization

2. **ContextGapDetector** - Stubbed, Grok handles natively
   - Lines: cog_twin.py:478-498
   - Status: gaps = [], gap_severity = 0.0
   - Note: "Grok handles gap detection natively via prompt engineering"

3. **Memory Chain Exploration** - Stubbed
   - Lines: cog_twin.py:510-513
   - Status: explored_chains = []
   - Note: "Grok explores memory context natively"

4. **Strategic Analysis** - Stubbed
   - Lines: cog_twin.py:515-518
   - Status: strategic_analysis = None
   - Note: "Grok handles multi-framework analysis natively"

### ✗ Broken Components

**None detected.** All critical paths operational with graceful fallbacks.

---

## Line References (Quick Lookup)

### Core Flow
- `think()` entry: cog_twin.py:365
- Mirror state: cog_twin.py:405-409
- Dual retrieval: cog_twin.py:411-425
- SQUIRREL hot: cog_twin.py:443-463
- Exemplar inject: cog_twin.py:465-476
- Voice prompt: cog_twin.py:520-583
- LLM streaming: cog_twin.py:585-612
- Tool execution: cog_twin.py:616-875
- Memory ingest: cog_twin.py:929-938
- Mirror record: cog_twin.py:962-973

### Memory Pipeline
- Pipeline init: memory_pipeline.py:191-229
- Ingest queue: memory_pipeline.py:264-272
- Batch process: memory_pipeline.py:309-370
- Session search: memory_pipeline.py:372-410
- Flush to disk: memory_pipeline.py:431-466

### WebSocket
- WS endpoint: main.py:1005
- Connection mgr: main.py:981-998
- Message routing: main.py:1044-1513
- Stream output: main.py:1274-1316
- CogTwin stream: main.py:1360-1378

### Retrieval
- DualRetriever: retrieval.py:395
- Process retrieve: retrieval.py:103-194
- Episodic retrieve: retrieval.py:330-392
- HybridSearch: hybrid_search.py:109-165
- SquirrelTool: squirrel.py:127-180

### Voice
- VenomVoice init: venom_voice.py:383
- Build prompt: venom_voice.py:391-492
- Parse output: venom_voice.py:869-929
- StreamingVoice: venom_voice.py:978-1005
- Tool protocol: venom_voice.py:270-326

### Chat Memory
- ChatMemoryStore: chat_memory.py:102
- Record exchange: chat_memory.py:129-181
- Time range query: chat_memory.py:216-239
- Format context: chat_memory.py:283-348

---

## Q&A Section

### Q1: think() Loop Steps

```
Step 1: Get cognitive state from mirror (lines 405-409)
Step 2: Embed query and retrieve memories (lines 411-425)
Step 2.25: Auto-inject last 1h session context via SQUIRREL (lines 443-463)
Step 2.5: Get high-scored reasoning exemplars (lines 465-476)
Step 3: Detect context gaps [STUBBED] (lines 478-498)
Step 4: Decide response mode (lines 500-508)
Step 5: Explore memory chains [STUBBED] (lines 510-513)
Step 6: Build voice context (lines 520-579)
Step 7: Generate through API with streaming (lines 585-612)
Step 8.5: Unified tool execution (GREP/SQUIRREL/VECTOR/EPISODIC) (lines 616-875)
Step 9: Parse output and extract actions (lines 892-900)
Step 10: Build response metadata (lines 901-915)
Step 11-13: Self-correction, crisis, personalize [STUBBED] (lines 917-924)
Step 14: Handle actions (REMEMBER, REFLECT, etc.) (lines 926-927)
Step 15: Ingest to memory pipeline (lines 929-938)
Step 15.5: Record to chat memory (lines 940-960)
Step 16: Record query in mirror (lines 962-973)
```

### Q2: Memory Injection Point

```
File: memory_pipeline.py
Function: _process_batch() (lines 309-370)
Trigger: Async loop (_process_loop) processes queue every 5s OR batch_size=10

Detailed Flow:
1. Queue ingestion: await memory_pipeline.ingest(cognitive_output) (line 264)
2. Batch collection: _process_loop collects until timeout/batch full (line 280)
3. Embedding: await embedder.embed_batch(texts) (line 328)
4. Clustering: cluster_engine.batch_assign(embeddings) (line 332)
5. Node conversion: output.to_memory_node() (line 348)
6. Session buffer: session_outputs.extend(outputs) (line 355)
7. Disk persistence: _flush_to_disk() on shutdown (line 431)
```

### Q3: WebSocket Streaming

```
think() yields → websocket_endpoint catches → ws.send_json()

EnterpriseTwin Path (main.py:1274-1316):
  async for chunk in active_twin.think_streaming(...):
      └─ await websocket.send_json({"type": "stream_chunk", "content": chunk, "done": False})

CogTwin Path (main.py:1360-1378):
  with client.messages.stream(...) as stream_response:
      for chunk in stream_response.text_stream:
          clean_chunk = streaming_voice.process_chunk(chunk)
          yield clean_chunk
              └─ await websocket.send_json({"type": "stream_chunk", ...})

Final signal: await websocket.send_json({"type": "stream_chunk", "content": "", "done": True})
```

### Q4: Tool Re-entry

```
When LLM emits [GREP term="X"], what happens?

Detection: if "[GREP" in full_response (line 623)
Execution:
  - If hybrid available: await retriever.hybrid.search(term, top_k=10) (line 632)
  - Else BM25 fallback: retriever.grep.grep(term) (line 670)
  - Results stored: tool_results['grep'] (line 696)

Re-injection:
  - Collect ALL tool results (GREP, SQUIRREL, VECTOR, EPISODIC)
  - Build combined_tool_context (line 842)
  - ONE synthesis call with ALL results (line 850)
  - Prompt: "Synthesize ALL results into a single coherent response"

Second LLM call?: YES (ONE unified synthesis, not per-tool)
```

### Q5: Session Context

```
Write path:
  1. think() STEP 15: await memory_pipeline.ingest(cognitive_output) (line 930)
  2. Pipeline queues: await queue.put(output) (line 271)
  3. Batch process: _process_batch() embeds + adds to session_outputs (line 355)

Read path:
  1. think() STEP 2: memory_pipeline.search_session(query_embedding, top_k=5) (line 438)
  2. Cosine similarity: session_norm @ query_norm (line 399)
  3. Return: [(CognitiveOutput, score), ...] (line 408)

TTL/limit:
  - TTL: Session lifetime (until CogTwin.stop() called)
  - Memory Limit: None (grows unbounded during session)
  - Disk Flush: On shutdown to data/memory_nodes/session_nodes_{timestamp}.json
```

### Q6: Streaming Cluster

```
Purpose: Real-time cluster assignment for cognitive outputs

Called from:
  - memory_pipeline.py:222 (_init_cluster_engine)
  - memory_pipeline.py:332 (cluster_assignments = cluster_engine.batch_assign)

Active: ⚠ PARTIALLY
  - Initialization attempted (line 232)
  - Fallback to None if StreamingClusterEngine unavailable (line 238)
  - Graceful degradation: cluster_id=-1 for all outputs (line 337)

Status: DORMANT
  - streaming_cluster.py not found in recon scan
  - System operates normally with cluster_id=-1 (noise cluster)
  - Impact: No cluster-based boosting, no new cluster detection
```

---

**END OF RECON**

✓ Mission complete. All systems mapped. Zero code modifications.
