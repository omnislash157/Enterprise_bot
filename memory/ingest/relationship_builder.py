"""
Relationship Builder - Phase 2: Cross-Chunk Relationship Inference

Philosophy: Build the knowledge graph at ingest time. Pre-compute relationships so
retrieval can traverse them instantly.

Phase 2 builds relationships ACROSS chunks:
- Process chains (step 1 → step 2 → step 3)
- Prerequisites ("read this first")
- Lateral connections ("see also")
- Contradictions ("this conflicts with that")
- Cluster labels (human-readable topic names)

Cost: ~$3.00 per 500 chunks (mix of Grok Fast and Claude Haiku)
Requires: All chunks from Phase 1 (with embeddings)

Usage:
    builder = RelationshipBuilder(
        grok_api_key=GROK_KEY,
        claude_api_key=CLAUDE_KEY
    )
    chunks_with_relations = await builder.build_all_relationships(enriched_chunks)

Version: 1.0.0
Date: 2024-12-22
"""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════════

PROCESS_CHAIN_PROMPT = """Analyze this document and identify any multi-step processes.

DOCUMENT: {source_file}
CHUNKS:
---
{chunks_text}
---

Identify any multi-step processes and map which chunks belong to each step.

For each process found:
1. process_name: Descriptive name (e.g., "credit_approval", "returns_processing")
2. steps: Ordered list of chunk indices that form this process

Return JSON:
{{
  "processes": [
    {{
      "process_name": "credit_memo_creation",
      "steps": [
        {{"chunk_index": 2, "step_number": 1, "description": "Initiate request"}},
        {{"chunk_index": 3, "step_number": 2, "description": "Enter details"}},
        {{"chunk_index": 5, "step_number": 3, "description": "Submit for approval"}}
      ]
    }}
  ]
}}

If no clear processes are found, return empty "processes" array."""


PREREQUISITE_PROMPT = """Given these two document chunks, determine if there's a prerequisite relationship.

CHUNK A (potential prerequisite):
---
{chunk_a_content}
---
Section: {chunk_a_section}

CHUNK B (depends on A?):
---
{chunk_b_content}
---
Section: {chunk_b_section}

Questions:
1. Does understanding Chunk B require knowledge from Chunk A?
2. Would reading A first make B clearer?
3. Does A define terms/concepts used in B?

Return JSON:
{{
  "is_prerequisite": boolean,
  "confidence": 0.0-1.0,
  "reasoning": "Chunk A defines credit memo structure, Chunk B assumes that knowledge"
}}"""


LATERAL_CONNECTION_PROMPT = """Given these two document chunks from different sections, determine if they're related.

CHUNK A:
---
{chunk_a_content}
---
Section: {chunk_a_section}

CHUNK B:
---
{chunk_b_content}
---
Section: {chunk_b_section}

Are these chunks related in a way that someone reading A might want to also see B?

Types of relationships:
- same_entity: Both discuss the same domain object from different angles
- complementary: Different parts of the same overall topic
- alternative: Different approaches to the same problem
- exception: One describes the rule, other describes exceptions

Return JSON:
{{
  "is_related": boolean,
  "relationship_type": "same_entity" | "complementary" | "alternative" | "exception" | null,
  "confidence": 0.0-1.0,
  "reasoning": "Both discuss credit memos - A is creation, B is voiding"
}}"""


CONTRADICTION_PROMPT = """Compare these two chunks for potential conflicts or contradictions.

CHUNK A (older or from document A):
---
{chunk_a_content}
---
SOURCE: {chunk_a_source}
DATE: {chunk_a_date}

CHUNK B (newer or from document B):
---
{chunk_b_content}
---
SOURCE: {chunk_b_source}
DATE: {chunk_b_date}

Analyze for:
1. Direct contradiction: Conflicting instructions or policies
2. Supersession: B updates/replaces A
3. Ambiguity: Both valid but could confuse users

Return JSON:
{{
  "has_conflict": boolean,
  "conflict_type": "contradiction" | "supersession" | "ambiguity" | null,
  "severity": "critical" | "moderate" | "minor" | null,
  "details": "A says 3-day approval, B says same-day for rush orders - not contradictory, B is exception",
  "recommendation": "Link as exception case" | "Flag for human review" | "B supersedes A"
}}"""


CLUSTER_LABEL_PROMPT = """Generate a human-readable label for this topic cluster.

CLUSTER CHUNKS (representative samples):
---
{chunks_text}
---

Generate:
1. cluster_label: Short, descriptive name (e.g., "Credit Memo Approval Procedures")
2. description: One-sentence description
3. key_concepts: 3-5 key concepts in this cluster

Return JSON:
{{
  "cluster_label": "Credit Memo Approval Procedures",
  "description": "Procedures for creating, reviewing, and approving customer credit memos",
  "key_concepts": ["credit memo", "approval workflow", "credit limits"]
}}"""


# ═══════════════════════════════════════════════════════════════════════════
# RELATIONSHIP BUILDER
# ═══════════════════════════════════════════════════════════════════════════


class RelationshipBuilder:
    """
    Phase 2: Cross-chunk relationship inference.

    Uses:
    - Grok Fast for simple comparisons (prerequisites, lateral connections)
    - Claude Haiku for complex reasoning (contradictions, cluster labels)
    """

    GROK_API_URL = "https://api.x.ai/v1/chat/completions"
    CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(
        self,
        grok_api_key: Optional[str] = None,
        claude_api_key: Optional[str] = None,
        grok_model: str = "grok-4-1-fast-reasoning",
        claude_model: str = "claude-3-haiku-20240307",
        requests_per_minute: int = 60,
    ):
        """
        Initialize Relationship Builder.

        Args:
            grok_api_key: xAI/Grok API key (or from XAI_API_KEY env)
            claude_api_key: Anthropic API key (or from ANTHROPIC_API_KEY env)
            grok_model: Grok model to use
            claude_model: Claude model to use
            requests_per_minute: Rate limit
        """
        self.grok_api_key = (
            grok_api_key or os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
        )
        self.claude_api_key = claude_api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.grok_api_key:
            raise ValueError("Grok API key required (XAI_API_KEY or GROK_API_KEY)")

        self.grok_model = grok_model
        self.claude_model = claude_model
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self.last_request_time = 0.0
        self._rate_lock = asyncio.Lock()

        # Stats
        self.stats = {
            "processes_detected": 0,
            "prerequisites_found": 0,
            "lateral_connections_found": 0,
            "contradictions_found": 0,
            "clusters_labeled": 0,
            "api_calls": 0,
            "errors": 0,
            "total_tokens": 0,
        }

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        async with self._rate_lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()

    async def _call_grok(
        self,
        client: httpx.AsyncClient,
        prompt: str,
        pass_name: str,
    ) -> Dict[str, Any]:
        """Call Grok API."""
        await self._rate_limit()

        try:
            response = await client.post(
                self.GROK_API_URL,
                headers={
                    "Authorization": f"Bearer {self.grok_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.grok_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                    "response_format": {"type": "json_object"},
                },
                timeout=60.0,
            )

            response.raise_for_status()
            data = response.json()
            self.stats["api_calls"] += 1

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            self.stats["total_tokens"] += usage.get("total_tokens", 0)

            # Clean and parse JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            return json.loads(content.strip())

        except Exception as e:
            logger.error(f"Error in {pass_name}: {e}")
            self.stats["errors"] += 1
            return {}

    async def _call_claude(
        self,
        client: httpx.AsyncClient,
        prompt: str,
        pass_name: str,
    ) -> Dict[str, Any]:
        """Call Claude API."""
        if not self.claude_api_key:
            logger.warning(f"{pass_name} requires Claude API key, skipping")
            return {}

        await self._rate_limit()

        try:
            response = await client.post(
                self.CLAUDE_API_URL,
                headers={
                    "x-api-key": self.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.claude_model,
                    "max_tokens": 1000,
                    "temperature": 0.3,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )

            response.raise_for_status()
            data = response.json()
            self.stats["api_calls"] += 1

            content = data["content"][0]["text"]
            usage = data.get("usage", {})
            self.stats["total_tokens"] += usage.get("input_tokens", 0) + usage.get(
                "output_tokens", 0
            )

            # Clean and parse JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            return json.loads(content.strip())

        except Exception as e:
            logger.error(f"Error in {pass_name}: {e}")
            self.stats["errors"] += 1
            return {}

    async def detect_process_chains(
        self,
        client: httpx.AsyncClient,
        chunks_by_doc: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Pass 2.1: Process Chain Detection

        Analyze each document to identify multi-step processes.

        Args:
            client: HTTP client
            chunks_by_doc: Dict of source_file -> list of chunks

        Returns:
            Dict of source_file -> list of detected processes
        """
        print("\n[Pass 2.1] Detecting process chains...")

        all_processes = {}

        for source_file, chunks in chunks_by_doc.items():
            # Format chunks for prompt
            chunks_text = "\n\n".join(
                [
                    f"[{i}] Section: {c.get('section_title', 'N/A')}\n{c.get('content', '')[:500]}"
                    for i, c in enumerate(chunks)
                ]
            )

            prompt = PROCESS_CHAIN_PROMPT.format(
                source_file=source_file,
                chunks_text=chunks_text,
            )

            result = await self._call_grok(client, prompt, "process_chain_detection")
            processes = result.get("processes", [])

            if processes:
                all_processes[source_file] = processes
                self.stats["processes_detected"] += len(processes)
                print(f"  {source_file}: Found {len(processes)} process(es)")

        return all_processes

    def _compute_similarity(self, emb_a: List[float], emb_b: List[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        a = np.array(emb_a)
        b = np.array(emb_b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def _find_similar_chunks(
        self,
        chunk: Dict[str, Any],
        all_chunks: List[Dict[str, Any]],
        threshold: float = 0.7,
        max_candidates: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find chunks similar to given chunk (for relationship inference)."""
        if "embedding" not in chunk or chunk["embedding"] is None:
            return []

        similarities = []
        for other in all_chunks:
            if other["id"] == chunk["id"]:
                continue
            if "embedding" not in other or other["embedding"] is None:
                continue

            sim = self._compute_similarity(chunk["embedding"], other["embedding"])
            if sim >= threshold:
                similarities.append((sim, other))

        # Sort by similarity descending, take top N
        similarities.sort(reverse=True, key=lambda x: x[0])
        return [other for _, other in similarities[:max_candidates]]

    async def infer_prerequisites(
        self,
        client: httpx.AsyncClient,
        chunks: List[Dict[str, Any]],
        max_concurrent: int = 5,
    ) -> Dict[str, List[str]]:
        """
        Pass 2.2: Prerequisite Inference

        For each chunk, find similar chunks and check if they're prerequisites.

        Args:
            client: HTTP client
            chunks: All chunks with embeddings
            max_concurrent: Max concurrent LLM calls

        Returns:
            Dict of chunk_id -> list of prerequisite chunk IDs
        """
        print("\n[Pass 2.2] Inferring prerequisites...")

        semaphore = asyncio.Semaphore(max_concurrent)
        prerequisites = {}

        async def check_prerequisite(chunk: Dict[str, Any]):
            similar = self._find_similar_chunks(
                chunk, chunks, threshold=0.7, max_candidates=10
            )

            chunk_prereqs = []

            for candidate in similar:
                async with semaphore:
                    prompt = PREREQUISITE_PROMPT.format(
                        chunk_a_content=candidate.get("content", "")[:1000],
                        chunk_a_section=candidate.get("section_title", ""),
                        chunk_b_content=chunk.get("content", "")[:1000],
                        chunk_b_section=chunk.get("section_title", ""),
                    )

                    result = await self._call_grok(client, prompt, "prerequisite_check")

                    if (
                        result.get("is_prerequisite")
                        and result.get("confidence", 0) >= 0.7
                    ):
                        chunk_prereqs.append(candidate["id"])
                        self.stats["prerequisites_found"] += 1

            if chunk_prereqs:
                prerequisites[chunk["id"]] = chunk_prereqs

        tasks = [check_prerequisite(chunk) for chunk in chunks]
        await asyncio.gather(*tasks)

        print(f"  Found {self.stats['prerequisites_found']} prerequisite relationships")

        return prerequisites

    async def find_lateral_connections(
        self,
        client: httpx.AsyncClient,
        chunks: List[Dict[str, Any]],
        max_concurrent: int = 5,
    ) -> Dict[str, List[str]]:
        """
        Pass 2.3: Lateral Connections (See Also)

        Find related chunks from different sections.

        Args:
            client: HTTP client
            chunks: All chunks with embeddings
            max_concurrent: Max concurrent LLM calls

        Returns:
            Dict of chunk_id -> list of related chunk IDs
        """
        print("\n[Pass 2.3] Finding lateral connections...")

        semaphore = asyncio.Semaphore(max_concurrent)
        connections = {}

        async def check_lateral(chunk: Dict[str, Any]):
            similar = self._find_similar_chunks(
                chunk, chunks, threshold=0.65, max_candidates=10
            )

            # Only check chunks from different sections
            different_section = [
                c
                for c in similar
                if c.get("section_title") != chunk.get("section_title")
            ]

            chunk_connections = []

            for candidate in different_section:
                async with semaphore:
                    prompt = LATERAL_CONNECTION_PROMPT.format(
                        chunk_a_content=chunk.get("content", "")[:1000],
                        chunk_a_section=chunk.get("section_title", ""),
                        chunk_b_content=candidate.get("content", "")[:1000],
                        chunk_b_section=candidate.get("section_title", ""),
                    )

                    result = await self._call_grok(
                        client, prompt, "lateral_connection_check"
                    )

                    if result.get("is_related") and result.get("confidence", 0) >= 0.7:
                        chunk_connections.append(candidate["id"])
                        self.stats["lateral_connections_found"] += 1

            if chunk_connections:
                connections[chunk["id"]] = chunk_connections

        tasks = [check_lateral(chunk) for chunk in chunks]
        await asyncio.gather(*tasks)

        print(f"  Found {self.stats['lateral_connections_found']} lateral connections")

        return connections

    async def detect_contradictions(
        self,
        client: httpx.AsyncClient,
        chunks: List[Dict[str, Any]],
        max_concurrent: int = 3,
    ) -> Dict[str, List[str]]:
        """
        Pass 2.4: Contradiction Detection

        Find conflicting or superseding chunks.

        Args:
            client: HTTP client
            chunks: All chunks with embeddings
            max_concurrent: Max concurrent LLM calls

        Returns:
            Dict of chunk_id -> list of conflicting chunk IDs
        """
        print("\n[Pass 2.4] Detecting contradictions...")

        # Group chunks by entity overlap for efficient comparison
        entity_groups = defaultdict(list)
        for chunk in chunks:
            for entity in chunk.get("entities", []):
                entity_groups[entity].append(chunk)

        semaphore = asyncio.Semaphore(max_concurrent)
        contradictions = {}

        async def check_contradiction(chunk: Dict[str, Any]):
            # Find chunks with overlapping entities
            candidates = set()
            for entity in chunk.get("entities", []):
                for candidate in entity_groups.get(entity, []):
                    if candidate["id"] != chunk["id"]:
                        candidates.add(candidate["id"])

            # Convert back to chunk objects
            candidate_chunks = [c for c in chunks if c["id"] in candidates]

            chunk_contradictions = []

            for candidate in candidate_chunks[:10]:  # Limit to 10 checks per chunk
                async with semaphore:
                    prompt = CONTRADICTION_PROMPT.format(
                        chunk_a_content=chunk.get("content", "")[:1000],
                        chunk_a_source=chunk.get("source_file", ""),
                        chunk_a_date=chunk.get("created_at", ""),
                        chunk_b_content=candidate.get("content", "")[:1000],
                        chunk_b_source=candidate.get("source_file", ""),
                        chunk_b_date=candidate.get("created_at", ""),
                    )

                    result = await self._call_claude(
                        client, prompt, "contradiction_detection"
                    )

                    if result.get("has_conflict"):
                        chunk_contradictions.append(candidate["id"])
                        self.stats["contradictions_found"] += 1

            if chunk_contradictions:
                contradictions[chunk["id"]] = chunk_contradictions

        tasks = [check_contradiction(chunk) for chunk in chunks]
        await asyncio.gather(*tasks)

        print(f"  Found {self.stats['contradictions_found']} contradictions")

        return contradictions

    async def generate_cluster_labels(
        self,
        client: httpx.AsyncClient,
        clusters: Dict[int, List[Dict[str, Any]]],
    ) -> Dict[int, Dict[str, Any]]:
        """
        Pass 2.5: Cluster Labeling

        Generate human-readable labels for topic clusters.

        Args:
            client: HTTP client
            clusters: Dict of cluster_id -> list of chunks

        Returns:
            Dict of cluster_id -> cluster metadata
        """
        print("\n[Pass 2.5] Generating cluster labels...")

        cluster_labels = {}

        for cluster_id, cluster_chunks in clusters.items():
            # Sample up to 5 representative chunks
            samples = cluster_chunks[:5]

            chunks_text = "\n\n".join(
                [
                    f"Section: {c.get('section_title', 'N/A')}\n{c.get('content', '')[:300]}"
                    for c in samples
                ]
            )

            prompt = CLUSTER_LABEL_PROMPT.format(chunks_text=chunks_text)

            result = await self._call_claude(client, prompt, "cluster_labeling")

            if result:
                cluster_labels[cluster_id] = result
                self.stats["clusters_labeled"] += 1

        print(f"  Labeled {self.stats['clusters_labeled']} clusters")

        return cluster_labels

    async def build_all_relationships(
        self,
        chunks: List[Dict[str, Any]],
        show_progress: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Run all Phase 2 passes.

        Args:
            chunks: Enriched chunks from Phase 1 (with embeddings)
            show_progress: Print progress

        Returns:
            Chunks with relationship metadata added
        """
        if show_progress:
            print(f"\n{'=' * 80}")
            print("PHASE 2: RELATIONSHIP BUILDING")
            print(f"{'=' * 80}")

        start_time = time.time()

        async with httpx.AsyncClient() as client:
            # Group chunks by source document
            chunks_by_doc = defaultdict(list)
            for chunk in chunks:
                chunks_by_doc[chunk.get("source_file", "unknown")].append(chunk)

            # 2.1: Detect process chains
            processes = await self.detect_process_chains(client, chunks_by_doc)

            # Apply process metadata to chunks
            for source_file, process_list in processes.items():
                for process in process_list:
                    for step in process.get("steps", []):
                        chunk_idx = step.get("chunk_index")
                        if chunk_idx < len(chunks_by_doc[source_file]):
                            chunk = chunks_by_doc[source_file][chunk_idx]
                            chunk["process_name"] = process.get("process_name")
                            chunk["process_step"] = step.get("step_number")

            # 2.2: Infer prerequisites
            prerequisites = await self.infer_prerequisites(
                client, chunks, max_concurrent=5
            )
            for chunk in chunks:
                chunk["prerequisite_ids"] = prerequisites.get(chunk["id"], [])

            # 2.3: Find lateral connections
            connections = await self.find_lateral_connections(
                client, chunks, max_concurrent=5
            )
            for chunk in chunks:
                chunk["see_also_ids"] = connections.get(chunk["id"], [])

            # 2.4: Detect contradictions
            contradictions = await self.detect_contradictions(
                client, chunks, max_concurrent=3
            )
            for chunk in chunks:
                chunk["contradiction_flags"] = contradictions.get(chunk["id"], [])
                chunk["needs_review"] = len(contradictions.get(chunk["id"], [])) > 0

            # 2.5: Generate cluster labels (if clusters exist)
            clusters_by_id = defaultdict(list)
            for chunk in chunks:
                if "cluster_id" in chunk and chunk["cluster_id"] != -1:
                    clusters_by_id[chunk["cluster_id"]].append(chunk)

            if clusters_by_id:
                cluster_labels = await self.generate_cluster_labels(
                    client, clusters_by_id
                )
                for chunk in chunks:
                    if chunk.get("cluster_id") in cluster_labels:
                        chunk["cluster_label"] = cluster_labels[
                            chunk["cluster_id"]
                        ].get("cluster_label")

        elapsed = time.time() - start_time

        if show_progress:
            print(f"\n{'=' * 80}")
            print(f"Phase 2 complete in {elapsed:.1f}s")
            print(f"{'=' * 80}")
            print(f"  Processes detected: {self.stats['processes_detected']}")
            print(f"  Prerequisites found: {self.stats['prerequisites_found']}")
            print(f"  Lateral connections: {self.stats['lateral_connections_found']}")
            print(f"  Contradictions found: {self.stats['contradictions_found']}")
            print(f"  Clusters labeled: {self.stats['clusters_labeled']}")
            print(f"  API calls: {self.stats['api_calls']}")
            print(f"  Total tokens: {self.stats['total_tokens']:,}")

            # Estimate cost
            estimated_cost = (
                self.stats["total_tokens"] / 1_000_000
            ) * 2.0  # Mixed pricing
            print(f"  Estimated cost: ${estimated_cost:.4f}")

        return chunks

    def get_stats(self) -> Dict[str, Any]:
        """Get relationship building statistics."""
        return self.stats


# ═══════════════════════════════════════════════════════════════════════════
# CLI TEST
# ═══════════════════════════════════════════════════════════════════════════


async def main():
    """Test the relationship builder."""
    from dotenv import load_dotenv

    load_dotenv()

    print("Relationship Builder Test - Phase 2")
    print("=" * 80)

    # Create test chunks (simulating Phase 1 output)
    test_chunks = [
        {
            "id": "chunk-1",
            "content": "Credit memos are documents used to reduce or eliminate amounts owed by customers. They are issued when goods are returned, damaged, or incorrectly charged.",
            "section_title": "Credit Memo Overview",
            "source_file": "credit_manual.docx",
            "entities": ["credit_memo", "customer"],
            "embedding": np.random.rand(1024).tolist(),  # Fake embedding
        },
        {
            "id": "chunk-2",
            "content": "To create a credit memo: 1) Verify the customer claim, 2) Check policy limits, 3) Enter details in system, 4) Submit for approval",
            "section_title": "Credit Memo Creation Process",
            "source_file": "credit_manual.docx",
            "entities": ["credit_memo"],
            "embedding": np.random.rand(1024).tolist(),
        },
        {
            "id": "chunk-3",
            "content": "To void a credit memo, navigate to the CM screen, select the memo, and click Void. You must have supervisor approval for amounts over $10k.",
            "section_title": "Voiding Credit Memos",
            "source_file": "credit_manual.docx",
            "entities": ["credit_memo"],
            "embedding": np.random.rand(1024).tolist(),
        },
    ]

    builder = RelationshipBuilder()

    print("\nBuilding relationships for 3 test chunks...")
    chunks_with_relations = await builder.build_all_relationships(test_chunks)

    print("\n" + "=" * 80)
    print("RELATIONSHIP RESULTS")
    print("=" * 80)

    for chunk in chunks_with_relations:
        print(f"\n[{chunk['id']}] {chunk['section_title']}")
        print(
            f"  Process: {chunk.get('process_name', 'None')} (step {chunk.get('process_step', 'N/A')})"
        )
        print(f"  Prerequisites: {chunk.get('prerequisite_ids', [])}")
        print(f"  See also: {chunk.get('see_also_ids', [])}")
        print(f"  Contradictions: {chunk.get('contradiction_flags', [])}")
        print(f"  Needs review: {chunk.get('needs_review', False)}")


if __name__ == "__main__":
    asyncio.run(main())
