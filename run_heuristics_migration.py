#!/usr/bin/env python
"""
Migration Runner: Add Query Heuristics Columns
Safely applies the query heuristics migration with verification.
"""
import os
import sys
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    """Get database connection from environment."""
    # Check for Azure individual params first (most reliable)
    azure_host = os.getenv("AZURE_PG_HOST")
    if azure_host:
        return psycopg2.connect(
            host=azure_host,
            port=int(os.getenv("AZURE_PG_PORT", "5432")),
            database=os.getenv("AZURE_PG_DATABASE", "postgres"),
            user=os.getenv("AZURE_PG_USER", "postgres"),
            password=os.getenv("AZURE_PG_PASSWORD", ""),
            sslmode='require'
        )

    # Check for AZURE_PG_CONNECTION_STRING
    connection_string = os.getenv("AZURE_PG_CONNECTION_STRING")
    if connection_string:
        return psycopg2.connect(connection_string)

    # Check for DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    # Fallback to individual params
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "enterprise_bot"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "")
    )

def check_existing_columns(conn):
    """Check which columns already exist."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'enterprise'
            AND table_name = 'query_log'
            AND column_name IN (
                'complexity_score',
                'intent_type',
                'specificity_score',
                'temporal_urgency',
                'is_multi_part',
                'department_context_inferred',
                'department_context_scores',
                'session_pattern'
            )
        """)
        existing = [row[0] for row in cur.fetchall()]
    return existing

def run_migration():
    """Run the migration."""
    print("=" * 80)
    print("Query Heuristics Migration Runner")
    print("=" * 80)

    try:
        # Connect to database
        print("\n[1/5] Connecting to database...")
        conn = get_connection()
        conn.autocommit = False
        print("✓ Connected successfully")

        # Check existing columns
        print("\n[2/5] Checking existing schema...")
        existing_cols = check_existing_columns(conn)
        if existing_cols:
            print(f"⚠ Found existing columns: {', '.join(existing_cols)}")
            print("  (Migration will skip these columns)")
        else:
            print("✓ No conflicts - ready to add all columns")

        # Read migration SQL
        print("\n[3/5] Reading migration file...")
        migration_path = "migrations/add_query_heuristics_columns.sql"
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
        print(f"✓ Loaded {len(migration_sql)} bytes from {migration_path}")

        # Run migration
        print("\n[4/5] Applying migration...")
        with conn.cursor() as cur:
            cur.execute(migration_sql)
        conn.commit()
        print("✓ Migration applied successfully")

        # Verify results
        print("\n[5/5] Verifying migration...")
        with conn.cursor() as cur:
            # Check columns
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'enterprise'
                AND table_name = 'query_log'
                AND column_name IN (
                    'complexity_score',
                    'intent_type',
                    'specificity_score',
                    'temporal_urgency',
                    'is_multi_part',
                    'department_context_inferred',
                    'department_context_scores',
                    'session_pattern'
                )
                ORDER BY column_name
            """)
            columns = cur.fetchall()

            # Check indexes
            cur.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'query_log'
                AND schemaname = 'enterprise'
                AND indexname LIKE 'idx_query_log_%'
            """)
            indexes = cur.fetchall()

        print("\n✓ Verification Results:")
        print(f"\n  Columns added ({len(columns)}):")
        for col_name, data_type, is_nullable in columns:
            print(f"    • {col_name:35s} {data_type:15s} (nullable: {is_nullable})")

        print(f"\n  Indexes created ({len(indexes)}):")
        for idx_name, idx_def in indexes:
            print(f"    • {idx_name}")

        conn.close()

        print("\n" + "=" * 80)
        print("✓ MIGRATION COMPLETE")
        print("=" * 80)
        print("\nNext steps:")
        print("  1. The analytics service will now populate these columns automatically")
        print("  2. Run test_query_heuristics.py to verify the analyzers work")
        print("  3. Monitor logs for heuristics analysis output")
        print("  4. Check new API endpoints: /api/analytics/department-usage-inferred")
        print()

        return 0

    except psycopg2.Error as e:
        print(f"\n✗ Database error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return 1
    except FileNotFoundError as e:
        print(f"\n✗ Migration file not found: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return 1

if __name__ == "__main__":
    sys.exit(run_migration())
