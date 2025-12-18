# Quick Start: PostgreSQL Migration

**5-minute guide to migrating from file-based to PostgreSQL storage.**

## Prerequisites

```bash
# 1. Install dependencies
pip install asyncpg pgvector

# 2. Set database URL
export DATABASE_URL='postgresql://user:pass@host:port/dbname'
```

## Step 1: Create Schema (30 seconds)

```bash
psql $DATABASE_URL -f db/migrations/001_memory_tables.sql
```

## Step 2: Generate Test User (10 seconds)

```bash
python generate_test_user.py --mode personal --email test@example.com
```

This outputs:
- SQL to create user
- User UUID
- Migration command

## Step 3: Create User in Database (10 seconds)

Copy the SQL from Step 2 and run:

```bash
psql $DATABASE_URL -c "INSERT INTO users ..."
```

Or save to file:
```bash
python generate_test_user.py --mode personal --email test@example.com --output user.sql
psql $DATABASE_URL -f user.sql
```

## Step 4: Run Migration (1-2 minutes)

```bash
# Use the UUID from Step 2
python migrate_to_postgres.py --user-id <uuid-from-step-2>
```

Example output:
```
============================================================
PostgreSQL Migration Tool - Phase 5
============================================================

Connected to PostgreSQL
Schema verified: memory_nodes table exists

Loaded 1523 nodes from data/corpus/nodes.json
Loaded embeddings with shape: (1523, 1024)

Progress: 1523/1523 (100.0%) - 1523 migrated, 0 errors

============================================================
MIGRATION SUMMARY
============================================================
Total nodes found:       1523
Successfully migrated:   1523
Errors:                  0
Time taken:              12.34s
============================================================
```

## Step 5: Verify (10 seconds)

```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM memory_nodes;"
```

## Complete Example (Copy-Paste)

```bash
# Setup
export DATABASE_URL='postgresql://localhost/cogtwin_memory'
pip install asyncpg pgvector

# Create schema
psql $DATABASE_URL -f db/migrations/001_memory_tables.sql

# Generate user SQL
python generate_test_user.py --mode personal --email test@example.com --output user.sql

# Create user
psql $DATABASE_URL -f user.sql

# Extract UUID from user.sql for migration
USER_ID=$(grep "VALUES" user.sql | sed -n "s/.*'\([^']*\)'.*/\1/p")

# Run migration
python migrate_to_postgres.py --user-id $USER_ID

# Verify
psql $DATABASE_URL -c "SELECT COUNT(*) FROM memory_nodes WHERE user_id = '$USER_ID';"
```

## Enterprise Mode

For enterprise/tenant migration:

```bash
# Generate tenant + user
python generate_test_user.py --mode enterprise \
  --tenant-name driscoll \
  --email admin@driscoll.com \
  --output tenant.sql

# Create in database
psql $DATABASE_URL -f tenant.sql

# Extract tenant UUID
TENANT_ID=$(grep "INSERT INTO tenants" tenant.sql | sed -n "s/.*'\([^']*\)'.*/\1/p")

# Migrate with tenant scope
python migrate_to_postgres.py --tenant-id $TENANT_ID
```

## Troubleshooting

### "DATABASE_URL not set"
```bash
export DATABASE_URL='postgresql://user:pass@host:port/dbname'
```

### "memory_nodes table does not exist"
```bash
psql $DATABASE_URL -f db/migrations/001_memory_tables.sql
```

### "Invalid UUID format"
Use the UUID from `generate_test_user.py` output, format: `11111111-1111-1111-1111-111111111111`

### "Nodes file not found"
Ensure you're in the project root and `data/corpus/nodes.json` exists.

## Next: Update Config

After successful migration, update `config.yaml`:

```yaml
memory:
  backend: postgres  # Change from 'file'
  postgres:
    connection_string: ${DATABASE_URL}
```

Then restart:
```bash
python main.py
```

## Rollback

To rollback to file-based storage:

1. Keep original `data/` directory
2. Change `config.yaml` back to `backend: file`
3. Restart server

The file-based data remains untouched during migration.

---

**For detailed documentation, see:**
- `MIGRATION_GUIDE.md` - Complete guide with troubleshooting
- `PHASE_5_SUMMARY.md` - Technical overview and design decisions
