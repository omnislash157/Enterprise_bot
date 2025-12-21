# Claude SDK Toolkit

A professional Python SDK toolkit for building Claude-powered applications with MCP (Model Context Protocol) server support.

## Features

- 🤖 **Claude Agent SDK Wrapper**: Streamlined interface for Claude AI interactions
- 🔧 **Custom Tool System**: Extensible framework for building and registering custom tools
- 📚 **Skills Management**: Load and manage context-rich skill files (.skill.md)
- 🌐 **MCP Server**: Expose custom tools via Model Context Protocol
- 💻 **Interactive CLI**: Rich terminal interface with command history and multi-line input
- 🗄️ **Database Tools**: Built-in PostgreSQL query, schema inspection, and export capabilities

## Installation

```bash
# From source
cd claude_sdk_toolkit
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

## Quick Start

### Interactive REPL

```bash
claude-chat
```

### One-Shot Execution

```bash
claude-run "Analyze the database schema and suggest optimizations"
```

### MCP Server

```bash
claude-mcp start
```

## Package Structure

```
claude_sdk_toolkit/
├── src/claude_sdk_toolkit/
│   ├── core/          # Core SDK client and session management
│   ├── cli/           # Interactive REPL and runner
│   ├── tools/         # Custom tool system and built-in tools
│   ├── skills/        # Skill loading and context management
│   ├── mcp/           # MCP server implementation
│   └── utils/         # Configuration and utilities
├── skills_data/       # Skill definition files (.skill.md)
├── examples/          # Example scripts
└── tests/             # Test suite
```

## Configuration

Create a `.env` file or set environment variables:

```bash
ANTHROPIC_API_KEY=your_key_here

# Optional: Database configuration
AZURE_PG_HOST=your_host
AZURE_PG_DATABASE=your_db
AZURE_PG_USER=your_user
AZURE_PG_PASSWORD=your_password
```

## Creating Custom Tools

```python
from claude_sdk_toolkit.tools.base import BaseTool, ToolMetadata, ToolParameter

class MyCustomTool(BaseTool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="my_tool",
            description="Does something useful",
            version="1.0.0",
            tags=["custom", "example"]
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="input",
                type="string",
                description="Input data",
                required=True
            )
        ]

    async def execute(self, input: str, **kwargs):
        # Your tool logic here
        return {"result": f"Processed: {input}"}
```

## Creating Skills

Create a `.skill.md` file in `skills_data/`:

```markdown
---
skill: my_skill
version: 1.0.0
tags: [example, demo]
tools: [my_tool]
---

# My Custom Skill

## Overview
Description of what this skill does...

## Usage
Example usage instructions...
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .

# Format code
black .
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or submit a pull request.
