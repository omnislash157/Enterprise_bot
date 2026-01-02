"""
Database Tools - SDK Native

Direct database access as first-class Claude tools.
No more shelling out to scripts - Claude calls these directly.

Tools:
    db_query: Execute SQL and get structured results
    db_tables: List tables with sizes
    db_describe: Get table schema
    db_sample: Random sample from table
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime

# SDK tool decorator
try:
    from claude_agent_sdk import tool
    SDK_AVAILABLE = True
except ImportError:
    # Fallback decorator for testing
    def tool(fn):
        fn._is_tool = True
        return fn
    SDK_AVAILABLE = False

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
# TOOLS
# =============================================================================

@tool
def db_query(query: str, limit: int = 100) -> Dict[str, Any]:
    """
    Execute a SQL query against the database.
    
    Args:
        query: SQL query to execute (SELECT, INSERT, UPDATE, DELETE)
        limit: Maximum rows to return for SELECT queries (default 100)
        
    Returns:
        Dict with 'columns', 'rows', 'row_count', and 'execution_time_ms'
        
    Examples:
        db_query("SELECT * FROM enterprise.users LIMIT 5")
        db_query("SELECT count(*) FROM enterprise.query_log WHERE created_at > now() - interval '1 day'")
    """
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
            # Convert to plain dicts (RealDictRow isn't JSON serializable)
            rows = [dict(row) for row in rows]
            
            # Convert datetime objects to strings
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, datetime):
                        row[k] = v.isoformat()
            
            result = {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "total_available": cur.rowcount if cur.rowcount >= 0 else len(rows),
            }
        else:
            # INSERT/UPDATE/DELETE
            conn.commit()
            result = {
                "affected_rows": cur.rowcount,
                "message": f"Query executed successfully. {cur.rowcount} rows affected."
            }
        
        cur.close()
        conn.close()
        
        elapsed = (datetime.now() - start).total_seconds() * 1000
        result["execution_time_ms"] = round(elapsed, 2)
        
        return result
        
    except Exception as e:
        return {
            "error": str(e),
            "query": query,
        }


@tool
def db_tables(schema: str = "enterprise") -> Dict[str, Any]:
    """
    List all tables in a database schema with row counts and sizes.
    
    Args:
        schema: Schema name (default: enterprise)
        
    Returns:
        Dict with 'tables' list containing name, row_count, size
    """
    query = """
        SELECT 
            t.table_name,
            pg_size_pretty(pg_total_relation_size(quote_ident(t.table_name))) as size,
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
        
        # Get row counts (separate query for each - faster than COUNT(*) on large tables)
        for table in tables:
            try:
                cur.execute(f"SELECT reltuples::bigint FROM pg_class WHERE relname = %s", (table["table_name"],))
                row = cur.fetchone()
                table["estimated_rows"] = row["reltuples"] if row else 0
            except:
                table["estimated_rows"] = "unknown"
        
        cur.close()
        conn.close()
        
        return {
            "schema": schema,
            "table_count": len(tables),
            "tables": tables,
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def db_describe(table: str, schema: str = "enterprise") -> Dict[str, Any]:
    """
    Describe a table's structure (columns, types, constraints).
    
    Args:
        table: Table name
        schema: Schema name (default: enterprise)
        
    Returns:
        Dict with 'columns' list and 'indexes' list
    """
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
        
        return {
            "schema": schema,
            "table": table,
            "row_count": row_count,
            "column_count": len(columns),
            "columns": columns,
            "indexes": indexes,
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def db_sample(table: str, n: int = 5, schema: str = "enterprise") -> Dict[str, Any]:
    """
    Get a random sample of rows from a table.
    
    Args:
        table: Table name
        n: Number of rows to sample (default: 5)
        schema: Schema name (default: enterprise)
        
    Returns:
        Dict with 'columns' and 'rows'
    """
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
        
        return {
            "table": f"{schema}.{table}",
            "sample_size": len(rows),
            "columns": columns,
            "rows": rows,
        }
        
    except Exception as e:
        return {"error": str(e)}


# Export tools list for aggregation
TOOLS = [db_query, db_tables, db_describe, db_sample]