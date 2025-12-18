#!/usr/bin/env python3
"""
Generate Test User/Tenant SQL - Phase 5 Helper
===============================================

Quick helper to generate SQL for creating test users or tenants
before running the migration script.

Usage:
    # Generate personal user
    python generate_test_user.py --mode personal --email test@example.com

    # Generate enterprise tenant + user
    python generate_test_user.py --mode enterprise --tenant-name driscoll --email admin@driscoll.com
"""

import argparse
import uuid
from datetime import datetime


def generate_personal_user(email: str, name: str = None) -> tuple[str, str]:
    """Generate SQL for a personal user."""
    user_id = str(uuid.uuid4())
    display_name = name or email.split('@')[0].title()

    sql = f"""-- Personal User
INSERT INTO users (id, auth_provider, external_id, email, display_name)
VALUES (
    '{user_id}',
    'test',
    'test_{email.split('@')[0]}',
    '{email}',
    '{display_name}'
)
ON CONFLICT (auth_provider, external_id) DO NOTHING;
"""

    return user_id, sql


def generate_enterprise_tenant(tenant_name: str, admin_email: str, admin_name: str = None) -> tuple[str, str, str]:
    """Generate SQL for an enterprise tenant and admin user."""
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    display_name = admin_name or f"{tenant_name.title()} Admin"

    sql = f"""-- Enterprise Tenant
INSERT INTO tenants (id, name, voice_engine, extraction_enabled)
VALUES (
    '{tenant_id}',
    '{tenant_name}',
    'enterprise',
    false
)
ON CONFLICT (name) DO NOTHING;

-- Enterprise Admin User
INSERT INTO users (id, auth_provider, external_id, email, display_name, tenant_id)
VALUES (
    '{user_id}',
    'azure_ad',
    'admin_{tenant_name}',
    '{admin_email}',
    '{display_name}',
    '{tenant_id}'
)
ON CONFLICT (auth_provider, external_id) DO NOTHING;
"""

    return tenant_id, user_id, sql


def main():
    parser = argparse.ArgumentParser(
        description="Generate SQL for test users or tenants",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Personal user
  python generate_test_user.py --mode personal --email test@example.com

  # Enterprise tenant
  python generate_test_user.py --mode enterprise --tenant-name driscoll --email admin@driscoll.com
"""
    )

    parser.add_argument(
        '--mode',
        type=str,
        required=True,
        choices=['personal', 'enterprise'],
        help='User mode (personal or enterprise)'
    )

    parser.add_argument(
        '--email',
        type=str,
        required=True,
        help='User email address'
    )

    parser.add_argument(
        '--name',
        type=str,
        help='Display name (optional, derived from email if not provided)'
    )

    parser.add_argument(
        '--tenant-name',
        type=str,
        help='Tenant name (required for enterprise mode)'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Output file (optional, prints to stdout if not provided)'
    )

    args = parser.parse_args()

    # Validate
    if args.mode == 'enterprise' and not args.tenant_name:
        parser.error("--tenant-name is required for enterprise mode")

    # Generate SQL
    print("=" * 70)
    print("Test User/Tenant Generator - Phase 5")
    print("=" * 70)
    print()

    if args.mode == 'personal':
        user_id, sql = generate_personal_user(args.email, args.name)

        print("PERSONAL USER GENERATED")
        print("-" * 70)
        print(sql)
        print("-" * 70)
        print()
        print("MIGRATION COMMAND:")
        print(f"  python migrate_to_postgres.py --user-id {user_id}")
        print()

    else:  # enterprise
        tenant_id, user_id, sql = generate_enterprise_tenant(
            args.tenant_name,
            args.email,
            args.name
        )

        print("ENTERPRISE TENANT + USER GENERATED")
        print("-" * 70)
        print(sql)
        print("-" * 70)
        print()
        print("MIGRATION COMMAND:")
        print(f"  python migrate_to_postgres.py --tenant-id {tenant_id}")
        print()

    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            f.write(sql)
        print(f"SQL saved to: {args.output}")
        print()

    print("NEXT STEPS:")
    print("1. Run the SQL above in your PostgreSQL database:")
    print("   psql $DATABASE_URL -c '<paste SQL>'")
    print()
    print("2. Run the migration script with the command shown above")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
