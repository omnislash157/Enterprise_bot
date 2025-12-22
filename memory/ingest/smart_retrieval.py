"""
Smart Retrieval - Enhanced RAG with Synthetic Questions

Philosophy: The enriched metadata makes retrieval trivial. Pre-computed tags,
synthetic questions, and relationships enable fast, precise results.

Key Innovation: Dual-embedding retrieval
- 30% weight on content similarity
- 50% weight on question similarity (THE SECRET WEAPON)
- 20% weight on tag overlap

This matches user queries (which are questions) against "what questions does this
chunk answer?" rather than just content similarity.

Usage:
    retriever = SmartRetriever(db_config, embedder)
    results = await retriever.retrieve(
        query="How do I approve a credit memo?",
        department="credit",
        user_role="credit_analyst"
    )

Version: 1.0.0
Date: 2024-12-22
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from memory.embedder import AsyncEmbedder
from memory.ingest.smart_tagger import SmartTagger

logger = logging.getLogger(__name__)


# ===========================================================================
# SMART RETRIEVER
# ===========================================================================


class SmartRetriever:
    """
    Enhanced retrieval with synthetic question matching.

    Uses dual-embedding approach:
    1. Embed user query once
    2. Match against both content and question embeddings
    3. Boost by tag overlap
    4. Expand with prerequisites
    """

    def __init__(
        self,
        db_config: Dict[str, Any],
        embedder: Optional[AsyncEmbedder] = None,
        tagger: Optional[SmartTagger] = None,
    ):
        """
        Initialize smart retriever.

        Args:
            db_config: PostgreSQL connection config
            embedder: Async embedder (if None, will create one)
            tagger: Smart tagger for query intent extraction (if None, will create one)
        """
        self.db_config = db_config
        self.embedder = embedder or AsyncEmbedder(provider="deepinfra")
        self.tagger = tagger or SmartTagger()

    def _get_db_connection(self):
        """Get database connection with dict cursor."""
        conn = psycopg2.connect(**self.db_config)
        return conn

    async def extract_query_intent(
        self,
        query: str,
    ) -> Dict[str, Any]:
        """
        Extract query intent for tag-based boosting.

        Uses a lightweight version of Pass 1.1 to classify the query.

        Args:
            query: User query

        Returns:
            Dict with query_types, entities, verbs
        """
        # Create minimal chunk for classification
        fake_chunk = {
            "content": query,
            "section_title": "",
            "source_file": "",
            "department_id": "",
        }

        import httpx

        async with httpx.AsyncClient() as client:
            classification = await self.tagger.classify_semantics(client, fake_chunk)

        return {
            "query_types": classification.get("query_types", []),
            "entities": classification.get("entities", []),
            "verbs": classification.get("verbs", []),
        }

    async def retrieve(
        self,
        query: str,
        department: str,
        user_role: str = "user",
        limit: int = 20,
        content_weight: float = 0.3,
        question_weight: float = 0.5,
        tag_weight: float = 0.2,
        min_score: float = 0.5,
        expand_prerequisites: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Smart retrieval with dual-embedding + tag boosting.

        Args:
            query: User query
            department: User's department
            user_role: User's role (for access control)
            limit: Max results to return
            content_weight: Weight for content similarity (default 0.3)
            question_weight: Weight for question similarity (default 0.5)
            tag_weight: Weight for tag overlap (default 0.2)
            min_score: Minimum combined score threshold
            expand_prerequisites: Include prerequisite chunks for top results

        Returns:
            List of result dicts with content, metadata, and scores
        """
        # 1. Embed query
        print(f"[Retrieve] Query: {query}")
        query_embedding = await self.embedder.embed_batch([query])
        query_vec = query_embedding[0]

        # 2. Extract query intent
        print("[Retrieve] Extracting query intent...")
        intent = await self.extract_query_intent(query)
        print(f"  Query types: {intent['query_types']}")
        print(f"  Entities: {intent['entities']}")
        print(f"  Verbs: {intent['verbs']}")

        # 3. Dual-embedding retrieval with tag boosting
        conn = self._get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Convert embedding to PostgreSQL vector format
        query_vec_str = "[" + ",".join(str(x) for x in query_vec.tolist()) + "]"

        # Convert arrays to PostgreSQL format
        query_types_str = "{" + ",".join(f'"{x}"' for x in intent["query_types"]) + "}"
        entities_str = "{" + ",".join(f'"{x}"' for x in intent["entities"]) + "}"
        verbs_str = "{" + ",".join(f'"{x}"' for x in intent["verbs"]) + "}"

        query_sql = f"""
        WITH scored AS (
            SELECT
                d.*,
                -- Content similarity
                1 - (d.embedding <=> %s::vector) AS content_sim,
                -- Question similarity (THE SECRET WEAPON)
                CASE
                    WHEN d.synthetic_questions_embedding IS NOT NULL
                    THEN 1 - (d.synthetic_questions_embedding <=> %s::vector)
                    ELSE 0
                END AS question_sim,
                -- Tag overlap bonuses
                CASE WHEN d.query_types && %s::text[] THEN 0.1 ELSE 0 END AS type_bonus,
                CASE WHEN d.entities && %s::text[] THEN 0.1 ELSE 0 END AS entity_bonus,
                CASE WHEN d.verbs && %s::text[] THEN 0.05 ELSE 0 END AS verb_bonus
            FROM enterprise.documents d
            WHERE d.is_active = TRUE
              AND %s = ANY(d.department_access)
              AND (d.requires_role IS NULL OR d.requires_role && ARRAY[%s]::text[])
        )
        SELECT *,
            -- Combined score: weight content vs question matching vs tag overlap
            (%s * content_sim) +
            (%s * question_sim) +
            (%s * (type_bonus + entity_bonus + verb_bonus)) AS combined_score
        FROM scored
        WHERE (content_sim >= 0.5 OR question_sim >= 0.6)
        ORDER BY
            combined_score DESC,
            importance DESC,
            process_step ASC NULLS LAST
        LIMIT %s
        """

        cur.execute(
            query_sql,
            (
                query_vec_str,  # For content similarity
                query_vec_str,  # For question similarity
                query_types_str,
                entities_str,
                verbs_str,
                department,
                user_role,
                content_weight,
                question_weight,
                tag_weight,
                limit,
            ),
        )

        results = cur.fetchall()

        print(f"[Retrieve] Found {len(results)} initial results")

        # 4. Expand with prerequisites (for top 5 results)
        if expand_prerequisites and results:
            top_ids = [r["id"] for r in results[:5]]

            # Get prerequisites for top results
            prereq_query = """
            SELECT DISTINCT d.*
            FROM enterprise.documents d
            WHERE d.id = ANY(
                SELECT unnest(prerequisite_ids)
                FROM enterprise.documents
                WHERE id = ANY(%s)
            )
            AND d.is_active = TRUE
            """

            cur.execute(prereq_query, (top_ids,))
            prereqs = cur.fetchall()

            if prereqs:
                print(f"[Retrieve] Expanded with {len(prereqs)} prerequisite chunks")
                # Add prerequisites to results (with lower score)
                for prereq in prereqs:
                    prereq["combined_score"] = 0.5  # Lower score for prerequisites
                    prereq["is_prerequisite"] = True
                    results.append(dict(prereq))

        cur.close()
        conn.close()

        # 5. Filter by minimum score
        filtered = [r for r in results if r.get("combined_score", 0) >= min_score]

        print(f"[Retrieve] Returning {len(filtered)} results (min_score={min_score})")

        return filtered

    async def retrieve_process(
        self,
        process_name: str,
        department: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all steps of a named process.

        Args:
            process_name: Process name (e.g., "credit_approval")
            department: User's department

        Returns:
            List of chunks ordered by process_step
        """
        conn = self._get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """
            SELECT *
            FROM enterprise.documents
            WHERE process_name = %s
              AND %s = ANY(department_access)
              AND is_active = TRUE
            ORDER BY process_step ASC
            """,
            (process_name, department),
        )

        results = cur.fetchall()

        cur.close()
        conn.close()

        print(f"[Retrieve Process] Found {len(results)} steps for '{process_name}'")

        return results

    async def expand_chunk_context(
        self,
        chunk_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Expand a single chunk with its context (prerequisites + see_also).

        Args:
            chunk_id: Chunk ID to expand

        Returns:
            List of related chunks
        """
        conn = self._get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """
            -- The original chunk
            SELECT d.*, 'source'::TEXT as relationship
            FROM enterprise.documents d
            WHERE d.id = %s

            UNION ALL

            -- Prerequisites
            SELECT d.*, 'prerequisite'::TEXT as relationship
            FROM enterprise.documents d
            WHERE d.id = ANY(
                SELECT unnest(prerequisite_ids)
                FROM enterprise.documents
                WHERE id = %s
            )

            UNION ALL

            -- See also
            SELECT d.*, 'see_also'::TEXT as relationship
            FROM enterprise.documents d
            WHERE d.id = ANY(
                SELECT unnest(see_also_ids)
                FROM enterprise.documents
                WHERE id = %s
            )
            """,
            (chunk_id, chunk_id, chunk_id),
        )

        results = cur.fetchall()

        cur.close()
        conn.close()

        print(f"[Expand Context] Retrieved {len(results)} related chunks")

        return results


# ===========================================================================
# CLI TEST
# ===========================================================================


async def main():
    """Test smart retrieval."""
    from dotenv import load_dotenv

    load_dotenv(override=True)

    print("Smart Retrieval Test")
    print("=" * 80)

    # Database config
    db_config = {
        "host": os.getenv("AZURE_PG_HOST", "localhost"),
        "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
        "user": os.getenv("AZURE_PG_USER", "postgres"),
        "password": os.getenv("AZURE_PG_PASSWORD"),
        "sslmode": os.getenv("AZURE_PG_SSLMODE", "require"),
        "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    }

    retriever = SmartRetriever(db_config)

    # Test queries
    test_queries = [
        ("How do I approve a credit memo?", "credit"),
        ("What's the process for receiving a shipment?", "warehouse"),
        ("Who do I escalate to for large credit requests?", "credit"),
    ]

    for query, department in test_queries:
        print(f"\n{'=' * 80}")
        print(f"Query: {query}")
        print(f"Department: {department}")
        print(f"{'=' * 80}")

        results = await retriever.retrieve(
            query=query,
            department=department,
            user_role="user",
            limit=5,
        )

        print(f"\nResults ({len(results)}):")
        for i, result in enumerate(results, 1):
            print(
                f"\n{i}. [{result.get('combined_score', 0):.3f}] {result.get('section_title', 'N/A')}"
            )
            print(f"   Source: {result.get('source_file', 'N/A')}")
            print(f"   Content: {result.get('content', '')[:200]}...")
            print(f"   Questions: {result.get('synthetic_questions', [])[:2]}")
            if result.get("is_prerequisite"):
                print(f"   [PREREQUISITE]")


if __name__ == "__main__":
    asyncio.run(main())
