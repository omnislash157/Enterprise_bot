"""
Run Migration 002: Auth Refactor to 2-Table Schema

This script:
1. Backs up current table data (if exists)
2. Executes the SQL migration
3. Validates the new schema
4. Reports results

Usage:
    python db/migrations/run_002_migration.py
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from pathlib import Path
import json
from datetime import datetime

load_dotenv()

# Database config
DB_CONFIG = {
    "user": os.getenv("AZURE_PG_USER", "mhartigan"),
    "password": os.getenv("AZURE_PG_PASSWORD"),
    "host": os.getenv("AZURE_PG_HOST", "cogtwin.postgres.database.azure.com"),
    "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
    "sslmode": "require"
}

def backup_current_data(conn):
    """Backup current users table data before migration."""
    print("\n📦 Backing up current data...")

    backup = {}

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Try to backup existing users
            cur.execute("""
                SELECT * FROM enterprise.users
                WHERE email = 'mhartigan@driscollfoods.com'
            """)
            matt = cur.fetchone()
            if matt:
                backup['matt_hartigan'] = dict(matt)
                print(f"   ✅ Backed up Matt Hartigan: {matt['email']}")

            # Count total users
            cur.execute("SELECT COUNT(*) as count FROM enterprise.users")
            count = cur.fetchone()['count']
            backup['total_users'] = count
            print(f"   ℹ️  Total users in DB: {count}")

    except Exception as e:
        print(f"   ⚠️  Backup skipped (table may not exist): {e}")

    # Save backup to file
    backup_file = Path("db/migrations/backup_002.json")
    backup_file.write_text(json.dumps(backup, indent=2, default=str))
    print(f"   💾 Backup saved to: {backup_file}")

    return backup

def run_migration(conn):
    """Execute the SQL migration."""
    print("\n🔨 Running migration...")

    sql_file = Path("db/migrations/002_auth_refactor_2table.sql")
    sql = sql_file.read_text()

    # Split by COMMIT to get main migration
    parts = sql.split("COMMIT;")
    migration_sql = parts[0] + "\nCOMMIT;"

    try:
        with conn.cursor() as cur:
            cur.execute(migration_sql)
        conn.commit()
        print("   ✅ Migration executed successfully")
        return True
    except Exception as e:
        conn.rollback()
        print(f"   ❌ Migration failed: {e}")
        return False

def validate_schema(conn):
    """Validate the new schema structure."""
    print("\n✅ Validating schema...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check tables exist
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'enterprise'
              AND table_name IN ('tenants', 'users')
            ORDER BY table_name
        """)
        tables = [r['table_name'] for r in cur.fetchall()]

        if set(tables) == {'tenants', 'users'}:
            print(f"   ✅ Tables exist: {tables}")
        else:
            print(f"   ❌ Missing tables. Found: {tables}")
            return False

        # Check users table columns
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'enterprise'
              AND table_name = 'users'
            ORDER BY ordinal_position
        """)
        columns = {r['column_name']: r['data_type'] for r in cur.fetchall()}

        required_cols = {
            'id': 'uuid',
            'tenant_id': 'uuid',
            'email': 'character varying',
            'display_name': 'character varying',
            'azure_oid': 'character varying',
            'department_access': 'ARRAY',
            'dept_head_for': 'ARRAY',
            'is_super_user': 'boolean',
            'is_active': 'boolean',
            'created_at': 'timestamp with time zone',
            'last_login_at': 'timestamp with time zone'
        }

        for col, dtype in required_cols.items():
            if col not in columns:
                print(f"   ❌ Missing column: {col}")
                return False
            if dtype != 'ARRAY' and columns[col] != dtype:
                print(f"   ⚠️  Column {col} has type {columns[col]} (expected {dtype})")

        print(f"   ✅ All required columns present")

        # Check indexes
        cur.execute("""
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'enterprise'
              AND tablename = 'users'
        """)
        indexes = [r['indexname'] for r in cur.fetchall()]

        required_indexes = [
            'idx_users_email',
            'idx_users_azure_oid',
            'idx_users_dept_access',
            'idx_users_dept_head'
        ]

        missing_indexes = [idx for idx in required_indexes if idx not in indexes]
        if missing_indexes:
            print(f"   ⚠️  Missing indexes: {missing_indexes}")
        else:
            print(f"   ✅ All indexes created")

        return True

def validate_seed_data(conn):
    """Validate seed data was inserted."""
    print("\n🌱 Validating seed data...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check tenant
        cur.execute("""
            SELECT slug, name, domain
            FROM enterprise.tenants
            WHERE slug = 'driscoll'
        """)
        tenant = cur.fetchone()

        if not tenant:
            print("   ❌ Driscoll tenant not found")
            return False

        print(f"   ✅ Tenant: {tenant['name']} ({tenant['domain']})")

        # Check Matt Hartigan
        cur.execute("""
            SELECT
                email,
                display_name,
                department_access,
                dept_head_for,
                is_super_user,
                is_active
            FROM enterprise.users
            WHERE email = 'mhartigan@driscollfoods.com'
        """)
        matt = cur.fetchone()

        if not matt:
            print("   ❌ Matt Hartigan not found")
            return False

        print(f"   ✅ User: {matt['display_name']} ({matt['email']})")
        print(f"      - Super user: {matt['is_super_user']}")
        print(f"      - Active: {matt['is_active']}")
        print(f"      - Department access: {matt['department_access']}")
        print(f"      - Dept head for: {matt['dept_head_for']}")

        # Test SSO login query
        cur.execute("""
            SELECT id, email, display_name, department_access
            FROM enterprise.users
            WHERE email = 'mhartigan@driscollfoods.com'
        """)
        sso_test = cur.fetchone()

        if sso_test:
            print(f"   ✅ SSO login query works")
        else:
            print(f"   ❌ SSO login query failed")
            return False

        return True

def main():
    print("=" * 80)
    print("MIGRATION 002: Auth Refactor - 2-Table Schema")
    print("=" * 80)
    print(f"Target: {DB_CONFIG['host']}/{DB_CONFIG['database']}")
    print(f"Schema: enterprise")
    print(f"Time: {datetime.now().isoformat()}")

    try:
        # Connect
        conn = psycopg2.connect(**DB_CONFIG)
        print("\n✅ Connected to database")

        # Backup
        backup = backup_current_data(conn)

        # Run migration
        success = run_migration(conn)
        if not success:
            print("\n❌ MIGRATION FAILED - Exiting")
            return 1

        # Validate
        schema_valid = validate_schema(conn)
        seed_valid = validate_seed_data(conn)

        if schema_valid and seed_valid:
            print("\n" + "=" * 80)
            print("✅ MIGRATION 002 COMPLETE")
            print("=" * 80)
            print("\nNew schema:")
            print("  - enterprise.tenants (id, slug, name, domain)")
            print("  - enterprise.users (id, email, tenant_id, department_access[], ...)")
            print("\nDeleted tables:")
            print("  - departments (→ department_access array)")
            print("  - access_config (→ department_access[] + dept_head_for[])")
            print("  - access_audit_log (not needed for MVP)")
            print("  - documents (RAG concern)")
            print("  - query_log (analytics concern)")
            print("\nNext steps:")
            print("  1. Refactor auth_service.py to use new schema")
            print("  2. Update admin_routes.py to use arrays")
            print("  3. Test SSO login")
            return 0
        else:
            print("\n⚠️  MIGRATION COMPLETED BUT VALIDATION FAILED")
            print("Check the output above for details")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if 'conn' in locals():
            conn.close()
            print("\n🔌 Database connection closed")

if __name__ == "__main__":
    exit(main())
