# SCHEMA LAW - MANDATORY PROTOCOL

## The Rule

**ANY database change MUST be immediately followed by:**
1. Running `SCHEMA_EXTRACTION.sql` against Azure PostgreSQL
2. Updating `DATABASE_SCHEMA_MAP.md` with the output
3. Committing the schema map in the same PR/commit as the code change

**No exceptions. No "I'll do it later." No "it's just a small index."**

---

## Why This Exists

- Ghost bugs from schema drift
- Recon missions waste hours rediscovering what tables exist
- SDK agents hallucinate column names that don't exist
- "It works on my machine" because local schema ≠ production schema

---

## The Workflow

### Before ANY Database Work
```bash
# Pull current state first
psql -h cogtwin.postgres.database.azure.com -U admin -d enterprise_bot -f SCHEMA_EXTRACTION.sql > schema_before.txt
```

### After ANY Database Work
```bash
# 1. Run extraction
psql -h cogtwin.postgres.database.azure.com -U admin -d enterprise_bot -f SCHEMA_EXTRACTION.sql > schema_after.txt

# 2. Diff to see what changed
diff schema_before.txt schema_after.txt

# 3. Update the schema map document
# (manually or via script that parses output)

# 4. Commit together
git add DATABASE_SCHEMA_MAP.md
git add migrations/XXX_whatever.sql  # if applicable
git commit -m "feat(db): add X table + update schema map"
```

---

## What Counts as a Database Change

- ✅ CREATE TABLE
- ✅ ALTER TABLE (add/drop/modify column)
- ✅ CREATE INDEX
- ✅ DROP INDEX
- ✅ CREATE/DROP FUNCTION
- ✅ CREATE/DROP TRIGGER
- ✅ CREATE/DROP VIEW
- ✅ Any DDL statement whatsoever

---

## Schema Map Location

```
docs/DATABASE_SCHEMA_MAP.md
```

This file is the **single source of truth** for what exists in production.

---

## Build Sheet Addendum

Add this section to EVERY build sheet that touches the database:

```markdown
## DATABASE CHANGE PROTOCOL

- [ ] Ran SCHEMA_EXTRACTION.sql before changes
- [ ] Ran SCHEMA_EXTRACTION.sql after changes  
- [ ] Updated docs/DATABASE_SCHEMA_MAP.md
- [ ] Schema map committed with code changes
```

---

## Enforcement

**Code review checklist:**
- [ ] Does this PR touch the database?
- [ ] If yes, is DATABASE_SCHEMA_MAP.md updated in the same PR?
- [ ] If no schema map update, **BLOCK THE PR**

---

## Quick Reference Commands

```bash
# Connect to Azure PostgreSQL
psql "host=cogtwin.postgres.database.azure.com port=5432 dbname=enterprise_bot user=admin sslmode=require"

# Run full extraction
\i SCHEMA_EXTRACTION.sql

# Quick table list
\dt enterprise.*

# Quick column check
\d enterprise.table_name

# Row counts
SELECT schemaname, tablename, n_live_tup FROM pg_stat_user_tables ORDER BY schemaname, tablename;
```

---

## Schema Map Template

The DATABASE_SCHEMA_MAP.md should follow this structure:

```markdown
# Database Schema Map
**Last Updated:** YYYY-MM-DD HH:MM UTC
**Updated By:** [name]
**Reason:** [what changed]

## Schemas
- enterprise (main application schema)
- public (extensions only)

## Tables

### enterprise.users
| Column | Type | Nullable | Default | Key | References |
|--------|------|----------|---------|-----|------------|
| id | uuid | NO | gen_random_uuid() | PK | |
| email | varchar(255) | NO | | | |
...

### enterprise.traces
...

## Indexes
...

## Functions
...

## Row Counts
| Table | Rows |
|-------|------|
| users | 42 |
| traces | 0 |
...
```

---

**This is law. Follow it.**
