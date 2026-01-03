#!/usr/bin/env python3
"""
Skill Scraper - Standalone Edition

Converts documentation websites into Claude skill packages.
Pure Python - no Claude orchestration needed.

Usage:
    python scraper.py https://docs.example.com
    python scraper.py https://docs.example.com --max-pages 100
    python scraper.py https://docs.datadoghq.com/integrations/aws/ -o ./skills

Output:
    ./scraped_skills/{domain}/
        SKILL.md           # Index with metadata
        getting-started/   # Organized markdown files
        api-reference/
        ...
        {domain}_skill.zip # Complete archive
"""

import asyncio
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
from typing import Optional
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_HEADERS = {
    "User-Agent": "SkillScraper/2.0 (Educational; https://github.com)",
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
    '/assets/', '/images/', '/fonts/', '/__/', '/api/', '/_',
}


class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Page:
    """Represents a scraped page."""
    url: str
    title: str
    html: str
    markdown: str = ""
    description: str = ""
    content_type: str = "documentation"
    filepath: str = ""


@dataclass 
class ScrapeResult:
    """Result of a scraping run."""
    skill_name: str
    pages: list[Page] = field(default_factory=list)
    failed_urls: list[str] = field(default_factory=list)
    output_dir: Path = None
    zip_path: Path = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def normalize_url(url: str, base_url: str = None) -> str:
    """Normalize URL: remove fragments, trailing slashes, ensure absolute."""
    if base_url:
        url = urljoin(base_url, url)
    
    parsed = urlparse(url)
    path = parsed.path.rstrip('/') or '/'
    return urlunparse((
        parsed.scheme,
        parsed.netloc.lower(),
        path,
        parsed.params,
        parsed.query,
        ''  # Remove fragment
    ))


def url_to_filepath(url: str) -> str:
    """Convert URL to relative file path."""
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    
    if not path:
        return 'index.md'
    
    # Remove file extension if present
    if '.' in path.split('/')[-1]:
        path = path.rsplit('.', 1)[0]
    
    # Clean segments
    segments = [re.sub(r'[^\w\-]', '_', seg) for seg in path.split('/') if seg]
    
    if not segments:
        return 'index.md'
    
    return '/'.join(segments) + '.md'


def should_crawl_url(url: str, base_domain: str, base_path: str = "") -> bool:
    """Determine if URL should be crawled."""
    parsed = urlparse(url)
    
    # Must be same domain
    if parsed.netloc.lower() != base_domain.lower():
        return False
    
    # Must be under base path (if specified)
    if base_path and not parsed.path.startswith(base_path):
        return False
    
    path_lower = parsed.path.lower()
    
    # Skip excluded extensions
    if any(path_lower.endswith(ext) for ext in EXCLUDED_EXTENSIONS):
        return False
    
    # Skip excluded paths
    if any(excl in parsed.path for excl in EXCLUDED_PATHS):
        return False
    
    # Must be http(s)
    if parsed.scheme not in ('http', 'https'):
        return False
    
    return True


def clean_html(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove non-content elements from HTML."""
    # Remove script, style, nav, etc.
    for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header',
                               'aside', 'noscript', 'iframe', 'svg']):
        tag.decompose()
    
    # Remove elements by class/id patterns
    noise_patterns = [
        'nav', 'navigation', 'menu', 'sidebar', 'footer', 'header',
        'advertisement', 'ad-', 'social', 'share', 'comment', 'cookie',
        'popup', 'modal', 'newsletter', 'subscribe', 'promo', 'banner'
    ]
    
    for pattern in noise_patterns:
        for element in soup.find_all(class_=re.compile(pattern, re.I)):
            element.decompose()
        for element in soup.find_all(id=re.compile(pattern, re.I)):
            element.decompose()
    
    return soup


def html_to_markdown(html: str) -> str:
    """Convert HTML to clean markdown."""
    soup = BeautifulSoup(html, 'html.parser')
    soup = clean_html(soup)
    
    # Find main content area
    main_content = (
        soup.find('main') or
        soup.find('article') or
        soup.find('div', class_=re.compile(r'content|main|body|docs', re.I)) or
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
    
    # Clean up
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    markdown = re.sub(r' +', ' ', markdown)
    
    return markdown.strip()


def extract_title(soup: BeautifulSoup) -> str:
    """Extract page title."""
    # Try various sources
    if soup.title and soup.title.string:
        title = soup.title.string
    elif soup.find('h1'):
        title = soup.find('h1').get_text()
    elif soup.find('meta', property='og:title'):
        title = soup.find('meta', property='og:title').get('content', '')
    else:
        title = 'Untitled'
    
    # Clean up
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.split(r'\s*[\|–—-]\s*', title)[0].strip()
    
    return title or 'Untitled'


def extract_description(soup: BeautifulSoup, markdown: str) -> str:
    """Extract or generate page description."""
    # Try meta description
    meta = soup.find('meta', attrs={'name': 'description'})
    if meta and meta.get('content'):
        return meta['content'].strip()[:200]
    
    # Try og:description
    og = soup.find('meta', property='og:description')
    if og and og.get('content'):
        return og['content'].strip()[:200]
    
    # Fall back to first paragraph
    lines = [l.strip() for l in markdown.split('\n') if l.strip() and not l.startswith('#')]
    if lines:
        desc = lines[0][:200]
        if len(lines[0]) > 200:
            desc = desc.rsplit(' ', 1)[0] + '...'
        return desc
    
    return 'No description available'


def classify_content(url: str, markdown: str) -> str:
    """Classify content type for organization."""
    url_lower = url.lower()
    md_lower = markdown.lower()
    
    if re.search(r'api|endpoint|request|response|reference', url_lower):
        return "api_reference"
    elif re.search(r'install|setup|getting.started|quickstart|quick-start', url_lower):
        return "getting_started"
    elif re.search(r'guide|tutorial|how.to|walkthrough', url_lower):
        return "guide"
    elif re.search(r'example|sample|demo', url_lower):
        return "examples"
    elif re.search(r'config|settings|options|configuration', url_lower):
        return "configuration"
    elif re.search(r'troubleshoot|faq|debug|error', url_lower):
        return "troubleshooting"
    else:
        return "documentation"


def extract_links(html: str, base_url: str, base_domain: str, base_path: str = "") -> set[str]:
    """Extract internal links from HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    links = set()
    
    for anchor in soup.find_all('a', href=True):
        href = anchor['href']
        
        # Skip non-navigable links
        if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            continue
        
        # Normalize to absolute URL
        absolute_url = normalize_url(href, base_url)
        
        # Check if should crawl
        if should_crawl_url(absolute_url, base_domain, base_path):
            links.add(absolute_url)
    
    return links


# =============================================================================
# SCRAPER CLASS
# =============================================================================

class SkillScraper:
    """Standalone documentation scraper."""
    
    def __init__(
        self,
        max_pages: int = 500,
        output_dir: str = "./scraped_skills",
        crawl_delay: float = 0.5,
        timeout: int = 30,
        verbose: bool = True
    ):
        self.max_pages = max_pages
        self.output_dir = Path(output_dir)
        self.crawl_delay = crawl_delay
        self.timeout = timeout
        self.verbose = verbose
        
        self.client: Optional[httpx.AsyncClient] = None
    
    def log(self, msg: str, color: str = ""):
        """Print log message if verbose."""
        if self.verbose:
            print(f"{color}{msg}{Colors.RESET}")
    
    async def check_robots(self, url: str) -> tuple[bool, float]:
        """Check robots.txt for permission and crawl delay."""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        try:
            response = await self.client.get(robots_url, timeout=10)
            if response.status_code == 200:
                rp = RobotFileParser()
                rp.parse(response.text.split('\n'))
                
                allowed = rp.can_fetch(DEFAULT_HEADERS['User-Agent'], url)
                delay = rp.crawl_delay(DEFAULT_HEADERS['User-Agent']) or self.crawl_delay
                
                return allowed, delay
        except:
            pass
        
        return True, self.crawl_delay
    
    async def fetch_page(self, url: str) -> Optional[Page]:
        """Fetch and parse a single page."""
        try:
            response = await self.client.get(url, timeout=self.timeout, follow_redirects=True)
            response.raise_for_status()
            
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            title = extract_title(soup)
            markdown = html_to_markdown(html)
            description = extract_description(soup, markdown)
            content_type = classify_content(url, markdown)
            filepath = url_to_filepath(url)
            
            return Page(
                url=str(response.url),
                title=title,
                html=html,
                markdown=markdown,
                description=description,
                content_type=content_type,
                filepath=filepath
            )
            
        except Exception as e:
            self.log(f"  Failed: {url} - {e}", Colors.RED)
            return None
    
    async def scrape(self, start_url: str) -> ScrapeResult:
        """Scrape a documentation site starting from URL."""
        
        # Parse base URL
        parsed = urlparse(start_url)
        base_domain = parsed.netloc
        base_path = parsed.path.rstrip('/')
        skill_name = base_domain.replace('www.', '').replace('.', '-')
        
        # Add path to skill name if not root
        if base_path and base_path != '/':
            path_suffix = base_path.strip('/').replace('/', '-')
            skill_name = f"{skill_name}--{path_suffix}"
        
        self.log(f"\n{'=' * 60}", Colors.CYAN)
        self.log(f"  SKILL SCRAPER", Colors.CYAN + Colors.BOLD)
        self.log(f"{'=' * 60}", Colors.CYAN)
        self.log(f"Target: {start_url}", Colors.DIM)
        self.log(f"Skill:  {skill_name}", Colors.DIM)
        self.log(f"Max:    {self.max_pages} pages", Colors.DIM)
        self.log(f"{'=' * 60}\n", Colors.CYAN)
        
        result = ScrapeResult(skill_name=skill_name)
        
        # Create HTTP client
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS) as self.client:
            
            # Check robots.txt
            self.log("Checking robots.txt...", Colors.DIM)
            allowed, delay = await self.check_robots(start_url)
            
            if not allowed:
                self.log("Blocked by robots.txt!", Colors.RED)
                return result
            
            self.crawl_delay = max(delay, self.crawl_delay)
            self.log(f"Crawl delay: {self.crawl_delay}s", Colors.DIM)
            
            # BFS crawl
            visited: set[str] = set()
            queue: list[str] = [normalize_url(start_url)]
            
            while queue and len(result.pages) < self.max_pages:
                url = queue.pop(0)
                
                if url in visited:
                    continue
                visited.add(url)
                
                # Fetch page
                self.log(f"[{len(result.pages) + 1}/{self.max_pages}] {url[:70]}...", Colors.DIM)
                page = await self.fetch_page(url)
                
                if page:
                    result.pages.append(page)
                    
                    # Extract and queue new links
                    new_links = extract_links(page.html, url, base_domain, base_path)
                    for link in new_links:
                        if link not in visited and link not in queue:
                            queue.append(link)
                else:
                    result.failed_urls.append(url)
                
                # Respect crawl delay
                await asyncio.sleep(self.crawl_delay)
        
        self.log(f"\nCrawled {len(result.pages)} pages ({len(result.failed_urls)} failed)", Colors.GREEN)
        
        # Write output
        if result.pages:
            await self.write_output(result)
        
        return result
    
    async def write_output(self, result: ScrapeResult):
        """Write scraped content to skill directory."""
        
        skill_dir = self.output_dir / result.skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        result.output_dir = skill_dir
        
        self.log(f"\nWriting to {skill_dir}...", Colors.DIM)
        
        # Write each page
        for page in result.pages:
            file_path = skill_dir / page.filepath
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Add frontmatter
            content = f"""---
title: {page.title}
url: {page.url}
type: {page.content_type}
---

# {page.title}

{page.markdown}
"""
            file_path.write_text(content, encoding='utf-8')
        
        # Generate SKILL.md
        skill_md = self.generate_skill_md(result)
        (skill_dir / "SKILL.md").write_text(skill_md, encoding='utf-8')
        
        # Create zip archive
        zip_path = self.output_dir / f"{result.skill_name}_skill.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in skill_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(skill_dir.parent)
                    zf.write(file_path, arcname)
        
        result.zip_path = zip_path
        
        self.log(f"Created {zip_path} ({zip_path.stat().st_size / 1024:.1f} KB)", Colors.GREEN)
    
    def generate_skill_md(self, result: ScrapeResult) -> str:
        """Generate SKILL.md index file."""
        
        # Group pages by content type
        grouped: dict[str, list[Page]] = {}
        for page in result.pages:
            ct = page.content_type
            if ct not in grouped:
                grouped[ct] = []
            grouped[ct].append(page)
        
        # Build index
        lines = [
            "---",
            f"name: {result.skill_name}",
            f"pages: {len(result.pages)}",
            f"generated: {datetime.now().isoformat()}",
            "---",
            "",
            f"# {result.skill_name.replace('-', ' ').title()}",
            "",
            f"Documentation skill with {len(result.pages)} pages.",
            "",
            "Use `view` to lazy-load any file.",
            "",
        ]
        
        # Section order
        sections = [
            ("getting_started", "Getting Started"),
            ("guide", "Guides"),
            ("api_reference", "API Reference"),
            ("configuration", "Configuration"),
            ("examples", "Examples"),
            ("troubleshooting", "Troubleshooting"),
            ("documentation", "Documentation"),
        ]
        
        for content_type, section_title in sections:
            if content_type in grouped:
                pages = sorted(grouped[content_type], key=lambda p: p.filepath)
                lines.append(f"## {section_title}")
                lines.append("")
                for page in pages:
                    desc = page.description[:80] if page.description else ""
                    lines.append(f"- `{page.filepath}` - {desc}")
                lines.append("")
        
        return '\n'.join(lines)


# =============================================================================
# CLI
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="Skill Scraper - Convert documentation sites to Claude skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scraper.py https://docs.python.org/3/tutorial/
    python scraper.py https://fastapi.tiangolo.com/tutorial/ --max-pages 50
    python scraper.py https://docs.datadoghq.com/integrations/aws/ -o ./skills
        """
    )
    
    parser.add_argument("url", help="Starting URL to scrape")
    parser.add_argument("--max-pages", "-m", type=int, default=100,
                        help="Maximum pages to crawl (default: 100)")
    parser.add_argument("--output", "-o", default="./scraped_skills",
                        help="Output directory (default: ./scraped_skills)")
    parser.add_argument("--delay", "-d", type=float, default=0.5,
                        help="Crawl delay in seconds (default: 0.5)")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Minimal output")
    
    args = parser.parse_args()
    
    # Validate URL
    parsed = urlparse(args.url)
    if not parsed.scheme or not parsed.netloc:
        print(f"{Colors.RED}Error: Invalid URL. Include scheme (https://){Colors.RESET}")
        sys.exit(1)
    
    # Run scraper
    scraper = SkillScraper(
        max_pages=args.max_pages,
        output_dir=args.output,
        crawl_delay=args.delay,
        verbose=not args.quiet
    )
    
    result = await scraper.scrape(args.url)
    
    # Summary
    print(f"\n{'=' * 60}")
    if result.pages:
        print(f"{Colors.GREEN}SUCCESS{Colors.RESET}")
        print(f"  Pages:  {len(result.pages)}")
        print(f"  Output: {result.output_dir}")
        print(f"  Zip:    {result.zip_path}")
    else:
        print(f"{Colors.RED}FAILED - No pages scraped{Colors.RESET}")
        sys.exit(1)
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())