#!/usr/bin/env python3
"""
Claude Agent SDK - One-Shot Runner + Interactive Mode
Execute a single prompt or start an interactive session.

Usage:
    python claude_run.py "Fix the bug in auth.py"
    python claude_run.py --preset scan
    python claude_run.py --file HANDOFF.md
    python claude_run.py -i                      # Interactive mode
    python claude_run.py -i "Start with this"   # Interactive with initial prompt
    echo "Scan codebase" | python claude_run.py -

Interactive Commands:
    /paste    - Multi-line paste mode (type END to submit)
    /file     - Load prompt from file
    /clear    - Clear conversation (start fresh)
    /quit     - Exit

Presets loaded from: .claude/presets/*.md
Session continuity: 
    .claude/CHANGELOG.md - Full detailed log
    .claude/CHANGELOG_COMPACT.md - Summarized for efficiency
"""

import asyncio
import sys
import os
import argparse
from pathlib import Path

try:
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        ToolUseBlock,
        TextBlock,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


# =============================================================================
# PROJECT ROOT & PRESETS
# =============================================================================

def find_project_root(start_path: str = None) -> str:
    """Find project root by looking for enterprise_bot markers."""
    path = Path(start_path or os.getcwd()).resolve()
    
    while path != path.parent:
        if (path / "core" / "protocols.py").exists():
            return str(path)
        if (path / ".git").exists() and (path / "core").exists():
            return str(path)
        path = path.parent
    
    return os.getcwd()


def load_presets(root: str) -> dict:
    """Load presets from .claude/presets/*.md"""
    presets = {}
    presets_dir = Path(root) / ".claude" / "presets"
    
    if presets_dir.exists():
        for f in presets_dir.glob("*.md"):
            presets[f.stem] = f.read_text()
    
    if "scan" not in presets:
        presets["scan"] = "Scan this codebase and create docs/WIRING_MAP.md documenting architecture, data flows, entry points, and module responsibilities."
    if "test" not in presets:
        presets["test"] = "Run tests. Fix any failures. Report results."
    
    return presets


def get_changelog_context(root: str) -> tuple[str, str]:
    """Read both changelogs for session continuity."""
    claude_dir = Path(root) / ".claude"
    
    compact_log = ""
    full_log = ""
    
    compact_path = claude_dir / "CHANGELOG_COMPACT.md"
    full_path = claude_dir / "CHANGELOG.md"
    
    if compact_path.exists():
        try:
            compact_log = compact_path.read_text().strip()
        except Exception:
            pass
    
    if full_path.exists():
        try:
            full_log = full_path.read_text().strip()
        except Exception:
            pass
    
    return compact_log, full_log


def build_system_prompt(cwd: str, custom_prompt: str = None) -> str:
    """Build system prompt with changelog context."""
    compact_log, full_log = get_changelog_context(cwd)
    
    changelog_prompt = """<session_memory>
You maintain two changelogs for session continuity:

1. `.claude/CHANGELOG.md` - Full detailed log of all work
2. `.claude/CHANGELOG_COMPACT.md` - Summarized version for efficiency

**Reading context:**
- Start by reading CHANGELOG_COMPACT.md for quick orientation
- Read full CHANGELOG.md when you need deeper context on specific past work

**Writing:**
- Always append to CHANGELOG.md with date, files modified, what was done
- When CHANGELOG.md grows large, summarize older entries into CHANGELOG_COMPACT.md

**Format for CHANGELOG.md entries:**
```
## [YYYY-MM-DD HH:MM] - Brief Title

### Files Modified
- path/to/file.py - what changed

### Summary
What was accomplished.

### Notes
Any issues or context for future sessions.
```

**CRITICAL CONSTRAINT:**
Do not modify any files unless explicitly asked to in the task.
"""

    if compact_log:
        changelog_prompt += f"""
**Current CHANGELOG_COMPACT.md:**
{compact_log}
"""

    if full_log:
        line_count = len(full_log.split('\n'))
        changelog_prompt += f"""
**CHANGELOG.md:** {line_count} lines available. Read .claude/CHANGELOG.md for full details if needed.
"""
    else:
        changelog_prompt += """
**No changelogs exist yet.** Create .claude/CHANGELOG.md after completing your first task.
"""

    changelog_prompt += "\n</session_memory>"

    if custom_prompt:
        return f"{changelog_prompt}\n\n{custom_prompt}"
    return changelog_prompt


# =============================================================================
# INPUT HELPERS
# =============================================================================

def get_input(prompt: str) -> str | None:
    """Get single line input, return None on EOF/interrupt."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return None


def get_paste_input() -> str | None:
    """Multi-line paste mode - type END on its own line to submit."""
    print(f"{Colors.DIM}Paste mode: Enter text, type END on its own line to submit{Colors.RESET}")
    print(f"{Colors.DIM}─────────────────────────────────────────{Colors.RESET}")
    
    lines = []
    try:
        while True:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        if not lines:
            print(f"\n{Colors.DIM}[Cancelled]{Colors.RESET}")
            return None
    
    if lines:
        print(f"{Colors.DIM}─────────────────────────────────────────{Colors.RESET}")
        print(f"{Colors.DIM}[Captured {len(lines)} lines]{Colors.RESET}")
        return '\n'.join(lines)
    return None


def get_file_input(filepath: str, root: str) -> str | None:
    """Load prompt from file."""
    path = Path(filepath)
    if not path.is_absolute() and not path.exists():
        path = Path(root) / filepath
    
    if not path.exists():
        print(f"{Colors.RED}File not found: {filepath}{Colors.RESET}")
        return None
    
    content = path.read_text().strip()
    print(f"{Colors.DIM}[Loaded {len(content)} chars from {path.name}]{Colors.RESET}")
    return content


# =============================================================================
# RUNNER
# =============================================================================

async def run_prompt(
    prompt: str,
    cwd: str,
    mode: str = "acceptEdits",
    tools: list = None,
    system_prompt: str = None,
    verbose: bool = True
) -> bool:
    """Execute a single prompt and stream results."""
    
    if not SDK_AVAILABLE:
        print(f"{Colors.RED}Error: claude_agent_sdk not installed{Colors.RESET}")
        print("Install with: pip install claude-agent-sdk")
        return False
    
    tools = tools or ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
    
    if verbose:
        display_prompt = ' '.join(line.strip() for line in prompt.strip().split('\n') if line.strip())
        print(f"{Colors.DIM}Prompt: {display_prompt[:100]}{'...' if len(display_prompt) > 100 else ''}{Colors.RESET}")
        print()
    
    options = ClaudeAgentOptions(
        cwd=cwd,
        allowed_tools=tools,
        permission_mode=mode,
        system_prompt=system_prompt
    )
    
    success = True
    current_text = ""
    
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        new_text = block.text
                        if new_text.startswith(current_text):
                            print(new_text[len(current_text):], end='', flush=True)
                        else:
                            print(new_text, end='', flush=True)
                        current_text = new_text
                        
                    elif isinstance(block, ToolUseBlock):
                        if verbose:
                            print(f"\n{Colors.YELLOW}[{block.name}]{Colors.RESET} ", end='')
                            if hasattr(block, 'input') and block.input:
                                input_str = str(block.input)
                                if len(input_str) > 80:
                                    input_str = input_str[:80] + "..."
                                print(f"{Colors.DIM}{input_str}{Colors.RESET}")
                        
            elif isinstance(message, ResultMessage):
                if message.subtype == "error":
                    success = False
                    print(f"\n{Colors.RED}[Error]{Colors.RESET}")
                elif verbose:
                    print(f"\n{Colors.GREEN}[Done]{Colors.RESET}")
                    
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
        success = False
    
    print()
    return success


# =============================================================================
# INTERACTIVE MODE
# =============================================================================

async def interactive_session(
    initial_prompt: str = None,
    cwd: str = None,
    mode: str = "acceptEdits",
    verbose: bool = True
):
    """Interactive turn-based session."""
    
    cwd = cwd or find_project_root()
    system_prompt = build_system_prompt(cwd)
    tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
    
    print(f"""
{Colors.CYAN}{Colors.BOLD}Claude Agent - Interactive Mode{Colors.RESET}
{Colors.DIM}Root: {cwd}
Mode: {mode}
Commands: /paste, /file <path>, /clear, /quit{Colors.RESET}
""")
    
    # Run initial prompt if provided
    if initial_prompt:
        await run_prompt(initial_prompt, cwd, mode, tools, system_prompt, verbose)
    
    # REPL loop
    while True:
        print(f"{Colors.CYAN}{'─' * 50}{Colors.RESET}")
        
        user_input = get_input(f"{Colors.BOLD}You:{Colors.RESET} ")
        
        if user_input is None:
            print(f"\n{Colors.DIM}Session ended.{Colors.RESET}")
            break
        
        if not user_input:
            continue
        
        # Handle commands
        if user_input.lower() in ('/quit', '/exit', '/q'):
            print(f"{Colors.DIM}Session ended.{Colors.RESET}")
            break
        
        elif user_input.lower() == '/paste':
            content = get_paste_input()
            if content:
                await run_prompt(content, cwd, mode, tools, system_prompt, verbose)
            continue
        
        elif user_input.lower().startswith('/file '):
            filepath = user_input[6:].strip()
            content = get_file_input(filepath, cwd)
            if content:
                await run_prompt(content, cwd, mode, tools, system_prompt, verbose)
            continue
        
        elif user_input.lower() == '/clear':
            system_prompt = build_system_prompt(cwd)  # Refresh
            print(f"{Colors.DIM}Conversation cleared.{Colors.RESET}")
            continue
        
        elif user_input.startswith('/'):
            print(f"{Colors.YELLOW}Unknown command. Try: /paste, /file, /clear, /quit{Colors.RESET}")
            continue
        
        # Regular prompt
        await run_prompt(user_input, cwd, mode, tools, system_prompt, verbose)


# =============================================================================
# CLI
# =============================================================================

async def main():
    project_root = find_project_root()
    presets = load_presets(project_root)
    
    parser = argparse.ArgumentParser(
        description="Execute Claude Agent SDK prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Presets: {', '.join(sorted(presets.keys())) or '(none)'}

Examples:
  python claude_run.py "Fix bugs in auth.py"
  python claude_run.py --preset scan
  python claude_run.py --file HANDOFF.md
  python claude_run.py -i                    # Interactive mode
  python claude_run.py -i "Start here"       # Interactive with initial prompt
        """
    )
    parser.add_argument("prompt", nargs="?", help="Prompt to execute (use - for stdin)")
    parser.add_argument("--preset", "-p", help="Use a preset")
    parser.add_argument("--file", "-f", help="Read prompt from file")
    parser.add_argument("--cwd", "-c", help="Working directory")
    parser.add_argument("--mode", "-m", choices=["acceptEdits", "bypassPermissions", "default"], default="acceptEdits")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")
    parser.add_argument("--list", "-l", action="store_true", help="List presets")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    # List presets
    if args.list:
        print(f"{Colors.CYAN}Available presets:{Colors.RESET}")
        for name in sorted(presets.keys()):
            preview = presets[name][:60].replace('\n', ' ')
            print(f"  {Colors.BOLD}{name}{Colors.RESET}: {Colors.DIM}{preview}...{Colors.RESET}")
        return
    
    cwd = args.cwd or project_root
    
    # Interactive mode
    if args.interactive:
        initial = None
        if args.preset:
            initial = presets.get(args.preset)
        elif args.file:
            initial = get_file_input(args.file, cwd)
        elif args.prompt and args.prompt != '-':
            initial = args.prompt
        
        await interactive_session(initial, cwd, args.mode, not args.quiet)
        return
    
    # One-shot mode - determine prompt source
    if args.preset:
        if args.preset not in presets:
            print(f"{Colors.RED}Unknown preset: {args.preset}{Colors.RESET}")
            sys.exit(1)
        prompt = presets[args.preset]
    elif args.file:
        prompt = get_file_input(args.file, cwd)
        if not prompt:
            sys.exit(1)
    elif args.prompt == "-":
        prompt = sys.stdin.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.print_help()
        sys.exit(1)
    
    system_prompt = build_system_prompt(cwd)
    success = await run_prompt(prompt, cwd, args.mode, verbose=not args.quiet, system_prompt=system_prompt)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())