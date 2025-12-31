# SESSION QUICKSTART PROMPT

Copy-paste this to start any new CogTwin/Enterprise Bot session:

---

```
## CONTEXT LOAD

I'm working on CogTwin/Enterprise Bot. Here's the workflow:

**Team:**
- You (Claude Opus 4.5): Architect, troubleshooter, spec designer
- SDK Agent (claude_cli.py): Deep recon, parallel builders
- Claude Code: Surgical implementation

**Protocol:** RECON → SPEC → BUILD → VALIDATE → SHIP

**Rules:**
1. No coding without a build sheet
2. SDK recon before touching unfamiliar code
3. One commit per logical change
4. Changelog updated with every ship
5. Validate before push

**SDK Commands:**
- Recon: `python claude_sdk_toolkit/claude_cli.py run -f RECON_MISSION.md`
- Build: `python claude_sdk_toolkit/claude_cli.py run -f BUILD_SHEET_XXX.md`
- Interactive: `python claude_sdk_toolkit/claude_cli.py chat`

**Stack:**
- Backend: FastAPI + WebSocket (Railway)
- Frontend: SvelteKit (same repo /frontend)
- Database: Azure PostgreSQL + pgvector
- Cache: Redis (Railway addon)
- AI: Grok 4.1 Fast Reasoning

---

## LAST SESSION

[Paste recent changelog entries here]

---

## THIS SESSION

**Goal:** [What we're doing]

**Current State:** [Working/Broken/New feature]

**Blockers:** [Any known issues]

---

Ready to start. What's our approach?
```

---

## USAGE

1. Copy the template above
2. Fill in:
   - Last session changelog
   - This session's goal
   - Current state
   - Any blockers
3. Paste to new Claude Opus chat
4. Opus will assess and recommend: recon, spec, or direct build

---

## EXAMPLE FILLED IN

```
## CONTEXT LOAD

[...standard context...]

---

## LAST SESSION

## 2024-12-23 - Security + Performance + Hybrid RAG

### Shipped
- set_division auth bypass fixed
- Message-level division read
- Zero-chunk guardrail
- Redis caching (embedding + RAG)
- Grok streaming responses
- Hybrid RAG with 845 synthetic questions

### Commits
- 7fca20e, 2f6f1a0, b0dbfa7 (security)
- fd52856, 90ee566 (performance)
- fe07345 (hybrid RAG)

---

## THIS SESSION

**Goal:** Add voice transcription for cognitive pattern capture

**Current State:** Working - all previous fixes deployed

**Blockers:** Need to decide on transcription provider (Whisper vs Deepgram)

---

Ready to start. What's our approach?
```

---

## OPUS RESPONSE PATTERN

Opus will typically respond with:

1. **Acknowledgment** of context
2. **Clarifying questions** if needed
3. **Recommendation:** recon needed? spec directly?
4. **First action item**

Example:
```
Got it. System is stable after yesterday's hardening session.

For voice transcription, I have a few questions:
1. Real-time streaming transcription or batch upload?
2. Speaker diarization needed (multi-person)?
3. Where does the audio come from (browser, mobile, uploaded files)?

Based on answers, I'll either:
- Spec a build sheet directly (if scope is clear)
- Send SDK for provider comparison recon (if decision needed)

What's the use case?
```
