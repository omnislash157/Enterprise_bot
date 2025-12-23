"""
Memory Tools - SDK Compatible Wrappers

Direct access to all 5 CogTwin RAG retrieval lanes as SDK-native tools.

Lanes:
    memory_vector: FAISS semantic similarity search
    memory_grep: BM25/keyword search with co-occurrence
    memory_episodic: Full conversation arc retrieval
    memory_squirrel: Temporal recall (last N hours)
    memory_search: Unified search across all lanes
"""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from claude_agent_sdk import tool

# Memory backends - try imports
FAISS_AVAILABLE = False
POSTGRES_AVAILABLE = False

try:
    import numpy as np
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    pass

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    pass

# =============================================================================
# CONFIG
# =============================================================================

MEMORY_DATA_DIR = os.getenv("COGTWIN_DATA_DIR", "./data")
EMBEDDING_DIM = 1024  # BGE-M3


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_db_connection():
    """Get PostgreSQL connection for memory queries."""
    if not POSTGRES_AVAILABLE:
        return None

    return psycopg2.connect(
        host=os.getenv("AZURE_PG_HOST", "localhost"),
        port=int(os.getenv("AZURE_PG_PORT", "5432")),
        database=os.getenv("AZURE_PG_DATABASE", "postgres"),
        user=os.getenv("AZURE_PG_USER", "postgres"),
        password=os.getenv("AZURE_PG_PASSWORD", ""),
        sslmode=os.getenv("AZURE_PG_SSLMODE", "require"),
    )


def get_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding via DeepInfra BGE-M3."""
    api_key = os.getenv("DEEPINFRA_API_KEY")
    if not api_key:
        return None

    try:
        import httpx
        response = httpx.post(
            "https://api.deepinfra.com/v1/inference/BAAI/bge-m3",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"inputs": [text]},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["embeddings"][0]
    except Exception:
        return None


# =============================================================================
# SDK TOOLS
# =============================================================================

@tool(
    name="memory_vector",
    description="Semantic similarity search across memory using FAISS vector search - finds conceptually similar memories even without exact word matches",
    input_schema={"query": str, "top_k": int, "threshold": float}
)
async def memory_vector(args: dict) -> Dict[str, Any]:
    """Semantic similarity search across memory nodes using FAISS."""
    query = args.get("query", "")
    top_k = args.get("top_k", 10)
    threshold = args.get("threshold", 0.5)

    if not query:
        return {
            "content": [{"type": "text", "text": "Error: query parameter is required"}],
            "isError": True
        }

    # Get query embedding
    embedding = get_embedding(query)
    if embedding is None:
        return {
            "content": [{"type": "text", "text": "Error: Embedding service not available. Set DEEPINFRA_API_KEY environment variable."}],
            "isError": True
        }

    # Try FAISS index
    index_path = os.path.join(MEMORY_DATA_DIR, "faiss_index.bin")
    metadata_path = os.path.join(MEMORY_DATA_DIR, "memory_metadata.json")

    if not os.path.exists(index_path):
        return {
            "content": [{"type": "text", "text": f"FAISS index not found at {index_path}. Run memory ingestion pipeline first."}],
            "isError": True
        }

    try:
        # Load index and metadata
        index = faiss.read_index(index_path)
        with open(metadata_path) as f:
            metadata = json.load(f)

        # Search
        query_vec = np.array([embedding], dtype=np.float32)
        distances, indices = index.search(query_vec, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(metadata):
                continue

            score = 1 - dist  # Convert distance to similarity
            if score < threshold:
                continue

            mem = metadata[idx]
            results.append({
                "score": round(float(score), 3),
                "human": mem.get("human_content", "")[:200],
                "assistant": mem.get("assistant_content", "")[:200],
                "timestamp": mem.get("created_at", "unknown"),
                "cluster": mem.get("cluster_label"),
            })

        if not results:
            return {
                "content": [{"type": "text", "text": f"No memories found matching '{query}' with threshold {threshold}"}]
            }

        result_text = f"🧠 Vector Search Results for: '{query}'\nFound {len(results)} matches\n\n"

        for i, r in enumerate(results, 1):
            result_text += f"{i}. Score: {r['score']}\n"
            result_text += f"   Human: {r['human']}\n"
            result_text += f"   Assistant: {r['assistant']}\n"
            result_text += f"   Time: {r['timestamp']}\n\n"

        return {
            "content": [{"type": "text", "text": result_text}]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error during vector search: {str(e)}"}],
            "isError": True
        }


@tool(
    name="memory_grep",
    description="Keyword/BM25 search across memory content - finds exact and fuzzy term matches, good for specific mentions",
    input_schema={"term": str, "context_chars": int, "max_results": int}
)
async def memory_grep(args: dict) -> Dict[str, Any]:
    """Keyword/BM25 search across memory content."""
    term = args.get("term", "")
    context_chars = args.get("context_chars", 150)
    max_results = args.get("max_results", 20)

    if not term:
        return {
            "content": [{"type": "text", "text": "Error: term parameter is required"}],
            "isError": True
        }

    # Try PostgreSQL full-text search first
    if POSTGRES_AVAILABLE:
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    id,
                    human_content,
                    assistant_content,
                    created_at,
                    ts_rank(
                        to_tsvector('english', coalesce(human_content, '') || ' ' || coalesce(assistant_content, '')),
                        plainto_tsquery('english', %s)
                    ) as score
                FROM memory.nodes
                WHERE
                    to_tsvector('english', coalesce(human_content, '') || ' ' || coalesce(assistant_content, ''))
                    @@ plainto_tsquery('english', %s)
                ORDER BY score DESC, created_at DESC
                LIMIT %s
            """

            cur.execute(query, (term, term, max_results))
            rows = cur.fetchall()

            if not rows:
                return {
                    "content": [{"type": "text", "text": f"No memories found containing '{term}'"}]
                }

            result_text = f"🔍 Grep Results for: '{term}'\nFound {len(rows)} matches\n\n"

            for i, row in enumerate(rows, 1):
                content = f"{row['human_content']} {row['assistant_content']}"
                term_lower = term.lower()
                pos = content.lower().find(term_lower)

                if pos >= 0:
                    start = max(0, pos - context_chars // 2)
                    end = min(len(content), pos + len(term) + context_chars // 2)
                    snippet = content[start:end]
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(content):
                        snippet = snippet + "..."
                else:
                    snippet = content[:context_chars] + "..."

                result_text += f"{i}. Score: {round(row['score'], 3)}\n"
                result_text += f"   {snippet}\n"
                result_text += f"   Time: {row['created_at'].isoformat()}\n\n"

            cur.close()
            conn.close()

            return {
                "content": [{"type": "text", "text": result_text}]
            }

        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"PostgreSQL search failed: {str(e)}. Falling back to file search."}],
                "isError": True
            }

    # Fallback: file-based grep
    metadata_path = os.path.join(MEMORY_DATA_DIR, "memory_metadata.json")

    if not os.path.exists(metadata_path):
        return {
            "content": [{"type": "text", "text": f"Memory metadata not found at {metadata_path}"}],
            "isError": True
        }

    try:
        with open(metadata_path) as f:
            memories = json.load(f)

        term_lower = term.lower()
        hits = []

        for mem in memories:
            content = f"{mem.get('human_content', '')} {mem.get('assistant_content', '')}"

            if term_lower in content.lower():
                pos = content.lower().find(term_lower)
                start = max(0, pos - context_chars // 2)
                end = min(len(content), pos + len(term) + context_chars // 2)
                snippet = content[start:end]

                hits.append({
                    "snippet": f"...{snippet}...",
                    "timestamp": mem.get("created_at", "unknown"),
                })

                if len(hits) >= max_results:
                    break

        if not hits:
            return {
                "content": [{"type": "text", "text": f"No memories found containing '{term}'"}]
            }

        result_text = f"🔍 File Grep Results for: '{term}'\nFound {len(hits)} matches\n\n"
        for i, hit in enumerate(hits, 1):
            result_text += f"{i}. {hit['snippet']}\n   Time: {hit['timestamp']}\n\n"

        return {
            "content": [{"type": "text", "text": result_text}]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"File search error: {str(e)}"}],
            "isError": True
        }


@tool(
    name="memory_episodic",
    description="Search full conversation arcs/episodes - finds complete project contexts and conversation threads",
    input_schema={"query": str, "timeframe": str, "top_k": int}
)
async def memory_episodic(args: dict) -> Dict[str, Any]:
    """Search full conversation arcs (episodic memory)."""
    query = args.get("query", "")
    timeframe = args.get("timeframe", "all")  # all, week, month, quarter
    top_k = args.get("top_k", 5)

    if not query:
        return {
            "content": [{"type": "text", "text": "Error: query parameter is required"}],
            "isError": True
        }

    episodes_path = os.path.join(MEMORY_DATA_DIR, "episodes.json")

    if not os.path.exists(episodes_path):
        return {
            "content": [{"type": "text", "text": f"Episodes not found at {episodes_path}. Run episodic memory ingestion first."}],
            "isError": True
        }

    try:
        with open(episodes_path) as f:
            episodes = json.load(f)

        # Filter by timeframe
        now = datetime.now()
        if timeframe == "week":
            cutoff = now - timedelta(days=7)
        elif timeframe == "month":
            cutoff = now - timedelta(days=30)
        elif timeframe == "quarter":
            cutoff = now - timedelta(days=90)
        else:
            cutoff = None

        if cutoff:
            episodes = [
                ep for ep in episodes
                if ep.get("created_at") and
                datetime.fromisoformat(ep["created_at"].replace("Z", "+00:00")) > cutoff
            ]

        # Simple keyword matching
        query_terms = query.lower().split()
        scored = []

        for ep in episodes:
            text = f"{ep.get('title', '')} {ep.get('summary', '')}".lower()
            score = sum(1 for term in query_terms if term in text)
            if score > 0:
                scored.append((score, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_episodes = scored[:top_k]

        if not top_episodes:
            return {
                "content": [{"type": "text", "text": f"No episodes found matching '{query}' in timeframe '{timeframe}'"}]
            }

        result_text = f"📖 Episodic Memory for: '{query}'\nFound {len(top_episodes)} episodes\n\n"

        for i, (score, ep) in enumerate(top_episodes, 1):
            result_text += f"{i}. {ep.get('title', 'Untitled')}\n"
            result_text += f"   Score: {score} | Messages: {ep.get('message_count', 0)}\n"
            result_text += f"   {ep.get('summary', '')[:200]}\n"
            result_text += f"   Time: {ep.get('created_at', 'unknown')}\n\n"

        return {
            "content": [{"type": "text", "text": result_text}]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Episodic search error: {str(e)}"}],
            "isError": True
        }


@tool(
    name="memory_squirrel",
    description="Temporal recall - get recent session context from last N hours. Highest trust source for 'what was that thing from earlier?'",
    input_schema={"hours_back": int, "search": str, "limit": int}
)
async def memory_squirrel(args: dict) -> Dict[str, Any]:
    """Temporal recall - get recent session context."""
    hours_back = args.get("hours_back", 1)
    search = args.get("search")
    limit = args.get("limit", 20)

    session_path = os.path.join(MEMORY_DATA_DIR, "session_outputs.json")
    cutoff = datetime.now() - timedelta(hours=hours_back)
    items = []

    # Try session file
    if os.path.exists(session_path):
        try:
            with open(session_path) as f:
                outputs = json.load(f)

            for output in outputs:
                ts_str = output.get("timestamp")
                if not ts_str:
                    continue

                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts.tzinfo:
                        ts = ts.replace(tzinfo=None)
                except:
                    continue

                if ts < cutoff:
                    continue

                content = output.get("content", "")

                if search and search.lower() not in content.lower():
                    continue

                items.append({
                    "timestamp": ts_str,
                    "content": content[:300],
                    "type": output.get("thought_type", "unknown"),
                })

                if len(items) >= limit:
                    break

        except Exception:
            pass

    # Also try PostgreSQL
    if POSTGRES_AVAILABLE and len(items) < limit:
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT content, created_at, thought_type
                FROM memory.session_outputs
                WHERE created_at > %s
            """
            params = [cutoff]

            if search:
                query += " AND content ILIKE %s"
                params.append(f"%{search}%")

            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit - len(items))

            cur.execute(query, params)

            for row in cur.fetchall():
                items.append({
                    "timestamp": row["created_at"].isoformat(),
                    "content": row["content"][:300],
                    "type": row.get("thought_type", "unknown"),
                })

            cur.close()
            conn.close()

        except:
            pass

    if not items:
        return {
            "content": [{"type": "text", "text": f"No recent items found in last {hours_back} hours"}]
        }

    result_text = f"🐿️ Squirrel Recall (last {hours_back}h)\nFound {len(items)} items\n\n"

    for i, item in enumerate(items, 1):
        result_text += f"{i}. [{item['type']}] {item['timestamp']}\n"
        result_text += f"   {item['content']}\n\n"

    return {
        "content": [{"type": "text", "text": result_text}]
    }


@tool(
    name="memory_search",
    description="Unified search across all memory lanes (vector, grep, episodic, squirrel) - use when you're not sure which lane to check",
    input_schema={"query": str, "lanes": str}
)
async def memory_search(args: dict) -> Dict[str, Any]:
    """Unified search across multiple memory lanes."""
    query = args.get("query", "")
    lanes = args.get("lanes", "all")

    if not query:
        return {
            "content": [{"type": "text", "text": "Error: query parameter is required"}],
            "isError": True
        }

    lane_list = lanes.lower().split(",") if lanes != "all" else ["vector", "grep", "episodic", "squirrel"]

    result_text = f"🔎 Unified Memory Search: '{query}'\n"
    result_text += f"Searching lanes: {', '.join(lane_list)}\n\n"

    total_hits = 0

    if "vector" in lane_list:
        vector_result = await memory_vector({"query": query, "top_k": 3, "threshold": 0.5})
        if not vector_result.get("isError"):
            result_text += "=" * 50 + "\n"
            result_text += "VECTOR LANE\n"
            result_text += "=" * 50 + "\n"
            result_text += vector_result["content"][0]["text"] + "\n\n"
            total_hits += 1

    if "grep" in lane_list:
        grep_result = await memory_grep({"term": query.split()[0] if query.split() else query, "max_results": 3})
        if not grep_result.get("isError"):
            result_text += "=" * 50 + "\n"
            result_text += "GREP LANE\n"
            result_text += "=" * 50 + "\n"
            result_text += grep_result["content"][0]["text"] + "\n\n"
            total_hits += 1

    if "episodic" in lane_list:
        episodic_result = await memory_episodic({"query": query, "timeframe": "all", "top_k": 2})
        if not episodic_result.get("isError"):
            result_text += "=" * 50 + "\n"
            result_text += "EPISODIC LANE\n"
            result_text += "=" * 50 + "\n"
            result_text += episodic_result["content"][0]["text"] + "\n\n"
            total_hits += 1

    if "squirrel" in lane_list:
        squirrel_result = await memory_squirrel({"hours_back": 24, "search": query.split()[0] if query.split() else None, "limit": 3})
        if not squirrel_result.get("isError"):
            result_text += "=" * 50 + "\n"
            result_text += "SQUIRREL LANE\n"
            result_text += "=" * 50 + "\n"
            result_text += squirrel_result["content"][0]["text"] + "\n\n"
            total_hits += 1

    if total_hits == 0:
        result_text += "No results found across any lanes.\n"

    return {
        "content": [{"type": "text", "text": result_text}]
    }


# Export tools list
TOOLS = [memory_vector, memory_grep, memory_episodic, memory_squirrel, memory_search]
