import psycopg2

conn = psycopg2.connect(
    user="Mhartigan",
    password="Lalamoney3!",
    host="enterprisebot.postgres.database.azure.com",
    port=5432,
    database="postgres",
    sslmode="require"
)

cur = conn.cursor()

# Create schemas
cur.execute("CREATE SCHEMA IF NOT EXISTS enterprise;")
cur.execute("CREATE SCHEMA IF NOT EXISTS cogtwin;")

# Verify
cur.execute("SELECT schema_name FROM information_schema.schemata;")
print(cur.fetchall())

conn.commit()
cur.close()
conn.close()

print("Done!")