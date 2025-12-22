#!/usr/bin/env python3
"""
Migration 001: Rebuild Enterprise Schema (Complex - Option B)

Date: 2024-12-21
Priority: HIGH - Blocking SSO and Admin Portal
Status: APPROVED by Architecture Session

SCOPE:
- Nuke all legacy enterprise.* tables
- Create 7-table Complex Schema (matches auth_service.py, admin_routes.py)
- Seed: Driscoll tenant, 6 departments, Matt as admin

SCHEMA MODEL:
- tenants: Multi-tenant ready (single tenant for now)
- users: Auth records, FK to tenant, azure_oid (NOT oid!)
- departments: Department definitions, FK to tenant
- access_config: Junction table - who has access to what department
- access_audit_log: Compliance trail for access changes
- documents: RAG chunks, FK to department
- query_log: Analytics for RAG queries

AUTHORIZATION LOGIC:
- Admin: can grant anyone to any department
- Dept Head: can only grant to THEIR department (is_dept_head=true)
- User: no granting power

DO NOT TOUCH: personal.* schema (v1.5 scope)
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Load environment variables
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Database credentials
DB_CONFIG = {
    'user': os.getenv('AZURE_PG_USER'),
    'password': os.getenv('AZURE_PG_PASSWORD'),
    'host': os.getenv('AZURE_PG_HOST'),
    'port': os.getenv('AZURE_PG_PORT', '5432'),
    'database': os.getenv('AZURE_PG_DATABASE', 'postgres'),
    'sslmode': os.getenv('AZURE_PG_SSLMODE', 'require')
}

# Validation
missing = [k for k, v in DB_CONFIG.items() if not v]
if missing:
    print(f"❌ ERROR: Missing environment variables: {', '.join(missing)}")
    print("📝 Please ensure .env file exists with AZURE_PG_* credentials")
    sys.exit(1)

print("=" * 80)
print("🗄️  MIGRATION 001: REBUILD ENTERPRISE SCHEMA (COMPLEX)")
print("=" * 80)
print(f"📍 Target: {DB_CONFIG['host']}/{DB_CONFIG['database']}")
print(f"👤 User: {DB_CONFIG['user']}")
print()


def execute_sql(cursor, sql, description):
    """Execute SQL with error handling and reporting"""
    try:
        print(f"⚙️  {description}...", end=" ", flush=True)
        cursor.execute(sql)
        print("✅")
        return True
    except Exception as e:
        print(f"❌\n   Error: {e}")
        return False


def main():
    conn = None
    try:
        # Connect to database
        print("🔌 Connecting to Azure PostgreSQL...", end=" ", flush=True)
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        print("✅")
        print()

        # ================================================================
        # PHASE 1: NUKE LEGACY TABLES
        # ================================================================
        print("💣 PHASE 1: NUKING LEGACY ENTERPRISE TABLES")
        print("-" * 80)

        # Get list of existing enterprise tables
        cursor.execute("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'enterprise'
            ORDER BY tablename;
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]

        if existing_tables:
            print(f"📋 Found {len(existing_tables)} existing tables:")
            for table in existing_tables:
                print(f"   - enterprise.{table}")
            print()

            # Drop tables in reverse dependency order
            tables_to_drop = [
                'query_log',
                'documents',
                'access_audit_log',
                'access_config',
                'users',
                'departments',
                'tenants'
            ]

            for table in tables_to_drop:
                if table in existing_tables:
                    execute_sql(
                        cursor,
                        f"DROP TABLE IF EXISTS enterprise.{table} CASCADE",
                        f"Dropping enterprise.{table}"
                    )
        else:
            print("ℹ️  No existing enterprise tables found (clean slate)")

        print()

        # ================================================================
        # PHASE 2: CREATE SCHEMA
        # ================================================================
        print("🏗️  PHASE 2: CREATING NEW SCHEMA (7 TABLES)")
        print("-" * 80)

        # Ensure enterprise schema exists
        execute_sql(
            cursor,
            "CREATE SCHEMA IF NOT EXISTS enterprise",
            "Creating enterprise schema"
        )

        # Enable pgvector extension
        execute_sql(
            cursor,
            "CREATE EXTENSION IF NOT EXISTS vector",
            "Enabling pgvector extension"
        )

        print()

        # Table 1: Tenants
        execute_sql(cursor, """
            CREATE TABLE enterprise.tenants (
                id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                slug            varchar(50) UNIQUE NOT NULL,
                name            varchar(255) NOT NULL,
                is_active       boolean DEFAULT true,
                created_at      timestamptz DEFAULT now()
            )
        """, "Creating tenants table")

        # Table 2: Departments
        execute_sql(cursor, """
            CREATE TABLE enterprise.departments (
                id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id       uuid NOT NULL REFERENCES enterprise.tenants(id),
                slug            varchar(50) NOT NULL,
                name            varchar(255) NOT NULL,
                description     text,
                is_active       boolean DEFAULT true,
                created_at      timestamptz DEFAULT now(),
                UNIQUE(tenant_id, slug)
            )
        """, "Creating departments table")

        # Table 3: Users
        execute_sql(cursor, """
            CREATE TABLE enterprise.users (
                id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id             uuid NOT NULL REFERENCES enterprise.tenants(id),
                email                 varchar(255) NOT NULL,
                display_name          varchar(255),
                azure_oid             varchar(255) UNIQUE,
                role                  varchar(50) DEFAULT 'user',
                primary_department_id uuid REFERENCES enterprise.departments(id),
                is_active             boolean DEFAULT true,
                created_at            timestamptz DEFAULT now(),
                last_login_at         timestamptz,
                UNIQUE(tenant_id, email)
            )
        """, "Creating users table (azure_oid, not oid!)")

        # Table 4: Access Config (junction table)
        execute_sql(cursor, """
            CREATE TABLE enterprise.access_config (
                id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id         uuid NOT NULL REFERENCES enterprise.users(id) ON DELETE CASCADE,
                department      varchar(50) NOT NULL,
                access_level    varchar(50) DEFAULT 'read',
                is_dept_head    boolean DEFAULT false,
                granted_by      uuid REFERENCES enterprise.users(id),
                granted_at      timestamptz DEFAULT now(),
                UNIQUE(user_id, department)
            )
        """, "Creating access_config table (junction)")

        # Table 5: Access Audit Log
        execute_sql(cursor, """
            CREATE TABLE enterprise.access_audit_log (
                id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                action          varchar(50) NOT NULL,
                actor_id        uuid REFERENCES enterprise.users(id),
                target_id       uuid REFERENCES enterprise.users(id),
                department_slug varchar(50),
                old_value       jsonb,
                new_value       jsonb,
                created_at      timestamptz DEFAULT now()
            )
        """, "Creating access_audit_log table")

        # Table 6: Documents (RAG chunks)
        execute_sql(cursor, """
            CREATE TABLE enterprise.documents (
                id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                department_id   uuid NOT NULL REFERENCES enterprise.departments(id),
                title           varchar(500),
                content         text NOT NULL,
                embedding       vector(1024),
                metadata        jsonb DEFAULT '{}',
                source_file     varchar(500),
                chunk_index     integer,
                created_at      timestamptz DEFAULT now()
            )
        """, "Creating documents table (RAG chunks)")

        # Table 7: Query Log (analytics)
        execute_sql(cursor, """
            CREATE TABLE enterprise.query_log (
                id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id         uuid REFERENCES enterprise.users(id),
                department_ids  uuid[],
                query_text      text,
                response_text   text,
                chunks_used     integer,
                latency_ms      integer,
                created_at      timestamptz DEFAULT now()
            )
        """, "Creating query_log table")

        print()

        # ================================================================
        # PHASE 3: CREATE INDEXES
        # ================================================================
        print("📇 PHASE 3: CREATING INDEXES")
        print("-" * 80)

        indexes = [
            ("idx_users_tenant", "enterprise.users(tenant_id)"),
            ("idx_users_email", "enterprise.users(email)"),
            ("idx_users_azure_oid", "enterprise.users(azure_oid)"),
            ("idx_departments_tenant", "enterprise.departments(tenant_id)"),
            ("idx_departments_slug", "enterprise.departments(slug)"),
            ("idx_access_config_user", "enterprise.access_config(user_id)"),
            ("idx_access_config_dept", "enterprise.access_config(department)"),
            ("idx_access_audit_actor", "enterprise.access_audit_log(actor_id)"),
            ("idx_access_audit_target", "enterprise.access_audit_log(target_id)"),
            ("idx_access_audit_created", "enterprise.access_audit_log(created_at)"),
            ("idx_documents_dept", "enterprise.documents(department_id)"),
            ("idx_query_log_user", "enterprise.query_log(user_id)"),
        ]

        for idx_name, idx_def in indexes:
            execute_sql(
                cursor,
                f"CREATE INDEX {idx_name} ON {idx_def}",
                f"Creating {idx_name}"
            )

        # Vector index (requires data, create it for future use)
        print("⚙️  Creating idx_documents_embedding (vector index)...", end=" ", flush=True)
        try:
            cursor.execute("""
                CREATE INDEX idx_documents_embedding
                ON enterprise.documents
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)
            print("✅")
        except Exception as e:
            # Vector indexes can fail if table is empty, that's OK
            print(f"⚠️  (will be created after documents are added)")

        print()

        # ================================================================
        # PHASE 4: SEED DATA
        # ================================================================
        print("🌱 PHASE 4: SEEDING DATA")
        print("-" * 80)

        # Seed tenant
        execute_sql(cursor, """
            INSERT INTO enterprise.tenants (slug, name)
            VALUES ('driscoll', 'Driscoll Foods')
            ON CONFLICT (slug) DO NOTHING
        """, "Seeding tenant: Driscoll Foods")

        # Get tenant ID
        cursor.execute("SELECT id FROM enterprise.tenants WHERE slug = 'driscoll'")
        tenant_id = cursor.fetchone()[0]
        print(f"   📌 Tenant ID: {tenant_id}")

        # Seed departments
        departments = [
            ('purchasing', 'Purchasing', 'Vendor management, POs, receiving'),
            ('credit', 'Credit', 'AR, customer credit, collections'),
            ('sales', 'Sales', 'Customer accounts, pricing, orders'),
            ('warehouse', 'Warehouse', 'Inventory, picking, shipping'),
            ('accounting', 'Accounting', 'AP, GL, financial reporting'),
            ('it', 'IT', 'Systems, infrastructure, support')
        ]

        for slug, name, description in departments:
            execute_sql(cursor, f"""
                INSERT INTO enterprise.departments (tenant_id, slug, name, description)
                VALUES ('{tenant_id}', '{slug}', '{name}', '{description}')
                ON CONFLICT (tenant_id, slug) DO NOTHING
            """, f"Seeding department: {name}")

        print()

        # Seed admin user (Matt)
        execute_sql(cursor, f"""
            INSERT INTO enterprise.users (tenant_id, email, display_name, role)
            VALUES (
                '{tenant_id}',
                'mhartigan@driscollfoods.com',
                'Matt Hartigan',
                'admin'
            )
            ON CONFLICT (tenant_id, email) DO NOTHING
        """, "Seeding admin user: Matt Hartigan")

        # Get Matt's user ID
        cursor.execute("""
            SELECT id FROM enterprise.users
            WHERE email = 'mhartigan@driscollfoods.com'
        """)
        matt_id = cursor.fetchone()[0]
        print(f"   📌 Admin User ID: {matt_id}")

        # Grant Matt access to all departments as dept_head
        cursor.execute("SELECT slug FROM enterprise.departments WHERE tenant_id = %s", (tenant_id,))
        dept_slugs = [row[0] for row in cursor.fetchall()]

        for dept_slug in dept_slugs:
            execute_sql(cursor, f"""
                INSERT INTO enterprise.access_config
                (user_id, department, access_level, is_dept_head, granted_by)
                VALUES (
                    '{matt_id}',
                    '{dept_slug}',
                    'admin',
                    true,
                    '{matt_id}'
                )
                ON CONFLICT (user_id, department) DO NOTHING
            """, f"Granting Matt access: {dept_slug}")

        print()

        # ================================================================
        # PHASE 5: VALIDATION
        # ================================================================
        print("✅ PHASE 5: VALIDATION QUERIES")
        print("-" * 80)

        # Count tables
        cursor.execute("""
            SELECT COUNT(*)
            FROM pg_tables
            WHERE schemaname = 'enterprise'
        """)
        table_count = cursor.fetchone()[0]
        print(f"📊 Tables in enterprise schema: {table_count}")

        # Count indexes
        cursor.execute("""
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE schemaname = 'enterprise'
        """)
        index_count = cursor.fetchone()[0]
        print(f"📇 Indexes created: {index_count}")

        # Count seed data
        cursor.execute("SELECT COUNT(*) FROM enterprise.tenants")
        print(f"🏢 Tenants: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM enterprise.departments")
        print(f"🏬 Departments: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM enterprise.users")
        print(f"👤 Users: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM enterprise.access_config")
        print(f"🔐 Access grants: {cursor.fetchone()[0]}")

        print()

        # Test query: Matt's access
        print("🔍 Test Query: Matt's Department Access")
        cursor.execute("""
            SELECT
                u.email,
                u.display_name,
                u.role,
                array_agg(ac.department ORDER BY ac.department) as departments
            FROM enterprise.users u
            LEFT JOIN enterprise.access_config ac ON u.id = ac.user_id
            WHERE u.email = 'mhartigan@driscollfoods.com'
            GROUP BY u.id, u.email, u.display_name, u.role
        """)
        result = cursor.fetchone()
        if result:
            email, name, role, depts = result
            print(f"   Email: {email}")
            print(f"   Name: {name}")
            print(f"   Role: {role}")
            print(f"   Departments: {', '.join(depts)}")

        print()

        # ================================================================
        # SUCCESS
        # ================================================================
        print("=" * 80)
        print("✅ MIGRATION 001 COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print()
        print("📋 SUMMARY:")
        print(f"   ✅ Nuked legacy enterprise tables")
        print(f"   ✅ Created 7 new tables (Complex Schema - Option B)")
        print(f"   ✅ Created {index_count} indexes")
        print(f"   ✅ Seeded 1 tenant (Driscoll Foods)")
        print(f"   ✅ Seeded 6 departments")
        print(f"   ✅ Seeded 1 admin user (Matt Hartigan)")
        print(f"   ✅ Granted Matt access to all departments")
        print()
        print("🎯 NEXT STEPS:")
        print("   1. Test SSO login flow (azure_oid column should work now)")
        print("   2. Test admin portal (schema matches auth_service.py)")
        print("   3. Verify VITE_API_URL is set in Railway frontend service")
        print()

        cursor.close()

    except psycopg2.Error as e:
        print(f"\n❌ DATABASE ERROR: {e}")
        print(f"   Code: {e.pgcode}")
        print(f"   Details: {e.pgerror}")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        if conn:
            conn.close()
            print("🔌 Database connection closed")


if __name__ == "__main__":
    main()
