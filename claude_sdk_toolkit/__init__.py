"""
SDK Custom Tools - MCP Server Factory

Aggregates all custom tools into a single MCP server for the Claude SDK.

Tools available:
- db_*: Database operations (query, tables, describe)
- memory_*: CogTwin RAG lane access (vector, grep, episodic, squirrel)
- railway_*: Railway deployment management (logs, redeploy, env)

Usage:
    from tools import create_tools_server
    
    server = create_tools_server()
    options = ClaudeAgentOptions(
        mcp_servers=[server],
        ...
    )
"""

import os
from typing import List, Optional

# Check SDK availability
try:
    from claude_agent_sdk import create_sdk_mcp_server
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    create_sdk_mcp_server = None

# Import tool modules
from .db_tools import TOOLS as DB_TOOLS
from .memory_tools import TOOLS as MEMORY_TOOLS
from .railway_tools import TOOLS as RAILWAY_TOOLS


def create_tools_server(
    include_db: bool = True,
    include_memory: bool = True,
    include_railway: bool = True,
):
    """
    Create MCP server with selected tool groups.
    
    Args:
        include_db: Include database tools
        include_memory: Include CogTwin memory tools
        include_railway: Include Railway deployment tools
        
    Returns:
        MCP server instance for SDK
    """
    if not SDK_AVAILABLE:
        raise RuntimeError("claude_agent_sdk not installed")
    
    tools = []
    
    if include_db:
        tools.extend(DB_TOOLS)
        
    if include_memory:
        tools.extend(MEMORY_TOOLS)
        
    if include_railway and os.getenv("RAILWAY_TOKEN"):
        tools.extend(RAILWAY_TOOLS)
    
    return create_sdk_mcp_server(tools)


def list_available_tools() -> List[str]:
    """List all available tool names."""
    tools = []
    tools.extend([t.__name__ for t in DB_TOOLS])
    tools.extend([t.__name__ for t in MEMORY_TOOLS])
    if os.getenv("RAILWAY_TOKEN"):
        tools.extend([t.__name__ for t in RAILWAY_TOOLS])
    return tools


__all__ = ["create_tools_server", "list_available_tools"]