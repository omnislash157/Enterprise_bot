#!/usr/bin/env python3
"""
Run database migration for Azure AD SSO Phase 1
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "user": os.getenv("AZURE_PG_USER", "mhartigan"),
    "password": os.getenv("AZURE_PG_PASSWORD", "Lalamoney3!"),
    "host": os.getenv("AZURE_PG_HOST", "cogtwin.postgres.database.azure.com"),
    "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
    "sslmode": "require"
}

def run_migration():
    """Run the azure_oid migration"""
    print("Connecting to database...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # Read migration file
        with open("migrations/add_azure_oid.sql", "r") as f:
            migration_sql = f.read()

        print("Running migration: add_azure_oid.sql")

        # Execute each statement
        statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]

        for statement in statements:
            if statement and not statement.startswith('SELECT'):
                print(f"  Executing: {statement[:60]}...")
                cur.execute(statement)

        conn.commit()

        # Verify the migration
        print("\nVerifying migration...")
        cur.execute("""
            SELECT
                column_name,
                data_type,
                character_maximum_length,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'enterprise'
            AND table_name = 'users'
            AND column_name = 'azure_oid'
        """)

        result = cur.fetchone()
        if result:
            print(f"✓ Column 'azure_oid' added successfully:")
            print(f"  - Type: {result[1]}")
            print(f"  - Max Length: {result[2]}")
            print(f"  - Nullable: {result[3]}")
        else:
            print("✗ Column 'azure_oid' not found!")

        # Check index
        cur.execute("""
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'enterprise'
            AND tablename = 'users'
            AND indexname = 'idx_users_azure_oid'
        """)

        if cur.fetchone():
            print("✓ Index 'idx_users_azure_oid' created successfully")
        else:
            print("✗ Index 'idx_users_azure_oid' not found!")

        print("\n✓ Migration completed successfully!")

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    run_migration()
