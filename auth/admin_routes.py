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
from .tenant_service import STATIC_DEPARTMENTS
from .audit_service import get_audit_service

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

    - Super users see all users
    - Dept heads see users in departments they head (or all if department filter not specified)
    - Regular users get 403
    """
    if not x_user_email:
        raise HTTPException(401, "X-User-Email header required")

    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)

    if not requester:
        raise HTTPException(401, "User not found")

    try:
        if department:
            # Filter by specific department
            users = auth.list_users_by_department(requester, department)
        else:
            # List all users (dept_heads+ only)
            users = auth.list_all_users(requester)

        # Optional search filter (client-side would be better, but this works)
        if search:
            search_lower = search.lower()
            users = [
                u for u in users
                if search_lower in u.email.lower()
                or (u.display_name and search_lower in u.display_name.lower())
            ]

        # Convert to response format
        user_list = [
            {
                "id": u.id,
                "email": u.email,
                "display_name": u.display_name,
                "departments": u.department_access,  # Standardized naming for frontend
                "dept_head_for": u.dept_head_for,
                "is_super_user": u.is_super_user,
                "is_active": u.is_active,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            }
            for u in users
        ]

        return APIResponse(
            success=True,
            data={"users": user_list, "count": len(user_list)},
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))


@admin_router.get("/users/{user_id}", response_model=APIResponse)
async def get_user_detail(
    user_id: str,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Get detailed info for a specific user.

    Dept heads can view users in departments they head.
    Super users can view any user.
    """
    if not x_user_email:
        raise HTTPException(401, "X-User-Email header required")

    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)

    if not requester:
        raise HTTPException(401, "User not found")

    # Check if requester has admin access
    if not requester.is_super_user and not requester.dept_head_for:
        raise HTTPException(403, "Admin access required")

    # Get target user by ID
    target = auth.get_user_by_id(user_id)
    if not target:
        raise HTTPException(404, f"User not found: {user_id}")

    # For dept_heads (non-super), check if they can see this user
    if not requester.is_super_user:
        # Dept head can only see users in departments they head
        visible_depts = set(requester.dept_head_for or [])
        target_depts = set(target.department_access or [])
        if not visible_depts.intersection(target_depts):
            raise HTTPException(403, "Cannot view this user")

    return APIResponse(
        success=True,
        data={
            "user": {
                "id": target.id,
                "email": target.email,
                "display_name": target.display_name,
                "departments": target.department_access,  # Standardized naming for frontend
                "dept_head_for": target.dept_head_for,
                "is_super_user": target.is_super_user,
                "is_active": target.is_active,
                "created_at": target.created_at.isoformat() if target.created_at else None,
                "last_login_at": target.last_login_at.isoformat() if target.last_login_at else None,
            }
        },
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

    - Super users can view any department
    - Dept heads can view departments they head
    """
    if not x_user_email:
        raise HTTPException(401, "X-User-Email header required")

    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)

    if not requester:
        raise HTTPException(401, "User not found")

    try:
        users = auth.list_users_by_department(requester, slug)

        user_list = [
            {
                "id": u.id,
                "email": u.email,
                "display_name": u.display_name,
                "departments": u.department_access,  # Standardized naming for frontend
                "dept_head_for": u.dept_head_for,
                "is_super_user": u.is_super_user,
                "is_active": u.is_active,
            }
            for u in users
        ]

        return APIResponse(
            success=True,
            data={"department": slug, "users": user_list, "count": len(user_list)},
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))


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

    - Super users can grant any department
    - Dept heads can grant departments they head (dept_head_for)
    - If make_dept_head=True, promotes user to dept head (super_user only)
    """
    if not x_user_email:
        raise HTTPException(401, "X-User-Email header required")

    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)

    if not requester:
        raise HTTPException(401, "User not found")

    # Get target user - support both user_id (UUID) and email
    target_email = request.user_id  # Might be email or UUID
    if "@" not in target_email:
        # It's a UUID, need to look up user
        target = auth.get_user_by_id(request.user_id)
        if not target:
            raise HTTPException(404, f"User not found: {request.user_id}")
        target_email = target.email

    try:
        # If make_dept_head, requires super_user
        if request.make_dept_head:
            if not requester.is_super_user:
                raise HTTPException(403, "Only super users can promote department heads")
            auth.promote_to_dept_head(requester, target_email, request.department_slug)
            action = "promoted to dept_head"
        else:
            # Regular access grant
            auth.grant_department_access(requester, target_email, request.department_slug)
            action = "granted access"

        logger.info(f"[Admin] {requester.email} {action} for {target_email} to {request.department_slug}")

        # Audit log
        audit = get_audit_service()
        audit.log_event(
            action="department_access_grant" if action == "granted access" else "dept_head_promote",
            actor_email=requester.email,
            target_email=target_email,
            department_slug=request.department_slug,
            reason=request.reason
        )

        return APIResponse(
            success=True,
            message=f"Successfully {action} to {request.department_slug} for {target_email}",
            data={
                "target_email": target_email,
                "department": request.department_slug,
                "action": action,
            },
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))


@admin_router.post("/access/revoke", response_model=APIResponse)
async def revoke_access(
    request: RevokeAccessRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Revoke department access from a user.

    - Super users can revoke any department
    - Dept heads can revoke departments they head (dept_head_for)
    """
    if not x_user_email:
        raise HTTPException(401, "X-User-Email header required")

    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)

    if not requester:
        raise HTTPException(401, "User not found")

    # Get target user - support both user_id (UUID) and email
    target_email = request.user_id  # Might be email or UUID
    if "@" not in target_email:
        target = auth.get_user_by_id(request.user_id)
        if not target:
            raise HTTPException(404, f"User not found: {request.user_id}")
        target_email = target.email

    try:
        auth.revoke_department_access(requester, target_email, request.department_slug)

        logger.info(f"[Admin] {requester.email} revoked {request.department_slug} access from {target_email}")

        # Audit log
        audit = get_audit_service()
        audit.log_event(
            action="department_access_revoke",
            actor_email=requester.email,
            target_email=target_email,
            department_slug=request.department_slug,
            reason=request.reason
        )

        return APIResponse(
            success=True,
            message=f"Successfully revoked {request.department_slug} access from {target_email}",
            data={
                "target_email": target_email,
                "department": request.department_slug,
                "action": "revoked",
            },
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))


# =============================================================================
# DEPT HEAD MANAGEMENT (SUPER_USER ONLY)
# =============================================================================

class PromoteDeptHeadRequest(BaseModel):
    """Request to promote user to department head."""
    target_email: str
    department: str


class RevokeDeptHeadRequest(BaseModel):
    """Request to revoke department head status."""
    target_email: str
    department: str


@admin_router.post("/dept-head/promote", response_model=APIResponse)
async def promote_to_dept_head(
    request: PromoteDeptHeadRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Promote a user to department head.

    SUPER USER ONLY.

    This gives the user the ability to grant/revoke access to the specified
    department for other users.
    """
    if not x_user_email:
        raise HTTPException(401, "X-User-Email header required")

    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)

    if not requester:
        raise HTTPException(401, "User not found")

    if not requester.is_super_user:
        raise HTTPException(403, "Only super users can promote department heads")

    try:
        auth.promote_to_dept_head(requester, request.target_email, request.department)

        logger.info(f"[Admin] {requester.email} promoted {request.target_email} to dept_head for {request.department}")

        # Audit log
        audit = get_audit_service()
        audit.log_event(
            action="dept_head_promote",
            actor_email=requester.email,
            target_email=request.target_email,
            department_slug=request.department,
            reason=request.reason if hasattr(request, 'reason') else None
        )

        return APIResponse(
            success=True,
            message=f"Successfully promoted {request.target_email} to department head for {request.department}",
            data={
                "target_email": request.target_email,
                "department": request.department,
            },
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))


@admin_router.post("/dept-head/revoke", response_model=APIResponse)
async def revoke_dept_head(
    request: RevokeDeptHeadRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Revoke department head status from a user.

    SUPER USER ONLY.

    Note: This does NOT remove their access to the department, just their
    ability to grant access to others.
    """
    if not x_user_email:
        raise HTTPException(401, "X-User-Email header required")

    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)

    if not requester:
        raise HTTPException(401, "User not found")

    if not requester.is_super_user:
        raise HTTPException(403, "Only super users can revoke department head status")

    try:
        auth.revoke_dept_head(requester, request.target_email, request.department)

        logger.info(f"[Admin] {requester.email} revoked dept_head from {request.target_email} for {request.department}")

        # Audit log
        audit = get_audit_service()
        audit.log_event(
            action="dept_head_revoke",
            actor_email=requester.email,
            target_email=request.target_email,
            department_slug=request.department,
            reason=None
        )

        return APIResponse(
            success=True,
            message=f"Successfully revoked department head status from {request.target_email} for {request.department}",
            data={
                "target_email": request.target_email,
                "department": request.department,
            },
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))


# =============================================================================
# SUPER USER MANAGEMENT (SUPER_USER ONLY)
# =============================================================================

class SuperUserRequest(BaseModel):
    """Request to promote/revoke super user status."""
    target_email: str


@admin_router.post("/super-user/promote", response_model=APIResponse)
async def make_super_user(
    request: SuperUserRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Promote a user to super user status.

    SUPER USER ONLY. Use carefully - super users have full access.
    """
    if not x_user_email:
        raise HTTPException(401, "X-User-Email header required")

    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)

    if not requester:
        raise HTTPException(401, "User not found")

    if not requester.is_super_user:
        raise HTTPException(403, "Only super users can promote other super users")

    try:
        auth.make_super_user(requester, request.target_email)

        logger.info(f"[Admin] {requester.email} promoted {request.target_email} to super_user")

        # Audit log
        audit = get_audit_service()
        audit.log_event(
            action="super_user_promote",
            actor_email=requester.email,
            target_email=request.target_email,
            reason=None
        )

        return APIResponse(
            success=True,
            message=f"Successfully promoted {request.target_email} to super user",
            data={"target_email": request.target_email},
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))


@admin_router.post("/super-user/revoke", response_model=APIResponse)
async def revoke_super_user(
    request: SuperUserRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Revoke super user status from a user.

    SUPER USER ONLY. Cannot revoke your own super_user status.
    """
    if not x_user_email:
        raise HTTPException(401, "X-User-Email header required")

    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)

    if not requester:
        raise HTTPException(401, "User not found")

    if not requester.is_super_user:
        raise HTTPException(403, "Only super users can revoke super user status")

    try:
        auth.revoke_super_user(requester, request.target_email)

        logger.info(f"[Admin] {requester.email} revoked super_user from {request.target_email}")

        # Audit log
        audit = get_audit_service()
        audit.log_event(
            action="super_user_revoke",
            actor_email=requester.email,
            target_email=request.target_email,
            reason=None
        )

        return APIResponse(
            success=True,
            message=f"Successfully revoked super user status from {request.target_email}",
            data={"target_email": request.target_email},
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))


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

    Permissions:
    - Super users: See all entries
    - Dept heads: See entries for their departments only
    """
    if not x_user_email:
        raise HTTPException(401, "X-User-Email header required")

    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)

    if not requester:
        raise HTTPException(401, "User not found")

    # Require admin access
    if not requester.is_super_user and not requester.dept_head_for:
        raise HTTPException(403, "Admin access required")

    # Non-super users can only see their departments
    if not requester.is_super_user and department:
        if department not in (requester.dept_head_for or []):
            raise HTTPException(403, f"No access to {department} audit log")

    # If non-super user with no department filter, limit to their departments
    effective_department = department
    if not requester.is_super_user and not department:
        # They can only see their own departments - take first one
        if requester.dept_head_for:
            effective_department = requester.dept_head_for[0]
        else:
            raise HTTPException(403, "No departments to view")

    audit = get_audit_service()
    entries = audit.query_log(
        action=action,
        target_email=target_email,
        department=effective_department,
        limit=limit,
        offset=offset
    )
    total = audit.count_log(
        action=action,
        target_email=target_email,
        department=effective_department
    )

    return APIResponse(
        success=True,
        data={
            "entries": entries,
            "total": total,
            "limit": limit,
            "offset": offset
        }
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

    Rewritten for 2-table schema (enterprise.users + enterprise.audit_log).
    """
    from core.database import get_db_pool

    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # User counts
            total_users = await conn.fetchval("SELECT COUNT(*) FROM enterprise.users")
            active_users = await conn.fetchval("SELECT COUNT(*) FROM enterprise.users WHERE is_active = true")
            super_users = await conn.fetchval("SELECT COUNT(*) FROM enterprise.users WHERE is_super_user = true")

            # Recent activity (last 24h)
            recent_logins = await conn.fetchval("""
                SELECT COUNT(*) FROM enterprise.users
                WHERE last_login_at > NOW() - INTERVAL '24 hours'
            """)

            # Audit events today
            audit_today = await conn.fetchval("""
                SELECT COUNT(*) FROM enterprise.audit_log
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)

            return {
                "users": {
                    "total": total_users,
                    "active": active_users,
                    "super_users": super_users,
                    "recent_logins_24h": recent_logins
                },
                "audit": {
                    "events_24h": audit_today
                },
                "departments": {
                    "count": 6  # Static post-migration
                }
            }
    except Exception as e:
        logger.error(f"[Admin] Stats error: {e}")
        return {"error": str(e), "users": {"total": 0}, "audit": {"events_24h": 0}}


# =============================================================================
# DEPARTMENTS LIST (for dropdowns)
# =============================================================================

@admin_router.get("/departments", response_model=APIResponse)
async def list_all_departments(
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    List all departments (static list post-migration).

    The departments table was deleted during schema migration.
    Department slugs are now just strings in user.department_access arrays.
    Returns the static list of 6 departments.
    """
    # Static departments after 2-table schema migration
    departments = [
        {"slug": "credit", "name": "Credit Department", "description": "Credit and collections"},
        {"slug": "sales", "name": "Sales Department", "description": "Sales operations"},
        {"slug": "warehouse", "name": "Warehouse", "description": "Warehouse operations"},
        {"slug": "accounting", "name": "Accounting", "description": "Financial operations"},
        {"slug": "hr", "name": "Human Resources", "description": "HR operations"},
        {"slug": "it", "name": "IT Department", "description": "Technology operations"},
    ]
    return APIResponse(success=True, data={"departments": departments})


# =============================================================================
# USER CRUD ENDPOINTS
# =============================================================================

class CreateUserRequest(BaseModel):
    """Request to create a single user."""
    email: str
    display_name: Optional[str] = None
    department: Optional[str] = None  # Single department to grant access to
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
    Create a single user with optional department access.

    Flow:
    1. Validate requester is admin (super_user or dept_head)
    2. Validate department if provided
    3. Create user via get_or_create_user()
    4. Grant department access if specified
    """
    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)

    if not requester:
        raise HTTPException(401, "Not authenticated")

    # Must be super_user or dept_head to create users
    if not requester.is_super_user and not requester.dept_head_for:
        raise HTTPException(403, "Only admins can create users")

    # Validate department if provided
    department = request.department
    valid_slugs = [d.slug for d in STATIC_DEPARTMENTS]
    if department and department not in valid_slugs:
        raise HTTPException(400, f"Invalid department: {department}. Valid: {valid_slugs}")

    # Check permission to grant this department
    if department and not requester.can_grant_access(department):
        raise HTTPException(403, f"You cannot grant access to {department}")

    try:
        # Create user (no access by default)
        user = auth.get_or_create_user(
            email=request.email,
            display_name=request.display_name
        )

        if not user:
            raise HTTPException(400, f"Could not create user: {request.email}")

        # Grant department access if specified
        if department:
            auth.grant_department_access(requester, request.email, department)

        logger.info(f"[Admin] {x_user_email} created user {request.email} with department={department}")

        return APIResponse(
            success=True,
            data={
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "display_name": user.display_name,
                    "departments": user.department_access + ([department] if department else []),
                    "is_active": user.is_active
                }
            }
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        logger.error(f"[Admin] Error creating user {request.email}: {e}")
        raise HTTPException(500, f"Error creating user: {str(e)}")


@admin_router.post("/users/batch", response_model=APIResponse)
async def batch_create_users(
    request: BatchCreateRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Batch create multiple users from CSV import.

    Flow:
    1. Validate requester permissions
    2. Validate all departments in request
    3. Process each user: create + grant access
    4. Return summary with success/failure counts
    """
    auth = get_auth_service()
    requester = auth.get_user_by_email(x_user_email)

    if not requester:
        raise HTTPException(401, "Not authenticated")

    if not requester.is_super_user and not requester.dept_head_for:
        raise HTTPException(403, "Only admins can batch create users")

    valid_slugs = [d.slug for d in STATIC_DEPARTMENTS]

    # Validate default department
    if request.default_department not in valid_slugs:
        raise HTTPException(400, f"Invalid default_department: {request.default_department}")

    results = {
        "created": [],
        "existing": [],
        "failed": [],
        "total": len(request.users)
    }

    for entry in request.users:
        try:
            # Determine department (entry-specific or default)
            department = entry.department or request.default_department

            # Validate department
            if department not in valid_slugs:
                results["failed"].append({
                    "email": entry.email,
                    "error": f"Invalid department: {department}"
                })
                continue

            # Check requester can grant this department
            if not requester.can_grant_access(department):
                results["failed"].append({
                    "email": entry.email,
                    "error": f"You cannot grant access to {department}"
                })
                continue

            # Check if user already exists
            existing_user = auth.get_user_by_email(entry.email)
            if existing_user:
                # User exists - just grant access if they don't have it
                if department not in existing_user.department_access:
                    auth.grant_department_access(requester, entry.email, department)
                results["existing"].append({
                    "email": entry.email,
                    "department": department,
                    "note": "User existed, access granted"
                })
                continue

            # Create new user
            user = auth.get_or_create_user(
                email=entry.email,
                display_name=entry.display_name
            )

            if not user:
                results["failed"].append({
                    "email": entry.email,
                    "error": "Could not create user (invalid email domain?)"
                })
                continue

            # Grant department access
            auth.grant_department_access(requester, entry.email, department)

            results["created"].append({
                "email": entry.email,
                "display_name": entry.display_name,
                "department": department
            })

        except Exception as e:
            results["failed"].append({
                "email": entry.email,
                "error": str(e)
            })

    logger.info(
        f"[Admin] {x_user_email} batch import: "
        f"{len(results['created'])} created, "
        f"{len(results['existing'])} existing, "
        f"{len(results['failed'])} failed"
    )

    return APIResponse(
        success=len(results["failed"]) == 0,
        data=results,
        error=f"{len(results['failed'])} users failed" if results["failed"] else None
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
