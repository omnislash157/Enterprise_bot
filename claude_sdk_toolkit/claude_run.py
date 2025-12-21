#!/usr/bin/env python3
"""
Claude Agent SDK - One-Shot Runner
Execute a single prompt and watch Claude work.

Usage:
    python claude_run.py "Fix the bug in auth.py and run tests"
    python claude_run.py --preset restructure
    python claude_run.py --file HANDOFF.md
    echo "Scan codebase" | python claude_run.py -

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
        # enterprise_bot specific
        if (path / "core" / "protocols.py").exists():
            return str(path)
        # Generic fallback
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
    
    # Built-in fallbacks
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


# =============================================================================
# RUNNER
# =============================================================================

async def run_prompt(
    prompt: str,
    cwd: str = None,
    mode: str = "acceptEdits",
    tools: list = None,
    system_prompt: str = None,
    verbose: bool = True
):
    """Execute a single prompt and stream results."""
    
    if not SDK_AVAILABLE:
        print(f"{Colors.RED}Error: claude_agent_sdk not installed{Colors.RESET}")
        print("Install with: pip install claude-agent-sdk")
        return False
    
    cwd = cwd or find_project_root()
    tools = tools or ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
    
    # Build changelog context
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
- When CHANGELOG.md grows large and you want efficiency, summarize older entries into CHANGELOG_COMPACT.md
- Compaction is your choice - do it when it helps, not forced

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
Do not modify any files unless explicitly asked to in the task. Read freely, write only what's requested.
"""

    if compact_log:
        changelog_prompt += f"""
**Current CHANGELOG_COMPACT.md:**
{compact_log}
"""

    if full_log:
        # Show size, let agent decide if it wants to read
        line_count = len(full_log.split('\n'))
        changelog_prompt += f"""
**CHANGELOG.md:** {line_count} lines available. Read .claude/CHANGELOG.md for full details if needed.
"""
    else:
        changelog_prompt += """
**No changelogs exist yet.** Create .claude/CHANGELOG.md after completing your first task.
"""

    changelog_prompt += "\n</session_memory>"

    if system_prompt:
        system_prompt = f"{changelog_prompt}\n\n{system_prompt}"
    else:
        system_prompt = changelog_prompt
    
    # Format prompt - compress to single line for display
    display_prompt = ' '.join(line.strip() for line in prompt.strip().split('\n') if line.strip())
    
    if verbose:
        print(f"{Colors.DIM}Root: {cwd}{Colors.RESET}")
        print(f"{Colors.DIM}Prompt: {display_prompt[:80]}{'...' if len(display_prompt) > 80 else ''}{Colors.RESET}")
        if compact_log or full_log:
            print(f"{Colors.DIM}Changelogs: compact={'yes' if compact_log else 'no'}, full={'yes' if full_log else 'no'}{Colors.RESET}")
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
# CLI
# =============================================================================

async def main():
    # Find project root first for preset loading
    project_root = find_project_root()
    presets = load_presets(project_root)
    
    parser = argparse.ArgumentParser(
        description="Execute a single Claude Agent SDK prompt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Presets (from .claude/presets/):
  {', '.join(sorted(presets.keys())) or '(none found)'}

Examples:
  python claude_run.py "Fix bugs in auth.py"
  python claude_run.py --preset scan
  python claude_run.py --file HANDOFF.md
  echo "Analyze codebase" | python claude_run.py -
        """
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="The prompt to execute (use - for stdin)"
    )
    parser.add_argument(
        "--preset", "-p",
        help="Use a preset from .claude/presets/"
    )
    parser.add_argument(
        "--file", "-f",
        help="Read prompt from file"
    )
    parser.add_argument(
        "--cwd", "-c",
        help="Override working directory"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["acceptEdits", "bypassPermissions", "default"],
        default="acceptEdits",
        help="Permission mode"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available presets"
    )
    
    args = parser.parse_args()
    
    # List presets
    if args.list:
        print(f"{Colors.CYAN}Available presets:{Colors.RESET}")
        for name in sorted(presets.keys()):
            preview = presets[name][:60].replace('\n', ' ')
            print(f"  {Colors.BOLD}{name}{Colors.RESET}: {Colors.DIM}{preview}...{Colors.RESET}")
        return
    
    # Determine prompt source
    if args.preset:
        if args.preset not in presets:
            print(f"{Colors.RED}Unknown preset: {args.preset}{Colors.RESET}")
            print(f"Available: {', '.join(sorted(presets.keys()))}")
            sys.exit(1)
        prompt = presets[args.preset]
    elif args.file:
        # Resolve file path relative to project root if not absolute
        file_path = Path(args.file)
        if not file_path.is_absolute() and not file_path.exists():
            file_path = Path(project_root) / args.file
        with open(file_path) as f:
            prompt = f.read()
    elif args.prompt == "-":
        prompt = sys.stdin.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.print_help()
        sys.exit(1)
    
    # Use provided cwd or auto-detected root
    cwd = args.cwd or project_root
    
    success = await run_prompt(
        prompt=prompt,
        cwd=cwd,
        mode=args.mode,
        verbose=not args.quiet
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())