# CHANGELOG

> **CONTEXT GUARD**: If Claude's last memory shows updating this changelog but the entries here don't match, the `/mnt/project` folder is stale. Ask user to sync project files.

---

## 2025-12-31

### Cogzy Personal Tier Launch
Wired personal auth into main.py - users can now sign up via email/password or Google OAuth. Added Redis session store initialization and cleanup. Created `clients/cogzy.yaml` with green branding extending `_personal.yaml`.

### Tenant Config System
Enhanced `tenant_loader.py` with `_extends` inheritance support. Added `/api/tenant/config` endpoint for dynamic branding. Frontend-cogzy now loads tenant config on mount and applies branding dynamically - no more hardcoded "Driscoll Intelligence".

### Enterprise Subdomain Support
Created wildcard tenant SQL for `*.cogzy.ai` subdomains. Any `{customer}.cogzy.ai` now resolves automatically with slug extraction from subdomain. Ready for Sysco, Ocean County College, etc.

### Docs Cleanup
Removed outdated docs (AdminPortal_AddUsers.md, PERSONAL_AUTH_IMPLEMENTATION.md, RECON_STREAMING_PIPELINE.md, cogrecon.md, credit_pipeline_handoff.md, database_map_index.md, driscoll_credit_schema.md, personalauth.md). Added FEATURE_BUILD_SHEET_TEMPLATE.md and SESSION_QUICKSTART.md.

---

## 2025-12-30

### Database Schema Frozen
Established schema commandments - no new tables/columns without dedicated architecture session. Created comprehensive DATABASE_SCHEMA_MAP.md with all 22 tables, 319 columns, 113 indexes documented.

### Frontend Tree Documentation
Created FRONTEND_TREE.md documenting both frontend/ (Enterprise) and frontend-cogzy/ (Personal SaaS) structures.

---

## Format Guide

```
## YYYY-MM-DD

### Feature/Fix Title (2-6 lines)
Brief description of what was accomplished. Include key files modified
if helpful. No need for exact git commit messages - summarize the win.
```
