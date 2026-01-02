# Skill Scraper Bot

Convert any documentation website into a Claude skill package (ZIP archive with SKILL.md index + organized markdown files).

## Quick Start

```bash
cd claude_sdk_toolkit
python skill_scraper_bot.py https://docs.example.com
```

## Usage

```bash
# Basic - scrape up to 500 pages
python skill_scraper_bot.py https://docs.example.com

# Limit pages
python skill_scraper_bot.py https://fastapi.tiangolo.com --max-pages 100

# Custom output directory
python skill_scraper_bot.py https://docs.anthropic.com -o ./my_skills

# Quiet mode (minimal output)
python skill_scraper_bot.py https://htmx.org/docs/ -q
```

## Output Structure

```
scraped_skills/
└── docs-example-com/
    ├── SKILL.md                    # Index with YAML frontmatter
    ├── getting-started/
    │   ├── installation.md
    │   └── quickstart.md
    ├── guides/
    │   ├── authentication.md
    │   └── advanced-usage.md
    ├── api-reference/
    │   ├── endpoints.md
    │   └── schemas.md
    └── docs-example-com_skill.zip  # Complete archive
```

## Features

✅ **Polite Crawling**: Respects robots.txt, implements crawl delays
✅ **Clean Conversion**: Strips navigation, ads, footers; preserves code blocks and tables
✅ **Smart Organization**: Auto-detects content types (getting_started, guide, api_reference, etc.)
✅ **Hierarchical Structure**: Maps URL paths to file paths
✅ **SKILL.md Generation**: Creates organized index with descriptions
✅ **Ready-to-Use**: Produces ZIP archives compatible with Claude UI

## Architecture

### Components

1. **Main Orchestrator** (`skill_scraper_bot.py`)
   - CLI entry point
   - Coordinates subagents
   - Streams progress

2. **Crawler Subagent** (`.claude/agents/skill-crawler.md`)
   - Checks robots.txt
   - Discovers internal links
   - Fetches pages

3. **Converter Subagent** (`.claude/agents/skill-converter.md`)
   - HTML → Markdown conversion
   - Content analysis
   - File writing

4. **Indexer Subagent** (`.claude/agents/skill-indexer.md`)
   - SKILL.md generation
   - Section organization
   - ZIP packaging

### Custom MCP Tools

Located in `tools/scraper_tools.py`:

- `check_robots` - Parse robots.txt
- `scrape_page` - Fetch single URL
- `discover_links` - Extract internal links
- `convert_to_md` - HTML to markdown
- `analyze_content` - Generate descriptions
- `write_skill_file` - Write to skill directory
- `generate_skill_md` - Create SKILL.md content
- `package_skill` - Create ZIP archive

## Requirements

```bash
pip install httpx beautifulsoup4 markdownify aiofiles lxml claude-agent-sdk
```

## Examples

### Small Documentation Site (HTMX)
```bash
python skill_scraper_bot.py https://htmx.org/docs/ --max-pages 50
```

### Medium API Documentation
```bash
python skill_scraper_bot.py https://docs.anthropic.com --max-pages 200
```

### Large Framework Docs
```bash
python skill_scraper_bot.py https://fastapi.tiangolo.com --max-pages 500
```

## SKILL.md Format

```yaml
---
name: skill-name
description: Concise description of what this skill covers
---

# Skill Name Documentation Index

Description of the skill and its contents.

Use `view` to lazy-load any file.

## Getting Started
- `getting-started/installation.md` — How to install...
- `getting-started/quickstart.md` — Quick start guide...

## Guides
- `guides/authentication.md` — Authentication setup...
- `guides/advanced-usage.md` — Advanced patterns...

## API Reference
- `api/endpoints.md` — API endpoint documentation...
- `api/schemas.md` — Request/response schemas...
```

## Troubleshooting

### Import Error: No module named 'claude_agent_sdk'
```bash
pip install claude-agent-sdk --break-system-packages
```

### Tools Not Loading
```bash
cd claude_sdk_toolkit
python -c "from tools.scraper_tools import scraper_server; print('OK')"
```

### Robots.txt Blocks Crawling
The bot will detect this and report it. If you believe this is incorrect, check:
- User-Agent in `tools/scraper_tools.py` (DEFAULT_HEADERS)
- robots.txt manually at `https://example.com/robots.txt`

## Advanced Configuration

Edit `tools/scraper_tools.py` to customize:

- `DEFAULT_HEADERS` - User-Agent and headers
- `EXCLUDED_EXTENSIONS` - Skip file types
- `EXCLUDED_PATHS` - Skip URL patterns
- `clean_html_content()` - Modify content cleaning
- `extract_title()` - Customize title extraction

## Performance

- **Small sites (<50 pages)**: ~2-5 minutes
- **Medium sites (100-200 pages)**: ~5-10 minutes
- **Large sites (500+ pages)**: ~15-30 minutes

Timing varies based on:
- Site response time
- robots.txt crawl delay
- Content size
- Number of code blocks/tables

## License

Part of the claude_sdk_toolkit project.

## Support

For issues or questions, see the main project documentation.
