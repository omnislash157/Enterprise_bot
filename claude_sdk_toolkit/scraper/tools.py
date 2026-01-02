"""
Skill Scraper MCP Tools

Custom tools for web scraping and skill generation.
Designed for use with Claude Agent SDK.

Version: 1.1.0
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
    path = parsed.path.rstrip('/') or '/'
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc.lower(),
        path,
        parsed.params,
        parsed.query,
        ''
    ))
    return normalized


def url_to_filepath(url: str, base_domain: str) -> str:
    """Convert URL to relative file path for skill structure."""
    parsed = urlparse(url)
    path = parsed.path.strip('/')

    if not path:
        path = 'index'

    if '.' in path.split('/')[-1]:
        path = path.rsplit('.', 1)[0]

    segments = [re.sub(r'[^\w\-]', '_', seg) for seg in path.split('/') if seg]

    if not segments:
        return 'index.md'

    return '/'.join(segments) + '.md'


def should_crawl_url(url: str, base_domain: str) -> bool:
    """Determine if URL should be crawled."""
    parsed = urlparse(url)

    if parsed.netloc.lower() != base_domain.lower():
        return False

    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in EXCLUDED_EXTENSIONS):
        return False

    if any(excl in parsed.path for excl in EXCLUDED_PATHS):
        return False

    if parsed.scheme not in ('http', 'https'):
        return False

    return True


def clean_html_content(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove non-content elements from HTML."""
    for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header',
                               'aside', 'noscript', 'iframe', 'svg']):
        tag.decompose()

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

    main_content = (
        soup.find('main') or
        soup.find('article') or
        soup.find('div', class_=re.compile(r'content|main|body', re.I)) or
        soup.find('body') or
        soup
    )

    markdown = md(
        str(main_content),
        heading_style='atx',
        bullets='-',
        code_language_callback=lambda el: el.get('class', [''])[0].replace('language-', '') if el.get('class') else ''
    )

    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    markdown = re.sub(r' +', ' ', markdown)
    markdown = markdown.strip()

    return markdown


def extract_title(soup: BeautifulSoup) -> str:
    """Extract page title from HTML."""
    title = None

    if soup.title:
        title = soup.title.string

    if not title:
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text()

    if not title:
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title.get('content')

    if title:
        title = re.sub(r'\s+', ' ', title).strip()
        title = re.split(r'\s*[\|--]\s*', title)[0].strip()

    return title or 'Untitled'


def extract_description(soup: BeautifulSoup, markdown: str) -> str:
    """Extract or generate page description."""
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        return meta_desc['content'].strip()[:200]

    og_desc = soup.find('meta', property='og:description')
    if og_desc and og_desc.get('content'):
        return og_desc['content'].strip()[:200]

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

@tool("check_robots", "Check robots.txt for a domain and return crawl rules. Call this FIRST before crawling.", {"url": str})
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


@tool("scrape_page", "Fetch a single URL and return its HTML content, title, and metadata.", {"url": str, "timeout": int})
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
                        "html": html
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


@tool("discover_links", "Extract all internal links from HTML content.", {"html": str, "base_url": str, "base_domain": str})
async def discover_links(args: dict[str, Any]) -> dict[str, Any]:
    """Extract and filter internal links from HTML."""
    html = args["html"]
    base_url = args["base_url"]
    base_domain = args["base_domain"]

    soup = BeautifulSoup(html, 'html.parser')
    links = set()

    for anchor in soup.find_all('a', href=True):
        href = anchor['href']

        if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            continue

        absolute_url = normalize_url(href, base_url)

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


@tool("convert_to_md", "Convert HTML content to clean markdown.", {"html": str, "base_url": str})
async def convert_to_md(args: dict[str, Any]) -> dict[str, Any]:
    """Convert HTML to markdown with metadata."""
    html = args["html"]
    base_url = args.get("base_url", "")

    soup = BeautifulSoup(html, 'html.parser')

    title = extract_title(soup)
    markdown = html_to_markdown(html, base_url)
    description = extract_description(soup, markdown)

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


@tool("analyze_content", "Analyze markdown content to generate description for SKILL.md index.", {"markdown": str, "title": str, "url_path": str})
async def analyze_content(args: dict[str, Any]) -> dict[str, Any]:
    """Generate description for skill index entry."""
    markdown = args["markdown"]
    title = args["title"]
    url_path = args["url_path"]

    headers = re.findall(r'^#{1,3}\s+(.+)$', markdown, re.MULTILINE)

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
                "suggested_index_entry": f"`{url_path}` - {first_para[:100]}"
            }, indent=2)
        }]
    }


@tool("write_skill_file", "Write a markdown file to the skill output directory.", {"skill_name": str, "relative_path": str, "content": str, "output_dir": str})
async def write_skill_file(args: dict[str, Any]) -> dict[str, Any]:
    """Write file to skill directory structure."""
    skill_name = args["skill_name"]
    relative_path = args["relative_path"]
    content = args["content"]
    output_dir = args.get("output_dir", "./scraped_skills")

    skill_dir = Path(output_dir) / skill_name
    file_path = skill_dir / relative_path

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)

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
            "isError": True
        }


@tool("generate_skill_md", "Generate the SKILL.md index file from page metadata.", {"skill_name": str, "description": str, "pages": str})
async def generate_skill_md(args: dict[str, Any]) -> dict[str, Any]:
    """Generate SKILL.md content from page metadata."""
    skill_name = args["skill_name"]
    description = args["description"]
    pages = json.loads(args["pages"])

    grouped = {}
    for page in pages:
        content_type = page.get("content_type", "documentation")
        if content_type not in grouped:
            grouped[content_type] = []
        grouped[content_type].append(page)

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
                desc = page.get('description', '')[:80]
                lines.append(f"- `{path}` - {desc}")

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


@tool("package_skill", "Create a zip archive of the completed skill directory.", {"skill_name": str, "output_dir": str})
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
            "isError": True
        }


# =============================================================================
# CREATE MCP SERVER
# =============================================================================

scraper_server = create_sdk_mcp_server(
    name="skill-scraper",
    version="1.1.0",
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
# EXPORTS
# =============================================================================

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


# For backwards compatibility
def get_scraper_tools():
    """Get the scraper MCP server dict for legacy usage."""
    return {"skill-scraper": scraper_server}


__all__ = ["scraper_server", "get_allowed_tools", "get_scraper_tools"]