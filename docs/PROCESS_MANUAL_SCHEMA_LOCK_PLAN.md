# Process Manual Schema Lock - Implementation Plan
**Driscoll Tenant (Tenant 1) - Multi-Tenant Architecture Foundation**

**Date:** December 18, 2024
**Status:** ✅ **APPROVED FOR EXECUTION**
**Scope:** Database schema enhancement, RLS implementation, chunking/embedding pipeline, multi-tenant architecture lock
**Timeline:** 17 days (sequential + parallel optimization)

---

## Executive Summary

This plan establishes a **schema-locked architecture** for process manuals in the enterprise bot, starting with Driscoll Foods as Tenant 1. The system will:

1. **Chunk 24 warehouse DOCX files → JSON format** (Phase 2.5) matching existing Sales/Purchasing structure
2. **Enhance `department_content` table** with vector embeddings (VECTOR(1024)), chunk hierarchy, metadata (Phase 1)
3. **Implement PostgreSQL Row Level Security (RLS)** for department-based access control at database level (Phase 2)
4. **Ingest 28 JSON files** (24 warehouse + 4 existing) into PostgreSQL with BGE-M3 embeddings via DeepInfra API (Phase 3)
5. **Integrate vector search** with CogTwin engine, combining manual chunks + conversation memories (Phase 4)
6. **Lock multi-tenant schema** (Phase 5) with Driscoll as reference implementation for future tenants

**Key Decisions:**
- ✅ PostgreSQL RLS policies for database-level security
- ✅ BGE-M3 embeddings via existing `embedder.py` + DeepInfra API
- ✅ Semantic chunking (by section/heading) for document structure preservation
- ✅ Manual department assignment only (admin portal) - NO Azure AD auto-assignment
- ✅ 17-day timeline with Phase 2.5 running parallel to Phase 1-2

---

## Current State Assessment

### ✅ What Already Works

| Component | Status | Details |
|-----------|--------|---------|
| **Azure Entra ID Integration** | ✅ Working | Email extraction via MSAL OAuth2, auto-provisioning users |
| **Database Schema** | ✅ Exists | `enterprise.departments`, `enterprise.department_content`, `enterprise.user_department_access` |
| **Admin Portal** | ✅ Complete | User management, department assignment, audit log (frontend + backend) |
| **Manuals Folder** | ✅ Populated | 24 warehouse DOCX files, 3 sales JSON chunks, 1 purchasing JSON chunk |
| **Permission Tiers** | ✅ Implemented | USER, DEPT_HEAD, SUPER_USER with application-level enforcement |
| **Audit Trail** | ✅ Active | `enterprise.access_audit_log` for SOX compliance |

### ❌ What's Missing

| Component | Status | Issue |
|-----------|--------|-------|
| **PostgreSQL RLS Policies** | ❌ Not Implemented | Access control is application-level only - no DB-level RLS |
| **Vector Embeddings in DB** | ❌ Missing | `department_content` has no `embedding` column |
| **Chunk Hierarchy** | ❌ Missing | No parent-child document-chunk relationship |
| **DOCX Processing Pipeline** | ❌ Missing | 24 warehouse DOCX files not ingested into database |
| **Semantic Chunking** | ❌ Missing | No structure-aware chunking (sections, headers, metadata) |
| **RLS for `department_content`** | ❌ Missing | No `ENABLE ROW LEVEL SECURITY` or `CREATE POLICY` statements |
| **Auto Department Assignment** | ❌ Missing | Azure AD groups not mapped to departments |

---

## Architecture Goals

### 1. Schema Lock Principles

**Definition:** A **schema lock** means the database structure for process manuals becomes the immutable foundation for all tenants. Once locked for Driscoll (Tenant 1), all future tenants follow the same structure.

**Why Lock?**
- **Multi-tenant consistency:** All tenants use identical table structure
- **Code reusability:** Single codebase serves all tenants
- **Migration safety:** Schema changes require explicit versioning
- **Security uniformity:** RLS policies apply identically across tenants

**Lock Criteria:**
- ✅ PostgreSQL RLS policies enabled and tested
- ✅ Chunk hierarchy validated with real documents
- ✅ Embedding pipeline produces consistent results
- ✅ Department-based access control verified
- ✅ Admin portal can manage all aspects
- ✅ Documentation complete

### 2. Multi-Tenant Hierarchy

```
enterprise_bot (application)
│
├── Tenant 1: Driscoll Foods
│   ├── Departments: Warehouse, Sales, Purchasing, Transportation, etc.
│   ├── Users: Auto-provisioned via Azure AD (driscoll.com domain)
│   ├── Manuals: 24+ process documents
│   └── Access Control: RLS based on user_department_access
│
├── Tenant 2: [Future Customer]
│   ├── Departments: [Custom departments]
│   ├── Users: Auto-provisioned via Azure AD ([customer] domain)
│   ├── Manuals: [Customer documents]
│   └── Access Control: Same RLS policies
│
└── Shared Infrastructure
    ├── PostgreSQL + pgvector
    ├── Azure AD OAuth2
    ├── Admin Portal
    └── CogTwin Engine
```

**Tenant Isolation:**
- Each tenant has a unique `tenant_id` (UUID)
- All tables have `tenant_id` foreign key
- RLS policies enforce `tenant_id` filtering
- Azure AD tenant ID maps to application `tenant_id`

---

## Phase-by-Phase Implementation Plan

---

## **PHASE 1: Database Schema Enhancement**
**Duration:** 2 days | **Dependencies:** None

---

**Goal:** Extend `department_content` table to support vector embeddings, chunk hierarchy, and rich metadata.

**Decision:** Use existing `department_content` table rather than creating new `process_manuals` table to maintain backward compatibility.

### 1.1 Create Migration Script

**File:** `db/migrations/002_enhance_department_content.sql`

**Changes:**
```sql
-- ============================================================================
-- PHASE 1: ENHANCE department_content FOR PROCESS MANUALS
-- ============================================================================

-- Add tenant_id for multi-tenant isolation
ALTER TABLE enterprise.department_content
ADD COLUMN tenant_id UUID REFERENCES tenants(id);

-- Create index on tenant_id
CREATE INDEX idx_dept_content_tenant_id ON enterprise.department_content(tenant_id);

-- Add vector embedding column (1024-dim BGE-M3 model)
ALTER TABLE enterprise.department_content
ADD COLUMN embedding VECTOR(1024);

-- Add chunk hierarchy columns
ALTER TABLE enterprise.department_content
ADD COLUMN parent_document_id UUID,                    -- Points to "parent" row (document root)
ADD COLUMN chunk_index INTEGER DEFAULT 0,              -- Order within document
ADD COLUMN is_document_root BOOLEAN DEFAULT FALSE,     -- TRUE for parent, FALSE for chunks
ADD COLUMN chunk_type VARCHAR(50) DEFAULT 'content';   -- 'title', 'section', 'content', 'metadata'

-- Add rich metadata columns
ALTER TABLE enterprise.department_content
ADD COLUMN source_file VARCHAR(255),                   -- Original filename (e.g., "Dispatching Manual.docx")
ADD COLUMN file_hash VARCHAR(64),                      -- SHA256 hash for deduplication
ADD COLUMN page_number INTEGER,                        -- Page in original document
ADD COLUMN section_title VARCHAR(255),                 -- Heading/section name
ADD COLUMN metadata JSONB DEFAULT '{}',                -- Flexible metadata (author, date, tags, etc.)
ADD COLUMN chunk_token_count INTEGER,                  -- Token count for this chunk
ADD COLUMN embedding_model VARCHAR(100) DEFAULT 'bge-m3-v1';  -- Model used for embedding

-- Add retrieval optimization columns
ALTER TABLE enterprise.department_content
ADD COLUMN access_count INTEGER DEFAULT 0,             -- How many times retrieved
ADD COLUMN last_accessed TIMESTAMPTZ,                  -- Last retrieval timestamp
ADD COLUMN relevance_score FLOAT;                      -- Optional pre-computed score

-- Add foreign key constraint for parent-child relationship (self-referencing)
ALTER TABLE enterprise.department_content
ADD CONSTRAINT fk_dept_content_parent
FOREIGN KEY (parent_document_id)
REFERENCES enterprise.department_content(id)
ON DELETE CASCADE;

-- Create indexes for performance
CREATE INDEX idx_dept_content_parent ON enterprise.department_content(parent_document_id);
CREATE INDEX idx_dept_content_chunk_idx ON enterprise.department_content(chunk_index);
CREATE INDEX idx_dept_content_is_root ON enterprise.department_content(is_document_root);
CREATE INDEX idx_dept_content_file_hash ON enterprise.department_content(file_hash);

-- Create IVFFlat vector index for cosine similarity search
CREATE INDEX idx_dept_content_embedding ON enterprise.department_content
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Add check constraint: chunks must have parent_document_id
ALTER TABLE enterprise.department_content
ADD CONSTRAINT chk_dept_content_chunk_parent
CHECK (
    (is_document_root = TRUE AND parent_document_id IS NULL) OR
    (is_document_root = FALSE AND parent_document_id IS NOT NULL)
);

-- Add unique constraint: prevent duplicate file hashes per tenant/department
CREATE UNIQUE INDEX idx_dept_content_unique_file
ON enterprise.department_content(tenant_id, department_id, file_hash)
WHERE file_hash IS NOT NULL AND is_document_root = TRUE;

-- Update timestamp trigger (already exists, but verify)
CREATE OR REPLACE FUNCTION enterprise.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_dept_content_updated_at ON enterprise.department_content;
CREATE TRIGGER update_dept_content_updated_at
BEFORE UPDATE ON enterprise.department_content
FOR EACH ROW
EXECUTE FUNCTION enterprise.update_updated_at_column();
```

**Rollback Script:**
```sql
-- Rollback: Remove added columns and constraints
ALTER TABLE enterprise.department_content
DROP COLUMN IF EXISTS tenant_id CASCADE,
DROP COLUMN IF EXISTS embedding CASCADE,
DROP COLUMN IF EXISTS parent_document_id CASCADE,
DROP COLUMN IF EXISTS chunk_index,
DROP COLUMN IF EXISTS is_document_root,
DROP COLUMN IF EXISTS chunk_type,
DROP COLUMN IF EXISTS source_file,
DROP COLUMN IF EXISTS file_hash,
DROP COLUMN IF EXISTS page_number,
DROP COLUMN IF EXISTS section_title,
DROP COLUMN IF EXISTS metadata,
DROP COLUMN IF EXISTS chunk_token_count,
DROP COLUMN IF EXISTS embedding_model,
DROP COLUMN IF EXISTS access_count,
DROP COLUMN IF EXISTS last_accessed,
DROP COLUMN IF EXISTS relevance_score;

DROP INDEX IF EXISTS idx_dept_content_tenant_id;
DROP INDEX IF EXISTS idx_dept_content_parent;
DROP INDEX IF EXISTS idx_dept_content_chunk_idx;
DROP INDEX IF EXISTS idx_dept_content_is_root;
DROP INDEX IF EXISTS idx_dept_content_file_hash;
DROP INDEX IF EXISTS idx_dept_content_embedding;
DROP INDEX IF EXISTS idx_dept_content_unique_file;
```

### 1.2 Apply Migration

**Steps:**
1. Test migration on local PostgreSQL instance
2. Verify indexes created successfully
3. Verify constraints enforced (try inserting invalid data)
4. Run EXPLAIN ANALYZE on sample queries
5. Apply to production Azure PostgreSQL

**Validation Queries:**
```sql
-- Verify columns added
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'enterprise'
AND table_name = 'department_content'
ORDER BY ordinal_position;

-- Verify indexes created
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'department_content';

-- Verify foreign keys
SELECT conname, contype, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'enterprise.department_content'::regclass;
```

**Success Criteria:**
- ✅ All columns added without errors
- ✅ All indexes created (8 new indexes)
- ✅ Foreign key constraint on `parent_document_id` works
- ✅ Check constraint prevents orphaned chunks
- ✅ Unique constraint prevents duplicate files
- ✅ IVFFlat index created for vector search

---

## **PHASE 2: PostgreSQL Row Level Security (RLS) Implementation**
**Duration:** 3 days | **Dependencies:** Phase 1

---

**Goal:** Enable database-level security policies so users can ONLY access documents for their assigned departments, enforced by PostgreSQL itself.

### 2.1 Design RLS Policies

**Architecture:**

```
User Request → FastAPI Endpoint → Set Session Variables → Query DB
                                   ↓
                           SET app.user_id = '<uuid>'
                           SET app.tenant_id = '<uuid>'
                                   ↓
                         PostgreSQL RLS Policy Enforces Filtering
                                   ↓
                         Returns ONLY Authorized Rows
```

**Policy Logic:**
1. **Tenant Isolation:** User can only access rows where `tenant_id` matches their tenant
2. **Department Access:** User can only access rows where `department_id` is in their `user_department_access` list
3. **Super Users:** Bypass RLS entirely (see all data for their tenant)

### 2.2 Create RLS Migration Script

**File:** `db/migrations/003_enable_rls_policies.sql`

```sql
-- ============================================================================
-- PHASE 2: ENABLE ROW LEVEL SECURITY (RLS) FOR DEPARTMENT CONTENT
-- ============================================================================

-- Enable RLS on department_content table
ALTER TABLE enterprise.department_content ENABLE ROW LEVEL SECURITY;

-- Create policy for SELECT: Users can only see content from departments they have access to
CREATE POLICY dept_content_select_policy ON enterprise.department_content
FOR SELECT
USING (
    -- Allow super users to see all content for their tenant
    (
        EXISTS (
            SELECT 1 FROM enterprise.users u
            WHERE u.id::text = current_setting('app.user_id', true)
            AND u.tenant_id = department_content.tenant_id
            AND u.role = 'super_user'
        )
    )
    OR
    -- Regular users: check department access
    (
        department_content.tenant_id::text = current_setting('app.tenant_id', true)
        AND
        EXISTS (
            SELECT 1 FROM enterprise.user_department_access uda
            WHERE uda.user_id::text = current_setting('app.user_id', true)
            AND uda.department_id = department_content.department_id
            AND uda.access_level IN ('read', 'write', 'admin')
            AND (uda.expires_at IS NULL OR uda.expires_at > NOW())
        )
    )
);

-- Create policy for INSERT: Only super users and dept heads can insert content
CREATE POLICY dept_content_insert_policy ON enterprise.department_content
FOR INSERT
WITH CHECK (
    -- Must match user's tenant
    tenant_id::text = current_setting('app.tenant_id', true)
    AND
    (
        -- Super users can insert anywhere
        EXISTS (
            SELECT 1 FROM enterprise.users u
            WHERE u.id::text = current_setting('app.user_id', true)
            AND u.tenant_id = department_content.tenant_id
            AND u.role IN ('super_user', 'dept_head')
        )
        OR
        -- Dept heads can insert in their departments
        EXISTS (
            SELECT 1 FROM enterprise.user_department_access uda
            WHERE uda.user_id::text = current_setting('app.user_id', true)
            AND uda.department_id = department_content.department_id
            AND uda.access_level IN ('write', 'admin')
            AND uda.is_dept_head = TRUE
        )
    )
);

-- Create policy for UPDATE: Same as INSERT
CREATE POLICY dept_content_update_policy ON enterprise.department_content
FOR UPDATE
USING (
    tenant_id::text = current_setting('app.tenant_id', true)
    AND
    (
        EXISTS (
            SELECT 1 FROM enterprise.users u
            WHERE u.id::text = current_setting('app.user_id', true)
            AND u.tenant_id = department_content.tenant_id
            AND u.role IN ('super_user', 'dept_head')
        )
        OR
        EXISTS (
            SELECT 1 FROM enterprise.user_department_access uda
            WHERE uda.user_id::text = current_setting('app.user_id', true)
            AND uda.department_id = department_content.department_id
            AND uda.access_level IN ('write', 'admin')
        )
    )
);

-- Create policy for DELETE: Only super users
CREATE POLICY dept_content_delete_policy ON enterprise.department_content
FOR DELETE
USING (
    tenant_id::text = current_setting('app.tenant_id', true)
    AND
    EXISTS (
        SELECT 1 FROM enterprise.users u
        WHERE u.id::text = current_setting('app.user_id', true)
        AND u.tenant_id = department_content.tenant_id
        AND u.role = 'super_user'
    )
);

-- Grant necessary permissions to application user
GRANT SELECT, INSERT, UPDATE, DELETE ON enterprise.department_content TO enterprise_bot_app;

-- Create helper function to set session context
CREATE OR REPLACE FUNCTION enterprise.set_user_context(p_user_id UUID, p_tenant_id UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.user_id', p_user_id::text, false);
    PERFORM set_config('app.tenant_id', p_tenant_id::text, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Test RLS policies (requires test user setup)
-- Example test script:
-- SELECT enterprise.set_user_context('<user-uuid>', '<tenant-uuid>');
-- SELECT * FROM enterprise.department_content;  -- Should only return authorized rows
-- RESET app.user_id; RESET app.tenant_id;  -- Clear context
```

**Rollback Script:**
```sql
-- Disable RLS
ALTER TABLE enterprise.department_content DISABLE ROW LEVEL SECURITY;

-- Drop policies
DROP POLICY IF EXISTS dept_content_select_policy ON enterprise.department_content;
DROP POLICY IF EXISTS dept_content_insert_policy ON enterprise.department_content;
DROP POLICY IF EXISTS dept_content_update_policy ON enterprise.department_content;
DROP POLICY IF EXISTS dept_content_delete_policy ON enterprise.department_content;

-- Drop helper function
DROP FUNCTION IF EXISTS enterprise.set_user_context(UUID, UUID);
```

### 2.3 Update Backend to Set Session Context

**File:** `postgres_backend.py` (modify)

**Add method to set session context before queries:**
```python
async def set_user_context(self, user_id: str, tenant_id: str):
    """Set PostgreSQL session variables for RLS enforcement."""
    async with self.pool.acquire() as conn:
        await conn.execute("SELECT enterprise.set_user_context($1::uuid, $2::uuid)", user_id, tenant_id)

async def clear_user_context(self, conn):
    """Clear session variables after query."""
    await conn.execute("RESET app.user_id")
    await conn.execute("RESET app.tenant_id")
```

**Modify all query methods to set context:**
```python
async def get_department_content(self, department_id: str, user_id: str, tenant_id: str):
    """Retrieve department content with RLS enforcement."""
    async with self.pool.acquire() as conn:
        # Set session context for RLS
        await conn.execute("SELECT enterprise.set_user_context($1::uuid, $2::uuid)", user_id, tenant_id)

        # Query - RLS policies automatically filter results
        query = """
            SELECT * FROM enterprise.department_content
            WHERE department_id = $1 AND active = TRUE
            ORDER BY created_at DESC
        """
        rows = await conn.fetch(query, department_id)

        # Clear context
        await self.clear_user_context(conn)

        return [dict(row) for row in rows]
```

**Update all FastAPI endpoints:**
```python
from fastapi import Depends
from auth_service import get_current_user, UserContext

@app.get("/api/departments/{dept_id}/content")
async def get_content(dept_id: str, user: UserContext = Depends(get_current_user)):
    # User context already has user_id, tenant_id from auth middleware
    content = await postgres_backend.get_department_content(
        department_id=dept_id,
        user_id=user.user_id,
        tenant_id=user.tenant_id
    )
    return content
```

### 2.4 Testing RLS Policies

**Test Cases:**
1. **User with access:** Can retrieve content for their department ✅
2. **User without access:** Cannot retrieve content for other departments ❌
3. **Super user:** Can retrieve all content for their tenant ✅
4. **Cross-tenant isolation:** User cannot see other tenant's data ❌
5. **Expired access:** User with expired access cannot retrieve content ❌

**Test Script:** `tests/test_rls_policies.py`
```python
import asyncio
import asyncpg
import os

async def test_rls():
    conn = await asyncpg.connect(os.getenv("AZURE_PG_CONNECTION_STRING"))

    # Test user IDs (replace with actual test users)
    SALES_USER_ID = "11111111-1111-1111-1111-111111111111"
    WAREHOUSE_USER_ID = "22222222-2222-2222-2222-222222222222"
    TENANT_ID = "driscoll-tenant-uuid"

    # Test 1: Sales user can see sales content
    await conn.execute("SELECT enterprise.set_user_context($1::uuid, $2::uuid)", SALES_USER_ID, TENANT_ID)
    sales_content = await conn.fetch("SELECT * FROM enterprise.department_content WHERE department_id = (SELECT id FROM enterprise.departments WHERE slug = 'sales')")
    print(f"✅ Sales user sees {len(sales_content)} sales documents")

    # Test 2: Sales user CANNOT see warehouse content
    warehouse_content = await conn.fetch("SELECT * FROM enterprise.department_content WHERE department_id = (SELECT id FROM enterprise.departments WHERE slug = 'warehouse')")
    assert len(warehouse_content) == 0, "❌ FAIL: Sales user can see warehouse content!"
    print("✅ Sales user cannot see warehouse content (as expected)")

    # Clear context
    await conn.execute("RESET app.user_id; RESET app.tenant_id;")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(test_rls())
```

**Success Criteria:**
- ✅ RLS policies enabled without errors
- ✅ All test cases pass
- ✅ `EXPLAIN` query shows RLS policy in plan
- ✅ Performance impact < 10ms per query

---

## **PHASE 2.5: DOCX to JSON Chunking Pipeline**
**Duration:** 3 days | **Dependencies:** None (can run in parallel with Phase 1-2)

---

**Goal:** Convert all 24 warehouse DOCX files into JSON chunk format matching the existing Sales/Purchasing JSON structure, creating a uniform ingestion source.

### 2.5.1 Analyze Existing JSON Structure

**Review existing chunk files to understand target format:**

**File:** `Manuals/Driscoll/Sales/bid_management_chunks.json`
**File:** `Manuals/Driscoll/Sales/sales_support_chunks.json`
**File:** `Manuals/Driscoll/Sales/telnet_sop_chunks.json`
**File:** `Manuals/Driscoll/Purchasing/purchasing_manual_chunks.json`

**Expected JSON Schema:**
```json
{
  "document_title": "Dispatching Manual",
  "department": "Warehouse",
  "chunks": [
    {
      "chunk_id": 1,
      "section_title": "Introduction",
      "content": "This manual covers...",
      "page_number": 1,
      "chunk_type": "section"
    },
    {
      "chunk_id": 2,
      "section_title": "Daily Checklist",
      "content": "1. Review dispatch queue...",
      "page_number": 3,
      "chunk_type": "content"
    }
  ],
  "metadata": {
    "source_file": "Dispatching Manual.docx",
    "created_date": "2024-11-10",
    "page_count": 15
  }
}
```

### 2.5.2 Build DOCX to JSON Converter

**File:** `ingestion/docx_to_json_chunks.py`

**Features:**
- Parse DOCX using `python-docx` library
- Extract text by section/heading structure (Heading 1, Heading 2, etc.)
- Preserve formatting metadata (bold, italic, lists)
- Track page numbers (approximate based on paragraph count)
- Generate JSON output matching existing chunk format
- Handle edge cases (no headings, images, tables)

**Core Function:**
```python
import json
from pathlib import Path
from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from datetime import datetime
import hashlib

def docx_to_json_chunks(docx_path: Path, department: str, output_dir: Path):
    """
    Convert DOCX file to JSON chunk format.

    Args:
        docx_path: Path to DOCX file
        department: Department name (Warehouse, Sales, Purchasing)
        output_dir: Directory to save JSON output

    Returns:
        Path to generated JSON file
    """
    doc = Document(docx_path)

    document_title = docx_path.stem  # Filename without extension
    chunks = []
    chunk_id = 0
    current_section = None
    current_content = []
    page_estimate = 1

    for para in doc.paragraphs:
        # Estimate page breaks (rough: ~40 lines per page)
        if len(current_content) > 40:
            page_estimate += 1
            current_content = []

        # Detect headings
        if para.style.name.startswith('Heading'):
            # Save previous section
            if current_section and current_content:
                chunks.append({
                    "chunk_id": chunk_id,
                    "section_title": current_section,
                    "content": "\n".join(current_content),
                    "page_number": page_estimate,
                    "chunk_type": "section"
                })
                chunk_id += 1
                current_content = []

            # Start new section
            current_section = para.text.strip()

        # Accumulate content
        elif para.text.strip():
            current_content.append(para.text.strip())

    # Save final section
    if current_section and current_content:
        chunks.append({
            "chunk_id": chunk_id,
            "section_title": current_section,
            "content": "\n".join(current_content),
            "page_number": page_estimate,
            "chunk_type": "section"
        })

    # If no headings found, treat as single chunk
    if not chunks:
        all_text = "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
        chunks.append({
            "chunk_id": 0,
            "section_title": document_title,
            "content": all_text,
            "page_number": 1,
            "chunk_type": "content"
        })

    # Build output structure
    output = {
        "document_title": document_title,
        "department": department,
        "chunks": chunks,
        "metadata": {
            "source_file": docx_path.name,
            "created_date": datetime.now().isoformat(),
            "page_count": page_estimate,
            "chunk_count": len(chunks),
            "file_hash": hashlib.sha256(docx_path.read_bytes()).hexdigest()
        }
    }

    # Save JSON
    output_file = output_dir / f"{docx_path.stem}_chunks.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"✅ Converted: {docx_path.name} → {output_file.name} ({len(chunks)} chunks)")
    return output_file
```

### 2.5.3 Batch Processing Script

**File:** `ingestion/batch_convert_warehouse_docx.py`

**Features:**
- Process all 24 warehouse DOCX files
- Save JSON outputs to `Manuals/Driscoll/Warehouse/chunks/`
- Progress tracking
- Error handling per file
- Summary report

**Usage:**
```bash
python ingestion/batch_convert_warehouse_docx.py \
  --input-dir ./Manuals/Driscoll/Warehouse \
  --output-dir ./Manuals/Driscoll/Warehouse/chunks \
  --department Warehouse
```

**Expected Output:**
```
DOCX to JSON Chunking Pipeline
================================

Scanning: ./Manuals/Driscoll/Warehouse/
Found 24 DOCX files.

Processing files...
✅ Converted: Dispatching Manual.docx → Dispatching Manual_chunks.json (8 chunks)
✅ Converted: Driver Check-in Manual.docx → Driver Check-in Manual_chunks.json (5 chunks)
✅ Converted: driver manual.docx → driver manual_chunks.json (12 chunks)
... [21 more files]

SUMMARY:
  Total files processed: 24
  Successful conversions: 24
  Errors: 0
  Total chunks created: 287
  Average chunks per file: 11.96
  Time taken: 1m 23s

Output directory: ./Manuals/Driscoll/Warehouse/chunks/
```

### 2.5.4 Validation & Quality Check

**File:** `ingestion/validate_json_chunks.py`

**Checks:**
- All JSON files are valid JSON
- Required fields present (document_title, department, chunks, metadata)
- No duplicate chunk_ids within a file
- Content is not empty
- File hashes are unique (no duplicates)

**Usage:**
```bash
python ingestion/validate_json_chunks.py \
  --json-dir ./Manuals/Driscoll/Warehouse/chunks \
  --department Warehouse
```

**Expected Output:**
```
Validating JSON chunks...
  ✅ Dispatching Manual_chunks.json (8 chunks)
  ✅ Driver Check-in Manual_chunks.json (5 chunks)
  ✅ driver manual_chunks.json (12 chunks)
  ... [21 more files]

VALIDATION SUMMARY:
  Total files validated: 24
  Valid files: 24
  Invalid files: 0
  Total chunks: 287
  Unique file hashes: 24

✅ All validations passed!
```

### 2.5.5 Manual Review Checklist

Before proceeding to Phase 3 (ingestion), manually review:
- [ ] Open 3-5 random JSON files and verify content looks correct
- [ ] Check that headings are properly extracted as section_titles
- [ ] Verify page_number estimates are reasonable
- [ ] Confirm no encoding issues (special characters display correctly)
- [ ] Check that file_hash is present in all metadata

**Success Criteria:**
- ✅ All 24 warehouse DOCX files converted to JSON
- ✅ JSON structure matches existing Sales/Purchasing format
- ✅ All validations pass (no errors)
- ✅ Manual review confirms quality
- ✅ Ready for Phase 3 database ingestion

---

## **PHASE 3: Document Ingestion Pipeline**
**Duration:** 4 days | **Dependencies:** Phase 1, Phase 2.5

---

**Goal:** Ingest all 28 JSON chunk files (24 warehouse + 4 existing) into `department_content` table with embeddings and proper metadata.

### 3.1 JSON Chunk Loader

**File:** `ingestion/json_chunk_loader.py`

**Features:**
- Load JSON files from all departments (Warehouse, Sales, Purchasing)
- Parse JSON structure and extract chunks
- Map department slug to department_id from database
- Validate JSON schema
- Handle errors gracefully

**Core Function:**
```python
import json
from pathlib import Path
from typing import List, Dict, Any

def load_json_chunks(json_path: Path, tenant_id: str, department_id: str) -> List[Dict[str, Any]]:
    """
    Load JSON chunk file and prepare for database ingestion.

    Args:
        json_path: Path to JSON chunk file
        tenant_id: Tenant UUID
        department_id: Department UUID

    Returns:
        List of chunk dictionaries ready for ingestion
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    document_title = data.get("document_title")
    department = data.get("department")
    chunks_raw = data.get("chunks", [])
    metadata = data.get("metadata", {})

    # Create document root
    root_chunk = {
        "tenant_id": tenant_id,
        "department_id": department_id,
        "content_type": "manual",
        "title": document_title,
        "content": f"Document: {document_title}",  # Root content
        "version": 1,
        "active": True,
        "is_document_root": True,
        "parent_document_id": None,
        "chunk_index": 0,
        "chunk_type": "metadata",
        "source_file": metadata.get("source_file", json_path.name),
        "file_hash": metadata.get("file_hash"),
        "metadata": json.dumps(metadata)
    }

    # Prepare chunks for ingestion
    ingestion_chunks = [root_chunk]

    for chunk_data in chunks_raw:
        chunk = {
            "tenant_id": tenant_id,
            "department_id": department_id,
            "content_type": "manual",
            "title": document_title,
            "content": chunk_data.get("content"),
            "version": 1,
            "active": True,
            "is_document_root": False,
            "parent_document_id": None,  # Will be set after root insertion
            "chunk_index": chunk_data.get("chunk_id", 0),
            "chunk_type": chunk_data.get("chunk_type", "content"),
            "section_title": chunk_data.get("section_title"),
            "page_number": chunk_data.get("page_number"),
            "source_file": metadata.get("source_file", json_path.name),
            "file_hash": metadata.get("file_hash"),
            "metadata": json.dumps({**metadata, "original_chunk_id": chunk_data.get("chunk_id")})
        }
        ingestion_chunks.append(chunk)

    return ingestion_chunks
```

### 3.2 Embedding Generation with DeepInfra

**Model:** BGE-M3 (1024-dim embeddings) via DeepInfra API

**Process:**
1. Use existing `embedder.py` with DeepInfra provider
2. Generate embeddings for each chunk's `content` field in batches
3. Store embeddings in `embedding` column (VECTOR(1024))
4. Leverage existing caching to avoid re-embedding

**Integration:**
```python
import sys
sys.path.append('..')  # Access embedder.py from parent dir
from embedder import AsyncEmbedder

# Initialize embedder with DeepInfra
embedder = AsyncEmbedder(
    provider="deepinfra",
    api_key=os.getenv("DEEPINFRA_API_KEY"),
    requests_per_minute=180  # Rate limit
)

# Batch embed all chunks
texts = [chunk["content"] for chunk in chunks]
embeddings = await embedder.embed_batch(
    texts,
    batch_size=32,
    max_concurrent=8,
    show_progress=True
)

# Assign embeddings back to chunks
for chunk, embedding in zip(chunks, embeddings):
    chunk["embedding"] = embedding.tolist()
```

### 3.3 Database Ingestion Script

**File:** `ingestion/ingest_driscoll_manuals.py`

**Features:**
- Parse all DOCX files in `/Manuals/Driscoll/`
- Map filename to department (Warehouse, Sales, Purchasing)
- Chunk documents with semantic preservation
- Generate embeddings for all chunks
- Insert into `department_content` with proper parent-child relationships
- Handle deduplication (skip files with same `file_hash`)
- Progress tracking and error handling

**Usage:**
```bash
python ingestion/ingest_driscoll_manuals.py \
  --tenant-id <driscoll-tenant-uuid> \
  --manuals-dir ./Manuals/Driscoll/ \
  --batch-size 32 \
  --dry-run  # Preview without inserting
```

**Output:**
```
Loading embedding model: BAAI/bge-m3...
Model loaded successfully.

Scanning: ./Manuals/Driscoll/Warehouse/
Found 24 DOCX files.

Processing: Dispatching Manual.docx
  - Department: Warehouse
  - File hash: a1b2c3d4...
  - Sections: 8
  - Chunks: 12 (1 root + 11 content chunks)
  - Embeddings generated: 12
  - Inserted: 12 rows

Processing: Driver Check-in Manual.docx
  - Department: Warehouse
  - File hash: b2c3d4e5...
  - Sections: 5
  - Chunks: 7 (1 root + 6 content chunks)
  - Embeddings generated: 7
  - Inserted: 7 rows

... [22 more files]

SUMMARY:
  Total files processed: 24
  Total chunks created: 287
  Total embeddings generated: 287
  Total rows inserted: 287
  Errors: 0
  Time taken: 3m 45s
```

### 3.5 Handle Existing JSON Chunks

**Files:**
- `Manuals/Driscoll/Sales/bid_management_chunks.json`
- `Manuals/Driscoll/Sales/sales_support_chunks.json`
- `Manuals/Driscoll/Sales/telnet_sop_chunks.json`
- `Manuals/Driscoll/Purchasing/purchasing_manual_chunks.json`

**Approach:**
1. Load JSON files
2. Parse structure (may already be chunked)
3. Generate embeddings for each chunk
4. Insert with appropriate metadata
5. Mark as `chunk_type='pre_chunked'` to indicate different source

**Script:** `ingestion/ingest_json_chunks.py`

```bash
python ingestion/ingest_json_chunks.py \
  --tenant-id <driscoll-tenant-uuid> \
  --json-files ./Manuals/Driscoll/Sales/*.json ./Manuals/Driscoll/Purchasing/*.json
```

**Success Criteria:**
- ✅ All 24 DOCX files parsed successfully
- ✅ All 4 JSON files ingested successfully
- ✅ 287+ chunks created with embeddings
- ✅ Parent-child relationships validated
- ✅ No duplicate `file_hash` entries
- ✅ All chunks have `tenant_id` and `department_id`

---

## **PHASE 4: Retrieval Enhancement**

**Goal:** Update CogTwin retrieval system to query PostgreSQL with RLS enforcement and use vector similarity search on `department_content` table.

### 4.1 Update Retrieval Service

**File:** `tenant_service.py` (modify)

**Current Method:**
```python
def get_department_content(tenant_id, department_id):
    # Application-level filtering
    query = "SELECT * FROM department_content WHERE department_id = $1"
    return db.execute(query, department_id)
```

**New Method with RLS:**
```python
async def get_department_content_with_rls(tenant_id: str, department_id: str, user_id: str):
    """Retrieve department content with RLS enforcement."""
    async with postgres_backend.pool.acquire() as conn:
        # Set session context for RLS
        await conn.execute("SELECT enterprise.set_user_context($1::uuid, $2::uuid)", user_id, tenant_id)

        # Query with RLS filtering
        query = """
            SELECT id, title, content, section_title, page_number,
                   chunk_type, metadata, access_count, created_at
            FROM enterprise.department_content
            WHERE department_id = $1
            AND active = TRUE
            AND is_document_root = FALSE  -- Exclude root metadata rows
            ORDER BY chunk_index
        """
        rows = await conn.fetch(query, department_id)

        # Clear context
        await conn.execute("RESET app.user_id; RESET app.tenant_id;")

        return [dict(row) for row in rows]
```

### 4.2 Vector Similarity Search

**New Method:**
```python
async def vector_search_department_content(
    query_embedding: list,
    user_id: str,
    tenant_id: str,
    department_ids: list = None,  # Optional: restrict to specific departments
    top_k: int = 10,
    min_similarity: float = 0.7
):
    """Perform vector similarity search with RLS enforcement."""
    async with postgres_backend.pool.acquire() as conn:
        # Set session context
        await conn.execute("SELECT enterprise.set_user_context($1::uuid, $2::uuid)", user_id, tenant_id)

        # Build query
        if department_ids:
            dept_filter = "AND department_id = ANY($4)"
            params = [query_embedding, min_similarity, top_k, department_ids]
        else:
            dept_filter = ""
            params = [query_embedding, min_similarity, top_k]

        query = f"""
            SELECT
                id, title, content, section_title, page_number,
                department_id, chunk_type, metadata,
                1 - (embedding <=> $1::vector) / 2 AS similarity
            FROM enterprise.department_content
            WHERE active = TRUE
            AND is_document_root = FALSE
            AND 1 - (embedding <=> $1::vector) / 2 >= $2
            {dept_filter}
            ORDER BY embedding <=> $1::vector
            LIMIT $3
        """

        # RLS policies automatically filter by user's department access
        rows = await conn.fetch(query, *params)

        # Clear context
        await conn.execute("RESET app.user_id; RESET app.tenant_id;")

        return [dict(row) for row in rows]
```

### 4.3 Integrate with CogTwin Engine

**File:** `cog_twin.py` (modify)

**Update `think()` method to use vector search:**
```python
async def think(self, user_input: str, user_id: str, tenant_id: str, department_ids: list = None):
    """Generate response with department-scoped manual retrieval."""

    # Generate query embedding
    query_embedding = self.embedding_service.generate_embedding(user_input)

    # Retrieve relevant manual chunks (RLS-enforced)
    manual_chunks = await vector_search_department_content(
        query_embedding=query_embedding,
        user_id=user_id,
        tenant_id=tenant_id,
        department_ids=department_ids,
        top_k=5,
        min_similarity=0.7
    )

    # Also retrieve user's conversation memories
    memory_chunks = await self.retriever.retrieve(
        query_embedding=query_embedding,
        user_id=user_id,
        tenant_id=tenant_id,
        top_k=10
    )

    # Build context from both sources
    context = self._build_context(manual_chunks, memory_chunks)

    # Generate response
    response = await self.llm.generate(
        prompt=user_input,
        context=context,
        system_prompt="You are an enterprise assistant. Answer using process manuals and conversation history."
    )

    return response
```

**Success Criteria:**
- ✅ Vector search returns relevant chunks from user's departments only
- ✅ RLS policies prevent cross-department leakage
- ✅ Response quality improves with manual context
- ✅ Search latency < 50ms for 1000+ chunks

---

## **PHASE 5: Multi-Tenant Architecture Lock**
**Duration:** 2 days | **Dependencies:** Phase 1-4

---

**Goal:** Finalize and document the schema as the locked architecture for all future tenants.

### 5.1 Tenant Provisioning Workflow

**New Tenant Onboarding:**
```
1. Create tenant record in `tenants` table
2. Map Azure AD tenant ID to application tenant_id
3. Create default departments for tenant (or copy from template)
4. Provision first super user (tenant admin) via admin portal
5. Ingest tenant's process manuals
6. Test RLS policies
7. Go live
```

**File:** `tenant_provisioning.py`

```python
async def provision_new_tenant(
    name: str,
    azure_tenant_id: str,
    admin_email: str,
    default_departments: list = ["warehouse", "sales", "purchasing", "transportation", "executive"]
):
    """Provision a new tenant with default departments and admin user."""

    # 1. Create tenant
    tenant_id = await db.fetchval("""
        INSERT INTO tenants (name, azure_tenant_id, voice_engine, config)
        VALUES ($1, $2, 'enterprise', '{}')
        RETURNING id
    """, name, azure_tenant_id)

    # 2. Create departments
    for dept_slug in default_departments:
        await db.execute("""
            INSERT INTO enterprise.departments (tenant_id, name, slug)
            VALUES ($1, $2, $3)
        """, tenant_id, dept_slug.title(), dept_slug)

    # 3. Provision admin user
    admin_user_id = await db.fetchval("""
        INSERT INTO enterprise.users (tenant_id, email, role, auth_provider)
        VALUES ($1, $2, 'super_user', 'azure_ad')
        RETURNING id
    """, tenant_id, admin_email)

    print(f"✅ Tenant '{name}' provisioned with ID: {tenant_id}")
    print(f"✅ Admin user '{admin_email}' created with ID: {admin_user_id}")
    print(f"✅ {len(default_departments)} departments created")

    return tenant_id
```

### 5.2 Schema Lock Documentation

**File:** `docs/SCHEMA_LOCK_V1.md`

**Contents:**
- Complete ERD (Entity Relationship Diagram)
- Table definitions with all columns
- RLS policy definitions
- Index strategy
- Foreign key constraints
- Check constraints
- Migration history (migrations 001-003)
- Version: 1.0.0
- Lock Date: [Phase 5 completion date]

**Lock Commitment:**
Once locked, any changes to these tables require:
1. New migration file with version bump
2. Approval from architecture team
3. Backward compatibility guarantee
4. Rollback script
5. Update to SCHEMA_LOCK documentation

### 5.3 Validation Checklist

Before locking schema:
- [ ] All 28 JSON chunk files ingested successfully (24 warehouse + 4 existing)
- [ ] RLS policies tested with 10+ test cases
- [ ] Vector search returns correct results
- [ ] Cross-tenant isolation verified (Tenant 1 cannot see Tenant 2 data)
- [ ] Admin portal can manage users and department access
- [ ] Azure AD SSO works end-to-end
- [ ] Manual department assignment works via admin portal
- [ ] Audit log captures all access changes
- [ ] Performance benchmarks pass (< 50ms vector search, < 10ms RLS overhead)
- [ ] Documentation complete (README, API docs, admin guide)

**Success Criteria:**
- ✅ Driscoll tenant fully operational
- ✅ Schema documented and locked
- ✅ Second tenant can be onboarded using same schema
- ✅ Zero schema changes required for new tenants

---

## Implementation Timeline ✅ UPDATED

| Phase | Duration | Dependencies | Deliverables |
|-------|----------|--------------|--------------|
| **Phase 1: Schema Enhancement** | 2 days | None | Migration 002, indexes created, rollback tested |
| **Phase 2: RLS Implementation** | 3 days | Phase 1 | Migration 003, RLS policies, backend integration, test suite |
| **Phase 2.5: DOCX to JSON Chunking** | 3 days | None (parallel) | 24 warehouse DOCX → JSON, validation scripts, 287+ chunks ready |
| **Phase 3: Document Ingestion** | 4 days | Phase 1, 2.5 | JSON loader, DeepInfra embedder integration, 28 files → PostgreSQL |
| **Phase 4: Retrieval Enhancement** | 3 days | Phase 2, 3 | Vector search with RLS, CogTwin integration, testing |
| **Phase 5: Schema Lock** | 2 days | Phase 1-4 | SCHEMA_LOCK_V1.md, validation, provisioning scripts |
| **TOTAL** | **17 days** | Sequential + Phase 2.5 parallel | Driscoll tenant operational, schema locked |

**Notes:**
- Phase 2.5 (DOCX to JSON) can run in parallel with Phase 1-2 to save time
- **Azure AD auto-assignment (original Phase 5) REMOVED** - manual assignment via admin portal only
- Total duration remains 17 days with parallel execution optimization

---

## Risk Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **RLS performance overhead** | High | Medium | Benchmark early, optimize indexes, use connection pooling |
| **DOCX parsing errors** | Medium | High | Try-catch per file, manual review for failures, fallback to plain text |
| **Azure AD group claims not included in tokens** | High | Low | Configure app registration early, test with dummy accounts |
| **Duplicate file hashes** | Low | Low | Use `ON CONFLICT DO NOTHING`, log duplicates for review |
| **Vector search returns irrelevant results** | Medium | Medium | Tune `min_similarity` threshold, improve chunking strategy |
| **Cross-tenant data leakage** | Critical | Low | Comprehensive RLS test suite, security audit before Phase 6 lock |

---

## Rollback Plan

If critical issues arise after deployment:

### Phase 1 Rollback
```sql
-- Run: db/migrations/002_enhance_department_content_ROLLBACK.sql
-- Drops all new columns and indexes
-- Existing data in `content` and `title` columns preserved
```

### Phase 2 Rollback
```sql
-- Run: db/migrations/003_enable_rls_policies_ROLLBACK.sql
-- Disables RLS, drops policies
-- Application continues with existing app-level filtering
```

### Phase 3 Rollback
```sql
-- Delete all ingested chunks
DELETE FROM enterprise.department_content
WHERE source_file IS NOT NULL  -- Only delete ingested files
AND tenant_id = 'driscoll-tenant-uuid';
```

### Full Rollback
- Restore database snapshot from before Phase 1
- Revert code to previous commit
- All manual files remain in `/Manuals/Driscoll/` (unchanged)

---

## Success Metrics

### Technical Metrics
- **RLS Enforcement:** 100% of queries filtered by user's department access
- **Vector Search Recall:** > 90% for test queries
- **Search Latency:** < 50ms for top-10 results
- **Ingestion Accuracy:** > 95% of chunks parsed correctly
- **Zero Cross-Tenant Leaks:** 100% isolation verified

### Business Metrics
- **User Satisfaction:** Users can find relevant manuals in < 3 searches
- **Onboarding Speed:** New tenant onboarded in < 1 day
- **Manual Access Accuracy:** 100% of users get correct department access via admin portal

---

## Post-Implementation Tasks

### Phase 7: Monitoring & Optimization (After Schema Lock)
1. Set up Grafana dashboards for vector search performance
2. Create alerts for RLS policy failures
3. Weekly audit log review for suspicious access patterns
4. Monthly review of `access_count` to identify frequently accessed manuals
5. Quarterly review of `min_similarity` threshold based on user feedback

### Phase 8: Advanced Features (Future Enhancements)
1. **Manual Versioning:** Track changes to process manuals over time
2. **Change Notifications:** Alert users when manuals in their department are updated
3. **Search Analytics:** Track which manuals are never accessed (candidates for archival)
4. **Multi-language Support:** Embed manuals in multiple languages
5. **PDF Support:** Extend parser to handle PDF files
6. **Image Search:** Embed images separately for visual search (e.g., "show me the forklift diagram")

---

## Appendix A: File Structure ✅ UPDATED

```
enterprise_bot/
│
├── db/
│   └── migrations/
│       ├── 001_memory_tables.sql                   (Existing - Phase 5 from PHASES_3_4_5_COMPLETE)
│       ├── 002_enhance_department_content.sql      (NEW - Phase 1)
│       ├── 002_enhance_department_content_ROLLBACK.sql
│       ├── 003_enable_rls_policies.sql             (NEW - Phase 2)
│       └── 003_enable_rls_policies_ROLLBACK.sql
│
├── ingestion/
│   ├── docx_to_json_chunks.py                      (NEW - Phase 2.5)
│   ├── batch_convert_warehouse_docx.py             (NEW - Phase 2.5)
│   ├── validate_json_chunks.py                     (NEW - Phase 2.5)
│   ├── json_chunk_loader.py                        (NEW - Phase 3)
│   └── ingest_driscoll_manuals.py                  (NEW - Phase 3)
│
├── tests/
│   ├── test_rls_policies.py                        (NEW - Phase 2)
│   ├── test_vector_search.py                       (NEW - Phase 4)
│   └── test_json_chunk_loader.py                   (NEW - Phase 3)
│
├── docs/
│   ├── PHASES_3_4_5_COMPLETE.md                    (Existing)
│   ├── PROCESS_MANUAL_SCHEMA_LOCK_PLAN.md          (THIS DOCUMENT - ✅ APPROVED)
│   ├── SCHEMA_LOCK_V1.md                           (NEW - Phase 5)
│   └── ADMIN_GUIDE_MANUAL_MANAGEMENT.md            (NEW - Phase 5)
│
├── Manuals/
│   └── Driscoll/
│       ├── Warehouse/                              (24 DOCX files - existing)
│       │   └── chunks/                             (NEW - Phase 2.5 output: 24 JSON files)
│       ├── Sales/                                  (3 JSON files - existing)
│       └── Purchasing/                             (1 JSON file - existing)
│
├── embedder.py                                     (Existing - use for Phase 3)
├── postgres_backend.py                             (Modify - Phase 2, 4)
├── tenant_service.py                               (Modify - Phase 4)
├── cog_twin.py                                     (Modify - Phase 4)
├── tenant_provisioning.py                          (NEW - Phase 5)
└── requirements.txt                                (Update - add python-docx)
```

**Key Changes from Original Plan:**
- **Phase 2.5 added:** DOCX to JSON chunking scripts (3 new files)
- **Phase 5 (Azure AD groups) removed:** No auto-assignment, manual only
- **auth_service.py NOT modified:** No Azure AD group mapping changes needed
- **embedder.py used as-is:** Existing DeepInfra integration, no new embedding_service.py
- **Migration 004 removed:** No azure_group_mappings table needed

---

## Appendix B: SQL Schema Summary (Post-Migration)

### `enterprise.department_content` (Enhanced)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | UUID | NOT NULL | Primary key |
| `tenant_id` | UUID | NULL | Multi-tenant isolation (FK to tenants) |
| `department_id` | UUID | NOT NULL | FK to departments |
| `content_type` | VARCHAR(50) | NULL | 'manual', 'policy', 'sop' |
| `title` | VARCHAR(255) | NOT NULL | Document title |
| `content` | TEXT | NOT NULL | Chunk text content |
| `version` | INTEGER | NULL | Document version |
| `active` | BOOLEAN | NULL | Soft delete flag |
| **`embedding`** | **VECTOR(1024)** | **NULL** | **Vector embedding** |
| **`parent_document_id`** | **UUID** | **NULL** | **FK to parent row (self)** |
| **`chunk_index`** | **INTEGER** | **NULL** | **Order within document** |
| **`is_document_root`** | **BOOLEAN** | **NULL** | **TRUE for parent, FALSE for chunks** |
| **`chunk_type`** | **VARCHAR(50)** | **NULL** | **'title', 'section', 'content'** |
| **`source_file`** | **VARCHAR(255)** | **NULL** | **Original filename** |
| **`file_hash`** | **VARCHAR(64)** | **NULL** | **SHA256 for deduplication** |
| **`page_number`** | **INTEGER** | **NULL** | **Page in original doc** |
| **`section_title`** | **VARCHAR(255)** | **NULL** | **Heading/section name** |
| **`metadata`** | **JSONB** | **NULL** | **Flexible metadata** |
| **`chunk_token_count`** | **INTEGER** | **NULL** | **Token count** |
| **`embedding_model`** | **VARCHAR(100)** | **NULL** | **'bge-m3-v1'** |
| **`access_count`** | **INTEGER** | **NULL** | **Retrieval count** |
| **`last_accessed`** | **TIMESTAMPTZ** | **NULL** | **Last retrieval time** |
| **`relevance_score`** | **FLOAT** | **NULL** | **Optional pre-computed score** |
| `created_at` | TIMESTAMPTZ | NULL | Created timestamp |
| `updated_at` | TIMESTAMPTZ | NULL | Updated timestamp |

### Indexes

1. `idx_dept_content_dept_id` - B-tree on `department_id`
2. `idx_dept_content_active` - B-tree on `active` (WHERE active = TRUE)
3. **`idx_dept_content_tenant_id`** - B-tree on `tenant_id`
4. **`idx_dept_content_parent`** - B-tree on `parent_document_id`
5. **`idx_dept_content_chunk_idx`** - B-tree on `chunk_index`
6. **`idx_dept_content_is_root`** - B-tree on `is_document_root`
7. **`idx_dept_content_file_hash`** - B-tree on `file_hash`
8. **`idx_dept_content_embedding`** - IVFFlat on `embedding` (cosine similarity)
9. **`idx_dept_content_unique_file`** - Unique index on `(tenant_id, department_id, file_hash)`

### Constraints

1. `fk_dept_content_dept` - FK to `enterprise.departments(id)`
2. `fk_dept_content_tenant` - FK to `tenants(id)`
3. **`fk_dept_content_parent`** - FK to `enterprise.department_content(id)` (self-referencing)
4. **`chk_dept_content_chunk_parent`** - CHECK constraint for parent-child consistency
5. **`chk_dept_content_unique_file`** - Unique constraint for deduplication

### RLS Policies

1. **`dept_content_select_policy`** - Users can only SELECT content from their authorized departments
2. **`dept_content_insert_policy`** - Only super users and dept heads can INSERT
3. **`dept_content_update_policy`** - Only super users and dept heads can UPDATE
4. **`dept_content_delete_policy`** - Only super users can DELETE

---

## Appendix C: Dependencies

### Python Packages (Add to `requirements.txt`)

```txt
# Existing
asyncpg>=0.29.0
pgvector>=0.2.5
fastapi>=0.104.0
msal>=1.24.0

# NEW for Phase 3: Document Ingestion
python-docx>=1.1.0          # DOCX parsing
sentence-transformers>=2.2.2 # BGE-M3 embeddings
pypdf>=3.17.0               # PDF support (future)
pillow>=10.1.0              # Image processing (future)
tiktoken>=0.5.1             # Token counting for chunking
```

---

## Appendix D: Testing Checklist

### Phase 1: Schema Enhancement
- [ ] Migration runs without errors
- [ ] All columns added with correct types
- [ ] Indexes created successfully
- [ ] Foreign key constraint works (test with INSERT)
- [ ] Check constraint prevents invalid data
- [ ] Unique constraint prevents duplicate files
- [ ] Rollback script works

### Phase 2: RLS Implementation
- [ ] RLS enabled on `department_content`
- [ ] All 4 policies created
- [ ] User with access can SELECT content ✅
- [ ] User without access cannot SELECT content ❌
- [ ] Super user can see all content ✅
- [ ] Cross-tenant isolation verified ❌
- [ ] Performance impact measured (< 10ms)
- [ ] `EXPLAIN ANALYZE` shows policy in plan

### Phase 3: Document Ingestion
- [ ] DOCX parser extracts sections correctly
- [ ] File hash generation works (SHA256)
- [ ] Chunking preserves section boundaries
- [ ] Embedding generation works (1024-dim)
- [ ] Parent-child relationships inserted correctly
- [ ] Deduplication prevents duplicate files
- [ ] All 24 warehouse DOCX files ingested ✅
- [ ] All 4 JSON files ingested ✅
- [ ] Total chunk count matches expectation (287+)

### Phase 4: Retrieval Enhancement
- [ ] Vector search returns relevant results
- [ ] RLS filtering works during vector search
- [ ] Search latency < 50ms
- [ ] CogTwin integrates manual context correctly
- [ ] Response quality improved vs baseline
- [ ] No cross-department leaks in results

### Phase 5: Azure AD Groups (Optional)
- [ ] Azure group mappings inserted
- [ ] Auto-assignment works on new user login
- [ ] Audit log shows "Auto-assigned" reason
- [ ] Manual overrides still work
- [ ] Multiple groups assign multiple departments

### Phase 6: Schema Lock
- [ ] All previous phases validated ✅
- [ ] Documentation complete (SCHEMA_LOCK_V1.md)
- [ ] Second tenant can be provisioned using same schema
- [ ] Provisioning script works end-to-end
- [ ] Zero schema changes needed for Tenant 2

---

## Appendix E: Next Steps After Plan Approval

1. **Create Git Branch:** `feature/process-manual-schema-lock`
2. **Phase 1 Implementation:** Start with migration 002
3. **Phase 2 Implementation:** Enable RLS and test extensively
4. **Phase 3 Implementation:** Build ingestion pipeline, test with 1 DOCX first
5. **Phase 4 Implementation:** Integrate with CogTwin, validate retrieval quality
6. **Phase 5 Implementation (Optional):** If auto-assignment desired
7. **Phase 6 Implementation:** Lock schema, write docs, provision Tenant 2 as test
8. **Code Review & QA:** Full security audit, performance testing
9. **Production Deployment:** Deploy to Azure, monitor for 1 week
10. **Schema Lock Announcement:** Communicate locked schema to team, freeze table definitions

---

## Implementation Decisions ✅ APPROVED

Based on stakeholder clarifications (December 18, 2024):

1. **Azure AD Groups:** ✅ **MANUAL ASSIGNMENT ONLY** - Azure AD used for authentication only ("opening the door"). Department access granted manually via admin portal by dept heads and super users. **Phase 5 (auto-assignment) REMOVED from this sprint.**

2. **Embedding Model:** ✅ **BGE-M3 (1024-dim) via DeepInfra API** - Confirmed using existing `embedder.py` with DEEPINFRA_API_KEY for GPU-accelerated embedding generation.

3. **Auto-Assignment:** ✅ **DEFERRED** - Not implementing Azure AD group mapping in this sprint. Admin portal handles all user/department assignments manually.

4. **Existing Data Migration:** ✅ **YES - Migrate all files** - Ingest all 4 existing JSON chunk files (Sales: 3, Purchasing: 1) + chunk remaining 24 warehouse DOCX files into JSON format first, then ingest to database.

5. **RLS Approach:** ✅ **PostgreSQL RLS policies** - Implementing database-level Row Level Security for defense-in-depth.

6. **Chunking Strategy:** ✅ **Semantic chunking** - Parse DOCX structure by section/heading, preserve document hierarchy for better retrieval context.

7. **Timeline:** ✅ **17 days acceptable** - No hard deadline pressure, quality over speed.

**PLAN STATUS:** ✅ **APPROVED FOR EXECUTION** - Ready to proceed with Phase 1 implementation.

---

## Conclusion

This plan establishes a **production-ready, multi-tenant architecture** for process manuals with:

✅ **Database-level security** (PostgreSQL RLS policies enforce department isolation)
✅ **Semantic search** (pgvector embeddings via BGE-M3 + DeepInfra API)
✅ **Department-based access control** (users get email from Azure AD → admin assigns departments → RLS enforces)
✅ **Document hierarchy** (parent-child chunk relationships with metadata preservation)
✅ **Locked schema** (foundation for all future tenants, Driscoll = reference implementation)
✅ **Manual workflow** (DOCX → JSON → PostgreSQL with embeddings)

Once executed, Driscoll (Tenant 1) will serve as the **reference implementation** for all subsequent tenant onboarding, ensuring consistency, security, and scalability.

---

## Next Steps - Ready to Execute ✅

**✅ PLAN APPROVED** - Stakeholder clarifications received December 18, 2024:
1. ✅ Manual assignment only (no Azure AD groups)
2. ✅ BGE-M3 via DeepInfra (existing embedder.py)
3. ✅ Chunk all DOCX to JSON first (Phase 2.5)
4. ✅ PostgreSQL RLS policies (Phase 2)
5. ✅ 17-day timeline acceptable

**Immediate Action Items:**
1. Create Git branch: `feature/process-manual-schema-lock`
2. Start Phase 1: Database schema enhancement (Migration 002)
3. Start Phase 2.5 (parallel): DOCX to JSON chunking pipeline
4. Document progress in `/docs/IMPLEMENTATION_LOG.md`

**Contact:** Matt Hartigan (mthartigan@...)
**Collaboration:** Claude Sonnet 4.5

---

**Document Version:** 2.0 ✅ APPROVED
**Last Updated:** December 18, 2024
**Author:** Matt Hartigan + Claude Sonnet 4.5
**Status:** ✅ **READY FOR PHASE 1 EXECUTION**
**Plan File:** `C:\Users\mthar\projects\enterprise_bot\docs\PROCESS_MANUAL_SCHEMA_LOCK_PLAN.md`
