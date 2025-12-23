# T1: SDK Tools - Complete Reference

## Overview
Claude SDK tools must follow specific decorator and return patterns. This doc covers the **exact requirements** discovered through recursive self-improvement.

---

## ✅ Correct Pattern

```python
from claude_agent_sdk import tool
from typing import Dict, Any

@tool(
    name="tool_name",  # REQUIRED: string identifier
    description="What the tool does - used by Claude for tool selection",  # REQUIRED
    input_schema={  # REQUIRED: dict or TypedDict
        "param1": str,
        "param2": int,
    }
)
async def tool_name(args: dict) -> Dict[str, Any]:
    """
    MUST be async.
    MUST take single 'args' dict parameter.
    MUST return {"content": [...]} format.
    """
    # Access parameters from args dict
    param1 = args.get("param1")
    param2 = args.get("param2", 10)  # with default

    # Do work
    result = do_something(param1, param2)

    # Return SDK format
    return {
        "content": [{
            "type": "text",
            "text": str(result)  # or json.dumps(result)
        }]
    }
```

---

## ❌ Common Mistakes

### Wrong: No decorator parameters
```python
@tool  # Missing name, description, schema!
def my_tool(param):  # Won't work
    return {"data": "..."}
```

### Wrong: Sync function
```python
@tool(name="x", description="y", input_schema={...})
def my_tool(args):  # Should be 'async def'
    return {...}
```

### Wrong: Direct parameters
```python
@tool(...)
async def my_tool(param1: str, param2: int):  # Should be single 'args' dict
    ...
```

### Wrong: Plain dict return
```python
@tool(...)
async def my_tool(args):
    return {"data": "value"}  # Should be {"content": [...]}
```

---

## 🎯 Error Handling

```python
@tool(...)
async def my_tool(args: dict) -> Dict[str, Any]:
    try:
        result = risky_operation(args["param"])
        return {
            "content": [{"type": "text", "text": result}]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "isError": True  # Mark as error
        }
```

---

## 📦 MCP Server Creation

```python
from claude_agent_sdk import create_sdk_mcp_server

# Define tools
TOOLS = [tool1, tool2, tool3]

# Create MCP server
server = create_sdk_mcp_server(TOOLS, name="my-tools")

# Use with agent
from claude_agent_sdk import ClaudeAgent, ClaudeAgentOptions

agent = ClaudeAgent(
    options=ClaudeAgentOptions(
        mcp_servers=[server],
        model="claude-sonnet-4"
    )
)
```

---

## 🔧 Input Schema Patterns

### Simple types
```python
input_schema={
    "text": str,
    "count": int,
    "enabled": bool,
    "ratio": float
}
```

### Optional parameters
```python
# All parameters are optional by default
# Add validation in function if needed
async def my_tool(args: dict):
    text = args.get("text")
    if not text:
        return {
            "content": [{"type": "text", "text": "Error: text is required"}],
            "isError": True
        }
```

### JSON Schema (advanced)
```python
input_schema={
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0}
    },
    "required": ["name"]
}
```

---

## 🧪 Testing Tools

```python
import asyncio

# Test directly
result = asyncio.run(my_tool({"param": "value"}))
print(result["content"][0]["text"])

# Check tool metadata
print(my_tool.name)
print(my_tool.description)
print(my_tool.input_schema)
```

---

## 📚 Tool Export Pattern

```python
# my_tools.py
@tool(...)
async def tool1(args): ...

@tool(...)
async def tool2(args): ...

@tool(...)
async def tool3(args): ...

# Export list for server creation
TOOLS = [tool1, tool2, tool3]
```

---

## 🔄 Auto-Loading .env

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Look for .env in project root
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded environment variables")

# Now tools can access env vars
api_token = os.getenv("API_TOKEN")
```

---

## 🎯 Real Example: Railway Services

```python
from claude_agent_sdk import tool
import os
import httpx

@tool(
    name="railway_services",
    description="List all services in a Railway project with their IDs and names",
    input_schema={"project_id": str}
)
async def railway_services(args: dict):
    project_id = args.get("project_id") or os.getenv("RAILWAY_PROJECT_ID")

    if not project_id:
        return {
            "content": [{"type": "text", "text": "Error: project_id required"}],
            "isError": True
        }

    # GraphQL query
    query = """
        query ($projectId: String!) {
            project(id: $projectId) {
                services { edges { node { id name } } }
            }
        }
    """

    response = httpx.post(
        "https://backboard.railway.app/graphql/v2",
        headers={"Authorization": f"Bearer {os.getenv('RAILWAY_TOKEN')}"},
        json={"query": query, "variables": {"projectId": project_id}}
    )

    data = response.json()
    services = [
        edge["node"]
        for edge in data["data"]["project"]["services"]["edges"]
    ]

    result_text = f"Found {len(services)} services:\n"
    for svc in services:
        result_text += f"  • {svc['name']} (ID: {svc['id'][:12]}...)\n"

    return {
        "content": [{"type": "text", "text": result_text}]
    }
```

---

## 🚨 Debugging Checklist

Tool not working? Check:
- ✅ Decorator has name, description, input_schema
- ✅ Function is async
- ✅ Function takes single 'args' dict
- ✅ Return has {"content": [...]} structure
- ✅ Tool is in TOOLS list
- ✅ MCP server includes the tool
- ✅ Environment variables are loaded

---

## 📖 Official Resources

- Claude SDK docs: https://github.com/anthropics/claude-agent-sdk
- MCP Protocol: https://modelcontextprotocol.io
- Tool examples: https://github.com/anthropics/claude-agent-sdk/tree/main/examples

---

*Discovered through recursive self-improvement - AI debugging its own tools*
