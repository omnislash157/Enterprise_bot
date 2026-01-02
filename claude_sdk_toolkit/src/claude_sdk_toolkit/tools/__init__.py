"""Claude SDK Toolkit - Tool Collection

This module provides a unified interface to all MCP tools including:
- Database tools (PostgreSQL query, schema inspection)
- Memory/RAG tools (vector search, episodic memory, grep)
- Railway tools (service management, logs, status)

Usage:
    from claude_sdk_toolkit.tools import create_mcp_server, ALL_TOOLS

    # Create server with all tools
    server = create_mcp_server()

    # Or create server with specific tool sets
    from claude_sdk_toolkit.tools.db import TOOLS as DB_TOOLS
    from claude_sdk_toolkit.tools.memory import TOOLS as MEMORY_TOOLS
"""

from typing import List
from claude_agent_sdk import create_sdk_mcp_server

# Import tool modules
from . import db
from . import memory
from . import railway

# Collect all tools
DB_TOOLS = db.TOOLS
MEMORY_TOOLS = memory.TOOLS
RAILWAY_TOOLS = railway.TOOLS

ALL_TOOLS = DB_TOOLS + MEMORY_TOOLS + RAILWAY_TOOLS


def create_mcp_server(
    name: str = "claude-sdk-toolkit",
    version: str = "1.0.0",
    tools: List = None
):
    """
    Create an MCP server with the specified tools.

    Args:
        name: Server name
        version: Server version
        tools: List of tools to include (defaults to ALL_TOOLS)

    Returns:
        MCP server instance
    """
    if tools is None:
        tools = ALL_TOOLS

    return create_sdk_mcp_server(
        name=name,
        version=version,
        tools=tools
    )


__all__ = [
    "create_mcp_server",
    "ALL_TOOLS",
    "DB_TOOLS",
    "MEMORY_TOOLS",
    "RAILWAY_TOOLS",
    "db",
    "memory",
    "railway",
]
