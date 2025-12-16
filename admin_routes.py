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

from auth_service import (
    get_auth_service,
    User,
    PermissionTier,
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
    """Require at least DEPT_HEAD tier."""
    if user.tier.value < PermissionTier.DEPT_HEAD.value:
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
    
    - DEPT_HEAD: sees users in their departments only
    - SUPER_USER: sees all users, can filter by department
    """
    user = get_current_user(x_user_email)
    require_admin(user)
    
    auth = get_auth_service()
    
    try:
        if user.is_super_user:
            if department:
                users = auth.list_users_in_department(user, department)
            else:
                users = auth.list_all_users(user)
        else:
            # Dept head - list their department's users
            dept_access = auth.get_user_department_access(user)
            head_depts = [a.department_slug for a in dept_access if a.is_dept_head]
            
            if department:
                if department not in head_depts:
                    raise HTTPException(403, f"Not authorized for department: {department}")
                users = auth.list_users_in_department(user, department)
            elif head_depts:
                # Get users from all their departments
                users = []
                for dept_slug in head_depts:
                    dept_users = auth.list_users_in_department(user, dept_slug)
                    users.extend(dept_users)
                # Dedupe by user ID
                seen = set()
                users = [u for u in users if not (u['id'] in seen or seen.add(u['id']))]
            else:
                users = []
        
        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            users = [
                u for u in users
                if search_lower in u.get('email', '').lower()
                or search_lower in (u.get('display_name') or '').lower()
            ]
        
        return APIResponse(
            success=True,
            data={
                "users": users,
                "count": len(users),
                "filtered_by": department,
                "search": search,
            }
        )
    
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(500, f"Error listing users: {str(e)}")


@admin_router.get("/users/{user_id}", response_model=APIResponse)
async def get_user_detail(
    user_id: str,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Get detailed info for a specific user.
    
    Includes their department access list.
    """
    actor = get_current_user(x_user_email)
    require_admin(actor)
    
    auth = get_auth_service()
    
    try:
        target = auth.get_user_by_id(user_id)
        
        if not target:
            raise HTTPException(404, "User not found")
        
        # Permission check - can actor see this user?
        if not actor.is_super_user:
            # Dept head can only see users in their departments
            actor_depts = set(auth.get_accessible_department_slugs(actor))
            target_depts = set(auth.get_accessible_department_slugs(target))
            
            if not actor_depts.intersection(target_depts):
                raise HTTPException(403, "Cannot view this user")
        
        # Get department access
        dept_access = auth.get_user_department_access(target)
        departments = [
            {
                "slug": a.department_slug,
                "name": a.department_name,
                "access_level": a.access_level,
                "is_dept_head": a.is_dept_head,
                "granted_at": a.granted_at.isoformat() if a.granted_at else None,
            }
            for a in dept_access
        ]
        
        return APIResponse(
            success=True,
            data={
                "user": {
                    "id": target.id,
                    "email": target.email,
                    "display_name": target.display_name,
                    "employee_id": target.employee_id,
                    "role": target.role,
                    "tier": target.tier.name,
                    "primary_department": target.primary_department_slug,
                    "active": target.active,
                    "departments": departments,
                }
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user detail: {e}")
        raise HTTPException(500, f"Error getting user: {str(e)}")


@admin_router.put("/users/{user_id}/role", response_model=APIResponse)
async def change_user_role(
    user_id: str,
    request: ChangeRoleRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Change a user's global role.
    
    SUPER_USER only.
    """
    actor = get_current_user(x_user_email)
    require_super_user(actor)
    
    auth = get_auth_service()
    
    try:
        target = auth.get_user_by_id(user_id)
        
        if not target:
            raise HTTPException(404, "User not found")
        
        # Prevent self-demotion
        if target.id == actor.id and request.new_role != "super_user":
            raise HTTPException(400, "Cannot demote yourself")
        
        old_role = target.role
        
        auth.change_user_role(
            actor=actor,
            target_user=target,
            new_role=request.new_role,
            reason=request.reason,
        )
        
        return APIResponse(
            success=True,
            data={
                "user_id": user_id,
                "old_role": old_role,
                "new_role": request.new_role,
                "message": f"Role changed from {old_role} to {request.new_role}",
            }
        )
    
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error changing role: {e}")
        raise HTTPException(500, f"Error changing role: {str(e)}")


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
    
    - DEPT_HEAD: must be head of this department
    - SUPER_USER: can view any department
    """
    actor = get_current_user(x_user_email)
    require_admin(actor)
    
    auth = get_auth_service()
    
    try:
        users = auth.list_users_in_department(actor, slug)
        
        return APIResponse(
            success=True,
            data={
                "department": slug,
                "users": users,
                "count": len(users),
            }
        )
    
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        logger.error(f"Error listing department users: {e}")
        raise HTTPException(500, f"Error listing users: {str(e)}")


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
    
    - DEPT_HEAD: can grant access to their department (not dept_head role)
    - SUPER_USER: can grant any access including dept_head
    """
    actor = get_current_user(x_user_email)
    require_admin(actor)
    
    auth = get_auth_service()
    
    try:
        target = auth.get_user_by_id(request.user_id)
        
        if not target:
            raise HTTPException(404, "Target user not found")
        
        auth.grant_department_access(
            actor=actor,
            target_user=target,
            department_slug=request.department_slug,
            access_level=request.access_level,
            make_dept_head=request.make_dept_head,
            reason=request.reason,
        )
        
        return APIResponse(
            success=True,
            data={
                "user_id": request.user_id,
                "department": request.department_slug,
                "access_level": request.access_level,
                "is_dept_head": request.make_dept_head,
                "message": f"Access granted to {request.department_slug}",
            }
        )
    
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error granting access: {e}")
        raise HTTPException(500, f"Error granting access: {str(e)}")


@admin_router.post("/access/revoke", response_model=APIResponse)
async def revoke_access(
    request: RevokeAccessRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Revoke department access from a user.
    
    - DEPT_HEAD: can revoke access from their department
    - SUPER_USER: can revoke any access
    """
    actor = get_current_user(x_user_email)
    require_admin(actor)
    
    auth = get_auth_service()
    
    try:
        target = auth.get_user_by_id(request.user_id)
        
        if not target:
            raise HTTPException(404, "Target user not found")
        
        success = auth.revoke_department_access(
            actor=actor,
            target_user=target,
            department_slug=request.department_slug,
            reason=request.reason,
        )
        
        if not success:
            return APIResponse(
                success=False,
                error="User did not have access to this department",
            )
        
        return APIResponse(
            success=True,
            data={
                "user_id": request.user_id,
                "department": request.department_slug,
                "message": f"Access revoked from {request.department_slug}",
            }
        )
    
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error revoking access: {e}")
        raise HTTPException(500, f"Error revoking access: {str(e)}")


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
    
    SUPER_USER only.
    
    Returns most recent entries first.
    """
    actor = get_current_user(x_user_email)
    require_super_user(actor)
    
    auth = get_auth_service()
    
    try:
        # Build query for audit log
        from auth_service import get_db_cursor, SCHEMA
        
        with get_db_cursor() as cur:
            # Build WHERE clauses
            conditions = []
            params = []
            
            if action:
                conditions.append("action = %s")
                params.append(action)
            
            if target_email:
                conditions.append("target_email ILIKE %s")
                params.append(f"%{target_email}%")
            
            if department:
                conditions.append("department_slug = %s")
                params.append(department)
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            # Get total count
            cur.execute(f"""
                SELECT COUNT(*) as total
                FROM {SCHEMA}.access_audit_log
                {where_clause}
            """, params)
            total = cur.fetchone()["total"]
            
            # Get entries
            cur.execute(f"""
                SELECT 
                    id, action, actor_email, target_email,
                    department_slug, old_value, new_value, reason,
                    created_at, ip_address::text
                FROM {SCHEMA}.access_audit_log
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, params + [limit, offset])
            
            entries = [dict(row) for row in cur.fetchall()]
        
        return APIResponse(
            success=True,
            data={
                "entries": entries,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(entries) < total,
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting audit log: {e}")
        raise HTTPException(500, f"Error getting audit log: {str(e)}")


# =============================================================================
# STATS ENDPOINT
# =============================================================================

@admin_router.get("/stats", response_model=APIResponse)
async def get_admin_stats(
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Get admin dashboard statistics.
    
    Returns user counts, department counts, recent activity.
    """
    actor = get_current_user(x_user_email)
    require_admin(actor)
    
    auth = get_auth_service()
    
    try:
        from auth_service import get_db_cursor, SCHEMA
        
        with get_db_cursor() as cur:
            # Total users
            cur.execute(f"SELECT COUNT(*) as count FROM {SCHEMA}.users WHERE active = TRUE")
            total_users = cur.fetchone()["count"]
            
            # Users by role
            cur.execute(f"""
                SELECT role, COUNT(*) as count 
                FROM {SCHEMA}.users 
                WHERE active = TRUE 
                GROUP BY role
            """)
            by_role = {row["role"]: row["count"] for row in cur.fetchall()}
            
            # Users by department
            cur.execute(f"""
                SELECT d.slug, d.name, COUNT(uda.user_id) as user_count
                FROM {SCHEMA}.departments d
                LEFT JOIN {SCHEMA}.user_department_access uda ON d.id = uda.department_id
                WHERE d.active = TRUE
                GROUP BY d.id, d.slug, d.name
                ORDER BY d.name
            """)
            by_department = [dict(row) for row in cur.fetchall()]
            
            # Recent logins (last 7 days)
            cur.execute(f"""
                SELECT COUNT(*) as count
                FROM {SCHEMA}.access_audit_log
                WHERE action = 'login'
                AND created_at > NOW() - INTERVAL '7 days'
            """)
            recent_logins = cur.fetchone()["count"]
            
            # Recent access changes (last 7 days)
            cur.execute(f"""
                SELECT COUNT(*) as count
                FROM {SCHEMA}.access_audit_log
                WHERE action IN ('grant', 'revoke', 'role_change')
                AND created_at > NOW() - INTERVAL '7 days'
            """)
            recent_changes = cur.fetchone()["count"]
        
        return APIResponse(
            success=True,
            data={
                "total_users": total_users,
                "users_by_role": by_role,
                "users_by_department": by_department,
                "recent_logins_7d": recent_logins,
                "recent_access_changes_7d": recent_changes,
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(500, f"Error getting stats: {str(e)}")


# =============================================================================
# DEPARTMENTS LIST (for dropdowns)
# =============================================================================

@admin_router.get("/departments", response_model=APIResponse)
async def list_all_departments(
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    List all departments.

    Used for dropdowns in admin UI.
    Super users see all, dept heads see only their departments.
    """
    actor = get_current_user(x_user_email)
    require_admin(actor)

    auth = get_auth_service()

    try:
        from auth_service import get_db_cursor, SCHEMA

        if actor.is_super_user:
            with get_db_cursor() as cur:
                cur.execute(f"""
                    SELECT id, slug, name, description
                    FROM {SCHEMA}.departments
                    WHERE active = TRUE
                    ORDER BY name
                """)
                departments = [dict(row) for row in cur.fetchall()]
        else:
            # Dept heads see only their departments
            dept_access = auth.get_user_department_access(actor)
            departments = [
                {
                    "id": a.department_id,
                    "slug": a.department_slug,
                    "name": a.department_name,
                }
                for a in dept_access
                if a.is_dept_head
            ]

        return APIResponse(
            success=True,
            data={
                "departments": departments,
                "count": len(departments),
            }
        )

    except Exception as e:
        logger.error(f"Error listing departments: {e}")
        raise HTTPException(500, f"Error listing departments: {str(e)}")


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

    SUPER_USER only.
    """
    actor = get_current_user(x_user_email)
    require_super_user(actor)

    auth = get_auth_service()

    try:
        user = auth.create_user(
            actor=actor,
            email=request.email,
            display_name=request.display_name,
            employee_id=request.employee_id,
            role=request.role,
            primary_department_slug=request.primary_department,
            department_access=request.department_access,
            reason=request.reason,
        )

        return APIResponse(
            success=True,
            data={
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "display_name": user.display_name,
                    "role": user.role,
                    "primary_department": user.primary_department_slug,
                },
                "message": f"User created: {user.email}",
            }
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(500, f"Error creating user: {str(e)}")


@admin_router.post("/users/batch", response_model=APIResponse)
async def batch_create_users(
    request: BatchCreateRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Batch create multiple users.

    SUPER_USER only.

    Accepts a list of users with email, optional display_name, and optional department.
    Returns counts of created, already_existed, and failed entries.
    """
    actor = get_current_user(x_user_email)
    require_super_user(actor)

    auth = get_auth_service()

    try:
        # Convert Pydantic models to dicts
        user_data = [
            {
                "email": u.email,
                "display_name": u.display_name,
                "department": u.department,
            }
            for u in request.users
        ]

        results = auth.batch_create_users(
            actor=actor,
            user_data=user_data,
            default_department=request.default_department,
            reason=request.reason,
        )

        return APIResponse(
            success=True,
            data={
                "created": results["created"],
                "created_count": len(results["created"]),
                "already_existed": results["already_existed"],
                "already_existed_count": len(results["already_existed"]),
                "failed": results["failed"],
                "failed_count": len(results["failed"]),
                "message": f"Created {len(results['created'])} users, "
                          f"{len(results['already_existed'])} already existed, "
                          f"{len(results['failed'])} failed",
            }
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        logger.error(f"Error in batch create: {e}")
        raise HTTPException(500, f"Error in batch create: {str(e)}")


@admin_router.put("/users/{user_id}", response_model=APIResponse)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Update user details.

    SUPER_USER only.
    """
    actor = get_current_user(x_user_email)
    require_super_user(actor)

    auth = get_auth_service()

    try:
        target = auth.get_user_by_id(user_id)

        if not target:
            raise HTTPException(404, "User not found")

        updated = auth.update_user(
            actor=actor,
            target_user=target,
            email=request.email,
            display_name=request.display_name,
            employee_id=request.employee_id,
            primary_department_slug=request.primary_department,
            reason=request.reason,
        )

        return APIResponse(
            success=True,
            data={
                "user": {
                    "id": updated.id,
                    "email": updated.email,
                    "display_name": updated.display_name,
                    "employee_id": updated.employee_id,
                    "primary_department": updated.primary_department_slug,
                },
                "message": f"User updated: {updated.email}",
            }
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(500, f"Error updating user: {str(e)}")


@admin_router.delete("/users/{user_id}", response_model=APIResponse)
async def deactivate_user(
    user_id: str,
    request: DeactivateRequest = None,
    x_user_email: str = Header(None, alias="X-User-Email"),
):
    """
    Deactivate (soft delete) a user.

    SUPER_USER only.
    User data is preserved but they cannot log in.
    """
    actor = get_current_user(x_user_email)
    require_super_user(actor)

    auth = get_auth_service()

    try:
        target = auth.get_user_by_id(user_id)

        if not target:
            raise HTTPException(404, "User not found")

        reason = request.reason if request else None
        auth.deactivate_user(actor=actor, target_user=target, reason=reason)

        return APIResponse(
            success=True,
            data={
                "user_id": user_id,
                "email": target.email,
                "message": f"User deactivated: {target.email}",
            }
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error deactivating user: {e}")
        raise HTTPException(500, f"Error deactivating user: {str(e)}")


@admin_router.post("/users/{user_id}/reactivate", response_model=APIResponse)
async def reactivate_user(
    user_id: str,
    x_user_email: str = Header(None, alias="X-User-Email"),
    reason: Optional[str] = None,
):
    """
    Reactivate a previously deactivated user.

    SUPER_USER only.
    """
    actor = get_current_user(x_user_email)
    require_super_user(actor)

    auth = get_auth_service()

    try:
        user = auth.reactivate_user(actor=actor, user_id=user_id, reason=reason)

        return APIResponse(
            success=True,
            data={
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "display_name": user.display_name,
                    "active": user.active,
                },
                "message": f"User reactivated: {user.email}",
            }
        )

    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error reactivating user: {e}")
        raise HTTPException(500, f"Error reactivating user: {str(e)}")
