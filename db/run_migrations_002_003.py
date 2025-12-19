"""
Run migrations 002 and 003 only (001 already exists)
"""

import psycopg2
import sys
from pathlib import Path

# Azure Flexible Server connection
CONN_PARAMS = {
    'host': 'cogtwin.postgres.database.azure.com',
    'database': 'postgres',
    'user': 'mhartigan',
    'password': 'Lalamoney3!',
    'sslmode': 'require',
    'port': 5432
}

def run_migration(conn, migration_file: Path):
    """Run a single migration file."""
    print(f"\n{'='*80}")
    print(f"Running: {migration_file.name}")
    print('='*80)

    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    cur = conn.cursor()
    try:
        # Execute the migration
        cur.execute(sql)
        conn.commit()
        print(f"[SUCCESS] {migration_file.name} executed successfully")
        return True
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {migration_file.name} failed: {e}")
        # Print more details
        import traceback
        traceback.print_exc()
        return False
    finally:
        cur.close()

def main():
    migrations_dir = Path(__file__).parent / 'migrations'

    # Only run 002 and 003
    migrations = [
        migrations_dir / '002_enhance_department_content.sql',
        migrations_dir / '003_enable_rls_policies.sql',
    ]

    print("\n" + "="*80)
    print("Azure Flexible Server Migration Runner (002 + 003)")
    print(f"Host: {CONN_PARAMS['host']}")
    print(f"Database: {CONN_PARAMS['database']}")
    print("="*80)

    # Connect
    try:
        conn = psycopg2.connect(**CONN_PARAMS)
        print("[OK] Connected to database")
    except Exception as e:
        print(f"[FATAL] Connection failed: {e}")
        sys.exit(1)

    # Run migrations
    results = []
    for migration in migrations:
        if not migration.exists():
            print(f"[SKIP] {migration.name} not found")
            results.append((migration.name, False))
            continue

        success = run_migration(conn, migration)
        results.append((migration.name, success))

    conn.close()

    # Summary
    print("\n" + "="*80)
    print("MIGRATION SUMMARY")
    print("="*80)
    for name, success in results:
        status = "[SUCCESS]" if success else "[FAILED]"
        print(f"{status} {name}")

    all_success = all(s for _, s in results)
    if all_success:
        print("\n[OK] All migrations completed successfully")
        print("\nDatabase is ready for ingestion!")
        return 0
    else:
        print("\n[ERROR] Some migrations failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
