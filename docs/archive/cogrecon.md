# RECON MISSION: Cognitive Streaming Pipeline

## OBJECTIVE
Map the existing CogTwin streaming architecture. This WORKED before. Find it, diagram it, report back.

---

## SCOPE

**Find and document:**
1. The `think()` loop in `cog_twin.py` - full async flow
2. Memory pipeline injection (outputs → inputs)
3. WebSocket streaming in `main.py`
4. Streaming cluster / real-time clustering
5. Tool execution mid-stream (GREP, SQUIRREL, VECTOR, EPISODIC)

**DO NOT:**
- Modify any code
- Suggest improvements
- Write prose explanations

---

## OUTPUT FORMAT

### Required Diagrams (ASCII)

```
DIAGRAM 1: think() Flow
========================
[boxes and arrows showing the 13-step loop]

DIAGRAM 2: Memory Injection
===========================
[how outputs become searchable inputs]

DIAGRAM 3: WebSocket Stream
===========================
[main.py → client data flow]

DIAGRAM 4: Tool Execution
=========================
[when/how GREP/SQUIRREL/VECTOR fire mid-response]
```

### Required Tables

| Component | File | Line Range | Status |
|-----------|------|------------|--------|
| ...       | ...  | ...        | ✓/✗/⚠  |

---

## FILES TO EXAMINE

```bash
# Core pipeline
core/cog_twin.py           # think() method - THE BRAIN
core/venom_voice.py        # Prompt building, action parsing
core/streaming_cluster.py  # Real-time clustering

# Memory loop
memory/memory_pipeline.py  # CognitiveOutput, batch ingest
memory/chat_memory.py      # ChatMemoryStore, exchanges
memory/squirrel.py         # Temporal recall tool

# WebSocket
core/main.py               # websocket_endpoint handler

# Supporting
memory/hybrid_search.py    # GREP/vector fusion
memory/retrieval.py        # DualRetriever
```

---

## SPECIFIC QUESTIONS TO ANSWER

### Q1: think() Loop Steps
List each step in order with line numbers:
```
Step 1: _____ (lines X-Y)
Step 2: _____ (lines X-Y)
...
```

### Q2: Memory Injection Point
Where exactly does LLM output get embedded and stored?
```
File: _____
Function: _____
Trigger: _____
```

### Q3: WebSocket Streaming
How do chunks flow from `think()` to browser?
```
think() yields → _____ → _____ → ws.send_json()
```

### Q4: Tool Re-entry
When LLM emits `[GREP term="X"]`, what happens?
```
Detection: _____
Execution: _____
Re-injection: _____
Second LLM call?: YES/NO
```

### Q5: Session Context
How does `session_outputs` get populated and queried?
```
Write path: _____
Read path: _____
TTL/limit: _____
```

### Q6: Streaming Cluster
What does `streaming_cluster.py` actually do? Is it used?
```
Purpose: _____
Called from: _____
Active: YES/NO
```

---

## EXECUTION COMMANDS

```bash
# Run from project root

# 1. Map think() method
grep -n "async def think\|STEP\|=====" core/cog_twin.py | head -60

# 2. Find memory injection
grep -n "ingest\|memory_pipeline\|CognitiveOutput" core/cog_twin.py

# 3. WebSocket handler
grep -n "websocket_endpoint\|think(\|yield\|send_json" core/main.py | head -50

# 4. Tool execution
grep -n "\[GREP\|\[SQUIRREL\|\[VECTOR\|tool_results" core/cog_twin.py

# 5. Session context
grep -n "session_outputs\|search_session" core/cog_twin.py memory/memory_pipeline.py

# 6. Streaming cluster usage
grep -rn "streaming_cluster\|StreamingCluster" core/ memory/
```

---

## DELIVERABLE

Single markdown file: `RECON_STREAMING_PIPELINE.md`

Structure:
```
# Streaming Pipeline Recon

## Status: [HEALTHY/DEGRADED/BROKEN]

## Architecture Diagram
[ASCII diagram of full flow]

## Component Map
[Table of all pieces]

## Data Flow
[Step-by-step with line refs]

## Tool Execution Flow
[Diagram of mid-stream tools]

## Memory Loop
[Diagram of snake-eating-tail]

## Findings
- ✓ Working: [list]
- ⚠ Dormant: [list]  
- ✗ Broken: [list]

## Line References
[Quick lookup table]
```

---

## SUCCESS CRITERIA

- [ ] All 6 questions answered with line numbers
- [ ] 4+ ASCII diagrams
- [ ] Component status table complete

