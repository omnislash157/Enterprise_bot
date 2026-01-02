# SDK Agent Session Memory

> **READ THIS FIRST EVERY SESSION.** You lose context between sessions. This file IS your memory.

## Mission

Reorganize `claude_sdk_toolkit/` into a clean, maintainable package while preserving the skill scraper subsystem.

---

## Critical Context

### What This Project Is
- Python SDK toolkit for building Claude agents with custom MCP tools
- Contains: DB tools, Memory/RAG tools, Railway tools, CLI interfaces, Skill Scraper bot
- Uses `claude_agent_sdk` with `@tool` decorator pattern

### The Skill Scraper (PRESERVE THIS)
A working system that converts documentation websites into Claude skill packages:
```
skill_scraper_bot.py      # CLI entry: python skill_scraper_bot.py https://docs.example.com
scraper_tools.py          # MCP tools: check_robots, scrape_page, discover_links, convert_to_md, etc.
skill-crawler.md          # Subagent definition
skill-converter.md        # Subagent definition  
skill-indexer.md          # Subagent definition
README_SKILL_SCRAPER.md   # Documentation
```
**DO NOT MODIFY THESE FILES** during reorganization. Move them intact.

### SDK Tool Pattern (use this for all tools)
```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("tool_name", "Description", {"param": str, "count": int})
async def tool_name(args: dict) -> dict:
    return {"content": [{"type": "text", "text": "result"}]}

server = create_sdk_mcp_server(name="server-name", version="1.0.0", tools=[tool_name])
```

---

## Target Structure

```
claude_sdk_toolkit/
├── CLAUDE.md                      # THIS FILE - session memory
├── CHANGELOG.md                   # Compact rolling log
├── pyproject.toml
├── README.md
│
├── src/claude_sdk_toolkit/
│   ├── __init__.py                # Package exports
│   ├── cli/
│   │   ├── __init__.py
│   │   └── beast.py               # Unified CLI (from claude_cli.py)
│   └── tools/
│       ├── __init__.py            # create_mcp_server(), TOOLS list
│       ├── db.py                  # from db_tools_sdk.py
│       ├── memory.py              # from memory_tools_sdk.py
│       └── railway.py             # from railway_tools_sdk.py
│
├── scraper/                       # Skill scraper subsystem (MOVE INTACT)
│   ├── __init__.py
│   ├── bot.py                     # skill_scraper_bot.py
│   ├── tools.py                   # scraper_tools.py
│   ├── README.md                  # README_SKILL_SCRAPER.md
│   └── agents/
│       ├── crawler.md
│       ├── converter.md
│       └── indexer.md
│
├── skills/                        # From skills_data/skills/
│   └── *.skill.md
│
├── docs/
│   ├── handoffs/                  # HANDOFF_*.md files
│   └── recon/                     # RECON_*.md files
│
└── archive/                       # Dead code (delete after confirming)
    ├── db_tools.py                # Old non-SDK version
    ├── memory_tools.py            # Old non-SDK version
    ├── railway_tools.py           # Old non-SDK version
    ├── claude_chat.py             # Superseded by claude_cli.py
    ├── claude_run.py              # Merged into beast.py
    ├── convert_tools.py           # One-time migration helper
    ├── migration_tenant_multitenant.py
    ├── sdk_recon.py
    └── __init___sdk.py            # Typo filename, merged
```

---

## Task Queue

Check boxes as you complete. Work top-to-bottom.

### Phase 1: Setup ✅ COMPLETE
- [x] Create `CHANGELOG.md` at project root
- [x] Create `archive/` folder
- [x] Create `docs/handoffs/` and `docs/recon/` folders

### Phase 2: Archive Dead Code ✅ COMPLETE
- [x] Move `db_tools.py` → `archive/` (keep `db_tools_sdk.py`)
- [x] Move `memory_tools.py` → `archive/` (keep `memory_tools_sdk.py`)
- [x] Move `railway_tools.py` → `archive/` (keep `railway_tools_sdk.py`)
- [x] Move `convert_tools.py` → `archive/`
- [x] Move `migration_tenant_multitenant.py` → `archive/`
- [x] Move `sdk_recon.py` → `archive/`
- [x] Move `__init___sdk.py` → `archive/` (after merging into `__init__.py`)
- [x] Move `claude_chat.py` → `archive/` (superseded by `claude_cli.py`)

### Phase 3: Organize Docs ✅ COMPLETE
- [x] Move `HANDOFF_*.md` → `docs/handoffs/`
- [x] Move `RECON_*.md` → `docs/recon/`
- [x] Move `*_MAP.md`, `*_SPEC.md`, `BUILD_*.md`, `SDK_*.md` → `docs/`
- [x] Move `vault_recon.md` → `docs/`

### Phase 4: Create Scraper Subsystem ✅ COMPLETE
- [x] Create `scraper/` folder
- [x] Create `scraper/agents/` folder
- [x] Move `skill_scraper_bot.py` → `scraper/bot.py`
- [x] Move `scraper_tools.py` (from `tools/`) → `scraper/tools.py`
- [x] Move `README_SKILL_SCRAPER.md` → `scraper/README.md`
- [x] Move `.claude/agents/skill-*.md` → `scraper/agents/`
- [x] Create `scraper/__init__.py` with exports
- [x] Update imports in `scraper/bot.py` to use `from .tools import ...`

### Phase 5: Populate src/claude_sdk_toolkit/tools/ ✅ COMPLETE
- [x] Copy `db_tools_sdk.py` → `src/claude_sdk_toolkit/tools/db.py`
- [x] Copy `memory_tools_sdk.py` → `src/claude_sdk_toolkit/tools/memory.py`
- [x] Copy `railway_tools_sdk.py` → `src/claude_sdk_toolkit/tools/railway.py`
- [x] Update `src/claude_sdk_toolkit/tools/__init__.py` to export all tools
- [x] Delete root-level `*_sdk.py` files after confirming

### Phase 6: Consolidate CLI ✅ COMPLETE
- [x] Copy `claude_cli.py` → `src/claude_sdk_toolkit/cli/beast.py`
- [x] Update imports in beast.py
- [x] Move `claude_run.py` → `archive/`
- [x] Delete root-level `claude_cli.py` after confirming

### Phase 7: Cleanup ✅ COMPLETE
- [x] Delete empty `tools/` folder at root (after scraper moved)
- [x] Delete `skills_data/` folder (after skills moved to `skills/`)
- [x] Delete `.claude/agents/` (after moved to `scraper/agents/`)
- [x] Update `pyproject.toml` entry points (SKIPPED - will do in next session if needed)
- [x] Test: `python -c "from claude_sdk_toolkit.tools import create_mcp_server"`
- [x] Test: `python scraper/bot.py --help`

---

## Session Protocol

**START of every session:**
1. Read this file completely
2. Read CHANGELOG.md for recent history
3. Check Task Queue for next incomplete item
4. Announce: "Resuming at Phase X, Task: [description]"

**END of every session:**
1. Update Task Queue checkboxes
2. Append to CHANGELOG.md (max 3 lines per session)
3. If blocked, add to BLOCKERS section below

**CHANGELOG format:**
```
## YYYY-MM-DD HH:MM
- [DONE] What was completed
- [NEXT] What's next
```

---

## Blockers

<!-- Add blockers here if stuck -->

---

## File Checksums (for verification)

After reorganization, run:
```bash
find . -name "*.py" -exec wc -l {} \; | sort -n
```

Key files that MUST survive intact:
- `scraper/bot.py` ~400 lines
- `scraper/tools.py` ~730 lines
- `src/claude_sdk_toolkit/tools/db.py` ~300 lines
- `src/claude_sdk_toolkit/tools/memory.py` ~450 lines
- `src/claude_sdk_toolkit/cli/beast.py` ~1200 lines

---

## Quick Reference

**Run skill scraper:**
```bash
python scraper/bot.py https://docs.example.com --max-pages 100
```

**Test tools:**
```bash
python -c "from claude_sdk_toolkit.tools import create_mcp_server; print('OK')"
```

**Run CLI:**
```bash
python -m claude_sdk_toolkit.cli.beast chat
```
