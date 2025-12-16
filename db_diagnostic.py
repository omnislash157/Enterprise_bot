"""
Database Diagnostic - Check Current State of Azure PostgreSQL

Run this BEFORE the auth sprint to see exactly what exists.

Usage:
    python db_diagnostic.py
"""

import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "user": "Mhartigan",
    "password": "Lalamoney3!",
    "host": "enterprisebot.postgres.database.azure.com",
    "port": 5432,
    "database": "postgres",
    "sslmode": "require"
}

def run_diagnostic():
    print("=" * 70)
    print("DATABASE DIAGNOSTIC - Azure PostgreSQL")
    print("=" * 70)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. List all schemas
    print("\n[1] SCHEMAS")
    print("-" * 40)
    cur.execute("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
        ORDER BY schema_name
    """)
    schemas = cur.fetchall()
    for s in schemas:
        print(f"  - {s['schema_name']}")
    
    # 2. List all tables in enterprise schema
    print("\n[2] TABLES IN 'enterprise' SCHEMA")
    print("-" * 40)
    cur.execute("""
        SELECT table_name, 
               (SELECT COUNT(*) FROM information_schema.columns c 
                WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) as column_count
        FROM information_schema.tables t
        WHERE table_schema = 'enterprise'
        ORDER BY table_name
    """)
    tables = cur.fetchall()
    
    if not tables:
        print("  (no tables found)")
    else:
        for t in tables:
            # Get row count
            try:
                cur.execute(f"SELECT COUNT(*) as cnt FROM enterprise.{t['table_name']}")
                row_count = cur.fetchone()['cnt']
            except:
                row_count = "?"
            print(f"  - {t['table_name']:<30} ({t['column_count']} cols, {row_count} rows)")
    
    # 3. Check specific tables we expect
    print("\n[3] EXPECTED TABLES STATUS")
    print("-" * 40)
    
    expected_tables = [
        ("tenants", "tenant_service.py --init"),
        ("departments", "upload_manuals.py --init-db"),
        ("department_content", "upload_manuals.py --init-db"),
        ("users", "auth_schema.py --init (NEW)"),
        ("user_department_access", "auth_schema.py --init (NEW)"),
        ("access_audit_log", "auth_schema.py --init (NEW)"),
    ]
    
    existing_table_names = [t['table_name'] for t in tables]
    
    for table_name, source in expected_tables:
        if table_name in existing_table_names:
            status = "EXISTS"
        else:
            status = "MISSING"
        print(f"  [{status:<7}] {table_name:<25} <- {source}")
    
    # 4. Show tenants data if exists
    if "tenants" in existing_table_names:
        print("\n[4] TENANTS DATA")
        print("-" * 40)
        cur.execute("SELECT id, slug, name, data_source_type, active FROM enterprise.tenants")
        tenants = cur.fetchall()
        for t in tenants:
            status = "active" if t['active'] else "inactive"
            print(f"  - {t['slug']}: {t['name']} ({t['data_source_type']}, {status})")
            print(f"    ID: {t['id']}")
    
    # 5. Show departments data if exists
    if "departments" in existing_table_names:
        print("\n[5] DEPARTMENTS DATA")
        print("-" * 40)
        cur.execute("SELECT id, slug, name, active FROM enterprise.departments ORDER BY name")
        depts = cur.fetchall()
        for d in depts:
            status = "active" if d['active'] else "inactive"
            print(f"  - {d['slug']:<20} {d['name']} ({status})")
    
    # 6. Show department_content summary if exists
    if "department_content" in existing_table_names:
        print("\n[6] DEPARTMENT CONTENT SUMMARY")
        print("-" * 40)
        cur.execute("""
            SELECT d.name as dept_name, COUNT(dc.id) as doc_count, 
                   SUM(LENGTH(dc.content)) as total_chars
            FROM enterprise.departments d
            LEFT JOIN enterprise.department_content dc ON d.id = dc.department_id AND dc.active = TRUE
            WHERE d.active = TRUE
            GROUP BY d.id, d.name
            ORDER BY d.name
        """)
        content_stats = cur.fetchall()
        for c in content_stats:
            chars = c['total_chars'] or 0
            print(f"  - {c['dept_name']:<20} {c['doc_count']} docs ({chars:,} chars)")
    
    # 7. Show users data if exists
    if "users" in existing_table_names:
        print("\n[7] USERS DATA")
        print("-" * 40)
        cur.execute("""
            SELECT u.email, u.role, u.display_name, d.slug as primary_dept
            FROM enterprise.users u
            LEFT JOIN enterprise.departments d ON u.primary_department_id = d.id
            ORDER BY u.role DESC, u.email
        """)
        users = cur.fetchall()
        if users:
            for u in users:
                dept = u['primary_dept'] or '-'
                print(f"  - {u['email']:<40} {u['role']:<12} {dept}")
        else:
            print("  (no users yet)")
    
    # 8. Check indexes
    print("\n[8] INDEXES IN 'enterprise' SCHEMA")
    print("-" * 40)
    cur.execute("""
        SELECT indexname, tablename
        FROM pg_indexes
        WHERE schemaname = 'enterprise'
        ORDER BY tablename, indexname
    """)
    indexes = cur.fetchall()
    if indexes:
        current_table = None
        for idx in indexes:
            if idx['tablename'] != current_table:
                current_table = idx['tablename']
                print(f"  {current_table}:")
            print(f"    - {idx['indexname']}")
    else:
        print("  (no custom indexes)")
    
    cur.close()
    conn.close()
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    missing = [t for t, _ in expected_tables if t not in existing_table_names]
    if missing:
        print(f"\nMISSING TABLES: {', '.join(missing)}")
        print("\nTo create missing tables:")
        if "users" in missing:
            print("  python auth_schema.py --init --seed")
    else:
        print("\nAll expected tables exist!")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_diagnostic()