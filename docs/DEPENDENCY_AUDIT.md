# DEPENDENCY AUDIT - Phase 1: Auth Service Refactor

**Generated:** 2025-12-21
**Purpose:** Complete dependency map for refactoring auth_service.py into enterprise.auth_users

---

## Executive Summary

This audit documents every file that depends on `auth/auth_service.py` and exactly how they use it. The goal is to ensure zero breakage during the refactor.

**Files analyzed:**
1. core/main.py (PRIMARY - WebSocket handler, auth deps)
2. auth/sso_routes.py (Azure SSO callback handler)
3. auth/admin_routes.py (Admin portal endpoints)
4. core/protocols.py (Public API surface)
5. auth/tenant_service.py (INDEPENDENT - no auth_service imports)
6. auth/azure_auth.py (INDEPENDENT - no auth_service imports)

**Critical finding:** `tenant_service.py` and `azure_auth.py` do NOT import from auth_service. They are independent.

---

## File: core/main.py

**Location:** `C:\Users\mthar\projects\enterprise_bot\core\main.py`

### Imports
```python
from auth.auth_service import get_auth_service, authenticate_user
```

### AuthService Method Calls

| Line | Method | Returns | Usage |
|------|--------|---------|-------|
| 193 | `get_auth_service()` | `AuthService` | Get singleton |
| 194 | `auth.get_user_by_azure_oid(graph_user.get("id"))` | `Optional[User]` | Look up user by Azure OID after SSO |
| 197 | `auth.get_user_department_access(user)` | `List[str]` | Get dept slugs for user |
| 222 | `get_auth_service()` | `AuthService` | Get singleton |
| 223 | `auth.get_or_create_user(x_user_email)` | `Optional[User]` | Legacy email header auth |
| 229 | `auth.get_user_department_access(user)` | `List[str]` | Get dept slugs for user |
| 559 | `get_auth_service()` | `AuthService` | Get singleton |
| 562 | `auth.get_user_by_email(user["email"])` | `Optional[User]` | Get User object from email |
| 566 | `auth.list_all_users(actor)` | `List[Dict]` | Admin endpoint - list all users |
| 568 | `auth.list_users_in_department(actor, department)` | `List[Dict]` | Admin endpoint - list dept users |
| 570 | `auth.list_users_in_department(actor, user["primary_department"])` | `List[Dict]` | Admin endpoint - list dept users |
| 748 | `get_auth_service()` | `AuthService` | Get singleton (WebSocket verify) |
| 749 | `auth.get_or_create_user(email)` | `Optional[User]` | Create/get user during WS verify |
| 756 | `auth.get_user_department_access(user)` | `List[str]` | Get dept slugs for WS context |
| 773 | `auth.record_login(user)` | `None` | Track login event |

### User Object Access

| Line | Field/Method | Type | Usage |
|------|--------------|------|-------|
| 199 | `user.id` | `str` | User ID for response |
| 200 | `user.email` | `str` | User email for response |
| 201 | `user.display_name` | `str` | Display name for response |
| 202 | `user.role` | `str` | Role for response |
| 203 | `user.tier.name` | `str` | Permission tier name |
| 204 | `user.employee_id` | `str` | Employee ID for response |
| 205 | `user.primary_department_slug` | `Optional[str]` | Primary dept for response |
| 207 | `user.is_super_user` | `bool` | Super user check |
| 208 | `user.can_manage_users` | `bool` | Admin permission check |
| 232 | `user.id` | `str` | User ID for response |
| 233 | `user.email` | `str` | User email for response |
| 234 | `user.display_name` | `str` | Display name for response |
| 235 | `user.role` | `str` | Role for response |
| 236 | `user.tier.name` | `str` | Permission tier name |
| 237 | `user.employee_id` | `str` | Employee ID for response |
| 238 | `user.primary_department_slug` | `Optional[str]` | Primary dept for response |
| 240 | `user.is_super_user` | `bool` | Super user check |
| 241 | `user.can_manage_users` | `bool` | Admin permission check |
| 565 | `user["is_super_user"]` | `bool` | Check if super user (dict access) |
| 569 | `user["primary_department"]` | `str` | Primary dept slug (dict access) |
| 751 | `user` | `User` | User object for dept access check |
| 759 | `user.primary_department_slug` | `Optional[str]` | Fallback dept if no access |
| 760 | `user.is_super_user` | `bool` | Super user bypass check |
| 761 | `user.primary_department_slug` | `Optional[str]` | Fallback dept if no access |
| 766 | `user.role` | `str` | User role for tenant context |
| 784 | `user.id` | `str` | User ID for analytics |
| 793 | `user.role` | `str` | User role for WS response |

### Direct DB Table References
- None found (auth_service handles all DB access)

### Dependencies Imported
```python
authenticate_user  # Line 24 (unused - imported but never called)
get_auth_service   # Line 24 (used extensively)
```

---

## File: auth/sso_routes.py

**Location:** `C:\Users\mthar\projects\enterprise_bot\auth\sso_routes.py`

### Imports
```python
from .auth_service import get_auth_service
```

### AuthService Method Calls

| Line | Method | Returns | Usage |
|------|--------|---------|-------|
| 152 | `await provision_user(azure_user)` | `User` | Provision user from Azure callback |
| 197 | `get_auth_service()` | `AuthService` | Get singleton |
| 198 | `auth.get_user_by_azure_oid(azure_user.oid)` | `Optional[User]` | Look up user by Azure OID |
| 203 | `auth.get_user_department_access(user)` | `List[str]` | Get dept slugs for user |
| 257 | `get_auth_service()` | `AuthService` | Get singleton (provision_user) |
| 260 | `auth.get_user_by_azure_oid(azure_user.oid)` | `Optional[User]` | Try find by Azure OID |
| 264 | `auth.update_user_from_azure(...)` | `User` | Update existing user from Azure |
| 272 | `auth.get_user_by_email(azure_user.email)` | `Optional[User]` | Try find by email |
| 276 | `auth.link_user_to_azure(user.id, azure_user.oid)` | `User` | Link existing user to Azure |
| 279 | `auth.create_user_from_azure(...)` | `User` | Create new user from Azure |
| 286 | `auth.get_user_department_access(user)` | `List[str]` | Get dept slugs for user |

### User Object Access

| Line | Field/Method | Type | Usage |
|------|--------------|------|-------|
| 165 | `user.id` | `str` | User ID for token response |
| 166 | `user.email` | `str` | User email for token response |
| 167 | `user.display_name` | `str` | Display name for token response |
| 168 | `user.role` | `str` | User role for token response |
| 169 | `user.dept_slugs` | `List[str]` | Department slugs (set at line 287) |
| 170 | `user.is_super_user` | `bool` | Super user flag for response |
| 171 | `user.can_manage_users` | `bool` | Admin permission for response |
| 214 | `user.id` | `str` | User ID for token response |
| 215 | `user.email` | `str` | User email for token response |
| 216 | `user.display_name` | `str` | Display name for token response |
| 217 | `user.role` | `str` | User role for token response |
| 219 | `user.is_super_user` | `bool` | Super user flag for response |
| 220 | `user.can_manage_users` | `bool` | Admin permission for response |
| 265-269 | `user.id`, `user` | `str`, `User` | Update user params |
| 276 | `user.id` | `str` | User ID for linking |
| 287 | `user.dept_slugs` | (set) | Set dept_slugs on user object |

### Direct DB Table References
- None found (auth_service handles all DB access)

---

## File: auth/admin_routes.py

**Location:** `C:\Users\mthar\projects\enterprise_bot\auth\admin_routes.py`

### Imports
```python
from .auth_service import (
    get_auth_service,
    User,
    PermissionTier,
)
```

### AuthService Method Calls

| Line | Method | Returns | Usage |
|------|--------|---------|-------|
| 121 | `get_auth_service()` | `AuthService` | Get singleton (get_current_user helper) |
| 122 | `auth.get_user_by_email(x_user_email)` | `Optional[User]` | Look up user by email header |
| 166 | `get_auth_service()` | `AuthService` | Get singleton (list_users endpoint) |
| 171 | `auth.list_users_in_department(user, department)` | `List[Dict]` | Super user dept filter |
| 173 | `auth.list_all_users(user)` | `List[Dict]` | Super user list all |
| 176 | `auth.get_user_department_access(user)` | `List[str]` | Get dept slugs for dept head |
| 177 | `auth.is_dept_head_for(user, d)` | `bool` | Check if dept head for dept |
| 182 | `auth.list_users_in_department(user, department)` | `List[Dict]` | Dept head dept filter |
| 187 | `auth.list_users_in_department(user, dept_slug)` | `List[Dict]` | Dept head list their depts |
| 234 | `get_auth_service()` | `AuthService` | Get singleton (get_user_detail) |
| 237 | `auth.get_user_by_id(user_id)` | `Optional[User]` | Look up user by ID |
| 245 | `auth.get_accessible_department_slugs(actor)` | `List[str]` | Get actor's dept slugs |
| 246 | `auth.get_accessible_department_slugs(target)` | `List[str]` | Get target's dept slugs |
| 252 | `auth.get_user_department_access(target)` | `List[str]` | Get target's dept access |
| 311 | `get_auth_service()` | `AuthService` | Get singleton (change_user_role) |
| 314 | `auth.get_user_by_id(user_id)` | `Optional[User]` | Look up user by ID |
| 325 | `auth.change_user_role(...)` | `None` | Change user's global role |
| 369 | `get_auth_service()` | `AuthService` | Get singleton (list_department_users) |
| 372 | `auth.list_users_in_department(actor, slug)` | `List[Dict]` | List dept users |
| 408 | `get_auth_service()` | `AuthService` | Get singleton (grant_access) |
| 411 | `auth.get_user_by_id(request.user_id)` | `Optional[User]` | Look up target user |
| 416 | `auth.grant_department_access(...)` | `bool` | Grant dept access |
| 459 | `get_auth_service()` | `AuthService` | Get singleton (revoke_access) |
| 462 | `auth.get_user_by_id(request.user_id)` | `Optional[User]` | Look up target user |
| 467 | `auth.revoke_department_access(...)` | `bool` | Revoke dept access |
| 602 | `get_auth_service()` | `AuthService` | Get singleton (admin_stats) |
| 682 | `get_auth_service()` | `AuthService` | Get singleton (list_all_departments) |
| 698 | `auth.get_user_department_access(actor)` | `List[str]` | Get actor's dept slugs |
| 699 | `auth.is_dept_head_for(actor, d)` | `bool` | Check if dept head |
| 782 | `get_auth_service()` | `AuthService` | Get singleton (create_user) |
| 785 | `auth.create_user(...)` | `User` | Create user with full params |
| 835 | `get_auth_service()` | `AuthService` | Get singleton (batch_create_users) |
| 848 | `auth.batch_create_users(...)` | `Dict[str, Any]` | Batch create users |
| 891 | `get_auth_service()` | `AuthService` | Get singleton (update_user) |
| 894 | `auth.get_user_by_id(user_id)` | `Optional[User]` | Look up target user |
| 899 | `auth.update_user(...)` | `User` | Update user details |
| 947 | `get_auth_service()` | `AuthService` | Get singleton (deactivate_user) |
| 950 | `auth.get_user_by_id(user_id)` | `Optional[User]` | Look up target user |
| 956 | `auth.deactivate_user(...)` | `bool` | Deactivate user |
| 990 | `get_auth_service()` | `AuthService` | Get singleton (reactivate_user) |
| 993 | `auth.reactivate_user(...)` | `User` | Reactivate user |

### User Object Access

| Line | Field/Method | Type | Usage |
|------|--------------|------|-------|
| 124 | `user.active` | `bool` | Check if user active |
| 127 | `user` | `User` | Return user object |
| 135 | `user.tier.value` | `int` | Permission tier check |
| 142 | `user.is_super_user` | `bool` | Super user check |
| 169 | `user.is_super_user` | `bool` | Super user check |
| 240 | `target` | `User` | Target user object |
| 277-286 | `target.id`, `target.email`, etc. | Various | User detail response |
| 314-321 | `target.id`, `target.role` | `str` | Role change validation |
| 324 | `target.role` | `str` | Old role for audit |
| 800-806 | `user.id`, `user.email`, etc. | Various | Created user response |
| 913-918 | `updated.id`, `updated.email`, etc. | Various | Updated user response |
| 962 | `target.email` | `str` | Deactivate response |
| 998-1003 | `user.id`, `user.email`, etc. | Various | Reactivate response |

### Direct DB Table References

| Line | Table | Query Type | Purpose |
|------|-------|------------|---------|
| 259-264 | `enterprise.departments`, `enterprise.access_config` | JOIN SELECT | Get department grants for user detail |
| 525-583 | `enterprise.access_audit_log` | SELECT | Audit log viewing (super user only) |
| 607-647 | `enterprise.users`, `enterprise.departments`, `enterprise.access_config`, `enterprise.access_audit_log` | Multiple SELECTs | Admin dashboard stats |
| 688-695 | `enterprise.departments` | SELECT | List all departments (super user) |
| 704-710 | `enterprise.departments` | SELECT | List dept head's departments |

### PermissionTier Usage

| Line | Usage | Purpose |
|------|-------|---------|
| 26 | `PermissionTier` | Import enum |
| 135 | `PermissionTier.DEPT_HEAD.value` | Compare permission level |

---

## File: core/protocols.py

**Location:** `C:\Users\mthar\projects\enterprise_bot\core\protocols.py`

### Imports
```python
from auth.auth_service import (
    get_auth_service,
    authenticate_user,
    User,
)
```

### Usage
This is the PUBLIC API surface. These 3 exports from auth_service are part of the stable protocol:
- `get_auth_service()` - Singleton factory
- `authenticate_user(email)` - Convenience function (wraps get_or_create_user)
- `User` - User dataclass

### Impact
**CRITICAL:** Any changes to these 3 exports will break the public API. They must remain stable or be deprecated with migration path.

---

## File: auth/tenant_service.py

**Location:** `C:\Users\mthar\projects\enterprise_bot\auth\tenant_service.py`

### Imports from auth_service
**NONE** - This file is completely independent. It only references `PermissionTier` enum which it DEFINES ITSELF (not imported from auth_service).

### Notes
- Defines its own `PermissionTier` enum (lines 65-68)
- Uses own DB connection helpers
- No auth_service imports or calls

---

## File: auth/azure_auth.py

**Location:** `C:\Users\mthar\projects\enterprise_bot\auth\azure_auth.py`

### Imports from auth_service
**NONE** - This file is completely independent. It handles Azure OAuth2 flow only.

### Notes
- Uses MSAL for token exchange
- Returns `AzureUser` dataclass (different from auth_service.User)
- No auth_service imports or calls
- SSO routes bridge Azure auth to auth_service

---

## Complete Method Inventory: AuthService API Surface

### User Lookup Methods
1. `get_user_by_email(email: str) -> Optional[User]`
2. `get_user_by_id(user_id: str) -> Optional[User]`
3. `get_user_by_azure_oid(azure_oid: str) -> Optional[User]`
4. `get_or_create_user(email, display_name=None, tenant_slug="driscoll") -> Optional[User]`

### Department Access Methods
5. `get_user_department_access(user: User) -> List[str]`
6. `can_access_department(user: User, department_slug: str) -> bool`
7. `get_accessible_department_slugs(user: User) -> List[str]`
8. `is_dept_head_for(user: User, department_slug: str) -> bool`

### Admin Operations (Require DEPT_HEAD or SUPER_USER)
9. `grant_department_access(actor, target_user, department_slug, access_level="read", make_dept_head=False, reason=None) -> bool`
10. `revoke_department_access(actor, target_user, department_slug, reason=None) -> bool`
11. `change_user_role(actor, target_user, new_role, reason=None) -> bool`

### User CRUD (Require SUPER_USER)
12. `create_user(actor, email, display_name=None, employee_id=None, role="user", primary_department_slug=None, department_access=None, reason=None) -> User`
13. `update_user(actor, target_user, email=None, display_name=None, employee_id=None, primary_department_slug=None, reason=None) -> User`
14. `deactivate_user(actor, target_user, reason=None) -> bool`
15. `reactivate_user(actor, user_id, reason=None) -> User`
16. `batch_create_users(actor, user_data: List[Dict], default_department="warehouse", reason=None) -> Dict[str, Any]`

### Admin Queries (Permission-checked)
17. `list_users_in_department(actor, department_slug) -> List[Dict[str, Any]]`
18. `list_all_users(actor) -> List[Dict[str, Any]]`

### Azure AD Integration
19. `create_user_from_azure(email, display_name, azure_oid) -> User`
20. `link_user_to_azure(user_id, azure_oid) -> User`
21. `update_user_from_azure(user_id, email, display_name, azure_oid) -> User`

### Session/Login Tracking
22. `record_login(user: User, ip_address=None) -> None`

### Cache Management
23. `_clear_user_cache(email: str) -> None` (private)
24. `clear_cache() -> None`

---

## User Dataclass Fields

```python
@dataclass
class User:
    id: str                                    # UUID
    email: str                                 # Email address
    display_name: Optional[str]                # Display name
    employee_id: Optional[str]                 # Employee ID
    tenant_id: str                             # Tenant UUID
    role: str                                  # 'user', 'dept_head', 'super_user'
    primary_department_id: Optional[str]       # Primary dept UUID
    primary_department_slug: Optional[str]     # Primary dept slug
    is_active: bool                            # Active flag

    # Computed properties
    @property
    def active(self) -> bool                   # Alias for is_active

    @property
    def tier(self) -> PermissionTier           # Computed from role

    @property
    def is_super_user(self) -> bool            # role == "super_user"

    @property
    def can_manage_users(self) -> bool         # tier >= DEPT_HEAD
```

---

## Database Tables Referenced (Indirect via auth_service)

All DB access goes through auth_service methods. Direct SQL only in admin_routes.py:

1. `enterprise.users` - User records
2. `enterprise.departments` - Department metadata
3. `enterprise.access_config` - Department access grants
4. `enterprise.access_audit_log` - Audit trail
5. `enterprise.tenants` - Tenant metadata

---

## Critical Dependencies for Refactor

### Must Preserve Exactly
1. **Function signatures** - All 24 methods must maintain exact signatures
2. **Return types** - User dataclass, List[str], List[Dict], bool, None
3. **Exception types** - PermissionError, ValueError
4. **User dataclass structure** - All fields and properties
5. **Singleton pattern** - `get_auth_service()` returns singleton

### Can Change Internally
1. Database schema (as long as methods work)
2. Caching strategy
3. SQL queries (as long as results match)
4. Internal helper methods

### Public API (protocols.py)
These 3 exports are public and used by external code:
1. `get_auth_service()` - Factory function
2. `authenticate_user(email)` - Convenience wrapper
3. `User` - User dataclass

---

## Refactor Risk Assessment

### LOW RISK
- tenant_service.py - No dependency
- azure_auth.py - No dependency

### MEDIUM RISK
- sso_routes.py - 11 method calls, well-encapsulated in provision_user()
- protocols.py - Only 3 exports, stable API

### HIGH RISK
- admin_routes.py - 40+ method calls, extensive User object access, direct DB queries
- core/main.py - 13 method calls, WebSocket handler, multiple code paths

### CRITICAL
Any change to User dataclass structure will cascade to all files.

---

## Recommended Refactor Strategy

### Phase 1: Create New Schema
1. Create `enterprise.auth_users` table (extends enterprise.users)
2. Migrate data with zero-downtime strategy
3. Keep old tables for rollback

### Phase 2: Update auth_service.py
1. Point queries to new table
2. Maintain exact method signatures
3. Run integration tests

### Phase 3: Verify Dependents
1. Test all endpoints in main.py
2. Test SSO flow in sso_routes.py
3. Test admin portal in admin_routes.py

### Phase 4: Clean Up
1. Drop old tables after 30-day soak
2. Update documentation
3. Archive migration scripts

---

## Test Coverage Required

Before refactor:
1. Unit tests for all 24 AuthService methods
2. Integration tests for main.py endpoints
3. Integration tests for admin_routes.py endpoints
4. Integration tests for SSO flow
5. Load tests for WebSocket handler

After refactor:
1. Same tests must pass
2. Performance benchmarks (no regressions)
3. Security audit (permission checks still work)

---

**END OF DEPENDENCY AUDIT**
