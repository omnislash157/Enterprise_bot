#!/usr/bin/env python3
"""
health_check.py - Automated Invariant Validation

Run this FIRST every session. If it fails, fix before doing anything else.

Usage:
    python health_check.py
    
Exit codes:
    0 = All invariants pass
    1 = One or more invariants violated
"""

import sys
from pathlib import Path

# Find project root (where this script should live)
SCRIPT_DIR = Path(__file__).parent.resolve()
CORE_DIR = SCRIPT_DIR / "core"
AUTH_DIR = SCRIPT_DIR / "auth"


def check_invariants():
    """Check all invariants, return list of violations."""
    errors = []
    warnings = []
    
    # =========================================================================
    # INVARIANT 1: Single Config System
    # =========================================================================
    dead_config = CORE_DIR / "config.py"
    if dead_config.exists():
        errors.append(
            "INVARIANT 1 VIOLATED: core/config.py exists (dead code)\n"
            "  Action: Delete it. Only config_loader.py should exist."
        )
    
    active_config = CORE_DIR / "config_loader.py"
    if not active_config.exists():
        errors.append(
            "INVARIANT 1 VIOLATED: core/config_loader.py missing\n"
            "  Action: This is the active config system - it must exist."
        )
    
    # =========================================================================
    # INVARIANT 2: Single Twin Router
    # =========================================================================
    main_py = CORE_DIR / "main.py"
    if main_py.exists():
        content = main_py.read_text()
        
        if "def get_twin_for_auth" in content:
            errors.append(
                "INVARIANT 2 VIOLATED: get_twin_for_auth() exists in main.py\n"
                "  Action: Delete it. Only get_twin() should exist."
            )
        
        if "get_twin_for_auth(" in content and "def get_twin_for_auth" not in content:
            errors.append(
                "INVARIANT 2 VIOLATED: get_twin_for_auth() is being called in main.py\n"
                "  Action: Replace with get_twin() call."
            )
    
    # =========================================================================
    # INVARIANT 5: TenantContext Field Names
    # =========================================================================
    if main_py.exists():
        content = main_py.read_text()
        
        # Check for tenant.email (wrong) vs tenant.user_email (correct)
        if "tenant.email" in content:
            # Make sure it's not part of "tenant.user_email"
            import re
            bad_refs = re.findall(r'tenant\.email(?!_)', content)
            if bad_refs:
                errors.append(
                    f"INVARIANT 5 VIOLATED: tenant.email found in main.py ({len(bad_refs)} occurrences)\n"
                    "  Action: Change to tenant.user_email"
                )
    
    # =========================================================================
    # INVARIANT 7: No Test Domains in Production Config
    # =========================================================================
    config_yaml = CORE_DIR / "config.yaml"
    if config_yaml.exists():
        content = config_yaml.read_text()
        
        test_domains = ["gmail.com", "yahoo.com", "hotmail.com", "test.com"]
        found_test_domains = [d for d in test_domains if d in content]
        
        if found_test_domains:
            errors.append(
                f"INVARIANT 7 VIOLATED: Test domain(s) in config.yaml: {found_test_domains}\n"
                "  Action: Remove from allowed_domains. Use .env for local testing."
            )
    
    # =========================================================================
    # INVARIANT 8: Email Login Security
    # =========================================================================
    if main_py.exists():
        content = main_py.read_text()
        
        # Check for the old pattern that accepted with warning
        if 'warning": "Email not in whitelist' in content:
            errors.append(
                "INVARIANT 8 VIOLATED: Email login accepts non-whitelist with warning\n"
                "  Action: Should reject with error, not warn and proceed."
            )
    
    # =========================================================================
    # BONUS CHECKS (Warnings, not errors)
    # =========================================================================
    
    # Check protocols.py exists and has expected exports
    protocols = CORE_DIR / "protocols.py"
    if protocols.exists():
        content = protocols.read_text()
        if "__all__" in content:
            # Count exports
            import re
            all_match = re.search(r'__all__\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if all_match:
                exports = all_match.group(1).count('"')
                if exports < 30:
                    warnings.append(
                        f"protocols.py has {exports} exports (expected ~37)\n"
                        "  This might be okay, but verify protocol boundary is complete."
                    )
    
    # Check for enterprise.departments table references (should be static)
    tenant_service = AUTH_DIR / "tenant_service.py"
    if tenant_service.exists():
        content = tenant_service.read_text()
        if "enterprise.departments" in content.lower() or "from departments" in content.lower():
            # Check if it's actually querying the table vs just referencing static
            if "SELECT" in content and "departments" in content:
                warnings.append(
                    "tenant_service.py may still query enterprise.departments table\n"
                    "  Verify: Table was deleted in Migration 002. Use STATIC_DEPARTMENTS."
                )
    
    return errors, warnings


def main():
    print("=" * 60)
    print("HEALTH CHECK - Validating Invariants")
    print("=" * 60)
    print()
    
    errors, warnings = check_invariants()
    
    # Print warnings first (non-fatal)
    if warnings:
        print("WARNINGS (review but not blocking):")
        print("-" * 40)
        for w in warnings:
            print(f"  [WARN] {w}")
        print()
    
    # Print errors (fatal)
    if errors:
        print("ERRORS (must fix before proceeding):")
        print("-" * 40)
        for e in errors:
            print(f"  [FAIL] {e}")
            print()
        print("=" * 60)
        print(f"HEALTH CHECK FAILED: {len(errors)} invariant(s) violated")
        print("=" * 60)
        return 1
    
    print("All invariants pass!")
    print()
    print("=" * 60)
    print("HEALTH CHECK PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())