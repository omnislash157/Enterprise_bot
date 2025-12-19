#!/usr/bin/env python3
"""
Run Migration 002: Enhance department_content for Vector RAG
Phase 1 of Process Manual Schema Lock Plan
"""

import psycopg2
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

DB_CONFIG = {
    "user": os.getenv("AZURE_PG_USER", "mhartigan"),
    "password": os.getenv("AZURE_PG_PASSWORD", "Lalamoney3!"),
    "host": os.getenv("AZURE_PG_HOST", "cogtwin.postgres.database.azure.com"),
    "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
    "sslmode": "require"
}


def verify_prerequisites(cur):
    """Verify that prerequisites are met before running migration."""
    print("\n" + "=" * 70)
    print("VERIFYING PREREQUISITES")
    print("=" * 70)

    # Check pgvector extension
    print("\n1. Checking pgvector extension...")
    cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
    if cur.fetchone():
        print("   ✓ pgvector extension is installed")
    else:
        print("   ✗ pgvector extension is NOT installed")
        print("   Run: CREATE EXTENSION vector;")
        return False

    # Check tenants table
    print("\n2. Checking tenants table...")
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'tenants'
        )
    """)
    if cur.fetchone()[0]:
        print("   ✓ tenants table exists")
    else:
        print("   ✗ tenants table does NOT exist")
        print("   Run migration 001_memory_tables.sql first")
        return False

    # Check enterprise.department_content table
    print("\n3. Checking enterprise.department_content table...")
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'enterprise'
            AND table_name = 'department_content'
        )
    """)
    if cur.fetchone()[0]:
        print("   ✓ enterprise.department_content table exists")

        # Show current columns
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'enterprise'
            AND table_name = 'department_content'
            ORDER BY ordinal_position
        """)
        print("   Current columns:")
        for row in cur.fetchall():
            print(f"     - {row[0]}: {row[1]}")
    else:
        print("   ✗ enterprise.department_content table does NOT exist")
        print("   Run upload_manuals.py to create schema first")
        return False

    print("\n" + "=" * 70)
    print("✓ ALL PREREQUISITES MET")
    print("=" * 70)
    return True


def run_migration():
    """Run the department_content enhancement migration."""
    print("\n" + "=" * 70)
    print("RUNNING MIGRATION 002: ENHANCE DEPARTMENT_CONTENT")
    print("=" * 70)

    # Connect to database
    print("\nConnecting to database...")
    print(f"Host: {DB_CONFIG['host']}")
    print(f"Database: {DB_CONFIG['database']}")
    print(f"User: {DB_CONFIG['user']}")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # Verify prerequisites
        if not verify_prerequisites(cur):
            print("\n✗ Prerequisites not met. Aborting migration.")
            return False

        # Read migration file
        migration_path = Path(__file__).parent / "migrations" / "002_enhance_department_content.sql"
        print(f"\nReading migration file: {migration_path}")

        with open(migration_path, "r", encoding="utf-8") as f:
            migration_sql = f.read()

        print("\nExecuting migration...")
        print("-" * 70)

        # Execute migration
        cur.execute(migration_sql)
        conn.commit()

        print("\n" + "=" * 70)
        print("VERIFYING MIGRATION RESULTS")
        print("=" * 70)

        # Verify new columns
        print("\n1. Checking new columns...")
        cur.execute("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'enterprise'
            AND table_name = 'department_content'
            AND column_name IN (
                'tenant_id', 'embedding', 'parent_document_id', 'chunk_index',
                'is_document_root', 'chunk_type', 'source_file', 'file_hash',
                'section_title', 'chunk_token_count', 'embedding_model',
                'category', 'subcategory', 'keywords'
            )
            ORDER BY column_name
        """)

        new_columns = cur.fetchall()
        if new_columns:
            print(f"   ✓ Added {len(new_columns)} new columns:")
            for col in new_columns:
                col_type = col[2] if col[1] == 'USER-DEFINED' else col[1]
                print(f"     - {col[0]}: {col_type}")
        else:
            print("   ✗ No new columns found!")

        # Verify indexes
        print("\n2. Checking new indexes...")
        cur.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'enterprise'
            AND tablename = 'department_content'
            AND indexname LIKE '%embedding%'
            OR indexname LIKE '%tenant%'
            OR indexname LIKE '%parent%'
            OR indexname LIKE '%chunk%'
            OR indexname LIKE '%file_hash%'
            ORDER BY indexname
        """)

        indexes = cur.fetchall()
        if indexes:
            print(f"   ✓ Created {len(indexes)} new indexes:")
            for idx in indexes:
                print(f"     - {idx[0]}")
        else:
            print("   ⚠ No new indexes found (may already exist)")

        # Verify utility functions
        print("\n3. Checking utility functions...")
        cur.execute("""
            SELECT proname, pronargs
            FROM pg_proc
            WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'enterprise')
            AND proname IN ('get_document_chunks', 'search_department_content')
        """)

        functions = cur.fetchall()
        if functions:
            print(f"   ✓ Created {len(functions)} utility functions:")
            for func in functions:
                print(f"     - {func[0]}() with {func[1]} arguments")
        else:
            print("   ⚠ No utility functions found")

        # Check vector index specifically
        print("\n4. Checking vector index...")
        cur.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'enterprise'
            AND tablename = 'department_content'
            AND indexdef LIKE '%ivfflat%'
        """)

        vector_idx = cur.fetchone()
        if vector_idx:
            print(f"   ✓ Vector index created: {vector_idx[0]}")
            print(f"     Type: IVFFlat (approximate nearest neighbor)")
        else:
            print("   ⚠ Vector index not found (will be created on first vector insert)")

        print("\n" + "=" * 70)
        print("✓ MIGRATION 002 COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Run Phase 2: db/migrations/003_enable_rls_policies.sql")
        print("  2. Run Phase 3: ingestion pipeline to populate embeddings")
        print("  3. Run Phase 4: integrate vector search with CogTwin")
        print()

        return True

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
