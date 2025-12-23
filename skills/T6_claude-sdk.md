# T6: Claude SDK - Agent Configuration

## Overview
Claude Agent SDK for building agentic applications with tool use, streaming, and permissions.

---

## 🚀 Basic Agent

```python
from claude_agent_sdk import ClaudeAgent, ClaudeAgentOptions

agent = ClaudeAgent(
    options=ClaudeAgentOptions(
        model="claude-sonnet-4",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        system_prompt="You are a helpful coding assistant."
    )
)

# Sync usage
response = agent.run("Write a Python hello world")
print(response)

# Async usage
async def run_async():
    response = await agent.run_async("Write a hello world")
    return response
```

---

## 🛠️ Adding Tools

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

# Define tools
@tool(
    name="get_weather",
    description="Get current weather for a city",
    input_schema={"city": str}
)
async def get_weather(args: dict):
    city = args["city"]
    # Fetch weather...
    return {
        "content": [{"type": "text", "text": f"Weather in {city}: Sunny, 72°F"}]
    }

# Create MCP server
tools_server = create_sdk_mcp_server([get_weather])

# Agent with tools
agent = ClaudeAgent(
    options=ClaudeAgentOptions(
        model="claude-sonnet-4",
        mcp_servers=[tools_server]
    )
)

# Claude will call tools automatically
response = agent.run("What's the weather in SF?")
```

---

## 🌊 Streaming

```python
async def stream_response():
    agent = ClaudeAgent(
        options=ClaudeAgentOptions(model="claude-sonnet-4")
    )

    async for chunk in agent.stream("Write a story"):
        print(chunk, end="", flush=True)
```

---

## ⚙️ Agent Options

```python
from claude_agent_sdk import ClaudeAgentOptions

options = ClaudeAgentOptions(
    # Model
    model="claude-sonnet-4",          # or "claude-opus-4", "claude-haiku-4"

    # API
    api_key=os.getenv("ANTHROPIC_API_KEY"),

    # System prompt
    system_prompt="You are a helpful assistant.",

    # Tools
    mcp_servers=[tools_server],       # List of MCP servers

    # Generation params
    max_tokens=4096,
    temperature=1.0,                  # 0-1, higher = more creative

    # Streaming
    stream=False,                     # Enable streaming

    # Context
    max_turns=10,                     # Max conversation turns
    max_context_tokens=100000,        # Max context window

    # Safety
    allow_dangerous_tools=False,      # Block dangerous operations
)

agent = ClaudeAgent(options=options)
```

---

## 💬 Multi-Turn Conversations

```python
from claude_agent_sdk import ClaudeAgent, Message

agent = ClaudeAgent(options=ClaudeAgentOptions(model="claude-sonnet-4"))

# Conversation history
history = []

# Turn 1
response1 = agent.run(
    "What's 2+2?",
    conversation_history=history
)
history.append(Message(role="user", content="What's 2+2?"))
history.append(Message(role="assistant", content=response1))

# Turn 2 (with context)
response2 = agent.run(
    "What about 3+3?",
    conversation_history=history
)
```

---

## 🎯 Tool Permissions

```python
from claude_agent_sdk import tool, ToolPermission

@tool(
    name="delete_file",
    description="Delete a file (requires confirmation)",
    input_schema={"path": str},
    permission=ToolPermission.DANGEROUS  # Requires user confirmation
)
async def delete_file(args: dict):
    path = args["path"]
    os.remove(path)
    return {"content": [{"type": "text", "text": f"Deleted {path}"}]}
```

**Permission levels**:
- `SAFE` - Auto-approved
- `CONFIRMATION` - Ask user first
- `DANGEROUS` - Block unless allow_dangerous_tools=True

---

## 📊 Response Handling

```python
response = agent.run("Hello")

# String response
print(response)

# Structured response (if tools used)
if hasattr(response, 'tool_calls'):
    for call in response.tool_calls:
        print(f"Called tool: {call.name}")
        print(f"Args: {call.arguments}")
        print(f"Result: {call.result}")
```

---

## 🚨 Error Handling

```python
from claude_agent_sdk.exceptions import (
    APIError,
    RateLimitError,
    ContextLengthExceeded
)

try:
    response = agent.run("Hello")

except RateLimitError:
    print("Rate limited. Wait and retry.")

except ContextLengthExceeded:
    print("Context too long. Reduce history.")

except APIError as e:
    print(f"API error: {e}")
```

---

## 🔧 Advanced: Custom MCP Server

```python
from claude_agent_sdk import create_sdk_mcp_server

# Multiple tools
tools = [tool1, tool2, tool3, tool4]

# Create server with name
server = create_sdk_mcp_server(
    tools,
    name="my-custom-tools",
    description="Custom tool collection"
)

# Use in agent
agent = ClaudeAgent(
    options=ClaudeAgentOptions(
        mcp_servers=[server]
    )
)
```

---

## 🎭 System Prompt Patterns

### Coding Assistant
```python
system_prompt = """You are an expert Python developer.
Rules:
- Write clean, idiomatic Python 3.10+
- Include type hints
- Add docstrings for functions
- Handle errors with try/except
- Prefer async when possible
"""
```

### Research Assistant
```python
system_prompt = """You are a research assistant.
For each question:
1. Search relevant tools
2. Synthesize findings
3. Cite sources
4. Note confidence level
"""
```

### Tool Coordinator
```python
system_prompt = """You have access to these tools:
- db_query: For database operations
- memory_search: For retrieving context
- railway_logs: For checking deployments

Use them proactively to answer questions.
"""
```

---

## 📖 Model Selection

| Model | Best For | Cost | Speed |
|-------|----------|------|-------|
| `claude-sonnet-4` | Balanced | Medium | Fast |
| `claude-opus-4` | Complex reasoning | High | Slow |
| `claude-haiku-4` | Simple tasks | Low | Fastest |

---

## 🔄 Context Management

```python
def trim_context(history, max_tokens=50000):
    """Keep recent context within limits."""
    total_tokens = sum(estimate_tokens(msg.content) for msg in history)

    while total_tokens > max_tokens and len(history) > 1:
        # Remove oldest messages
        history.pop(0)
        total_tokens = sum(estimate_tokens(msg.content) for msg in history)

    return history
```

---

## 🚀 Production Patterns

### Retry Logic
```python
import asyncio

async def run_with_retry(agent, prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await agent.run_async(prompt)
        except RateLimitError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
```

### Caching
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_agent_call(prompt: str):
    """Cache repeated prompts."""
    return agent.run(prompt)
```

---

## 📊 Monitoring

```python
import time

def run_with_metrics(agent, prompt):
    start = time.time()

    try:
        response = agent.run(prompt)
        elapsed = time.time() - start

        print(f"✅ Success in {elapsed:.2f}s")
        print(f"Tokens: {estimate_tokens(response)}")

        return response

    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ Failed in {elapsed:.2f}s: {e}")
        raise
```

---

## 🔧 Environment Setup

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxx
```

Get key from: https://console.anthropic.com/

---

## 📖 Official Resources

- SDK Docs: https://github.com/anthropics/claude-agent-sdk
- API Reference: https://docs.anthropic.com/
- Examples: https://github.com/anthropics/claude-agent-sdk/tree/main/examples

---

*Claude SDK is the official Python framework for building agentic applications with Claude.*
