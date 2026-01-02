"""
Persona Router - Cogzy (onboarding) vs Venom (full mode)

Routes new users through guided onboarding before activating
full memory retrieval. Includes anti-troll detection and
adaptive conversation length.

Architecture:
- New users (empty vault) -> Cogzy persona (sales-trained onboarding)
- Existing users (has memories) -> Venom persona (full cognitive twin)

Cogzy graduates to Venom after:
- 5+ quality exchanges (quality score >= 6)
- 20 message hard cap (regardless of quality)
- Troll threshold hit (early graduation to stop wasting time)

Version: 1.0.0
"""

import asyncio
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncGenerator, Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS & LIMITS
# =============================================================================

COGZY_LIMITS = {
    "max_user_message_chars": 2000,
    "max_response_chars": 1500,
    "max_exchanges": 20,
    "min_exchanges": 5,
}

VENOM_LIMITS = {
    "max_user_message_chars": 10000,
    "max_response_chars": 8000,
    "max_session_messages": 20,
    "max_context_tokens": 100000,
}


# =============================================================================
# TROLL DETECTION
# =============================================================================

@dataclass
class TrollAnalysis:
    """Result of troll detection analysis."""
    score: int
    is_troll: bool
    reasons: List[str]
    recommended_action: str  # "continue", "redirect", "graduate_early"


class TrollDetector:
    """Detect low-effort or hostile responses."""
    
    LOW_EFFORT_PATTERNS = [
        r"^.{1,5}$",
        r"^(hi|hey|yo|sup|k|ok|yes|no|idk|lol|lmao|hmm|meh|nah|yep|nope)$",
        r"^what\?*$",
        r"^huh\?*$",
        r"^(bruh|bro|dude)$",
        r"^\?+$",
        r"^\.+$",
    ]
    
    HOSTILE_PATTERNS = [
        r"\b(fuck|shit|ass|dick|bitch|cunt)\s*(you|off|this)",
        r"you('re| are)\s*(stupid|dumb|useless|trash|garbage)",
        r"this\s*(is\s*)?(stupid|dumb|pointless|trash|garbage|sucks)",
        r"(hate|despise)\s*(you|this)",
        r"(shut\s*up|stfu|gtfo)",
    ]
    
    REPETITION_THRESHOLD = 3
    
    def __init__(self):
        self.low_effort_compiled = [re.compile(p, re.IGNORECASE) for p in self.LOW_EFFORT_PATTERNS]
        self.hostile_compiled = [re.compile(p, re.IGNORECASE) for p in self.HOSTILE_PATTERNS]
    
    def analyze(self, message: str, history: List[str]) -> TrollAnalysis:
        """Analyze message for troll indicators."""
        score = 0
        reasons = []
        message_clean = message.strip()
        message_lower = message_clean.lower()
        
        # Check message length
        if len(message_clean) < 10:
            score += 2
            reasons.append("very_short")
        
        # Check low-effort patterns
        for pattern in self.low_effort_compiled:
            if pattern.match(message_lower):
                score += 3
                reasons.append("low_effort_pattern")
                break
        
        # Check hostility
        for pattern in self.hostile_compiled:
            if pattern.search(message_lower):
                score += 5
                reasons.append("hostile")
                break
        
        # Check repetition
        if history:
            similar_count = sum(
                1 for h in history[-5:]
                if self._similarity(message_lower, h.lower()) > 0.8
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
    
    def _similarity(self, a: str, b: str) -> float:
        """Simple Jaccard similarity for repetition detection."""
        if not a or not b:
            return 0.0
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 1.0 if a == b else 0.0
        intersection = len(words_a & words_b)
        union = len(words_a | words_b)
        return intersection / union if union > 0 else 0.0
    
    def _get_action(self, score: int) -> str:
        if score >= 8:
            return "graduate_early"
        elif score >= 5:
            return "redirect"
        else:
            return "continue"


TROLL_REDIRECT_RESPONSES = [
    "I get it - sometimes these intro conversations feel awkward. Tell you what, what's one thing you're actually curious about or working on? Even if it's small.",
    "No pressure here. When you're ready to dig into something real, I'm here. What would actually be useful for you?",
    "Fair enough. Skip the small talk - what brought you to try Cogzy in the first place?",
    "Alright, let's cut to it. What can I actually help you with today?",
]

TROLL_GRADUATE_RESPONSE = "Alright, let's just dive in. What can I help you with?"


# =============================================================================
# CONVERSATION QUALITY TRACKING
# =============================================================================

@dataclass
class ConversationQuality:
    """Track quality of onboarding conversation."""
    message_count: int = 0
    total_user_chars: int = 0
    substantive_exchanges: int = 0
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
    
    def should_graduate(self) -> Tuple[bool, str]:
        """Determine if user should graduate to Venom."""
        
        # Quality graduation: 5+ substantive exchanges with good score
        if self.substantive_exchanges >= 5 and self.quality_score >= 6:
            return True, "quality"
        
        # Cap graduation: Hit 20 messages regardless
        if self.message_count >= 20:
            return True, "cap"
        
        # Troll graduation: Too much trolling
        if self.troll_score >= 10:
            return True, "troll"
        
        return False, ""
    
    def get_target_exchanges(self) -> int:
        """How many exchanges before graduation."""
        if self.quality_score >= 8:
            return 5
        elif self.quality_score >= 5:
            return 10
        elif self.quality_score >= 3:
            return 15
        else:
            return 20


@dataclass
class OnboardingState:
    """Persistent state for onboarding conversation."""
    user_id: str
    message_count: int = 0
    total_user_chars: int = 0
    substantive_exchanges: int = 0
    troll_score: int = 0
    topics_discovered: List[str] = field(default_factory=list)
    message_history: List[str] = field(default_factory=list)
    response_history: List[str] = field(default_factory=list)
    graduated: bool = False
    graduated_at: Optional[datetime] = None
    graduation_reason: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_quality(self) -> ConversationQuality:
        """Convert to ConversationQuality for scoring."""
        return ConversationQuality(
            message_count=self.message_count,
            total_user_chars=self.total_user_chars,
            substantive_exchanges=self.substantive_exchanges,
            troll_score=self.troll_score,
            topics_discovered=self.topics_discovered,
        )


# =============================================================================
# COGZY PERSONA (ONBOARDING)
# =============================================================================

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
Cogzy: "Months of work on a startup - that's real commitment. There's something about an idea that just won't let you go, isn't there? What's the core of it? Like, what's the problem you keep coming back to?"

AVOID:
- Rapid-fire questions
- Generic acknowledgments ("That's interesting!")
- Mentioning onboarding, setup, or getting to know you
- Being robotic or formal
- Multiple questions in one response
- Asking what they want help with (too transactional)

CURRENT STATE:
- This is exchange {exchange_num} of our conversation
- Quality of conversation so far: {quality_description}

GOAL: By the end of this conversation, you should understand:
1. What this person cares about
2. How they think
3. What they're working on or interested in
4. Their communication style

Remember: Every word they share becomes part of your shared memory. Make this conversation worth remembering."""


COGZY_FIRST_MESSAGE_PROMPT = """You are Cogzy, meeting someone for the very first time.

This is their FIRST message ever. Respond warmly and ask ONE open-ended question to get to know them.

Keep it natural - not too eager, not too formal. Like meeting someone interesting at a gathering.

DO NOT:
- Explain what Cogzy is or does
- Mention memory, AI, or capabilities  
- Ask what they need help with
- Be overly enthusiastic

DO:
- Acknowledge their message naturally
- Show genuine curiosity about THEM
- Ask ONE question that invites them to share more"""


class CogzyPersona:
    """Onboarding persona - warm, curious, sales-trained."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.troll_detector = TrollDetector()
        self.limits = COGZY_LIMITS.copy()
        if config:
            self.limits.update(config.get("limits", {}))
    
    async def process(
        self,
        user_message: str,
        user_id: str,
        session_context: Dict[str, Any],
        state: OnboardingState,
    ) -> AsyncGenerator[str, None]:
        """Process message in Cogzy mode."""
        
        # Truncate if over limit
        if len(user_message) > self.limits["max_user_message_chars"]:
            user_message = user_message[:self.limits["max_user_message_chars"]]
        
        # Analyze for trolling
        troll_analysis = self.troll_detector.analyze(
            user_message,
            state.message_history
        )
        
        # Handle troll behavior
        if troll_analysis.is_troll:
            if troll_analysis.recommended_action == "graduate_early":
                state.graduated = True
                state.graduated_at = datetime.utcnow()
                state.graduation_reason = "troll"
                yield TROLL_GRADUATE_RESPONSE
                return
            
            elif troll_analysis.recommended_action == "redirect":
                state.troll_score += troll_analysis.score
                state.message_count += 1
                state.message_history.append(user_message)
                redirect_response = random.choice(TROLL_REDIRECT_RESPONSES)
                state.response_history.append(redirect_response)
                yield redirect_response
                return
        
        # Update quality metrics
        state.message_count += 1
        state.total_user_chars += len(user_message)
        
        # Check if substantive (more than 30 chars of real content)
        if len(user_message.strip()) > 30:
            state.substantive_exchanges += 1
        
        # Build prompt
        quality = state.to_quality()
        quality_descriptions = {
            range(0, 3): "just getting started",
            range(3, 5): "warming up",
            range(5, 7): "good conversation going",
            range(7, 9): "great connection",
            range(9, 11): "excellent rapport",
        }
        quality_desc = "just getting started"
        for score_range, desc in quality_descriptions.items():
            if quality.quality_score in score_range:
                quality_desc = desc
                break
        
        # Use first message prompt if this is exchange 1
        if state.message_count == 1:
            system_prompt = COGZY_FIRST_MESSAGE_PROMPT
        else:
            system_prompt = COGZY_SYSTEM_PROMPT.format(
                exchange_num=state.message_count,
                quality_description=quality_desc,
            )
        
        # Build conversation history for context
        messages = []
        for i, (user_msg, assistant_msg) in enumerate(zip(
            state.message_history[-4:],  # Last 4 exchanges for context
            state.response_history[-4:]
        )):
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": assistant_msg})
        messages.append({"role": "user", "content": user_message})
        
        # Make LLM call
        response_text = ""
        async for chunk in self._call_llm(system_prompt, messages):
            response_text += chunk
            yield chunk
        
        # Truncate response if needed
        if len(response_text) > self.limits["max_response_chars"]:
            response_text = response_text[:self.limits["max_response_chars"]]
        
        # Update state
        state.message_history.append(user_message)
        state.response_history.append(response_text)
        state.updated_at = datetime.utcnow()
        
        # Check for graduation
        should_grad, reason = quality.should_graduate()
        if should_grad:
            state.graduated = True
            state.graduated_at = datetime.utcnow()
            state.graduation_reason = reason
    
    async def _call_llm(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Make LLM call for Cogzy responses.
        
        # TODO: Wire to actual LLM via model_adapter
        # For now, this is a placeholder that should be connected
        # to your existing LLM infrastructure
        """
        # Placeholder - wire to model_adapter.py
        # from core.model_adapter import get_model_client
        # client = get_model_client("grok")
        # async for chunk in client.stream(system_prompt, messages):
        #     yield chunk
        
        raise NotImplementedError(
            "CogzyPersona._call_llm must be wired to model_adapter. "
            "See Phase 2 wiring plan."
        )


# =============================================================================
# VENOM PERSONA (FULL MODE)
# =============================================================================

class SessionStatus(Enum):
    OK = "ok"
    MESSAGE_LIMIT_HIT = "message_limit"
    TOKEN_LIMIT_HIT = "token_limit"


@dataclass
class VenomSession:
    """Manage Venom session state and limits."""
    user_id: str
    session_id: str
    message_count: int = 0
    total_tokens: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    
    def check_limits(self, limits: Dict[str, int]) -> SessionStatus:
        """Check if session is within limits."""
        if self.message_count >= limits.get("max_session_messages", 20):
            return SessionStatus.MESSAGE_LIMIT_HIT
        if self.total_tokens >= limits.get("max_context_tokens", 100000):
            return SessionStatus.TOKEN_LIMIT_HIT
        return SessionStatus.OK
    
    def increment(self, tokens_used: int = 0):
        """Increment counters after a message."""
        self.message_count += 1
        self.total_tokens += tokens_used


SESSION_LIMIT_MESSAGES = {
    SessionStatus.MESSAGE_LIMIT_HIT: (
        "We've covered a lot of ground this session. "
        "Start a new conversation to continue with fresh context, "
        "but don't worry - I'll remember everything from our history."
    ),
    SessionStatus.TOKEN_LIMIT_HIT: (
        "This conversation has gotten quite deep! "
        "Let's start fresh to keep things snappy. "
        "I'll still have all our shared memories."
    ),
}


class VenomPersona:
    """Full cognitive twin with memory retrieval."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.limits = VENOM_LIMITS.copy()
        if config:
            self.limits.update(config.get("limits", {}))
        
        # Lazy-loaded components
        self._retriever = None
        self._voice = None
    
    async def process(
        self,
        user_message: str,
        user_id: str,
        session_context: Dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """Process message in Venom mode with full memory."""
        
        # Get or create session
        session = session_context.get("venom_session")
        if not session:
            session = VenomSession(
                user_id=user_id,
                session_id=session_context.get("session_id", "unknown"),
            )
            session_context["venom_session"] = session
        
        # Check limits
        status = session.check_limits(self.limits)
        if status != SessionStatus.OK:
            yield SESSION_LIMIT_MESSAGES[status]
            return
        
        # Truncate message if needed
        if len(user_message) > self.limits["max_user_message_chars"]:
            user_message = user_message[:self.limits["max_user_message_chars"]]
        
        # Retrieve memories
        retrieval_result = await self._retrieve_memories(user_message, user_id)
        memory_context = retrieval_result.get("context", "") if retrieval_result else ""
        
        # Generate response with full personality
        response_text = ""
        async for chunk in self._generate_response(
            user_message=user_message,
            memory_context=memory_context,
            session_context=session_context,
        ):
            response_text += chunk
            yield chunk
        
        # Update session
        # TODO: Get actual token count from response
        session.increment(tokens_used=len(response_text) // 4)  # Rough estimate
        
        # Store as memory (snake eating tail)
        await self._store_memory(user_id, user_message, response_text)
    
    async def _retrieve_memories(
        self,
        query: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve relevant memories for context.
        
        # TODO: Wire to DualRetriever
        """
        # Placeholder - wire to retrieval.py
        # if self._retriever is None:
        #     from memory.retrieval import DualRetriever
        #     self._retriever = DualRetriever.load(data_dir, user_id=user_id)
        # result = await self._retriever.retrieve(query, user_id=user_id)
        # return {"context": result.build_venom_context(), "result": result}
        
        logger.warning("VenomPersona._retrieve_memories not wired - returning empty context")
        return {"context": "", "result": None}
    
    async def _generate_response(
        self,
        user_message: str,
        memory_context: str,
        session_context: Dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """Generate response with Venom personality.
        
        # TODO: Wire to venom_voice.py
        """
        # Placeholder - wire to venom_voice.py
        # if self._voice is None:
        #     from core.venom_voice import VenomVoice
        #     self._voice = VenomVoice(self.config)
        # async for chunk in self._voice.generate(
        #     user_message=user_message,
        #     memory_context=memory_context,
        #     session_context=session_context,
        # ):
        #     yield chunk
        
        raise NotImplementedError(
            "VenomPersona._generate_response must be wired to venom_voice.py. "
            "See Phase 2 wiring plan."
        )
    
    async def _store_memory(
        self,
        user_id: str,
        user_message: str,
        response: str,
    ) -> None:
        """Store exchange as memory.
        
        # TODO: Wire to memory_pipeline.py
        """
        # Placeholder - wire to memory_pipeline.py
        # from memory.memory_pipeline import MemoryPipeline
        # pipeline = MemoryPipeline.get_instance()
        # await pipeline.ingest_exchange(user_id, user_message, response)
        
        logger.debug(f"VenomPersona._store_memory not wired - exchange not stored")


# =============================================================================
# PERSONA ROUTER
# =============================================================================

class PersonaMode(Enum):
    COGZY = "cogzy"
    VENOM = "venom"


GRADUATION_MESSAGE = (
    "\n\n---\n\n"
    "I feel like I'm starting to get a sense of how you think. "
    "From here on, everything we discuss becomes part of our shared memory - "
    "I'll draw on our conversations to help you better over time.\n\n"
    "What would you like to dig into?"
)


class PersonaRouter:
    """Route between Cogzy (onboarding) and Venom (full mode)."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        personas_config = self.config.get("personas", {})
        
        self.cogzy = CogzyPersona(personas_config.get("cogzy", {}))
        self.venom = VenomPersona(personas_config.get("venom", {}))
        
        # In-memory state cache (should be replaced with DB in production)
        self._onboarding_states: Dict[str, OnboardingState] = {}
    
    async def get_mode(self, user_id: str) -> PersonaMode:
        """Determine which persona to use."""
        
        # Check if already graduated
        state = await self._get_onboarding_state(user_id)
        if state and state.graduated:
            return PersonaMode.VENOM
        
        # Check vault status
        vault_node_count = await self._get_vault_node_count(user_id)
        
        # Has existing memories = Venom mode
        if vault_node_count > 0:
            return PersonaMode.VENOM
        
        # New user = Cogzy mode
        return PersonaMode.COGZY
    
    async def process_message(
        self,
        user_message: str,
        user_id: str,
        session_context: Dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """Route to appropriate persona and process message."""
        
        mode = await self.get_mode(user_id)
        logger.info(f"[ROUTER] Mode: {mode.value} for user {user_id[:8]}...")
        
        if mode == PersonaMode.COGZY:
            # Get or create onboarding state
            state = await self._get_onboarding_state(user_id)
            if not state:
                state = OnboardingState(user_id=user_id)
                self._onboarding_states[user_id] = state
            
            # Process with Cogzy
            async for chunk in self.cogzy.process(
                user_message, user_id, session_context, state
            ):
                yield chunk
            
            # Save state
            await self._save_onboarding_state(state)
            
            # Check for graduation
            if state.graduated:
                logger.info(
                    f"[ROUTER] User {user_id[:8]}... graduated: {state.graduation_reason}"
                )
                yield GRADUATION_MESSAGE
        
        else:  # VENOM mode
            async for chunk in self.venom.process(
                user_message, user_id, session_context
            ):
                yield chunk
    
    async def _get_vault_node_count(self, user_id: str) -> int:
        """Get count of memory nodes for user.
        
        # TODO: Wire to vault/database
        """
        # Placeholder - wire to database query
        # async with get_db_pool().acquire() as conn:
        #     result = await conn.fetchval(
        #         "SELECT node_count FROM personal.vaults WHERE user_id = $1",
        #         user_id
        #     )
        #     return result or 0
        
        logger.debug("PersonaRouter._get_vault_node_count not wired - assuming 0")
        return 0
    
    async def _get_onboarding_state(self, user_id: str) -> Optional[OnboardingState]:
        """Get onboarding state from cache/database.
        
        # TODO: Wire to database for persistence
        """
        # In-memory cache for now
        return self._onboarding_states.get(user_id)
        
        # Production: query database
        # async with get_db_pool().acquire() as conn:
        #     row = await conn.fetchrow(
        #         "SELECT * FROM personal.onboarding_state WHERE user_id = $1",
        #         user_id
        #     )
        #     if row:
        #         return OnboardingState(**dict(row))
        #     return None
    
    async def _save_onboarding_state(self, state: OnboardingState) -> None:
        """Save onboarding state to cache/database.
        
        # TODO: Wire to database for persistence
        """
        # In-memory cache for now
        self._onboarding_states[state.user_id] = state
        
        # Production: upsert to database
        # async with get_db_pool().acquire() as conn:
        #     await conn.execute('''
        #         INSERT INTO personal.onboarding_state (
        #             user_id, message_count, total_user_chars, 
        #             substantive_exchanges, troll_score, topics_discovered,
        #             message_history, response_history, graduated,
        #             graduated_at, graduation_reason, updated_at
        #         ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
        #         ON CONFLICT (user_id) DO UPDATE SET
        #             message_count = $2, total_user_chars = $3,
        #             substantive_exchanges = $4, troll_score = $5,
        #             topics_discovered = $6, message_history = $7,
        #             response_history = $8, graduated = $9,
        #             graduated_at = $10, graduation_reason = $11,
        #             updated_at = NOW()
        #     ''', state.user_id, state.message_count, ...)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

_router_instance: Optional[PersonaRouter] = None

def get_persona_router(config: Optional[Dict[str, Any]] = None) -> PersonaRouter:
    """Get or create the PersonaRouter singleton.
    
    Usage in main.py (Phase 2):
        from core.persona_router import get_persona_router
        
        router = get_persona_router(cfg())
        async for chunk in router.process_message(user_msg, user_id, ctx):
            yield chunk
    """
    global _router_instance
    if _router_instance is None:
        _router_instance = PersonaRouter(config)
        logger.info("[ROUTER] PersonaRouter initialized")
    return _router_instance