"""
Skill Scraper Bot - Main Orchestrator (FIXED)

Coordinates crawling, conversion, and skill packaging using
Claude Agent SDK with custom MCP tools.

Usage:
    python bot.py https://docs.example.com
    python bot.py https://docs.example.com --max-pages 100 --output ./skills

Version: 1.1.0 - Fixed AgentDefinition dataclass usage
"""

import asyncio
import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AgentDefinition,  # Import the dataclass!
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

# Import our custom tools
# The tools.py file exports scraper_server directly
try:
    from .tools import scraper_server, get_allowed_tools
except ImportError:
    try:
        from tools import scraper_server, get_allowed_tools
    except ImportError:
        # Fallback for when run from different directory
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from tools import scraper_server, get_allowed_tools


# =============================================================================
# CONFIGURATION
# =============================================================================

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


# =============================================================================
# ORCHESTRATOR PROMPT
# =============================================================================

ORCHESTRATOR_SYSTEM_PROMPT = """You are a Skill Scraper Orchestrator responsible for converting documentation websites into Claude skill packages.

## Your Mission

Given a documentation URL, coordinate the complete scraping and skill generation pipeline:

1. **CRAWL** - Discover and fetch all pages from the documentation site
2. **CONVERT** - Transform HTML to clean markdown
3. **INDEX** - Create SKILL.md and package the skill

## Available Custom Tools

You have access to these MCP tools:

- `mcp__skill-scraper__check_robots` - Check robots.txt (ALWAYS DO FIRST)
- `mcp__skill-scraper__scrape_page` - Fetch a single URL
- `mcp__skill-scraper__discover_links` - Extract internal links from HTML
- `mcp__skill-scraper__convert_to_md` - Convert HTML to markdown
- `mcp__skill-scraper__analyze_content` - Generate descriptions for index
- `mcp__skill-scraper__write_skill_file` - Write file to skill directory
- `mcp__skill-scraper__generate_skill_md` - Create SKILL.md content
- `mcp__skill-scraper__package_skill` - Create final zip archive

## Execution Strategy

Work sequentially through the pipeline:

1. Check robots.txt first
2. Start from the root URL, fetch page, discover links
3. Build a queue of URLs to visit (breadth-first)
4. For each page: fetch -> convert to markdown -> write file
5. Track all pages for the index
6. Generate SKILL.md with descriptions
7. Package into zip

## Output Requirements

- Skill directory: `scraped_skills/{domain}/`
- Index file: `scraped_skills/{domain}/SKILL.md`
- Zip archive: `scraped_skills/{domain}_skill.zip`

## Progress Reporting

Report progress at each stage:
- "Checking robots.txt..."
- "Discovered X pages to crawl"
- "Crawled X/Y pages..."
- "Converting X/Y pages..."
- "Generating index..."
- "Packaging complete: {zip_path}"

## Error Handling

- If robots.txt disallows crawling, STOP and report
- If a page fails to fetch, log and continue
- If conversion fails, use minimal fallback
- Always produce SOME output even if partial
"""


# =============================================================================
# MAIN BOT
# =============================================================================

async def run_skill_scraper(
    url: str,
    max_pages: int = 500,
    output_dir: str = "./scraped_skills",
    verbose: bool = True
) -> bool:
    """Run the skill scraper bot."""

    # Parse domain for skill name
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    skill_name = domain.replace('.', '-')

    print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 63}{Colors.RESET}")
    print(f"{Colors.CYAN}  SKILL SCRAPER BOT{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 63}{Colors.RESET}")
    print(f"{Colors.DIM}Target URL:  {url}{Colors.RESET}")
    print(f"{Colors.DIM}Skill Name:  {skill_name}{Colors.RESET}")
    print(f"{Colors.DIM}Max Pages:   {max_pages}{Colors.RESET}")
    print(f"{Colors.DIM}Output Dir:  {output_dir}{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 63}{Colors.RESET}\n")

    # Build the prompt
    prompt = f"""Scrape the documentation website and create a Claude skill package.

**Target URL:** {url}
**Skill Name:** {skill_name}
**Max Pages:** {max_pages}
**Output Directory:** {output_dir}

Execute the full pipeline:
1. Check robots.txt for {url}
2. Crawl all documentation pages (max {max_pages})
3. Convert each page to clean markdown
4. Generate SKILL.md index with descriptions
5. Package into {skill_name}_skill.zip

Begin crawling now."""

    # Configure options with custom MCP tools
    # NOTE: Using proper dict format for mcp_servers (server name -> config)
    options = ClaudeAgentOptions(
        cwd=str(Path.cwd()),
        mcp_servers={"skill-scraper": scraper_server},
        allowed_tools=[
            # Standard tools
            "Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task",
            # Our custom MCP tools
            *get_allowed_tools()
        ],
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        permission_mode="acceptEdits",
        max_turns=200,  # Allow enough turns for large sites
    )

    # Run the bot
    success = True
    current_text = ""

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            # Stream text output
                            new_text = block.text
                            if new_text.startswith(current_text):
                                print(new_text[len(current_text):], end='', flush=True)
                            else:
                                print(new_text, end='', flush=True)
                            current_text = new_text

                        elif isinstance(block, ToolUseBlock):
                            if verbose:
                                tool_name = block.name.split('__')[-1] if '__' in block.name else block.name
                                print(f"\n{Colors.YELLOW}[{tool_name}]{Colors.RESET} ", end='')
                                if hasattr(block, 'input') and block.input:
                                    # Show truncated input
                                    input_preview = str(block.input)
                                    if 'html' in input_preview.lower():
                                        input_preview = "{html content...}"
                                    elif len(input_preview) > 80:
                                        input_preview = input_preview[:80] + "..."
                                    print(f"{Colors.DIM}{input_preview}{Colors.RESET}")

                elif isinstance(message, ResultMessage):
                    if message.subtype == "error":
                        success = False
                        print(f"\n{Colors.RED}[Error] {message}{Colors.RESET}")
                    else:
                        print(f"\n{Colors.GREEN}[Complete]{Colors.RESET}")

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[Interrupted]{Colors.RESET}")
        success = False
    except Exception as e:
        print(f"\n{Colors.RED}[Error] {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        success = False

    # Report final status
    print(f"\n{Colors.CYAN}{'=' * 63}{Colors.RESET}")
    if success:
        skill_path = Path(output_dir) / skill_name
        zip_path = Path(output_dir) / f"{skill_name}_skill.zip"
        print(f"{Colors.GREEN}[OK] Skill generated successfully!{Colors.RESET}")
        print(f"{Colors.DIM}  Skill directory: {skill_path}{Colors.RESET}")
        print(f"{Colors.DIM}  Zip archive:     {zip_path}{Colors.RESET}")
    else:
        print(f"{Colors.RED}[X] Skill generation failed or incomplete{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 63}{Colors.RESET}\n")

    return success


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Skill Scraper Bot - Convert documentation sites to Claude skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bot.py https://docs.python.org/3/
  python bot.py https://fastapi.tiangolo.com --max-pages 100
  python bot.py https://docs.anthropic.com --output ./my_skills
        """
    )

    parser.add_argument("url", help="Root URL of documentation site to scrape")
    parser.add_argument("--max-pages", "-m", type=int, default=500,
                        help="Maximum pages to crawl (default: 500)")
    parser.add_argument("--output", "-o", default="./scraped_skills",
                        help="Output directory (default: ./scraped_skills)")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Minimal output")

    args = parser.parse_args()

    # Validate URL
    parsed = urlparse(args.url)
    if not parsed.scheme or not parsed.netloc:
        print(f"{Colors.RED}Error: Invalid URL. Must include scheme (https://){Colors.RESET}")
        sys.exit(1)

    # Run bot
    success = asyncio.run(run_skill_scraper(
        url=args.url,
        max_pages=args.max_pages,
        output_dir=args.output,
        verbose=not args.quiet
    ))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()