# Cogzy Frontend Pruning Spec

## Feature: COGZY_FRONTEND_PRUNE
**Priority:** P0 - Blocking Ship  
**Estimated Complexity:** Medium  
**Dependencies:** None - cleanup operation

---

## 1. OVERVIEW

### User Story
> As Cogzy personal tier, I need a clean frontend without enterprise/Driscoll cruft so that the codebase is maintainable and the UX is focused on personal memory features.

### Acceptance Criteria
- [ ] All credit-related routes, components, stores removed
- [ ] All admin/analytics/observability routes removed
- [ ] All Azure AD SSO code removed (keep Google OAuth only)
- [ ] All Driscoll-specific branding/references removed
- [ ] No broken imports or dangling references
- [ ] App builds successfully (`npm run build`)
- [ ] App runs successfully (`npm run dev`)
- [ ] Login flow works (Google OAuth + email/password)
- [ ] Chat interface works
- [ ] No TypeScript errors

---

## 2. PHASE 1: DEEP RECON

**CRITICAL: Do NOT delete anything until recon is complete.**

The SDK agent must produce a complete wiring map before any modifications.

### Task 1A: Generate Complete File Tree

```bash
cd frontend_cogzy
find src -type f -name "*.svelte" -o -name "*.ts" -o -name "*.js" | sort > /tmp/all_files.txt
cat /tmp/all_files.txt
```

### Task 1B: Map All Imports Per File

For EVERY file in `src/`, extract:
1. What it imports (from where)
2. What it exports
3. What components it renders (for .svelte files)

```bash
# Generate import map
for f in $(find src -name "*.ts" -o -name "*.svelte"); do
  echo "=== $f ==="
  grep -E "^import |^export " "$f" 2>/dev/null || echo "(no imports/exports)"
  echo ""
done > /tmp/import_map.txt
```

### Task 1C: Identify DELETE Candidates

Files to DELETE (verify existence first):

**Routes to DELETE:**
- `src/routes/credit/` - entire directory
- `src/routes/admin/` - entire directory
- `src/routes/auth/callback/+page.svelte` - Azure SSO callback
- `src/routes/login/+page.svelte` - if redundant (check if Login.svelte handles it)

**Stores to DELETE:**
- `src/lib/stores/admin.ts`
- `src/lib/stores/analytics.ts`
- `src/lib/stores/observability.ts`
- `src/lib/stores/credit.ts`
- `src/lib/stores/tenant.ts` - enterprise tenant switching
- `src/lib/stores/personalAuth.ts` - if consolidated into auth.ts

**Components to DELETE:**
- `src/lib/components/CreditForm.svelte`
- `src/lib/components/EnterpriseLogin.svelte`
- `src/lib/components/admin/` - entire directory
- `src/lib/components/ribbon/` - if Driscoll-branded (inspect first)

### Task 1D: Identify KEEP Files

Files to KEEP (verify they exist and are clean):

**Routes to KEEP:**
- `src/routes/+layout.svelte`
- `src/routes/+page.svelte`
- `src/routes/auth/google/callback/+page.svelte`

**Stores to KEEP:**
- `src/lib/stores/auth.ts` (personal auth with Google + email)
- `src/lib/stores/session.ts`
- `src/lib/stores/websocket.ts`
- `src/lib/stores/voice.ts`
- `src/lib/stores/cheeky.ts`
- `src/lib/stores/theme.ts`

**Components to KEEP:**
- `src/lib/components/Login.svelte`
- `src/lib/components/ChatOverlay.svelte`
- `src/lib/components/ConnectionStatus.svelte`
- `src/lib/components/ToastProvider.svelte`

**Directories to KEEP:**
- `src/lib/threlte/` - 3D scene (Cogzy identity)
- `src/lib/cheeky/` - personality phrases
- `src/lib/utils/`

### Task 1E: Build Dependency Graph

For each DELETE candidate, find all references:

```bash
# For each file to delete, find what imports it
FILE_TO_DELETE="admin.ts"
grep -r "from.*$FILE_TO_DELETE" src/ --include="*.ts" --include="*.svelte"
grep -r "import.*$FILE_TO_DELETE" src/ --include="*.ts" --include="*.svelte"
```

Create a table:

| File to Delete | Imported By | Action Required |
|----------------|-------------|-----------------|
| admin.ts | +layout.svelte | Remove import |
| CreditForm.svelte | credit/+page.svelte | Delete route |
| ... | ... | ... |

### Task 1F: Check for Side Effects

Look for:
1. **onMount calls** that reference deleted stores
2. **WebSocket handlers** that expect deleted message types
3. **Navigation links** pointing to deleted routes
4. **Conditional renders** checking deleted feature flags

```bash
# Find nav links to admin/credit routes
grep -r "href.*admin\|href.*credit" src/ --include="*.svelte"

# Find feature flags
grep -r "hasFeature\|isAdmin\|showCredit\|showAnalytics" src/ --include="*.svelte" --include="*.ts"
```

---

## 3. PHASE 2: RECON OUTPUT DOCUMENT

Create this exact file: `docs/COGZY_FRONTEND_WIRING_MAP.md`

```markdown
# Cogzy Frontend Wiring Map

Generated: [DATE]
Purpose: Dependency map for safe pruning of enterprise features

## File Inventory

### Total Files
- Routes: X files
- Stores: X files  
- Components: X files
- Utils: X files

### DELETE List (with dependencies)

#### Routes to Delete
| Route | Dependencies | Imported By | Safe to Delete |
|-------|--------------|-------------|----------------|
| src/routes/credit/+page.svelte | CreditForm, credit.ts | Nav.svelte | Yes after Nav cleanup |
| src/routes/admin/+page.svelte | admin.ts, analytics.ts | Nav.svelte | Yes after Nav cleanup |
| ... | ... | ... | ... |

#### Stores to Delete
| Store | Exports | Imported By | Safe to Delete |
|-------|---------|-------------|----------------|
| admin.ts | adminUsers, loadAdminData | admin/+page.svelte | Yes after route delete |
| ... | ... | ... | ... |

#### Components to Delete
| Component | Props/Exports | Used By | Safe to Delete |
|-----------|---------------|---------|----------------|
| CreditForm.svelte | onSubmit | credit/+page.svelte | Yes after route delete |
| ... | ... | ... | ... |

### KEEP List (verify clean)

#### Routes to Keep
| Route | Dependencies | Status |
|-------|--------------|--------|
| +page.svelte | ChatOverlay, session.ts | Clean |
| ... | ... | ... |

#### Stores to Keep
| Store | Exports | Used By | Status |
|-------|---------|---------|--------|
| auth.ts | isAuthenticated, login, logout | +layout.svelte, Login.svelte | Clean |
| ... | ... | ... | ... |

### Cleanup Actions Required

#### In +layout.svelte
- [ ] Remove import: admin.ts
- [ ] Remove import: analytics.ts
- [ ] Remove conditional: {#if showAdmin}
- [ ] Remove nav link: /admin

#### In Nav.svelte (or ribbon/)
- [ ] Remove link: /credit
- [ ] Remove link: /admin/*
- [ ] Remove feature checks: hasFeature('analytics')

#### In websocket.ts
- [ ] Remove handler: admin_update (if exists)
- [ ] Remove handler: credit_status (if exists)

### Deletion Order (dependency-safe)

Execute in this order to avoid broken imports:

1. **Leaf routes first** (no other files import these)
   - src/routes/admin/alerts/+page.svelte
   - src/routes/admin/audit/+page.svelte
   - ...

2. **Parent routes** (after children deleted)
   - src/routes/admin/+layout.svelte
   - src/routes/admin/+page.svelte
   - src/routes/credit/+page.svelte

3. **Components** (after routes deleted)
   - src/lib/components/admin/*
   - src/lib/components/CreditForm.svelte

4. **Stores** (after all consumers deleted)
   - src/lib/stores/admin.ts
   - src/lib/stores/analytics.ts
   - src/lib/stores/credit.ts

5. **Cleanup imports** (in remaining files)
   - +layout.svelte
   - Nav.svelte / ribbon components

### Post-Deletion Verification

```bash
# Must pass after all deletions
npm run build
npm run dev

# Check for orphan imports
grep -r "from.*admin" src/
grep -r "from.*credit" src/
grep -r "from.*analytics" src/
grep -r "from.*observability" src/
```
```

---

## 4. PHASE 3: EXECUTE PRUNING

**Only after Phase 2 document is complete and reviewed.**

### Task 3A: Delete Leaf Routes

```bash
# Admin sub-routes (delete children first)
rm -rf src/routes/admin/alerts/
rm -rf src/routes/admin/audit/
rm -rf src/routes/admin/logs/
rm -rf src/routes/admin/queries/
rm -rf src/routes/admin/system/
rm -rf src/routes/admin/traces/
rm -rf src/routes/admin/analytics/
rm -rf src/routes/admin/users/

# Admin parent
rm -rf src/routes/admin/

# Credit
rm -rf src/routes/credit/

# Azure callback (keep Google)
rm -rf src/routes/auth/callback/
```

### Task 3B: Delete Components

```bash
rm -rf src/lib/components/admin/
rm -f src/lib/components/CreditForm.svelte
rm -f src/lib/components/EnterpriseLogin.svelte
```

### Task 3C: Delete Stores

```bash
rm -f src/lib/stores/admin.ts
rm -f src/lib/stores/analytics.ts
rm -f src/lib/stores/observability.ts
rm -f src/lib/stores/credit.ts
rm -f src/lib/stores/tenant.ts
```

### Task 3D: Clean Up Remaining Files

For each file in KEEP list, remove:
- Imports from deleted files
- References to deleted components
- Navigation links to deleted routes
- Feature flag checks for deleted features

**+layout.svelte cleanup pattern:**
```svelte
<!-- REMOVE these imports -->
- import { adminStore } from '$lib/stores/admin';
- import { analyticsStore } from '$lib/stores/analytics';

<!-- REMOVE these conditionals -->
- {#if $isAdmin}
-   <a href="/admin">Admin</a>
- {/if}

<!-- REMOVE these nav items -->
- <a href="/credit">Credit</a>
```

### Task 3E: Verify Build

```bash
cd frontend_cogzy
npm run build 2>&1 | tee /tmp/build_output.txt

# Check for errors
grep -i "error" /tmp/build_output.txt

# If errors, identify broken imports
grep -i "cannot find" /tmp/build_output.txt
grep -i "not found" /tmp/build_output.txt
```

### Task 3F: Verify Runtime

```bash
npm run dev &
sleep 5

# Test endpoints
curl http://localhost:5173/ -s | head -20
curl http://localhost:5173/auth/google/callback -s | head -20

# Kill dev server
pkill -f "vite"
```

---

## 5. PHASE 4: UPDATE DOCUMENTATION

### Task 4A: Update FRONTEND_TREE.md

Replace with new structure:

```markdown
# Frontend - SvelteKit File Tree (Cogzy Personal)

**Last Updated**: [DATE]

Single frontend app for Cogzy personal SaaS tier.

## frontend_cogzy/

```
frontend_cogzy/
|
+-- package.json
+-- svelte.config.js
+-- tailwind.config.js
+-- postcss.config.js
+-- tsconfig.json
|
+-- src/
    +-- app.html
    +-- app.css
    |
    +-- routes/
    |   +-- +layout.svelte             # Root layout (auth check)
    |   +-- +page.svelte               # Home - chat interface
    |   +-- auth/
    |       +-- google/callback/+page.svelte  # Google OAuth callback
    |
    +-- lib/
        +-- stores/
        |   +-- auth.ts                # Google OAuth + email/password
        |   +-- session.ts             # Chat session state
        |   +-- websocket.ts           # WebSocket manager
        |   +-- voice.ts               # Voice mode state
        |   +-- cheeky.ts              # Status phrase rotation
        |   +-- theme.ts               # Theme preferences
        |
        +-- components/
        |   +-- Login.svelte           # Login form (Google + email)
        |   +-- ChatOverlay.svelte     # Main chat interface
        |   +-- ConnectionStatus.svelte # WebSocket status
        |   +-- ToastProvider.svelte   # Toast notifications
        |
        +-- threlte/                   # 3D scene components
        +-- cheeky/                    # Status phrases
        +-- utils/                     # Helper functions
```

## Routing

- `/` - Chat interface (requires auth)
- `/auth/google/callback` - Google OAuth return

## Auth Flow

1. User visits `/`
2. +layout.svelte checks auth state
3. If not authenticated, shows Login.svelte
4. Login offers: Google OAuth (primary) + email/password (toggle)
5. On success, shows ChatOverlay.svelte
```

### Task 4B: Update CHANGELOG.md

Add entry:

```markdown
## [DATE] - Cogzy Frontend Pruning

### Files Deleted
- src/routes/admin/* (entire admin suite - 10 files)
- src/routes/credit/* (credit form route)
- src/routes/auth/callback/* (Azure SSO)
- src/lib/stores/admin.ts, analytics.ts, observability.ts, credit.ts, tenant.ts
- src/lib/components/admin/* (entire admin component suite)
- src/lib/components/CreditForm.svelte, EnterpriseLogin.svelte

### Files Modified
- src/routes/+layout.svelte - Removed admin/credit imports and nav
- [list other modified files]

### Summary
Pruned all enterprise/Driscoll features from frontend_cogzy to create clean personal SaaS tier. Removed: admin dashboard, analytics suite, observability panels, credit form, Azure SSO, tenant switching. Kept: Google OAuth, email/password auth, chat interface, 3D visualizations, voice mode.
```

---

## 6. AGENT EXECUTION BLOCK

Copy this entire block to SDK agent:

```
FEATURE: COGZY_FRONTEND_PRUNE

PHASE 1 - RECON (DO NOT DELETE YET):

TASK 1A: List all files
cd frontend_cogzy && find src -type f \( -name "*.svelte" -o -name "*.ts" \) | sort

TASK 1B: Map imports for each file
for f in $(find src -name "*.ts" -o -name "*.svelte"); do
  echo "=== $f ===" && grep -E "^import |^export " "$f" 2>/dev/null
done

TASK 1C: Find references to DELETE candidates
grep -rn "admin" src/ --include="*.svelte" --include="*.ts"
grep -rn "credit" src/ --include="*.svelte" --include="*.ts"
grep -rn "analytics" src/ --include="*.svelte" --include="*.ts"
grep -rn "observability" src/ --include="*.svelte" --include="*.ts"
grep -rn "tenant" src/ --include="*.svelte" --include="*.ts"
grep -rn "Enterprise" src/ --include="*.svelte" --include="*.ts"
grep -rn "Azure\|azure" src/ --include="*.svelte" --include="*.ts"
grep -rn "Driscoll\|driscoll" src/ --include="*.svelte" --include="*.ts"

TASK 1D: Find nav links
grep -rn "href=" src/ --include="*.svelte" | grep -E "admin|credit|analytics"

TASK 1E: Create docs/COGZY_FRONTEND_WIRING_MAP.md with findings

STOP AND REPORT before Phase 2.

---

PHASE 2 - DELETE (only after recon approved):

[Execute deletion tasks from spec]

PHASE 3 - VERIFY:
npm run build
npm run dev (test manually)

PHASE 4 - DOCUMENT:
Update FRONTEND_TREE.md
Update CHANGELOG.md

COMPLETION CRITERIA:
- Wiring map document created
- All DELETE candidates removed
- No broken imports
- npm run build passes
- npm run dev works
- Login flow works
- Chat works
```

---

## 7. ROLLBACK PLAN

If something breaks badly:

```bash
# Git rollback
git checkout -- src/
git clean -fd src/

# Or selective restore
git checkout HEAD -- src/routes/admin/
```

---

## 8. POST-PRUNE ADDITIONS (Future)

After pruning is complete, these routes can be added for personal tier:

- `src/routes/vault/+page.svelte` - Memory upload UI
- `src/routes/settings/+page.svelte` - User preferences
- `src/routes/memory/+page.svelte` - Simple memory browser (node count, recent uploads)

These are NEW features, not enterprise carryovers.
