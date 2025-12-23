# T4: Memory RAG - CogTwin Retrieval

## Overview
5-lane retrieval system: FAISS vector search, BM25 grep, episodic conversations, temporal squirrel, and unified search.

---

## 🧠 Architecture

```
Query → [VECTOR] → FAISS semantic similarity
      → [GREP]   → BM25/PostgreSQL full-text
      → [EPISODIC] → Full conversation arcs
      → [SQUIRREL] → Recent session (last N hours)
      → [SEARCH] → Unified multi-lane
```

**Trust hierarchy**: Squirrel > Episodic > Vector > Grep

---

## 🎯 Lane 1: Vector Search (Semantic)

```python
@tool(name="memory_vector", ...)
async def memory_vector(args: dict):
    query = args["query"]
    top_k = args.get("top_k", 10)
    threshold = args.get("threshold", 0.5)

    # Get embedding via DeepInfra BGE-M3
    embedding = get_embedding(query)

    # Load FAISS index
    index = faiss.read_index("data/faiss_index.bin")
    metadata = json.load(open("data/memory_metadata.json"))

    # Search
    query_vec = np.array([embedding], dtype=np.float32)
    distances, indices = index.search(query_vec, top_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        score = 1 - dist  # Convert distance to similarity
        if score >= threshold:
            results.append({
                "score": score,
                "human": metadata[idx]["human_content"],
                "assistant": metadata[idx]["assistant_content"],
                "timestamp": metadata[idx]["created_at"]
            })

    return {"results": results}
```

**Use when**: Semantic search, finding conceptually similar memories

---

## 🔍 Lane 2: Grep Search (Keyword)

```python
@tool(name="memory_grep", ...)
async def memory_grep(args: dict):
    term = args["term"]
    max_results = args.get("max_results", 20)

    # PostgreSQL full-text search
    query = """
        SELECT id, human_content, assistant_content, created_at,
               ts_rank(to_tsvector('english', content),
                       plainto_tsquery('english', %s)) as score
        FROM memory.nodes
        WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
        ORDER BY score DESC, created_at DESC
        LIMIT %s
    """

    cur.execute(query, (term, term, max_results))
    hits = cur.fetchall()

    return {"hits": hits}
```

**Use when**: Exact term matching, verifying frequency, finding co-occurrences

---

## 📖 Lane 3: Episodic Search (Conversations)

```python
@tool(name="memory_episodic", ...)
async def memory_episodic(args: dict):
    query = args["query"]
    timeframe = args.get("timeframe", "all")  # all/week/month/quarter
    top_k = args.get("top_k", 5)

    # Load episodes
    episodes = json.load(open("data/episodes.json"))

    # Filter by timeframe
    if timeframe != "all":
        cutoff = datetime.now() - timedelta(days=TIMEFRAME_DAYS[timeframe])
        episodes = [ep for ep in episodes
                   if parse_datetime(ep["created_at"]) > cutoff]

    # Keyword match on title + summary
    query_terms = query.lower().split()
    scored = []
    for ep in episodes:
        text = f"{ep['title']} {ep['summary']}".lower()
        score = sum(1 for term in query_terms if term in text)
        if score > 0:
            scored.append((score, ep))

    scored.sort(reverse=True)
    return {"episodes": [ep for _, ep in scored[:top_k]]}
```

**Use when**: Finding project context, "what were we working on", interrupted work

---

## 🐿️ Lane 4: Squirrel (Temporal Recall)

```python
@tool(name="memory_squirrel", ...)
async def memory_squirrel(args: dict):
    hours_back = args.get("hours_back", 1)
    search = args.get("search")
    limit = args.get("limit", 20)

    cutoff = datetime.now() - timedelta(hours=hours_back)

    # Load session outputs
    outputs = json.load(open("data/session_outputs.json"))

    items = []
    for output in outputs:
        ts = parse_datetime(output["timestamp"])
        if ts < cutoff:
            continue

        content = output["content"]
        if search and search.lower() not in content.lower():
            continue

        items.append({
            "timestamp": output["timestamp"],
            "content": content[:400],
            "type": output["thought_type"]
        })

        if len(items) >= limit:
            break

    return {"items": items}
```

**Use when**: "What was that from an hour ago?", recent session context

---

## 🔎 Lane 5: Unified Search

```python
@tool(name="memory_search", ...)
async def memory_search(args: dict):
    query = args["query"]
    lanes = args.get("lanes", "all")  # "all" or "vector,grep,episodic"

    results = {}

    if "vector" in lanes:
        results["vector"] = await memory_vector({"query": query, "top_k": 3})

    if "grep" in lanes:
        first_term = query.split()[0]
        results["grep"] = await memory_grep({"term": first_term, "max_results": 3})

    if "episodic" in lanes:
        results["episodic"] = await memory_episodic({"query": query, "top_k": 2})

    if "squirrel" in lanes:
        results["squirrel"] = await memory_squirrel({"hours_back": 24, "search": query.split()[0]})

    return results
```

**Use when**: Not sure which lane to use, exploratory search

---

## 🔧 Embedding Generation

```python
import httpx

def get_embedding(text: str) -> list[float]:
    """Generate BGE-M3 embedding via DeepInfra."""
    api_key = os.getenv("DEEPINFRA_API_KEY")

    response = httpx.post(
        "https://api.deepinfra.com/v1/inference/BAAI/bge-m3",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"inputs": [text]},
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()["embeddings"][0]
```

**Model**: BAAI/bge-m3 (1024 dimensions)
**Cost**: ~$0.0001 per 1K tokens

---

## 📊 FAISS Index Structure

```python
import faiss
import numpy as np

# Create index
dimension = 1024
index = faiss.IndexFlatL2(dimension)  # L2 distance

# Add vectors
embeddings = np.array(embeddings_list, dtype=np.float32)
index.add(embeddings)

# Save
faiss.write_index(index, "faiss_index.bin")

# Load
index = faiss.read_index("faiss_index.bin")

# Search
query_vec = np.array([embedding], dtype=np.float32)
distances, indices = index.search(query_vec, k=10)
```

---

## 🎯 Lane Selection Guide

| Need | Lane | Why |
|------|------|-----|
| Concept similarity | Vector | BGE-M3 semantic embedding |
| Exact term | Grep | BM25 keyword matching |
| Project context | Episodic | Full conversation arcs |
| Recent memory | Squirrel | Last N hours, highest trust |
| Not sure | Search | Try all lanes |

---

## 🔧 Environment Setup

```bash
# .env
DEEPINFRA_API_KEY=xxx  # For embeddings
AZURE_PG_HOST=xxx      # For grep lane (optional)
AZURE_PG_USER=xxx
AZURE_PG_PASSWORD=xxx
COGTWIN_DATA_DIR=./data  # Where FAISS index lives
```

---

## 📁 Data Structure

```
data/
├── faiss_index.bin           # FAISS vector index
├── memory_metadata.json      # [{id, human_content, assistant_content, timestamp}]
├── episodes.json             # [{id, title, summary, message_count, created_at}]
└── session_outputs.json      # [{timestamp, content, thought_type}]
```

---

## 🚨 Error Handling

```python
# FAISS not available
if not os.path.exists("data/faiss_index.bin"):
    return {
        "error": "FAISS index not found. Run memory ingestion first.",
        "fallback": "Use memory_grep for keyword search instead."
    }

# Embedding service down
if embedding is None:
    return {
        "error": "Embedding service not available. Check DEEPINFRA_API_KEY.",
        "fallback": "Use memory_grep for keyword search."
    }
```

---

## 📖 Ingestion Pipeline

```python
# 1. Extract Q/A pairs from conversation
# 2. Generate embeddings for each pair
# 3. Build FAISS index
# 4. Store metadata alongside

from memory.ingest import ingest_conversation

ingest_conversation(
    conversation_json="chat_export.json",
    output_dir="data/"
)
```

---

*CogTwin RAG is a 5-lane retrieval system optimized for chat memory. Trust decreases: Squirrel > Episodic > Vector > Grep.*
