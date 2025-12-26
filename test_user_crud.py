"""
Test script for Phase 2 - User CRUD endpoints

Tests:
1. Update user (display_name)
2. Deactivate user
3. Reactivate user
"""

import asyncio
import sys
from auth.auth_service import get_auth_service

def test_user_crud():
    """Test user CRUD operations"""
    auth = get_auth_service()

    print("=" * 70)
    print("Testing Phase 2 - User CRUD Endpoints")
    print("=" * 70)

    # Get super user for testing
    test_email = "mhartigan@driscollfoods.com"
    print(f"\n1. Looking up super user: {test_email}")
    super_user = auth.get_user_by_email(test_email)

    if not super_user:
        print(f"   ERROR: User not found: {test_email}")
        return False

    if not super_user.is_super_user:
        print(f"   ERROR: User is not a super user")
        return False

    print(f"   ✓ Found super user: {super_user.display_name or super_user.email}")

    # Get or create a test user for testing
    test_target_email = "test.user@driscollfoods.com"
    print(f"\n2. Getting or creating test user: {test_target_email}")

    # First, try to get existing user (active users only)
    existing_user = auth.get_user_by_email(test_target_email)

    if existing_user:
        # User exists and is active
        test_user = existing_user
        print(f"   ✓ Using existing test user: {test_user.email}")
    else:
        # Check if user exists but is inactive using psycopg2
        import psycopg2
        from psycopg2.extras import RealDictCursor

        DB_CONFIG = {
            "user": "mhartigan",
            "password": "Lalamoney3!",
            "host": "cogtwin.postgres.database.azure.com",
            "port": 5432,
            "database": "postgres",
            "sslmode": "require"
        }

        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                "SELECT email, is_active FROM enterprise.users WHERE LOWER(email) = %s",
                (test_target_email.lower(),)
            )
            inactive_check = cur.fetchone()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"   WARNING: Could not check for inactive user: {e}")
            inactive_check = None

        if inactive_check:
            # User exists but is inactive, reactivate
            print(f"   Found inactive user, reactivating...")
            auth.reactivate_user(super_user, test_target_email)
            test_user = auth.get_user_by_email(test_target_email)
            print(f"   ✓ Reactivated test user: {test_user.email}")
        else:
            # Create new user
            test_user = auth.get_or_create_user(
                email=test_target_email,
                display_name="Test User"
            )
            print(f"   ✓ Created test user: {test_user.email}")

    if not test_user:
        print(f"   ERROR: Could not get or create test user")
        return False

    # Test 1: Update user
    print(f"\n3. Testing update_user method")
    try:
        success = auth.update_user(
            updater=super_user,
            target_email=test_target_email,
            display_name="Updated Test User"
        )

        if not success:
            print(f"   ERROR: update_user returned False")
            return False

        # Verify update
        updated_user = auth.get_user_by_email(test_target_email)
        if updated_user.display_name != "Updated Test User":
            print(f"   ERROR: Display name not updated. Got: {updated_user.display_name}")
            return False

        print(f"   ✓ update_user works correctly")
        print(f"     New display_name: {updated_user.display_name}")

    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    # Test 2: Deactivate user
    print(f"\n4. Testing deactivate_user method")
    try:
        success = auth.deactivate_user(
            deactivator=super_user,
            target_email=test_target_email
        )

        if not success:
            print(f"   ERROR: deactivate_user returned False")
            return False

        # Verify deactivation (user should not be found by get_user_by_email)
        deactivated_user = auth.get_user_by_email(test_target_email)
        if deactivated_user:
            print(f"   ERROR: User still active after deactivation")
            return False

        print(f"   ✓ deactivate_user works correctly")
        print(f"     User is now inactive")

    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    # Test 3: Reactivate user
    print(f"\n5. Testing reactivate_user method")
    try:
        success = auth.reactivate_user(
            reactivator=super_user,
            target_email=test_target_email
        )

        if not success:
            print(f"   ERROR: reactivate_user returned False")
            return False

        # Verify reactivation
        reactivated_user = auth.get_user_by_email(test_target_email)
        if not reactivated_user:
            print(f"   ERROR: User not found after reactivation")
            return False

        if not reactivated_user.is_active:
            print(f"   ERROR: User is_active still False")
            return False

        print(f"   ✓ reactivate_user works correctly")
        print(f"     User is now active again")

    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    # Cleanup: Deactivate test user
    print(f"\n6. Cleanup: Deactivating test user")
    try:
        auth.deactivate_user(super_user, test_target_email)
        print(f"   ✓ Test user deactivated")
    except Exception as e:
        print(f"   WARNING: Could not cleanup test user: {e}")

    print("\n" + "=" * 70)
    print("✓ All Phase 2 tests passed!")
    print("=" * 70)

    return True

if __name__ == "__main__":
    try:
        success = test_user_crud()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
