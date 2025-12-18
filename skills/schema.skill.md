# Skill: Schema Design (schema)

## Overview
Database schema design, migrations, star schema generation, and DDL management.

## Capabilities

### Schema Design
- Table design with constraints
- Index recommendations
- Foreign key relationships
- Normalization analysis

### Migrations
- Generate migration scripts
- Up/down migrations
- Version tracking
- Rollback support

### Star Schema
- Identify fact tables
- Extract dimensions
- Generate surrogate keys
- SCD Type 1/2 patterns

## DDL Generation

### Create Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = true;
```

### Foreign Keys
```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    total_amount DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
```

## Star Schema Templates

### Fact Table
```sql
CREATE TABLE fact_sales (
    sale_id SERIAL PRIMARY KEY,
    -- Dimension keys (surrogate)
    date_key INTEGER REFERENCES dim_date(date_key),
    customer_key INTEGER REFERENCES dim_customer(customer_key),
    product_key INTEGER REFERENCES dim_product(product_key),
    store_key INTEGER REFERENCES dim_store(store_key),

    -- Degenerate dimensions
    order_number VARCHAR(50),

    -- Measures
    quantity INTEGER,
    unit_price DECIMAL(10, 2),
    discount_amount DECIMAL(10, 2),
    total_amount DECIMAL(10, 2),

    -- Audit
    load_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bitmap indexes for dimensions (PostgreSQL uses B-tree)
CREATE INDEX idx_fact_sales_date ON fact_sales(date_key);
CREATE INDEX idx_fact_sales_customer ON fact_sales(customer_key);
CREATE INDEX idx_fact_sales_product ON fact_sales(product_key);
```

### Date Dimension
```sql
CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,  -- YYYYMMDD format
    full_date DATE NOT NULL,
    day_of_week INTEGER,
    day_name VARCHAR(10),
    day_of_month INTEGER,
    day_of_year INTEGER,
    week_of_year INTEGER,
    month_number INTEGER,
    month_name VARCHAR(10),
    quarter INTEGER,
    year INTEGER,
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    fiscal_year INTEGER,
    fiscal_quarter INTEGER
);

-- Populate date dimension
INSERT INTO dim_date
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER as date_key,
    d as full_date,
    EXTRACT(DOW FROM d) as day_of_week,
    TO_CHAR(d, 'Day') as day_name,
    EXTRACT(DAY FROM d) as day_of_month,
    EXTRACT(DOY FROM d) as day_of_year,
    EXTRACT(WEEK FROM d) as week_of_year,
    EXTRACT(MONTH FROM d) as month_number,
    TO_CHAR(d, 'Month') as month_name,
    EXTRACT(QUARTER FROM d) as quarter,
    EXTRACT(YEAR FROM d) as year,
    EXTRACT(DOW FROM d) IN (0, 6) as is_weekend,
    FALSE as is_holiday,
    CASE WHEN EXTRACT(MONTH FROM d) >= 7
         THEN EXTRACT(YEAR FROM d) + 1
         ELSE EXTRACT(YEAR FROM d) END as fiscal_year,
    CASE WHEN EXTRACT(MONTH FROM d) >= 7
         THEN EXTRACT(QUARTER FROM d) - 2
         ELSE EXTRACT(QUARTER FROM d) + 2 END as fiscal_quarter
FROM generate_series('2020-01-01'::date, '2030-12-31'::date, '1 day'::interval) d;
```

### Customer Dimension (SCD Type 2)
```sql
CREATE TABLE dim_customer (
    customer_key SERIAL PRIMARY KEY,  -- Surrogate key
    customer_id INTEGER NOT NULL,     -- Natural key
    name VARCHAR(255),
    email VARCHAR(255),
    segment VARCHAR(50),
    region VARCHAR(100),
    -- SCD Type 2 fields
    effective_date DATE NOT NULL,
    expiration_date DATE DEFAULT '9999-12-31',
    is_current BOOLEAN DEFAULT true
);

CREATE INDEX idx_dim_customer_natural ON dim_customer(customer_id);
CREATE INDEX idx_dim_customer_current ON dim_customer(customer_id, is_current)
    WHERE is_current = true;
```

## Migration Scripts

### Migration Template
```sql
-- Migration: 001_create_users
-- Created: 2024-01-15

-- UP
BEGIN;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_migrations (version, applied_at)
VALUES ('001_create_users', CURRENT_TIMESTAMP);

COMMIT;

-- DOWN
BEGIN;

DROP TABLE IF EXISTS users;

DELETE FROM schema_migrations WHERE version = '001_create_users';

COMMIT;
```

### Migration Tracking
```sql
CREATE TABLE schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## CLI Commands (Planned)

```
/schema design <table>           Interactive table designer
/schema analyze <table>          Analyze existing table
/schema normalize <table>        Suggest normalization
/schema star <fact> <dims>       Generate star schema
/schema migrate create <name>    Create new migration
/schema migrate up               Run pending migrations
/schema migrate down             Rollback last migration
/schema migrate status           Show migration status
```

## Index Recommendations

```python
def recommend_indexes(table_name, query_patterns):
    """Analyze query patterns and recommend indexes."""
    recommendations = []

    for query in query_patterns:
        # WHERE clause columns
        where_cols = extract_where_columns(query)
        if where_cols:
            recommendations.append({
                "type": "B-tree",
                "columns": where_cols,
                "reason": "Filter optimization"
            })

        # JOIN columns
        join_cols = extract_join_columns(query)
        if join_cols:
            recommendations.append({
                "type": "B-tree",
                "columns": join_cols,
                "reason": "Join optimization"
            })

        # ORDER BY columns
        order_cols = extract_order_columns(query)
        if order_cols:
            recommendations.append({
                "type": "B-tree",
                "columns": order_cols,
                "reason": "Sort optimization"
            })

    return deduplicate(recommendations)
```

## PostgreSQL-Specific Features

### Partial Indexes
```sql
-- Index only active users
CREATE INDEX idx_users_active ON users(email)
    WHERE is_active = true;
```

### Expression Indexes
```sql
-- Index on lowercase email
CREATE INDEX idx_users_email_lower ON users(LOWER(email));
```

### GIN Indexes (for JSONB/arrays)
```sql
CREATE INDEX idx_users_metadata ON users USING GIN(metadata);
```

### BRIN Indexes (for time-series)
```sql
CREATE INDEX idx_events_time ON events USING BRIN(created_at);
```
