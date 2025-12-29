#!/usr/bin/env python3
"""
Test Smart RAG Enrichment Pipeline

Place this in your enterprise_bot root directory.

Usage:
    # Set environment variables first (PowerShell):
    $env:XAI_API_KEY="xai-..."
    $env:ANTHROPIC_API_KEY="sk-..."
    $env:DEEPINFRA_API_KEY="..."
    $env:AZURE_PG_HOST="driscoll-postgres.postgres.database.azure.com"
    $env:AZURE_PG_DATABASE="postgres"
    $env:AZURE_PG_USER="..."
    $env:AZURE_PG_PASSWORD="..."
    
    # Then run:
    python test_smart_rag.py tagger   # Test just question generation
    python test_smart_rag.py embed    # Test tagger + embeddings
    python test_smart_rag.py full     # Full pipeline with DB
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv(override=True)


def check_env():
    """Check required environment variables."""
    required = [
        ("XAI_API_KEY", "Grok API for enrichment"),
        ("DEEPINFRA_API_KEY", "BGE-M3 embeddings"),
        ("AZURE_PG_HOST", "PostgreSQL host"),
        ("AZURE_PG_PASSWORD", "PostgreSQL password"),
    ]
    
    optional = [
        ("ANTHROPIC_API_KEY", "Claude for relationships (optional)"),
    ]
    
    missing = []
    for var, desc in required:
        val = os.getenv(var)
        if not val:
            missing.append(f"  {var}: {desc}")
        else:
            masked = val[:8] + "..." if len(val) > 12 else "***"
            print(f"  [OK] {var}: {masked}")
    
    for var, desc in optional:
        val = os.getenv(var)
        if val:
            masked = val[:8] + "..." if len(val) > 12 else "***"
            print(f"  [OK] {var}: {masked}")
        else:
            print(f"  [--] {var}: Not set ({desc})")
    
    if missing:
        print("\nMissing required variables:")
        for m in missing:
            print(m)
        return False
    
    return True


async def test_tagger_only():
    """Test just the smart tagger (Phase 1)."""
    from memory.ingest.smart_tagger import SmartTagger
    
    print("\n" + "=" * 60)
    print("PHASE 1 TEST: Smart Tagger")
    print("=" * 60)
    
    test_chunk = {
        "content": """Credit Memo Approval Process

To approve a credit memo for a customer dispute:

1. Review the customer's claim and supporting documentation
2. Verify the claim is within policy limits ($50,000 or less)
3. Check if customer is current on payments
4. Submit the credit memo through the system
5. For amounts over $50,000, escalate to Credit Manager

Note: All credit memos must be processed within 3 business days.""",
        "section_title": "Credit Approval Procedures",
        "source_file": "credit_policies_manual.docx",
        "department_id": "credit",
    }
    
    tagger = SmartTagger()
    enriched = await tagger.enrich_batch([test_chunk], show_progress=True)
    
    chunk = enriched[0]
    
    print("\n[SYNTHETIC QUESTIONS - THE SECRET WEAPON]")
    for i, q in enumerate(chunk.get("synthetic_questions", []), 1):
        print(f"  {i}. {q}")
    
    print("\n[SEMANTIC CLASSIFICATION]")
    print(f"  Query types: {chunk.get('query_types', [])}")
    print(f"  Entities: {chunk.get('entities', [])}")
    print(f"  Is procedure: {chunk.get('is_procedure')}")
    
    print("\n[QUALITY SCORES]")
    print(f"  Importance: {chunk.get('importance')}/10")
    print(f"  Actionability: {chunk.get('actionability_score')}/10")
    
    return chunk


async def test_embeddings(enriched_chunk):
    """Test embedding generation."""
    from memory.embedder import AsyncEmbedder
    import numpy as np
    
    print("\n" + "=" * 60)
    print("EMBEDDING TEST: Content + Questions")
    print("=" * 60)
    
    embedder = AsyncEmbedder(provider="deepinfra")
    
    # Embed content
    content = enriched_chunk.get("content", "")
    content_emb = await embedder.embed_batch([content])
    print(f"\n[CONTENT EMBEDDING]")
    print(f"  Shape: {content_emb.shape}")
    print(f"  Sample values: {content_emb[0][:5]}")
    
    # Embed questions
    questions = enriched_chunk.get("synthetic_questions", [])
    if questions:
        q_embs = await embedder.embed_batch(questions)
        avg_q_emb = np.mean(q_embs, axis=0)
        print(f"\n[QUESTION EMBEDDINGS]")
        print(f"  Questions: {len(questions)}")
        print(f"  Each shape: {q_embs[0].shape}")
        print(f"  Averaged shape: {avg_q_emb.shape}")
        
        # Test similarity
        from numpy.linalg import norm
        cos_sim = np.dot(content_emb[0], avg_q_emb) / (norm(content_emb[0]) * norm(avg_q_emb))
        print(f"\n[SIMILARITY CHECK]")
        print(f"  Content <-> Questions similarity: {cos_sim:.4f}")
        
        return content_emb[0], avg_q_emb
    
    return content_emb[0], None


async def test_full_pipeline():
    """Test the full enrichment pipeline."""
    from memory.ingest.enrichment_pipeline import EnrichmentPipeline
    
    print("\n" + "=" * 60)
    print("FULL PIPELINE TEST")
    print("=" * 60)
    
    db_config = {
        "host": os.getenv("AZURE_PG_HOST", "localhost"),
        "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
        "user": os.getenv("AZURE_PG_USER", "postgres"),
        "password": os.getenv("AZURE_PG_PASSWORD"),
        "sslmode": os.getenv("AZURE_PG_SSLMODE", "require"),
        "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    }
    
    test_chunks = [
        {
            "id": "test-1",
            "content": """Credit Memo Approval Process

To approve a credit memo for a customer dispute:
1. Review the customer's claim
2. Verify within policy limits ($50k)
3. Submit through system
4. Escalate if over $50k""",
            "section_title": "Credit Approval",
            "source_file": "credit_manual.docx",
            "department_id": "credit",
            "token_count": 80,
        },
        {
            "id": "test-2",
            "content": """Warehouse Receiving Checklist

When receiving shipments:
1. Check BOL against PO
2. Inspect for damage
3. Count and verify quantities
4. Sign BOL, note discrepancies
5. Enter receipt within 1 hour""",
            "section_title": "Receiving Procedures",
            "source_file": "warehouse_manual.docx",
            "department_id": "warehouse",
            "token_count": 70,
        },
    ]
    
    pipeline = EnrichmentPipeline(db_config)
    stats = await pipeline.run(test_chunks)
    
    print("\n[PIPELINE STATS]")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    return stats


async def main():
    """Main test runner."""
    print("=" * 60)
    print("SMART RAG ENRICHMENT PIPELINE TEST")
    print("=" * 60)
    print("\nChecking environment...")
    
    if not check_env():
        print("\nFix missing variables and try again.")
        sys.exit(1)
    
    # Parse args
    mode = sys.argv[1] if len(sys.argv) > 1 else "tagger"
    
    if mode == "tagger":
        # Just test the tagger
        chunk = await test_tagger_only()
        print("\n" + "=" * 60)
        print("Tagger test passed! Questions generated.")
        print("=" * 60)
        
    elif mode == "embed":
        # Test tagger + embeddings
        chunk = await test_tagger_only()
        await test_embeddings(chunk)
        print("\n" + "=" * 60)
        print("Embedding test passed!")
        print("=" * 60)
        
    elif mode == "full":
        # Full pipeline (requires DB)
        await test_full_pipeline()
        print("\n" + "=" * 60)
        print("Full pipeline test complete!")
        print("=" * 60)
    
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python test_smart_rag.py [tagger|embed|full]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
