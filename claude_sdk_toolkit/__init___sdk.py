"""
SDK Custom Tools - Unified Registration

Aggregates all SDK-compatible custom tools into a single MCP server.

Tools available (12 total):
- railway_*: Railway deployment management (3 tools)
- memory_*: CogTwin RAG lane access (5 tools)
- db_*: PostgreSQL database operations (4 tools)

Usage:
    from claude_sdk_toolkit import create_mcp_server, list_all_tools

    # Create MCP server with all tools
    server = create_mcp_server()

    # Or selectively include tool groups
    server = create_mcp_server(
        include_railway=True,
        include_memory=True,
        include_db=True
    )

    # Use with Claude SDK agent
    from claude_agent_sdk import ClaudeAgentOptions
    options = ClaudeAgentOptions(
        mcp_servers=[server],
        ...
    )
"""

import os
from typing import List, Optional
from pathlib import Path

# Auto-load .env file if it exists
try:
    from dotenv import load_dotenv
    # Look for .env in project root (parent of claude_sdk_toolkit)
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment variables from {env_path}")
    else:
        # Try current directory
        load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not installed. Install with: pip install python-dotenv")
    print("   Environment variables must be set manually.")

# Check SDK availability
try:
    from claude_agent_sdk import create_sdk_mcp_server
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    create_sdk_mcp_server = None

# Import all SDK tool modules
try:
    # Try relative imports first (when imported as package)
    from .railway_tools_sdk import TOOLS as RAILWAY_TOOLS
    from .memory_tools_sdk import TOOLS as MEMORY_TOOLS
    from .db_tools_sdk import TOOLS as DB_TOOLS
except ImportError:
    # Fall back to absolute imports (when run as script)
    from railway_tools_sdk import TOOLS as RAILWAY_TOOLS
    from memory_tools_sdk import TOOLS as MEMORY_TOOLS
    from db_tools_sdk import TOOLS as DB_TOOLS


def create_mcp_server(
    include_railway: bool = True,
    include_memory: bool = True,
    include_db: bool = True,
    server_name: str = "enterprise-tools"
):
    """
    Create MCP server with selected tool groups.

    Args:
        include_railway: Include Railway deployment tools (requires RAILWAY_TOKEN)
        include_memory: Include CogTwin memory/RAG tools
        include_db: Include PostgreSQL database tools
        server_name: Name for the MCP server

    Returns:
        MCP server instance ready for SDK agent registration

    Example:
        >>> server = create_mcp_server()
        >>> from claude_agent_sdk import ClaudeAgent
        >>> agent = ClaudeAgent(mcp_servers=[server])
    """
    if not SDK_AVAILABLE:
        raise RuntimeError(
            "claude_agent_sdk not installed. "
            "Install with: pip install claude-agent-sdk"
        )

    tools = []

    if include_railway and os.getenv("RAILWAY_TOKEN"):
        tools.extend(RAILWAY_TOOLS)
        print(f"✅ Loaded {len(RAILWAY_TOOLS)} Railway tools")
    elif include_railway:
        print("⚠️  Railway tools skipped: RAILWAY_TOKEN not set")

    if include_memory:
        tools.extend(MEMORY_TOOLS)
        print(f"✅ Loaded {len(MEMORY_TOOLS)} Memory tools")

    if include_db:
        # Check if DB credentials are set
        if os.getenv("AZURE_PG_HOST") and os.getenv("AZURE_PG_PASSWORD"):
            tools.extend(DB_TOOLS)
            print(f"✅ Loaded {len(DB_TOOLS)} Database tools")
        else:
            print("⚠️  Database tools skipped: Azure PG credentials not set")

    if not tools:
        raise RuntimeError("No tools available. Check environment variables.")

    print(f"\n🎯 Total tools registered: {len(tools)}")
    return create_sdk_mcp_server(tools, name=server_name)


def list_all_tools() -> List[dict]:
    """
    List all available tools with their metadata.

    Returns:
        List of dicts with tool name, description, and group
    """
    all_tools = []

    # Railway tools
    if os.getenv("RAILWAY_TOKEN"):
        for tool in RAILWAY_TOOLS:
            all_tools.append({
                "name": tool.name,
                "description": tool.description,
                "group": "railway",
                "available": True
            })
    else:
        for tool in RAILWAY_TOOLS:
            all_tools.append({
                "name": tool.name,
                "description": tool.description,
                "group": "railway",
                "available": False,
                "reason": "RAILWAY_TOKEN not set"
            })

    # Memory tools
    for tool in MEMORY_TOOLS:
        all_tools.append({
            "name": tool.name,
            "description": tool.description,
            "group": "memory",
            "available": True
        })

    # Database tools
    db_available = bool(os.getenv("AZURE_PG_HOST") and os.getenv("AZURE_PG_PASSWORD"))
    for tool in DB_TOOLS:
        all_tools.append({
            "name": tool.name,
            "description": tool.description,
            "group": "database",
            "available": db_available,
            "reason": "Azure PG credentials not set" if not db_available else None
        })

    return all_tools


def print_tool_inventory():
    """Print a formatted inventory of all tools."""
    tools = list_all_tools()

    print("=" * 70)
    print("🛠️  ENTERPRISE TOOLKIT - Tool Inventory")
    print("=" * 70)
    print()

    groups = {}
    for tool in tools:
        group = tool["group"]
        if group not in groups:
            groups[group] = []
        groups[group].append(tool)

    for group_name, group_tools in groups.items():
        available_count = sum(1 for t in group_tools if t["available"])
        total_count = len(group_tools)

        print(f"📦 {group_name.upper()} ({available_count}/{total_count} available)")
        print("-" * 70)

        for tool in group_tools:
            status = "✅" if tool["available"] else "❌"
            print(f"{status} {tool['name']}")
            print(f"   {tool['description'][:60]}...")
            if not tool["available"]:
                print(f"   ⚠️  {tool.get('reason', 'Not available')}")
        print()

    print("=" * 70)
    print(f"Total: {sum(1 for t in tools if t['available'])}/{len(tools)} tools ready")
    print("=" * 70)


# Convenience exports
__all__ = [
    "create_mcp_server",
    "list_all_tools",
    "print_tool_inventory",
    "RAILWAY_TOOLS",
    "MEMORY_TOOLS",
    "DB_TOOLS",
]
