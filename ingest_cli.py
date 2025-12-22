#!/usr/bin/env python3
"""
Smart RAG Ingestion CLI

Enrich document chunks with LLM-generated synthetic questions and ingest to database.

Usage:
    # Scan a folder to see what would be processed
    python ingest_cli.py scan manuals/Driscoll

    # Enrich a single file (saves to JSON, no DB)
    python ingest_cli.py enrich manuals/Driscoll/Sales/sales_support_chunks.json

    # Enrich entire folder recursively
    python ingest_cli.py enrich manuals/Driscoll --recursive

    # Full pipeline: enrich + embed + save to DB
    python ingest_cli.py ingest manuals/Driscoll/Sales/sales_support_chunks.json

    # Ingest entire folder to DB (skips already ingested)
    python ingest_cli.py ingest manuals/Driscoll --recursive --skip-existing

    # Force re-ingest everything (no skip)
    python ingest_cli.py ingest manuals/Driscoll --recursive --force

    # Dry run (show what would happen)
    python ingest_cli.py ingest manuals/Driscoll --recursive --dry-run

    # Check what's in the database
    python ingest_cli.py status

Options:
    --recursive, -r     Process subfolders
    --dry-run, -n       Show what would happen without doing it
    --output, -o        Output folder for enriched JSON files
    --batch-size, -b    Chunks per batch (default: 20)
    --department, -d    Override department tag (default: infer from folder)
    --skip-existing     Skip chunks already in DB or enriched folder
    --force             Force re-process even if exists (opposite of --skip-existing)
    --verbose, -v       Show detailed progress
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv

load_dotenv(override=True)


# =============================================================================
# DEDUPLICATION
# =============================================================================


def content_hash(content: str) -> str:
    """Generate hash of content for deduplication."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()[:16]


def get_existing_hashes_from_db(db_config: Dict) -> Set[str]:
    """Get content hashes of all existing chunks in database."""
    import psycopg2

    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        # Get hashes - we'll compute from content
        cur.execute(
            """
            SELECT DISTINCT md5(content)
            FROM enterprise.documents
            WHERE is_active = TRUE
        """
        )

        hashes = {row[0] for row in cur.fetchall()}

        cur.close()
        conn.close()

        return hashes
    except Exception as e:
        print(f"Warning: Could not check existing DB entries: {e}")
        return set()


def get_existing_chunk_ids_from_db(db_config: Dict) -> Set[str]:
    """Get IDs of all existing chunks in database."""
    import psycopg2

    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        # Get source_file + section combinations as composite key
        cur.execute(
            """
            SELECT DISTINCT source_file || '::' || COALESCE(section_title, '')
            FROM enterprise.documents
            WHERE is_active = TRUE
        """
        )

        ids = {row[0] for row in cur.fetchall()}

        cur.close()
        conn.close()

        return ids
    except Exception as e:
        print(f"Warning: Could not check existing DB entries: {e}")
        return set()


def get_existing_sources_from_db(db_config: Dict) -> Set[str]:
    """Get source files already fully ingested."""
    import psycopg2

    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT DISTINCT source_file
            FROM enterprise.documents
            WHERE is_active = TRUE
        """
        )

        sources = {row[0] for row in cur.fetchall()}

        cur.close()
        conn.close()

        return sources
    except Exception as e:
        print(f"Warning: Could not check existing DB entries: {e}")
        return set()


def get_enriched_files(output_dir: Path) -> Set[str]:
    """Get stems of already enriched files."""
    if not output_dir.exists():
        return set()

    enriched = set()
    for f in output_dir.glob("*_enriched.json"):
        # Remove _enriched suffix to get original stem
        original_stem = f.stem.replace("_enriched", "")
        enriched.add(original_stem)

    return enriched


# =============================================================================
# FILE DISCOVERY
# =============================================================================


def find_chunk_files(path: Path, recursive: bool = False) -> List[Path]:
    """Find all JSON chunk files in path."""
    if path.is_file():
        if path.suffix == ".json":
            return [path]
        return []

    pattern = "**/*.json" if recursive else "*.json"
    files = list(path.glob(pattern))

    # Filter to only files that look like chunk files
    chunk_files = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                # Must have 'chunks' array
                if isinstance(data.get("chunks"), list):
                    chunk_files.append(f)
        except (json.JSONDecodeError, IOError):
            continue

    return sorted(chunk_files)


def infer_department(file_path: Path) -> str:
    """Infer department from folder structure."""
    parts = file_path.parts

    # Look for known department folders
    dept_map = {
        "sales": "sales",
        "warehouse": "warehouse",
        "credit": "credit",
        "purchasing": "purchasing",
        "transportation": "transportation",
        "operations": "operations",
        "admin": "admin",
        "hr": "hr",
    }

    for part in parts:
        lower = part.lower()
        if lower in dept_map:
            return dept_map[lower]

    return "general"


def load_chunks_from_file(
    file_path: Path, department: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Load and transform chunks from a JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    dept = department or infer_department(file_path)
    source_file = file_path.name

    chunks = []
    for i, chunk in enumerate(data.get("chunks", [])):
        content = chunk.get("content", "")

        # Transform to pipeline format
        transformed = {
            "id": chunk.get("id", f"{file_path.stem}_{i}"),
            "content": content,
            "content_hash": content_hash(content),  # For deduplication
            "section_title": _build_section_title(chunk),
            "source_file": source_file,
            "department_id": dept,
            "chunk_index": i,
            "token_count": int(len(content.split()) * 1.3),  # Rough estimate
            # Preserve original metadata
            "_original": {
                "keywords": chunk.get("keywords", []),
                "email": chunk.get("email", ""),
                "category": chunk.get("category", ""),
                "subcategory": chunk.get("subcategory", ""),
            },
        }
        chunks.append(transformed)

    return chunks


def _build_section_title(chunk: Dict) -> str:
    """Build section title from chunk metadata."""
    category = chunk.get("category", "")
    subcategory = chunk.get("subcategory", "")

    if category and subcategory:
        return f"{category} - {subcategory}"
    elif category:
        return category
    elif chunk.get("id"):
        return chunk["id"].replace("_", " ").title()
    return "Unknown Section"


# =============================================================================
# COMMANDS
# =============================================================================


async def cmd_scan(args):
    """Scan and show what would be processed."""
    path = Path(args.path)

    if not path.exists():
        print(f"ERROR: Path not found: {path}")
        return 1

    files = find_chunk_files(path, args.recursive)

    if not files:
        print(f"No chunk files found in: {path}")
        return 1

    # Check what's already in DB if requested
    existing_sources = set()
    if args.check_db:
        db_config = _get_db_config()
        if db_config:
            existing_sources = get_existing_sources_from_db(db_config)

    print(f"\n{'=' * 60}")
    print(f"SCAN RESULTS: {path}")
    print(f"{'=' * 60}")
    print(f"Recursive: {args.recursive}")
    print(f"Files found: {len(files)}")
    if args.check_db:
        print(f"Already in DB: {len(existing_sources)} source files")
    print()

    total_chunks = 0
    new_chunks = 0

    for f in files:
        chunks = load_chunks_from_file(f)
        dept = infer_department(f)
        total_chunks += len(chunks)

        rel_path = f.relative_to(path) if path.is_dir() else f.name

        in_db = f.name in existing_sources
        status = " [IN DB]" if in_db else ""

        if not in_db:
            new_chunks += len(chunks)

        print(f"  [{dept:12}] {rel_path}: {len(chunks)} chunks{status}")

    print()
    print(f"Total: {len(files)} files, {total_chunks} chunks")
    if args.check_db:
        print(f"New (not in DB): {new_chunks} chunks")

    # Estimate cost
    chunks_to_process = new_chunks if args.check_db else total_chunks
    est_cost = chunks_to_process * 4 * 0.003
    print(f"Estimated enrichment cost: ${est_cost:.2f}")

    return 0


async def cmd_enrich(args):
    """Enrich chunks with synthetic questions (no DB)."""
    from memory.ingest.smart_tagger import SmartTagger

    path = Path(args.path)
    output_dir = Path(args.output) if args.output else Path("enriched_output")

    if not path.exists():
        print(f"ERROR: Path not found: {path}")
        return 1

    files = find_chunk_files(path, args.recursive)

    if not files:
        print(f"No chunk files found in: {path}")
        return 1

    # Check what's already enriched
    already_enriched = get_enriched_files(output_dir) if args.skip_existing else set()

    # Filter files
    if args.skip_existing and not args.force:
        files_to_process = [f for f in files if f.stem not in already_enriched]
        skipped = len(files) - len(files_to_process)
        if skipped:
            print(f"Skipping {skipped} already enriched files")
        files = files_to_process

    if not files:
        print("All files already enriched. Use --force to re-process.")
        return 0

    if args.dry_run:
        print(f"\n[DRY RUN] Would enrich {len(files)} files")
        for f in files:
            chunks = load_chunks_from_file(f, args.department)
            status = " [SKIP]" if f.stem in already_enriched else ""
            print(f"  {f.name}: {len(chunks)} chunks{status}")
        return 0

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"ENRICHMENT: {path}")
    print(f"{'=' * 60}")
    print(f"Files to process: {len(files)}")
    print(f"Output: {output_dir}")
    print()

    tagger = SmartTagger()

    total_chunks = 0
    total_questions = 0

    for file_idx, file_path in enumerate(files, 1):
        print(f"\n[{file_idx}/{len(files)}] Processing: {file_path.name}")

        chunks = load_chunks_from_file(file_path, args.department)
        print(f"  Loaded {len(chunks)} chunks")

        # Enrich
        enriched = await tagger.enrich_batch(
            chunks,
            batch_size=args.batch_size,
            show_progress=args.verbose,
        )

        # Count questions generated
        for chunk in enriched:
            total_questions += len(chunk.get("synthetic_questions", []))

        total_chunks += len(enriched)

        # Save enriched output
        output_file = output_dir / f"{file_path.stem}_enriched.json"
        output_data = {
            "source_file": str(file_path),
            "enriched_at": datetime.now().isoformat(),
            "chunk_count": len(enriched),
            "chunks": enriched,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, default=str)

        print(f"  Saved: {output_file}")

        # Show sample
        if args.verbose and enriched:
            sample = enriched[0]
            print(f"\n  Sample [{sample['id']}]:")
            for q in sample.get("synthetic_questions", [])[:3]:
                print(f"    Q: {q}")

    print(f"\n{'=' * 60}")
    print(f"ENRICHMENT COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Files processed: {len(files)}")
    print(f"  Chunks enriched: {total_chunks}")
    print(f"  Questions generated: {total_questions}")
    print(f"  Output folder: {output_dir}")

    stats = tagger.get_stats()
    print(f"\n  API calls: {stats['api_calls']}")
    print(f"  Tokens used: {stats['total_tokens']:,}")
    print(f"  Errors: {stats['errors']}")

    return 0


def _get_db_config() -> Optional[Dict]:
    """Get database config from environment."""
    host = os.getenv("AZURE_PG_HOST")
    password = os.getenv("AZURE_PG_PASSWORD")

    if not host or not password:
        return None

    return {
        "host": host,
        "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
        "user": os.getenv("AZURE_PG_USER", "postgres"),
        "password": password,
        "sslmode": os.getenv("AZURE_PG_SSLMODE", "require"),
        "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    }


async def cmd_ingest(args):
    """Full pipeline: enrich + embed + save to DB."""
    from memory.ingest.enrichment_pipeline import EnrichmentPipeline

    path = Path(args.path)

    if not path.exists():
        print(f"ERROR: Path not found: {path}")
        return 1

    files = find_chunk_files(path, args.recursive)

    if not files:
        print(f"No chunk files found in: {path}")
        return 1

    # Verify DB connection
    db_config = _get_db_config()
    if not db_config:
        print(
            "ERROR: Database not configured. Set AZURE_PG_HOST and AZURE_PG_PASSWORD in .env"
        )
        return 1

    # Check what's already in DB
    existing_sources = set()
    existing_hashes = set()

    if args.skip_existing and not args.force:
        print("Checking database for existing chunks...")
        existing_sources = get_existing_sources_from_db(db_config)
        existing_hashes = get_existing_hashes_from_db(db_config)
        print(
            f"  Found {len(existing_sources)} source files, {len(existing_hashes)} chunk hashes"
        )

    # Load all chunks
    all_chunks = []
    skipped_files = 0
    skipped_chunks = 0

    for f in files:
        # Skip entire file if source already in DB
        if args.skip_existing and not args.force and f.name in existing_sources:
            skipped_files += 1
            continue

        chunks = load_chunks_from_file(f, args.department)

        # Filter out individual chunks that are already in DB (by content hash)
        if args.skip_existing and not args.force:
            new_chunks = []
            for chunk in chunks:
                # Check by content hash (md5 to match DB query)
                db_hash = hashlib.md5(chunk["content"].encode("utf-8")).hexdigest()
                if db_hash not in existing_hashes:
                    new_chunks.append(chunk)
                else:
                    skipped_chunks += 1
            chunks = new_chunks

        all_chunks.extend(chunks)

    # Report what was skipped
    if args.skip_existing and not args.force:
        if skipped_files:
            print(f"Skipped {skipped_files} files (already in DB)")
        if skipped_chunks:
            print(f"Skipped {skipped_chunks} individual chunks (already in DB)")

    if not all_chunks:
        print("\nAll chunks already in database. Use --force to re-ingest.")
        return 0

    if args.dry_run:
        print(f"\n[DRY RUN] Would ingest:")
        print(f"  Files: {len(files) - skipped_files}")
        print(f"  Total chunks: {len(all_chunks)}")

        # Show breakdown by department
        by_dept = {}
        for c in all_chunks:
            dept = c.get("department_id", "unknown")
            by_dept[dept] = by_dept.get(dept, 0) + 1

        print(f"\n  By department:")
        for dept, count in sorted(by_dept.items()):
            print(f"    {dept}: {count}")

        # Estimate cost
        est_cost = len(all_chunks) * 0.013  # ~$0.013 per chunk (enrich + embed)
        print(f"\n  Estimated cost: ${est_cost:.2f}")
        return 0

    print(f"\n{'=' * 60}")
    print(f"FULL INGESTION: {path}")
    print(f"{'=' * 60}")
    print(f"Files: {len(files) - skipped_files} (skipped {skipped_files})")
    print(f"Chunks: {len(all_chunks)} (skipped {skipped_chunks})")
    print(f"Database: {db_config['host']}")
    print()

    # Confirm
    if not args.yes:
        confirm = input("Proceed with ingestion? [y/N]: ")
        if confirm.lower() != "y":
            print("Aborted.")
            return 1

    # Run pipeline
    pipeline = EnrichmentPipeline(db_config)
    stats = await pipeline.run(all_chunks)

    print(f"\n{'=' * 60}")
    print(f"INGESTION COMPLETE")
    print(f"{'=' * 60}")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    return 0


async def cmd_status(args):
    """Show what's in the database."""
    db_config = _get_db_config()
    if not db_config:
        print("ERROR: Database not configured.")
        return 1

    import psycopg2

    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        print(f"\n{'=' * 60}")
        print("DATABASE STATUS")
        print(f"{'=' * 60}")

        # Total chunks
        cur.execute("SELECT COUNT(*) FROM enterprise.documents WHERE is_active = TRUE")
        total = cur.fetchone()[0]
        print(f"\nTotal active chunks: {total}")

        # By source file
        cur.execute(
            """
            SELECT source_file, COUNT(*) as cnt
            FROM enterprise.documents
            WHERE is_active = TRUE
            GROUP BY source_file
            ORDER BY cnt DESC
        """
        )
        sources = cur.fetchall()

        print(f"\nBy source file ({len(sources)} files):")
        for source, count in sources[:20]:
            print(f"  {source}: {count}")
        if len(sources) > 20:
            print(f"  ... and {len(sources) - 20} more")

        # By department
        cur.execute(
            """
            SELECT department_id, COUNT(*) as cnt
            FROM enterprise.documents
            WHERE is_active = TRUE
            GROUP BY department_id
            ORDER BY cnt DESC
        """
        )
        depts = cur.fetchall()

        print(f"\nBy department:")
        for dept, count in depts:
            print(f"  {dept}: {count}")

        # With synthetic questions
        cur.execute(
            """
            SELECT COUNT(*)
            FROM enterprise.documents
            WHERE is_active = TRUE
            AND array_length(synthetic_questions, 1) > 0
        """
        )
        with_questions = cur.fetchone()[0]
        print(f"\nWith synthetic questions: {with_questions}")

        # With embeddings
        cur.execute(
            """
            SELECT COUNT(*)
            FROM enterprise.documents
            WHERE is_active = TRUE
            AND embedding IS NOT NULL
        """
        )
        with_embeddings = cur.fetchone()[0]
        print(f"With embeddings: {with_embeddings}")

        # With question embeddings
        cur.execute(
            """
            SELECT COUNT(*)
            FROM enterprise.documents
            WHERE is_active = TRUE
            AND synthetic_questions_embedding IS NOT NULL
        """
        )
        with_q_embeddings = cur.fetchone()[0]
        print(f"With question embeddings: {with_q_embeddings}")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Smart RAG Ingestion CLI - Enrich documents with synthetic questions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Scan command
    scan_parser = subparsers.add_parser(
        "scan", help="Scan folder and show what would be processed"
    )
    scan_parser.add_argument("path", help="File or folder to scan")
    scan_parser.add_argument(
        "-r", "--recursive", action="store_true", help="Scan subfolders"
    )
    scan_parser.add_argument(
        "--check-db", action="store_true", help="Check what exists in DB"
    )

    # Enrich command
    enrich_parser = subparsers.add_parser(
        "enrich", help="Enrich chunks with synthetic questions (no DB)"
    )
    enrich_parser.add_argument("path", help="File or folder to enrich")
    enrich_parser.add_argument(
        "-r", "--recursive", action="store_true", help="Process subfolders"
    )
    enrich_parser.add_argument("-o", "--output", help="Output folder for enriched JSON")
    enrich_parser.add_argument(
        "-b", "--batch-size", type=int, default=20, help="Chunks per batch"
    )
    enrich_parser.add_argument("-d", "--department", help="Override department tag")
    enrich_parser.add_argument(
        "-n", "--dry-run", action="store_true", help="Show what would happen"
    )
    enrich_parser.add_argument(
        "--skip-existing", action="store_true", help="Skip already enriched files"
    )
    enrich_parser.add_argument(
        "--force", action="store_true", help="Force re-process even if exists"
    )
    enrich_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose output"
    )

    # Ingest command
    ingest_parser = subparsers.add_parser(
        "ingest", help="Full pipeline: enrich + embed + DB"
    )
    ingest_parser.add_argument("path", help="File or folder to ingest")
    ingest_parser.add_argument(
        "-r", "--recursive", action="store_true", help="Process subfolders"
    )
    ingest_parser.add_argument(
        "-b", "--batch-size", type=int, default=20, help="Chunks per batch"
    )
    ingest_parser.add_argument("-d", "--department", help="Override department tag")
    ingest_parser.add_argument(
        "-n", "--dry-run", action="store_true", help="Show what would happen"
    )
    ingest_parser.add_argument(
        "--skip-existing", action="store_true", help="Skip chunks already in DB"
    )
    ingest_parser.add_argument(
        "--force", action="store_true", help="Force re-ingest even if exists"
    )
    ingest_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation"
    )
    ingest_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose output"
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Show database status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Run command
    if args.command == "scan":
        return asyncio.run(cmd_scan(args))
    elif args.command == "enrich":
        return asyncio.run(cmd_enrich(args))
    elif args.command == "ingest":
        return asyncio.run(cmd_ingest(args))
    elif args.command == "status":
        return asyncio.run(cmd_status(args))

    return 0


if __name__ == "__main__":
    sys.exit(main())
