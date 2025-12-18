#!/usr/bin/env python3
"""
Database Tools for Claude Agent SDK
Provides PostgreSQL query, schema inspection, and CSV export capabilities.

Usage:
    from db_tools import DatabaseTool

    db = DatabaseTool()
    db.connect()

    # Query and display as table
    db.query("SELECT * FROM users LIMIT 10")

    # Show all tables
    db.tables()

    # Describe a table's structure
    db.describe("users")

    # Export query results to CSV
    db.to_csv("SELECT * FROM users", "users_export.csv")
"""

import os
import sys
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use system env vars

# Try to import psycopg2 (PostgreSQL adapter)
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("Warning: psycopg2 not installed. Install with: pip install psycopg2-binary")

# Try tabulate for pretty table output
try:
    from tabulate import tabulate
    TABULATE_AVAILABLE = True
except ImportError:
    TABULATE_AVAILABLE = False


class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    BLUE = '\033[94m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


class DatabaseTool:
    """PostgreSQL database tool for the Claude Agent SDK."""

    def __init__(self,
                 host: str = None,
                 port: int = None,
                 database: str = None,
                 user: str = None,
                 password: str = None,
                 sslmode: str = "require"):
        """Initialize with connection parameters or environment variables.

        Environment variables (fallbacks):
            AZURE_PG_HOST, AZURE_PG_PORT, AZURE_PG_DATABASE,
            AZURE_PG_USER, AZURE_PG_PASSWORD
        """
        self.host = host or os.getenv("AZURE_PG_HOST", "enterprisebot.postgres.database.azure.com")
        self.port = port or int(os.getenv("AZURE_PG_PORT", "5432"))
        self.database = database or os.getenv("AZURE_PG_DATABASE", "enterprise_bot")
        self.user = user or os.getenv("AZURE_PG_USER", "Mhartigan")
        self.password = password or os.getenv("AZURE_PG_PASSWORD", "Lalamoney3!")
        self.sslmode = sslmode

        self.conn = None
        self.last_results = None
        self.last_columns = None

    def connect(self) -> bool:
        """Establish database connection."""
        if not PSYCOPG2_AVAILABLE:
            print(f"{Colors.RED}Error: psycopg2 not installed. Run: pip install psycopg2-binary{Colors.RESET}")
            return False

        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                sslmode=self.sslmode,
                connect_timeout=10
            )
            print(f"{Colors.GREEN}Connected to {self.database}@{self.host}{Colors.RESET}")
            return True
        except Exception as e:
            print(f"{Colors.RED}Connection failed: {e}{Colors.RESET}")
            return False

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            print(f"{Colors.DIM}Disconnected{Colors.RESET}")

    def _ensure_connected(self) -> bool:
        """Ensure we have an active connection."""
        if self.conn is None:
            return self.connect()
        try:
            # Test connection
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except:
            # Reconnect
            return self.connect()

    def _format_table(self, rows: List[tuple], columns: List[str], max_col_width: int = 50) -> str:
        """Format results as a table string."""
        if not rows:
            return f"{Colors.DIM}(No results){Colors.RESET}"

        # Truncate long values
        def truncate(val, max_len=max_col_width):
            s = str(val) if val is not None else "NULL"
            return s[:max_len-3] + "..." if len(s) > max_len else s

        truncated_rows = [[truncate(cell) for cell in row] for row in rows]

        if TABULATE_AVAILABLE:
            return tabulate(truncated_rows, headers=columns, tablefmt="psql")
        else:
            # Simple fallback formatting
            lines = []
            # Header
            header = " | ".join(f"{col:<20}" for col in columns)
            lines.append(header)
            lines.append("-" * len(header))
            # Rows
            for row in truncated_rows:
                lines.append(" | ".join(f"{str(cell):<20}" for cell in row))
            return "\n".join(lines)

    def query(self, sql: str, params: tuple = None, limit: int = 100) -> Optional[List[Dict]]:
        """Execute a query and display results as a table.

        Args:
            sql: SQL query to execute
            params: Optional parameters for parameterized queries
            limit: Max rows to display (default 100)

        Returns:
            List of dicts with results, or None on error
        """
        if not self._ensure_connected():
            return None

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)

                # Check if it's a SELECT query
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchmany(limit)
                    total_count = cur.rowcount if cur.rowcount >= 0 else len(rows)

                    # Store for later export
                    self.last_results = rows
                    self.last_columns = columns

                    # Display table
                    print(f"\n{Colors.CYAN}Query Results ({len(rows)} of {total_count} rows):{Colors.RESET}")
                    print(self._format_table(rows, columns))

                    if len(rows) < total_count:
                        print(f"{Colors.DIM}(Showing first {limit} rows. Use to_csv() for full export){Colors.RESET}")

                    # Return as list of dicts
                    return [dict(zip(columns, row)) for row in rows]
                else:
                    # Non-SELECT (INSERT, UPDATE, DELETE)
                    self.conn.commit()
                    affected = cur.rowcount
                    print(f"{Colors.GREEN}Query executed. {affected} rows affected.{Colors.RESET}")
                    return []

        except Exception as e:
            self.conn.rollback()
            print(f"{Colors.RED}Query error: {e}{Colors.RESET}")
            return None

    def tables(self, schema: str = "public") -> List[str]:
        """List all tables in the database.

        Args:
            schema: Schema to list tables from (default: public)

        Returns:
            List of table names
        """
        if not self._ensure_connected():
            return []

        sql = """
            SELECT table_name,
                   pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) as size,
                   (SELECT count(*) FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = t.table_name) as columns
            FROM information_schema.tables t
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (schema, schema))
                rows = cur.fetchall()
                columns = ["Table Name", "Size", "Columns"]

                print(f"\n{Colors.CYAN}Tables in schema '{schema}':{Colors.RESET}")
                print(self._format_table(rows, columns))

                return [row[0] for row in rows]
        except Exception as e:
            print(f"{Colors.RED}Error listing tables: {e}{Colors.RESET}")
            return []

    def describe(self, table_name: str, schema: str = "public") -> List[Dict]:
        """Describe a table's structure (columns, types, constraints).

        Args:
            table_name: Name of the table
            schema: Schema name (default: public)

        Returns:
            List of column info dicts
        """
        if not self._ensure_connected():
            return []

        sql = """
            SELECT
                c.column_name,
                c.data_type,
                c.character_maximum_length as max_len,
                c.is_nullable,
                c.column_default,
                CASE WHEN pk.column_name IS NOT NULL THEN 'PK' ELSE '' END as key
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
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (schema, table_name, schema, table_name))
                rows = cur.fetchall()
                columns = ["Column", "Type", "Max Len", "Nullable", "Default", "Key"]

                print(f"\n{Colors.CYAN}Structure of '{schema}.{table_name}':{Colors.RESET}")
                print(self._format_table(rows, columns))

                # Also show row count
                cur.execute(f"SELECT count(*) FROM {schema}.{table_name}")
                count = cur.fetchone()[0]
                print(f"{Colors.DIM}Total rows: {count:,}{Colors.RESET}")

                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"{Colors.RED}Error describing table: {e}{Colors.RESET}")
            return []

    def indexes(self, table_name: str, schema: str = "public") -> List[Dict]:
        """Show indexes on a table.

        Args:
            table_name: Name of the table
            schema: Schema name (default: public)

        Returns:
            List of index info dicts
        """
        if not self._ensure_connected():
            return []

        sql = """
            SELECT
                i.relname as index_name,
                am.amname as index_type,
                ARRAY_AGG(a.attname ORDER BY array_position(ix.indkey, a.attnum)) as columns,
                ix.indisunique as is_unique,
                ix.indisprimary as is_primary
            FROM pg_class t
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_am am ON i.relam = am.oid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE t.relname = %s AND n.nspname = %s
            GROUP BY i.relname, am.amname, ix.indisunique, ix.indisprimary
            ORDER BY i.relname
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (table_name, schema))
                rows = cur.fetchall()
                columns = ["Index Name", "Type", "Columns", "Unique", "Primary"]

                print(f"\n{Colors.CYAN}Indexes on '{schema}.{table_name}':{Colors.RESET}")
                print(self._format_table(rows, columns))

                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"{Colors.RED}Error getting indexes: {e}{Colors.RESET}")
            return []

    def to_csv(self, sql_or_table: str, filepath: str, params: tuple = None) -> bool:
        """Export query results or table to CSV.

        Args:
            sql_or_table: SQL query or table name
            filepath: Output CSV file path
            params: Optional query parameters

        Returns:
            True on success, False on error
        """
        if not self._ensure_connected():
            return False

        # Check if it's a table name or SQL
        sql = sql_or_table if sql_or_table.strip().upper().startswith("SELECT") else f"SELECT * FROM {sql_or_table}"

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

                # Write CSV
                filepath = Path(filepath)
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(rows)

                print(f"{Colors.GREEN}Exported {len(rows)} rows to {filepath}{Colors.RESET}")
                return True

        except Exception as e:
            print(f"{Colors.RED}Export error: {e}{Colors.RESET}")
            return False

    def export_last(self, filepath: str) -> bool:
        """Export the last query results to CSV.

        Args:
            filepath: Output CSV file path

        Returns:
            True on success, False on error
        """
        if self.last_results is None or self.last_columns is None:
            print(f"{Colors.YELLOW}No previous query results to export{Colors.RESET}")
            return False

        try:
            filepath = Path(filepath)
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.last_columns)
                writer.writerows(self.last_results)

            print(f"{Colors.GREEN}Exported {len(self.last_results)} rows to {filepath}{Colors.RESET}")
            return True
        except Exception as e:
            print(f"{Colors.RED}Export error: {e}{Colors.RESET}")
            return False

    def sample(self, table_name: str, n: int = 10, schema: str = "public") -> List[Dict]:
        """Get a random sample of rows from a table.

        Args:
            table_name: Name of the table
            n: Number of rows to sample
            schema: Schema name (default: public)

        Returns:
            List of sample row dicts
        """
        sql = f"SELECT * FROM {schema}.{table_name} ORDER BY RANDOM() LIMIT %s"
        return self.query(sql, (n,))

    def count(self, table_name: str, where: str = None, schema: str = "public") -> int:
        """Count rows in a table with optional WHERE clause.

        Args:
            table_name: Name of the table
            where: Optional WHERE clause (without 'WHERE' keyword)
            schema: Schema name (default: public)

        Returns:
            Row count
        """
        if not self._ensure_connected():
            return -1

        sql = f"SELECT count(*) FROM {schema}.{table_name}"
        if where:
            sql += f" WHERE {where}"

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                count = cur.fetchone()[0]
                print(f"{Colors.CYAN}{table_name}: {count:,} rows{Colors.RESET}")
                return count
        except Exception as e:
            print(f"{Colors.RED}Count error: {e}{Colors.RESET}")
            return -1

    def schemas(self) -> List[str]:
        """List all schemas in the database."""
        if not self._ensure_connected():
            return []

        sql = """
            SELECT schema_name,
                   (SELECT count(*) FROM information_schema.tables
                    WHERE table_schema = s.schema_name) as table_count
            FROM information_schema.schemata s
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY schema_name
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                columns = ["Schema", "Tables"]

                print(f"\n{Colors.CYAN}Schemas:{Colors.RESET}")
                print(self._format_table(rows, columns))

                return [row[0] for row in rows]
        except Exception as e:
            print(f"{Colors.RED}Error listing schemas: {e}{Colors.RESET}")
            return []


# Singleton instance for easy import
_db_instance = None

def get_db() -> DatabaseTool:
    """Get or create the singleton database tool instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseTool()
    return _db_instance


# Quick functions for direct use
def db_query(sql: str, params: tuple = None, limit: int = 100):
    """Quick query function."""
    db = get_db()
    return db.query(sql, params, limit)

def db_tables(schema: str = "public"):
    """Quick tables list function."""
    db = get_db()
    return db.tables(schema)

def db_describe(table_name: str, schema: str = "public"):
    """Quick describe function."""
    db = get_db()
    return db.describe(table_name, schema)

def db_to_csv(sql_or_table: str, filepath: str):
    """Quick CSV export function."""
    db = get_db()
    return db.to_csv(sql_or_table, filepath)


if __name__ == "__main__":
    # Quick test
    print(f"{Colors.CYAN}Database Tools - Quick Test{Colors.RESET}")
    print(f"{Colors.DIM}Checking dependencies...{Colors.RESET}")

    if not PSYCOPG2_AVAILABLE:
        print(f"{Colors.RED}Missing: psycopg2-binary{Colors.RESET}")
        print("Install: pip install psycopg2-binary")
    else:
        print(f"{Colors.GREEN}psycopg2: OK{Colors.RESET}")

    if not TABULATE_AVAILABLE:
        print(f"{Colors.YELLOW}Optional: tabulate (for prettier tables){Colors.RESET}")
        print("Install: pip install tabulate")
    else:
        print(f"{Colors.GREEN}tabulate: OK{Colors.RESET}")

    # Test connection
    print(f"\n{Colors.DIM}Testing connection...{Colors.RESET}")
    db = DatabaseTool()
    if db.connect():
        db.schemas()
        db.tables()
        db.disconnect()
