# Skill: Database Tools (db)

## Overview
PostgreSQL database interaction via `db_tools.py`. Query, inspect schema, export data.

## Connection
```python
from db_tools import DatabaseTool, get_db

# Auto-connects using env vars
db = get_db()
db.connect()  # Uses AZURE_PG_* env vars
```

Environment variables:
- `AZURE_PG_HOST` - Database host
- `AZURE_PG_PORT` - Port (default 5432)
- `AZURE_PG_DATABASE` - Database name
- `AZURE_PG_USER` - Username
- `AZURE_PG_PASSWORD` - Password

## CLI Commands

### Connection
```
/db              Connect to database
/db disconnect   Close connection
```

### Schema Inspection
```
/db schemas              List all schemas
/db tables               List tables with size/column count
/db describe <table>     Show columns, types, constraints, row count
/db indexes <table>      Show indexes on table
```

### Querying
```
/db query <sql>          Run SQL, display as table (limit 100 rows)
/db sample <table> [n]   Get n random rows (default 10)
/db count <table>        Count rows in table
```

### Export
```
/db csv <table> <file>   Export table to CSV
/db csv "SELECT..." <f>  Export query results to CSV
```

## Python API

### DatabaseTool Class

```python
db = DatabaseTool(
    host="...",      # or AZURE_PG_HOST
    port=5432,       # or AZURE_PG_PORT
    database="...",  # or AZURE_PG_DATABASE
    user="...",      # or AZURE_PG_USER
    password="...",  # or AZURE_PG_PASSWORD
    sslmode="require"
)
```

### Methods

| Method | Args | Returns | Description |
|--------|------|---------|-------------|
| `connect()` | - | bool | Establish connection |
| `disconnect()` | - | - | Close connection |
| `query(sql, params, limit)` | sql:str, params:tuple, limit:int=100 | List[Dict] | Run query, display table |
| `tables(schema)` | schema:str="public" | List[str] | List tables |
| `describe(table, schema)` | table:str, schema:str="public" | List[Dict] | Show table structure |
| `indexes(table, schema)` | table:str, schema:str="public" | List[Dict] | Show indexes |
| `schemas()` | - | List[str] | List schemas |
| `sample(table, n, schema)` | table:str, n:int=10, schema:str="public" | List[Dict] | Random sample |
| `count(table, where, schema)` | table:str, where:str=None, schema:str="public" | int | Count rows |
| `to_csv(sql_or_table, filepath)` | sql_or_table:str, filepath:str | bool | Export to CSV |
| `export_last(filepath)` | filepath:str | bool | Export last query results |

### Example Usage

```python
from db_tools import get_db

db = get_db()

# List all tables
db.tables()

# Describe a table
db.describe("users")

# Query with display
results = db.query("SELECT * FROM users WHERE active = true LIMIT 10")

# Export to CSV
db.to_csv("users", "users_export.csv")
db.to_csv("SELECT * FROM orders WHERE date > '2024-01-01'", "recent_orders.csv")

# Parameterized query (safe from SQL injection)
db.query("SELECT * FROM users WHERE email = %s", ("user@example.com",))

# Count with filter
db.count("orders", "status = 'pending'")
```

## Output Format

Tables are displayed using `tabulate` (psql format) or fallback ASCII:

```
+----+----------+------------------+------------+
| id | username | email            | created_at |
+----+----------+------------------+------------+
| 1  | alice    | alice@example.com| 2024-01-15 |
| 2  | bob      | bob@example.com  | 2024-01-16 |
+----+----------+------------------+------------+
```

## Dependencies

Required:
- `psycopg2-binary` - PostgreSQL adapter

Optional:
- `tabulate` - Pretty table output
- `python-dotenv` - Load .env files

```bash
pip install psycopg2-binary tabulate python-dotenv
```

## Error Handling

- Connection errors show host/port info
- Query errors trigger automatic rollback
- Timeout: 10 second connection timeout
- SSL: Required by default for Azure

## Security Notes

- Use parameterized queries for user input
- Credentials loaded from env vars (not hardcoded)
- SSL mode "require" for encrypted connections
- Read-only queries recommended for exploration
