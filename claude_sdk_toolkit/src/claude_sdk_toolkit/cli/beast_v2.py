#!/usr/bin/env python3
"""
Beast CLI v2 - Direct Anthropic SDK with Lazy Skill Loading

A clean Claude chat interface that:
1. Loads skill indexes (SKILL.md) into system prompt - lightweight metadata
2. Provides tools as direct Python functions - no MCP overhead  
3. Uses Anthropic SDK directly - no Claude Code CLI subprocess
4. Lazy-loads skill content via 'view' tool on demand

Usage:
    python beast_v2.py chat
    python beast_v2.py chat --skills-dir ./skills
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any, Callable

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Anthropic SDK
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("Error: anthropic package required. Run: pip install anthropic")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 8192
SKILLS_DIR = Path(os.getenv("SKILLS_DIR", "./skills"))

# Colors for terminal
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


# =============================================================================
# SKILL LOADER - Lazy Loading Architecture
# =============================================================================

class SkillLoader:
    """
    Loads skill indexes (SKILL.md) for system prompt context.
    Actual skill content is lazy-loaded via the view tool.
    """
    
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skill_indexes: dict[str, str] = {}
        self._load_indexes()
    
    def _load_indexes(self):
        """Load all SKILL.md files as lightweight indexes."""
        if not self.skills_dir.exists():
            return
            
        # Look for SKILL.md files
        for skill_file in self.skills_dir.glob("**/SKILL.md"):
            skill_name = skill_file.parent.name if skill_file.parent != self.skills_dir else "root"
            try:
                content = skill_file.read_text(encoding='utf-8')
                self.skill_indexes[skill_name] = content
            except Exception as e:
                print(f"{Colors.YELLOW}Warning: Could not load {skill_file}: {e}{Colors.RESET}")
        
        # Also load .skill.md files directly in skills dir
        for skill_file in self.skills_dir.glob("*.skill.md"):
            skill_name = skill_file.stem.replace('.skill', '')
            try:
                content = skill_file.read_text(encoding='utf-8')
                self.skill_indexes[skill_name] = content
            except Exception as e:
                print(f"{Colors.YELLOW}Warning: Could not load {skill_file}: {e}{Colors.RESET}")
    
    def get_system_prompt_context(self) -> str:
        """Generate skill context for system prompt - indexes only."""
        if not self.skill_indexes:
            return ""
        
        lines = [
            "",
            "## Available Skills",
            "",
            "You have access to the following skill indexes. Use the `view` tool to lazy-load specific files when you need detailed content.",
            "",
        ]
        
        for name, content in self.skill_indexes.items():
            # Truncate to first ~50 lines for index preview
            preview_lines = content.split('\n')[:50]
            preview = '\n'.join(preview_lines)
            if len(content.split('\n')) > 50:
                preview += f"\n... ({len(content.split(chr(10))) - 50} more lines, use view to see full content)"
            
            lines.append(f"### Skill: {name}")
            lines.append("```")
            lines.append(preview)
            lines.append("```")
            lines.append("")
        
        return '\n'.join(lines)


# =============================================================================
# TOOL DEFINITIONS - Direct Python Functions
# =============================================================================

# Tool registry
TOOLS: dict[str, Callable] = {}
TOOL_SCHEMAS: list[dict] = []


def register_tool(name: str, description: str, parameters: dict):
    """Decorator to register a tool with its schema."""
    def decorator(func: Callable):
        TOOLS[name] = func
        TOOL_SCHEMAS.append({
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": parameters,
                "required": [k for k, v in parameters.items() if not v.get("optional", False)]
            }
        })
        return func
    return decorator


# -----------------------------------------------------------------------------
# Core Tools
# -----------------------------------------------------------------------------

@register_tool(
    name="view",
    description="View contents of a file or directory. Use this to lazy-load skill content or inspect files.",
    parameters={
        "path": {"type": "string", "description": "Path to file or directory to view"},
        "max_lines": {"type": "integer", "description": "Maximum lines to return (default: 200)", "optional": True}
    }
)
async def tool_view(path: str, max_lines: int = 200) -> str:
    """View file or directory contents."""
    target = Path(path).expanduser()
    
    if not target.exists():
        return f"Error: Path does not exist: {path}"
    
    if target.is_dir():
        # List directory
        items = []
        for item in sorted(target.iterdir()):
            prefix = "[DIR] " if item.is_dir() else "[FILE]"
            size = ""
            if item.is_file():
                size = f" ({item.stat().st_size:,} bytes)"
            items.append(f"{prefix} {item.name}{size}")
        return f"Directory: {path}\n\n" + '\n'.join(items[:100])
    
    else:
        # Read file
        try:
            content = target.read_text(encoding='utf-8')
            lines = content.split('\n')
            if len(lines) > max_lines:
                truncated = '\n'.join(lines[:max_lines])
                return f"{truncated}\n\n... truncated ({len(lines) - max_lines} more lines)"
            return content
        except UnicodeDecodeError:
            return f"Error: Binary file, cannot display as text: {path}"
        except Exception as e:
            return f"Error reading file: {e}"


@register_tool(
    name="bash",
    description="Execute a bash/shell command and return output.",
    parameters={
        "command": {"type": "string", "description": "Command to execute"},
        "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30)", "optional": True}
    }
)
async def tool_bash(command: str, timeout: int = 30) -> str:
    """Execute shell command."""
    import subprocess
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd()
        )
        
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        
        return output.strip() or "(no output)"
        
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {e}"


@register_tool(
    name="write",
    description="Write content to a file. Creates parent directories if needed.",
    parameters={
        "path": {"type": "string", "description": "Path to file to write"},
        "content": {"type": "string", "description": "Content to write to file"}
    }
)
async def tool_write(path: str, content: str) -> str:
    """Write content to file."""
    target = Path(path).expanduser()
    
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


@register_tool(
    name="glob",
    description="Find files matching a glob pattern.",
    parameters={
        "pattern": {"type": "string", "description": "Glob pattern (e.g., '**/*.py')"},
        "root": {"type": "string", "description": "Root directory to search from", "optional": True}
    }
)
async def tool_glob(pattern: str, root: str = ".") -> str:
    """Find files matching pattern."""
    root_path = Path(root).expanduser()
    
    try:
        matches = list(root_path.glob(pattern))[:100]  # Limit results
        if not matches:
            return f"No files found matching: {pattern}"
        
        result = f"Found {len(matches)} files:\n\n"
        for match in matches:
            result += f"  {match}\n"
        
        return result
    except Exception as e:
        return f"Error in glob: {e}"


@register_tool(
    name="grep",
    description="Search for text pattern in files.",
    parameters={
        "pattern": {"type": "string", "description": "Text or regex pattern to search for"},
        "path": {"type": "string", "description": "File or directory to search"},
        "recursive": {"type": "boolean", "description": "Search recursively in directories", "optional": True}
    }
)
async def tool_grep(pattern: str, path: str, recursive: bool = True) -> str:
    """Search for pattern in files."""
    import re
    
    target = Path(path).expanduser()
    results = []
    
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex pattern: {e}"
    
    def search_file(file_path: Path):
        try:
            content = file_path.read_text(encoding='utf-8')
            for i, line in enumerate(content.split('\n'), 1):
                if regex.search(line):
                    results.append(f"{file_path}:{i}: {line.strip()[:100]}")
                    if len(results) >= 50:
                        return
        except:
            pass
    
    if target.is_file():
        search_file(target)
    elif target.is_dir():
        glob_pattern = "**/*" if recursive else "*"
        for file_path in target.glob(glob_pattern):
            if file_path.is_file() and file_path.suffix in ('.py', '.md', '.txt', '.json', '.yaml', '.yml', '.toml'):
                search_file(file_path)
                if len(results) >= 50:
                    break
    
    if not results:
        return f"No matches found for: {pattern}"
    
    return f"Found {len(results)} matches:\n\n" + '\n'.join(results)


# -----------------------------------------------------------------------------
# Database Tools (if available)
# -----------------------------------------------------------------------------

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv("AZURE_PG_HOST", "localhost"),
        port=int(os.getenv("AZURE_PG_PORT", "5432")),
        database=os.getenv("AZURE_PG_DATABASE", "postgres"),
        user=os.getenv("AZURE_PG_USER", "postgres"),
        password=os.getenv("AZURE_PG_PASSWORD", ""),
        sslmode=os.getenv("AZURE_PG_SSLMODE", "require"),
        connect_timeout=10,
    )


if DB_AVAILABLE:
    @register_tool(
        name="db_query",
        description="Execute SQL query against PostgreSQL database.",
        parameters={
            "query": {"type": "string", "description": "SQL query to execute"},
            "limit": {"type": "integer", "description": "Max rows to return (default: 100)", "optional": True}
        }
    )
    async def tool_db_query(query: str, limit: int = 100) -> str:
        """Execute SQL query."""
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Add LIMIT if SELECT without LIMIT
            if query.strip().upper().startswith("SELECT") and "LIMIT" not in query.upper():
                query = f"{query.rstrip(';')} LIMIT {limit}"
            
            cur.execute(query)
            
            if cur.description:
                rows = [dict(r) for r in cur.fetchall()]
                # Convert datetimes
                for row in rows:
                    for k, v in row.items():
                        if isinstance(v, datetime):
                            row[k] = v.isoformat()
                
                result = f"Returned {len(rows)} rows:\n\n"
                result += json.dumps(rows[:20], indent=2, default=str)
                if len(rows) > 20:
                    result += f"\n\n... and {len(rows) - 20} more rows"
                return result
            else:
                conn.commit()
                return f"Query executed. Rows affected: {cur.rowcount}"
                
        except Exception as e:
            return f"Database error: {e}"
        finally:
            if 'conn' in locals():
                conn.close()

    @register_tool(
        name="db_tables",
        description="List all tables in a database schema.",
        parameters={
            "schema": {"type": "string", "description": "Schema name (default: 'public')", "optional": True}
        }
    )
    async def tool_db_tables(schema: str = "public") -> str:
        """List database tables."""
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT table_name, 
                       pg_size_pretty(pg_total_relation_size(quote_ident(table_schema)||'.'||quote_ident(table_name))) as size
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """, (schema,))
            
            tables = cur.fetchall()
            result = f"Tables in schema '{schema}':\n\n"
            for t in tables:
                result += f"  - {t['table_name']} ({t['size']})\n"
            
            return result
            
        except Exception as e:
            return f"Database error: {e}"
        finally:
            if 'conn' in locals():
                conn.close()


# =============================================================================
# CHAT SESSION
# =============================================================================

class ChatSession:
    """Interactive chat session with Claude."""
    
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        skills_dir: Path = SKILLS_DIR,
        system_prompt: str = None
    ):
        self.client = anthropic.Anthropic()
        self.model = model
        self.messages: list[dict] = []
        self.skill_loader = SkillLoader(skills_dir)
        self.custom_system_prompt = system_prompt
        
    def _build_system_prompt(self) -> str:
        """Build full system prompt with skill context."""
        base = self.custom_system_prompt or """You are Claude, an AI assistant with access to tools and skills.

You can use tools to:
- View files and directories
- Execute shell commands  
- Search code and files
- Query databases (if configured)

When you need detailed information from a skill, use the `view` tool to load the specific file."""

        skill_context = self.skill_loader.get_system_prompt_context()
        
        return base + skill_context
    
    async def _execute_tool(self, name: str, input_data: dict) -> str:
        """Execute a tool and return result."""
        if name not in TOOLS:
            return f"Error: Unknown tool '{name}'"
        
        try:
            # Get the tool function
            tool_func = TOOLS[name]
            
            # Call it with the input data as kwargs
            result = await tool_func(**input_data)
            return result
            
        except Exception as e:
            return f"Tool error: {e}"
    
    async def send_message(self, user_message: str) -> str:
        """Send message and get response, handling tool calls."""
        
        # Add user message
        self.messages.append({"role": "user", "content": user_message})
        
        # Keep processing until we get a final response (no more tool calls)
        while True:
            # Call Claude
            response = self.client.messages.create(
                model=self.model,
                max_tokens=DEFAULT_MAX_TOKENS,
                system=self._build_system_prompt(),
                tools=TOOL_SCHEMAS,
                messages=self.messages
            )
            
            # Check stop reason
            if response.stop_reason == "end_turn":
                # Extract text response
                text_parts = []
                for block in response.content:
                    if hasattr(block, 'text'):
                        text_parts.append(block.text)
                
                # Add assistant message to history
                self.messages.append({"role": "assistant", "content": response.content})
                
                return '\n'.join(text_parts)
            
            elif response.stop_reason == "tool_use":
                # Process tool calls
                tool_results = []
                
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"{Colors.YELLOW}[Tool: {block.name}]{Colors.RESET} ", end='', flush=True)
                        
                        # Execute tool
                        result = await self._execute_tool(block.name, block.input)
                        
                        # Truncate long results for display
                        display_result = result[:100] + "..." if len(result) > 100 else result
                        print(f"{Colors.DIM}{display_result}{Colors.RESET}")
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                
                # Add assistant message with tool use
                self.messages.append({"role": "assistant", "content": response.content})
                
                # Add tool results
                self.messages.append({"role": "user", "content": tool_results})
                
                # Continue loop to get Claude's response to tool results
                
            else:
                # Unexpected stop reason
                return f"Unexpected stop reason: {response.stop_reason}"
    
    def print_banner(self):
        """Print welcome banner."""
        print(f"\n{Colors.CYAN}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}  BEAST CLI v2 - Direct Anthropic SDK{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.DIM}Model: {self.model}{Colors.RESET}")
        print(f"{Colors.DIM}Skills loaded: {len(self.skill_loader.skill_indexes)}{Colors.RESET}")
        print(f"{Colors.DIM}Tools available: {', '.join(TOOLS.keys())}{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.DIM}Commands: /quit, /clear, /skills, /tools{Colors.RESET}")
        print()
    
    async def run(self):
        """Run interactive chat loop."""
        self.print_banner()
        
        while True:
            try:
                # Get user input
                user_input = input(f"{Colors.GREEN}You:{Colors.RESET} ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith('/'):
                    cmd = user_input.lower()
                    
                    if cmd in ('/quit', '/exit', '/q'):
                        print(f"\n{Colors.CYAN}Goodbye!{Colors.RESET}\n")
                        break
                    
                    elif cmd == '/clear':
                        self.messages.clear()
                        print(f"{Colors.DIM}Conversation cleared.{Colors.RESET}\n")
                        continue
                    
                    elif cmd == '/skills':
                        print(f"\n{Colors.CYAN}Loaded Skills:{Colors.RESET}")
                        for name in self.skill_loader.skill_indexes:
                            print(f"  - {name}")
                        print()
                        continue
                    
                    elif cmd == '/tools':
                        print(f"\n{Colors.CYAN}Available Tools:{Colors.RESET}")
                        for name in TOOLS:
                            print(f"  - {name}")
                        print()
                        continue
                    
                    else:
                        print(f"{Colors.YELLOW}Unknown command: {cmd}{Colors.RESET}\n")
                        continue
                
                # Send message and get response
                print(f"\n{Colors.BLUE}Claude:{Colors.RESET} ", end='', flush=True)
                
                response = await self.send_message(user_input)
                print(response)
                print()
                
            except KeyboardInterrupt:
                print(f"\n\n{Colors.CYAN}Goodbye!{Colors.RESET}\n")
                break
            except EOFError:
                break
            except Exception as e:
                print(f"\n{Colors.RED}Error: {e}{Colors.RESET}\n")


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Beast CLI v2 - Claude chat with lazy skill loading",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Chat command
    chat_parser = subparsers.add_parser('chat', help='Start interactive chat')
    chat_parser.add_argument('--model', '-m', default=DEFAULT_MODEL,
                            help=f'Model to use (default: {DEFAULT_MODEL})')
    chat_parser.add_argument('--skills-dir', '-s', type=Path, default=SKILLS_DIR,
                            help=f'Skills directory (default: {SKILLS_DIR})')
    chat_parser.add_argument('--system-prompt', '-p', type=str,
                            help='Custom system prompt')
    
    # Parse args
    args = parser.parse_args()
    
    if args.command == 'chat':
        session = ChatSession(
            model=args.model,
            skills_dir=args.skills_dir,
            system_prompt=args.system_prompt
        )
        asyncio.run(session.run())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()