# RECON MISSION: CogTwin Memory Architecture Deep Dive

## MISSION OBJECTIVE
Map the COMPLETE memory architecture of CogTwin. Every file, every pipeline, every wire. We need a full topographical map before designing the next evolution.

---

## PARALLEL AGENT DEPLOYMENT

### AGENT 1: Core Orchestrators
**Files to analyze:**
- `cog_twin.py` - Personal cognitive twin orchestrator
- `venom_voice.py` - Voice/personality layer
- `enterprise_twin.py` - Enterprise fork orchestrator

**Extract:**
- All imports (especially memory-related)
- How each orchestrator calls memory systems
- Config loading patterns
- Differences between personal vs enterprise mode
- Entry points and exit points
- What triggers memory reads vs writes

**Output format:**
```
ORCHESTRATOR: [filename]
IMPORTS: [list all memory-related imports]
MEMORY_READ_CALLS: [function -> what it calls -> what it expects back]
MEMORY_WRITE_CALLS: [function -> what it writes -> where]
CONFIG_SOURCES: [where does it get config from]
MODE_SWITCHES: [how does it know personal vs enterprise]
```

---

### AGENT 2: Memory Pipeline Files
**Files to analyze:**
- `memory_pipeline.py` - Main pipeline orchestrator
- `memory_backend.py` - Storage abstraction
- `chat_memory.py` - Conversation memory
- `retrieval.py` - Retrieval orchestration

**Extract:**
- Pipeline stages (ingest -> process -> store -> retrieve)
- What each stage inputs/outputs
- Database calls (table names, queries)
- Vector operations (embeddings, similarity)
- Caching layers

**Output format:**
```
FILE: [filename]
PURPOSE: [one-line description]
PIPELINE_STAGE: [ingest/process/store/retrieve/orchestrate]
INPUTS: [what data comes in, from where]
OUTPUTS: [what data goes out, to where]
DB_TABLES: [tables touched]
VECTOR_OPS: [embedding/similarity operations]
DEPENDENCIES: [other memory files it imports]
```

---

### AGENT 3: Retrieval Lanes (The 5-Lane System)
**Files to analyze:**
- `hybrid_search.py` - Multi-lane search orchestrator
- `fast_filter.py` - BM25/keyword lane
- `scoring.py` - Result scoring/ranking
- `embedder.py` - Embedding generation
- `streaming_cluster.py` - Cluster-based retrieval

**Extract:**
- Each retrieval lane's purpose
- How lanes are combined/weighted
- Scoring algorithms
- Threshold configurations
- Performance characteristics

**Output format:**
```
LANE: [name]
FILE: [filename]
PURPOSE: [what type of memory does it find]
ALGORITHM: [BM25/vector/temporal/etc]
INPUTS: [query format expected]
OUTPUTS: [result format returned]
WEIGHTS: [how is it weighted in final results]
THRESHOLDS: [any cutoff values]
```

---

### AGENT 4: Specialized Memory Systems
**Files to analyze:**
- `squirrel.py` - Temporal "what did we discuss an hour ago" recall
- `memory_grep.py` - Pattern-based memory search
- `metacognitive_mirror.py` - Self-reflection/reasoning traces
- `reasoning_trace.py` - Reasoning capture
- `read_traces.py` - Trace retrieval

**Extract:**
- What makes each system unique
- When each system is triggered
- Data structures used
- How they integrate with main pipeline

**Output format:**
```
SYSTEM: [name]
FILE: [filename]
UNIQUE_PURPOSE: [what can ONLY this system do]
TRIGGER_CONDITIONS: [when is it called]
DATA_STRUCTURE: [how does it store/retrieve]
INTEGRATION_POINT: [where does it plug into main pipeline]
```

---

### AGENT 5: Processing & Enrichment
**Files to analyze:**
- `llm_tagger.py` - LLM-based tagging
- `heuristic_enricher.py` - Rule-based enrichment
- `cluster_schema.py` - Cluster definitions
- `dedup.py` - Deduplication logic
- `evolution_engine.py` - Memory evolution/consolidation

**Extract:**
- Processing stages
- What metadata gets added
- Clustering logic
- Dedup strategies
- How memories evolve over time

**Output format:**
```
PROCESSOR: [name]
FILE: [filename]
STAGE: [pre-store/post-store/periodic]
INPUT: [raw data format]
OUTPUT: [enriched data format]
METADATA_ADDED: [what fields get added]
TRIGGERS: [sync/async/batch]
```

---

### AGENT 6: Configuration & Database Schema
**Files to analyze:**
- `config.yaml` - Main configuration
- `config_loader.py` - Config parsing
- `postgres.py` - Database operations
- `protocols.py` - Nuclear elements/core knowledge
- `schemas.py` - Pydantic models
- All migration files in `migrations/`

**Extract:**
- All config keys related to memory
- Feature flags for personal vs enterprise
- Database schema for memory tables
- Vector column definitions
- Index strategies

**Output format:**
```
CONFIG_SECTION: [section name]
KEYS: [list of keys with descriptions]
PERSONAL_VS_ENTERPRISE: [what differs between modes]

DB_TABLE: [table name]
COLUMNS: [column definitions]
VECTOR_COLUMNS: [which columns are vectors, dimensions]
INDEXES: [index definitions]
RELATIONSHIPS: [foreign keys]
```

---

## SYNTHESIS REQUIREMENTS

After all agents complete, synthesize into:

### 1. WIRING DIAGRAM
```
[User Query] 
    ↓
[Orchestrator: cog_twin.py OR enterprise_twin.py]
    ↓
[Memory Pipeline Entry Point]
    ↓
[Lane 1: ???] → [weight: ???]
[Lane 2: ???] → [weight: ???]
[Lane 3: ???] → [weight: ???]
[Lane 4: ???] → [weight: ???]
[Lane 5: ???] → [weight: ???]
    ↓
[Scoring/Ranking]
    ↓
[Context Assembly]
    ↓
[LLM Call]
    ↓
[Response + Memory Write]
```

### 2. DATA FLOW MAP
For each memory node, trace:
- Where does it originate (chat, document, reasoning trace)?
- What processing does it go through?
- Where does it get stored?
- How does it get retrieved?
- When does it evolve/consolidate?

### 3. CONFIG SEPARATION MATRIX
| Config Key | Personal Mode | Enterprise Mode | Notes |
|------------|---------------|-----------------|-------|
| ... | ... | ... | ... |

### 4. DATABASE SCHEMA SUMMARY
All memory-related tables with relationships

### 5. GAPS & OPPORTUNITIES
Based on architecture review:
- What's missing?
- What's redundant?
- What could be optimized?
- What's the weakest lane?

---

## EXECUTION COMMAND

```bash
python claude_sdk_toolkit/claude_cli.py run -f RECON_MEMORY_ARCHITECTURE.md
```

---

## DELIVERABLE

Single consolidated `MEMORY_ARCHITECTURE_MAP.md` with:
1. Wiring diagram
2. Per-file analysis summaries
3. Data flow maps
4. Config matrix
5. Schema summary
6. Identified gaps/opportunities

This becomes the blueprint for our design session.
