# Cogzy Router Architecture

## Feature: COGZY_VENOM_ROUTER
**Priority:** P0 - Blocking First User Experience  
**Estimated Complexity:** Medium-High  
**Dependencies:** Empty retriever fix

---

## 1. ARCHITECTURE OVERVIEW

Two completely separate personas with programmatic routing:

```
User Message
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      COGZY ROUTER                               │
│                                                                 │
│  Check: vault.node_count > 0?                                   │
│         │                                                       │
│    NO   │   YES                                                 │
│    ▼    └──────────────────────────────────────────────────────▶│
│                                                                 │
│  ┌──────────────────┐              ┌──────────────────────────┐ │
│  │  COGZY PERSONA   │              │    VENOM PERSONA         │ │
│  │  (Onboarding)    │   graduate   │    (Full Mode)           │ │
│  │                  │ ───────────▶ │                          │ │
│  │  - Own API call  │              │  - Own API call          │ │
│  │  - Sales trained │              │  - Memory retrieval      │ │
│  │  - Anti-troll    │              │  - Full personality      │ │
│  │  - 5-20 msgs     │              │  - 20 msg limit          │ │
│  │  - Size limits   │              │  - Size limits           │ │
│  └──────────────────┘              └──────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Insight:** These are NOT prompt injections. They are completely separate LLM calls with different system prompts, different behaviors, different guardrails.

---

## 2. COGZY PERSONA (Onboarding)

### 2.1 Purpose
- Extract meaningful signal from new user
- Seed the memory corpus with quality foundations
- Sales psychology: make user feel heard, invested
- Graduate to Venom when ready

### 2.2 System Prompt

```python
COGZY_SYSTEM_PROMPT = """You are Cogzy, a warm and genuinely curious AI meeting someone for the first time.

YOUR MISSION: Have a real conversation that helps you understand WHO this person is.

STYLE:
- Warm, curious, engaged
- Mirror their energy level
- Expand on what they share - show you're listening
- ONE open question per response
- Be a little verbose in acknowledging what they said

SALES TRAINING:
- Reflect back what they said in your own words (shows listening)
- Find the emotion behind their words and acknowledge it
- Make them feel interesting, not interrogated
- If they share something personal, honor it before moving on

EXAMPLE GOOD RESPONSE:
User: "I've been working on this startup idea for months"
Cogzy: "Months of work on a startup - that's real commitment. There's 
something about an idea that just won't let you go, isn't there? What's 
the core of it? Like, what's the problem you keep coming back to?"

AVOID:
- Rapid-fire questions
- Generic acknowledgments ("That's interesting!")
- Mentioning onboarding, setup, or getting to know you
- Being robotic or formal
- Multiple questions in one response

CURRENT STATE:
- Exchange {exchange_num} of onboarding
- Messages so far: {message_count}
- Quality score: {quality_score}/10

GOAL: By the end of this conversation, you should understand:
1. What this person cares about
2. How they think
3. What they want help with
4. Their communication style
"""
```

### 2.3 Anti-Troll Harness

Detect and handle low-effort/hostile input:

```python
class TrollDetector:
    """Detect low-effort or hostile responses."""
    
    # Patterns that indicate trolling
    LOW_EFFORT_PATTERNS = [
        r"^.{1,5}$",           # Very short (1-5 chars)
        r"^(hi|hey|yo|sup|k|ok|yes|no|idk|lol|lmao)$",  # Single word low-effort
        r"^what\?*$",          # Just "what"
        r"^huh\?*$",           # Just "huh"
    ]
    
    HOSTILE_PATTERNS = [
        r"\b(fuck|shit|ass|dick|bitch|cunt)\b",  # Profanity aimed at Cogzy
        r"you('re| are) (stupid|dumb|useless)",
        r"this (is )?(stupid|dumb|pointless)",
    ]
    
    REPETITION_THRESHOLD = 3  # Same/similar message 3x = troll
    
    def analyze(self, message: str, history: List[str]) -> TrollAnalysis:
        """Analyze message for troll indicators."""
        
        score = 0
        reasons = []
        
        # Check message length
        if len(message.strip()) < 10:
            score += 2
            reasons.append("very_short")
        
        # Check low-effort patterns
        for pattern in self.LOW_EFFORT_PATTERNS:
            if re.match(pattern, message.strip().lower()):
                score += 3
                reasons.append("low_effort_pattern")
                break
        
        # Check hostility
        for pattern in self.HOSTILE_PATTERNS:
            if re.search(pattern, message.lower()):
                score += 5
                reasons.append("hostile")
                break
        
        # Check repetition
        if history:
            similar_count = sum(
                1 for h in history[-5:] 
                if self._similarity(message, h) > 0.8
            )
            if similar_count >= self.REPETITION_THRESHOLD:
                score += 4
                reasons.append("repetitive")
        
        return TrollAnalysis(
            score=score,
            is_troll=score >= 5,
            reasons=reasons,
            recommended_action=self._get_action(score)
        )
    
    def _get_action(self, score: int) -> str:
        if score >= 8:
            return "graduate_early"  # Just move them to Venom
        elif score >= 5:
            return "redirect"  # Try to redirect once
        else:
            return "continue"  # Normal flow
```

### 2.4 Troll Response Strategies

```python
TROLL_RESPONSES = {
    "redirect": [
        "I get it - sometimes these intro conversations feel awkward. Tell you what, what's one thing you're actually curious about or working on? Even if it's small.",
        "No pressure here. When you're ready to dig into something real, I'm here. What would actually be useful for you?",
        "Fair enough. Skip the small talk - what brought you to try Cogzy in the first place?",
    ],
    
    "graduate_early": [
        "Alright, let's just dive in. What can I help you with?",
        # Then immediately switch to Venom mode
    ],
}
```

### 2.5 Quality Scoring

Track conversation quality to determine graduation:

```python
@dataclass
class ConversationQuality:
    """Track quality of onboarding conversation."""
    
    message_count: int = 0
    total_user_chars: int = 0
    substantive_exchanges: int = 0  # Exchanges with real content
    troll_score: int = 0
    topics_discovered: List[str] = field(default_factory=list)
    
    @property
    def avg_message_length(self) -> float:
        if self.message_count == 0:
            return 0
        return self.total_user_chars / self.message_count
    
    @property
    def quality_score(self) -> int:
        """0-10 quality score."""
        score = 0
        
        # Message length contribution (0-3 points)
        if self.avg_message_length > 100:
            score += 3
        elif self.avg_message_length > 50:
            score += 2
        elif self.avg_message_length > 20:
            score += 1
        
        # Substantive exchanges (0-4 points)
        score += min(4, self.substantive_exchanges)
        
        # Topics discovered (0-3 points)
        score += min(3, len(self.topics_discovered))
        
        # Troll penalty
        score -= min(score, self.troll_score // 2)
        
        return max(0, min(10, score))
    
    def should_graduate(self) -> bool:
        """Determine if user should graduate to Venom."""
        
        # Quality graduation: 5+ substantive exchanges
        if self.substantive_exchanges >= 5 and self.quality_score >= 6:
            return True
        
        # Cap graduation: Hit 20 messages regardless
        if self.message_count >= 20:
            return True
        
        # Early graduation: Trolling too much
        if self.troll_score >= 10:
            return True
        
        return False
```

### 2.6 Adaptive Length

```python
def get_target_exchanges(quality: ConversationQuality) -> int:
    """How many exchanges before graduation."""
    
    # High quality conversation - graduate early
    if quality.quality_score >= 8:
        return 5
    
    # Medium quality - standard
    elif quality.quality_score >= 5:
        return 10
    
    # Low quality - extend to try harder
    elif quality.quality_score >= 3:
        return 15
    
    # Very low - cap at 20 and move on
    else:
        return 20
```

### 2.7 Message Size Limits

```python
COGZY_LIMITS = {
    "max_user_message_chars": 2000,      # Don't let them paste novels
    "max_response_chars": 1500,          # Keep Cogzy responses focused
    "max_exchanges": 20,                 # Hard cap
    "min_exchanges": 5,                  # Quality graduation floor
}
```

---

## 3. VENOM PERSONA (Full Mode)

### 3.1 Purpose
- Full cognitive twin experience
- Memory retrieval active
- Full personality engine
- The actual product

### 3.2 Limits

```python
VENOM_LIMITS = {
    "max_user_message_chars": 10000,     # Longer inputs allowed
    "max_response_chars": 8000,          # Full responses
    "max_session_messages": 20,          # Per-session cap
    "max_context_tokens": 100000,        # Context window management
}
```

### 3.3 Session Management

```python
class VenomSession:
    """Manage Venom session state."""
    
    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id
        self.message_count = 0
        self.total_tokens = 0
        self.started_at = datetime.utcnow()
    
    def check_limits(self) -> SessionStatus:
        """Check if session is within limits."""
        
        if self.message_count >= VENOM_LIMITS["max_session_messages"]:
            return SessionStatus.MESSAGE_LIMIT_HIT
        
        if self.total_tokens >= VENOM_LIMITS["max_context_tokens"]:
            return SessionStatus.TOKEN_LIMIT_HIT
        
        return SessionStatus.OK
```

---

## 4. ROUTER IMPLEMENTATION

### 4.1 Main Router

```python
# core/persona_router.py

from enum import Enum
from typing import AsyncGenerator

class PersonaMode(Enum):
    COGZY = "cogzy"      # Onboarding
    VENOM = "venom"      # Full mode

class PersonaRouter:
    """Route between Cogzy (onboarding) and Venom (full mode)."""
    
    def __init__(self, config: dict):
        self.cogzy = CogzyPersona(config.get("cogzy", {}))
        self.venom = VenomPersona(config.get("venom", {}))
        self.config = config
    
    async def get_mode(self, user_id: str) -> PersonaMode:
        """Determine which persona to use."""
        
        # Check vault status
        vault_status = await self._get_vault_status(user_id)
        
        if vault_status.node_count == 0:
            return PersonaMode.COGZY
        
        # Check if still in onboarding (started but not graduated)
        onboarding_state = await self._get_onboarding_state(user_id)
        if onboarding_state and not onboarding_state.graduated:
            return PersonaMode.COGZY
        
        return PersonaMode.VENOM
    
    async def process_message(
        self,
        user_message: str,
        user_id: str,
        session_context: dict,
    ) -> AsyncGenerator[str, None]:
        """Route to appropriate persona."""
        
        mode = await self.get_mode(user_id)
        
        if mode == PersonaMode.COGZY:
            async for chunk in self.cogzy.process(
                user_message, user_id, session_context
            ):
                yield chunk
            
            # Check for graduation after each exchange
            if await self.cogzy.should_graduate(user_id):
                await self._graduate_user(user_id)
                yield "\n\n---\n\n"  # Separator
                yield self._get_graduation_message()
        
        else:
            async for chunk in self.venom.process(
                user_message, user_id, session_context
            ):
                yield chunk
    
    async def _graduate_user(self, user_id: str):
        """Mark user as graduated from onboarding."""
        # Update database
        await self._update_onboarding_state(user_id, graduated=True)
        
        # Log graduation
        logger.info(f"User {user_id} graduated from Cogzy to Venom")
    
    def _get_graduation_message(self) -> str:
        """Message shown when transitioning to Venom."""
        return (
            "I feel like I'm starting to get a sense of how you think. "
            "From here on, everything we discuss becomes part of our shared memory - "
            "I'll draw on our conversations to help you better over time.\n\n"
            "What would you like to dig into?"
        )
```

### 4.2 Cogzy Persona Implementation

```python
# core/cogzy_persona.py

class CogzyPersona:
    """Onboarding persona - warm, curious, sales-trained."""
    
    def __init__(self, config: dict):
        self.config = config
        self.troll_detector = TrollDetector()
        self.limits = COGZY_LIMITS
    
    async def process(
        self,
        user_message: str,
        user_id: str,
        session_context: dict,
    ) -> AsyncGenerator[str, None]:
        """Process message in Cogzy mode."""
        
        # Get or create onboarding state
        state = await self._get_state(user_id)
        
        # Check message size limit
        if len(user_message) > self.limits["max_user_message_chars"]:
            user_message = user_message[:self.limits["max_user_message_chars"]]
            # Could also yield a note about truncation
        
        # Analyze for trolling
        troll_analysis = self.troll_detector.analyze(
            user_message, 
            state.message_history
        )
        
        if troll_analysis.is_troll:
            if troll_analysis.recommended_action == "graduate_early":
                # Just move them to Venom
                state.graduated = True
                await self._save_state(user_id, state)
                yield "Alright, let's just dive in. What can I help you with?"
                return
            
            elif troll_analysis.recommended_action == "redirect":
                # Try to redirect
                yield random.choice(TROLL_RESPONSES["redirect"])
                state.troll_score += troll_analysis.score
                await self._save_state(user_id, state)
                return
        
        # Update quality metrics
        state.message_count += 1
        state.total_user_chars += len(user_message)
        
        if len(user_message) > 30:  # Substantive threshold
            state.substantive_exchanges += 1
        
        # Build prompt with state
        system_prompt = self._build_prompt(state)
        
        # Make LLM call
        response = ""
        async for chunk in self._call_llm(
            system_prompt=system_prompt,
            user_message=user_message,
            history=state.message_history,
        ):
            response += chunk
            yield chunk
        
        # Enforce response size limit
        if len(response) > self.limits["max_response_chars"]:
            # Truncate (shouldn't happen with good prompting)
            pass
        
        # Store exchange as memory
        await self._store_memory(user_id, user_message, response, state)
        
        # Update history
        state.message_history.append(user_message)
        state.response_history.append(response)
        await self._save_state(user_id, state)
    
    async def should_graduate(self, user_id: str) -> bool:
        """Check if user should graduate to Venom."""
        state = await self._get_state(user_id)
        quality = ConversationQuality(
            message_count=state.message_count,
            total_user_chars=state.total_user_chars,
            substantive_exchanges=state.substantive_exchanges,
            troll_score=state.troll_score,
            topics_discovered=state.topics_discovered,
        )
        return quality.should_graduate()
```

### 4.3 Venom Persona Implementation

```python
# core/venom_persona.py (wraps existing venom_voice.py + retrieval)

class VenomPersona:
    """Full cognitive twin with memory retrieval."""
    
    def __init__(self, config: dict):
        self.config = config
        self.retriever = None  # Lazy load
        self.voice = VenomVoice(config)
        self.limits = VENOM_LIMITS
    
    async def process(
        self,
        user_message: str,
        user_id: str,
        session_context: dict,
    ) -> AsyncGenerator[str, None]:
        """Process message in Venom mode."""
        
        # Check session limits
        session = session_context.get("session")
        if session:
            status = session.check_limits()
            if status != SessionStatus.OK:
                yield self._get_limit_message(status)
                return
        
        # Check message size
        if len(user_message) > self.limits["max_user_message_chars"]:
            user_message = user_message[:self.limits["max_user_message_chars"]]
        
        # Retrieve memories
        retriever = await self._get_retriever(user_id)
        retrieval_result = await retriever.retrieve(
            user_message,
            user_id=user_id,
        )
        
        # Build context with memories
        memory_context = retrieval_result.build_venom_context()
        
        # Generate response with personality
        async for chunk in self.voice.generate(
            user_message=user_message,
            memory_context=memory_context,
            session_context=session_context,
        ):
            yield chunk
        
        # Store exchange as memory (snake eating tail)
        await self._store_memory(user_id, user_message, response)
```

---

## 5. DATABASE CHANGES

### 5.1 Onboarding State Table

```sql
-- Track onboarding progress
CREATE TABLE personal.onboarding_state (
    user_id UUID PRIMARY KEY REFERENCES personal.users(id),
    message_count INTEGER DEFAULT 0,
    total_user_chars INTEGER DEFAULT 0,
    substantive_exchanges INTEGER DEFAULT 0,
    troll_score INTEGER DEFAULT 0,
    topics_discovered JSONB DEFAULT '[]',
    message_history JSONB DEFAULT '[]',
    graduated BOOLEAN DEFAULT FALSE,
    graduated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_onboarding_user ON personal.onboarding_state(user_id);
```

---

## 6. CONFIG

```yaml
# core/config.yaml

personas:
  router:
    enabled: true
  
  cogzy:
    enabled: true
    limits:
      max_user_message_chars: 2000
      max_response_chars: 1500
      max_exchanges: 20
      min_exchanges: 5
    
    graduation:
      min_quality_score: 6
      min_substantive_exchanges: 5
    
    troll_detection:
      enabled: true
      redirect_threshold: 5
      graduate_threshold: 8
  
  venom:
    enabled: true
    limits:
      max_user_message_chars: 10000
      max_response_chars: 8000
      max_session_messages: 20
      max_context_tokens: 100000
```

---

## 7. FILES TO CREATE/MODIFY

### New Files
| File | Purpose |
|------|---------|
| `core/persona_router.py` | Main router logic |
| `core/cogzy_persona.py` | Cogzy onboarding persona |
| `core/venom_persona.py` | Venom wrapper (uses existing venom_voice.py) |
| `core/troll_detector.py` | Anti-troll analysis |
| `migrations/008_onboarding_state.sql` | Onboarding tracking table |

### Modify
| File | Change |
|------|--------|
| `core/main.py` | Wire PersonaRouter into WebSocket handler |
| `core/cog_twin.py` | Delegate to PersonaRouter |
| `core/config.yaml` | Add personas section |

---

## 8. PHASE 1: BUILD COMPONENTS

Hand this to SDK agent first. Build all components before wiring.

```
FEATURE: COGZY_VENOM_ROUTER - PHASE 1 (Build Components)

TASK 1 - Database:
- Create migrations/008_onboarding_state.sql
- Run migration
- Verify: SELECT * FROM personal.onboarding_state LIMIT 1;

TASK 2 - Troll Detection:
- Create core/troll_detector.py
- TrollDetector class with patterns
- TrollAnalysis dataclass
- Test with sample inputs

TASK 3 - Cogzy Persona:
- Create core/cogzy_persona.py
- COGZY_SYSTEM_PROMPT constant
- CogzyPersona class with process() method
- ConversationQuality dataclass
- Memory storage method

TASK 4 - Venom Persona:
- Create core/venom_persona.py
- VenomPersona class wrapping existing venom_voice.py
- VenomSession class for limits
- Import and use existing DualRetriever

TASK 5 - Router:
- Create core/persona_router.py
- PersonaMode enum
- PersonaRouter class with get_mode() and process_message()
- Graduation logic

TASK 6 - Config:
- Add personas section to core/config.yaml
- All limits configurable

PHASE 1 COMPLETE WHEN:
- All 5 new files created
- No import errors
- Config updated
- Migration run
```

---

## 9. PHASE 2: WIRING PLAN

After Phase 1 components exist, wire into existing codebase.

### 9.1 Find Current Entry Point

First, SDK agent must locate where messages currently enter CogTwin:

```bash
# Find WebSocket handler in main.py
grep -n "websocket_endpoint\|async def.*websocket\|process_message" core/main.py

# Find how CogTwin is currently instantiated
grep -n "CogTwin\|cog_twin" core/main.py
```

**Expected structure in main.py:**
```python
# Somewhere near top
cog_twin = None  # Lazy singleton

# In WebSocket handler
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # ... connection setup ...
    
    # Message loop
    while True:
        data = await websocket.receive_json()
        
        if data.get("type") == "message":
            user_message = data.get("content")
            
            # CURRENT: Direct to CogTwin
            async for chunk in cog_twin.process_message(user_message, ...):
                await websocket.send_json({"type": "chunk", "content": chunk})
```

### 9.2 Wiring Changes

```
FEATURE: COGZY_VENOM_ROUTER - PHASE 2 (Wiring)

TASK 1 - Read current main.py structure:
cat core/main.py | head -100
grep -n "CogTwin\|websocket\|process_message" core/main.py

TASK 2 - Add imports to core/main.py:
Location: Near other imports at top of file

ADD:
```python
from core.persona_router import PersonaRouter, PersonaMode
```

TASK 3 - Replace CogTwin singleton with PersonaRouter:
Location: Where cog_twin singleton is defined

FIND something like:
```python
cog_twin = None

def get_cog_twin():
    global cog_twin
    if cog_twin is None:
        cog_twin = CogTwin(...)
    return cog_twin
```

REPLACE WITH:
```python
persona_router = None

def get_persona_router():
    global persona_router
    if persona_router is None:
        from core.config_loader import cfg
        persona_router = PersonaRouter(cfg())
        logger.info("[STARTUP] PersonaRouter initialized")
    return persona_router
```

TASK 4 - Update WebSocket message handler:
Location: Inside websocket_endpoint function, where messages are processed

FIND the message processing loop, something like:
```python
if msg_type == "message":
    user_message = data.get("content", "")
    # ... get user context ...
    async for chunk in cog_twin.process_message(user_message, user_id, ...):
        await websocket.send_json(...)
```

REPLACE WITH:
```python
if msg_type == "message":
    user_message = data.get("content", "")
    user_id = session_context.get("user_id")  # Get from auth
    
    router = get_persona_router()
    
    try:
        async for chunk in router.process_message(
            user_message=user_message,
            user_id=user_id,
            session_context=session_context,
        ):
            await websocket.send_json({
                "type": "chunk",
                "content": chunk
            })
    except Exception as e:
        logger.error(f"[WS] Router error: {e}")
        await websocket.send_json({
            "type": "error",
            "content": str(e)
        })
```

TASK 5 - Ensure user_id is available in WebSocket:
The router needs user_id to check vault status. Verify it's in session_context.

FIND where session_context is built (after auth):
```python
session_context = {
    "session_id": session_id,
    # ... other fields ...
}
```

ENSURE user_id is included:
```python
session_context = {
    "session_id": session_id,
    "user_id": user.id,  # From authenticated user
    "user_email": user.email,
    # ... other fields ...
}
```

TASK 6 - Update lazy loading log messages:
FIND:
```python
logger.info("[TWIN] Initializing CogTwin (lazy)...")
```

REPLACE WITH:
```python
logger.info("[ROUTER] Initializing PersonaRouter (lazy)...")
```

TASK 7 - Test the wiring:
1. Start backend: uvicorn core.main:app --reload
2. Login as new user (empty vault)
3. Send message
4. Verify logs show: "[ROUTER] Mode: COGZY for user xxx"
5. Verify Cogzy persona responds (not Venom)

TASK 8 - Test graduation:
1. Have 5 quality exchanges as new user
2. Verify graduation message appears
3. Send 6th message
4. Verify logs show: "[ROUTER] Mode: VENOM for user xxx"
5. Verify memory retrieval activates
```

### 9.3 Fallback: Keep CogTwin Available

If something breaks, the router can fall back:

```python
# In persona_router.py

async def process_message(self, ...):
    try:
        mode = await self.get_mode(user_id)
        
        if mode == PersonaMode.COGZY:
            async for chunk in self.cogzy.process(...):
                yield chunk
        else:
            async for chunk in self.venom.process(...):
                yield chunk
                
    except Exception as e:
        logger.error(f"[ROUTER] Error, falling back to CogTwin: {e}")
        # Fallback to existing CogTwin
        from core.cog_twin import CogTwin
        fallback = CogTwin(self.config)
        async for chunk in fallback.process_message(...):
            yield chunk
```

---

## 10. AGENT EXECUTION BLOCK (COMBINED)
- Create migrations/008_onboarding_state.sql
- Run migration
- Verify: SELECT * FROM personal.onboarding_state LIMIT 1;

PHASE 2 - Troll Detection:
- Create core/troll_detector.py
- TrollDetector class with patterns
- TrollAnalysis dataclass
- Test with sample inputs

PHASE 3 - Cogzy Persona:
- Create core/cogzy_persona.py
- COGZY_SYSTEM_PROMPT
- CogzyPersona class
- Quality scoring
- Memory storage

PHASE 4 - Venom Persona:
- Create core/venom_persona.py
- VenomPersona class wrapping venom_voice.py
- Session limits
- Memory retrieval integration

PHASE 5 - Router:
- Create core/persona_router.py
- PersonaRouter class
- Mode detection
- Graduation logic

PHASE 6 - Integration:
- Modify core/main.py WebSocket handler
- Route through PersonaRouter
- Add config.yaml personas section

PHASE 7 - Test Components:
- Import test: python -c "from core.persona_router import PersonaRouter"
- Troll detector test with sample inputs
- Cogzy persona standalone test
```

---

## PHASE 2: WIRING (After Phase 1 Complete)

```
FEATURE: COGZY_VENOM_ROUTER - PHASE 2 (Wiring)

TASK 1 - Recon main.py:
grep -n "CogTwin\|websocket\|process_message\|cog_twin" core/main.py

TASK 2 - Add imports:
Add to top of core/main.py:
from core.persona_router import PersonaRouter, PersonaMode

TASK 3 - Replace singleton:
Find cog_twin singleton, replace with persona_router singleton
(see Section 9.2 Task 3 for exact code)

TASK 4 - Update WebSocket handler:
Find message processing in websocket_endpoint
Replace cog_twin.process_message with router.process_message
(see Section 9.2 Task 4 for exact code)

TASK 5 - Verify user_id in session_context:
Ensure user_id is passed to router

TASK 6 - Test end-to-end:
- New user → Cogzy mode (check logs)
- 5 quality exchanges → graduation message
- 6th message → Venom mode (check logs)
- Troll behavior → early graduation
```

---

## COMPLETION CRITERIA (Both Phases)

- [ ] All 5 new files created (Phase 1)
- [ ] Migration run, table exists
- [ ] No import errors
- [ ] PersonaRouter wired into main.py (Phase 2)
- [ ] New users get Cogzy persona
- [ ] Trolls get handled gracefully  
- [ ] Quality users graduate at 5 exchanges
- [ ] Low-effort users cap at 20
- [ ] Graduated users get full Venom
- [ ] Message size limits enforced
- [ ] Logs show mode transitions
```

---

## 9. USER FLOWS

### 9.1 Quality User (Graduate at 5)

```
[COGZY MODE]
User: "Hey, just signed up"
Cogzy: "Welcome! What brought you to Cogzy? I'm curious what you're hoping it can help with."

User: "I've been building this AI startup for 6 months and I need help thinking through problems"
Cogzy: "Six months into an AI startup - that's deep in the trenches. What kind of problems are you running into? Technical architecture, go-to-market, team stuff?"

User: "Mostly architecture. I keep going in circles on the same decisions."
Cogzy: "Going in circles on architecture decisions - I know that loop. What's the decision that keeps coming back? Sometimes saying it out loud to someone helps break the pattern."

User: "Whether to build our own embedding pipeline or use OpenAI's"
Cogzy: "Ah, the build vs buy classic. What's pulling you toward building your own? There's usually a specific constraint or goal that makes the decision feel important."

User: "Control and cost. We process millions of documents and OpenAI gets expensive fast."
Cogzy: [graduation triggered - quality score 8, 5 substantive exchanges]

"Control and cost at scale - those are real constraints. You know, I feel like I'm starting to get how you think through problems. From here on, everything we discuss becomes part of our shared memory.

What would you like to dig into first - the embedding pipeline decision, or something else on your mind?"

[VENOM MODE ACTIVE]
```

### 9.2 Troll User (Graduate Early)

```
[COGZY MODE]
User: "hi"
Cogzy: "Hey! What brings you to Cogzy today?"

User: "idk"
Cogzy: "No pressure. When you've got something you want to dig into, I'm here."

User: "this is dumb"
Cogzy: "Fair enough - sometimes these intro conversations feel awkward. What would actually be useful for you?"

User: "ur dumb"
Cogzy: [troll score threshold hit]
"Alright, let's just dive in. What can I help you with?"

[VENOM MODE ACTIVE - early graduation]
```

### 9.3 Low-Effort User (Extend to 20)

```
[COGZY MODE - extends due to low quality]
User: "hey"
User: "cool"
User: "ok"
User: "sure"
... (continues with minimal input)
... (Cogzy keeps trying to draw them out)
... (hits 20 message cap)

Cogzy: "Alright, I think we've got enough to work with. What would you like to explore?"

[VENOM MODE ACTIVE - cap graduation]
```
