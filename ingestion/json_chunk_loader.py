"""
JSON Chunk Loader - Phase 3 Ingestion

Loads JSON chunk files from all departments (Sales, Purchasing, Warehouse).
Validates structure and prepares for database insertion.

Usage:
    from ingestion.json_chunk_loader import load_all_chunks

    chunks = load_all_chunks()
    for chunk in chunks:
        print(f"{chunk['department']}/{chunk['file']}: {chunk['id']}")
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class LoadedChunk:
    """A single chunk loaded from JSON with metadata."""
    # Chunk data
    chunk_id: str
    category: str
    subcategory: str
    keywords: List[str]
    content: str

    # Source metadata
    department: str
    source_file: str
    file_hash: str
    knowledge_base: str

    # Token count (approximate)
    token_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for database insertion."""
        return {
            'chunk_id': self.chunk_id,
            'category': self.category,
            'subcategory': self.subcategory,
            'keywords': self.keywords,
            'content': self.content,
            'department': self.department,
            'source_file': self.source_file,
            'file_hash': self.file_hash,
            'knowledge_base': self.knowledge_base,
            'token_count': self.token_count,
        }


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def approximate_token_count(text: str) -> int:
    """
    Approximate token count (4 chars ≈ 1 token).
    More accurate than just splitting by spaces.
    """
    return len(text) // 4


def load_json_file(file_path: Path) -> List[LoadedChunk]:
    """
    Load a single JSON chunk file.

    Args:
        file_path: Path to JSON file

    Returns:
        List of LoadedChunk objects
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract department from path (e.g., "Manuals/Driscoll/Warehouse/chunks/...")
    path_parts = file_path.parts
    if 'Driscoll' in path_parts:
        dept_index = path_parts.index('Driscoll') + 1
        department = path_parts[dept_index].lower()  # "Sales", "Warehouse", etc.
    else:
        department = 'unknown'

    # Extract chunks
    chunks = []
    knowledge_base = data.get('knowledge_base', 'unknown')

    for chunk_data in data.get('chunks', []):
        # Compute unique hash for THIS chunk (not the file)
        # Hash: source_file + chunk_id + content
        chunk_content = chunk_data.get('content', '')
        chunk_id = chunk_data.get('id', 'unknown')
        unique_string = f"{file_path.name}::{chunk_id}::{chunk_content}"
        chunk_hash = hashlib.sha256(unique_string.encode('utf-8')).hexdigest()

        chunk = LoadedChunk(
            chunk_id=chunk_id,
            category=chunk_data.get('category', 'general'),
            subcategory=chunk_data.get('subcategory', 'general'),
            keywords=chunk_data.get('keywords', []),
            content=chunk_content,
            department=department,
            source_file=file_path.name,
            file_hash=chunk_hash,  # Unique per chunk
            knowledge_base=knowledge_base,
            token_count=approximate_token_count(chunk_content),
        )
        chunks.append(chunk)

    return chunks


def load_all_chunks(base_path: Optional[Path] = None) -> List[LoadedChunk]:
    """
    Load all JSON chunk files from all departments.

    Args:
        base_path: Base path to Manuals directory (defaults to auto-detect)

    Returns:
        List of all loaded chunks
    """
    if base_path is None:
        # Auto-detect base path
        base_path = Path(__file__).parent.parent / 'Manuals' / 'Driscoll'

    all_chunks = []
    departments = ['Sales', 'Purchasing', 'Warehouse']

    for dept in departments:
        dept_path = base_path / dept

        # Sales and Purchasing have chunks at root level
        if dept in ['Sales', 'Purchasing']:
            json_files = list(dept_path.glob('*_chunks.json'))
        # Warehouse has chunks in subdirectory
        else:
            chunks_dir = dept_path / 'chunks'
            if chunks_dir.exists():
                json_files = list(chunks_dir.glob('*_chunks.json'))
            else:
                json_files = []

        for json_file in json_files:
            try:
                chunks = load_json_file(json_file)
                all_chunks.extend(chunks)
                print(f"[OK] Loaded {len(chunks)} chunks from {dept}/{json_file.name}")
            except Exception as e:
                print(f"[ERROR] Failed to load {dept}/{json_file.name}: {e}")

    return all_chunks


def get_summary_stats(chunks: List[LoadedChunk]) -> Dict[str, Any]:
    """Get summary statistics about loaded chunks."""
    by_dept = {}
    by_category = {}
    total_tokens = 0

    for chunk in chunks:
        # By department
        by_dept[chunk.department] = by_dept.get(chunk.department, 0) + 1

        # By category
        by_category[chunk.category] = by_category.get(chunk.category, 0) + 1

        # Total tokens
        total_tokens += chunk.token_count

    return {
        'total_chunks': len(chunks),
        'by_department': by_dept,
        'by_category': by_category,
        'total_tokens': total_tokens,
        'avg_tokens_per_chunk': total_tokens // len(chunks) if chunks else 0,
    }


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    from pprint import pprint

    print("JSON Chunk Loader - Phase 3")
    print("=" * 80)

    # Load all chunks
    chunks = load_all_chunks()

    # Summary
    stats = get_summary_stats(chunks)
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    pprint(stats)

    # Sample chunk
    if chunks:
        print("\n" + "=" * 80)
        print("SAMPLE CHUNK")
        print("=" * 80)
        sample = chunks[0]
        print(f"ID: {sample.chunk_id}")
        print(f"Department: {sample.department}")
        print(f"Category: {sample.category}/{sample.subcategory}")
        print(f"Keywords: {', '.join(sample.keywords[:5])}")
        print(f"Content preview: {sample.content[:200]}...")
        print(f"Token count: {sample.token_count}")

    print("\n[SUCCESS] Chunk loading test complete")
