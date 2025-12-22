#!/usr/bin/env python3
"""
Enrich pre-chunked sales support data with synthetic questions.

Usage:
    python enrich_sales_chunks.py tagger    # Just generate questions (no DB)
    python enrich_sales_chunks.py full      # Full pipeline with DB insert
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)


def load_chunks(json_path: str) -> list:
    """Load chunks from JSON and transform to pipeline format."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = []
    for chunk in data.get("chunks", []):
        # Transform to pipeline expected format
        transformed = {
            "id": chunk.get("id"),
            "content": chunk.get("content", ""),
            "section_title": f"{chunk.get('category', '')} - {chunk.get('subcategory', '')}",
            "source_file": "sales_support_chunks.json",
            "department_id": "sales",  # All sales support
            "chunk_index": len(chunks),
            # Preserve original metadata
            "original_keywords": chunk.get("keywords", []),
            "email": chunk.get("email", ""),
            "category": chunk.get("category", ""),
            "subcategory": chunk.get("subcategory", ""),
        }
        chunks.append(transformed)

    return chunks


async def enrich_only(chunks: list):
    """Run Phase 1 enrichment only (no DB)."""
    from memory.ingest.smart_tagger import SmartTagger

    print(f"\n{'=' * 60}")
    print(f"ENRICHING {len(chunks)} SALES SUPPORT CHUNKS")
    print(f"{'=' * 60}")

    tagger = SmartTagger()
    enriched = await tagger.enrich_batch(chunks, show_progress=True)

    # Show results
    print(f"\n{'=' * 60}")
    print("ENRICHMENT RESULTS")
    print(f"{'=' * 60}")

    for chunk in enriched:
        print(f"\n[{chunk['id']}] {chunk['section_title']}")
        print(f"  Original keywords: {chunk.get('original_keywords', [])}")
        print(f"  Email: {chunk.get('email', 'N/A')}")
        print(f"\n  SYNTHETIC QUESTIONS:")
        for i, q in enumerate(chunk.get("synthetic_questions", []), 1):
            print(f"    {i}. {q}")
        print(f"\n  Entities: {chunk.get('entities', [])}")
        print(f"  Query types: {chunk.get('query_types', [])}")
        print(f"  Importance: {chunk.get('importance', 0)}/10")
        print("-" * 40)

    # Save enriched to JSON for inspection
    output_path = "sales_support_enriched.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2)
    print(f"\nSaved enriched chunks to: {output_path}")

    return enriched


async def full_pipeline(chunks: list):
    """Run full pipeline with DB insertion."""
    from memory.ingest.enrichment_pipeline import EnrichmentPipeline

    db_config = {
        "host": os.getenv("AZURE_PG_HOST", "localhost"),
        "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
        "user": os.getenv("AZURE_PG_USER", "postgres"),
        "password": os.getenv("AZURE_PG_PASSWORD"),
        "sslmode": os.getenv("AZURE_PG_SSLMODE", "require"),
        "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    }

    pipeline = EnrichmentPipeline(db_config)
    stats = await pipeline.run(chunks)

    return stats


async def main():
    # Find the JSON file
    json_path = "sales_support_chunks.json"
    if not Path(json_path).exists():
        # Try uploads folder
        json_path = Path(__file__).parent / "sales_support_chunks.json"
        if not json_path.exists():
            print(f"ERROR: Cannot find {json_path}")
            print(
                "Place sales_support_chunks.json in the same directory as this script."
            )
            sys.exit(1)

    print(f"Loading chunks from: {json_path}")
    chunks = load_chunks(str(json_path))
    print(f"Loaded {len(chunks)} chunks")

    # Parse mode
    mode = sys.argv[1] if len(sys.argv) > 1 else "tagger"

    if mode == "tagger":
        await enrich_only(chunks)
    elif mode == "full":
        await full_pipeline(chunks)
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python enrich_sales_chunks.py [tagger|full]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
