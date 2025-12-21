#!/usr/bin/env python3
"""
Claude Agent SDK Interactive CLI
A REPL interface for chatting with Claude Code and watching it work on your codebase.

Usage:
    python claude_chat.py [--cwd /path/to/project] [--mode acceptEdits|bypassPermissions|default]
    
Commands:
    /cwd <path>     - Change working directory
    /mode <mode>    - Change permission mode
    /tools          - List enabled tools
    /tools add|rm   - Add or remove tools
    /clear          - Clear conversation history (start fresh session)
    /help           - Show help
    /quit           - Exit
"""

import asyncio
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# readline is Unix-only, use pyreadline3 on Windows or skip
try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    try:
        import pyreadline3 as readline
        READLINE_AVAILABLE = True
    except ImportError:
        READLINE_AVAILABLE = False

import select

def input_with_timeout(prompt: str, timeout: float = 3600.0) -> str | None:
    """Non-blocking input with timeout. Returns None on timeout."""
    print(prompt, end='', flush=True)
    if sys.platform == 'win32':
        # Windows fallback - no select on stdin, use threading
        import threading
        result = [None]
        def get_input():
            try:
                result[0] = sys.stdin.readline().rstrip('\n')
            except:
                pass
        thread = threading.Thread(target=get_input, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            print(f"\n{Colors.YELLOW}[Timeout after {timeout}s - continuing]{Colors.RESET}")
            return None
        return result[0]
    else:
        # Unix - use select
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if ready:
            return sys.stdin.readline().rstrip('\n')
        print(f"\n{Colors.YELLOW}[Timeout after {timeout}s - continuing]{Colors.RESET}")
        return None


try:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        ToolUseBlock,
        TextBlock,
        ToolResultBlock,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    print("Warning: claude_agent_sdk not installed. Running in simulation mode.")

# Database tools
try:
    from db_tools import DatabaseTool, get_db
    DB_TOOLS_AVAILABLE = True
except ImportError:
    DB_TOOLS_AVAILABLE = False

# Grok API (OpenAI-compatible)
try:
    from openai import OpenAI
    GROK_AVAILABLE = True
except ImportError:
    GROK_AVAILABLE = False
    print("Note: openai not installed. Install with: pip install openai")


# ANSI colors for terminal output
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


DEFAULT_TOOLS = [
    "Read", "Write", "Edit", "Bash", 
    "Glob", "Grep", "Task"
]

ALL_TOOLS = [
    "Read", "Write", "Edit", "Bash",
    "Glob", "Grep", "WebSearch", "WebFetch",
    "Task", "Skill"
]

# Skills system - lazy-loaded documentation
SKILLS_DIR = Path(__file__).parent / "skills"
SKILLS_INDEX = """# Available Skills
| Skill | Description |
|-------|-------------|
| db | PostgreSQL queries, schema, CSV export |
| etl | ETL pipeline generation |
| excel | Excel/XLSX export with formatting |
| powerbi | Power BI dataset push, DAX |
| schema | Schema design, migrations |
| profile | Data profiling, quality checks |

Use /skill <name> to load skill docs into context."""

def load_skill(skill_name: str) -> str | None:
    """Load a skill's documentation file."""
    skill_file = SKILLS_DIR / f"{skill_name}.skill.md"
    if skill_file.exists():
        return skill_file.read_text()
    return None

def get_available_skills() -> list[str]:
    """Get list of available skill names."""
    if not SKILLS_DIR.exists():
        return []
    return [f.stem.replace(".skill", "") for f in SKILLS_DIR.glob("*.skill.md")]


# Preset prompts for common tasks
PROMPTS = {
    "nerve0": """Create src/lib/components/nervecenter/StateMonitor.svelte - a debug panel showing live state. First read src/lib/stores/session.ts to understand the store. Track isStreaming, currentStream.length, phase. Log state changes with timestamps. Cyberpunk styling with #00ff41 green accents. Add to Nerve Center page.""",

    "nerve1": """Create src/lib/components/nervecenter/LaneHeatmap.svelte showing 5 retrieval lanes: FAISS, BM25, SQUIRREL, EPISODIC, TRACES. Heat bars 0-100% based on activity. Color gradient cold to hot. Show call count and latency per lane.""",

    "nerve2": """In main.py add MetricsCollector class and emit_state_transition function. Push system_metrics via WebSocket every 5 seconds. Track lane latencies and token counts.""",

    "phase5wire": """In memory_backend.py: 1) Add import at top: 'from postgres_backend import PostgresBackend as AsyncPostgresBackend' with try/except. 2) In get_backend() postgres branch, build connection string from config or env var AZURE_PG_CONNECTION_STRING. 3) Delete the stub PostgresBackend class that raises NotImplementedError.""",

    "cleanup": """Phase 6 cleanup: 1) Move enterprise_twin.py to archive/deprecated/. 2) In config_loader.py mark context_stuffing_enabled() as deprecated, return False. 3) In test_setup.py remove EnterpriseTwin import test. 4) Update stale 'Phase 5' comments to reflect completion.""",
}


class ClaudeCLI:
    def __init__(self, cwd: str = None, mode: str = "acceptEdits", system_prompt: str = None):
        self.cwd = Path(cwd or os.getcwd()).resolve()
        self.mode = mode
        self.tools = DEFAULT_TOOLS.copy()
        self.system_prompt = system_prompt
        self.client = None
        self.session_active = False
        self.history_file = Path.home() / ".claude_chat_history"
        self.input_timeout = None  # No timeout by default, set with /timeout <seconds>
        self.db = None  # Database tool instance
        self.loaded_skills = set()  # Track which skills are loaded
        self._turn_count = 0  # Track conversation turns

        # Grok chat
        self.grok_client = None
        self.grok_history = []  # Store conversation history for Grok
        self.grok_mode = False  # Flag to indicate if we're in Grok mode

        # Setup readline history (if available)
        if READLINE_AVAILABLE:
            if self.history_file.exists():
                try:
                    readline.read_history_file(self.history_file)
                except Exception:
                    pass
            readline.set_history_length(1000)
        
    def print_banner(self):
        mode_str = f"{Colors.MAGENTA}Grok Chat{Colors.RESET}" if self.grok_mode else f"Claude ({self.mode})"
        print(f"""
{Colors.CYAN}{Colors.BOLD}Claude Agent SDK - Interactive CLI{Colors.RESET}
{Colors.DIM}Working directory: {self.cwd}
Mode: {mode_str}
Tools: {', '.join(self.tools)}
Type /help for commands, /quit to exit{Colors.RESET}
""")

    def print_help(self):
        print(f"""
{Colors.BOLD}Commands:{Colors.RESET}
  {Colors.CYAN}/cwd <path>{Colors.RESET}       Change working directory
  {Colors.CYAN}/mode <mode>{Colors.RESET}      Permission mode: acceptEdits, bypassPermissions, default
  {Colors.CYAN}/tools{Colors.RESET}            Show enabled tools
  {Colors.CYAN}/tools add <t>{Colors.RESET}    Add tool (e.g., /tools add WebSearch)
  {Colors.CYAN}/tools rm <t>{Colors.RESET}     Remove tool
  {Colors.CYAN}/clear{Colors.RESET}            Start fresh session (clears context)
  {Colors.CYAN}/timeout <s>{Colors.RESET}      Set input timeout (seconds), 'off' to disable (default: off)
  {Colors.CYAN}/status{Colors.RESET}           Show current config
  {Colors.CYAN}/load <file>{Colors.RESET}      Load prompt from file and execute
  {Colors.CYAN}/prompt <name>{Colors.RESET}    Run predefined prompt (nerve0, nerve1, phase5wire, cleanup)
  {Colors.CYAN}/db{Colors.RESET}               Connect to database
  {Colors.CYAN}/db tables{Colors.RESET}        List all tables
  {Colors.CYAN}/db describe <t>{Colors.RESET}  Show table structure
  {Colors.CYAN}/db query <sql>{Colors.RESET}   Run SQL query
  {Colors.CYAN}/db csv <t> <f>{Colors.RESET}   Export table/query to CSV file
  {Colors.CYAN}/skill{Colors.RESET}            List available skills
  {Colors.CYAN}/skill <name>{Colors.RESET}     Load skill docs into context
  {Colors.CYAN}/paste{Colors.RESET}            Multi-line paste mode (end with empty line)
  {Colors.CYAN}/batch <file>{Colors.RESET}     Run commands from file
  {Colors.CYAN}/grok{Colors.RESET}             Toggle Grok chat mode (test copy/paste)
  {Colors.CYAN}/grok clear{Colors.RESET}       Clear Grok conversation history
  {Colors.CYAN}/quit{Colors.RESET}             Exit

{Colors.BOLD}Multi-line Input:{Colors.RESET}
  - {Colors.GREEN}Backslash continuation{Colors.RESET}: End line with \\ to continue on next line
    Example: This is a long \\
             multi-line message
  - {Colors.GREEN}Direct paste{Colors.RESET}: Paste multi-line text - it will be detected automatically
  - {Colors.GREEN}/paste command{Colors.RESET}: Explicit multi-line mode (end with empty line)
  - {Colors.GREEN}Empty line submits{Colors.RESET}: After pasting, press Enter on empty line to submit

{Colors.BOLD}Tips:{Colors.RESET}
  - Conversations persist across turns - use /clear to start fresh
  - Tool use is shown in real-time as Claude works
  - No input timeout by default - take your time typing

{Colors.BOLD}Available Tools:{Colors.RESET}
  {', '.join(ALL_TOOLS)}
""")

    def handle_command(self, cmd: str) -> bool:
        """Handle slash commands. Returns True if command was handled."""
        parts = cmd.strip().split(maxsplit=2)
        command = parts[0].lower()
        
        if command == "/quit" or command == "/exit":
            return None  # Signal to exit
            
        elif command == "/help":
            self.print_help()
            
        elif command == "/cwd":
            if len(parts) < 2:
                print(f"{Colors.DIM}Current: {self.cwd}{Colors.RESET}")
            else:
                new_cwd = Path(parts[1]).expanduser().resolve()
                if new_cwd.exists() and new_cwd.is_dir():
                    self.cwd = new_cwd
                    self.session_active = False  # Force new session
                    print(f"{Colors.GREEN}Working directory: {self.cwd}{Colors.RESET}")
                else:
                    print(f"{Colors.RED}Directory not found: {parts[1]}{Colors.RESET}")
                    
        elif command == "/mode":
            if len(parts) < 2:
                print(f"{Colors.DIM}Current mode: {self.mode}{Colors.RESET}")
            else:
                mode = parts[1]
                if mode in ["acceptEdits", "bypassPermissions", "default"]:
                    self.mode = mode
                    self.session_active = False
                    print(f"{Colors.GREEN}Permission mode: {self.mode}{Colors.RESET}")
                else:
                    print(f"{Colors.RED}Invalid mode. Use: acceptEdits, bypassPermissions, default{Colors.RESET}")
                    
        elif command == "/tools":
            if len(parts) == 1:
                print(f"{Colors.DIM}Enabled: {', '.join(self.tools)}{Colors.RESET}")
            elif parts[1] == "add" and len(parts) > 2:
                tool = parts[2]
                if tool in ALL_TOOLS and tool not in self.tools:
                    self.tools.append(tool)
                    self.session_active = False
                    print(f"{Colors.GREEN}Added: {tool}{Colors.RESET}")
                elif tool in self.tools:
                    print(f"{Colors.YELLOW}Already enabled: {tool}{Colors.RESET}")
                else:
                    print(f"{Colors.RED}Unknown tool: {tool}{Colors.RESET}")
            elif parts[1] == "rm" and len(parts) > 2:
                tool = parts[2]
                if tool in self.tools:
                    self.tools.remove(tool)
                    self.session_active = False
                    print(f"{Colors.GREEN}Removed: {tool}{Colors.RESET}")
                else:
                    print(f"{Colors.RED}Not enabled: {tool}{Colors.RESET}")
                    
        elif command == "/timeout":
            if len(parts) < 2:
                timeout_str = f"{self.input_timeout}s" if self.input_timeout else "disabled"
                print(f"{Colors.DIM}Input timeout: {timeout_str}{Colors.RESET}")
            else:
                val = parts[1].lower()
                if val in ["off", "none", "0"]:
                    self.input_timeout = None
                    print(f"{Colors.GREEN}Input timeout disabled{Colors.RESET}")
                else:
                    try:
                        self.input_timeout = float(val)
                        print(f"{Colors.GREEN}Input timeout: {self.input_timeout}s{Colors.RESET}")
                    except ValueError:
                        print(f"{Colors.RED}Invalid timeout. Use number or 'off'{Colors.RESET}")

        elif command == "/clear":
            self.session_active = False
            self.client = None
            self._turn_count = 0
            print(f"{Colors.GREEN}Session cleared. Next message starts fresh.{Colors.RESET}")
            
        elif command == "/status":
            timeout_str = f"{self.input_timeout}s" if self.input_timeout else "disabled"
            session_info = f"Active (Turn {self._turn_count})" if self.session_active else "Not active"
            print(f"""
{Colors.BOLD}Current Configuration:{Colors.RESET}
  Working directory: {self.cwd}
  Permission mode: {self.mode}
  Tools: {', '.join(self.tools)}
  Session: {session_info}
  Input timeout: {timeout_str}
  Loaded skills: {', '.join(self.loaded_skills) if self.loaded_skills else 'None'}
  System prompt: {self.system_prompt[:50] + '...' if self.system_prompt else 'None'}
""")

        elif command == "/load":
            if len(parts) < 2:
                print(f"{Colors.RED}Usage: /load <filepath>{Colors.RESET}")
            else:
                filepath = Path(parts[1]).expanduser()
                if filepath.exists():
                    prompt = filepath.read_text()
                    print(f"{Colors.GREEN}Loaded {len(prompt)} chars from {filepath}{Colors.RESET}")
                    return ("execute", prompt)  # Signal to execute this prompt
                else:
                    print(f"{Colors.RED}File not found: {filepath}{Colors.RESET}")

        elif command == "/prompt":
            if len(parts) < 2:
                print(f"{Colors.DIM}Available: {', '.join(PROMPTS.keys())}{Colors.RESET}")
            else:
                name = parts[1]
                if name in PROMPTS:
                    prompt = PROMPTS[name]
                    print(f"{Colors.GREEN}Running preset: {name}{Colors.RESET}")
                    return ("execute", prompt)
                else:
                    print(f"{Colors.RED}Unknown preset: {name}. Available: {', '.join(PROMPTS.keys())}{Colors.RESET}")

        elif command == "/db":
            if not DB_TOOLS_AVAILABLE:
                print(f"{Colors.RED}Database tools not available. Install: pip install psycopg2-binary tabulate{Colors.RESET}")
            elif len(parts) == 1:
                # Just /db - connect to database
                if self.db is None:
                    self.db = DatabaseTool()
                if self.db.connect():
                    print(f"{Colors.DIM}Use /db tables, /db describe <table>, /db query <sql>{Colors.RESET}")
            elif parts[1] == "tables":
                if self.db is None:
                    self.db = DatabaseTool()
                    self.db.connect()
                self.db.tables()
            elif parts[1] == "schemas":
                if self.db is None:
                    self.db = DatabaseTool()
                    self.db.connect()
                self.db.schemas()
            elif parts[1] == "describe" and len(parts) > 2:
                if self.db is None:
                    self.db = DatabaseTool()
                    self.db.connect()
                self.db.describe(parts[2])
            elif parts[1] == "indexes" and len(parts) > 2:
                if self.db is None:
                    self.db = DatabaseTool()
                    self.db.connect()
                self.db.indexes(parts[2])
            elif parts[1] == "query" and len(parts) > 2:
                if self.db is None:
                    self.db = DatabaseTool()
                    self.db.connect()
                # Rejoin the SQL query parts
                sql = cmd.split(maxsplit=2)[2] if len(cmd.split(maxsplit=2)) > 2 else ""
                self.db.query(sql)
            elif parts[1] == "csv" and len(parts) > 3:
                if self.db is None:
                    self.db = DatabaseTool()
                    self.db.connect()
                table_or_sql = parts[2]
                filepath = parts[3]
                self.db.to_csv(table_or_sql, filepath)
            elif parts[1] == "sample" and len(parts) > 2:
                if self.db is None:
                    self.db = DatabaseTool()
                    self.db.connect()
                table = parts[2]
                n = int(parts[3]) if len(parts) > 3 else 10
                self.db.sample(table, n)
            elif parts[1] == "count" and len(parts) > 2:
                if self.db is None:
                    self.db = DatabaseTool()
                    self.db.connect()
                self.db.count(parts[2])
            elif parts[1] == "disconnect":
                if self.db:
                    self.db.disconnect()
                    self.db = None
            else:
                print(f"""{Colors.CYAN}Database commands:{Colors.RESET}
  /db              Connect to database
  /db tables       List all tables
  /db schemas      List all schemas
  /db describe <t> Show table structure
  /db indexes <t>  Show table indexes
  /db query <sql>  Run SQL query
  /db sample <t> [n] Get n random rows (default 10)
  /db count <t>    Count rows in table
  /db csv <t> <f>  Export table to CSV file
  /db disconnect   Close connection""")

        elif command == "/skill":
            available = get_available_skills()
            if len(parts) == 1:
                # List skills
                print(f"\n{Colors.CYAN}Available Skills:{Colors.RESET}")
                print(SKILLS_INDEX)
                if self.loaded_skills:
                    print(f"\n{Colors.GREEN}Loaded:{Colors.RESET} {', '.join(self.loaded_skills)}")
            else:
                skill_name = parts[1].lower()
                if skill_name in available:
                    skill_doc = load_skill(skill_name)
                    if skill_doc:
                        self.loaded_skills.add(skill_name)
                        print(f"{Colors.GREEN}Loaded skill: {skill_name}{Colors.RESET}")
                        print(f"{Colors.DIM}({len(skill_doc)} chars added to context){Colors.RESET}")
                        # Return the skill doc to be injected into the next prompt
                        return ("skill_loaded", skill_name, skill_doc)
                    else:
                        print(f"{Colors.RED}Could not load skill: {skill_name}{Colors.RESET}")
                else:
                    print(f"{Colors.RED}Unknown skill: {skill_name}{Colors.RESET}")
                    print(f"{Colors.DIM}Available: {', '.join(available)}{Colors.RESET}")

        elif command == "/skills":
            # Alias for /skill
            print(f"\n{Colors.CYAN}Available Skills:{Colors.RESET}")
            print(SKILLS_INDEX)
            if self.loaded_skills:
                print(f"\n{Colors.GREEN}Loaded:{Colors.RESET} {', '.join(self.loaded_skills)}")

        elif command == "/paste":
            # Multi-line paste mode - read until empty line or EOF
            print(f"{Colors.DIM}Paste mode: Enter commands/text, end with empty line or Ctrl+D{Colors.RESET}")
            lines = []
            while True:
                try:
                    line = input(f"{Colors.DIM}...{Colors.RESET} ")
                    if not line.strip():  # Empty line ends paste
                        break
                    lines.append(line)
                except EOFError:
                    break
            if lines:
                combined = '\n'.join(lines)
                print(f"{Colors.GREEN}Captured {len(lines)} lines ({len(combined)} chars){Colors.RESET}")
                return ("execute", combined)

        elif command == "/batch":
            # Execute multiple commands from a file
            if len(parts) < 2:
                print(f"{Colors.RED}Usage: /batch <filepath>{Colors.RESET}")
            else:
                filepath = Path(parts[1]).expanduser()
                if filepath.exists():
                    commands = filepath.read_text().strip().split('\n')
                    commands = [c.strip() for c in commands if c.strip() and not c.startswith('#')]
                    print(f"{Colors.GREEN}Loaded {len(commands)} commands from {filepath}{Colors.RESET}")
                    # Return batch for processing
                    return ("batch", commands)
                else:
                    print(f"{Colors.RED}File not found: {filepath}{Colors.RESET}")

        elif command == "/grok":
            if not GROK_AVAILABLE:
                print(f"{Colors.RED}Grok requires openai package. Install with: pip install openai{Colors.RESET}")
            elif len(parts) > 1 and parts[1] == "clear":
                # Clear Grok history
                self.grok_history = []
                print(f"{Colors.GREEN}Grok conversation history cleared{Colors.RESET}")
            else:
                # Toggle Grok mode
                self.grok_mode = not self.grok_mode
                if self.grok_mode:
                    # Initialize Grok client if needed
                    if self.grok_client is None:
                        api_key = os.environ.get("XAI_API_KEY")
                        if not api_key:
                            print(f"{Colors.RED}XAI_API_KEY environment variable not set{Colors.RESET}")
                            print(f"{Colors.DIM}Get your API key from: https://console.x.ai/{Colors.RESET}")
                            self.grok_mode = False
                        else:
                            self.grok_client = OpenAI(
                                api_key=api_key,
                                base_url="https://api.x.ai/v1"
                            )
                            print(f"{Colors.GREEN}Grok mode enabled!{Colors.RESET}")
                            print(f"{Colors.DIM}This is a simple chat mode - perfect for testing copy/paste!{Colors.RESET}")
                            print(f"{Colors.DIM}Type /grok again to return to Claude mode{Colors.RESET}")
                            print(f"{Colors.DIM}Use /grok clear to reset conversation{Colors.RESET}")
                else:
                    print(f"{Colors.GREEN}Grok mode disabled - back to Claude{Colors.RESET}")

        else:
            print(f"{Colors.RED}Unknown command: {command}. Type /help for commands.{Colors.RESET}")

        return True

    def format_prompt(self, text: str) -> str:
        """Format multi-line input for SDK compatibility.

        Preserves formatting for pasted content while ensuring SDK compatibility.
        """
        # Don't strip newlines - the SDK can handle them
        return text.strip()

    async def send_message(self, prompt: str):
        """Send message and stream response."""
        if not SDK_AVAILABLE:
            print(f"\n{Colors.MAGENTA}[Simulation Mode]{Colors.RESET}")
            print(f"{Colors.DIM}Would send to SDK:{Colors.RESET}")
            print(f"  cwd: {self.cwd}")
            print(f"  mode: {self.mode}")
            print(f"  tools: {self.tools}")
            print(f"  prompt: {prompt[:100]}...")
            return
            
        # Format prompt for SDK
        formatted = self.format_prompt(prompt)
        
        options = ClaudeAgentOptions(
            cwd=str(self.cwd),
            allowed_tools=self.tools,
            permission_mode=self.mode,
            system_prompt=self.system_prompt
        )
        
        print()  # Blank line before response

        try:
            if not self.session_active or self.client is None:
                # Start new session
                print(f"{Colors.DIM}[Starting new session]{Colors.RESET}")
                self.client = ClaudeSDKClient(options=options)
                await self.client.__aenter__()
                self.session_active = True
                self._turn_count = 0
            else:
                # Continuing existing session
                print(f"{Colors.DIM}[Turn {self._turn_count}]{Colors.RESET}")

            # Increment turn count for next message
            self._turn_count += 1

            await self.client.query(formatted)
            
            current_text = ""
            async for message in self.client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            # Stream text output
                            new_text = block.text
                            if new_text.startswith(current_text):
                                # Print only new content
                                print(new_text[len(current_text):], end='', flush=True)
                            else:
                                print(new_text, end='', flush=True)
                            current_text = new_text
                            
                        elif isinstance(block, ToolUseBlock):
                            # Show tool invocation
                            print(f"\n{Colors.YELLOW}[{block.name}]{Colors.RESET} ", end='', flush=True)
                            if hasattr(block, 'input') and block.input:
                                # Truncate long inputs
                                input_str = str(block.input)
                                if len(input_str) > 100:
                                    input_str = input_str[:100] + "..."
                                print(f"{Colors.DIM}{input_str}{Colors.RESET}")
                            
                elif isinstance(message, ResultMessage):
                    # Session complete
                    if message.subtype == "success":
                        print(f"\n{Colors.GREEN}[Done]{Colors.RESET}")
                    elif message.subtype == "error":
                        print(f"\n{Colors.RED}[Error]{Colors.RESET}")
                        
        except Exception as e:
            print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
            print(f"{Colors.YELLOW}Session reset - next message will start fresh{Colors.RESET}")
            self.session_active = False
            self.client = None
            self._turn_count = 0
            
        print()  # Blank line after response

    def send_grok_message(self, prompt: str):
        """Send message to Grok and display response."""
        if not GROK_AVAILABLE or self.grok_client is None:
            print(f"{Colors.RED}Grok not available{Colors.RESET}")
            return

        # Add user message to history
        self.grok_history.append({
            "role": "user",
            "content": prompt
        })

        print()  # Blank line before response
        print(f"{Colors.MAGENTA}Grok:{Colors.RESET} ", end='', flush=True)

        try:
            # Call Grok API with streaming
            response = self.grok_client.chat.completions.create(
                model="grok-beta",
                messages=self.grok_history,
                stream=True,
            )

            # Stream the response
            full_response = ""
            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    print(content, end='', flush=True)
                    full_response += content

            print()  # Newline after response

            # Add assistant response to history
            self.grok_history.append({
                "role": "assistant",
                "content": full_response
            })

        except Exception as e:
            print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")

        print()  # Blank line after response

    def get_multiline_input(self, prompt: str, timeout: float = None) -> str:
        """Get input that may span multiple lines.

        Args:
            prompt: The prompt to display
            timeout: Optional timeout in seconds. None = wait forever (default behavior)

        Supports:
        - Shift-Enter: Add a line break and continue on next line
        - Backslash continuation (line ending with \\)
        - Multi-line paste (detected automatically)
        - Enter alone: Submit the input
        - /paste command for explicit multi-line mode
        """
        lines = []
        current_prompt = prompt

        while True:
            try:
                if timeout is not None:
                    line = input_with_timeout(current_prompt, timeout)
                    if line is None:
                        # Timeout - return what we have or None
                        return '\n'.join(lines) if lines else None
                else:
                    # Read input with multi-line paste support
                    # This handles pasting multiple lines at once
                    line = input(current_prompt)

                # Check if we got an empty line and we already have content
                if not line and lines:
                    # Empty line after content - user wants to submit
                    break

                # Check if line contains embedded newlines (paste detection)
                # Note: Standard input() doesn't preserve newlines in paste,
                # but some terminals may. We'll also check stdin buffer.
                if '\n' in line:
                    # Multi-line paste detected - split and add all lines
                    paste_lines = line.split('\n')
                    lines.extend(paste_lines)
                    # Show visual feedback for paste
                    print(f"{Colors.DIM}[Pasted {len(paste_lines)} lines]{Colors.RESET}")

                    # Check if there's more data in stdin (multi-line paste)
                    # Read any remaining buffered lines
                    import sys
                    if sys.platform != 'win32':
                        import select
                        while select.select([sys.stdin], [], [], 0)[0]:
                            try:
                                extra_line = sys.stdin.readline().rstrip('\n')
                                if extra_line:
                                    lines.append(extra_line)
                                else:
                                    break
                            except:
                                break
                    print(f"{Colors.DIM}[Total: {len(lines)} lines - Press Enter to submit or continue typing]{Colors.RESET}")
                    current_prompt = f"{Colors.DIM}...{Colors.RESET} "
                    continue
                elif line.endswith('\\'):
                    # Backslash continuation - remove backslash and continue
                    lines.append(line[:-1])
                    current_prompt = f"{Colors.DIM}...{Colors.RESET} "
                else:
                    # Regular line
                    lines.append(line)
                    # If we have multiple lines already, ask if they want to continue
                    if len(lines) > 1:
                        # Already in multi-line mode, pressing enter alone submits
                        break
                    else:
                        # Single line, submit immediately unless it ends with backslash
                        break

            except EOFError:
                # Ctrl+D pressed
                if lines:
                    print(f"\n{Colors.DIM}[EOF - submitting {len(lines)} lines]{Colors.RESET}")
                    break
                return None
            except KeyboardInterrupt:
                # Ctrl+C pressed
                print(f"\n{Colors.DIM}[Cancelled]{Colors.RESET}")
                return None

        result = '\n'.join(lines)
        return result if result else None

    async def run(self):
        """Main REPL loop."""
        self.print_banner()
        
        while True:
            try:
                # Get input
                user_input = self.get_multiline_input(f"{Colors.CYAN}You:{Colors.RESET} ", self.input_timeout)
                
                if user_input is None:
                    break
                    
                if not user_input.strip():
                    continue
                    
                # Save to history
                if READLINE_AVAILABLE:
                    try:
                        readline.write_history_file(self.history_file)
                    except Exception:
                        pass
                
                # Handle commands
                if user_input.startswith('/'):
                    result = self.handle_command(user_input)
                    if result is None:  # /quit
                        break
                    if isinstance(result, tuple):
                        if result[0] == "execute":
                            # Execute loaded prompt
                            await self.send_message(result[1])
                        elif result[0] == "skill_loaded":
                            # Skill loaded - store for next message context
                            skill_name, skill_doc = result[1], result[2]
                            # Inject skill context into system prompt temporarily
                            print(f"{Colors.DIM}Skill '{skill_name}' ready. Your next message will include this context.{Colors.RESET}")
                            # Store pending skill context
                            if not hasattr(self, '_pending_skill_context'):
                                self._pending_skill_context = ""
                            self._pending_skill_context += f"\n\n---\n# Skill: {skill_name}\n{skill_doc}"
                        elif result[0] == "batch":
                            # Execute batch commands sequentially
                            for i, batch_cmd in enumerate(result[1], 1):
                                print(f"{Colors.DIM}[{i}/{len(result[1])}] {batch_cmd[:50]}...{Colors.RESET}")
                                if batch_cmd.startswith('/'):
                                    batch_result = self.handle_command(batch_cmd)
                                    if isinstance(batch_result, tuple) and batch_result[0] == "execute":
                                        await self.send_message(batch_result[1])
                                else:
                                    await self.send_message(batch_cmd)
                    continue

                # Check if we're in Grok mode
                if self.grok_mode:
                    # Send to Grok (synchronous)
                    self.send_grok_message(user_input)
                else:
                    # Check for pending skill context and prepend to message
                    skill_prefix = ""
                    if hasattr(self, '_pending_skill_context') and self._pending_skill_context:
                        skill_prefix = f"[SKILL CONTEXT]{self._pending_skill_context}\n[END SKILL CONTEXT]\n\n"
                        self._pending_skill_context = ""  # Clear after use

                    # Send to Claude
                    await self.send_message(skill_prefix + user_input)
                
            except KeyboardInterrupt:
                print(f"\n{Colors.DIM}(Use /quit to exit){Colors.RESET}")
                continue
                
        # Cleanup
        if self.client:
            await self.client.__aexit__(None, None, None)
        print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")


async def main():
    parser = argparse.ArgumentParser(
        description="Interactive CLI for Claude Agent SDK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python claude_chat.py
  python claude_chat.py --cwd /path/to/project
  python claude_chat.py --mode bypassPermissions
  python claude_chat.py --cwd ~/code/myproject --mode acceptEdits
        """
    )
    parser.add_argument(
        "--cwd", "-c",
        help="Working directory for Claude to operate in",
        default=os.getcwd()
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["acceptEdits", "bypassPermissions", "default"],
        default="acceptEdits",
        help="Permission mode (default: acceptEdits)"
    )
    parser.add_argument(
        "--system", "-s",
        help="Custom system prompt",
        default=None
    )
    
    args = parser.parse_args()
    
    cli = ClaudeCLI(
        cwd=args.cwd,
        mode=args.mode,
        system_prompt=args.system
    )
    
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())