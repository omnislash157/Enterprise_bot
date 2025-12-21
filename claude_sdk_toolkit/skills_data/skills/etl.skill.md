# Skill: ETL Pipeline Generation (etl)

## Overview
Generate ETL (Extract-Transform-Load) pipelines from database schemas. Creates pandas-based Python scripts.

## Capabilities

### Extract Patterns
- Full table extraction
- Incremental by timestamp/ID
- Change Data Capture (CDC) simulation
- Parameterized date ranges

### Transform Patterns
- Column renaming (snake_case, camelCase)
- Type casting and validation
- Null handling (fill, drop, default)
- Deduplication
- Aggregations
- Joins and lookups

### Load Patterns
- Insert (append)
- Upsert (insert or update)
- Truncate and load
- Merge (SCD Type 1/2)

## Generated Script Structure

```python
#!/usr/bin/env python3
"""
ETL Pipeline: {source} -> {target}
Generated: {timestamp}
"""

import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, timedelta

# Configuration
SOURCE_CONN = os.getenv("SOURCE_DB_URL")
TARGET_CONN = os.getenv("TARGET_DB_URL")

def extract(conn, last_run=None):
    """Extract data from source."""
    query = """
        SELECT * FROM {table}
        WHERE updated_at > %(last_run)s
    """
    return pd.read_sql(query, conn, params={"last_run": last_run})

def transform(df):
    """Apply transformations."""
    df = df.copy()
    # Rename columns
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    # Handle nulls
    df["status"] = df["status"].fillna("unknown")
    # Type conversions
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df

def load(df, conn, table, mode="append"):
    """Load to target."""
    df.to_sql(table, conn, if_exists=mode, index=False)

def run_pipeline():
    """Main ETL orchestration."""
    source = create_engine(SOURCE_CONN)
    target = create_engine(TARGET_CONN)

    # Track last run
    last_run = get_last_run() or datetime(2020, 1, 1)

    # ETL
    raw = extract(source, last_run)
    clean = transform(raw)
    load(clean, target, "target_table")

    # Update checkpoint
    save_last_run(datetime.now())

if __name__ == "__main__":
    run_pipeline()
```

## CLI Commands (Planned)

```
/etl generate <source_table> <target_table>  Generate ETL script
/etl incremental <table> <timestamp_col>     Generate incremental ETL
/etl full <table>                            Generate full-load ETL
/etl validate <script>                       Validate ETL script
```

## Best Practices

1. **Idempotency** - Scripts can be re-run safely
2. **Checkpointing** - Track last successful run
3. **Logging** - Log row counts, timing, errors
4. **Validation** - Verify data quality post-load
5. **Atomicity** - Use transactions for loads

## Dependencies

```bash
pip install pandas sqlalchemy psycopg2-binary
```

## Integration with db_tools

```python
from db_tools import get_db

db = get_db()

# Analyze source table
db.describe("source_table")
db.sample("source_table", 5)

# Generate ETL based on schema
# (ETL generator would read this metadata)
```
