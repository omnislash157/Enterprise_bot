"""
Smart Tagger - Phase 1: Per-Chunk LLM Enrichment

Philosophy: Spend aggressively at ingest time. Every dollar here saves $100 in bad
retrievals and user frustration.

Phase 1 enriches EACH chunk with:
- Semantic classification (query_types, verbs, entities, actors, conditions)
- Synthetic questions (5 questions this chunk answers - THE SECRET WEAPON)
- Quality scores (importance, completeness, actionability)
- Key concepts (acronyms, jargon, numeric thresholds)

Cost: ~$1.50 per 500 chunks (Grok Fast at $0.50/M tokens)
Parallelizable: Yes (20 chunks at a time)

Usage:
    tagger = SmartTagger(api_key=GROK_API_KEY)
    enriched = await tagger.enrich_batch(chunks, batch_size=20)

Version: 1.0.0
Date: 2024-12-22
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════════

SEMANTIC_CLASSIFICATION_PROMPT = """You are a document analyst for a food distribution company. Analyze this chunk and extract structured metadata.

CHUNK:
---
{content}
---

SECTION: {section_title}
SOURCE: {source_file}
DEPARTMENT: {department_id}

Extract the following. Be thorough - missing tags mean missed retrievals.

1. query_types - What kinds of questions does this answer?
   Options: how_to, policy, troubleshoot, definition, lookup, escalation, reference, compliance, training

2. verbs - What actions are described? Include ALL verbs, even implied ones.
   Common: approve, reject, submit, create, void, escalate, review, verify, process, route, receive, ship, return, cancel, modify, lookup, calculate, notify, document

3. entities - What domain objects are involved?
   Common: credit_memo, purchase_order, invoice, customer, vendor, return, shipment, pallet, BOL, driver, route, warehouse, dock, inventory, payment, discount, claim

4. actors - Who performs or is affected by these actions?
   Common: sales_rep, warehouse_mgr, credit_analyst, purchasing_agent, driver, supervisor, customer, vendor, accounting, dispatch, receiver

5. conditions - What triggers, exceptions, or contexts apply?
   Common: exception, dispute, rush_order, new_customer, over_limit, damage, shortage, late_delivery, temperature_violation, cod, prepaid, backorder

6. Document type flags:
   - is_procedure: Does this describe step-by-step instructions?
   - is_policy: Does this state rules, requirements, or compliance?
   - is_form: Does this describe a form, template, or document format?

Return ONLY valid JSON:
{{
  "query_types": [...],
  "verbs": [...],
  "entities": [...],
  "actors": [...],
  "conditions": [...],
  "is_procedure": boolean,
  "is_policy": boolean,
  "is_form": boolean
}}"""


SYNTHETIC_QUESTIONS_PROMPT = """You are creating a FAQ for a food distribution company's internal knowledge base.

Given this document chunk, generate 5 DIFFERENT questions that someone might ask that this chunk answers.

CHUNK:
---
{content}
---

SECTION: {section_title}

Requirements:
1. Questions should be natural - how a real employee would ask
2. Vary the phrasing: some direct ("How do I..."), some situational ("What if...")
3. Include at least one question that uses domain jargon
4. Include at least one question from a confused/frustrated employee
5. Rate each question's complexity: basic (1), intermediate (2), advanced (3)

Return JSON:
{{
  "questions": [
    {{"text": "How do I void a credit memo?", "complexity": 1}},
    {{"text": "What's the process when a customer disputes a credit amount?", "complexity": 2}},
    {{"text": "Can I backdate a credit memo for last month's billing cycle?", "complexity": 3}},
    {{"text": "The system won't let me submit - what am I missing?", "complexity": 1}},
    {{"text": "Who needs to approve credits over $50k?", "complexity": 2}}
  ]
}}"""


QUALITY_SCORING_PROMPT = """You are evaluating document quality for a knowledge base. Score this chunk on multiple dimensions.

CHUNK:
---
{content}
---

SECTION: {section_title}
SOURCE: {source_file}

Score each dimension 1-10:

1. importance: How critical is this information?
   - 10: Compliance-critical, legal, safety
   - 7-9: Core business process, frequently needed
   - 4-6: Standard procedure, occasional reference
   - 1-3: Nice-to-know, rare edge case

2. specificity: How narrow is the use case?
   - 10: Extremely specific edge case
   - 5: Common but bounded scenario
   - 1: Broad overview, applies widely

3. complexity: What expertise level is needed?
   - 10: Requires deep domain expertise
   - 5: Needs basic training
   - 1: Anyone could understand

4. completeness: Is this chunk self-contained?
   - 10: Fully answers the question, no other context needed
   - 5: Needs some related info
   - 1: Fragment, requires significant context

5. actionability: Can someone act on this immediately?
   - 10: Clear, specific steps they can take now
   - 5: Informative but needs interpretation
   - 1: Background info only, no direct action

Also provide:
6. confidence: How confident are you in these scores? (0.0-1.0)

Return JSON:
{{
  "importance": 7,
  "specificity": 5,
  "complexity": 4,
  "completeness": 8,
  "actionability": 9,
  "confidence": 0.85,
  "reasoning": "Core credit process, well-documented steps, self-contained"
}}"""


CONCEPT_EXTRACTION_PROMPT = """Extract specialized terminology from this document chunk.

CHUNK:
---
{content}
---

Extract:
1. acronyms: Any abbreviations with their full meanings
2. jargon: Domain-specific terms that might confuse new employees
3. numeric_thresholds: Any specific numbers, limits, or thresholds mentioned

Return JSON:
{{
  "acronyms": {{
    "BOL": "Bill of Lading",
    "PO": "Purchase Order"
  }},
  "jargon": {{
    "cross-dock": "Transferring goods directly from receiving to shipping without storage",
    "drop ship": "Shipment sent directly from vendor to customer"
  }},
  "numeric_thresholds": {{
    "credit_approval_limit": {{"value": 50000, "unit": "USD", "context": "Requires supervisor approval above this"}},
    "processing_deadline": {{"value": 3, "unit": "days", "context": "Credits must be processed within"}}
  }}
}}"""


# ═══════════════════════════════════════════════════════════════════════════
# SMART TAGGER
# ═══════════════════════════════════════════════════════════════════════════


class SmartTagger:
    """
    Phase 1: Per-chunk LLM enrichment.

    Uses Grok Fast for cheap, fast tagging. Runs 4 passes per chunk:
    1. Semantic classification
    2. Synthetic question generation
    3. Quality scoring
    4. Concept extraction

    All passes are parallelized for speed.
    """

    # Grok/xAI API endpoint (OpenAI-compatible)
    API_URL = "https://api.x.ai/v1/chat/completions"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "grok-4-1-fast-reasoning",  # Latest Grok model
        requests_per_minute: int = 60,
    ):
        """
        Initialize Smart Tagger.

        Args:
            api_key: xAI/Grok API key (or from XAI_API_KEY env)
            model: Model to use (grok-4-1-fast-reasoning recommended for quality)
            requests_per_minute: Rate limit
        """
        self.api_key = api_key or os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
        if not self.api_key:
            raise ValueError("XAI_API_KEY or GROK_API_KEY required")

        self.model = model
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self.last_request_time = 0.0
        self._rate_lock = asyncio.Lock()

        # Stats
        self.stats = {
            "chunks_enriched": 0,
            "api_calls": 0,
            "errors": 0,
            "total_tokens": 0,
            "pass_1_calls": 0,
            "pass_2_calls": 0,
            "pass_3_calls": 0,
            "pass_4_calls": 0,
        }

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        async with self._rate_lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()

    async def _call_llm(
        self,
        client: httpx.AsyncClient,
        prompt: str,
        pass_name: str,
    ) -> Dict[str, Any]:
        """
        Call Grok API with prompt.

        Args:
            client: HTTP client
            prompt: Formatted prompt
            pass_name: Name of pass (for logging)

        Returns:
            Parsed JSON response
        """
        await self._rate_limit()

        try:
            response = await client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,  # Low temp for consistent extraction
                    "max_tokens": 1000,
                    "response_format": {"type": "json_object"},
                },
                timeout=60.0,
            )

            response.raise_for_status()
            data = response.json()

            self.stats["api_calls"] += 1

            # Extract content
            content = data["choices"][0]["message"]["content"]

            # Track tokens
            usage = data.get("usage", {})
            self.stats["total_tokens"] += usage.get("total_tokens", 0)

            # Parse JSON response
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error in {pass_name}: {e}")
            self.stats["errors"] += 1
            return {}

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error in {pass_name}: {e.response.status_code}")
            self.stats["errors"] += 1
            return {}

        except Exception as e:
            logger.error(f"Error in {pass_name}: {e}")
            self.stats["errors"] += 1
            return {}

    async def classify_semantics(
        self,
        client: httpx.AsyncClient,
        chunk: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Pass 1.1: Semantic Classification

        Extract query_types, verbs, entities, actors, conditions, and type flags.
        """
        self.stats["pass_1_calls"] += 1

        prompt = SEMANTIC_CLASSIFICATION_PROMPT.format(
            content=chunk.get("content", ""),
            section_title=chunk.get("section_title", ""),
            source_file=chunk.get("source_file", ""),
            department_id=chunk.get("department_id", ""),
        )

        result = await self._call_llm(client, prompt, "semantic_classification")

        # Ensure all fields exist with defaults
        return {
            "query_types": result.get("query_types", []),
            "verbs": result.get("verbs", []),
            "entities": result.get("entities", []),
            "actors": result.get("actors", []),
            "conditions": result.get("conditions", []),
            "is_procedure": result.get("is_procedure", False),
            "is_policy": result.get("is_policy", False),
            "is_form": result.get("is_form", False),
        }

    async def generate_questions(
        self,
        client: httpx.AsyncClient,
        chunk: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Pass 1.2: Synthetic Question Generation

        Generate 5 questions this chunk answers.
        """
        self.stats["pass_2_calls"] += 1

        prompt = SYNTHETIC_QUESTIONS_PROMPT.format(
            content=chunk.get("content", ""),
            section_title=chunk.get("section_title", ""),
        )

        result = await self._call_llm(client, prompt, "question_generation")

        # Extract just the text of questions
        questions = result.get("questions", [])
        return {
            "synthetic_questions": [
                q.get("text", "") for q in questions if q.get("text")
            ],
            "question_complexity": [q.get("complexity", 1) for q in questions],
        }

    async def score_quality(
        self,
        client: httpx.AsyncClient,
        chunk: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Pass 1.3: Quality & Importance Scoring

        Score importance, specificity, complexity, completeness, actionability.
        """
        self.stats["pass_3_calls"] += 1

        prompt = QUALITY_SCORING_PROMPT.format(
            content=chunk.get("content", ""),
            section_title=chunk.get("section_title", ""),
            source_file=chunk.get("source_file", ""),
        )

        result = await self._call_llm(client, prompt, "quality_scoring")

        return {
            "importance": result.get("importance", 5),
            "specificity": result.get("specificity", 5),
            "complexity": result.get("complexity", 5),
            "completeness_score": result.get("completeness", 5),
            "actionability_score": result.get("actionability", 5),
            "confidence_score": result.get("confidence", 0.7),
            "quality_reasoning": result.get("reasoning", ""),
        }

    async def extract_concepts(
        self,
        client: httpx.AsyncClient,
        chunk: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Pass 1.4: Key Concept Extraction

        Extract acronyms, jargon, numeric thresholds.
        """
        self.stats["pass_4_calls"] += 1

        prompt = CONCEPT_EXTRACTION_PROMPT.format(
            content=chunk.get("content", ""),
        )

        result = await self._call_llm(client, prompt, "concept_extraction")

        return {
            "acronyms": result.get("acronyms", {}),
            "jargon": result.get("jargon", {}),
            "numeric_thresholds": result.get("numeric_thresholds", {}),
        }

    async def enrich_chunk(
        self,
        client: httpx.AsyncClient,
        chunk: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run all Phase 1 passes on a single chunk.

        All passes run in parallel for speed.

        Args:
            client: HTTP client
            chunk: Chunk dict with content, section_title, etc.

        Returns:
            Enriched chunk with all Phase 1 metadata
        """
        # Run all 4 passes in parallel
        classification, questions, scores, concepts = await asyncio.gather(
            self.classify_semantics(client, chunk),
            self.generate_questions(client, chunk),
            self.score_quality(client, chunk),
            self.extract_concepts(client, chunk),
        )

        # Merge results into chunk
        enriched = {
            **chunk,
            **classification,
            **questions,
            **scores,
            **concepts,
        }

        self.stats["chunks_enriched"] += 1

        return enriched

    async def enrich_batch(
        self,
        chunks: List[Dict[str, Any]],
        batch_size: int = 20,
        max_concurrent: int = 10,
        show_progress: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Enrich a batch of chunks.

        Args:
            chunks: List of chunk dicts
            batch_size: Not used (kept for API consistency)
            max_concurrent: Max concurrent chunk enrichments
            show_progress: Print progress

        Returns:
            List of enriched chunks
        """
        if show_progress:
            print(f"Enriching {len(chunks)} chunks with {self.model}...")

        semaphore = asyncio.Semaphore(max_concurrent)

        async def enrich_with_semaphore(
            client: httpx.AsyncClient, chunk: Dict[str, Any], idx: int
        ):
            async with semaphore:
                enriched = await self.enrich_chunk(client, chunk)

                if show_progress and (idx + 1) % 10 == 0:
                    print(f"  Progress: {idx + 1}/{len(chunks)}")

                return enriched

        start_time = time.time()

        async with httpx.AsyncClient() as client:
            tasks = [
                enrich_with_semaphore(client, chunk, i)
                for i, chunk in enumerate(chunks)
            ]
            results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        if show_progress:
            print(f"Enriched {len(chunks)} chunks in {elapsed:.1f}s")
            print(f"Rate: {len(chunks) / elapsed:.1f} chunks/sec")
            print(f"Total tokens: {self.stats['total_tokens']:,}")
            # Estimate cost (grok-4-1-fast-reasoning: ~$2/M tokens, mixed input/output)
            estimated_cost = (self.stats["total_tokens"] / 1_000_000) * 2.0
            print(f"Estimated cost: ${estimated_cost:.4f}")

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get enrichment statistics."""
        return self.stats


# ═══════════════════════════════════════════════════════════════════════════
# CLI TEST
# ═══════════════════════════════════════════════════════════════════════════


async def main():
    """Test the tagger."""
    from dotenv import load_dotenv

    load_dotenv()

    print("Smart Tagger Test - Phase 1 Enrichment")
    print("=" * 80)

    # Create test chunk
    test_chunk = {
        "content": """Credit Memo Approval Process

To approve a credit memo for a customer dispute:

1. Review the customer's claim and supporting documentation (photos, BOL, delivery receipt)
2. Verify the claim is within policy limits ($50,000 or less)
3. Check if customer is current on payments (no overdue invoices)
4. Submit the credit memo through the system
5. For amounts over $50,000, escalate to the Credit Manager for approval

Note: All credit memos must be processed within 3 business days of receipt.
""",
        "section_title": "Credit Approval Procedures",
        "source_file": "credit_policies_manual.docx",
        "department_id": "credit",
        "chunk_index": 5,
    }

    tagger = SmartTagger()

    print(f"\nEnriching test chunk from: {test_chunk['source_file']}")
    enriched = await tagger.enrich_batch([test_chunk], show_progress=True)

    print("\n" + "=" * 80)
    print("ENRICHMENT RESULTS")
    print("=" * 80)

    chunk = enriched[0]

    print("\n[SEMANTIC CLASSIFICATION]")
    print(f"  Query types: {chunk.get('query_types', [])}")
    print(f"  Verbs: {chunk.get('verbs', [])}")
    print(f"  Entities: {chunk.get('entities', [])}")
    print(f"  Actors: {chunk.get('actors', [])}")
    print(f"  Conditions: {chunk.get('conditions', [])}")
    print(f"  Is procedure: {chunk.get('is_procedure', False)}")
    print(f"  Is policy: {chunk.get('is_policy', False)}")

    print("\n[SYNTHETIC QUESTIONS]")
    for i, q in enumerate(chunk.get("synthetic_questions", []), 1):
        print(f"  {i}. {q}")

    print("\n[QUALITY SCORES]")
    print(f"  Importance: {chunk.get('importance', 0)}/10")
    print(f"  Specificity: {chunk.get('specificity', 0)}/10")
    print(f"  Complexity: {chunk.get('complexity', 0)}/10")
    print(f"  Completeness: {chunk.get('completeness_score', 0)}/10")
    print(f"  Actionability: {chunk.get('actionability_score', 0)}/10")
    print(f"  Confidence: {chunk.get('confidence_score', 0):.2f}")
    print(f"  Reasoning: {chunk.get('quality_reasoning', '')}")

    print("\n[KEY CONCEPTS]")
    print(f"  Acronyms: {chunk.get('acronyms', {})}")
    print(f"  Jargon: {chunk.get('jargon', {})}")
    print(f"  Numeric thresholds: {chunk.get('numeric_thresholds', {})}")

    print("\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)
    stats = tagger.get_stats()
    print(f"  API calls: {stats['api_calls']}")
    print(f"  Pass 1 (semantic): {stats['pass_1_calls']}")
    print(f"  Pass 2 (questions): {stats['pass_2_calls']}")
    print(f"  Pass 3 (quality): {stats['pass_3_calls']}")
    print(f"  Pass 4 (concepts): {stats['pass_4_calls']}")
    print(f"  Errors: {stats['errors']}")


if __name__ == "__main__":
    asyncio.run(main())
