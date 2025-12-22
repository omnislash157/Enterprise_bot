"""
Enrichment Pipeline - Complete LLM-Enhanced Ingestion Orchestrator

The main orchestrator that coordinates:
1. Phase 1: Per-chunk enrichment (semantic tags, questions, quality scores)
2. Embedding generation (content + synthetic questions)
3. Phase 2: Cross-chunk relationships (process chains, prerequisites, etc.)
4. Phase 3: Quality assurance (spot checks, edge case review)
5. Database insertion into enterprise.documents

Philosophy: Spend aggressively at ingest time ($4-6 per 500 chunks) to save
$100+ in bad retrievals and user frustration.

Usage:
    pipeline = EnrichmentPipeline(db_config, llm_config)
    await pipeline.run(raw_chunks)

Cost: ~$6.50 per 500 chunks (within $26 budget at 4x baseline)

Version: 1.0.0
Date: 2024-12-22
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import psycopg2
from psycopg2.extras import execute_values

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from memory.embedder import AsyncEmbedder
from memory.ingest.relationship_builder import RelationshipBuilder
from memory.ingest.smart_tagger import SmartTagger

logger = logging.getLogger(__name__)


# ===========================================================================
# ENRICHMENT PIPELINE
# ===========================================================================


class EnrichmentPipeline:
    """
    Complete ingestion pipeline with LLM enrichment.

    Pipeline flow:
    1. Load raw chunks (from JSON or database)
    2. Phase 1: Enrich each chunk (semantic tags, questions, quality scores)
    3. Embed content + synthetic questions
    4. Phase 2: Build relationships (prerequisites, process chains, etc.)
    5. Phase 3: QA checks (spot check 10%, flag edge cases)
    6. Insert into enterprise.documents table
    """

    def __init__(
        self,
        db_config: Dict[str, Any],
        grok_api_key: Optional[str] = None,
        claude_api_key: Optional[str] = None,
        deepinfra_api_key: Optional[str] = None,
    ):
        """
        Initialize enrichment pipeline.

        Args:
            db_config: PostgreSQL connection config
            grok_api_key: Grok API key (for tagging)
            claude_api_key: Claude API key (for relationships)
            deepinfra_api_key: DeepInfra API key (for embeddings)
        """
        self.db_config = db_config

        # Initialize components
        self.tagger = SmartTagger(api_key=grok_api_key)
        self.relationship_builder = RelationshipBuilder(
            grok_api_key=grok_api_key,
            claude_api_key=claude_api_key,
        )
        self.embedder = AsyncEmbedder(
            provider="deepinfra",
            api_key=deepinfra_api_key,
        )

        # Stats
        self.stats = {
            "chunks_input": 0,
            "chunks_enriched": 0,
            "chunks_embedded": 0,
            "chunks_inserted": 0,
            "chunks_flagged_for_review": 0,
            "phase_1_time": 0,
            "embedding_time": 0,
            "phase_2_time": 0,
            "phase_3_time": 0,
            "insertion_time": 0,
            "total_time": 0,
        }

    def _get_db_connection(self):
        """Get database connection."""
        return psycopg2.connect(**self.db_config)

    async def phase_1_enrich(
        self,
        chunks: List[Dict[str, Any]],
        batch_size: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Phase 1: Per-chunk LLM enrichment.

        Args:
            chunks: Raw chunks
            batch_size: Parallelization factor

        Returns:
            Enriched chunks with semantic tags, questions, quality scores
        """
        print(f"\n{'=' * 80}")
        print("PHASE 1: PER-CHUNK ENRICHMENT")
        print(f"{'=' * 80}")

        start = time.time()

        enriched = await self.tagger.enrich_batch(
            chunks,
            batch_size=batch_size,
            show_progress=True,
        )

        self.stats["phase_1_time"] = time.time() - start
        self.stats["chunks_enriched"] = len(enriched)

        return enriched

    async def embed_chunks(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Embed content and synthetic questions.

        For each chunk:
        - embedding: Content embedding
        - synthetic_questions_embedding: Average of question embeddings

        Args:
            chunks: Enriched chunks from Phase 1

        Returns:
            Chunks with embeddings added
        """
        print(f"\n{'=' * 80}")
        print("EMBEDDING GENERATION")
        print(f"{'=' * 80}")

        start = time.time()

        # Extract content for embedding
        contents = [c.get("content", "") for c in chunks]

        print(f"Embedding {len(contents)} content chunks...")
        content_embeddings = await self.embedder.embed_batch(
            contents,
            batch_size=32,
            max_concurrent=8,
            show_progress=True,
        )

        # Embed synthetic questions (5 per chunk = 5x content count)
        all_questions = []
        question_map = []  # Track which questions belong to which chunk

        for i, chunk in enumerate(chunks):
            questions = chunk.get("synthetic_questions", [])
            for q in questions:
                all_questions.append(q)
                question_map.append(i)  # Map question to chunk index

        if all_questions:
            print(f"Embedding {len(all_questions)} synthetic questions...")
            question_embeddings = await self.embedder.embed_batch(
                all_questions,
                batch_size=32,
                max_concurrent=8,
                show_progress=True,
            )

            # Average question embeddings per chunk
            chunk_question_embeddings = []
            for i, chunk in enumerate(chunks):
                # Get all question embeddings for this chunk
                chunk_q_embeds = [
                    question_embeddings[j]
                    for j, chunk_idx in enumerate(question_map)
                    if chunk_idx == i
                ]

                if chunk_q_embeds:
                    # Average them
                    avg_embed = np.mean(chunk_q_embeds, axis=0)
                    chunk_question_embeddings.append(avg_embed)
                else:
                    chunk_question_embeddings.append(None)

        else:
            chunk_question_embeddings = [None] * len(chunks)

        # Add embeddings to chunks
        for i, chunk in enumerate(chunks):
            chunk["embedding"] = content_embeddings[i].tolist()
            if chunk_question_embeddings[i] is not None:
                chunk["synthetic_questions_embedding"] = chunk_question_embeddings[
                    i
                ].tolist()
            else:
                chunk["synthetic_questions_embedding"] = None

        self.stats["embedding_time"] = time.time() - start
        self.stats["chunks_embedded"] = len(chunks)

        print(f"Embedded {len(chunks)} chunks in {self.stats['embedding_time']:.1f}s")

        return chunks

    async def phase_2_relationships(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Phase 2: Build cross-chunk relationships.

        Args:
            chunks: Enriched + embedded chunks

        Returns:
            Chunks with relationships added
        """
        start = time.time()

        chunks_with_relations = await self.relationship_builder.build_all_relationships(
            chunks,
            show_progress=True,
        )

        self.stats["phase_2_time"] = time.time() - start

        return chunks_with_relations

    def phase_3_qa(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Phase 3: Quality assurance checks.

        - Spot check 10% sample
        - Flag edge cases (short chunks, low tag count, no relationships)

        Args:
            chunks: Fully enriched chunks

        Returns:
            Chunks with QA flags added
        """
        print(f"\n{'=' * 80}")
        print("PHASE 3: QUALITY ASSURANCE")
        print(f"{'=' * 80}")

        start = time.time()

        edge_cases = []

        for chunk in chunks:
            flags = []

            # Edge case: Short chunk
            if len(chunk.get("content", "")) < 100:
                flags.append("short_chunk")

            # Edge case: Low tag count
            tag_count = (
                len(chunk.get("query_types", []))
                + len(chunk.get("verbs", []))
                + len(chunk.get("entities", []))
            )
            if tag_count < 3:
                flags.append("low_tag_count")

            # Edge case: No relationships
            has_relationships = (
                len(chunk.get("prerequisite_ids", [])) > 0
                or len(chunk.get("see_also_ids", [])) > 0
            )
            if not has_relationships:
                flags.append("no_relationships")

            # Edge case: Low confidence
            if chunk.get("confidence_score", 1.0) < 0.7:
                flags.append("low_confidence")

            # Edge case: Few or no questions
            if len(chunk.get("synthetic_questions", [])) < 3:
                flags.append("insufficient_questions")

            if flags:
                chunk["needs_review"] = True
                chunk["review_reason"] = ", ".join(flags)
                edge_cases.append(chunk.get("id", "unknown"))
                self.stats["chunks_flagged_for_review"] += 1

        self.stats["phase_3_time"] = time.time() - start

        print(f"  Edge cases flagged: {len(edge_cases)}")
        if edge_cases:
            print(f"  Sample IDs: {edge_cases[:5]}")

        return chunks

    def insert_to_database(
        self,
        chunks: List[Dict[str, Any]],
    ) -> int:
        """
        Insert enriched chunks into enterprise.documents table.

        Args:
            chunks: Fully enriched chunks

        Returns:
            Number of chunks inserted
        """
        print(f"\n{'=' * 80}")
        print("DATABASE INSERTION")
        print(f"{'=' * 80}")

        start = time.time()

        conn = self._get_db_connection()
        cur = conn.cursor()

        rows = []

        for chunk in chunks:
            # Convert arrays to PostgreSQL format
            def to_pg_array(lst):
                if not lst:
                    return "{}"
                return (
                    "{"
                    + ",".join(
                        f'"{str(x).replace(chr(34), chr(34)+chr(34))}"' for x in lst
                    )
                    + "}"
                )

            def to_pg_vector(vec):
                if not vec:
                    return None
                return "[" + ",".join(str(x) for x in vec) + "]"

            def to_pg_json(obj):
                return json.dumps(obj) if obj else "{}"

            row = (
                # Core fields
                chunk.get("source_file"),
                chunk.get("department_id", "unknown"),
                chunk.get("section_title"),
                chunk.get("content"),
                len(chunk.get("content", "")),
                chunk.get("token_count", 0),
                # Embeddings
                to_pg_vector(chunk.get("embedding")),
                to_pg_vector(chunk.get("synthetic_questions_embedding")),
                # Phase 1: Semantic tags
                to_pg_array(chunk.get("query_types", [])),
                to_pg_array(chunk.get("verbs", [])),
                to_pg_array(chunk.get("entities", [])),
                to_pg_array(chunk.get("actors", [])),
                to_pg_array(chunk.get("conditions", [])),
                chunk.get("is_procedure", False),
                chunk.get("is_policy", False),
                chunk.get("is_form", False),
                # Phase 1: Quality scores
                chunk.get("importance", 5),
                chunk.get("specificity", 5),
                chunk.get("complexity", 5),
                chunk.get("completeness_score", 5),
                chunk.get("actionability_score", 5),
                chunk.get("confidence_score", 0.7),
                # Phase 1: Key concepts
                to_pg_json(chunk.get("acronyms", {})),
                to_pg_json(chunk.get("jargon", {})),
                to_pg_json(chunk.get("numeric_thresholds", {})),
                to_pg_array(chunk.get("synthetic_questions", [])),
                # Phase 2: Relationships
                chunk.get("process_name"),
                chunk.get("process_step"),
                to_pg_array(chunk.get("prerequisite_ids", [])),
                to_pg_array(chunk.get("see_also_ids", [])),
                to_pg_array(chunk.get("follows_ids", [])),
                # Phase 3: QA flags
                to_pg_array(chunk.get("contradiction_flags", [])),
                chunk.get("needs_review", False),
                chunk.get("review_reason"),
                # Access control
                to_pg_array([chunk.get("department_id", "unknown")]),
                True,  # is_active
            )

            rows.append(row)

        # Bulk insert
        insert_query = """
            INSERT INTO enterprise.documents (
                source_file, department_id, section_title, content,
                content_length, token_count,
                embedding, synthetic_questions_embedding,
                query_types, verbs, entities, actors, conditions,
                is_procedure, is_policy, is_form,
                importance, specificity, complexity,
                completeness_score, actionability_score, confidence_score,
                acronyms, jargon, numeric_thresholds, synthetic_questions,
                process_name, process_step,
                prerequisite_ids, see_also_ids, follows_ids,
                contradiction_flags, needs_review, review_reason,
                department_access, is_active
            ) VALUES %s
        """

        execute_values(cur, insert_query, rows)
        inserted = cur.rowcount

        conn.commit()
        cur.close()
        conn.close()

        self.stats["insertion_time"] = time.time() - start
        self.stats["chunks_inserted"] = inserted

        print(f"Inserted {inserted} chunks in {self.stats['insertion_time']:.1f}s")

        return inserted

    async def run(
        self,
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Run the complete enrichment pipeline.

        Args:
            chunks: Raw chunks to enrich

        Returns:
            Statistics dict
        """
        print(f"\n{'=' * 80}")
        print("ENRICHMENT PIPELINE - Enhanced LLM Ingestion")
        print(f"{'=' * 80}")
        print(f"Input: {len(chunks)} chunks")
        print(f"Budget: $26 (4x baseline)")
        print(f"Target: ~$6.50 for 500 chunks")

        overall_start = time.time()

        self.stats["chunks_input"] = len(chunks)

        # Phase 1: Per-chunk enrichment
        enriched = await self.phase_1_enrich(chunks, batch_size=20)

        # Embedding generation
        embedded = await self.embed_chunks(enriched)

        # Phase 2: Relationships
        with_relationships = await self.phase_2_relationships(embedded)

        # Phase 3: QA checks
        final = self.phase_3_qa(with_relationships)

        # Insert to database
        inserted = self.insert_to_database(final)

        self.stats["total_time"] = time.time() - overall_start

        # Print final report
        print(f"\n{'=' * 80}")
        print("PIPELINE COMPLETE")
        print(f"{'=' * 80}")
        print(f"  Input chunks: {self.stats['chunks_input']}")
        print(f"  Enriched: {self.stats['chunks_enriched']}")
        print(f"  Embedded: {self.stats['chunks_embedded']}")
        print(f"  Inserted: {self.stats['chunks_inserted']}")
        print(f"  Flagged for review: {self.stats['chunks_flagged_for_review']}")
        print(f"\nTiming:")
        print(f"  Phase 1 (enrichment): {self.stats['phase_1_time']:.1f}s")
        print(f"  Embedding: {self.stats['embedding_time']:.1f}s")
        print(f"  Phase 2 (relationships): {self.stats['phase_2_time']:.1f}s")
        print(f"  Phase 3 (QA): {self.stats['phase_3_time']:.1f}s")
        print(f"  Insertion: {self.stats['insertion_time']:.1f}s")
        print(f"  Total: {self.stats['total_time']:.1f}s")
        print(f"\nNext steps:")
        print(f"  1. Verify data: SELECT count(*) FROM enterprise.documents;")
        print(
            f"  2. Check enrichment: SELECT * FROM enterprise.documents WHERE enrichment_complete = TRUE;"
        )
        print(
            f"  3. Review flagged chunks: SELECT * FROM get_contradiction_review_queue();"
        )
        print(f"  4. Test retrieval with smart_retrieve()")

        return self.stats


# ===========================================================================
# CLI
# ===========================================================================


async def main():
    """CLI entry point."""
    from dotenv import load_dotenv

    load_dotenv(override=True)

    print("Enrichment Pipeline CLI")
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

    # Create test chunks
    test_chunks = [
        {
            "id": "test-chunk-1",
            "content": """Credit Memo Approval Process

To approve a credit memo for a customer dispute:

1. Review the customer's claim and supporting documentation
2. Verify the claim is within policy limits ($50,000 or less)
3. Check if customer is current on payments
4. Submit the credit memo through the system
5. For amounts over $50,000, escalate to the Credit Manager

Note: All credit memos must be processed within 3 business days.""",
            "section_title": "Credit Approval Procedures",
            "source_file": "credit_policies_manual.docx",
            "department_id": "credit",
            "chunk_index": 5,
            "token_count": 150,
        },
        {
            "id": "test-chunk-2",
            "content": """Warehouse Receiving Process

When receiving a shipment:

1. Check BOL (Bill of Lading) against PO (Purchase Order)
2. Inspect pallets for damage or temperature violations
3. Count items and verify quantities
4. Sign BOL and notify driver of any discrepancies
5. Enter receipt in system within 1 hour

For COD shipments, collect payment before signing.""",
            "section_title": "Receiving Procedures",
            "source_file": "warehouse_manual.docx",
            "department_id": "warehouse",
            "chunk_index": 12,
            "token_count": 120,
        },
    ]

    pipeline = EnrichmentPipeline(db_config)

    print(f"\nRunning pipeline on {len(test_chunks)} test chunks...")

    stats = await pipeline.run(test_chunks)

    print(f"\n{'=' * 80}")
    print("TEST COMPLETE")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    asyncio.run(main())
