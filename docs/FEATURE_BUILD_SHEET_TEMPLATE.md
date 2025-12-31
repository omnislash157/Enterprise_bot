# Feature Build Sheet Template

## Feature: [FEATURE_NAME]
**Priority:** P0/P1/P2  
**Estimated Complexity:** Low/Medium/High  
**Dependencies:** [list any features that must exist first]

---

## 1. OVERVIEW

### User Story
> As a [role], I want to [action] so that [benefit].

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

---

## 2. DATABASE CHANGES

### New Tables
```sql
-- Table: enterprise.xxx
CREATE TABLE enterprise.xxx (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ...
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_xxx ON enterprise.xxx(field);
```

### Schema Modifications
```sql
-- Add column to existing table
ALTER TABLE enterprise.users ADD COLUMN new_field TYPE DEFAULT value;
```

### Migration File
```
Path: migrations/00X_feature_name.sql
```

---

## 3. BACKEND CHANGES

### New Files
| File | Purpose |
|------|---------|
| `core/feature_name.py` | Core logic |
| `auth/feature_routes.py` | API endpoints |

### File: core/feature_name.py
```python
"""
Feature Name - Description

Version: 1.0.0
"""

class FeatureClass:
    def __init__(self, config):
        pass
    
    async def method_one(self, param: str) -> dict:
        """Description."""
        pass
```

### File: auth/feature_routes.py (or add to existing)
```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/feature", tags=["feature"])

@router.get("/endpoint")
async def get_endpoint(user = Depends(get_current_user)):
    """Description."""
    return {"data": ...}

@router.post("/endpoint")
async def post_endpoint(payload: PayloadModel, user = Depends(get_current_user)):
    """Description."""
    return {"success": True}
```

### Wire into main.py
```python
# Add import
from auth.feature_routes import router as feature_router

# Add router (near other router registrations)
app.include_router(feature_router)
logger.info("[STARTUP] Feature routes loaded at /api/feature")
```

### WebSocket Changes (if any)
```python
# In websocket_endpoint, add handler:
elif msg_type == "feature_action":
    result = await handle_feature_action(data)
    await websocket.send_json({
        "type": "feature_result",
        "data": result
    })
```

---

## 4. FRONTEND CHANGES

### New Files
| File | Purpose |
|------|---------|
| `src/lib/stores/feature.ts` | State management |
| `src/lib/components/Feature/FeatureComponent.svelte` | UI component |
| `src/routes/feature/+page.svelte` | Route page (if needed) |

### File: src/lib/stores/feature.ts
```typescript
import { writable, derived } from 'svelte/store';

// Types
export interface FeatureItem {
    id: string;
    name: string;
    // ...
}

// State
export const featureItems = writable<FeatureItem[]>([]);
export const featureLoading = writable(false);
export const featureError = writable<string | null>(null);

// Derived
export const featureCount = derived(featureItems, $items => $items.length);

// Actions
export async function loadFeatures(): Promise<void> {
    featureLoading.set(true);
    try {
        const res = await fetch(`${API_URL}/api/feature/endpoint`);
        const data = await res.json();
        featureItems.set(data.items);
    } catch (e) {
        featureError.set(e.message);
    } finally {
        featureLoading.set(false);
    }
}

export async function createFeature(payload: Partial<FeatureItem>): Promise<boolean> {
    // ...
}
```

### File: src/lib/components/Feature/FeatureComponent.svelte
```svelte
<script lang="ts">
    import { featureItems, loadFeatures } from '$lib/stores/feature';
    import { onMount } from 'svelte';
    
    onMount(() => {
        loadFeatures();
    });
</script>

<div class="feature-container">
    {#each $featureItems as item}
        <div class="feature-item">{item.name}</div>
    {/each}
</div>

<style>
    .feature-container {
        /* styles */
    }
</style>
```

### Wire into existing components
```svelte
<!-- In parent component, add: -->
<script>
    import FeatureComponent from '$lib/components/Feature/FeatureComponent.svelte';
</script>

<!-- Add to template: -->
<FeatureComponent />
```

### WebSocket Message Types (if any)
```typescript
// Add to websocket types:
| { type: 'feature_action'; payload: FeaturePayload }
| { type: 'feature_result'; data: FeatureResult }
```

---

## 5. ENVIRONMENT VARIABLES

### Backend (Railway)
```
FEATURE_API_KEY=xxx           # If external service needed
FEATURE_ENABLED=true          # Feature flag
```

### Frontend (Vercel/.env)
```
VITE_FEATURE_ENABLED=true
```

### Config.yaml additions
```yaml
features:
  feature_name:
    enabled: true
    setting_one: value
    setting_two: 100
```

---

## 6. INTEGRATION CHECKLIST

### Backend
- [ ] Database migration created and tested locally
- [ ] Core logic implemented with error handling
- [ ] API routes created with auth guards
- [ ] Routes wired into main.py
- [ ] WebSocket handlers added (if needed)
- [ ] Config.yaml updated
- [ ] Environment variables documented

### Frontend
- [ ] Types defined
- [ ] Store created with actions
- [ ] Component(s) created
- [ ] Wired into parent components
- [ ] WebSocket handlers added (if needed)
- [ ] Environment variables set

### Deployment
- [ ] Railway env vars added
- [ ] Vercel env vars added (if frontend separate)
- [ ] Database migration run on production

---

## 7. TESTING COMMANDS

```bash
# Backend - local test
curl -X GET http://localhost:8000/api/feature/endpoint -H "Authorization: Bearer xxx"

# Backend - production test
curl -X GET https://xxx.railway.app/api/feature/endpoint -H "Authorization: Bearer xxx"

# Database verification
psql -c "SELECT * FROM enterprise.xxx LIMIT 5;"
```

---

## 8. AGENT EXECUTION BLOCK

Copy this entire section to SDK agent:

```
FEATURE BUILD: [FEATURE_NAME]

TASK 1 - Database (if needed):
- Run migration: migrations/00X_feature_name.sql
- Verify: SELECT * FROM enterprise.xxx LIMIT 1;

TASK 2 - Backend:
- Create file: core/feature_name.py [paste code block]
- Create/edit: auth/feature_routes.py [paste code block]
- Edit main.py: Add router import and registration
- Edit config.yaml: Add feature config

TASK 3 - Frontend:
- Create file: src/lib/stores/feature.ts [paste code block]
- Create file: src/lib/components/Feature/FeatureComponent.svelte [paste code block]
- Edit parent component: Wire in FeatureComponent

TASK 4 - Verify:
- Backend: curl test endpoint
- Frontend: Check component renders
- Integration: End-to-end test

COMPLETION CRITERIA:
- All files created
- No TypeScript/Python errors
- Endpoint responds correctly
- UI component visible
```

---

## 9. ROLLBACK PLAN

If something breaks:
```sql
-- Database rollback
DROP TABLE IF EXISTS enterprise.xxx;
ALTER TABLE enterprise.users DROP COLUMN IF EXISTS new_field;
```

```bash
# Git rollback
git revert HEAD~N  # N = number of commits for this feature
```
