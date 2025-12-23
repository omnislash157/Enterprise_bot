"""
Database Tools - SDK Compatible Wrappers

Direct PostgreSQL database access as SDK-native tools.

Tools:
    db_query: Execute SQL and get structured results
    db_tables: List tables with sizes
    db_describe: Get table schema
    db_sample: Random sample from table
"""

import os
from typing import Dict, Any
from datetime import datetime
from claude_agent_sdk import tool

# Database driver
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


# =============================================================================
# CONNECTION
# =============================================================================

def get_connection():
    """Get database connection from env vars."""
    if not DB_AVAILABLE:
        raise RuntimeError("psycopg2 not installed: pip install psycopg2-binary")

    return psycopg2.connect(
        host=os.getenv("AZURE_PG_HOST", "localhost"),
        port=int(os.getenv("AZURE_PG_PORT", "5432")),
        database=os.getenv("AZURE_PG_DATABASE", "postgres"),
        user=os.getenv("AZURE_PG_USER", "postgres"),
        password=os.getenv("AZURE_PG_PASSWORD", ""),
        sslmode=os.getenv("AZURE_PG_SSLMODE", "require"),
        connect_timeout=10,
    )


# =============================================================================
# SDK TOOLS
# =============================================================================

@tool(
    name="db_query",
    description="Execute a SQL query against the PostgreSQL database - supports SELECT, INSERT, UPDATE, DELETE",
    input_schema={"query": str, "limit": int}
)
async def db_query(args: dict) -> Dict[str, Any]:
    """Execute a SQL query against the database."""
    query = args.get("query", "")
    limit = args.get("limit", 100)

    if not query:
        return {
            "content": [{"type": "text", "text": "Error: query parameter is required"}],
            "isError": True
        }

    if not DB_AVAILABLE:
        return {
            "content": [{"type": "text", "text": "Error: psycopg2 not installed. Run: pip install psycopg2-binary"}],
            "isError": True
        }

    start = datetime.now()

    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Add LIMIT if not present and it's a SELECT
        query_upper = query.strip().upper()
        if query_upper.startswith("SELECT") and "LIMIT" not in query_upper:
            query = f"{query.rstrip(';')} LIMIT {limit}"

        cur.execute(query)

        if cur.description:
            # SELECT query
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            rows = [dict(row) for row in rows]

            # Convert datetime objects to strings
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, datetime):
                        row[k] = v.isoformat()

            elapsed = (datetime.now() - start).total_seconds() * 1000

            result_text = f"📊 Query Results\n"
            result_text += f"Execution time: {elapsed:.2f}ms\n"
            result_text += f"Rows returned: {len(rows)}\n"
            result_text += f"Columns: {', '.join(columns)}\n\n"

            if rows:
                # Show first few rows
                for i, row in enumerate(rows[:5], 1):
                    result_text += f"Row {i}:\n"
                    for col in columns:
                        value = str(row[col])[:100]  # Truncate long values
                        result_text += f"  {col}: {value}\n"
                    result_text += "\n"

                if len(rows) > 5:
                    result_text += f"... and {len(rows) - 5} more rows\n"
            else:
                result_text += "No rows returned.\n"

            cur.close()
            conn.close()

            return {
                "content": [{"type": "text", "text": result_text}]
            }
        else:
            # INSERT/UPDATE/DELETE
            conn.commit()
            affected = cur.rowcount
            elapsed = (datetime.now() - start).total_seconds() * 1000

            cur.close()
            conn.close()

            result_text = f"✅ Query executed successfully\n"
            result_text += f"Execution time: {elapsed:.2f}ms\n"
            result_text += f"Rows affected: {affected}\n"

            return {
                "content": [{"type": "text", "text": result_text}]
            }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Database error: {str(e)}\n\nQuery:\n{query}"}],
            "isError": True
        }


@tool(
    name="db_tables",
    description="List all tables in a database schema with row counts and sizes",
    input_schema={"schema": str}
)
async def db_tables(args: dict) -> Dict[str, Any]:
    """List all tables in a database schema."""
    schema = args.get("schema", "enterprise")

    if not DB_AVAILABLE:
        return {
            "content": [{"type": "text", "text": "Error: psycopg2 not installed"}],
            "isError": True
        }

    query = """
        SELECT
            t.table_name,
            pg_size_pretty(pg_total_relation_size(quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))) as size,
            (SELECT count(*) FROM information_schema.columns c
             WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) as column_count
        FROM information_schema.tables t
        WHERE t.table_schema = %s AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name
    """

    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, (schema,))
        tables = [dict(row) for row in cur.fetchall()]

        # Get row counts
        for table in tables:
            try:
                cur.execute(f"SELECT reltuples::bigint FROM pg_class WHERE relname = %s", (table["table_name"],))
                row = cur.fetchone()
                table["estimated_rows"] = row["reltuples"] if row else 0
            except:
                table["estimated_rows"] = "unknown"

        cur.close()
        conn.close()

        result_text = f"📋 Tables in schema '{schema}'\n"
        result_text += f"Total tables: {len(tables)}\n\n"

        for i, t in enumerate(tables, 1):
            result_text += f"{i}. {t['table_name']}\n"
            result_text += f"   Rows: ~{t['estimated_rows']:,} | Columns: {t['column_count']} | Size: {t['size']}\n"

        return {
            "content": [{"type": "text", "text": result_text}]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error listing tables: {str(e)}"}],
            "isError": True
        }


@tool(
    name="db_describe",
    description="Describe a table's structure - shows columns, types, constraints, and indexes",
    input_schema={"table": str, "schema": str}
)
async def db_describe(args: dict) -> Dict[str, Any]:
    """Describe a table's structure."""
    table = args.get("table", "")
    schema = args.get("schema", "enterprise")

    if not table:
        return {
            "content": [{"type": "text", "text": "Error: table parameter is required"}],
            "isError": True
        }

    if not DB_AVAILABLE:
        return {
            "content": [{"type": "text", "text": "Error: psycopg2 not installed"}],
            "isError": True
        }

    columns_query = """
        SELECT
            c.column_name,
            c.data_type,
            c.character_maximum_length as max_length,
            c.is_nullable,
            c.column_default,
            CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT ku.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku ON tc.constraint_name = ku.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s AND tc.table_name = %s
        ) pk ON c.column_name = pk.column_name
        WHERE c.table_schema = %s AND c.table_name = %s
        ORDER BY c.ordinal_position
    """

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
        WHERE t.relname = %s AND n.nspname = %s
    """

    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get columns
        cur.execute(columns_query, (schema, table, schema, table))
        columns = [dict(row) for row in cur.fetchall()]

        # Get indexes
        cur.execute(indexes_query, (table, schema))
        indexes = [dict(row) for row in cur.fetchall()]

        # Get row count
        cur.execute(f"SELECT count(*) as count FROM {schema}.{table}")
        row_count = cur.fetchone()["count"]

        cur.close()
        conn.close()

        result_text = f"🗂️ Table: {schema}.{table}\n"
        result_text += f"Rows: {row_count:,}\n"
        result_text += f"Columns: {len(columns)}\n\n"

        result_text += "COLUMNS:\n"
        for col in columns:
            pk_marker = " 🔑" if col["is_primary_key"] else ""
            nullable = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"
            result_text += f"  • {col['column_name']}{pk_marker}\n"
            result_text += f"    Type: {col['data_type']}"
            if col['max_length']:
                result_text += f"({col['max_length']})"
            result_text += f" | {nullable}\n"
            if col['column_default']:
                result_text += f"    Default: {col['column_default']}\n"

        if indexes:
            result_text += "\nINDEXES:\n"
            for idx in indexes:
                idx_type = "PRIMARY KEY" if idx["is_primary"] else ("UNIQUE" if idx["is_unique"] else "INDEX")
                result_text += f"  • {idx['index_name']} ({idx_type}, {idx['index_type']})\n"

        return {
            "content": [{"type": "text", "text": result_text}]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error describing table: {str(e)}"}],
            "isError": True
        }


@tool(
    name="db_sample",
    description="Get a random sample of rows from a table - useful for exploring data",
    input_schema={"table": str, "n": int, "schema": str}
)
async def db_sample(args: dict) -> Dict[str, Any]:
    """Get a random sample of rows from a table."""
    table = args.get("table", "")
    n = args.get("n", 5)
    schema = args.get("schema", "enterprise")

    if not table:
        return {
            "content": [{"type": "text", "text": "Error: table parameter is required"}],
            "isError": True
        }

    if not DB_AVAILABLE:
        return {
            "content": [{"type": "text", "text": "Error: psycopg2 not installed"}],
            "isError": True
        }

    query = f"SELECT * FROM {schema}.{table} ORDER BY RANDOM() LIMIT %s"

    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, (n,))

        columns = [desc[0] for desc in cur.description]
        rows = [dict(row) for row in cur.fetchall()]

        # Convert datetime objects
        for row in rows:
            for k, v in row.items():
                if isinstance(v, datetime):
                    row[k] = v.isoformat()

        cur.close()
        conn.close()

        result_text = f"🎲 Random Sample from {schema}.{table}\n"
        result_text += f"Sample size: {len(rows)}\n"
        result_text += f"Columns: {', '.join(columns)}\n\n"

        for i, row in enumerate(rows, 1):
            result_text += f"Row {i}:\n"
            for col in columns:
                value = str(row[col])[:100]
                result_text += f"  {col}: {value}\n"
            result_text += "\n"

        return {
            "content": [{"type": "text", "text": result_text}]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error sampling table: {str(e)}"}],
            "isError": True
        }


# Export tools list
TOOLS = [db_query, db_tables, db_describe, db_sample]
