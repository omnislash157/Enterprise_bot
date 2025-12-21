# Skill: Data Profiling (profile)

## Overview
Analyze data quality, distributions, and statistics. Identify nulls, outliers, and data issues.

## Capabilities

### Column Statistics
- Count, distinct count, null count
- Min, max, mean, median, stddev
- Top values and frequencies
- Data type validation

### Quality Checks
- Null percentage thresholds
- Duplicate detection
- Referential integrity
- Format validation (email, phone, etc.)

### Distribution Analysis
- Histograms
- Percentiles
- Skewness and kurtosis
- Outlier detection

## SQL Profiling Queries

### Basic Column Profile
```sql
SELECT
    COUNT(*) as total_rows,
    COUNT(column_name) as non_null_count,
    COUNT(*) - COUNT(column_name) as null_count,
    ROUND(100.0 * (COUNT(*) - COUNT(column_name)) / COUNT(*), 2) as null_pct,
    COUNT(DISTINCT column_name) as distinct_count,
    MIN(column_name) as min_value,
    MAX(column_name) as max_value
FROM table_name;
```

### Numeric Column Profile
```sql
SELECT
    COUNT(*) as total_rows,
    COUNT(amount) as non_null,
    ROUND(AVG(amount), 2) as mean,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount) as median,
    ROUND(STDDEV(amount), 2) as stddev,
    MIN(amount) as min_value,
    MAX(amount) as max_value,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY amount) as p25,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY amount) as p75,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY amount) as p95
FROM orders;
```

### Top Values
```sql
SELECT
    column_name,
    COUNT(*) as frequency,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
FROM table_name
WHERE column_name IS NOT NULL
GROUP BY column_name
ORDER BY frequency DESC
LIMIT 10;
```

### Full Table Profile
```sql
WITH column_stats AS (
    SELECT
        'column_1' as column_name,
        COUNT(*) as total,
        COUNT(column_1) as non_null,
        COUNT(DISTINCT column_1) as distinct_count
    FROM table_name
    UNION ALL
    SELECT
        'column_2',
        COUNT(*),
        COUNT(column_2),
        COUNT(DISTINCT column_2)
    FROM table_name
    -- Repeat for each column
)
SELECT
    column_name,
    total,
    non_null,
    total - non_null as nulls,
    ROUND(100.0 * (total - non_null) / total, 2) as null_pct,
    distinct_count,
    ROUND(100.0 * distinct_count / non_null, 2) as unique_pct
FROM column_stats;
```

## Python Profiler

```python
import pandas as pd
from db_tools import get_db

def profile_table(table_name, sample_size=10000):
    """Generate comprehensive table profile."""
    db = get_db()

    # Get sample
    df = pd.DataFrame(db.sample(table_name, sample_size))

    profile = {
        "table": table_name,
        "row_count": db.count(table_name),
        "sample_size": len(df),
        "columns": []
    }

    for col in df.columns:
        col_profile = {
            "name": col,
            "dtype": str(df[col].dtype),
            "non_null": df[col].count(),
            "null_count": df[col].isnull().sum(),
            "null_pct": round(100 * df[col].isnull().sum() / len(df), 2),
            "unique": df[col].nunique(),
            "unique_pct": round(100 * df[col].nunique() / df[col].count(), 2) if df[col].count() > 0 else 0,
        }

        # Numeric stats
        if df[col].dtype in ['int64', 'float64']:
            col_profile.update({
                "min": df[col].min(),
                "max": df[col].max(),
                "mean": round(df[col].mean(), 2),
                "median": df[col].median(),
                "stddev": round(df[col].std(), 2),
                "p25": df[col].quantile(0.25),
                "p75": df[col].quantile(0.75),
                "p95": df[col].quantile(0.95),
            })

        # Top values
        top_values = df[col].value_counts().head(5).to_dict()
        col_profile["top_values"] = top_values

        profile["columns"].append(col_profile)

    return profile
```

## Quality Rules

### Null Threshold Check
```python
def check_null_thresholds(profile, thresholds):
    """Check columns against null thresholds."""
    issues = []
    for col in profile["columns"]:
        threshold = thresholds.get(col["name"], 5)  # Default 5%
        if col["null_pct"] > threshold:
            issues.append({
                "column": col["name"],
                "issue": "null_threshold",
                "actual": col["null_pct"],
                "threshold": threshold
            })
    return issues
```

### Duplicate Check
```sql
SELECT
    column_1, column_2,  -- key columns
    COUNT(*) as duplicate_count
FROM table_name
GROUP BY column_1, column_2
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;
```

### Referential Integrity Check
```sql
-- Find orphaned records
SELECT c.id, c.parent_id
FROM child_table c
LEFT JOIN parent_table p ON c.parent_id = p.id
WHERE p.id IS NULL;
```

### Format Validation
```sql
-- Email format check
SELECT email, COUNT(*)
FROM users
WHERE email !~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
GROUP BY email;

-- Phone format check
SELECT phone, COUNT(*)
FROM users
WHERE phone !~ '^\+?[0-9]{10,15}$'
GROUP BY phone;
```

## CLI Commands (Planned)

```
/db profile <table>              Full table profile
/db profile <table> <column>     Single column profile
/db quality <table>              Run quality checks
/db duplicates <table> <cols>    Find duplicates
/db orphans <child> <parent>     Find orphaned records
```

## Output Formats

### Console Table
```
Column Profile: users
+------------+--------+-------+--------+---------+--------+
| Column     | Type   | Nulls | Null%  | Unique  | Top    |
+------------+--------+-------+--------+---------+--------+
| id         | int64  | 0     | 0.0%   | 10000   | -      |
| email      | object | 5     | 0.05%  | 9995    | -      |
| status     | object | 0     | 0.0%   | 3       | active |
| created_at | datetime| 0    | 0.0%   | 9876    | -      |
+------------+--------+-------+--------+---------+--------+
```

### JSON Export
```json
{
  "table": "users",
  "row_count": 10000,
  "columns": [
    {
      "name": "email",
      "dtype": "object",
      "null_pct": 0.05,
      "unique": 9995,
      "top_values": {"user@example.com": 2}
    }
  ]
}
```

## Dependencies

```bash
pip install pandas
```
