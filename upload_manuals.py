"""
Bulk Manual Uploader - Reads .docx and .json files and inserts into Supabase department_content

Usage:
    python upload_manuals.py           # Dry run
    python upload_manuals.py --execute # Actually upload

Requirements:
    pip install python-docx supabase python-dotenv

Folder structure expected:
    Manuals/Driscoll/
    ├── Warehouse/
    │   ├── Driver Check-in Manual.docx
    │   ├── Driver Check-in Manual.json  ← JSON also supported
    │   ├── Receiving Procedures.docx
    │   └── ...
    ├── Sales/
    │   └── ...
    ├── Credit/
    │   └── ...
    └── ...

Supported formats:
    .docx - Converted to markdown (headings, lists, tables preserved)
    .json - Pretty-printed JSON string (LLM reads it fine)
"""

import os
import json
from pathlib import Path
from docx import Document
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIG
# =============================================================================

# Path to your manuals folder
MANUALS_ROOT = Path(r"C:\Users\mthar\projects\enterprise_bot\Manuals\Driscoll")

# Department folder name → Supabase department_id mapping
# From your JSON export
DEPARTMENT_IDS = {
    "warehouse": "0519634e-1731-42d0-875e-ac640dbdedc4",
    "sales": "018951b1-520e-4f20-988e-60aed6c239c4",
    "credit": "34a816ed-400f-43ba-9b56-4d75e76838e7",
    "purchasing": "4b14f65a-642b-4fc8-8afb-61d939b45c59",
    "transportation": "aed7a2cc-204f-4c07-bb98-87def3885568",
    "executive": "fd390515-1d45-489b-aa78-5447fa6dd8fd",
}

# Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Use service_role key for inserts, not anon


# =============================================================================
# DOCX READER
# =============================================================================

def read_docx(file_path: Path) -> str:
    """
    Extract text from a .docx file.
    Preserves paragraph structure with double newlines.
    """
    doc = Document(file_path)
    
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    
    # Also extract text from tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                paragraphs.append(row_text)
    
    return "\n\n".join(paragraphs)


def read_json_manual(file_path: Path) -> str:
    """
    Read JSON manual and convert to string for context stuffing.
    LLM reads pretty-printed JSON just fine.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return json.dumps(data, indent=2)


def read_docx_as_markdown(file_path: Path) -> str:
    """
    Extract text from .docx and convert to basic markdown.
    Handles headings, bold, lists somewhat.
    """
    doc = Document(file_path)
    
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        
        # Check paragraph style for headings
        style_name = para.style.name.lower() if para.style else ""
        
        if "heading 1" in style_name:
            lines.append(f"# {text}")
        elif "heading 2" in style_name:
            lines.append(f"## {text}")
        elif "heading 3" in style_name:
            lines.append(f"### {text}")
        elif "list" in style_name or "bullet" in style_name:
            lines.append(f"- {text}")
        else:
            lines.append(text)
    
    # Tables as markdown
    for table in doc.tables:
        table_lines = []
        for i, row in enumerate(table.rows):
            cells = [cell.text.strip() for cell in row.cells]
            table_lines.append("| " + " | ".join(cells) + " |")
            if i == 0:
                # Header separator
                table_lines.append("|" + "|".join(["---"] * len(cells)) + "|")
        lines.extend(table_lines)
        lines.append("")  # blank line after table
    
    return "\n\n".join(lines)


# =============================================================================
# SUPABASE UPLOADER
# =============================================================================

def upload_manuals(dry_run: bool = True):
    """
    Walk through manual folders and upload to Supabase.
    
    Args:
        dry_run: If True, just print what would be uploaded without actually inserting
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Set SUPABASE_URL and SUPABASE_KEY in .env")
        return
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    uploaded = 0
    skipped = 0
    errors = []
    
    print(f"Scanning: {MANUALS_ROOT}\n")
    
    for dept_folder in MANUALS_ROOT.iterdir():
        if not dept_folder.is_dir():
            continue
        
        # Normalize folder name to match our mapping
        folder_name = dept_folder.name.lower().strip()
        
        # Handle variations
        folder_mapping = {
            "warehouse": "warehouse",
            "warehouse operations": "warehouse",
            "sales": "sales",
            "credit": "credit",
            "credit department": "credit",
            "purchasing": "purchasing",
            "transportation": "transportation",
            "executive": "executive",
            "executive team": "executive",
            "hr": "executive",  # Map HR to executive if no HR dept
        }
        
        dept_key = folder_mapping.get(folder_name)
        
        if not dept_key:
            print(f"⚠️  Unknown department folder: {dept_folder.name} - SKIPPING")
            skipped += 1
            continue
        
        dept_id = DEPARTMENT_IDS.get(dept_key)
        if not dept_id:
            print(f"⚠️  No department_id for: {dept_key} - SKIPPING")
            skipped += 1
            continue
        
        print(f"📁 {dept_folder.name} → {dept_key} ({dept_id})")

        # Process all .docx and .json files in this folder
        for file in dept_folder.glob("*"):
            # Skip temp files and unsupported formats
            if file.name.startswith("~$"):
                continue

            # Determine file type and reader
            if file.suffix == ".docx":
                reader = read_docx_as_markdown
            elif file.suffix == ".json":
                reader = read_json_manual
            else:
                continue  # Skip unsupported file types

            title = file.stem  # Filename without extension

            try:
                content = reader(file)
                
                if not content.strip():
                    print(f"   ⚠️  Empty file: {file.name}")
                    skipped += 1
                    continue
                
                print(f"   📄 {title} ({len(content)} chars)")
                
                if not dry_run:
                    # Check if this manual already exists
                    existing = supabase.table("department_content").select(
                        "id, version"
                    ).eq("department_id", dept_id).eq("title", title).execute()
                    
                    if existing.data:
                        # UPDATE existing - bump version
                        old_version = existing.data[0]["version"]
                        new_version = old_version + 1
                        record_id = existing.data[0]["id"]
                        
                        result = supabase.table("department_content").update({
                            "content": content,
                            "version": new_version,
                            "active": True,
                        }).eq("id", record_id).execute()
                        
                        print(f"      ↻ Updated (v{old_version} → v{new_version})")
                        uploaded += 1
                    else:
                        # INSERT new
                        result = supabase.table("department_content").insert({
                            "department_id": dept_id,
                            "content_type": "manual",
                            "title": title,
                            "content": content,
                            "version": 1,
                            "active": True,
                        }).execute()
                        
                        if result.data:
                            print(f"      ✓ Inserted (v1)")
                            uploaded += 1
                        else:
                            errors.append(f"{file.name}: Insert returned no data")
                else:
                    uploaded += 1

            except Exception as e:
                print(f"   ❌ Error reading {file.name}: {e}")
                errors.append(f"{file.name}: {e}")
    
    print("\n" + "="*50)
    print(f"{'DRY RUN ' if dry_run else ''}SUMMARY:")
    print(f"  ✅ {'Would upload' if dry_run else 'Uploaded'}: {uploaded}")
    print(f"  ⏭️  Skipped: {skipped}")
    print(f"  ❌ Errors: {len(errors)}")
    
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e}")
    
    if dry_run:
        print("\n👆 This was a DRY RUN. To actually upload, run:")
        print("   upload_manuals(dry_run=False)")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Check for --execute flag
    if "--execute" in sys.argv:
        print("🚀 EXECUTING UPLOAD (not a dry run)\n")
        upload_manuals(dry_run=False)
    else:
        print("🔍 DRY RUN MODE (use --execute to actually upload)\n")
        upload_manuals(dry_run=True)