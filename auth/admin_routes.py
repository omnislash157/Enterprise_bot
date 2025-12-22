"""
Admin Routes - FastAPI Router for Admin Portal

Handles:
- User management (list, view, role changes)
- Department access grants/revokes
- Audit log viewing

All endpoints require at least DEPT_HEAD tier.
Super user-only endpoints are clearly marked.

Wire into main.py:
    from admin_routes import admin_router
    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
"""

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging

from .auth_service import (
    get_auth_service,
    User,
)

logger = logging.getLogger(__name__)

admin_router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class UserSummary(BaseModel):
    """Summary user info for list views."""
    id: str
    email: str
    display_name: Optional[str] = None
    employee_id: Optional[str] = None
    role: str
    primary_department: Optional[str] = None
    active: bool = True
    last_login_at: Optional[datetime] = None


class UserDetail(BaseModel):
    """Detailed user info including department access."""
    id: str
    email: str
    display_name: Optional[str] = None
    employee_id: Optional[str] = None
    role: str
    tier: str
    primary_department: Optional[str] = None
    active: bool = True
    last_login_at: Optional[datetime] = None
    departments: List[dict] = []


class GrantAccessRequest(BaseModel):
    """Request to grant department access."""
    user_id: str
    department_slug: str
    access_level: str = "read"  # 'read', 'write', 'admin'
    make_dept_head: bool = False
    reason: Optional[str] = None


class RevokeAccessRequest(BaseModel):
    """Request to revoke department access."""
    user_id: str
    department_slug: str
    reason: Optional[str] = None


class ChangeRoleRequest(BaseModel):
    """Request to change user role (super_user only)."""
    new_role: str = Field(..., pattern="^(user|dept_head|super_user)$")
    reason: Optional[str] = None


class AuditLogEntry(BaseModel):
    """Single audit log entry."""
    id: str
    action: str
    actor_email: Optional[str] = None
    target_email: Optional[str] = None
    department_slug: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime
    ip_address: Optional[str] = None


class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


# =============================================================================
# AUTH HELPERS
# =============================================================================

def get_current_user(x_user_email: str = Header(None, alias="X-User-Email")) -> User:
    """
    Get authenticated user from header.
    
    In production, this should validate a JWT or session token.
    For now, we use X-User-Email header (trusted proxy mode).
    """
    if not x_user_email:
        raise HTTPException(401, "Authentication required")
    
    auth = get_auth_service()
    user = auth.get_user_by_email(x_user_email)
    
    if not user:
        raise HTTPException(401, "User not found")
    
    if not user.active:
        raise HTTPException(403, "User account is disabled")
    
    return user


def require_admin(user: User) -> User:
    """Require at least dept_head or super_user."""
    if not user.is_super_user and not user.dept_head_for:
        raise HTTPException(403, "Admin access required")
    return user


def require_super_user(user: User) -> User:
    """Require SUPER_USER tier."""
    if not user.is_super_user:
        raise HTTPException(403, "Super user access required")
    return user


# =============================================================================
# USER MANAGEMENT ENDPOINTS
# =============================================================================

@admin_router.get("/users", response_model=APIResponse)
async def list_users(
    x_user_email: str = Header(None, alias="X-User-Email"),
    department: Optional[str] = Query(None, description="Filter by department slug"),
    search: Optional[str] = Query(None, description="Search by email or name"),
):
    """
    List users visible to the current admin.

    TODO: Rewrite for 2-table schema (no more access_config table).
    This endpoint relied on list_users_in_department() and list_all_users()
    which were removed during schema migration.

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "Admin portal pending redesign for 2-table schema. "
        "Use grant/revoke endpoints for now. "
        "See MIGRATION_001_COMPLETE.md for details."
    )


@admin_router.get("/users/{user_id}", response_model=APIResponse)
async def get_user_detail(
    user_id: str,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Get detailed info for a specific user.

    TODO: Rewrite for 2-table schema (no more access_config, departments tables).
    This endpoint relied on SQL joins to deleted tables.

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "Admin portal pending redesign for 2-table schema. "
        "Use grant/revoke endpoints for now. "
        "See MIGRATION_001_COMPLETE.md for details."
    )


@admin_router.put("/users/{user_id}/role", response_model=APIResponse)
async def change_user_role(
    user_id: str,
    request: ChangeRoleRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Change a user's global role - DEPRECATED.

    TODO: The 2-table schema has no roles. Permissions are:
    - is_super_user (boolean flag)
    - dept_head_for (array of departments)

    STUB: Returns 501 Not Implemented. Use grant_department_access with
    make_dept_head=True instead.
    """
    raise HTTPException(
        501,
        "Role changes deprecated in 2-table schema. "
        "Use grant_department_access(make_dept_head=True) to grant admin rights. "
        "See MIGRATION_001_COMPLETE.md for details."
    )


# =============================================================================
# DEPARTMENT USER ENDPOINTS
# =============================================================================

@admin_router.get("/departments/{slug}/users", response_model=APIResponse)
async def list_department_users(
    slug: str,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    List all users with access to a specific department.

    TODO: Rewrite for 2-table schema. Need to query users table and filter
    by department_access array contains slug.

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "Admin portal pending redesign for 2-table schema. "
        "See MIGRATION_001_COMPLETE.md for details."
    )


# =============================================================================
# ACCESS CONTROL ENDPOINTS
# =============================================================================

@admin_router.post("/access/grant", response_model=APIResponse)
async def grant_access(
    request: GrantAccessRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Grant department access to a user.

    TODO: This endpoint needs get_user_by_id() which doesn't exist in new schema.
    The new grant_department_access() signature is also different.

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "Admin portal pending redesign for 2-table schema. "
        "Use direct SQL or auth_service updates. "
        "See MIGRATION_001_COMPLETE.md for details."
    )


@admin_router.post("/access/revoke", response_model=APIResponse)
async def revoke_access(
    request: RevokeAccessRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Revoke department access from a user.

    TODO: This endpoint needs get_user_by_id() which doesn't exist in new schema.
    The new revoke_department_access() signature is also different.

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "Admin portal pending redesign for 2-table schema. "
        "Use direct SQL or auth_service updates. "
        "See MIGRATION_001_COMPLETE.md for details."
    )


# =============================================================================
# AUDIT LOG ENDPOINTS
# =============================================================================

@admin_router.get("/audit", response_model=APIResponse)
async def get_audit_log(
    x_user_email: str = Header(None, alias="X-User-Email"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    target_email: Optional[str] = Query(None, description="Filter by target user email"),
    department: Optional[str] = Query(None, description="Filter by department slug"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    View audit log entries.

    TODO: The access_audit_log table was deleted during schema migration.
    Need to decide if we still need audit logging and recreate if needed.

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "Audit log table deleted during schema migration. "
        "See MIGRATION_001_COMPLETE.md for details."
    )


# =============================================================================
# STATS ENDPOINT
# =============================================================================

@admin_router.get("/stats", response_model=APIResponse)
async def get_admin_stats(
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Get admin dashboard statistics.

    TODO: This endpoint queries deleted tables (departments, access_config, access_audit_log).
    Need to rewrite for 2-table schema (just enterprise.users table).

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "Admin stats pending redesign for 2-table schema. "
        "See MIGRATION_001_COMPLETE.md for details."
    )


# =============================================================================
# DEPARTMENTS LIST (for dropdowns)
# =============================================================================

@admin_router.get("/departments", response_model=APIResponse)
async def list_all_departments(
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    List all departments.

    TODO: The departments table was deleted during schema migration.
    Department slugs are now just strings in user.department_access arrays.
    Need to use tenant_service or hardcode department list.

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "Departments table deleted during schema migration. "
        "Use tenant_service.list_departments() instead. "
        "See MIGRATION_001_COMPLETE.md for details."
    )


# =============================================================================
# USER CRUD ENDPOINTS
# =============================================================================

class CreateUserRequest(BaseModel):
    """Request to create a single user."""
    email: str
    display_name: Optional[str] = None
    employee_id: Optional[str] = None
    role: str = "user"
    primary_department: Optional[str] = None
    department_access: Optional[List[str]] = None
    reason: Optional[str] = None


class UpdateUserRequest(BaseModel):
    """Request to update user details."""
    email: Optional[str] = None
    display_name: Optional[str] = None
    employee_id: Optional[str] = None
    primary_department: Optional[str] = None
    reason: Optional[str] = None


class BatchUserEntry(BaseModel):
    """Single entry in batch user creation."""
    email: str
    display_name: Optional[str] = None
    department: Optional[str] = None


class BatchCreateRequest(BaseModel):
    """Request for batch user creation."""
    users: List[BatchUserEntry]
    default_department: str = "warehouse"
    reason: Optional[str] = None


class DeactivateRequest(BaseModel):
    """Request to deactivate a user."""
    reason: Optional[str] = None


@admin_router.post("/users", response_model=APIResponse)
async def create_user(
    request: CreateUserRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Create a single user.

    TODO: The auth.create_user() method signature changed.
    No more employee_id, role, primary_department_slug fields.
    Use auth.get_or_create_user() then grant_department_access().

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "User creation pending redesign for 2-table schema. "
        "Use get_or_create_user() + grant_department_access(). "
        "See MIGRATION_001_COMPLETE.md for details."
    )


@admin_router.post("/users/batch", response_model=APIResponse)
async def batch_create_users(
    request: BatchCreateRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Batch create multiple users.

    TODO: The auth.batch_create_users() method doesn't exist anymore.
    Need to loop and call get_or_create_user() + grant_department_access().

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "Batch user creation pending redesign for 2-table schema. "
        "See MIGRATION_001_COMPLETE.md for details."
    )


@admin_router.put("/users/{user_id}", response_model=APIResponse)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Update user details.

    TODO: The auth.update_user() method signature changed.
    No more employee_id, primary_department_slug fields.
    Also get_user_by_id() doesn't exist.

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "User update pending redesign for 2-table schema. "
        "See MIGRATION_001_COMPLETE.md for details."
    )


@admin_router.delete("/users/{user_id}", response_model=APIResponse)
async def deactivate_user(
    user_id: str,
    request: DeactivateRequest = None,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Deactivate (soft delete) a user.

    TODO: The auth.deactivate_user() method signature changed.
    Also get_user_by_id() doesn't exist.

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "User deactivation pending redesign for 2-table schema. "
        "See MIGRATION_001_COMPLETE.md for details."
    )


@admin_router.post("/users/{user_id}/reactivate", response_model=APIResponse)
async def reactivate_user(
    user_id: str,
    x_user_email: str = Header(None, alias="X-User-Email"),
    reason: Optional[str] = None,
):
    """
    Reactivate a previously deactivated user.

    TODO: The auth.reactivate_user() method signature changed.

    STUB: Returns 501 Not Implemented until admin portal is redesigned.
    """
    raise HTTPException(
        501,
        "User reactivation pending redesign for 2-table schema. "
        "See MIGRATION_001_COMPLETE.md for details."
    )
