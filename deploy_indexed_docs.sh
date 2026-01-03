#!/bin/bash
# =============================================================================
# Deploy Indexed Docs + SDK Toolkit Changes
# Run from: C:\Users\mthar\projects\enterprise_bot
# =============================================================================

set -e  # Exit on error

echo "=========================================="
echo "STEP 1: Check current branch"
echo "=========================================="
git branch --show-current
git status --short

echo ""
echo "=========================================="
echo "STEP 2: Stage indexed docs file"
echo "=========================================="
# Replace old file with indexed version (assuming you renamed it)
git add docs/driscoll/sales_warehouse.txt
echo "Staged: docs/driscoll/sales_warehouse.txt"

echo ""
echo "=========================================="
echo "STEP 3: Stage SDK toolkit changes"
echo "=========================================="
# Add everything in the sdk toolkit folder (new files, modifications, deletions)
git add claude_sdk_toolkit/
echo "Staged: claude_sdk_toolkit/ (all changes)"

echo ""
echo "=========================================="
echo "STEP 4: Review staged changes"
echo "=========================================="
git status
echo ""
echo "Files to be committed:"
git diff --cached --stat

echo ""
echo "=========================================="
echo "STEP 5: Commit"
echo "=========================================="
git commit -m "feat: add TOC indexing to context stuffing + SDK toolkit updates

Context Stuffing:
- Added 54-section TOC index to sales_warehouse.txt
- Section markers (<!-- SECTION: name -->) for Grok navigation
- ~1,200 token overhead for semantic document map
- Enables faster LLM retrieval without RAG

SDK Toolkit:
- Parallel development work from claude_sdk_toolkit/
- Inclusions, deletions, and cleanup"

echo ""
echo "=========================================="
echo "STEP 6: Push to main"
echo "=========================================="
git push origin main

echo ""
echo "=========================================="
echo "DONE - Railway will auto-deploy from main"
echo "=========================================="
echo "Monitor at: https://railway.app/dashboard"
