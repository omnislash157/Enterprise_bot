#!/usr/bin/env python3
"""
Claude CLI - Beast Mode

Unified interface for Claude Agent SDK with:
- Custom MCP tools (db, memory, railway)
- Dual model backend (Claude SDK + Grok)
- Session continuity with CHANGELOG
- Full DevOps capabilities
- Graceful interrupt handling (Ctrl+C without crash)
- Failure guidance protocols

Usage:
    python claude_cli.py chat              # Interactive REPL with custom tools
    python claude_cli.py run "Fix the bug" # One-shot execution
    python claude_cli.py db tables         # Direct database access
    python claude_cli.py memory search X   # Direct memory search
    python claude_cli.py railway logs svc  # Direct Railway access

Custom Tools (available to Claude automatically):
    db_query, db_tables, db_describe, db_sample
    memory_vector, memory_grep, memory_episodic, memory_squirrel, memory_search
    railway_services, railway_status, railway_logs, railway_redeploy, railway_env_*

Interrupt Handling:
    Ctrl+C during streaming - Gracefully stops current operation, keeps session
    /interrupt - Stop current operation programmatically
    Ctrl+C at prompt - Show exit message (use /quit to exit)

Failure Guidance:
    When operations fail, Claude will:
    1. Stop and analyze what went wrong
    2. Query user for clarification/direction
    3. Propose 2-3 alternative approaches
    4. Wait for explicit approval before continuing

    This prevents token burn in wrong directions!

Version: 2.2.0 (beast-mode + SDK interrupt + guidance)
"""

import asyncio
import argparse
import os
import sys
import json
import signal
from pathlib import Path
from datetime import datetime
from typing import Any, List, Dict, Optional

# readline for history
try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    try:
        import pyreadline3 as readline
        READLINE_AVAILABLE = True
    except ImportError:
        READLINE_AVAILABLE = False

# Claude SDK
try:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        ToolUseBlock,
        TextBlock,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

# Custom tools
try:
    from tools import create_tools_server, list_available_tools
    CUSTOM_TOOLS_AVAILABLE = True
except ImportError:
    CUSTOM_TOOLS_AVAILABLE = False
    def list_available_tools():
        return []

# Direct tool access (for CLI commands)
try:
    from tools.db_tools import db_query, db_tables, db_describe, db_sample
    DB_TOOLS_DIRECT = True
except ImportError:
    DB_TOOLS_DIRECT = False

try:
    from tools.memory_tools import memory_vector, memory_grep, memory_episodic, memory_squirrel, memory_search
    MEMORY_TOOLS_DIRECT = True
except ImportError:
    MEMORY_TOOLS_DIRECT = False

try:
    from tools.railway_tools import railway_services, railway_status, railway_logs, railway_redeploy
    RAILWAY_TOOLS_DIRECT = True
except ImportError:
    RAILWAY_TOOLS_DIRECT = False

# Grok (OpenAI-compatible)
try:
    from openai import OpenAI
    GROK_AVAILABLE = True
except ImportError:
    GROK_AVAILABLE = False


# =============================================================================
# CONSTANTS
# =============================================================================

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    BLUE = '\033[94m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


DEFAULT_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
ALL_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch", "Task"]


# =============================================================================
# PROJECT HELPERS
# =============================================================================

def find_project_root(start: str = None) -> Path:
    """Find project root by looking for markers."""
    path = Path(start or os.getcwd()).resolve()
    
    while path != path.parent:
        if (path / ".git").exists():
            return path
        if (path / ".claude").exists():
            return path
        if (path / "pyproject.toml").exists():
            return path
        path = path.parent
    
    return Path.cwd()


def load_presets(root: Path) -> Dict[str, str]:
    """Load presets from .claude/presets/*.md"""
    presets = {}
    presets_dir = root / ".claude" / "presets"
    
    if presets_dir.exists():
        for f in presets_dir.glob("*.md"):
            presets[f.stem] = f.read_text()
    
    # Built-in presets
    if "scan" not in presets:
        presets["scan"] = "Scan this codebase and create docs/WIRING_MAP.md documenting architecture."
    if "test" not in presets:
        presets["test"] = "Run tests. Fix any failures. Report results."
    
    return presets


def build_system_prompt(cwd: Path) -> str:
    """Build system prompt with CHANGELOG context and failure guidance."""
    claude_dir = cwd / ".claude"

    prompt = """You maintain session continuity via .claude/CHANGELOG.md.

After completing tasks, append:
```
## [YYYY-MM-DD HH:MM] - Brief Title
### Files Modified
- path/to/file.py - what changed
### Summary
What was accomplished.
```

CRITICAL: Do not modify files unless explicitly asked.

=== FAILURE GUIDANCE PROTOCOL ===

When an operation fails or produces unexpected results, you MUST follow this protocol:

1. STOP IMMEDIATELY - Do not continue down the same path
2. ANALYZE - Clearly explain what went wrong and why
3. QUERY USER - Ask specific questions to clarify intent/requirements
4. PROPOSE OPTIONS - Present 2-3 alternative approaches with trade-offs
5. WAIT FOR APPROVAL - Do NOT proceed without user confirmation

Example:
"The test suite failed with error X. This could be because:
- Approach A: dependency issue (fix: install Y)
- Approach B: configuration problem (fix: update Z)
- Approach C: architectural mismatch (fix: refactor W)

Which direction should I take? Or would you prefer a different approach?"

DO NOT:
- Repeatedly try the same failing approach
- Make assumptions about requirements
- Burn tokens exploring without user guidance
- Continue if user sends interrupt signal (Ctrl+C)

This protocol prevents wasted effort and ensures alignment!
"""

    # Add CHANGELOG context
    changelog = claude_dir / "CHANGELOG.md"
    if changelog.exists():
        content = changelog.read_text()
        lines = len(content.split('\n'))
        prompt += f"\n\nCHANGELOG: {lines} lines. Read .claude/CHANGELOG.md for context.\n"

    return prompt


# =============================================================================
# INPUT HELPERS
# =============================================================================

def get_multiline_input(prompt: str) -> Optional[str]:
    """Get multi-line input with backslash continuation."""
    lines = []
    current_prompt = prompt

    while True:
        try:
            line = input(current_prompt)

            if not line and lines:
                break

            if line.endswith('\\'):
                lines.append(line[:-1])
                current_prompt = f"{Colors.DIM}...{Colors.RESET} "
            else:
                lines.append(line)
                if len(lines) == 1:
                    break

        except EOFError:
            if lines:
                break
            return None
        except KeyboardInterrupt:
            print(f"\n{Colors.DIM}[Cancelled]{Colors.RESET}")
            return None

    result = '\n'.join(lines)
    return result.strip() if result.strip() else None


def get_paste_input() -> Optional[str]:
    """Multi-line paste mode - END to submit."""
    print(f"{Colors.DIM}Paste mode: type END on its own line to submit{Colors.RESET}")

    lines = []
    try:
        while True:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        if not lines:
            return None

    if lines:
        print(f"{Colors.DIM}[Captured {len(lines)} lines]{Colors.RESET}")
        return '\n'.join(lines)
    return None


# =============================================================================
# GROK CLIENT
# =============================================================================

class GrokClient:
    """
    Grok API client - cheap alternative to Claude for simple tasks.
    
    Uses OpenAI-compatible API at api.x.ai
    """
    
    def __init__(self):
        self.client = None
        self.history = []
        self.model = "grok-beta"  # Or grok-2, grok-3
    
    def connect(self) -> bool:
        if not GROK_AVAILABLE:
            print(f"{Colors.RED}Grok requires: pip install openai{Colors.RESET}")
            return False
        
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            print(f"{Colors.RED}XAI_API_KEY not set{Colors.RESET}")
            return False
        
        self.client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        return True
    
    def chat(self, message: str, system: str = None) -> str:
        """Send message and stream response."""
        if not self.client and not self.connect():
            return ""
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(self.history)
        messages.append({"role": "user", "content": message})
        
        print(f"\n{Colors.MAGENTA}Grok:{Colors.RESET} ", end='', flush=True)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
            )
            
            full_response = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    print(content, end='', flush=True)
                    full_response += content
            
            print()
            
            self.history.append({"role": "user", "content": message})
            self.history.append({"role": "assistant", "content": full_response})
            
            return full_response
            
        except Exception as e:
            print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
            return ""
    
    def clear(self):
        self.history = []


# =============================================================================
# INTERRUPT HANDLING
# =============================================================================

class AsyncInterruptHandler:
    """
    Manages graceful interruption of streaming operations.
    
    Uses asyncio Event + background task to properly call client.interrupt()
    from a sync signal handler context. This is the SDK-proper way to interrupt.
    """

    def __init__(self):
        self.interrupted = False
        self.interrupt_event = None
        self.client = None
        self.original_handler = None
        self._monitor_task = None
        self._loop = None

    async def __aenter__(self):
        self.interrupted = False
        self.interrupt_event = asyncio.Event()
        self._loop = asyncio.get_running_loop()
        self.original_handler = signal.signal(signal.SIGINT, self._handle_interrupt)
        return self

    async def __aexit__(self, *args):
        signal.signal(signal.SIGINT, self.original_handler)
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    def _handle_interrupt(self, signum, frame):
        """Handle Ctrl+C - sets event that monitor task watches."""
        self.interrupted = True
        print(f"\n{Colors.YELLOW}[Interrupt received - stopping gracefully...]{Colors.RESET}")
        # Thread-safe way to set the event from signal handler
        if self._loop and self.interrupt_event:
            self._loop.call_soon_threadsafe(self.interrupt_event.set)

    def set_client(self, client):
        """Set the client to interrupt when signal received."""
        self.client = client
        # Start monitor task that will call client.interrupt() when signal fires
        if self.client and self._loop:
            self._monitor_task = asyncio.create_task(self._interrupt_monitor())

    async def _interrupt_monitor(self):
        """Background task that calls client.interrupt() when event is set."""
        try:
            await self.interrupt_event.wait()
            if self.client:
                print(f"{Colors.DIM}[Calling SDK interrupt...]{Colors.RESET}")
                await self.client.interrupt()
                print(f"{Colors.GREEN}[SDK interrupt sent]{Colors.RESET}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"{Colors.RED}[Interrupt error: {e}]{Colors.RESET}")

    def check(self):
        """Check if interrupted."""
        return self.interrupted


# Legacy sync handler for non-streaming contexts (prompt input)
class InterruptHandler:
    """Simple sync interrupt handler for prompts."""

    def __init__(self):
        self.interrupted = False
        self.original_handler = None

    def __enter__(self):
        self.interrupted = False
        self.original_handler = signal.signal(signal.SIGINT, self._handle_interrupt)
        return self

    def __exit__(self, *args):
        signal.signal(signal.SIGINT, self.original_handler)

    def _handle_interrupt(self, signum, frame):
        self.interrupted = True
        print(f"\n{Colors.YELLOW}[Interrupted]{Colors.RESET}")

    def check(self):
        return self.interrupted


# =============================================================================
# SDK STREAMING
# =============================================================================

async def stream_sdk_response(
    prompt: str,
    cwd: Path,
    mode: str = "acceptEdits",
    tools: List[str] = None,
    system_prompt: str = None,
    client: Any = None,
    use_custom_tools: bool = True,
) -> tuple[bool, Any]:
    """
    Stream SDK response with custom tools and proper interrupt handling.
    
    Uses AsyncInterruptHandler to call client.interrupt() when Ctrl+C is pressed,
    which properly stops the SDK mid-stream without crashing the session.
    """

    if not SDK_AVAILABLE:
        print(f"\n{Colors.MAGENTA}[Simulation]{Colors.RESET} Would send: {prompt[:100]}...")
        return True, None

    tools = tools or DEFAULT_TOOLS

    # Build options
    options_kwargs = {
        "cwd": str(cwd),
        "allowed_tools": tools,
        "permission_mode": mode,
    }

    if system_prompt:
        options_kwargs["system_prompt"] = system_prompt

    # Add custom MCP tools
    if use_custom_tools and CUSTOM_TOOLS_AVAILABLE:
        try:
            mcp_server = create_tools_server()
            options_kwargs["mcp_servers"] = [mcp_server]
        except Exception as e:
            print(f"{Colors.YELLOW}[Custom tools unavailable: {e}]{Colors.RESET}")

    options = ClaudeAgentOptions(**options_kwargs)

    current_text = ""
    success = True
    new_session = client is None
    interrupted = False

    # Install async interrupt handler
    interrupt_handler = AsyncInterruptHandler()

    try:
        async with interrupt_handler:
            if new_session:
                client = ClaudeSDKClient(options=options)
                await client.__aenter__()
                print(f"{Colors.DIM}[New session]{Colors.RESET}")

            # Wire up the interrupt handler to this client
            # When Ctrl+C fires, it will call client.interrupt()
            interrupt_handler.set_client(client)

            await client.query(prompt)

            async for message in client.receive_response():
                # Check for interrupt (set by signal handler)
                if interrupt_handler.check():
                    interrupted = True
                    # Don't break immediately - let SDK process the interrupt
                    # The client.interrupt() has already been called by monitor task
                    break

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
                            # Show tool use - includes our custom tools!
                            tool_name = block.name

                            # Color code by tool type
                            if tool_name.startswith("db_"):
                                color = Colors.BLUE
                            elif tool_name.startswith("memory_"):
                                color = Colors.MAGENTA
                            elif tool_name.startswith("railway_"):
                                color = Colors.GREEN
                            else:
                                color = Colors.YELLOW

                            print(f"\n{color}[{tool_name}]{Colors.RESET} ", end='')

                            if hasattr(block, 'input') and block.input:
                                input_str = str(block.input)
                                if len(input_str) > 100:
                                    input_str = input_str[:100] + "..."
                                print(f"{Colors.DIM}{input_str}{Colors.RESET}")

                elif isinstance(message, ResultMessage):
                    if message.subtype == "error":
                        success = False
                        print(f"\n{Colors.RED}[Error]{Colors.RESET}")
                    else:
                        print(f"\n{Colors.GREEN}[Done]{Colors.RESET}")

            if interrupted:
                print(f"\n{Colors.YELLOW}[Operation interrupted via SDK - session preserved]{Colors.RESET}")
                success = False

    except KeyboardInterrupt:
        # Fallback in case interrupt handler fails
        print(f"\n{Colors.YELLOW}[Interrupted - session preserved]{Colors.RESET}")
        success = False

    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
        success = False
        if client:
            await client.__aexit__(None, None, None)
        client = None

    print()
    return success, client


# =============================================================================
# CHAT SESSION
# =============================================================================

class ChatSession:
    """Interactive chat with Claude SDK + Grok + custom tools."""
    
    def __init__(self, cwd: Path, mode: str = "acceptEdits"):
        self.cwd = cwd
        self.mode = mode
        self.tools = DEFAULT_TOOLS.copy()
        self.client = None
        self.turn_count = 0
        self.system_prompt = build_system_prompt(cwd)
        self.history_file = Path.home() / ".claude_cli_history"
        
        # Backends
        self.grok = GrokClient()
        self.active_backend = "claude"  # claude | grok
        
        # Presets
        self.presets = load_presets(cwd)
        
        # Readline
        if READLINE_AVAILABLE and self.history_file.exists():
            try:
                readline.read_history_file(self.history_file)
                readline.set_history_length(1000)
            except:
                pass
    
    def save_history(self):
        if READLINE_AVAILABLE:
            try:
                readline.write_history_file(self.history_file)
            except:
                pass
    
    def print_banner(self):
        custom_tools = list_available_tools() if CUSTOM_TOOLS_AVAILABLE else []
        
        print(f"""
{Colors.CYAN}{Colors.BOLD}Claude CLI - Beast Mode{Colors.RESET}
{Colors.DIM}Directory: {self.cwd}
Backend: {Colors.BOLD}{self.active_backend.upper()}{Colors.RESET}{Colors.DIM}
SDK Tools: {', '.join(self.tools)}
Custom Tools: {len(custom_tools)} available ({', '.join(custom_tools[:5])}{'...' if len(custom_tools) > 5 else ''})
Type /help for commands{Colors.RESET}
""")
    
    def print_help(self):
        print(f"""
{Colors.BOLD}Backend:{Colors.RESET}
  {Colors.CYAN}/claude{Colors.RESET}           Switch to Claude SDK (agentic, tools)
  {Colors.CYAN}/grok{Colors.RESET}             Switch to Grok (fast, cheap)
  {Colors.CYAN}/grok clear{Colors.RESET}       Clear Grok history

{Colors.BOLD}Session:{Colors.RESET}
  {Colors.CYAN}/clear{Colors.RESET}            Start fresh session
  {Colors.CYAN}/status{Colors.RESET}           Show current config
  {Colors.CYAN}/cwd [path]{Colors.RESET}       Show/change directory
  {Colors.CYAN}/mode <m>{Colors.RESET}         Permission mode

{Colors.BOLD}Interrupt:{Colors.RESET}
  {Colors.CYAN}Ctrl+C{Colors.RESET}            During streaming: stop gracefully, keep session
                     At prompt: show reminder (use /quit to exit)
  {Colors.CYAN}/guidance{Colors.RESET}         Show failure guidance protocol

{Colors.BOLD}Tools:{Colors.RESET}
  {Colors.CYAN}/tools{Colors.RESET}            List SDK + custom tools
  {Colors.CYAN}/tools add|rm <t>{Colors.RESET} Add/remove SDK tool

{Colors.BOLD}Direct Tool Access:{Colors.RESET}
  {Colors.CYAN}/db <cmd>{Colors.RESET}         Database: tables, query, describe, sample
  {Colors.CYAN}/memory <cmd>{Colors.RESET}     Memory: vector, grep, episodic, squirrel, search
  {Colors.CYAN}/railway <cmd>{Colors.RESET}    Railway: services, status, logs, redeploy

{Colors.BOLD}Presets:{Colors.RESET}
  {Colors.CYAN}/preset{Colors.RESET}           List presets
  {Colors.CYAN}/preset <name>{Colors.RESET}    Run preset
  {Colors.CYAN}/load <file>{Colors.RESET}      Load prompt from file

{Colors.BOLD}Input:{Colors.RESET}
  {Colors.CYAN}/paste{Colors.RESET}            Multi-line mode (END to submit)
  {Colors.CYAN}line \\{Colors.RESET}            Backslash continues line

{Colors.CYAN}/quit{Colors.RESET}               Exit
""")
    
    def handle_db(self, args: List[str]):
        """Direct database tool access."""
        if not DB_TOOLS_DIRECT:
            print(f"{Colors.RED}Database tools not available{Colors.RESET}")
            return
        
        if not args:
            print(f"""{Colors.CYAN}Database commands:{Colors.RESET}
  /db tables [schema]       List tables
  /db describe <table>      Show structure
  /db query <sql>           Run SQL query
  /db sample <table> [n]    Random sample""")
            return
        
        cmd = args[0].lower()
        
        try:
            if cmd == "tables":
                schema = args[1] if len(args) > 1 else "enterprise"
                result = db_tables(schema)
            elif cmd == "describe" and len(args) > 1:
                result = db_describe(args[1])
            elif cmd == "query" and len(args) > 1:
                sql = ' '.join(args[1:])
                result = db_query(sql)
            elif cmd == "sample" and len(args) > 1:
                n = int(args[2]) if len(args) > 2 else 5
                result = db_sample(args[1], n)
            else:
                print(f"{Colors.RED}Unknown db command: {cmd}{Colors.RESET}")
                return
            
            print(json.dumps(result, indent=2, default=str))
            
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.RESET}")
    
    def handle_memory(self, args: List[str]):
        """Direct memory tool access."""
        if not MEMORY_TOOLS_DIRECT:
            print(f"{Colors.RED}Memory tools not available{Colors.RESET}")
            return
        
        if not args:
            print(f"""{Colors.CYAN}Memory commands:{Colors.RESET}
  /memory vector <query>     Semantic search
  /memory grep <term>        Keyword search
  /memory episodic <query>   Conversation arcs
  /memory squirrel [hours]   Recent context
  /memory search <query>     All lanes""")
            return
        
        cmd = args[0].lower()
        
        try:
            if cmd == "vector" and len(args) > 1:
                query = ' '.join(args[1:])
                result = memory_vector(query)
            elif cmd == "grep" and len(args) > 1:
                result = memory_grep(args[1])
            elif cmd == "episodic" and len(args) > 1:
                query = ' '.join(args[1:])
                result = memory_episodic(query)
            elif cmd == "squirrel":
                hours = int(args[1]) if len(args) > 1 else 1
                result = memory_squirrel(hours)
            elif cmd == "search" and len(args) > 1:
                query = ' '.join(args[1:])
                result = memory_search(query)
            else:
                print(f"{Colors.RED}Unknown memory command: {cmd}{Colors.RESET}")
                return
            
            print(json.dumps(result, indent=2, default=str))
            
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.RESET}")
    
    def handle_railway(self, args: List[str]):
        """Direct Railway tool access."""
        if not RAILWAY_TOOLS_DIRECT:
            print(f"{Colors.RED}Railway tools not available (set RAILWAY_TOKEN){Colors.RESET}")
            return
        
        if not args:
            print(f"""{Colors.CYAN}Railway commands:{Colors.RESET}
  /railway services         List services
  /railway status <svc>     Deployment status
  /railway logs <svc> [n]   Get logs
  /railway redeploy <svc>   Trigger redeploy""")
            return
        
        cmd = args[0].lower()
        
        try:
            if cmd == "services":
                result = railway_services()
            elif cmd == "status" and len(args) > 1:
                result = railway_status(args[1])
            elif cmd == "logs" and len(args) > 1:
                lines = int(args[2]) if len(args) > 2 else 50
                result = railway_logs(args[1], lines)
            elif cmd == "redeploy" and len(args) > 1:
                result = railway_redeploy(args[1])
            else:
                print(f"{Colors.RED}Unknown railway command: {cmd}{Colors.RESET}")
                return
            
            print(json.dumps(result, indent=2, default=str))
            
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.RESET}")
    
    def print_guidance(self):
        """Print failure guidance protocol."""
        print(f"""
{Colors.BOLD}{Colors.YELLOW}=== FAILURE GUIDANCE PROTOCOL ==={Colors.RESET}

When operations fail or produce unexpected results:

{Colors.GREEN}1. STOP IMMEDIATELY{Colors.RESET}
   Don't continue down the same failing path

{Colors.GREEN}2. ANALYZE{Colors.RESET}
   Clearly explain what went wrong and why

{Colors.GREEN}3. QUERY USER{Colors.RESET}
   Ask specific questions to clarify intent/requirements

{Colors.GREEN}4. PROPOSE OPTIONS{Colors.RESET}
   Present 2-3 alternative approaches with trade-offs

{Colors.GREEN}5. WAIT FOR APPROVAL{Colors.RESET}
   Do NOT proceed without user confirmation

{Colors.BOLD}Example:{Colors.RESET}
{Colors.DIM}"The test suite failed with error X. This could be because:
- Approach A: dependency issue (fix: install Y)
- Approach B: configuration problem (fix: update Z)
- Approach C: architectural mismatch (fix: refactor W)

Which direction should I take? Or would you prefer a different approach?"{Colors.RESET}

{Colors.BOLD}{Colors.RED}DO NOT:{Colors.RESET}
  × Repeatedly try the same failing approach
  × Make assumptions about requirements
  × Burn tokens exploring without user guidance
  × Continue if user interrupts (Ctrl+C)

{Colors.GREEN}This protocol prevents wasted effort and ensures alignment!{Colors.RESET}
""")

    def handle_command(self, cmd: str) -> Optional[str]:
        """Handle slash command. Returns 'quit' or 'execute:...' or None."""
        parts = cmd.strip().split(maxsplit=2)
        command = parts[0].lower()

        if command in ("/quit", "/exit", "/q"):
            return "quit"

        elif command == "/help":
            self.print_help()

        elif command == "/guidance":
            self.print_guidance()
        
        elif command == "/claude":
            self.active_backend = "claude"
            print(f"{Colors.GREEN}Backend: Claude SDK (agentic){Colors.RESET}")
        
        elif command == "/grok":
            if len(parts) > 1 and parts[1] == "clear":
                self.grok.clear()
                print(f"{Colors.GREEN}Grok history cleared{Colors.RESET}")
            else:
                self.active_backend = "grok"
                print(f"{Colors.GREEN}Backend: Grok (fast/cheap){Colors.RESET}")
        
        elif command == "/clear":
            self.client = None
            self.turn_count = 0
            self.grok.clear()
            print(f"{Colors.GREEN}Session cleared{Colors.RESET}")
        
        elif command == "/status":
            custom = list_available_tools() if CUSTOM_TOOLS_AVAILABLE else []
            print(f"""
{Colors.BOLD}Status:{Colors.RESET}
  Backend: {self.active_backend}
  Directory: {self.cwd}
  Mode: {self.mode}
  SDK Tools: {', '.join(self.tools)}
  Custom Tools: {len(custom)}
  Session: {'Active' if self.client else 'None'} (turn {self.turn_count})
  Presets: {len(self.presets)}
""")
        
        elif command == "/cwd":
            if len(parts) < 2:
                print(f"{Colors.DIM}{self.cwd}{Colors.RESET}")
            else:
                new_cwd = Path(parts[1]).expanduser().resolve()
                if new_cwd.exists() and new_cwd.is_dir():
                    self.cwd = new_cwd
                    self.system_prompt = build_system_prompt(self.cwd)
                    self.presets = load_presets(self.cwd)
                    self.client = None
                    print(f"{Colors.GREEN}Directory: {self.cwd}{Colors.RESET}")
                else:
                    print(f"{Colors.RED}Not found: {parts[1]}{Colors.RESET}")
        
        elif command == "/mode":
            if len(parts) < 2:
                print(f"{Colors.DIM}Mode: {self.mode}{Colors.RESET}")
            elif parts[1] in ["acceptEdits", "bypassPermissions", "default"]:
                self.mode = parts[1]
                self.client = None
                print(f"{Colors.GREEN}Mode: {self.mode}{Colors.RESET}")
            else:
                print(f"{Colors.RED}Invalid. Use: acceptEdits, bypassPermissions, default{Colors.RESET}")
        
        elif command == "/tools":
            if len(parts) == 1:
                print(f"{Colors.CYAN}SDK Tools:{Colors.RESET} {', '.join(self.tools)}")
                print(f"{Colors.DIM}Available: {', '.join(ALL_TOOLS)}{Colors.RESET}")
                if CUSTOM_TOOLS_AVAILABLE:
                    custom = list_available_tools()
                    print(f"{Colors.CYAN}Custom Tools:{Colors.RESET} {', '.join(custom)}")
            elif parts[1] == "add" and len(parts) > 2:
                if parts[2] in ALL_TOOLS and parts[2] not in self.tools:
                    self.tools.append(parts[2])
                    self.client = None
                    print(f"{Colors.GREEN}Added: {parts[2]}{Colors.RESET}")
            elif parts[1] == "rm" and len(parts) > 2:
                if parts[2] in self.tools:
                    self.tools.remove(parts[2])
                    self.client = None
                    print(f"{Colors.GREEN}Removed: {parts[2]}{Colors.RESET}")
        
        elif command == "/db":
            db_args = parts[1].split() if len(parts) > 1 else []
            self.handle_db(db_args)
        
        elif command == "/memory":
            mem_args = parts[1].split() if len(parts) > 1 else []
            self.handle_memory(mem_args)
        
        elif command == "/railway":
            rail_args = parts[1].split() if len(parts) > 1 else []
            self.handle_railway(rail_args)
        
        elif command == "/preset":
            if len(parts) < 2:
                print(f"{Colors.CYAN}Presets:{Colors.RESET}")
                for name in sorted(self.presets.keys()):
                    preview = self.presets[name][:50].replace('\n', ' ')
                    print(f"  {Colors.BOLD}{name}{Colors.RESET}: {Colors.DIM}{preview}...{Colors.RESET}")
            elif parts[1] in self.presets:
                return f"execute:{self.presets[parts[1]]}"
            else:
                print(f"{Colors.RED}Unknown preset: {parts[1]}{Colors.RESET}")
        
        elif command == "/load":
            if len(parts) < 2:
                print(f"{Colors.RED}Usage: /load <file>{Colors.RESET}")
            else:
                fp = Path(parts[1]).expanduser()
                if not fp.is_absolute():
                    fp = self.cwd / fp
                if fp.exists():
                    content = fp.read_text()
                    print(f"{Colors.GREEN}Loaded {len(content)} chars{Colors.RESET}")
                    return f"execute:{content}"
                else:
                    print(f"{Colors.RED}Not found: {fp}{Colors.RESET}")
        
        elif command == "/paste":
            content = get_paste_input()
            if content:
                return f"execute:{content}"
        
        else:
            print(f"{Colors.RED}Unknown: {command}. Try /help{Colors.RESET}")
        
        return None
    
    async def run(self):
        """Main REPL loop."""
        self.print_banner()
        
        while True:
            try:
                # Prompt shows backend
                if self.active_backend == "grok":
                    prompt = f"{Colors.MAGENTA}Grok:{Colors.RESET} "
                else:
                    prompt = f"{Colors.CYAN}You:{Colors.RESET} "
                
                user_input = get_multiline_input(prompt)
                
                if user_input is None:
                    break
                
                if not user_input:
                    continue
                
                self.save_history()
                
                # Handle commands
                if user_input.startswith('/'):
                    result = self.handle_command(user_input)
                    if result == "quit":
                        break
                    elif result and result.startswith("execute:"):
                        user_input = result[8:]
                    else:
                        continue
                
                # Route to backend
                if self.active_backend == "grok":
                    self.grok.chat(user_input, system=self.system_prompt)
                else:
                    self.turn_count += 1
                    success, self.client = await stream_sdk_response(
                        prompt=user_input,
                        cwd=self.cwd,
                        mode=self.mode,
                        tools=self.tools,
                        system_prompt=self.system_prompt,
                        client=self.client,
                        use_custom_tools=True,
                    )
                    if not success:
                        # Don't fully clear session on interrupt - just mark as failed turn
                        print(f"{Colors.YELLOW}[Session preserved - ready for next input]{Colors.RESET}")

            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}(Ctrl+C detected - use /quit to exit, or continue working){Colors.RESET}")
        
        # Cleanup
        if self.client:
            await self.client.__aexit__(None, None, None)
        print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")


# =============================================================================
# ONE-SHOT
# =============================================================================

async def run_oneshot(prompt: str, cwd: Path, mode: str, verbose: bool) -> bool:
    """Execute single prompt."""
    system_prompt = build_system_prompt(cwd)
    
    if verbose:
        display = ' '.join(prompt.split())[:80]
        print(f"{Colors.DIM}Prompt: {display}{'...' if len(display) >= 80 else ''}{Colors.RESET}\n")
    
    success, _ = await stream_sdk_response(
        prompt=prompt,
        cwd=cwd,
        mode=mode,
        system_prompt=system_prompt,
        verbose=verbose,
    )
    
    return success


# =============================================================================
# CLI COMMANDS
# =============================================================================

def cmd_chat(args):
    cwd = Path(args.cwd).resolve() if args.cwd else find_project_root()
    session = ChatSession(cwd=cwd, mode=args.mode)
    asyncio.run(session.run())


def cmd_run(args):
    cwd = Path(args.cwd).resolve() if args.cwd else find_project_root()
    presets = load_presets(cwd)
    
    if args.preset:
        if args.preset not in presets:
            print(f"{Colors.RED}Unknown preset: {args.preset}{Colors.RESET}")
            sys.exit(1)
        prompt = presets[args.preset]
    elif args.file:
        fp = Path(args.file)
        if not fp.is_absolute():
            fp = cwd / fp
        if not fp.exists():
            print(f"{Colors.RED}Not found: {args.file}{Colors.RESET}")
            sys.exit(1)
        prompt = fp.read_text()
    elif args.prompt:
        prompt = sys.stdin.read() if args.prompt == "-" else args.prompt
    else:
        print(f"{Colors.RED}No prompt. Use positional arg, -p preset, or -f file{Colors.RESET}")
        sys.exit(1)
    
    success = asyncio.run(run_oneshot(prompt, cwd, args.mode, not args.quiet))
    sys.exit(0 if success else 1)


def cmd_db(args):
    """Direct database access."""
    if not DB_TOOLS_DIRECT:
        print(f"{Colors.RED}Database tools unavailable{Colors.RESET}")
        sys.exit(1)
    
    if not args.db_args:
        print("Usage: claude_cli db [tables|describe|query|sample] ...")
        sys.exit(1)
    
    cmd = args.db_args[0]
    rest = args.db_args[1:]
    
    try:
        if cmd == "tables":
            result = db_tables(rest[0] if rest else "enterprise")
        elif cmd == "describe" and rest:
            result = db_describe(rest[0])
        elif cmd == "query" and rest:
            result = db_query(' '.join(rest))
        elif cmd == "sample" and rest:
            n = int(rest[1]) if len(rest) > 1 else 5
            result = db_sample(rest[0], n)
        else:
            print(f"Unknown: {cmd}")
            sys.exit(1)
        
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        sys.exit(1)


def cmd_memory(args):
    """Direct memory access."""
    if not MEMORY_TOOLS_DIRECT:
        print(f"{Colors.RED}Memory tools unavailable{Colors.RESET}")
        sys.exit(1)
    
    if not args.mem_args:
        print("Usage: claude_cli memory [vector|grep|episodic|squirrel|search] ...")
        sys.exit(1)
    
    cmd = args.mem_args[0]
    rest = args.mem_args[1:]
    
    try:
        if cmd == "vector" and rest:
            result = memory_vector(' '.join(rest))
        elif cmd == "grep" and rest:
            result = memory_grep(rest[0])
        elif cmd == "episodic" and rest:
            result = memory_episodic(' '.join(rest))
        elif cmd == "squirrel":
            hours = int(rest[0]) if rest else 1
            result = memory_squirrel(hours)
        elif cmd == "search" and rest:
            result = memory_search(' '.join(rest))
        else:
            print(f"Unknown: {cmd}")
            sys.exit(1)
        
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        sys.exit(1)


def cmd_railway(args):
    """Direct Railway access."""
    if not RAILWAY_TOOLS_DIRECT:
        print(f"{Colors.RED}Railway tools unavailable (set RAILWAY_TOKEN){Colors.RESET}")
        sys.exit(1)
    
    if not args.rail_args:
        print("Usage: claude_cli railway [services|status|logs|redeploy] ...")
        sys.exit(1)
    
    cmd = args.rail_args[0]
    rest = args.rail_args[1:]
    
    try:
        if cmd == "services":
            result = railway_services()
        elif cmd == "status" and rest:
            result = railway_status(rest[0])
        elif cmd == "logs" and rest:
            lines = int(rest[1]) if len(rest) > 1 else 50
            result = railway_logs(rest[0], lines)
        elif cmd == "redeploy" and rest:
            result = railway_redeploy(rest[0])
        else:
            print(f"Unknown: {cmd}")
            sys.exit(1)
        
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        sys.exit(1)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Claude CLI - Beast Mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cwd", "-c", help="Working directory")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # chat
    chat_p = subparsers.add_parser("chat", help="Interactive REPL")
    chat_p.add_argument("--mode", "-m", default="acceptEdits")
    chat_p.set_defaults(func=cmd_chat)
    
    # run
    run_p = subparsers.add_parser("run", help="One-shot execution")
    run_p.add_argument("prompt", nargs="?")
    run_p.add_argument("--preset", "-p")
    run_p.add_argument("--file", "-f")
    run_p.add_argument("--mode", "-m", default="acceptEdits")
    run_p.add_argument("--quiet", "-q", action="store_true")
    run_p.set_defaults(func=cmd_run)
    
    # db
    db_p = subparsers.add_parser("db", help="Database operations")
    db_p.add_argument("db_args", nargs="*")
    db_p.set_defaults(func=cmd_db)
    
    # memory
    mem_p = subparsers.add_parser("memory", help="Memory search")
    mem_p.add_argument("mem_args", nargs="*")
    mem_p.set_defaults(func=cmd_memory)
    
    # railway
    rail_p = subparsers.add_parser("railway", help="Railway management")
    rail_p.add_argument("rail_args", nargs="*")
    rail_p.set_defaults(func=cmd_railway)
    
    args = parser.parse_args()
    
    # Default to chat
    if not args.command:
        args.command = "chat"
        args.mode = "acceptEdits"
        args.func = cmd_chat
    
    args.func(args)


if __name__ == "__main__":
    main()