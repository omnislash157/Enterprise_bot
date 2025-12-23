"""Run migration 004_audit_log.sql"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

connection_string = os.getenv('AZURE_PG_CONNECTION_STRING')

# Read migration file
with open('db/migrations/004_audit_log.sql', 'r') as f:
    migration_sql = f.read()

# Connect and run migration
try:
    conn = psycopg2.connect(connection_string)
    cur = conn.cursor()

    print("Running migration 004_audit_log.sql...")
    cur.execute(migration_sql)
    conn.commit()

    print("✅ Migration completed successfully!")

    # Verify table exists
    cur.execute("SELECT COUNT(*) FROM enterprise.audit_log;")
    count = cur.fetchone()[0]
    print(f"✅ Table enterprise.audit_log exists (current rows: {count})")

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ Migration failed: {e}")
    raise
