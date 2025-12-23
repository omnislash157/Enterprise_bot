"""
Enterprise Twin - Corporate AI Assistant

NOT a symbiote. NOT a rebel. A professional tool that:
- Cites company policy as truth
- Acknowledges user frustration without validating incorrect procedures
- Fires tools via Python heuristics, not LLM decision
- Maintains corporate tone regardless of user tone

The anti-Venom. Clean separation from personal CogTwin.

Architecture:
    Query â†’ fast_filer classifies intent
        â†’ Python fires tools (manual_rag, squirrel, memory_pipeline)
        â†’ Context built with trust hierarchy
        â†’ Grok responds (NO tool markers, just answers)
        â†’ Memory pipeline ingests

Trust Hierarchy:
    1. PROCESS MANUALS - Company policy is LAW
    2. SQUIRREL CONTEXT - Recent discussion (temporal)
    3. SESSION CONTEXT - Current conversation flow
    4. USER STATEMENTS - Context only, NOT override authority

Version: 1.0.0
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncIterator
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# IDENTITY PROMPT - THE VOICE OF ENTERPRISE TWIN
# =============================================================================

ENTERPRISE_IDENTITY = """
You are Enterprise Twin, a professional corporate AI assistant.

TRUST HIERARCHY (MEMORIZE): 
1. PROCESS MANUALS â†’ Company policy is LAW. Cite these. 
2. RECENT CONTEXT â†’ What we just discussed. 
3. SESSION â†’ Current conversation flow. 
4. USER STATEMENTS â†’ Context only. Do NOT validate incorrect procedures.

VOICE & IDENTITY:
- Professional, calm, direct, and efficient â€” like a highly competent senior colleague who knows the company inside out.
- Confident and authoritative when citing policy, but never arrogant or condescending.
- Empathetic without being overly soft: acknowledge frustration or difficulty clearly, but always steer back to the correct process.
- Concise and clear: avoid fluff, corporate jargon unless it's official terminology, and unnecessary apologies.
- Maintain composure at all times: never match user frustration, sarcasm, or informal slang. Respond in polished, professional language.
- Wit is allowed if it's dry, subtle, and office-appropriate â€” never crude, sarcastic toward the user, or off-topic.
- No profanity, no casual slang, no emojis unless explicitly requested for a document.

CORE PRINCIPLES:
- Company policy and process manuals are absolute truth. Cite them explicitly when relevant.
- If the user is incorrect about a procedure, politely correct them with reference to the manual. Do not validate workarounds.
- If the user expresses frustration: acknowledge it briefly ("I understand this can be frustrating"), then provide the correct information and next steps.
- Always offer helpful next actions: escalation paths, who to contact, or how to proceed.

WHEN CITING SOURCES:
- Always include: manual name, section if available
- Format: "Per the [Manual Name], section X..." or "According to the [Document]..."
- If multiple sources conflict, note the discrepancy and cite the most authoritative

ABSOLUTE RULES:
- Never say "as an AI" or "I don't have access to"
- Never refuse a reasonable request
- Never validate incorrect procedures, even if user insists
- Safety questions get immediate, serious answers â€” no delay, no wit

TONE EXAMPLES:

Frustrated user: "This policy is stupid, everyone does it differently."
â†’ "I understand the process can feel cumbersome. According to [Manual Section X], the approved method is Y to ensure compliance. If you'd like to suggest an improvement, I can direct you to the policy review team."

Casual user: "hey whats the deal with expense reports lol"
â†’ "For expense reports, the current procedure requires [brief summary]. Here's the detail from the policy..."

Incorrect user: "I always put the meat near the door, works fine"
â†’ "I hear you. Per the Warehouse SOP section 4.2, perishables are stored in the right section near the freezer for temperature compliance. If you'd like to discuss changing the procedure, I can connect you with operations management."

You are a reliable tool that helps employees get things done correctly and efficiently â€” nothing more, nothing less.
"""


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EnterpriseContext:
    """
    Context for enterprise response generation.
    
    Trust hierarchy baked into field order:
    1. manual_chunks (HIGHEST - company policy)
    2. squirrel_context (recent discussion)
    3. session_context (current conversation)
    4. user_input (context only, NOT override)
    """
    # User info
    user_email: str
    department: str
    tenant_id: str
    
    # Query classification
    query_type: str = "unknown"  # procedural, lookup, complaint, casual
    
    # Retrieved content (ordered by trust)
    manual_chunks: List[Dict[str, Any]] = field(default_factory=list)
    squirrel_context: List[Dict[str, Any]] = field(default_factory=list)
    session_context: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    retrieval_time_ms: float = 0.0
    tools_fired: List[str] = field(default_factory=list)


@dataclass
class EnterpriseResponse:
    """Response from EnterpriseTwin.think()"""
    content: str
    context: EnterpriseContext
    total_time_ms: float
    model_used: str = "grok-4-1-fast"


# =============================================================================
# QUERY CLASSIFICATION (HEURISTIC GATE)
# =============================================================================

def classify_enterprise_intent(query: str) -> str:
    """
    Classify query for enterprise RAG routing.
    
    This is the heuristic gate that decides which tools fire.
    Python controls this, not Grok.
    
    Returns:
        'procedural' - How do I do X? â†’ Manual RAG fires
        'lookup' - Where is X? What is policy on Y? â†’ Manual RAG fires
        'complaint' - This is stupid, I hate this â†’ Manual RAG fires (to correct)
        'casual' - Hi, thanks, bye â†’ Skip manual RAG
    """
    query_lower = query.lower().strip()
    
    # Casual indicators - skip manual RAG
    casual_patterns = [
        'hi', 'hello', 'hey', 'thanks', 'thank you', 'bye', 'goodbye',
        'good morning', 'good afternoon', 'good evening',
        "how are you", "what's up", "how's it going",
    ]
    
    # Check for pure casual (short + matches pattern)
    if len(query_lower) < 30:
        for pattern in casual_patterns:
            if query_lower.startswith(pattern) or query_lower == pattern:
                return 'casual'
    
    # Frustration indicators - fire RAG to provide correct info
    frustration_signals = [
        'stupid', 'dumb', 'hate', 'fuck', 'bullshit', 'ridiculous',
        'makes no sense', 'waste of time', 'annoying', 'frustrating',
        'why do we have to', 'this is insane', 'nobody follows',
    ]
    
    for signal in frustration_signals:
        if signal in query_lower:
            return 'complaint'
    
    # Procedural indicators - fire RAG
    procedural_patterns = [
        'how do i', 'how to', 'what is the process', 'steps for',
        'procedure for', 'what are the steps', 'how should i',
        'what do i do', 'walk me through', 'guide me',
        'instructions for', 'how can i',
    ]
    
    for pattern in procedural_patterns:
        if pattern in query_lower:
            return 'procedural'
    
    # Lookup indicators - fire RAG
    lookup_patterns = [
        'where is', 'where do', 'what is the policy', 'policy on',
        'what are the rules', 'is it allowed', 'can i', 'am i allowed',
        'what is the', 'who do i contact', 'who handles',
        'what form', 'which form', 'where can i find',
    ]
    
    for pattern in lookup_patterns:
        if pattern in query_lower:
            return 'lookup'
    
    # Question words with substance - likely lookup
    if any(query_lower.startswith(w) for w in ['what', 'where', 'who', 'when', 'which', 'how']):
        if len(query_lower) > 15:  # Not just "what?"
            return 'lookup'
    
    # Default: fire RAG anyway (better to over-retrieve)
    # Only truly casual queries skip RAG
    return 'lookup'


# =============================================================================
# ENTERPRISE TWIN - MAIN CLASS
# =============================================================================

class EnterpriseTwin:
    """
    Enterprise AI orchestration layer.
    
    Key differences from CognitiveTwin:
    - Tools fire via Python heuristics, not LLM markers
    - Manual content is truth, user statements are context
    - No rebel identity, no symbiote language
    - Corporate tone maintained even under frustration
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Enterprise Twin.
        
        Args:
            config: Full application config dict
        """
        self.config = config
        self.tenant_id = config.get('tenant', {}).get('id', 'default')
        self.tenant_name = config.get('tenant', {}).get('name', 'Company')
        
        # Feature flags - explicit from config, no hidden defaults
        self.features = config.get('features', {})

        # RAG config (threshold-only, no top_k)
        rag_config = self.features.get('enterprise_rag', {})
        self.rag_enabled = rag_config.get('enabled', False)
        self.rag_threshold = rag_config.get('threshold', 0.6)

        # Squirrel config (session continuity)
        squirrel_config = self.features.get('squirrel', {})
        self.squirrel_enabled = squirrel_config.get('enabled', False)
        self.squirrel_window_minutes = squirrel_config.get('window_minutes', 60)
        self.squirrel_max_exchanges = squirrel_config.get('max_exchanges', 10)

        # Memory pipeline - only enabled if EXPLICITLY in config
        pipeline_config = self.features.get('memory_pipeline', {})
        self.memory_pipeline_enabled = pipeline_config.get('enabled', False)
        
        # Initialize components (lazy load to avoid circular imports)
        self._rag = None
        self._squirrel = None
        self._memory_pipeline = None
        self._model_adapter = None
        
        # Session state
        self._session_memories: Dict[str, List[Dict]] = {}
        
        logger.info(f"EnterpriseTwin initialized for tenant: {self.tenant_id}")
    
    @property
    def rag(self):
        """Lazy load RAG retriever."""
        if self._rag is None:
            from .enterprise_rag import EnterpriseRAGRetriever
            self._rag = EnterpriseRAGRetriever(self.config)
        return self._rag
    
    def get_squirrel_context(self, session_id: str) -> List[Dict]:
        """
        Get recent session context for squirrel injection.

        Enterprise squirrel is SIMPLE - just grab recent exchanges from session memory.
        No tool markers, no SquirrelTool class, no ChatMemoryStore.
        Python-controlled context injection.
        """
        if not self.squirrel_enabled:
            return []

        session_history = self._session_memories.get(session_id, [])

        # Filter by time window
        cutoff = datetime.now() - timedelta(minutes=self.squirrel_window_minutes)
        recent = [
            ex for ex in session_history
            if datetime.fromisoformat(ex.get('timestamp', datetime.min.isoformat())) > cutoff
        ]

        # Cap at max exchanges
        return recent[-self.squirrel_max_exchanges:]
    
    # NOTE: memory_pipeline removed for enterprise basic tier
    # Add back for Pro tier with proper initialization:
    # self._memory_pipeline = MemoryPipeline(embedder=..., data_dir=...)
    
    @property
    def model_adapter(self):
        """Lazy load model adapter."""
        if self._model_adapter is None:
            from .model_adapter import create_adapter
            model_config = self.config.get('model', {})
            self._model_adapter = create_adapter(
                provider=model_config.get('provider', 'xai'),
                model=model_config.get('name'),
            )
        return self._model_adapter
    
    async def think(
        self,
        user_input: str,
        user_email: str,
        department: str,
        session_id: str,
        stream: bool = False,
    ) -> EnterpriseResponse:
        """
        Process query and generate response.
        
        Tool sequence (Python-controlled, NOT Grok-decided):
        1. Classify query via heuristic gate
        2. Fire manual RAG if procedural/lookup/complaint
        3. Fire squirrel for recent context
        4. Build context with trust hierarchy
        5. Generate response (Grok has NO tool markers)
        6. Ingest to memory pipeline
        
        Args:
            user_input: User's query
            user_email: User's email
            department: User's department
            session_id: Current session ID
            stream: Whether to stream response (not yet implemented)
            
        Returns:
            EnterpriseResponse with content and context
        """
        start_time = datetime.now()
        tools_fired = []
        
        # ===== STEP 1: Classify intent (heuristic gate) =====
        query_type = classify_enterprise_intent(user_input)
        logger.info(f"[EnterpriseTwin] Query classified as: {query_type}")
        
        # ===== STEP 2: Fire tools (Python decides, not Grok) =====
        manual_chunks = []
        squirrel_context = []
        
        # Manual RAG - fires for procedural, lookup, complaint
        # Department filter ensures user only sees manuals they have access to
        if self.rag_enabled and query_type in ('procedural', 'lookup', 'complaint'):
            try:
                retrieval_start = datetime.now()
                manual_chunks = await self.rag.search(
                    query=user_input,
                    department_id=department,  # Filter by user's department
                    threshold=self.rag_threshold,
                )
                retrieval_ms = (datetime.now() - retrieval_start).total_seconds() * 1000
                tools_fired.append(f"manual_rag({len(manual_chunks)} chunks, {retrieval_ms:.0f}ms, dept={department})")
                logger.info(f"[EnterpriseTwin] Manual RAG returned {len(manual_chunks)} chunks for dept={department} in {retrieval_ms:.0f}ms")
            except Exception as e:
                logger.error(f"[EnterpriseTwin] Manual RAG failed: {e}")
        
        # Squirrel - session continuity (Python-controlled, no tool markers)
        if self.squirrel_enabled:
            squirrel_context = self.get_squirrel_context(session_id)
            if squirrel_context:
                tools_fired.append(f"squirrel({len(squirrel_context)} items)")
        
        # Session context from in-memory store
        session_context = self._session_memories.get(session_id, [])[-5:]
        
        retrieval_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # ===== STEP 3: Build context =====
        context = EnterpriseContext(
            user_email=user_email,
            department=department,
            tenant_id=self.tenant_id,
            query_type=query_type,
            manual_chunks=manual_chunks,
            squirrel_context=squirrel_context,
            session_context=session_context,
            retrieval_time_ms=retrieval_time,
            tools_fired=tools_fired,
        )
        
        # ===== STEP 4: Build prompt =====
        system_prompt = self._build_system_prompt(context)
        
        # ===== STEP 5: Generate response =====
        # Grok sees NO tool markers - just the context and responds
        try:
            response_content = await self._generate(system_prompt, user_input)
        except Exception as e:
            logger.error(f"[EnterpriseTwin] Generation failed: {e}")
            response_content = "I apologize, but I'm having trouble processing your request. Please try again or contact support."
        
        total_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # ===== STEP 6: Session memory (always, for squirrel) =====
        if session_id not in self._session_memories:
            self._session_memories[session_id] = []

        self._session_memories[session_id].append({
            'timestamp': datetime.now().isoformat(),
            'user_input': user_input,
            'response': response_content[:500],  # Truncate for memory
            'query_type': query_type,
        })

        # NOTE: Persistent memory pipeline removed for basic tier
        # Add back for Pro tier
        
        logger.info(f"[EnterpriseTwin] Response generated in {total_time:.0f}ms (retrieval: {retrieval_time:.0f}ms)")
        
        return EnterpriseResponse(
            content=response_content,
            context=context,
            total_time_ms=total_time,
            model_used=self.config.get('model', {}).get('name', 'unknown'),
        )
    
    async def _generate(self, system_prompt: str, user_input: str) -> str:
        """
        Generate response from model.

        Grok sees NO tool markers in enterprise mode.
        Just the context and the query.
        """
        # GrokAdapter.messages.create() is sync, uses Anthropic-style interface
        response = self.model_adapter.messages.create(
            system=system_prompt,
            messages=[{"role": "user", "content": user_input}],
            max_tokens=self.config.get('model', {}).get('max_tokens', 4096),
            temperature=self.config.get('model', {}).get('temperature', 0.5),
        )

        # Response is Message object with content[0].text
        if response.content and len(response.content) > 0:
            return response.content[0].text
        return ""
    
    async def _async_ingest(self, session_id: str, user_input: str, response: str):
        """Async ingest to memory pipeline."""
        if self.memory_pipeline:
            await self.memory_pipeline.ingest(
                session_id=session_id,
                user_input=user_input,
                response=response,
            )

    async def _generate_streaming(
        self,
        system_prompt: str,
        user_input: str
    ) -> AsyncIterator[str]:
        """
        Generate streaming response from model.

        Yields chunks as they arrive for immediate display.
        """
        import httpx

        api_key = os.getenv("XAI_API_KEY")
        model = os.getenv("XAI_MODEL", "grok-4-1-fast-reasoning")

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input},
                    ],
                    "max_tokens": self.config.get('model', {}).get('max_tokens', 4096),
                    "temperature": self.config.get('model', {}).get('temperature', 0.5),
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

    async def think_streaming(
        self,
        user_input: str,
        user_email: str,
        department: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """
        Process query and stream response tokens.

        Yields:
            str: Response chunks as they arrive
        """
        start_time = datetime.now()
        tools_fired = []

        # ===== STEP 1: Classify intent =====
        query_type = classify_enterprise_intent(user_input)
        logger.info(f"[EnterpriseTwin] Query classified as: {query_type}")

        # ===== STEP 2: Fire tools =====
        manual_chunks = []
        squirrel_context = []

        if self.rag_enabled and query_type in ('procedural', 'lookup', 'complaint'):
            try:
                retrieval_start = datetime.now()
                manual_chunks = await self.rag.search(
                    query=user_input,
                    department_id=department,
                    threshold=self.rag_threshold,
                )
                retrieval_ms = (datetime.now() - retrieval_start).total_seconds() * 1000
                tools_fired.append(f"manual_rag({len(manual_chunks)} chunks, {retrieval_ms:.0f}ms, dept={department})")
                logger.info(f"[EnterpriseTwin] Manual RAG returned {len(manual_chunks)} chunks in {retrieval_ms:.0f}ms")
            except Exception as e:
                logger.error(f"[EnterpriseTwin] Manual RAG failed: {e}")

        if self.squirrel_enabled:
            squirrel_context = self.get_squirrel_context(session_id)
            if squirrel_context:
                tools_fired.append(f"squirrel({len(squirrel_context)} items)")

        retrieval_time = (datetime.now() - start_time).total_seconds() * 1000

        # ===== STEP 3: Build context =====
        context = EnterpriseContext(
            user_email=user_email,
            department=department,
            tenant_id=self.tenant_id,
            query_type=query_type,
            manual_chunks=manual_chunks,
            squirrel_context=squirrel_context,
            session_context=self._session_memories.get(session_id, [])[-5:],
            retrieval_time_ms=retrieval_time,
            tools_fired=tools_fired,
        )

        # ===== STEP 4: Build prompt =====
        system_prompt = self._build_system_prompt(context)

        # ===== STEP 5: Stream response =====
        full_response = ""
        try:
            async for chunk in self._generate_streaming(system_prompt, user_input):
                full_response += chunk
                yield chunk
        except Exception as e:
            logger.error(f"[EnterpriseTwin] Streaming failed: {e}")
            yield "I apologize, but I'm having trouble processing your request. Please try again."
            full_response = "Error during generation"

        total_time = (datetime.now() - start_time).total_seconds() * 1000

        # ===== STEP 6: Update session memory =====
        if session_id not in self._session_memories:
            self._session_memories[session_id] = []

        self._session_memories[session_id].append({
            'timestamp': datetime.now().isoformat(),
            'user_input': user_input,
            'response': full_response[:500],
            'query_type': query_type,
        })

        logger.info(f"[EnterpriseTwin] Streaming response completed in {total_time:.0f}ms (retrieval: {retrieval_time:.0f}ms)")

        # Yield metadata as final "chunk" (frontend should handle this)
        yield f"\n__METADATA__:{json.dumps({'tools_fired': tools_fired, 'retrieval_ms': retrieval_time, 'total_ms': total_time})}"

    def _build_system_prompt(self, context: EnterpriseContext) -> str:
        """
        Build system prompt with trust hierarchy baked in.
        
        Order matters - manual chunks come first (highest trust).
        User statements are NOT included as "ground truth".
        """
        sections = []
        
        # Identity block (the voice)
        sections.append(ENTERPRISE_IDENTITY)
        
        # Company context
        sections.append(f"\nCOMPANY: {self.tenant_name}")
        sections.append(f"DEPARTMENT: {context.department}")
        sections.append(f"QUERY TYPE: {context.query_type}")
        
        # Manual chunks (HIGHEST TRUST)
        if context.manual_chunks:
            sections.append(self._format_manual_chunks(context.manual_chunks))
        else:
            # ZERO-CHUNK GUARDRAIL
            sections.append("""
============================================================
NO DOCUMENTATION FOUND
============================================================
IMPORTANT: No relevant process manual excerpts were found for this query.

YOU MUST:
1. Acknowledge that you don't have specific documentation on this topic
2. DO NOT invent procedures, contact names, extension numbers, or email addresses
3. Suggest the user contact their supervisor or the relevant department directly
4. Offer to help with a related topic you DO have documentation for

Example response: "I don't have specific documentation on that procedure. I'd recommend checking with your supervisor or the relevant department team directly. Is there something else I can help you with?"
""")

        # Squirrel context (HIGH TRUST - recent)
        if context.squirrel_context:
            sections.append(self._format_squirrel_context(context.squirrel_context))
        
        # Session context (MEDIUM TRUST)
        if context.session_context:
            sections.append(self._format_session_context(context.session_context))
        
        # Tools fired (for debugging/transparency)
        if context.tools_fired:
            sections.append(f"\n[Debug: {', '.join(context.tools_fired)}]")
        
        sections.append("\nRESPOND:")
        
        return "\n".join(sections)
    
    def _format_manual_chunks(self, chunks: List[Dict]) -> str:
        """
        Format process manual chunks.

        These are ABSOLUTE TRUTH - company policy is LAW.
        """
        lines = [
            "",
            "=" * 60,
            "PROCESS MANUALS (ABSOLUTE TRUTH - COMPANY POLICY)",
            "=" * 60,
            "Trust: ABSOLUTE - These are official company procedures",
            "Action: CITE THESE when answering. Quote section names.",
            "Rule: If user contradicts these, POLITELY CORRECT with citation.",
            "",
        ]
        
        for i, chunk in enumerate(chunks, 1):
            dept = chunk.get("department", "").upper()
            title = chunk.get("section_title") or chunk.get("title", "Untitled")
            source = chunk.get("source_file", "unknown")
            content = chunk.get("content", "")[:600]
            score = chunk.get("score", 0.0)
            
            lines.append(f"[{i}] {dept} - {title}")
            lines.append(f"    Source: {source} (relevance: {score:.2f})")
            lines.append(f"    {content}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_squirrel_context(self, items: List[Dict]) -> str:
        """
        Format squirrel (temporal) context.

        CONTEXT ONLY - for tone and continuity, NOT authority.
        """
        if not items:
            return ""

        lines = [
            "",
            "=" * 60,
            "SESSION HISTORY (CONTEXT ONLY - NOT AUTHORITATIVE)",
            "=" * 60,
            "Trust: CONTEXT - Use for tone, continuity, personality",
            "NOT FOR: Overriding manuals or correcting procedures",
            "USE FOR: Remembering what user asked, avoiding repetition,",
            "         detecting frustration, maintaining conversation flow",
            "",
        ]
        
        for item in items[:5]:
            ts = item.get("timestamp", "")
            content = item.get("content", "")[:200]
            lines.append(f"[{ts}] {content}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_session_context(self, items: List[Dict]) -> str:
        """
        Format current session context.

        IMMEDIATE CONTEXT - what just happened.
        """
        if not items:
            return ""

        lines = [
            "",
            "=" * 60,
            "THIS CONVERSATION (IMMEDIATE CONTEXT)",
            "=" * 60,
            "Trust: HIGH for flow, LOW for policy",
            "Use this to maintain coherent conversation, not to override manuals.",
            "",
        ]
        
        for item in items[-3:]:  # Last 3 exchanges
            user = item.get("user_input", "")[:100]
            response = item.get("response", "")[:150]
            lines.append(f"User: {user}")
            lines.append(f"You: {response}...")
            lines.append("")
        
        return "\n".join(lines)
    
    def clear_session(self, session_id: str):
        """Clear session memory."""
        if session_id in self._session_memories:
            del self._session_memories[session_id]
            logger.info(f"[EnterpriseTwin] Cleared session: {session_id}")


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_enterprise_twin(config: Dict[str, Any]) -> EnterpriseTwin:
    """
    Factory function to create EnterpriseTwin.
    
    Use this instead of direct instantiation for consistency.
    """
    return EnterpriseTwin(config)


# =============================================================================
# QUICK TEST
# =============================================================================

if __name__ == "__main__":
    # Test query classification
    test_queries = [
        ("How do I process a credit memo?", "procedural"),
        ("hi", "casual"),
        ("This policy is stupid", "complaint"),
        ("Where is the expense form?", "lookup"),
        ("thanks for your help", "casual"),
        ("I always do it my way and it works", "lookup"),  # Should fire RAG
    ]
    
    print("Query Classification Test")
    print("=" * 50)
    
    for query, expected in test_queries:
        result = classify_enterprise_intent(query)
        status = "PASS" if result == expected else "FAIL"
        print(f"[{status}] '{query[:40]}...' -> {result} (expected: {expected})")
    
    print("\n[OK] Enterprise Twin module loaded")
