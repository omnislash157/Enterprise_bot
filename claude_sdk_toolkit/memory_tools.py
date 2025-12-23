"""
Memory Tools - CogTwin RAG Lane Access

Direct access to all 5 retrieval lanes as first-class Claude tools.
No more tool markers in prompts - Claude calls these natively.

Lanes:
    memory_vector: FAISS semantic similarity search
    memory_grep: BM25/keyword search with co-occurrence
    memory_episodic: Full conversation arc retrieval
    memory_squirrel: Temporal recall (last N hours)
    memory_search: Unified search across all lanes

Architecture:
    These tools hit the same backends as VenomVoice tool parsing,
    but directly - no LLM-in-the-loop for tool dispatch.
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# SDK tool decorator
try:
    from claude_agent_sdk import tool
    SDK_AVAILABLE = True
except ImportError:
    def tool(fn):
        fn._is_tool = True
        return fn
    SDK_AVAILABLE = False

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
# BACKENDS
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
    """
    Generate embedding via DeepInfra BGE-M3.
    Returns None if not configured.
    """
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
    except Exception as e:
        return None


# =============================================================================
# TOOLS
# =============================================================================

@tool
def memory_vector(query: str, top_k: int = 10, threshold: float = 0.5) -> Dict[str, Any]:
    """
    Semantic similarity search across memory nodes using FAISS.
    
    Finds memories that are conceptually similar to the query,
    even if they don't share exact words.
    
    Args:
        query: Natural language search query
        top_k: Maximum results to return (default: 10)
        threshold: Minimum similarity score 0-1 (default: 0.5)
        
    Returns:
        Dict with 'results' list containing id, content, score, timestamp
        
    Examples:
        memory_vector("async Python patterns")
        memory_vector("database connection issues", top_k=5)
    """
    # Get query embedding
    embedding = get_embedding(query)
    if embedding is None:
        return {
            "error": "Embedding service not available. Set DEEPINFRA_API_KEY.",
            "fallback": "Use memory_grep for keyword search instead."
        }
    
    # Try FAISS index
    index_path = os.path.join(MEMORY_DATA_DIR, "faiss_index.bin")
    metadata_path = os.path.join(MEMORY_DATA_DIR, "memory_metadata.json")
    
    if not os.path.exists(index_path):
        return {
            "error": f"FAISS index not found at {index_path}",
            "hint": "Run memory ingestion pipeline first."
        }
    
    try:
        import json
        
        # Load index and metadata
        index = faiss.read_index(index_path)
        with open(metadata_path) as f:
            metadata = json.load(f)
        
        # Search
        query_vec = np.array([embedding], dtype=np.float32)
        distances, indices = index.search(query_vec, top_k)
        
        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < 0 or idx >= len(metadata):
                continue
            
            score = 1 - dist  # Convert distance to similarity
            if score < threshold:
                continue
            
            mem = metadata[idx]
            results.append({
                "id": mem.get("id", f"mem_{idx}"),
                "score": round(float(score), 3),
                "human_content": mem.get("human_content", "")[:300],
                "assistant_content": mem.get("assistant_content", "")[:300],
                "timestamp": mem.get("created_at", "unknown"),
                "cluster_label": mem.get("cluster_label"),
            })
        
        return {
            "query": query,
            "lane": "VECTOR/FAISS",
            "result_count": len(results),
            "results": results,
        }
        
    except Exception as e:
        return {"error": str(e), "lane": "VECTOR/FAISS"}


@tool
def memory_grep(
    term: str,
    context_chars: int = 150,
    max_results: int = 20
) -> Dict[str, Any]:
    """
    Keyword/BM25 search across memory content.
    
    Finds exact and fuzzy term matches. Good for:
    - Finding specific mentions ("PFG", "Railway")
    - Verifying frequency of terms
    - Finding co-occurring terms
    
    Args:
        term: Search term or phrase
        context_chars: Characters of context around match (default: 150)
        max_results: Maximum results to return (default: 20)
        
    Returns:
        Dict with 'hits' list, 'total_occurrences', 'co_occurring_terms'
        
    Examples:
        memory_grep("Railway deploy")
        memory_grep("error 500", max_results=10)
    """
    # Try PostgreSQL full-text search first
    if POSTGRES_AVAILABLE:
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Use PostgreSQL ts_rank for BM25-like scoring
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
            
            hits = []
            for row in rows:
                content = f"{row['human_content']} {row['assistant_content']}"
                # Find term position for context snippet
                term_lower = term.lower()
                content_lower = content.lower()
                pos = content_lower.find(term_lower)
                
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
                
                hits.append({
                    "id": str(row["id"]),
                    "score": round(float(row["score"]), 3),
                    "snippet": snippet,
                    "timestamp": row["created_at"].isoformat() if row["created_at"] else "unknown",
                })
            
            cur.close()
            conn.close()
            
            return {
                "term": term,
                "lane": "GREP/BM25",
                "result_count": len(hits),
                "hits": hits,
            }
            
        except Exception as e:
            # Fall through to file-based search
            pass
    
    # Fallback: file-based grep
    import json
    metadata_path = os.path.join(MEMORY_DATA_DIR, "memory_metadata.json")
    
    if not os.path.exists(metadata_path):
        return {"error": f"Memory metadata not found at {metadata_path}"}
    
    try:
        with open(metadata_path) as f:
            memories = json.load(f)
        
        term_lower = term.lower()
        hits = []
        
        for mem in memories:
            content = f"{mem.get('human_content', '')} {mem.get('assistant_content', '')}"
            content_lower = content.lower()
            
            if term_lower in content_lower:
                pos = content_lower.find(term_lower)
                start = max(0, pos - context_chars // 2)
                end = min(len(content), pos + len(term) + context_chars // 2)
                snippet = content[start:end]
                
                hits.append({
                    "id": mem.get("id", "unknown"),
                    "snippet": f"...{snippet}..." if start > 0 else snippet + "...",
                    "timestamp": mem.get("created_at", "unknown"),
                })
                
                if len(hits) >= max_results:
                    break
        
        return {
            "term": term,
            "lane": "GREP/FILE",
            "result_count": len(hits),
            "hits": hits,
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def memory_episodic(
    query: str,
    timeframe: str = "all",
    top_k: int = 5
) -> Dict[str, Any]:
    """
    Search full conversation arcs (episodic memory).
    
    Unlike memory_vector which searches Q/A pairs, this searches
    entire conversations - good for finding project context,
    "what were we working on", interrupted work, etc.
    
    Args:
        query: Search query
        timeframe: "all", "week", "month", "quarter" (default: all)
        top_k: Maximum conversations to return (default: 5)
        
    Returns:
        Dict with 'episodes' list containing title, summary, message_count, timestamps
        
    Examples:
        memory_episodic("Railway deployment issues")
        memory_episodic("CogTwin architecture", timeframe="month")
    """
    import json
    episodes_path = os.path.join(MEMORY_DATA_DIR, "episodes.json")
    
    if not os.path.exists(episodes_path):
        return {
            "error": f"Episodes not found at {episodes_path}",
            "hint": "Run episodic memory ingestion first."
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
        
        # Simple keyword matching for now (could use embeddings)
        query_terms = query.lower().split()
        scored = []
        
        for ep in episodes:
            text = f"{ep.get('title', '')} {ep.get('summary', '')}".lower()
            score = sum(1 for term in query_terms if term in text)
            if score > 0:
                scored.append((score, ep))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        top_episodes = scored[:top_k]
        
        results = []
        for score, ep in top_episodes:
            results.append({
                "id": ep.get("id"),
                "title": ep.get("title"),
                "summary": ep.get("summary", "")[:300],
                "message_count": ep.get("message_count", 0),
                "created_at": ep.get("created_at"),
                "duration_minutes": ep.get("duration_minutes"),
                "relevance_score": score,
            })
        
        return {
            "query": query,
            "timeframe": timeframe,
            "lane": "EPISODIC",
            "result_count": len(results),
            "episodes": results,
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def memory_squirrel(
    hours_back: int = 1,
    search: str = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Temporal recall - get recent session context.
    
    "What was that thing from an hour ago?" - SQUIRREL finds it.
    Highest trust source after current session.
    
    Args:
        hours_back: How many hours to look back (default: 1)
        search: Optional keyword filter
        limit: Maximum items to return (default: 20)
        
    Returns:
        Dict with 'items' list containing timestamp, content, type
        
    Examples:
        memory_squirrel(hours_back=2)
        memory_squirrel(hours_back=24, search="database")
    """
    import json
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
                
                # Apply search filter
                if search and search.lower() not in content.lower():
                    continue
                
                items.append({
                    "timestamp": ts_str,
                    "content": content[:400],
                    "thought_type": output.get("thought_type", "unknown"),
                })
                
                if len(items) >= limit:
                    break
                    
        except Exception as e:
            pass
    
    # Also try PostgreSQL if available
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
                    "content": row["content"][:400],
                    "thought_type": row.get("thought_type", "unknown"),
                })
            
            cur.close()
            conn.close()
            
        except:
            pass
    
    return {
        "lane": "SQUIRREL",
        "hours_back": hours_back,
        "search_filter": search,
        "result_count": len(items),
        "items": items,
    }


@tool
def memory_search(query: str, lanes: str = "all") -> Dict[str, Any]:
    """
    Unified search across multiple memory lanes.
    
    Fires multiple lanes in parallel and merges results.
    Use this when you're not sure which lane has the answer.
    
    Args:
        query: Search query
        lanes: Comma-separated lanes or "all" (default: all)
                Options: vector, grep, episodic, squirrel
                
    Returns:
        Dict with results from each lane, merged and ranked
        
    Examples:
        memory_search("Python async patterns")
        memory_search("Railway", lanes="grep,squirrel")
    """
    results = {
        "query": query,
        "lanes_searched": [],
        "total_results": 0,
    }
    
    lane_list = lanes.lower().split(",") if lanes != "all" else ["vector", "grep", "episodic", "squirrel"]
    
    if "vector" in lane_list:
        vector_results = memory_vector(query, top_k=5)
        results["vector"] = vector_results
        results["lanes_searched"].append("VECTOR")
        if "results" in vector_results:
            results["total_results"] += len(vector_results["results"])
    
    if "grep" in lane_list:
        grep_results = memory_grep(query.split()[0] if query.split() else query, max_results=5)
        results["grep"] = grep_results
        results["lanes_searched"].append("GREP")
        if "hits" in grep_results:
            results["total_results"] += len(grep_results["hits"])
    
    if "episodic" in lane_list:
        episodic_results = memory_episodic(query, top_k=3)
        results["episodic"] = episodic_results
        results["lanes_searched"].append("EPISODIC")
        if "episodes" in episodic_results:
            results["total_results"] += len(episodic_results["episodes"])
    
    if "squirrel" in lane_list:
        # Search last 24h for the query terms
        squirrel_results = memory_squirrel(hours_back=24, search=query.split()[0] if query.split() else None, limit=5)
        results["squirrel"] = squirrel_results
        results["lanes_searched"].append("SQUIRREL")
        if "items" in squirrel_results:
            results["total_results"] += len(squirrel_results["items"])
    
    return results


# Export tools list
TOOLS = [memory_vector, memory_grep, memory_episodic, memory_squirrel, memory_search]