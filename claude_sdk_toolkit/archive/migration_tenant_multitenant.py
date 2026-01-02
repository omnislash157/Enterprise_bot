"""
Multi-Tenant Domain Routing Migration
Extends tenants table with Azure AD fields and creates Driscoll tenant
"""
import asyncio
import asyncpg
import os
from datetime import datetime

# Database connection details
DB_CONFIG = {
    'user': 'mhartigan',
    'password': 'Lalamoney3!',
    'host': 'cogtwin.postgres.database.azure.com',
    'port': 5432,
    'database': 'postgres',
    'ssl': 'require'
}

async def run_migration():
    print(f"[{datetime.now()}] Connecting to database...")
    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Check if tenants table exists
        print("\n[1/6] Checking if tenants table exists...")
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'enterprise' AND table_name = 'tenants'
            );
        """)

        if not table_exists:
            print("   ❌ Tenants table does not exist. Creating it first...")
            await conn.execute("""
                CREATE TABLE enterprise.tenants (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    slug VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    domain VARCHAR(255) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
            print("   ✅ Tenants table created")
        else:
            print("   ✅ Tenants table exists")

        # Check current schema
        print("\n[2/6] Checking current schema...")
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'enterprise' AND table_name = 'tenants'
            ORDER BY ordinal_position;
        """)

        print("   Current columns:")
        for col in columns:
            print(f"      - {col['column_name']}: {col['data_type']}")

        # Add new columns if they don't exist
        print("\n[3/6] Adding Azure AD and branding columns...")

        columns_to_add = [
            ('azure_tenant_id', 'VARCHAR(100)'),
            ('azure_client_id', 'VARCHAR(100)'),
            ('azure_client_secret_ref', 'VARCHAR(255)'),
            ('branding', "JSONB DEFAULT '{}'::jsonb"),
            ('is_active', 'BOOLEAN DEFAULT true')
        ]

        for col_name, col_type in columns_to_add:
            col_exists = await conn.fetchval(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_schema = 'enterprise'
                    AND table_name = 'tenants'
                    AND column_name = '{col_name}'
                );
            """)

            if not col_exists:
                await conn.execute(f"""
                    ALTER TABLE enterprise.tenants
                    ADD COLUMN {col_name} {col_type};
                """)
                print(f"   ✅ Added column: {col_name}")
            else:
                print(f"   ⏭️  Column already exists: {col_name}")

        # Create unique index on domain
        print("\n[4/6] Creating unique index on domain...")
        index_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE schemaname = 'enterprise'
                AND tablename = 'tenants'
                AND indexname = 'idx_tenants_domain'
            );
        """)

        if not index_exists:
            await conn.execute("""
                CREATE UNIQUE INDEX idx_tenants_domain
                ON enterprise.tenants(domain);
            """)
            print("   ✅ Index created")
        else:
            print("   ⏭️  Index already exists")

        # Check for existing Driscoll tenant
        print("\n[5/6] Checking for Driscoll tenant...")
        driscoll_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM enterprise.tenants
                WHERE slug = 'driscoll'
            );
        """)

        if not driscoll_exists:
            # Get Azure credentials from environment (if available)
            azure_tenant_id = os.getenv('AZURE_AD_TENANT_ID', '67de5fcd-a0e9-447d-9f28-e613d82a68eb')
            azure_client_id = os.getenv('AZURE_AD_CLIENT_ID', '6bd5e110-a031-46e3-b62a-cb3b75f3cb32')

            await conn.execute("""
                INSERT INTO enterprise.tenants
                (slug, name, domain, azure_tenant_id, azure_client_id, is_active)
                VALUES ($1, $2, $3, $4, $5, $6);
            """, 'driscoll', 'Driscoll Foods', 'driscollintel.com',
                azure_tenant_id, azure_client_id, True)
            print("   ✅ Driscoll tenant created")
        else:
            print("   ⏭️  Driscoll tenant already exists")

            # Update it with Azure credentials if not set
            driscoll = await conn.fetchrow("""
                SELECT azure_tenant_id, azure_client_id
                FROM enterprise.tenants
                WHERE slug = 'driscoll';
            """)

            if not driscoll['azure_tenant_id']:
                azure_tenant_id = os.getenv('AZURE_AD_TENANT_ID', '67de5fcd-a0e9-447d-9f28-e613d82a68eb')
                azure_client_id = os.getenv('AZURE_AD_CLIENT_ID', '6bd5e110-a031-46e3-b62a-cb3b75f3cb32')

                await conn.execute("""
                    UPDATE enterprise.tenants
                    SET azure_tenant_id = $1, azure_client_id = $2
                    WHERE slug = 'driscoll';
                """, azure_tenant_id, azure_client_id)
                print("   ✅ Updated Driscoll tenant with Azure credentials")

        # Link existing users to Driscoll tenant
        print("\n[6/6] Linking existing users to Driscoll tenant...")

        # Check if tenant_id column exists in users table
        tenant_col_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'enterprise'
                AND table_name = 'users'
                AND column_name = 'tenant_id'
            );
        """)

        if tenant_col_exists:
            unlinked_users = await conn.fetchval("""
                SELECT COUNT(*)
                FROM enterprise.users
                WHERE tenant_id IS NULL;
            """)

            if unlinked_users > 0:
                await conn.execute("""
                    UPDATE enterprise.users
                    SET tenant_id = (SELECT id FROM enterprise.tenants WHERE slug = 'driscoll')
                    WHERE tenant_id IS NULL;
                """)
                print(f"   ✅ Linked {unlinked_users} users to Driscoll tenant")
            else:
                print("   ⏭️  All users already linked to tenants")
        else:
            print("   ⚠️  tenant_id column not found in users table - skipping user linking")

        # Display final schema
        print("\n" + "="*60)
        print("MIGRATION COMPLETE")
        print("="*60)

        print("\nFinal tenants table structure:")
        final_columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'enterprise' AND table_name = 'tenants'
            ORDER BY ordinal_position;
        """)

        for col in final_columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"   {col['column_name']}: {col['data_type']} ({nullable})")

        # Display tenants
        print("\nCurrent tenants:")
        tenants = await conn.fetch("""
            SELECT slug, name, domain, azure_tenant_id, is_active
            FROM enterprise.tenants
            ORDER BY created_at;
        """)

        for tenant in tenants:
            status = "✅ ACTIVE" if tenant['is_active'] else "❌ INACTIVE"
            has_azure = "🔐 SSO" if tenant['azure_tenant_id'] else "🔓 No SSO"
            print(f"   {tenant['slug']}: {tenant['name']} ({tenant['domain']}) - {status} {has_azure}")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()
        print(f"\n[{datetime.now()}] Database connection closed")

if __name__ == "__main__":
    asyncio.run(run_migration())
