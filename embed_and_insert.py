#!/usr/bin/env python3
"""
Embed enriched chunks and insert to PostgreSQL.

Takes enriched JSON files (output from smart_tagger) and:
1. Generates content embeddings
2. Generates question embeddings (averaged per chunk)
3. Inserts everything to enterprise.documents

Usage:
    # Single file
    python embed_and_insert.py path/to/enriched.json

    # Multiple files
    python embed_and_insert.py manuals/Driscoll/Warehouse/chunks/*_enriched.json

    # All enriched files in a directory tree
    python embed_and_insert.py --recursive manuals/
"""

import asyncio
import json
import os
import sys
from glob import glob
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

load_dotenv(override=True)


def load_enriched_chunks(json_path: str) -> List[Dict[str, Any]]:
    """Load enriched chunks from JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle both formats: {chunks: [...]} or [...]
    if isinstance(data, dict):
        chunks = data.get("chunks", [])
        source_meta = {
            "source_file": data.get("source_file", json_path),
            "enriched_at": data.get("enriched_at", ""),
        }
    else:
        chunks = data
        source_meta = {"source_file": json_path}

    # Add source metadata to each chunk
    for chunk in chunks:
        if "source_file" not in chunk or not chunk["source_file"]:
            chunk["source_file"] = source_meta["source_file"]

    return chunks


async def embed_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate embeddings for content and synthetic questions."""
    from memory.embedder import AsyncEmbedder

    embedder = AsyncEmbedder(provider="deepinfra")

    print(f"\n[EMBEDDING] Processing {len(chunks)} chunks...")

    # 1. Embed all content
    contents = [c.get("content", "") for c in chunks]
    print(f"  Embedding {len(contents)} content chunks...")
    content_embeddings = await embedder.embed_batch(
        contents,
        batch_size=32,
        max_concurrent=8,
        show_progress=True,
    )

    # 2. Embed all synthetic questions
    all_questions = []
    question_map = []  # (chunk_index, question_index)

    for i, chunk in enumerate(chunks):
        questions = chunk.get("synthetic_questions", [])
        for j, q in enumerate(questions):
            all_questions.append(q)
            question_map.append(i)

    print(f"  Embedding {len(all_questions)} synthetic questions...")
    if all_questions:
        question_embeddings = await embedder.embed_batch(
            all_questions,
            batch_size=32,
            max_concurrent=8,
            show_progress=True,
        )

        # Average question embeddings per chunk
        chunk_question_embeddings = [None] * len(chunks)
        for i in range(len(chunks)):
            chunk_q_indices = [j for j, ci in enumerate(question_map) if ci == i]
            if chunk_q_indices:
                chunk_q_embeds = [question_embeddings[j] for j in chunk_q_indices]
                avg_embed = np.mean(chunk_q_embeds, axis=0)
                chunk_question_embeddings[i] = avg_embed
    else:
        chunk_question_embeddings = [None] * len(chunks)

    # 3. Add embeddings to chunks
    for i, chunk in enumerate(chunks):
        chunk["embedding"] = content_embeddings[i].tolist()
        if chunk_question_embeddings[i] is not None:
            chunk["synthetic_questions_embedding"] = chunk_question_embeddings[
                i
            ].tolist()
        else:
            chunk["synthetic_questions_embedding"] = None

    print(f"  Done! {len(chunks)} chunks embedded.")
    return chunks


def insert_to_database(chunks: List[Dict[str, Any]], db_config: Dict[str, Any]) -> int:
    """Insert embedded chunks to enterprise.documents."""

    print(f"\n[DATABASE] Inserting {len(chunks)} chunks...")

    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()

    rows = []

    for chunk in chunks:
        # Helper functions
        def to_pg_array(lst):
            if not lst:
                return "{}"
            cleaned = []
            for x in lst:
                s = str(x).replace('"', '\\"').replace("'", "''")
                cleaned.append(f'"{s}"')
            return "{" + ",".join(cleaned) + "}"

        def to_pg_vector(vec):
            if vec is None:
                return None
            return "[" + ",".join(str(x) for x in vec) + "]"

        def to_pg_json(obj):
            return json.dumps(obj) if obj else "{}"

        # Build row tuple
        row = (
            # Core fields
            chunk.get("source_file", "unknown"),
            chunk.get("department_id", "unknown"),
            chunk.get("section_title", ""),
            chunk.get("content", ""),
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
            # Phase 2: Relationships (empty for now)
            chunk.get("process_name"),
            chunk.get("process_step"),
            to_pg_array(chunk.get("prerequisite_ids", [])),
            to_pg_array(chunk.get("see_also_ids", [])),
            to_pg_array(chunk.get("follows_ids", [])),
            # Phase 3: QA flags
            to_pg_array(chunk.get("contradiction_flags", [])),
            chunk.get("needs_review", False),
            chunk.get("review_reason"),
            # Access control - use department_id as access
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

    print(f"  Inserted {inserted} chunks to enterprise.documents")
    return inserted


def find_enriched_files(paths: List[str], recursive: bool = False) -> List[str]:
    """Find all enriched JSON files from paths."""
    files = []

    for path in paths:
        p = Path(path)

        if p.is_file() and path.endswith(".json"):
            files.append(str(p))
        elif p.is_dir():
            if recursive:
                # Find all *_enriched.json files recursively
                for f in p.rglob("*_enriched.json"):
                    files.append(str(f))
            else:
                # Just this directory
                for f in p.glob("*_enriched.json"):
                    files.append(str(f))
        elif "*" in path:
            # Glob pattern
            files.extend(glob(path))

    return sorted(set(files))


async def main():
    # Parse args
    args = sys.argv[1:]

    if not args or args[0] in ["-h", "--help"]:
        print(__doc__)
        sys.exit(0)

    recursive = False
    paths = []

    for arg in args:
        if arg == "--recursive":
            recursive = True
        else:
            paths.append(arg)

    if not paths:
        print("ERROR: No paths specified")
        print("Usage: python embed_and_insert.py [--recursive] <path> [path2] ...")
        sys.exit(1)

    # Find all enriched files
    files = find_enriched_files(paths, recursive)

    if not files:
        print(f"ERROR: No enriched JSON files found in: {paths}")
        print("Looking for files matching *_enriched.json")
        sys.exit(1)

    print(f"Found {len(files)} enriched files:")
    for f in files:
        print(f"  - {f}")

    # Load all chunks
    all_chunks = []
    for f in files:
        print(f"\nLoading: {f}")
        chunks = load_enriched_chunks(f)
        print(f"  {len(chunks)} chunks")
        all_chunks.extend(chunks)

    print(f"\n{'=' * 60}")
    print(f"TOTAL: {len(all_chunks)} chunks from {len(files)} files")
    print(f"{'=' * 60}")

    # Embed all chunks
    embedded_chunks = await embed_chunks(all_chunks)

    # Database config
    db_config = {
        "host": os.getenv("AZURE_PG_HOST", "localhost"),
        "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
        "user": os.getenv("AZURE_PG_USER", "postgres"),
        "password": os.getenv("AZURE_PG_PASSWORD"),
        "sslmode": os.getenv("AZURE_PG_SSLMODE", "require"),
        "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    }

    # Insert to database
    inserted = insert_to_database(embedded_chunks, db_config)

    print(f"\n{'=' * 60}")
    print(f"COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Files processed: {len(files)}")
    print(f"  Chunks embedded: {len(embedded_chunks)}")
    print(f"  Rows inserted: {inserted}")
    print(f"\nVerify with:")
    print(f"  SELECT COUNT(*) FROM enterprise.documents;")
    print(
        f"  SELECT section_title, synthetic_questions[1:2] FROM enterprise.documents LIMIT 5;"
    )


if __name__ == "__main__":
    asyncio.run(main())
