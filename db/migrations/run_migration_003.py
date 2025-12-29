#!/usr/bin/env python3
"""
Run Migration 003: Smart Documents Schema

Usage:
    python run_migration_003.py

Requires:
    - .env file with Azure PostgreSQL credentials
    - 003_smart_documents.sql in same directory or db/migrations/
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import psycopg2
try:
    import psycopg2
except ImportError:
    print("[ERROR] psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)


def get_connection():
    """Build connection from environment variables."""
    conn_params = {
        "host": os.getenv("AZURE_PG_HOST", "cogtwin.postgres.database.azure.com"),
        "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
        "user": os.getenv("AZURE_PG_USER", "mhartigan"),
        "password": os.getenv("AZURE_PG_PASSWORD"),
        "port": int(os.getenv("AZURE_PG_PORT", "5432")),
        "sslmode": "require",
    }

    if not conn_params["password"]:
        print("[ERROR] AZURE_PG_PASSWORD not set in .env")
        sys.exit(1)

    print(f"[INFO] Connecting to {conn_params['host']}...")
    return psycopg2.connect(**conn_params)


def find_sql_file():
    """Find the migration SQL file."""
    candidates = [
        Path("003_smart_documents.sql"),
        Path("db/migrations/003_smart_documents.sql"),
        Path(__file__).parent / "003_smart_documents.sql",
        Path(__file__).parent / "db/migrations/003_smart_documents.sql",
    ]

    for path in candidates:
        if path.exists():
            return path

    print("[ERROR] Could not find 003_smart_documents.sql")
    print("  Searched:")
    for p in candidates:
        print(f"    - {p.absolute()}")
    sys.exit(1)


def run_migration():
    """Execute the migration."""
    sql = sql_file.read_text(encoding="utf-8")
    print(f"[INFO] Found migration: {sql_file}")

    # Read SQL
    sql = sql_file.read_text()
    print(f"[INFO] Loaded {len(sql):,} bytes of SQL")

    # Connect and execute
    conn = get_connection()
    cur = conn.cursor()

    try:
        print("[INFO] Running migration...")
        cur.execute(sql)
        conn.commit()
        print("[OK] Migration 003 complete!")

        # Verify table exists
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'enterprise'
            AND table_name = 'documents'
            ORDER BY ordinal_position
            LIMIT 10
        """
        )
        columns = [row[0] for row in cur.fetchall()]
        print(
            f"[OK] Table enterprise.documents created with columns: {', '.join(columns)}..."
        )

        # Count indexes
        cur.execute(
            """
            SELECT count(*)
            FROM pg_indexes
            WHERE schemaname = 'enterprise'
            AND tablename = 'documents'
        """
        )
        idx_count = cur.fetchone()[0]
        print(f"[OK] {idx_count} indexes created")

    except psycopg2.Error as e:
        conn.rollback()
        print(f"[ERROR] Migration failed: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

    print("\n[NEXT STEPS]")
    print("  1. Run ingestion to populate table")
    print("  2. After data load: VACUUM ANALYZE enterprise.documents;")


if __name__ == "__main__":
    print("=" * 60)
    print("Migration 003: Smart Documents Schema")
    print("=" * 60)
    run_migration()
