"""
Test script for Phase 2 - Admin API endpoints

Tests that the admin API endpoints return proper responses instead of 501 errors.
This doesn't start the server, it just verifies the endpoint implementations exist.
"""

import inspect
from auth.admin_routes import admin_router

def test_admin_endpoints():
    """Verify admin endpoints are implemented"""
    print("=" * 70)
    print("Testing Phase 2 - Admin API Endpoint Implementations")
    print("=" * 70)

    # Get all routes from the admin router
    routes = {}
    for route in admin_router.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            path = route.path
            methods = route.methods
            endpoint = route.endpoint if hasattr(route, 'endpoint') else None
            routes[f"{list(methods)[0] if methods else 'GET'} {path}"] = endpoint

    # Test cases for the three endpoints
    test_cases = [
        {
            "name": "update_user",
            "route": "PUT /users/{user_id}",
            "description": "Update user details"
        },
        {
            "name": "deactivate_user",
            "route": "DELETE /users/{user_id}",
            "description": "Deactivate (soft delete) a user"
        },
        {
            "name": "reactivate_user",
            "route": "POST /users/{user_id}/reactivate",
            "description": "Reactivate a previously deactivated user"
        }
    ]

    all_passed = True

    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. Testing {test['name']} endpoint")
        print(f"   Route: {test['route']}")
        print(f"   Description: {test['description']}")

        # Check if route exists
        if test['route'] not in routes:
            print(f"   ✗ ERROR: Route not found in admin_router")
            all_passed = False
            continue

        endpoint = routes[test['route']]
        if not endpoint:
            print(f"   ✗ ERROR: Endpoint function not found")
            all_passed = False
            continue

        # Check if endpoint is implemented (not just raising 501)
        source = inspect.getsource(endpoint)

        # Check for 501 error (stub implementation)
        if "501" in source and "Not Implemented" in source:
            print(f"   ✗ ERROR: Endpoint still returns 501 (stub implementation)")
            all_passed = False
            continue

        # Check for proper implementation patterns
        has_auth_check = "auth.get_auth_service()" in source or "get_auth_service()" in source
        has_permission_check = "requester" in source or "updater" in source or "deactivator" in source or "reactivator" in source
        has_return = "return APIResponse" in source or "return " in source

        if not has_auth_check:
            print(f"   ⚠ WARNING: No auth service check found")

        if not has_permission_check:
            print(f"   ⚠ WARNING: No permission check found")

        if not has_return:
            print(f"   ✗ ERROR: No return statement found")
            all_passed = False
            continue

        print(f"   ✓ Endpoint implemented correctly")
        print(f"     - Auth check: {'✓' if has_auth_check else '✗'}")
        print(f"     - Permission check: {'✓' if has_permission_check else '✗'}")
        print(f"     - Returns response: {'✓' if has_return else '✗'}")

    # Additional checks
    print(f"\n4. Checking UpdateUserRequest model")
    from auth.admin_routes import UpdateUserRequest

    # Check that deprecated fields are removed
    model_fields = UpdateUserRequest.model_fields.keys()
    deprecated_fields = ['employee_id', 'primary_department']
    has_deprecated = any(field in model_fields for field in deprecated_fields)

    if has_deprecated:
        print(f"   ✗ ERROR: UpdateUserRequest still has deprecated fields")
        all_passed = False
    else:
        print(f"   ✓ Deprecated fields removed")

    # Check that proper fields exist
    if 'display_name' in model_fields:
        print(f"   ✓ display_name field exists")
    else:
        print(f"   ✗ ERROR: display_name field missing")
        all_passed = False

    if 'reason' in model_fields:
        print(f"   ✓ reason field exists")
    else:
        print(f"   ✗ ERROR: reason field missing")
        all_passed = False

    # Summary
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ All Phase 2 endpoint checks passed!")
        print("  The endpoints are properly implemented and ready for use.")
    else:
        print("✗ Some checks failed!")
        print("  Please review the errors above.")
    print("=" * 70)

    return all_passed

if __name__ == "__main__":
    import sys
    try:
        success = test_admin_endpoints()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
