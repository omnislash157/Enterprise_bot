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
    print("Install with: pip install claude-agent-sdk")


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
        
        # Setup readline history (if available)
        if READLINE_AVAILABLE:
            if self.history_file.exists():
                try:
                    readline.read_history_file(self.history_file)
                except Exception:
                    pass
            readline.set_history_length(1000)
        
    def print_banner(self):
        print(f"""
{Colors.CYAN}{Colors.BOLD}Claude Agent SDK - Interactive CLI{Colors.RESET}
{Colors.DIM}Working directory: {self.cwd}
Permission mode: {self.mode}
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
  {Colors.CYAN}/status{Colors.RESET}           Show current config
  {Colors.CYAN}/load <file>{Colors.RESET}      Load prompt from file and execute
  {Colors.CYAN}/prompt <name>{Colors.RESET}    Run predefined prompt (nerve0, nerve1, phase5wire, cleanup)
  {Colors.CYAN}/quit{Colors.RESET}             Exit

{Colors.BOLD}Tips:{Colors.RESET}
  - Multi-line input: end with \\ to continue on next line
  - Prompts are auto-formatted for SDK compatibility
  - Tool use is shown in real-time as Claude works

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
                    
        elif command == "/clear":
            self.session_active = False
            self.client = None
            print(f"{Colors.GREEN}Session cleared. Next message starts fresh.{Colors.RESET}")
            
        elif command == "/status":
            print(f"""
{Colors.BOLD}Current Configuration:{Colors.RESET}
  Working directory: {self.cwd}
  Permission mode: {self.mode}
  Tools: {', '.join(self.tools)}
  Session active: {self.session_active}
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

        else:
            print(f"{Colors.RED}Unknown command: {command}. Type /help for commands.{Colors.RESET}")
            
        return True

    def format_prompt(self, text: str) -> str:
        """Format multi-line input into single-line SDK-compatible prompt."""
        # Replace newlines with periods/semicolons for SDK compatibility
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        return ' '.join(lines)

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
                self.client = ClaudeSDKClient(options=options)
                await self.client.__aenter__()
                self.session_active = True
                
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
            self.session_active = False
            self.client = None
            
        print()  # Blank line after response

    def get_multiline_input(self, prompt: str) -> str:
        """Get input that may span multiple lines (ending with \\)."""
        lines = []
        current_prompt = prompt
        
        while True:
            try:
                line = input(current_prompt)
                if line.endswith('\\'):
                    lines.append(line[:-1])  # Remove trailing backslash
                    current_prompt = f"{Colors.DIM}...{Colors.RESET} "
                else:
                    lines.append(line)
                    break
            except EOFError:
                return None
                
        return '\n'.join(lines)

    async def run(self):
        """Main REPL loop."""
        self.print_banner()
        
        while True:
            try:
                # Get input
                user_input = self.get_multiline_input(f"{Colors.CYAN}You:{Colors.RESET} ")
                
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
                    if isinstance(result, tuple) and result[0] == "execute":
                        # Execute loaded prompt
                        await self.send_message(result[1])
                    continue
                
                # Send to Claude
                await self.send_message(user_input)
                
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