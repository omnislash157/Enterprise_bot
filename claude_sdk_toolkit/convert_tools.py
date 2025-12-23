"""
Helper script to convert old-style tools to SDK-compatible format.
This is a one-time migration script.
"""

import re
import json

def wrap_return_for_sdk(content_text: str, is_error: bool = False) -> str:
    """Generate SDK-compatible return statement."""
    error_flag = ', "isError": True' if is_error else ''
    return f'''{{
            "content": [{{"type": "text", "text": {content_text}}}]{error_flag}
        }}'''

def convert_railway_tools():
    """Convert Railway tools to SDK format."""

    # Read file
    with open("railway_tools.py", "r") as f:
        content = f.read()

    # Convert each tool function manually with patterns
    # This is complex - easier to do manually or with AST parsing
    # For now, let's just document what needs changing

    changes_needed = """
    For each @tool decorated function:
    1. Change decorator: @tool(name="func_name", description="...", input_schema={...})
    2. Change signature: async def func_name(args: dict) -> Dict[str, Any]
    3. Change parameter access: args.get("param_name")
    4. Wrap ALL returns in: {"content": [{"type": "text", "text": "..."}]}
    5. Add "isError": True for error returns
    """

    print(changes_needed)

if __name__ == "__main__":
    convert_railway_tools()
