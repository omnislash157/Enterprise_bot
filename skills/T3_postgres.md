# T3: PostgreSQL - Database Operations

## Overview
Direct Azure PostgreSQL access using psycopg2 for queries, schema operations, and data exploration.

---

## 🔌 Connection

```python
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    """Get PostgreSQL connection from environment variables."""
    return psycopg2.connect(
        host=os.getenv("AZURE_PG_HOST"),
        port=int(os.getenv("AZURE_PG_PORT", "5432")),
        database=os.getenv("AZURE_PG_DATABASE", "postgres"),
        user=os.getenv("AZURE_PG_USER"),
        password=os.getenv("AZURE_PG_PASSWORD"),
        sslmode=os.getenv("AZURE_PG_SSLMODE", "require"),
        connect_timeout=10
    )
```

---

## 📝 Execute Query

```python
def execute_query(sql: str, params: tuple = None, limit: int = 100):
    """Execute SQL query and return results."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Add LIMIT if SELECT without one
        if sql.strip().upper().startswith("SELECT") and "LIMIT" not in sql.upper():
            sql = f"{sql.rstrip(';')} LIMIT {limit}"

        cur.execute(sql, params)

        if cur.description:
            # SELECT query - return rows
            columns = [desc[0] for desc in cur.description]
            rows = [dict(row) for row in cur.fetchall()]

            # Convert datetime to string
            from datetime import datetime
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, datetime):
                        row[k] = v.isoformat()

            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows)
            }
        else:
            # INSERT/UPDATE/DELETE - commit and return count
            conn.commit()
            return {
                "affected_rows": cur.rowcount,
                "message": f"{cur.rowcount} rows affected"
            }

    finally:
        cur.close()
        conn.close()
```

---

## 📋 List Tables

```python
def list_tables(schema: str = "enterprise"):
    """List all tables in schema with metadata."""
    query = """
        SELECT
            t.table_name,
            pg_size_pretty(pg_total_relation_size(
                quote_ident(t.table_schema) || '.' || quote_ident(t.table_name)
            )) as size,
            (SELECT count(*)
             FROM information_schema.columns c
             WHERE c.table_schema = t.table_schema
               AND c.table_name = t.table_name) as column_count
        FROM information_schema.tables t
        WHERE t.table_schema = %s
          AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name
    """

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(query, (schema,))
    tables = [dict(row) for row in cur.fetchall()]

    # Get estimated row counts
    for table in tables:
        cur.execute(
            "SELECT reltuples::bigint FROM pg_class WHERE relname = %s",
            (table["table_name"],)
        )
        row = cur.fetchone()
        table["estimated_rows"] = row["reltuples"] if row else 0

    cur.close()
    conn.close()

    return tables
```

---

## 🔍 Describe Table

```python
def describe_table(table: str, schema: str = "enterprise"):
    """Get table schema with columns, types, constraints, indexes."""
    # Columns query
    columns_query = """
        SELECT
            c.column_name,
            c.data_type,
            c.character_maximum_length as max_length,
            c.is_nullable,
            c.column_default,
            CASE WHEN pk.column_name IS NOT NULL
                 THEN true ELSE false END as is_primary_key
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT ku.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
              ON tc.constraint_name = ku.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
        ) pk ON c.column_name = pk.column_name
        WHERE c.table_schema = %s
          AND c.table_name = %s
        ORDER BY c.ordinal_position
    """

    # Indexes query
    indexes_query = """
        SELECT
            i.relname as index_name,
            am.amname as index_type,
            ix.indisunique as is_unique,
            ix.indisprimary as is_primary
        FROM pg_class t
        JOIN pg_index ix ON t.oid = ix.indrelid
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_am am ON i.relam = am.oid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE t.relname = %s
          AND n.nspname = %s
    """

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(columns_query, (schema, table, schema, table))
    columns = [dict(row) for row in cur.fetchall()]

    cur.execute(indexes_query, (table, schema))
    indexes = [dict(row) for row in cur.fetchall()]

    cur.execute(f"SELECT count(*) as count FROM {schema}.{table}")
    row_count = cur.fetchone()["count"]

    cur.close()
    conn.close()

    return {
        "table": f"{schema}.{table}",
        "row_count": row_count,
        "columns": columns,
        "indexes": indexes
    }
```

---

## 🎲 Random Sample

```python
def sample_table(table: str, n: int = 5, schema: str = "enterprise"):
    """Get random sample of rows from table."""
    query = f"SELECT * FROM {schema}.{table} ORDER BY RANDOM() LIMIT %s"

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(query, (n,))

    columns = [desc[0] for desc in cur.description]
    rows = [dict(row) for row in cur.fetchall()]

    # Convert datetime
    from datetime import datetime
    for row in rows:
        for k, v in row.items():
            if isinstance(v, datetime):
                row[k] = v.isoformat()

    cur.close()
    conn.close()

    return {
        "table": f"{schema}.{table}",
        "sample_size": len(rows),
        "columns": columns,
        "rows": rows
    }
```

---

## 🔒 Safe Query Patterns

### Using Parameters (Prevents SQL Injection)
```python
# ✅ GOOD - parameterized query
cur.execute(
    "SELECT * FROM users WHERE email = %s",
    (user_email,)
)

# ❌ BAD - string interpolation
cur.execute(f"SELECT * FROM users WHERE email = '{user_email}'")
```

### Schema/Table Names (Can't be parameterized)
```python
# ✅ GOOD - whitelist validation
ALLOWED_SCHEMAS = ["enterprise", "memory", "public"]
if schema not in ALLOWED_SCHEMAS:
    raise ValueError(f"Invalid schema: {schema}")

# ✅ GOOD - identifier quoting
from psycopg2 import sql
query = sql.SQL("SELECT * FROM {}.{}").format(
    sql.Identifier(schema),
    sql.Identifier(table)
)
```

---

## 📊 Common Query Patterns

### Pagination
```python
def paginate(table, page=1, per_page=20, order_by="id"):
    offset = (page - 1) * per_page
    query = f"""
        SELECT * FROM {table}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
    """
    cur.execute(query, (per_page, offset))
    return cur.fetchall()
```

### Full-Text Search
```python
def search_documents(term: str, limit: int = 20):
    query = """
        SELECT
            id, content,
            ts_rank(
                to_tsvector('english', content),
                plainto_tsquery('english', %s)
            ) as rank
        FROM documents
        WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
        ORDER BY rank DESC
        LIMIT %s
    """
    cur.execute(query, (term, term, limit))
    return cur.fetchall()
```

### Aggregations
```python
# Count by group
SELECT department, COUNT(*) as user_count
FROM users
GROUP BY department
ORDER BY user_count DESC

# Stats
SELECT
    COUNT(*) as total,
    AVG(score) as avg_score,
    MAX(created_at) as latest
FROM query_log
WHERE created_at > NOW() - INTERVAL '24 hours'
```

---

## 🎯 SDK Tool Example

```python
from claude_agent_sdk import tool

@tool(
    name="db_query",
    description="Execute a SQL query against the PostgreSQL database",
    input_schema={"query": str, "limit": int}
)
async def db_query(args: dict):
    query = args.get("query", "")
    limit = args.get("limit", 100)

    if not query:
        return {
            "content": [{"type": "text", "text": "Error: query parameter required"}],
            "isError": True
        }

    try:
        result = execute_query(query, limit=limit)

        if "rows" in result:
            # SELECT query
            text = f"📊 Query Results\n"
            text += f"Rows: {result['row_count']}\n"
            text += f"Columns: {', '.join(result['columns'])}\n\n"

            for i, row in enumerate(result['rows'][:5], 1):
                text += f"Row {i}:\n"
                for col in result['columns']:
                    text += f"  {col}: {row[col]}\n"

            if result['row_count'] > 5:
                text += f"\n... and {result['row_count'] - 5} more rows\n"

        else:
            # INSERT/UPDATE/DELETE
            text = f"✅ {result['message']}"

        return {
            "content": [{"type": "text", "text": text}]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Database error: {str(e)}"}],
            "isError": True
        }
```

---

## 🚨 Error Handling

```python
try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query)
    conn.commit()

except psycopg2.OperationalError as e:
    # Connection failed
    return {"error": f"Connection failed: {e}"}

except psycopg2.ProgrammingError as e:
    # SQL syntax error
    return {"error": f"SQL error: {e}"}

except psycopg2.IntegrityError as e:
    # Constraint violation (FK, unique, etc.)
    return {"error": f"Constraint violation: {e}"}

finally:
    if cur:
        cur.close()
    if conn:
        conn.close()
```

---

## 🔧 Environment Setup

```bash
# .env file
AZURE_PG_HOST=cogtwin.postgres.database.azure.com
AZURE_PG_PORT=5432
AZURE_PG_DATABASE=postgres
AZURE_PG_USER=mhartigan
AZURE_PG_PASSWORD=your_password
AZURE_PG_SSLMODE=require
```

---

## 📖 Useful Queries

### Show all schemas
```sql
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
ORDER BY schema_name;
```

### Show table sizes
```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'enterprise'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Active connections
```sql
SELECT
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query
FROM pg_stat_activity
WHERE state = 'active';
```

---

*psycopg2 is the standard PostgreSQL adapter for Python. RealDictCursor returns dict rows.*
