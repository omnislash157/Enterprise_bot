# PostgreSQL Migration Guide - Phase 5

This guide walks through migrating existing file-based memory data to PostgreSQL with pgvector.

## Prerequisites

### 1. Install Required Packages

```bash
pip install asyncpg pgvector
```

### 2. Set Up PostgreSQL with pgvector

You need a PostgreSQL instance with the pgvector extension. Options:

**Option A: Railway (Recommended for production)**
```bash
# Create a new PostgreSQL database on Railway
# Railway includes pgvector by default
```

**Option B: Local PostgreSQL**
```bash
# Install PostgreSQL 14+ and pgvector
# macOS
brew install postgresql pgvector

# Ubuntu/Debian
sudo apt install postgresql-14 postgresql-14-pgvector

# Start PostgreSQL
brew services start postgresql  # macOS
sudo systemctl start postgresql # Linux
```

### 3. Create Database and Run Schema

```bash
# Create database
createdb cogtwin_memory

# Run migration schema
psql cogtwin_memory -f db/migrations/001_memory_tables.sql
```

### 4. Set Environment Variable

```bash
# Set DATABASE_URL
export DATABASE_URL='postgresql://username:password@localhost:5432/cogtwin_memory'

# For Railway, use the connection string from your dashboard
export DATABASE_URL='postgresql://postgres:...'
```

## Migration Process

### Step 1: Verify Your Data

Check that your existing data is present:

```bash
# Verify nodes.json exists and has data
ls -lh data/corpus/nodes.json

# Verify embeddings exist
ls -lh data/vectors/nodes.npy
```

### Step 2: Create User or Tenant

You need to create a user (personal mode) or tenant (enterprise mode) first.

**For Personal Mode:**
```sql
-- Create a test user
INSERT INTO users (id, auth_provider, external_id, email, display_name)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'test',
    'test_user_001',
    'test@example.com',
    'Test User'
);
```

**For Enterprise Mode:**
```sql
-- Create tenant
INSERT INTO tenants (id, name, voice_engine, extraction_enabled)
VALUES (
    '22222222-2222-2222-2222-222222222222',
    'driscoll',
    'enterprise',
    false
);

-- Create enterprise user linked to tenant
INSERT INTO users (id, auth_provider, external_id, email, display_name, tenant_id)
VALUES (
    '33333333-3333-3333-3333-333333333333',
    'azure_ad',
    'admin@driscoll.com',
    'admin@driscoll.com',
    'Driscoll Admin',
    '22222222-2222-2222-2222-222222222222'
);
```

### Step 3: Run Migration

**Personal Mode:**
```bash
python migrate_to_postgres.py --user-id 11111111-1111-1111-1111-111111111111
```

**Enterprise Mode:**
```bash
python migrate_to_postgres.py --tenant-id 22222222-2222-2222-2222-222222222222
```

**Custom Data Directory:**
```bash
python migrate_to_postgres.py --user-id 11111111-1111-1111-1111-111111111111 --data-dir /path/to/data
```

### Step 4: Verify Migration

```sql
-- Check total nodes migrated
SELECT COUNT(*) FROM memory_nodes;

-- Check nodes by user
SELECT user_id, COUNT(*) as node_count
FROM memory_nodes
GROUP BY user_id;

-- Check nodes by tenant
SELECT tenant_id, COUNT(*) as node_count
FROM memory_nodes
GROUP BY tenant_id;

-- Test vector search (should return similar nodes)
SELECT id, human_content, assistant_content
FROM memory_nodes
ORDER BY embedding <=> (SELECT embedding FROM memory_nodes LIMIT 1)
LIMIT 5;
```

## Migration Output

The script provides detailed progress and statistics:

```
============================================================
PostgreSQL Migration Tool - Phase 5
============================================================

Data directory: /Users/you/projects/enterprise_bot/data
Database: localhost:5432/cogtwin_memory

Ready to migrate in personal mode
All nodes will be stamped with: user_id = 11111111-1111-1111-1111-111111111111

Continue? [y/N]: y

Connected to PostgreSQL
Schema verified: memory_nodes table exists

------------------------------------------------------------
LOADING DATA FROM FILES
------------------------------------------------------------
Loaded 1523 nodes from data/corpus/nodes.json
Loaded embeddings with shape: (1523, 1024)

------------------------------------------------------------
MIGRATING TO POSTGRESQL
------------------------------------------------------------
Progress: 1523/1523 (100.0%) - 1523 migrated, 0 errors

============================================================
MIGRATION SUMMARY
============================================================
Total nodes found:       1523
Successfully migrated:   1523
Skipped:                 0
Errors:                  0
Time taken:              12.34s
Average per node:        8.1ms
============================================================

Migration completed successfully!
```

## Troubleshooting

### Error: "memory_nodes table does not exist"

Run the schema migration first:
```bash
psql $DATABASE_URL -f db/migrations/001_memory_tables.sql
```

### Error: "Invalid UUID format"

Ensure you're using a valid UUID format:
```bash
# Valid UUID format (with hyphens)
11111111-1111-1111-1111-111111111111

# Invalid formats
11111111111111111111111111111111  # No hyphens
test_user_123                      # Not a UUID
```

### Error: "DATABASE_URL environment variable not set"

Set the environment variable:
```bash
export DATABASE_URL='postgresql://user:pass@host:port/dbname'
```

### Error: "Nodes file not found"

Ensure your data directory is correct:
```bash
# Check data structure
ls -la data/corpus/
ls -la data/vectors/

# Use custom data directory
python migrate_to_postgres.py --user-id <uuid> --data-dir /path/to/data
```

### Error: "Node count does not match embedding count"

Your data files are out of sync. Regenerate them:
```bash
# Re-run ingestion to sync files
python ingest.py
```

## Post-Migration

### Update Config

Update `config.yaml` to use PostgreSQL backend:

```yaml
memory:
  backend: postgres  # Change from 'file' to 'postgres'
  postgres:
    connection_string: ${DATABASE_URL}
```

### Test Retrieval

Start the server and test that memory retrieval works:

```bash
python main.py
```

Navigate to http://localhost:8000 and ask a question that should match your migrated memories.

### Performance Tuning

For large corpora (>100k nodes), adjust the IVFFlat index:

```sql
-- Drop old index
DROP INDEX idx_memory_nodes_embedding;

-- Create new index with more lists
CREATE INDEX idx_memory_nodes_embedding ON memory_nodes
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 500);  -- Adjust based on corpus size

-- For >1M vectors, consider HNSW instead
CREATE INDEX idx_memory_nodes_embedding ON memory_nodes
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

### Backup Strategy

**File-based (before migration):**
```bash
# Backup entire data directory
tar -czf data-backup-$(date +%Y%m%d).tar.gz data/
```

**PostgreSQL (after migration):**
```bash
# Backup database
pg_dump $DATABASE_URL > cogtwin_backup_$(date +%Y%m%d).sql

# Backup with compression
pg_dump $DATABASE_URL | gzip > cogtwin_backup_$(date +%Y%m%d).sql.gz
```

## Rollback

If you need to rollback to file-based storage:

1. Keep your original `data/` directory
2. Change `config.yaml` back to `backend: file`
3. Restart the server

The file-based data remains untouched during migration.

## Multi-Tenant Migration

To migrate data for multiple tenants:

```bash
# Tenant 1
python migrate_to_postgres.py --tenant-id <tenant1_uuid> --data-dir /data/tenant1

# Tenant 2
python migrate_to_postgres.py --tenant-id <tenant2_uuid> --data-dir /data/tenant2
```

Each tenant's memories are isolated by `tenant_id` in the database.

## Support

For issues or questions:
1. Check the error message and troubleshooting section
2. Verify database connection: `psql $DATABASE_URL -c "SELECT version();"`
3. Check schema exists: `psql $DATABASE_URL -c "\dt"`
4. Review migration logs for specific errors
