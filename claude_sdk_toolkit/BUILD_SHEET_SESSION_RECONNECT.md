# Feature Build Sheet: Session Timeout/Reconnect

**Priority:** P2  
**Estimated Effort:** 8-10 hours (Phase 1+2)  
**Dependencies:** None

---

## 1. OVERVIEW

### User Story
> As a user, I want my chat session to survive page reloads and network blips so that I don't lose my conversation context.

### Acceptance Criteria
- [ ] Messages persist across page reload (localStorage)
- [ ] Department selection persists across page reload
- [ ] Connection state indicator shows "Reconnecting..." during blips
- [ ] Stale sessions (>1 hour) are cleaned up
- [ ] (Optional) Server-side session table for cross-device sync

### What Already Works
- ✅ WebSocket auto-reconnect with exponential backoff (websocket.ts)
- ✅ Max 5 reconnect attempts before giving up
- ✅ Ping/pong heartbeat (client-driven)
- ✅ Department switching mid-session

### What's Missing
- ❌ No state persistence (messages lost on reload)
- ❌ No connection state UI feedback
- ❌ No server-side session storage

---

## 2. DATABASE CHANGES (Optional - Phase 2)

### Migration File: `db/migrations/005_websocket_sessions.sql`

```sql
-- Migration 005: WebSocket session state persistence
-- Optional: Only needed for cross-device session sync

CREATE TABLE IF NOT EXISTS enterprise.websocket_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    user_id UUID REFERENCES enterprise.users(id),
    user_email VARCHAR(255) NOT NULL,
    department TEXT NOT NULL,
    state_snapshot JSONB DEFAULT '{}',
    last_heartbeat TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '1 hour'
);

-- Indexes
CREATE INDEX idx_ws_sessions_user ON enterprise.websocket_sessions(user_id);
CREATE INDEX idx_ws_sessions_expires ON enterprise.websocket_sessions(expires_at);
CREATE INDEX idx_ws_sessions_email ON enterprise.websocket_sessions(user_email);

-- Cleanup function (call via pg_cron or background task)
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM enterprise.websocket_sessions
    WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE enterprise.websocket_sessions IS 'WebSocket session state for reconnect - created 2024-12-23';
```

---

## 3. BACKEND CHANGES (Optional - Phase 2)

### New File: `core/session_manager.py`

```python
"""
Session Manager - WebSocket session state persistence.

Enables session restore after page reload or network reconnect.

Version: 1.0.0
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

from psycopg2.extras import RealDictCursor
from auth_service import get_db_connection

logger = logging.getLogger(__name__)

SCHEMA = "enterprise"
SESSION_TTL_HOURS = 1

_session_manager = None


@dataclass
class SessionState:
    """Serializable session state."""
    session_id: str
    user_email: str
    department: str
    messages: List[Dict[str, Any]]
    last_heartbeat: datetime
    created_at: datetime
    
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_email": self.user_email,
            "department": self.department,
            "messages": self.messages,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class SessionManager:
    """
    Manages WebSocket session state persistence.
    
    Uses PostgreSQL for storage. Could be swapped for Redis if needed.
    """
    
    def save_session(
        self,
        session_id: str,
        user_email: str,
        department: str,
        messages: Optional[List[Dict]] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Save or update session state.
        
        Called on:
        - verify (initial connection)
        - set_division (department change)
        - periodically during active chat
        """
        try:
            state_snapshot = json.dumps({
                "messages": messages or [],
                "saved_at": datetime.utcnow().isoformat()
            })
            
            expires_at = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)
            
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                    INSERT INTO {SCHEMA}.websocket_sessions 
                        (session_id, user_id, user_email, department, state_snapshot, 
                         last_heartbeat, expires_at)
                    VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                        department = EXCLUDED.department,
                        state_snapshot = EXCLUDED.state_snapshot,
                        last_heartbeat = NOW(),
                        expires_at = EXCLUDED.expires_at
                """, (
                    session_id,
                    user_id,
                    user_email.lower(),
                    department,
                    state_snapshot,
                    expires_at
                ))
                conn.commit()
                
            logger.debug(f"[Session] Saved state for {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"[Session] Failed to save {session_id}: {e}")
            return False

    def restore_session(self, session_id: str) -> Optional[SessionState]:
        """
        Restore session state if exists and not expired.
        
        Returns None if session not found or expired.
        """
        try:
            with get_db_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute(f"""
                    SELECT session_id, user_email, department, state_snapshot,
                           last_heartbeat, created_at
                    FROM {SCHEMA}.websocket_sessions
                    WHERE session_id = %s AND expires_at > NOW()
                """, (session_id,))
                
                row = cur.fetchone()
                if not row:
                    return None
                
                state_data = row['state_snapshot'] or {}
                if isinstance(state_data, str):
                    state_data = json.loads(state_data)
                
                return SessionState(
                    session_id=row['session_id'],
                    user_email=row['user_email'],
                    department=row['department'],
                    messages=state_data.get('messages', []),
                    last_heartbeat=row['last_heartbeat'],
                    created_at=row['created_at']
                )
                
        except Exception as e:
            logger.error(f"[Session] Failed to restore {session_id}: {e}")
            return None

    def update_heartbeat(self, session_id: str) -> bool:
        """Update last_heartbeat timestamp (call on any WS activity)."""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                    UPDATE {SCHEMA}.websocket_sessions
                    SET last_heartbeat = NOW(),
                        expires_at = NOW() + INTERVAL '{SESSION_TTL_HOURS} hours'
                    WHERE session_id = %s
                """, (session_id,))
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"[Session] Heartbeat update failed: {e}")
            return False

    def delete_session(self, session_id: str) -> bool:
        """Delete session (on intentional disconnect)."""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                    DELETE FROM {SCHEMA}.websocket_sessions
                    WHERE session_id = %s
                """, (session_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[Session] Delete failed: {e}")
            return False

    def cleanup_expired(self) -> int:
        """Remove expired sessions. Call periodically."""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                    DELETE FROM {SCHEMA}.websocket_sessions
                    WHERE expires_at < NOW()
                """)
                count = cur.rowcount
                conn.commit()
                if count > 0:
                    logger.info(f"[Session] Cleaned up {count} expired sessions")
                return count
        except Exception as e:
            logger.error(f"[Session] Cleanup failed: {e}")
            return 0


def get_session_manager() -> SessionManager:
    """Get singleton SessionManager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
```

### File: `main.py` - Optional Backend Integration

Add session save after verify succeeds (around line 757):
```python
# After successful verify, save session state
from core.session_manager import get_session_manager
session_mgr = get_session_manager()
session_mgr.save_session(
    session_id=session_id,
    user_email=user_email,
    department=tenant.department
)
```

---

## 4. FRONTEND CHANGES (Phase 1 - Required)

### File: `src/lib/stores/session.ts`

#### Add Session Persistence Helpers (add after imports, around line 20)

```typescript
// Session state persistence keys
const SESSION_STORAGE_KEY = 'cogtwin_session';
const SESSION_TTL_MS = 60 * 60 * 1000; // 1 hour

interface PersistedSession {
    sessionId: string;
    department: string;
    messages: Message[];
    timestamp: number;
}

function saveSessionToStorage(sessionId: string, department: string, messages: Message[]): void {
    try {
        const data: PersistedSession = {
            sessionId,
            department,
            messages: messages.slice(-50), // Keep last 50 messages only
            timestamp: Date.now()
        };
        localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(data));
    } catch (e) {
        console.warn('[Session] Failed to save to localStorage:', e);
    }
}

function loadSessionFromStorage(sessionId: string): PersistedSession | null {
    try {
        const saved = localStorage.getItem(SESSION_STORAGE_KEY);
        if (!saved) return null;
        
        const data: PersistedSession = JSON.parse(saved);
        
        // Check if same session and not stale
        if (data.sessionId !== sessionId) {
            console.log('[Session] Different session ID, clearing storage');
            localStorage.removeItem(SESSION_STORAGE_KEY);
            return null;
        }
        
        if (Date.now() - data.timestamp > SESSION_TTL_MS) {
            console.log('[Session] Session expired, clearing storage');
            localStorage.removeItem(SESSION_STORAGE_KEY);
            return null;
        }
        
        return data;
    } catch (e) {
        console.warn('[Session] Failed to load from localStorage:', e);
        return null;
    }
}

function clearSessionStorage(): void {
    localStorage.removeItem(SESSION_STORAGE_KEY);
}
```

#### Add Connection State to Store (add to store state interface)

```typescript
// Add to SessionState interface (around line 57-66)
interface SessionState {
    // ... existing fields ...
    connectionState: 'connecting' | 'connected' | 'reconnecting' | 'disconnected';
    reconnectAttempts: number;
}

// Update initial state
const initialState: SessionState = {
    // ... existing fields ...
    connectionState: 'disconnected',
    reconnectAttempts: 0
};
```

#### Modify init() Function (around line 211)

```typescript
async function init(sessionId: string, department: string): Promise<void> {
    // Try to restore from localStorage first
    const saved = loadSessionFromStorage(sessionId);
    if (saved) {
        console.log(`[Session] Restoring ${saved.messages.length} messages from localStorage`);
        store.update(s => ({
            ...s,
            messages: saved.messages,
            currentDivision: saved.department
        }));
        // Use saved department if current doesn't match
        if (saved.department && saved.department !== department) {
            department = saved.department;
        }
    }
    
    store.update(s => ({ ...s, connectionState: 'connecting' }));
    
    // ... rest of existing init logic ...
}
```

#### Add Auto-Save on Message Changes

```typescript
// In the message handling section, after adding a message:
function addMessage(message: Message): void {
    store.update(s => {
        const newMessages = [...s.messages, message];
        // Auto-save to localStorage
        if (s.sessionId && s.currentDivision) {
            saveSessionToStorage(s.sessionId, s.currentDivision, newMessages);
        }
        return { ...s, messages: newMessages };
    });
}
```

#### Update Connection State on WebSocket Events

```typescript
// In websocket onopen handler:
store.update(s => ({ ...s, connectionState: 'connected', reconnectAttempts: 0 }));

// In websocket onclose handler (reconnecting):
store.update(s => ({ 
    ...s, 
    connectionState: 'reconnecting',
    reconnectAttempts: s.reconnectAttempts + 1
}));

// In websocket onerror or max retries:
store.update(s => ({ ...s, connectionState: 'disconnected' }));
```

---

### File: `src/lib/components/ConnectionStatus.svelte` (New)

```svelte
<script lang="ts">
    import { session } from '$lib/stores/session';
    
    $: state = $session.connectionState;
    $: attempts = $session.reconnectAttempts;
    $: maxAttempts = 5;
    
    $: statusText = {
        'connecting': 'Connecting...',
        'connected': '',
        'reconnecting': `Reconnecting... (${attempts}/${maxAttempts})`,
        'disconnected': 'Disconnected'
    }[state];
    
    $: statusColor = {
        'connecting': 'text-yellow-400',
        'connected': 'text-green-400',
        'reconnecting': 'text-orange-400',
        'disconnected': 'text-red-400'
    }[state];
</script>

{#if state !== 'connected'}
    <div class="fixed top-0 left-0 right-0 z-50 bg-gray-900/95 border-b border-gray-700 px-4 py-2">
        <div class="flex items-center justify-center gap-2 text-sm {statusColor}">
            {#if state === 'reconnecting'}
                <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
            {/if}
            <span>{statusText}</span>
            {#if state === 'disconnected'}
                <button 
                    class="ml-2 px-2 py-1 bg-cyan-600 hover:bg-cyan-500 rounded text-white text-xs"
                    on:click={() => window.location.reload()}
                >
                    Reload
                </button>
            {/if}
        </div>
    </div>
{/if}
```

---

### File: `src/routes/+layout.svelte` - Wire in ConnectionStatus

```svelte
<script>
    // Add import
    import ConnectionStatus from '$lib/components/ConnectionStatus.svelte';
</script>

<!-- Add at top of template, before other content -->
<ConnectionStatus />

<!-- ... rest of layout ... -->
```

---

## 5. INTEGRATION CHECKLIST

### Phase 1 - Frontend (Required)
- [ ] Add persistence helpers to session.ts
- [ ] Add connectionState to store
- [ ] Modify init() to restore from localStorage
- [ ] Add auto-save on message changes
- [ ] Update connection state on WS events
- [ ] Create ConnectionStatus.svelte component
- [ ] Wire into +layout.svelte
- [ ] Test: reload page, messages persist
- [ ] Test: disconnect network, see "Reconnecting..."
- [ ] Test: reconnect, session continues

### Phase 2 - Backend (Optional)
- [ ] Create migration 005_websocket_sessions.sql
- [ ] Run migration
- [ ] Create core/session_manager.py
- [ ] Add session save in main.py after verify
- [ ] Test: session persists server-side

---

## 6. TESTING SCENARIOS

```
Scenario 1: Page Reload
1. Start chat, send a few messages
2. Reload page (F5)
3. Expected: Messages restored, same department

Scenario 2: Network Blip
1. Start chat
2. Disable network (airplane mode or DevTools)
3. Expected: "Reconnecting..." banner appears
4. Re-enable network
5. Expected: Reconnects, banner disappears

Scenario 3: Session Timeout
1. Start chat
2. Wait >1 hour (or modify SESSION_TTL_MS for testing)
3. Reload page
4. Expected: Session cleared, starts fresh

Scenario 4: Different Session ID
1. Start chat with session ABC
2. Open new tab with session XYZ
3. Expected: Each tab has independent state
```

---

## 7. AGENT EXECUTION BLOCK

```
FEATURE BUILD: Session Reconnect (Phase 1 - Frontend Only)

TASK 1 - Session Store Updates:
File: frontend/src/lib/stores/session.ts

Step 1: Add persistence helpers after imports (saveSessionToStorage, loadSessionFromStorage, clearSessionStorage)

Step 2: Add connectionState and reconnectAttempts to SessionState interface

Step 3: Modify init() to call loadSessionFromStorage first

Step 4: Add auto-save in message handling

Step 5: Update connectionState on WebSocket events

TASK 2 - Connection Status Component:
- Create file: frontend/src/lib/components/ConnectionStatus.svelte
- Wire into: frontend/src/routes/+layout.svelte

TASK 3 - Verification:
- npm run dev
- Open chat, send messages
- Reload page - messages should persist
- Open DevTools Network tab, go offline
- Should see "Reconnecting..." banner
- Go back online - should reconnect

COMPLETION CRITERIA:
- Messages survive page reload
- Connection state banner appears during disconnect
- No console errors
- Session clears after 1 hour
```

---

## 8. ROLLBACK PLAN

```bash
# Frontend rollback
git checkout HEAD -- frontend/src/lib/stores/session.ts
rm frontend/src/lib/components/ConnectionStatus.svelte
# Remove ConnectionStatus import from +layout.svelte

# Backend rollback (if Phase 2 done)
DROP TABLE IF EXISTS enterprise.websocket_sessions;
rm core/session_manager.py
```

---

## Notes

**Why localStorage over sessionStorage?**
- sessionStorage clears on tab close
- localStorage persists across tabs AND page reloads
- We add our own TTL (1 hour) for cleanup

**Why limit to 50 messages?**
- localStorage has ~5MB limit
- 50 messages is plenty for context
- Older messages can be fetched from server if needed

**Phase 2 value:**
- Cross-device session sync (start on desktop, continue on mobile)
- Server-side session analytics
- Admin visibility into active sessions
- Not required for basic reconnect UX
