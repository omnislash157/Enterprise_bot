# Feature Build Sheet: Web Scraper → Claude Skill Converter

## Feature: skill-scraper
**Priority:** P0  
**Estimated Complexity:** High  
**Dependencies:** claude-agent-sdk, httpx, beautifulsoup4, markdownify, aiofiles

---

## 1. OVERVIEW

### User Story
> As a developer, I want to point a bot at any public documentation website and have it automatically generate a complete Claude skill package (SKILL.md + markdown files + zip archive) so that I can instantly give Claude deep knowledge about any technology.

### Acceptance Criteria
- [ ] Bot accepts a root URL and crawls all linked pages within same domain
- [ ] Respects robots.txt and implements polite crawling (rate limiting)
- [ ] Converts HTML content to clean markdown preserving code blocks, tables, headers
- [ ] Generates hierarchical folder structure matching site URL paths
- [ ] Creates SKILL.md index with auto-generated descriptions for each file
- [ ] Produces ready-to-use zip archive
- [ ] Supports parallel crawling with configurable concurrency
- [ ] Handles JS-rendered pages via fallback (Playwright optional)
- [ ] Reports progress and handles errors gracefully

---

## 2. ARCHITECTURE

### System Design
```
┌─────────────────────────────────────────────────────────────────────┐
│                     SKILL SCRAPER ORCHESTRATOR                       │
│                     (Main Agent - Coordinator)                       │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
           ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
           │  CRAWLER      │ │  CONVERTER    │ │  INDEXER      │
           │  SUBAGENT     │ │  SUBAGENT     │ │  SUBAGENT     │
           │               │ │               │ │               │
           │  - Discover   │ │  - HTML→MD    │ │  - Analyze    │
           │  - Fetch      │ │  - Clean      │ │  - Summarize  │
           │  - Queue      │ │  - Structure  │ │  - Generate   │
           └───────────────┘ └───────────────┘ └───────────────┘
                    │              │              │
                    ▼              ▼              ▼
           ┌─────────────────────────────────────────────────────┐
           │                  CUSTOM MCP TOOLS                    │
           │                                                      │
           │  scrape_page      - Fetch & parse single URL        │
           │  discover_links   - Extract all internal links      │
           │  convert_to_md    - HTML → Markdown conversion      │
           │  analyze_content  - Generate summary/description    │
           │  write_skill_file - Write file to skill structure   │
           │  package_skill    - Create final zip archive        │
           │  check_robots     - Parse robots.txt                │
           └─────────────────────────────────────────────────────┘
```

### File Structure Output
```
scraped_skills/
└── {domain}/
    ├── SKILL.md                    # Index file (TOC + descriptions)
    ├── getting-started/
    │   ├── installation.md
    │   ├── quickstart.md
    │   └── configuration.md
    ├── guides/
    │   ├── authentication.md
    │   ├── advanced-usage.md
    │   └── best-practices.md
    ├── api-reference/
    │   ├── endpoints.md
    │   ├── schemas.md
    │   └── errors.md
    └── {domain}_skill.zip          # Complete archive
```

---

## 3. CUSTOM MCP TOOLS

### File: tools/scraper_tools.py

```python
"""
Skill Scraper MCP Tools

Custom tools for web scraping and skill generation.
Designed for use with Claude Agent SDK.

Version: 1.0.0
"""

import asyncio
import re
import hashlib
import json
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import aiofiles

from claude_agent_sdk import tool, create_sdk_mcp_server


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_HEADERS = {
    "User-Agent": "ClaudeSkillScraper/1.0 (Educational; +https://anthropic.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

EXCLUDED_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
    '.pdf', '.zip', '.tar', '.gz', '.mp4', '.mp3', '.wav',
    '.woff', '.woff2', '.ttf', '.eot', '.css', '.js'
}

EXCLUDED_PATHS = {
    '/cdn-cgi/', '/_next/static/', '/static/js/', '/static/css/',
    '/assets/', '/images/', '/fonts/', '/__/'
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def normalize_url(url: str, base_url: str = None) -> str:
    """Normalize URL: remove fragments, trailing slashes, ensure absolute."""
    if base_url:
        url = urljoin(base_url, url)
    
    parsed = urlparse(url)
    # Remove fragment, normalize path
    path = parsed.path.rstrip('/') or '/'
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc.lower(),
        path,
        parsed.params,
        parsed.query,
        ''  # No fragment
    ))
    return normalized


def url_to_filepath(url: str, base_domain: str) -> str:
    """Convert URL to relative file path for skill structure."""
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    
    if not path:
        path = 'index'
    
    # Remove file extension if present
    if '.' in path.split('/')[-1]:
        path = path.rsplit('.', 1)[0]
    
    # Clean path segments
    segments = [re.sub(r'[^\w\-]', '_', seg) for seg in path.split('/') if seg]
    
    if not segments:
        return 'index.md'
    
    return '/'.join(segments) + '.md'


def should_crawl_url(url: str, base_domain: str) -> bool:
    """Determine if URL should be crawled."""
    parsed = urlparse(url)
    
    # Must be same domain
    if parsed.netloc.lower() != base_domain.lower():
        return False
    
    # Skip excluded extensions
    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in EXCLUDED_EXTENSIONS):
        return False
    
    # Skip excluded paths
    if any(excl in parsed.path for excl in EXCLUDED_PATHS):
        return False
    
    # Must be http(s)
    if parsed.scheme not in ('http', 'https'):
        return False
    
    return True


def clean_html_content(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove non-content elements from HTML."""
    # Remove script, style, nav, footer, etc.
    for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 
                               'aside', 'noscript', 'iframe', 'svg']):
        tag.decompose()
    
    # Remove elements by common class/id patterns
    noise_patterns = [
        'nav', 'navigation', 'menu', 'sidebar', 'footer', 'header',
        'advertisement', 'ad-', 'social', 'share', 'comment', 'cookie',
        'popup', 'modal', 'newsletter', 'subscribe', 'promo'
    ]
    
    for pattern in noise_patterns:
        for element in soup.find_all(class_=re.compile(pattern, re.I)):
            element.decompose()
        for element in soup.find_all(id=re.compile(pattern, re.I)):
            element.decompose()
    
    return soup


def html_to_markdown(html: str, base_url: str = None) -> str:
    """Convert HTML to clean markdown."""
    soup = BeautifulSoup(html, 'html.parser')
    soup = clean_html_content(soup)
    
    # Find main content area
    main_content = (
        soup.find('main') or 
        soup.find('article') or 
        soup.find('div', class_=re.compile(r'content|main|body', re.I)) or
        soup.find('body') or
        soup
    )
    
    # Convert to markdown
    markdown = md(
        str(main_content),
        heading_style='atx',
        bullets='-',
        code_language_callback=lambda el: el.get('class', [''])[0].replace('language-', '') if el.get('class') else ''
    )
    
    # Clean up excessive whitespace
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    markdown = re.sub(r' +', ' ', markdown)
    markdown = markdown.strip()
    
    return markdown


def extract_title(soup: BeautifulSoup) -> str:
    """Extract page title from HTML."""
    # Try multiple sources
    title = None
    
    # <title> tag
    if soup.title:
        title = soup.title.string
    
    # <h1> tag
    if not title:
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text()
    
    # og:title meta
    if not title:
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title.get('content')
    
    # Clean up
    if title:
        title = re.sub(r'\s+', ' ', title).strip()
        # Remove common suffixes
        title = re.split(r'\s*[\|–—-]\s*', title)[0].strip()
    
    return title or 'Untitled'


def extract_description(soup: BeautifulSoup, markdown: str) -> str:
    """Extract or generate page description."""
    # Try meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        return meta_desc['content'].strip()[:200]
    
    # Try og:description
    og_desc = soup.find('meta', property='og:description')
    if og_desc and og_desc.get('content'):
        return og_desc['content'].strip()[:200]
    
    # Fall back to first paragraph
    lines = [l.strip() for l in markdown.split('\n') if l.strip() and not l.startswith('#')]
    if lines:
        first_para = lines[0][:200]
        if len(lines[0]) > 200:
            first_para = first_para.rsplit(' ', 1)[0] + '...'
        return first_para
    
    return 'No description available'


# =============================================================================
# MCP TOOLS
# =============================================================================

@tool(
    "check_robots",
    "Check robots.txt for a domain and return crawl rules. Call this FIRST before crawling.",
    {"url": str}
)
async def check_robots(args: dict[str, Any]) -> dict[str, Any]:
    """Parse robots.txt and return crawl permissions."""
    url = args["url"]
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    try:
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=10) as client:
            response = await client.get(robots_url)
            
            if response.status_code == 200:
                rp = RobotFileParser()
                rp.parse(response.text.split('\n'))
                
                can_fetch = rp.can_fetch(DEFAULT_HEADERS['User-Agent'], url)
                crawl_delay = rp.crawl_delay(DEFAULT_HEADERS['User-Agent']) or 1
                
                # Extract sitemap URLs
                sitemaps = []
                for line in response.text.split('\n'):
                    if line.lower().startswith('sitemap:'):
                        sitemaps.append(line.split(':', 1)[1].strip())
                
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "allowed": can_fetch,
                            "crawl_delay": crawl_delay,
                            "sitemaps": sitemaps,
                            "robots_txt_found": True
                        }, indent=2)
                    }]
                }
            else:
                # No robots.txt = allowed
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "allowed": True,
                            "crawl_delay": 1,
                            "sitemaps": [],
                            "robots_txt_found": False
                        }, indent=2)
                    }]
                }
                
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "allowed": True,
                    "crawl_delay": 1,
                    "sitemaps": [],
                    "robots_txt_found": False,
                    "error": str(e)
                }, indent=2)
            }]
        }


@tool(
    "scrape_page",
    "Fetch a single URL and return its HTML content, title, and metadata. Use for crawling documentation sites.",
    {
        "url": str,
        "timeout": int  # Optional, defaults to 30
    }
)
async def scrape_page(args: dict[str, Any]) -> dict[str, Any]:
    """Fetch and parse a single web page."""
    url = args["url"]
    timeout = args.get("timeout", 30)
    
    try:
        async with httpx.AsyncClient(
            headers=DEFAULT_HEADERS, 
            timeout=timeout,
            follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            title = extract_title(soup)
            final_url = str(response.url)
            
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": True,
                        "url": final_url,
                        "title": title,
                        "status_code": response.status_code,
                        "content_type": response.headers.get('content-type', ''),
                        "html_length": len(html),
                        "html": html  # Full HTML for conversion
                    }, indent=2)
                }]
            }
            
    except httpx.HTTPStatusError as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "url": url,
                    "error": f"HTTP {e.response.status_code}",
                    "status_code": e.response.status_code
                }, indent=2)
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "url": url,
                    "error": str(e)
                }, indent=2)
            }]
        }


@tool(
    "discover_links",
    "Extract all internal links from HTML content. Returns deduplicated list of URLs to crawl.",
    {
        "html": str,
        "base_url": str,
        "base_domain": str
    }
)
async def discover_links(args: dict[str, Any]) -> dict[str, Any]:
    """Extract and filter internal links from HTML."""
    html = args["html"]
    base_url = args["base_url"]
    base_domain = args["base_domain"]
    
    soup = BeautifulSoup(html, 'html.parser')
    links = set()
    
    for anchor in soup.find_all('a', href=True):
        href = anchor['href']
        
        # Skip empty, javascript, mailto, tel links
        if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            continue
        
        # Normalize and make absolute
        absolute_url = normalize_url(href, base_url)
        
        # Check if should crawl
        if should_crawl_url(absolute_url, base_domain):
            links.add(absolute_url)
    
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "discovered_urls": sorted(links),
                "count": len(links)
            }, indent=2)
        }]
    }


@tool(
    "convert_to_md",
    "Convert HTML content to clean markdown. Strips navigation, ads, and non-content elements.",
    {
        "html": str,
        "base_url": str
    }
)
async def convert_to_md(args: dict[str, Any]) -> dict[str, Any]:
    """Convert HTML to markdown with metadata."""
    html = args["html"]
    base_url = args.get("base_url", "")
    
    soup = BeautifulSoup(html, 'html.parser')
    
    title = extract_title(soup)
    markdown = html_to_markdown(html, base_url)
    description = extract_description(soup, markdown)
    
    # Count content metrics
    word_count = len(markdown.split())
    code_blocks = markdown.count('```')
    headers = len(re.findall(r'^#{1,6}\s', markdown, re.MULTILINE))
    
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "title": title,
                "description": description,
                "markdown": markdown,
                "metrics": {
                    "word_count": word_count,
                    "code_blocks": code_blocks,
                    "headers": headers,
                    "char_count": len(markdown)
                }
            }, indent=2)
        }]
    }


@tool(
    "analyze_content",
    "Analyze markdown content to generate a concise description suitable for SKILL.md index.",
    {
        "markdown": str,
        "title": str,
        "url_path": str
    }
)
async def analyze_content(args: dict[str, Any]) -> dict[str, Any]:
    """Generate description for skill index entry."""
    markdown = args["markdown"]
    title = args["title"]
    url_path = args["url_path"]
    
    # Extract key information
    headers = re.findall(r'^#{1,3}\s+(.+)$', markdown, re.MULTILINE)
    
    # Get first paragraph (non-header content)
    paragraphs = []
    for line in markdown.split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('```'):
            paragraphs.append(line)
            if len(paragraphs) >= 2:
                break
    
    first_para = ' '.join(paragraphs)[:200]
    if len(' '.join(paragraphs)) > 200:
        first_para = first_para.rsplit(' ', 1)[0] + '...'
    
    # Detect content type
    content_type = "documentation"
    if re.search(r'api|endpoint|request|response', markdown, re.I):
        content_type = "api_reference"
    elif re.search(r'install|setup|getting.started|quickstart', url_path, re.I):
        content_type = "getting_started"
    elif re.search(r'guide|tutorial|how.to', url_path, re.I):
        content_type = "guide"
    elif re.search(r'example|sample|demo', url_path, re.I):
        content_type = "examples"
    elif re.search(r'config|settings|options', url_path, re.I):
        content_type = "configuration"
    
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "title": title,
                "description": first_para,
                "content_type": content_type,
                "key_headers": headers[:5],
                "suggested_index_entry": f"`{url_path}` — {first_para[:100]}"
            }, indent=2)
        }]
    }


@tool(
    "write_skill_file",
    "Write a markdown file to the skill output directory structure.",
    {
        "skill_name": str,
        "relative_path": str,  # e.g., "guides/authentication.md"
        "content": str,
        "output_dir": str  # Base output directory
    }
)
async def write_skill_file(args: dict[str, Any]) -> dict[str, Any]:
    """Write file to skill directory structure."""
    skill_name = args["skill_name"]
    relative_path = args["relative_path"]
    content = args["content"]
    output_dir = args.get("output_dir", "./scraped_skills")
    
    # Build full path
    skill_dir = Path(output_dir) / skill_name
    file_path = skill_dir / relative_path
    
    try:
        # Create directories
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(content)
        
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "path": str(file_path),
                    "bytes_written": len(content.encode('utf-8'))
                }, indent=2)
            }]
        }
        
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "path": str(file_path),
                    "error": str(e)
                }, indent=2)
            }],
            "is_error": True
        }


@tool(
    "generate_skill_md",
    "Generate the SKILL.md index file from collected page metadata.",
    {
        "skill_name": str,
        "description": str,
        "pages": str  # JSON array of {path, title, description, content_type}
    }
)
async def generate_skill_md(args: dict[str, Any]) -> dict[str, Any]:
    """Generate SKILL.md content from page metadata."""
    skill_name = args["skill_name"]
    description = args["description"]
    pages = json.loads(args["pages"])
    
    # Group pages by content type / directory
    grouped = {}
    for page in pages:
        content_type = page.get("content_type", "documentation")
        if content_type not in grouped:
            grouped[content_type] = []
        grouped[content_type].append(page)
    
    # Build SKILL.md content
    lines = [
        "---",
        f"name: {skill_name}",
        f"description: {description}",
        "---",
        "",
        f"# {skill_name.replace('-', ' ').title()} Documentation Index",
        "",
        f"{description}",
        "",
        "Use `view` to lazy-load any file.",
        "",
    ]
    
    # Section order preference
    section_order = [
        ("getting_started", "Getting Started"),
        ("guide", "Guides"),
        ("api_reference", "API Reference"),
        ("configuration", "Configuration"),
        ("examples", "Examples"),
        ("documentation", "Documentation"),
    ]
    
    for content_type, section_title in section_order:
        if content_type in grouped:
            section_pages = grouped[content_type]
            lines.append(f"## {section_title}")
            lines.append("")
            
            for page in sorted(section_pages, key=lambda x: x.get('path', '')):
                path = page.get('path', 'unknown.md')
                title = page.get('title', 'Untitled')
                desc = page.get('description', '')[:80]
                lines.append(f"- `{path}` — {desc}")
            
            lines.append("")
    
    skill_md_content = '\n'.join(lines)
    
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "skill_md_content": skill_md_content,
                "total_pages": len(pages),
                "sections": list(grouped.keys())
            }, indent=2)
        }]
    }


@tool(
    "package_skill",
    "Create a zip archive of the completed skill directory.",
    {
        "skill_name": str,
        "output_dir": str
    }
)
async def package_skill(args: dict[str, Any]) -> dict[str, Any]:
    """Create zip archive of skill directory."""
    skill_name = args["skill_name"]
    output_dir = args.get("output_dir", "./scraped_skills")
    
    skill_dir = Path(output_dir) / skill_name
    zip_path = skill_dir.parent / f"{skill_name}_skill.zip"
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in skill_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(skill_dir.parent)
                    zf.write(file_path, arcname)
        
        # Get zip stats
        zip_size = zip_path.stat().st_size
        file_count = len(list(skill_dir.rglob('*.md')))
        
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "zip_path": str(zip_path),
                    "zip_size_bytes": zip_size,
                    "zip_size_human": f"{zip_size / 1024:.1f} KB",
                    "file_count": file_count
                }, indent=2)
            }]
        }
        
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": str(e)
                }, indent=2)
            }],
            "is_error": True
        }


# =============================================================================
# CREATE MCP SERVER
# =============================================================================

scraper_server = create_sdk_mcp_server(
    name="skill-scraper",
    version="1.0.0",
    tools=[
        check_robots,
        scrape_page,
        discover_links,
        convert_to_md,
        analyze_content,
        write_skill_file,
        generate_skill_md,
        package_skill
    ]
)


# =============================================================================
# EXPORT FOR USE
# =============================================================================

def get_scraper_tools():
    """Get the scraper MCP server for use with Claude Agent SDK."""
    return {"skill-scraper": scraper_server}


def get_allowed_tools():
    """Get list of allowed tool names for ClaudeAgentOptions."""
    return [
        "mcp__skill-scraper__check_robots",
        "mcp__skill-scraper__scrape_page",
        "mcp__skill-scraper__discover_links",
        "mcp__skill-scraper__convert_to_md",
        "mcp__skill-scraper__analyze_content",
        "mcp__skill-scraper__write_skill_file",
        "mcp__skill-scraper__generate_skill_md",
        "mcp__skill-scraper__package_skill",
    ]
```

---

## 4. SUBAGENT DEFINITIONS

### File: .claude/agents/skill-crawler.md

```markdown
---
name: skill-crawler
description: Web crawler specialist. Use for discovering and fetching pages from documentation sites. MUST be used for all URL discovery and page fetching operations.
tools: mcp__skill-scraper__check_robots, mcp__skill-scraper__scrape_page, mcp__skill-scraper__discover_links
model: sonnet
---

You are a web crawler specialist responsible for systematically discovering and fetching pages from documentation websites.

## Your Responsibilities

1. **Check robots.txt FIRST** - Always call `check_robots` before crawling any domain
2. **Respect crawl delays** - Honor the crawl_delay from robots.txt
3. **Discover links** - Use `discover_links` to find all internal URLs
4. **Fetch pages** - Use `scrape_page` to retrieve HTML content
5. **Track progress** - Maintain a visited set to avoid duplicates

## Crawling Strategy

1. Start with the root URL provided
2. Fetch the page and extract links
3. Add new links to the queue
4. Process queue breadth-first
5. Stop when queue is empty or max pages reached

## Output Format

For each page successfully crawled, output:
```json
{
  "url": "https://...",
  "title": "Page Title",
  "html": "...",
  "links_found": 15
}
```

## Constraints

- Maximum 500 pages per crawl
- Skip binary files (images, PDFs, etc.)
- Stay within the same domain
- Handle errors gracefully - log and continue
```

### File: .claude/agents/skill-converter.md

```markdown
---
name: skill-converter
description: Content converter specialist. Use for converting HTML to clean markdown and analyzing content. MUST be used for all HTML→markdown conversion.
tools: mcp__skill-scraper__convert_to_md, mcp__skill-scraper__analyze_content, mcp__skill-scraper__write_skill_file
model: sonnet
---

You are a content conversion specialist responsible for transforming HTML documentation into clean, well-structured markdown files.

## Your Responsibilities

1. **Convert HTML to Markdown** - Use `convert_to_md` to transform HTML
2. **Preserve important content** - Keep code blocks, tables, headers intact
3. **Remove noise** - Strip navigation, ads, footers, sidebars
4. **Analyze content** - Use `analyze_content` to generate descriptions
5. **Write files** - Use `write_skill_file` to save to skill structure

## Conversion Guidelines

- Preserve code blocks with language hints
- Convert tables to markdown tables
- Keep header hierarchy (h1 → #, h2 → ##, etc.)
- Remove duplicate content
- Clean up excessive whitespace

## File Naming

Convert URL paths to file paths:
- `/docs/getting-started/` → `getting-started.md`
- `/api/v2/users` → `api/v2/users.md`
- `/guide/authentication#oauth` → `guide/authentication.md`

## Output

For each converted file, report:
```json
{
  "source_url": "https://...",
  "output_path": "guides/auth.md",
  "title": "Authentication Guide",
  "description": "How to authenticate with the API...",
  "word_count": 1250
}
```
```

### File: .claude/agents/skill-indexer.md

```markdown
---
name: skill-indexer
description: Index generator specialist. Use for creating SKILL.md and packaging the final skill. MUST be used for final skill assembly.
tools: mcp__skill-scraper__generate_skill_md, mcp__skill-scraper__write_skill_file, mcp__skill-scraper__package_skill
model: sonnet
---

You are an index generator specialist responsible for creating the SKILL.md file and packaging the completed skill.

## Your Responsibilities

1. **Collect page metadata** - Gather titles, descriptions, paths from all converted files
2. **Generate SKILL.md** - Create the index using `generate_skill_md`
3. **Organize sections** - Group pages logically (Getting Started, Guides, API, etc.)
4. **Write index** - Use `write_skill_file` to save SKILL.md
5. **Package skill** - Use `package_skill` to create the zip archive

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
| File | Contents |
|------|----------|
| `guides/auth.md` | Authentication setup |
| `guides/advanced.md` | Advanced usage patterns |

## API Reference
- `api/endpoints.md` — API endpoint documentation
- `api/schemas.md` — Request/response schemas
```

## Quality Checks

Before packaging:
- [ ] SKILL.md has valid YAML frontmatter
- [ ] All referenced files exist
- [ ] Descriptions are concise (<100 chars)
- [ ] Sections are logically organized
- [ ] No duplicate entries
```

---

## 5. MAIN ORCHESTRATOR

### File: skill_scraper_bot.py

```python
"""
Skill Scraper Bot - Main Orchestrator

Coordinates crawling, conversion, and skill packaging using
Claude Agent SDK with custom MCP tools and parallel subagents.

Usage:
    python skill_scraper_bot.py https://docs.example.com
    python skill_scraper_bot.py https://docs.example.com --max-pages 100 --output ./skills
    
Version: 1.0.0
"""

import asyncio
import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

# Import our custom tools
from tools.scraper_tools import get_scraper_tools, get_allowed_tools


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

1. **CRAWL** - Use the `skill-crawler` subagent to discover and fetch all pages
2. **CONVERT** - Use the `skill-converter` subagent to transform HTML to markdown
3. **INDEX** - Use the `skill-indexer` subagent to create SKILL.md and package

## Available Custom Tools

You have access to these MCP tools (use them directly or via subagents):

- `mcp__skill-scraper__check_robots` - Check robots.txt (ALWAYS DO FIRST)
- `mcp__skill-scraper__scrape_page` - Fetch a single URL
- `mcp__skill-scraper__discover_links` - Extract internal links from HTML
- `mcp__skill-scraper__convert_to_md` - Convert HTML to markdown
- `mcp__skill-scraper__analyze_content` - Generate descriptions for index
- `mcp__skill-scraper__write_skill_file` - Write file to skill directory
- `mcp__skill-scraper__generate_skill_md` - Create SKILL.md content
- `mcp__skill-scraper__package_skill` - Create final zip archive

## Execution Strategy

For LARGE sites (>50 pages), use parallel subagents:
```
1. Crawler discovers all URLs (breadth-first)
2. Spawn multiple Converter agents in parallel (batch of 10)
3. Indexer assembles final skill
```

For SMALL sites (<50 pages), work sequentially:
```
1. Crawl → Convert → Index in single flow
```

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
    
    print(f"\n{Colors.CYAN}{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.RESET}")
    print(f"{Colors.CYAN}  SKILL SCRAPER BOT{Colors.RESET}")
    print(f"{Colors.CYAN}═══════════════════════════════════════════════════════════════{Colors.RESET}")
    print(f"{Colors.DIM}Target URL:  {url}{Colors.RESET}")
    print(f"{Colors.DIM}Skill Name:  {skill_name}{Colors.RESET}")
    print(f"{Colors.DIM}Max Pages:   {max_pages}{Colors.RESET}")
    print(f"{Colors.DIM}Output Dir:  {output_dir}{Colors.RESET}")
    print(f"{Colors.CYAN}═══════════════════════════════════════════════════════════════{Colors.RESET}\n")
    
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

    # Configure options with custom MCP tools and subagents
    options = ClaudeAgentOptions(
        cwd=str(Path.cwd()),
        mcp_servers=get_scraper_tools(),
        allowed_tools=[
            # Standard tools
            "Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task",
            # Our custom MCP tools
            *get_allowed_tools()
        ],
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        permission_mode="acceptEdits",
        # Subagent definitions
        agents={
            "skill-crawler": {
                "description": "Web crawler specialist. Use for discovering and fetching pages from documentation sites.",
                "prompt": """You are a web crawler. Your job is to:
1. Check robots.txt first
2. Fetch pages using scrape_page
3. Discover links using discover_links
4. Return all discovered URLs and their HTML content

Be systematic. Track visited URLs. Report progress.""",
                "tools": [
                    "mcp__skill-scraper__check_robots",
                    "mcp__skill-scraper__scrape_page", 
                    "mcp__skill-scraper__discover_links"
                ],
                "model": "sonnet"
            },
            "skill-converter": {
                "description": "Content converter. Use for HTML to markdown conversion.",
                "prompt": """You are a content converter. Your job is to:
1. Convert HTML to markdown using convert_to_md
2. Analyze content for descriptions using analyze_content
3. Write files to skill structure using write_skill_file

Preserve code blocks, tables, and headers. Remove navigation noise.""",
                "tools": [
                    "mcp__skill-scraper__convert_to_md",
                    "mcp__skill-scraper__analyze_content",
                    "mcp__skill-scraper__write_skill_file"
                ],
                "model": "sonnet"
            },
            "skill-indexer": {
                "description": "Index generator. Use for creating SKILL.md and packaging.",
                "prompt": """You are an index generator. Your job is to:
1. Collect all page metadata
2. Generate SKILL.md using generate_skill_md
3. Write the index file
4. Package the skill using package_skill

Create clear, organized documentation indexes.""",
                "tools": [
                    "mcp__skill-scraper__generate_skill_md",
                    "mcp__skill-scraper__write_skill_file",
                    "mcp__skill-scraper__package_skill"
                ],
                "model": "sonnet"
            }
        }
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
        success = False
    
    # Report final status
    print(f"\n{Colors.CYAN}═══════════════════════════════════════════════════════════════{Colors.RESET}")
    if success:
        skill_path = Path(output_dir) / skill_name
        zip_path = Path(output_dir) / f"{skill_name}_skill.zip"
        print(f"{Colors.GREEN}✓ Skill generated successfully!{Colors.RESET}")
        print(f"{Colors.DIM}  Skill directory: {skill_path}{Colors.RESET}")
        print(f"{Colors.DIM}  Zip archive:     {zip_path}{Colors.RESET}")
    else:
        print(f"{Colors.RED}✗ Skill generation failed or incomplete{Colors.RESET}")
    print(f"{Colors.CYAN}═══════════════════════════════════════════════════════════════{Colors.RESET}\n")
    
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
  python skill_scraper_bot.py https://docs.python.org/3/
  python skill_scraper_bot.py https://fastapi.tiangolo.com --max-pages 100
  python skill_scraper_bot.py https://docs.anthropic.com --output ./my_skills
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
```

---

## 6. DEPENDENCIES

### requirements.txt (additions)

```
httpx>=0.27.0
beautifulsoup4>=4.12.0
markdownify>=0.12.0
aiofiles>=24.1.0
lxml>=5.0.0
```

### Install command
```bash
pip install httpx beautifulsoup4 markdownify aiofiles lxml --break-system-packages
```

---

## 7. INTEGRATION CHECKLIST

### Files to Create
- [ ] `tools/scraper_tools.py` - Custom MCP tools
- [ ] `skill_scraper_bot.py` - Main orchestrator
- [ ] `.claude/agents/skill-crawler.md` - Crawler subagent
- [ ] `.claude/agents/skill-converter.md` - Converter subagent
- [ ] `.claude/agents/skill-indexer.md` - Indexer subagent

### Wire into Existing System
- [ ] Add `from tools.scraper_tools import get_scraper_tools` to claude_cli.py
- [ ] Add scraper tools to available MCP servers
- [ ] Create preset: `.claude/presets/scrape_skill.md`

### Testing
```bash
# Test individual tools
python -c "from tools.scraper_tools import scraper_server; print('Tools loaded OK')"

# Test small site
python skill_scraper_bot.py https://htmx.org/docs/ --max-pages 20

# Test medium site
python skill_scraper_bot.py https://docs.anthropic.com --max-pages 100

# Verify output
ls -la scraped_skills/
unzip -l scraped_skills/*_skill.zip
```

---

## 8. AGENT EXECUTION BLOCK

Copy this to run with your SDK agent:

```
SKILL SCRAPER BOT BUILD

TASK 1 - Setup:
Create directories:
- tools/
- .claude/agents/
- scraped_skills/

TASK 2 - Create MCP Tools:
Create file: tools/scraper_tools.py
[See Section 3 code block]

Create file: tools/__init__.py
```python
from .scraper_tools import get_scraper_tools, get_allowed_tools, scraper_server
```

TASK 3 - Create Subagents:
Create file: .claude/agents/skill-crawler.md [See Section 4]
Create file: .claude/agents/skill-converter.md [See Section 4]
Create file: .claude/agents/skill-indexer.md [See Section 4]

TASK 4 - Create Main Bot:
Create file: skill_scraper_bot.py [See Section 5]

TASK 5 - Install Dependencies:
Run: pip install httpx beautifulsoup4 markdownify aiofiles lxml --break-system-packages

TASK 6 - Test:
Run: python -c "from tools.scraper_tools import scraper_server; print('OK')"
Run: python skill_scraper_bot.py https://htmx.org/docs/ --max-pages 10

COMPLETION CRITERIA:
- All files created without syntax errors
- Tools import successfully
- Bot runs and produces output in scraped_skills/
- Zip file is valid and contains SKILL.md
```

---

## 9. USAGE

After build is complete:

```bash
# Basic usage
python skill_scraper_bot.py https://docs.example.com

# With limits
python skill_scraper_bot.py https://fastapi.tiangolo.com --max-pages 100

# Custom output
python skill_scraper_bot.py https://docs.anthropic.com -o ./my_skills -m 200

# Quiet mode
python skill_scraper_bot.py https://htmx.org/docs/ -q
```

### Output Structure
```
scraped_skills/
└── docs-anthropic-com/
    ├── SKILL.md
    ├── getting-started/
    │   ├── quickstart.md
    │   └── installation.md
    ├── guides/
    │   ├── prompt-engineering.md
    │   └── tool-use.md
    ├── api/
    │   └── messages.md
    └── docs-anthropic-com_skill.zip
```

---

## 10. TIME ESTIMATE

| Phase | Estimated Time |
|-------|---------------|
| Create tools/scraper_tools.py | 5-10 min |
| Create subagent definitions | 2-3 min |
| Create main orchestrator | 3-5 min |
| Install dependencies | 1 min |
| Test & debug | 5-10 min |
| **Total** | **15-30 min** |

With parallel agents handling the heavy lifting, a 100-page site should scrape and convert in **~5 minutes**.
