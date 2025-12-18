"""Quick test to verify enterprise_bot setup."""
from pathlib import Path

print("=" * 60)
print("ENTERPRISE BOT SETUP VERIFICATION")
print("=" * 60)

# 1. Test config loader
print("\n1. CONFIG LOADER")
try:
    from config_loader import load_config, cfg, memory_enabled, is_enterprise_mode
    load_config()
    print(f"   Mode: {cfg('deployment.mode')}")
    print(f"   Tier: {cfg('deployment.tier')}")
    print(f"   Memory Enabled: {memory_enabled()}")
    print(f"   Enterprise Mode: {is_enterprise_mode()}")
    print(f"   Context Stuffing: DEPRECATED (RAG only)")
    print("   [OK] Config loads correctly")
except Exception as e:
    print(f"   [FAIL] {e}")

# 2. Test doc loader
print("\n2. DOC LOADER")
try:
    from doc_loader import DocLoader
    loader = DocLoader(Path("./manuals/Driscoll"))
    stats = loader.get_stats()
    print(f"   Total docs: {stats.total_docs}")
    print(f"   Total tokens: {stats.total_tokens:,}")
    print(f"   Divisions: {list(stats.by_division.keys())}")
    print("   [OK] Doc loader works")
except Exception as e:
    print(f"   [FAIL] {e}")

# 3. Test CogTwin import (replaced EnterpriseTwin)
print("\n3. COGTWIN")
try:
    from cog_twin import CogTwin
    print("   [OK] CogTwin imports")
except Exception as e:
    print(f"   [FAIL] {e}")

# 4. Check directory structure
print("\n4. DIRECTORY STRUCTURE")
required = [
    "config.yaml",
    "config_loader.py",
    "cog_twin.py",
    "doc_loader.py",
    "backend/app/main.py",
    "manuals/Driscoll/Warehouse",
    "data",
]
for path in required:
    p = Path(path)
    exists = p.exists()
    status = "[OK]" if exists else "[MISSING]"
    print(f"   {status} {path}")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
