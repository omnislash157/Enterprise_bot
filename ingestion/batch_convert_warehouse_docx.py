"""
Batch DOCX to JSON Converter - Warehouse Manuals
==================================================

Converts all Warehouse .docx files to JSON chunk format.

Features:
- Parallel processing with multiprocessing
- Automatic category inference from filename
- Progress reporting
- Error handling per file
- Output to Manuals/Driscoll/Warehouse/chunks/

Usage:
    python ingestion/batch_convert_warehouse_docx.py [--workers 4] [--dry-run]

Output:
    Manuals/Driscoll/Warehouse/chunks/*.json (21 files)
"""

import argparse
import json
import multiprocessing as mp
from pathlib import Path
from typing import List, Dict, Any, Tuple
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.docx_to_json_chunks import convert_docx_to_chunks, save_chunks_to_json


# Category mapping based on filename patterns
CATEGORY_MAPPING = {
    "receiving": ["receiving"],
    "dispatching": ["dispatching", "dispatch"],
    "driver_checkin": ["driver check-in", "driver checkin"],
    "driver": ["driver manual"],
    "hr": ["hr manual"],
    "inventory": ["inventory control", "inventory"],
    "invoice": ["invoice cleaning"],
    "night_shift_checking": ["night shift checking"],
    "night_shift_clerk": ["night shift clerk"],
    "night_shift_hilo": ["night shift hi-lo"],
    "night_shift_loading": ["night shift loading"],
    "night_shift_picking": ["night shift picking"],
    "night_shift_supervisor": ["night shift supervisor"],
    "night_shift_switcher": ["night shift switcher"],
    "ops_admin": ["ops admin"],
    "putaway": ["putaway"],
    "replen": ["replen"],
    "routing": ["routing"],
    "transportation": ["transportation"],
    "upc": ["upc collecting", "upc"],
    "john_cantelli": ["john cantelli"]
}


def infer_category(filename: str) -> str:
    """
    Infer category from filename.

    Examples:
        "Receiving Manual.docx" -> "receiving"
        "Night Shift Picking Manual.docx" -> "night_shift_picking"
        "driver manual.docx" -> "driver"
    """
    filename_lower = filename.lower()

    for category, patterns in CATEGORY_MAPPING.items():
        for pattern in patterns:
            if pattern in filename_lower:
                return category

    # Fallback: use filename stem as category
    return Path(filename).stem.lower().replace(" ", "_").replace("-", "_")


def convert_single_file(args: Tuple[Path, Path, bool]) -> Dict[str, Any]:
    """
    Convert a single DOCX file to JSON chunks.

    Args:
        args: Tuple of (docx_path, output_dir, dry_run)

    Returns:
        Dict with result info
    """
    docx_path, output_dir, dry_run = args
    result = {
        "file": docx_path.name,
        "success": False,
        "chunks": 0,
        "output": None,
        "error": None
    }

    try:
        # Infer category
        category = infer_category(docx_path.name)

        # Convert to chunks
        chunks_data = convert_docx_to_chunks(
            docx_path=str(docx_path),
            department="Warehouse",
            category=category,
            max_chunk_tokens=500
        )

        result["chunks"] = len(chunks_data["chunks"])

        if not dry_run:
            # Save to chunks directory
            output_filename = docx_path.stem.lower().replace(" ", "_") + "_chunks.json"
            output_path = output_dir / output_filename
            save_chunks_to_json(chunks_data, str(output_path))
            result["output"] = str(output_path)

        result["success"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


def batch_convert_warehouse_manuals(
    warehouse_dir: Path,
    output_dir: Path,
    workers: int = 4,
    dry_run: bool = False
) -> List[Dict[str, Any]]:
    """
    Convert all DOCX files in Warehouse directory to JSON chunks.

    Args:
        warehouse_dir: Path to Manuals/Driscoll/Warehouse
        output_dir: Path to output directory (will be created)
        workers: Number of parallel workers
        dry_run: If True, don't write files

    Returns:
        List of result dicts
    """
    # Find all DOCX files
    docx_files = sorted(warehouse_dir.glob("*.docx"))

    if not docx_files:
        print(f"⚠ No .docx files found in {warehouse_dir}")
        return []

    print(f"Found {len(docx_files)} DOCX files")
    print(f"Output directory: {output_dir}")
    print(f"Workers: {workers}")
    print(f"Dry run: {dry_run}")
    print()

    # Create output directory
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare arguments for parallel processing
    args_list = [(f, output_dir, dry_run) for f in docx_files]

    # Process in parallel
    if workers > 1:
        with mp.Pool(workers) as pool:
            results = pool.map(convert_single_file, args_list)
    else:
        results = [convert_single_file(args) for args in args_list]

    return results


def print_results(results: List[Dict[str, Any]]) -> None:
    """Print conversion results summary."""
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print("\n" + "=" * 60)
    print("CONVERSION RESULTS")
    print("=" * 60)

    if successful:
        print(f"\n✓ Successfully converted {len(successful)} files:")
        total_chunks = sum(r["chunks"] for r in successful)
        for r in successful:
            status = f"  {r['file']:<45} → {r['chunks']:>3} chunks"
            if r["output"]:
                print(status)
            else:
                print(status + " (dry run)")
        print(f"\nTotal chunks: {total_chunks}")

    if failed:
        print(f"\n✗ Failed to convert {len(failed)} files:")
        for r in failed:
            print(f"  {r['file']}: {r['error']}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Batch convert Warehouse DOCX manuals to JSON chunks"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write output files, just test conversion"
    )
    parser.add_argument(
        "--warehouse-dir",
        type=str,
        default="Manuals/Driscoll/Warehouse",
        help="Path to Warehouse directory (default: Manuals/Driscoll/Warehouse)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="Manuals/Driscoll/Warehouse/chunks",
        help="Output directory for JSON chunks (default: Manuals/Driscoll/Warehouse/chunks)"
    )

    args = parser.parse_args()

    # Resolve paths
    warehouse_dir = Path(args.warehouse_dir)
    output_dir = Path(args.output_dir)

    if not warehouse_dir.exists():
        print(f"✗ Error: Warehouse directory not found: {warehouse_dir}")
        sys.exit(1)

    # Run batch conversion
    results = batch_convert_warehouse_manuals(
        warehouse_dir=warehouse_dir,
        output_dir=output_dir,
        workers=args.workers,
        dry_run=args.dry_run
    )

    # Print results
    print_results(results)

    # Exit with error code if any failed
    failed_count = sum(1 for r in results if not r["success"])
    if failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
