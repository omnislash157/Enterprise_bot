"""
DOCX to JSON Chunker
====================

Converts .docx process manuals into structured JSON chunks compatible with
existing Sales/Purchasing chunk format.

Features:
- Heading-based chunking (# Section Title)
- Paragraph aggregation under headings
- Smart token estimation (~4 chars = 1 token)
- Keyword extraction from content
- Department/category metadata
- File hash tracking for deduplication

Usage:
    from ingestion.docx_to_json_chunks import convert_docx_to_chunks

    chunks = convert_docx_to_chunks(
        docx_path="Manuals/Driscoll/Warehouse/Receiving Manual.docx",
        department="Warehouse",
        category="receiving"
    )
"""

import re
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from docx import Document
from docx.text.paragraph import Paragraph
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table


def extract_text_from_docx(docx_path: str) -> List[Dict[str, Any]]:
    """
    Extract all text blocks from DOCX with structure preservation.

    Returns list of blocks with:
    - type: 'heading' | 'paragraph' | 'table'
    - level: heading level (1-9) if applicable
    - text: extracted text
    """
    doc = Document(docx_path)
    blocks = []

    for element in doc.element.body:
        if isinstance(element, CT_P):
            para = Paragraph(element, doc)
            text = para.text.strip()
            if not text:
                continue

            # Detect heading by style or manual markers
            style_name = para.style.name.lower() if para.style else ""

            if "heading" in style_name:
                # Extract level from style (Heading 1, Heading 2, etc.)
                level_match = re.search(r'heading\s*(\d+)', style_name)
                level = int(level_match.group(1)) if level_match else 1
                blocks.append({
                    "type": "heading",
                    "level": level,
                    "text": text
                })
            elif text.startswith("#"):
                # Markdown-style heading
                level = len(re.match(r'^#+', text).group(0))
                blocks.append({
                    "type": "heading",
                    "level": level,
                    "text": text.lstrip("#").strip()
                })
            else:
                blocks.append({
                    "type": "paragraph",
                    "text": text
                })

        elif isinstance(element, CT_Tbl):
            table = Table(element, doc)
            table_text = extract_table_text(table)
            if table_text.strip():
                blocks.append({
                    "type": "table",
                    "text": table_text
                })

    return blocks


def extract_table_text(table: Table) -> str:
    """Extract text from table in readable format."""
    rows = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        if any(cells):  # Skip empty rows
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def estimate_tokens(text: str) -> int:
    """Estimate token count (~4 chars = 1 token for English)."""
    return len(text) // 4


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """
    Extract keywords from text using simple heuristics.

    - Convert to lowercase
    - Remove common words
    - Split on whitespace and punctuation
    - Take top N most frequent
    """
    # Common stopwords
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "can", "this", "that", "these",
        "those", "i", "you", "he", "she", "it", "we", "they", "what", "which",
        "who", "when", "where", "why", "how", "all", "each", "every", "both",
        "few", "more", "most", "other", "some", "such", "no", "nor", "not",
        "only", "own", "same", "so", "than", "too", "very", "as", "by", "from"
    }

    # Tokenize and clean
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    words = [w for w in words if w not in stopwords]

    # Count frequencies
    freq = {}
    for word in words:
        freq[word] = freq.get(word, 0) + 1

    # Sort by frequency and take top N
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:max_keywords]]


def generate_chunk_id(department: str, category: str, section_title: str, index: int) -> str:
    """Generate unique chunk ID."""
    base = f"{department}_{category}_{section_title}".lower()
    base = re.sub(r'[^a-z0-9]+', '_', base)
    base = base.strip('_')
    return f"{base}_{index}"


def compute_file_hash(docx_path: str) -> str:
    """Compute SHA256 hash of file for deduplication."""
    sha256 = hashlib.sha256()
    with open(docx_path, 'rb') as f:
        for block in iter(lambda: f.read(4096), b""):
            sha256.update(block)
    return sha256.hexdigest()


def chunk_by_sections(
    blocks: List[Dict[str, Any]],
    max_chunk_tokens: int = 500
) -> List[Dict[str, Any]]:
    """
    Group blocks into chunks by sections.

    Strategy:
    1. Start new chunk on heading
    2. Aggregate paragraphs under heading until token limit
    3. If single paragraph exceeds limit, create single-para chunk
    """
    chunks = []
    current_chunk = None
    current_section = "Introduction"

    for block in blocks:
        if block["type"] == "heading":
            # Save previous chunk if exists
            if current_chunk and current_chunk["content"].strip():
                chunks.append(current_chunk)

            # Start new chunk
            current_section = block["text"]
            current_chunk = {
                "section_title": current_section,
                "content": "",
                "token_count": 0
            }

        else:
            # Add to current chunk
            if current_chunk is None:
                # Handle content before first heading
                current_chunk = {
                    "section_title": current_section,
                    "content": "",
                    "token_count": 0
                }

            text = block["text"]
            tokens = estimate_tokens(text)

            # Check if adding this would exceed limit
            if current_chunk["token_count"] + tokens > max_chunk_tokens and current_chunk["content"]:
                # Save current chunk and start new one
                chunks.append(current_chunk)
                current_chunk = {
                    "section_title": current_section,
                    "content": text,
                    "token_count": tokens
                }
            else:
                # Add to current chunk
                if current_chunk["content"]:
                    current_chunk["content"] += "\n\n"
                current_chunk["content"] += text
                current_chunk["token_count"] += tokens

    # Save final chunk
    if current_chunk and current_chunk["content"].strip():
        chunks.append(current_chunk)

    return chunks


def convert_docx_to_chunks(
    docx_path: str,
    department: str,
    category: str,
    subcategory: Optional[str] = None,
    max_chunk_tokens: int = 500
) -> Dict[str, Any]:
    """
    Convert DOCX manual to JSON chunk structure.

    Args:
        docx_path: Path to .docx file
        department: Department name (e.g., "Warehouse")
        category: Primary category (e.g., "receiving")
        subcategory: Optional subcategory
        max_chunk_tokens: Maximum tokens per chunk

    Returns:
        Dictionary with:
        - knowledge_base: base name
        - version: "1.0"
        - description: brief description
        - source_file: original filename
        - file_hash: SHA256 hash
        - chunks: list of chunk objects
    """
    path = Path(docx_path)

    # Extract text blocks
    blocks = extract_text_from_docx(docx_path)

    if not blocks:
        raise ValueError(f"No content extracted from {docx_path}")

    # Chunk by sections
    raw_chunks = chunk_by_sections(blocks, max_chunk_tokens)

    # Build final chunk objects
    chunks = []
    for idx, raw_chunk in enumerate(raw_chunks):
        content = raw_chunk["content"]
        section = raw_chunk["section_title"]

        chunk = {
            "id": generate_chunk_id(department, category, section, idx),
            "category": category,
            "section_title": section,
            "keywords": extract_keywords(content, max_keywords=10),
            "content": content,
            "chunk_token_count": raw_chunk["token_count"]
        }

        if subcategory:
            chunk["subcategory"] = subcategory

        chunks.append(chunk)

    # Build output structure
    base_name = path.stem.lower().replace(" ", "_")
    knowledge_base = f"driscoll_{department.lower()}_{base_name}"

    return {
        "knowledge_base": knowledge_base,
        "version": "1.0",
        "description": f"{department} {category} processes and procedures",
        "source_file": path.name,
        "file_hash": compute_file_hash(docx_path),
        "chunks": chunks
    }


def save_chunks_to_json(chunks_data: Dict[str, Any], output_path: str) -> None:
    """Save chunks to JSON file with pretty formatting."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(chunks_data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # Test on a single file
    import sys

    if len(sys.argv) < 4:
        print("Usage: python docx_to_json_chunks.py <docx_path> <department> <category>")
        sys.exit(1)

    docx_path = sys.argv[1]
    department = sys.argv[2]
    category = sys.argv[3]

    try:
        chunks = convert_docx_to_chunks(docx_path, department, category)
        output_path = Path(docx_path).with_suffix(".json")
        save_chunks_to_json(chunks, str(output_path))
        print(f"✓ Converted {docx_path}")
        print(f"  → {len(chunks['chunks'])} chunks")
        print(f"  → {output_path}")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
