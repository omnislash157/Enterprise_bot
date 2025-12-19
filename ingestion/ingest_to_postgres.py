"""
PostgreSQL Ingestion Pipeline - Phase 3

Ingests JSON chunks into department_content with:
1. Deduplication (via file_hash)
2. BGE-M3 embeddings (optional - can be added later)
3. Department/tenant mapping
4. RLS context setting

Usage:
    python ingestion/ingest_to_postgres.py [--embed]

    --embed: Generate embeddings during ingestion (slow, optional)
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.json_chunk_loader import load_all_chunks, LoadedChunk, get_summary_stats

# Optional: embedder for vector generation
try:
    from embedder import AsyncEmbedder
    EMBEDDER_AVAILABLE = True
except ImportError:
    EMBEDDER_AVAILABLE = False


load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('AZURE_PG_HOST', 'cogtwin.postgres.database.azure.com'),
    'database': os.getenv('AZURE_PG_DATABASE', 'postgres'),
    'user': os.getenv('AZURE_PG_USER', 'mhartigan'),
    'password': os.getenv('AZURE_PG_PASSWORD'),
    'sslmode': 'require',
    'port': int(os.getenv('AZURE_PG_PORT', '5432'))
}


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_department_ids(conn) -> Dict[str, str]:
    """Get department slug -> UUID mapping."""
    cur = conn.cursor()
    cur.execute("SELECT slug, id FROM enterprise.departments")
    dept_map = {row[0]: str(row[1]) for row in cur.fetchall()}
    cur.close()
    return dept_map


def get_tenant_id(conn, tenant_name: str = 'Driscoll Foods') -> str:
    """Get tenant UUID by name."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM tenants WHERE name = %s", (tenant_name,))
    row = cur.fetchone()
    cur.close()
    if not row:
        raise ValueError(f"Tenant '{tenant_name}' not found")
    return str(row[0])


def check_existing_chunks(conn, file_hashes: List[str]) -> set:
    """Check which file hashes already exist in the database."""
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT file_hash FROM enterprise.department_content WHERE file_hash = ANY(%s)",
        (file_hashes,)
    )
    existing = {row[0] for row in cur.fetchall()}
    cur.close()
    return existing


async def generate_embeddings(chunks: List[LoadedChunk]) -> Dict[str, List[float]]:
    """
    Generate embeddings for all chunks.

    Returns:
        Dict mapping chunk content hash to embedding vector
    """
    if not EMBEDDER_AVAILABLE:
        print("[WARNING] Embedder not available, skipping embedding generation")
        return {}

    print(f"[EMBED] Generating embeddings for {len(chunks)} chunks...")
    embedder = AsyncEmbedder(provider="deepinfra")

    # Extract content
    contents = [chunk.content for chunk in chunks]

    # Generate embeddings in batches
    embeddings = await embedder.embed_batch(
        contents,
        batch_size=10,  # DeepInfra rate limit
        max_concurrent=2,
        show_progress=True
    )

    # Map content to embedding
    embedding_map = {}
    for chunk, embedding in zip(chunks, embeddings):
        # Use chunk ID as key
        embedding_map[chunk.chunk_id] = embedding.tolist()

    print(f"[OK] Generated {len(embedding_map)} embeddings")
    return embedding_map


def insert_chunks(
    conn,
    chunks: List[LoadedChunk],
    tenant_id: str,
    dept_map: Dict[str, str],
    embeddings: Optional[Dict[str, List[float]]] = None
):
    """
    Insert chunks into department_content table.

    Args:
        conn: Database connection
        chunks: List of LoadedChunk objects
        tenant_id: Tenant UUID
        dept_map: Department slug -> UUID mapping
        embeddings: Optional dict of chunk_id -> embedding vector
    """
    cur = conn.cursor()

    # Prepare data for bulk insert
    rows = []
    for chunk in chunks:
        # Get department UUID
        dept_id = dept_map.get(chunk.department)
        if not dept_id:
            print(f"[WARNING] Unknown department '{chunk.department}', skipping chunk {chunk.chunk_id}")
            continue

        # Get embedding if available
        embedding = None
        if embeddings and chunk.chunk_id in embeddings:
            # Convert list to PostgreSQL array format
            embedding_list = embeddings[chunk.chunk_id]
            embedding = f"[{','.join(str(x) for x in embedding_list)}]"

        # Convert keywords list to JSON string
        import json as json_module
        keywords_json = json_module.dumps(chunk.keywords)

        row = (
            tenant_id,  # tenant_id
            dept_id,  # department_id
            chunk.chunk_id,  # title
            chunk.content,  # content
            'manual',  # content_type
            None,  # version
            True,  # active
            embedding,  # embedding (vector or None)
            None,  # parent_document_id
            0,  # chunk_index
            False,  # is_document_root
            'content',  # chunk_type
            chunk.source_file,  # source_file
            chunk.file_hash,  # file_hash
            chunk.chunk_id,  # section_title
            chunk.token_count,  # chunk_token_count
            'BAAI/bge-m3',  # embedding_model
            chunk.category,  # category
            chunk.subcategory,  # subcategory
            keywords_json,  # keywords (JSON string)
        )
        rows.append(row)

    if not rows:
        print("[WARNING] No valid rows to insert")
        return 0

    # Bulk insert
    # Note: ON CONFLICT requires a unique index, which may not exist yet
    # So we'll just insert and handle duplicates manually
    insert_query = """
        INSERT INTO enterprise.department_content (
            tenant_id, department_id, title, content, content_type, version, active,
            embedding, parent_document_id, chunk_index, is_document_root, chunk_type,
            source_file, file_hash, section_title, chunk_token_count, embedding_model,
            category, subcategory, keywords
        ) VALUES %s
    """

    # Execute bulk insert
    execute_values(cur, insert_query, rows)
    inserted = cur.rowcount

    conn.commit()
    cur.close()

    return inserted


async def main(generate_embeds: bool = False):
    """Main ingestion pipeline."""
    print("=" * 80)
    print("PostgreSQL Ingestion Pipeline - Phase 3")
    print("=" * 80)

    # Load chunks
    print("\n[1/5] Loading JSON chunks...")
    chunks = load_all_chunks()
    stats = get_summary_stats(chunks)
    print(f"[OK] Loaded {stats['total_chunks']} chunks")
    print(f"  - Sales: {stats['by_department'].get('sales', 0)} chunks")
    print(f"  - Purchasing: {stats['by_department'].get('purchasing', 0)} chunks")
    print(f"  - Warehouse: {stats['by_department'].get('warehouse', 0)} chunks")
    print(f"  - Total tokens: ~{stats['total_tokens']:,}")

    # Connect to database
    print("\n[2/5] Connecting to database...")
    try:
        conn = get_db_connection()
        print(f"[OK] Connected to {DB_CONFIG['host']}")
    except Exception as e:
        print(f"[FATAL] Connection failed: {e}")
        return 1

    # Get tenant and department IDs
    print("\n[3/5] Loading tenant and department mappings...")
    try:
        tenant_id = get_tenant_id(conn, 'Driscoll Foods')
        dept_map = get_department_ids(conn)
        print(f"[OK] Tenant ID: {tenant_id}")
        print(f"[OK] Departments: {', '.join(dept_map.keys())}")
    except Exception as e:
        print(f"[ERROR] Failed to load mappings: {e}")
        conn.close()
        return 1

    # Check for existing chunks (deduplication)
    print("\n[4/5] Checking for existing chunks...")
    file_hashes = list(set(chunk.file_hash for chunk in chunks))
    existing_hashes = check_existing_chunks(conn, file_hashes)
    if existing_hashes:
        print(f"[INFO] Found {len(existing_hashes)} existing file hashes (will skip duplicates)")
        # Filter out chunks with existing hashes
        chunks_to_insert = [c for c in chunks if c.file_hash not in existing_hashes]
        print(f"[INFO] {len(chunks_to_insert)} new chunks to insert")
    else:
        chunks_to_insert = chunks
        print(f"[OK] No existing chunks found, will insert all {len(chunks)}")

    if not chunks_to_insert:
        print("[INFO] All chunks already exist in database. Nothing to do.")
        conn.close()
        return 0

    # Generate embeddings if requested
    embeddings = None
    if generate_embeds:
        print("\n[4.5/5] Generating embeddings...")
        embeddings = await generate_embeddings(chunks_to_insert)
    else:
        print("\n[4.5/5] Skipping embedding generation (use --embed to generate)")

    # Insert chunks
    print("\n[5/5] Inserting chunks into database...")
    try:
        inserted = insert_chunks(conn, chunks_to_insert, tenant_id, dept_map, embeddings)
        print(f"[OK] Inserted {inserted} chunks")
    except Exception as e:
        print(f"[ERROR] Insertion failed: {e}")
        import traceback
        traceback.print_exc()
        conn.close()
        return 1

    conn.close()

    # Summary
    print("\n" + "=" * 80)
    print("INGESTION COMPLETE")
    print("=" * 80)
    print(f"Total chunks loaded: {len(chunks)}")
    print(f"Chunks inserted: {inserted}")
    print(f"Chunks skipped (duplicates): {len(chunks) - len(chunks_to_insert)}")
    if embeddings:
        print(f"Embeddings generated: {len(embeddings)}")
    else:
        print("Embeddings: Not generated (use --embed flag)")

    print("\n[SUCCESS] Ingestion pipeline complete!")
    print("\nNext steps:")
    print("1. Verify data: SELECT count(*), department_id FROM enterprise.department_content GROUP BY department_id;")
    print("2. Test vector search: Add get_relevant_manuals() to tenant_service.py")
    print("3. Integrate with CogTwin")

    return 0


if __name__ == "__main__":
    import sys
    generate_embeds = '--embed' in sys.argv

    if generate_embeds and not EMBEDDER_AVAILABLE:
        print("[ERROR] --embed flag requires embedder.py to be available")
        sys.exit(1)

    exit_code = asyncio.run(main(generate_embeds))
    sys.exit(exit_code)
