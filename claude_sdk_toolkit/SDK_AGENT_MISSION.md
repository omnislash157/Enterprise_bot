# MISSION: Frontend ↔ Backend Integration Audit

## Objective
Deep recon of frontend and backend codebases. Find EVERY integration mismatch. Output a fix plan.

## Your Tools
You have access to: Read, Write, Edit, Bash, Glob, Grep, Task (sub-agents)

## Repositories
- **Backend:** Current directory (`C:\Users\mthar\projects\enterprise_bot`)
- **Frontend:** `C:\Users\mthar\projects\enterprise_bot\frontend` (SvelteKit)

---

## PHASE 1: Backend Audit (10 min)

### 1.1 WebSocket Messages
```bash
grep -n "send_json\|msg_type ==" core/main.py
```
Document every message type: `connected`, `verified`, `error`, `stream_chunk`, `cognitive_state`, `division_changed`

### 1.2 REST Endpoints
```bash
grep -rn "@app\.\|@router\." core/ auth/ --include="*.py"
```

### 1.3 Where division is read
```bash
grep -n "department\|division" core/main.py core/enterprise_twin.py
```

**CRITICAL BUG TO VERIFY:** Line 703 of main.py reads `division` from verify message:
```python
requested_division = data.get("division", "warehouse")
```
But does frontend send it?

---

## PHASE 2: Frontend Audit (10 min)

### 2.1 Find WebSocket code
```bash
find frontend/src -name "*.ts" -o -name "*.svelte" | xargs grep -l "WebSocket\|\.send("
```

### 2.2 Find all message sends
```bash
grep -rn "\.send\|JSON.stringify" frontend/src --include="*.ts" --include="*.svelte"
```

### 2.3 Check verify message
Look for where `type: 'verify'` is sent. Does it include `division`?

### 2.4 Check auth store types
```bash
cat frontend/src/lib/stores/auth.ts
```
Compare User interface against backend's /api/whoami response.

### 2.5 Check admin types
```bash
cat frontend/src/lib/stores/admin.ts
```

---

## PHASE 3: Type Comparison

### Backend expects (from /api/whoami):
```typescript
interface User {
  email: string;
  display_name?: string;
  division: string;
  departments: string[];
  is_super_user: boolean;
  dept_head_for: string[];
  tenant_id: string;
}
```

### Check frontend has ALL these fields.

### WebSocket verified message:
```json
{
  "type": "verified",
  "email": "...",
  "division": "warehouse",
  "departments": ["sales", "purchasing", ...]
}
```

### Check frontend handles `departments` array (not just `division`).

---

## PHASE 4: Known Bugs to Fix

### BUG 1: Division Race Condition (CRITICAL)
**Symptom:** User selects "sales" but RAG queries "warehouse"
**Cause:** Frontend sends `set_division` BEFORE `verify` completes. Then `verify` overwrites.

**Current flow (BROKEN):**
```
FE → set_division(sales)     ← BEFORE AUTH
FE → verify(email)
BE ← division_changed(sales) ← ack
BE ← verified(warehouse)     ← OVERWRITES!
```

**Fix options:**
1. Include `division` in `verify` message (backend supports this!)
2. OR wait for `verified` before sending `set_division`

### BUG 2: Zero-Chunk Hallucination
**Symptom:** RAG returns 0 chunks but Grok invents procedures
**Fix:** Add guardrail to system prompt in enterprise_twin.py

---

## DELIVERABLES

Create a single file `INTEGRATION_FIXES.md` with:

### 1. Mismatch Table
| Location | Backend | Frontend | Fix |
|----------|---------|----------|-----|
| verify message | accepts division field | sends/doesn't send? | Add division to verify |
| User type | has dept_head_for | has/missing? | Add to interface |
| ... | | | |

### 2. Fix Order (with file:line)
1. [ ] Frontend: Add `division` to verify message (file:line)
2. [ ] Frontend: Remove pre-auth set_division (file:line)
3. [ ] Frontend: Add dept_head_for to User type (file:line)
4. [ ] Backend: Add zero-chunk guardrail (enterprise_twin.py:XXX)

### 3. Verification Commands
```bash
# After fixes, test this:
curl -X GET https://xxx.railway.app/api/whoami -H "Authorization: ..."
# Watch Railway logs for: "Filtering by department: sales"
```

---

## EXECUTION

Start with:
```
Read core/main.py lines 690-760 (verify handler)
Read core/main.py lines 853-882 (set_division handler)
Then find frontend WebSocket connection code and trace the flow.
```

**Success = One clear INTEGRATION_FIXES.md with every mismatch and exact fixes.**
