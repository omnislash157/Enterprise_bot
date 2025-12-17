"""
Auth Service - User Lookup and Permission Checking

Works alongside tenant_service.py to handle:
- User lookup by email (SSO or whitelist)
- Department access verification
- Permission checks for gated departments
- Admin operations (grant/revoke access)

This is the bridge between SSO/email auth and the UserContext system.

Usage:
    from auth_service import AuthService, get_auth_service
    
    auth = get_auth_service()
    
    # Look up user and build context
    user = auth.get_user_by_email("jafflerbach@driscollfoods.com")
    ctx = auth.build_user_context(user)
    
    # Check department access
    if auth.can_access_department(user, "purchasing"):
        # User has explicit access to gated department
        ...
    
    # Admin operations
    auth.grant_department_access(
        actor=admin_user,
        target_user=new_user,
        department_slug="warehouse"
    )
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# DATABASE CONFIG (same as tenant_service.py)
# =============================================================================

DB_CONFIG = {
    "user": os.getenv("AZURE_PG_USER", "Mhartigan"),
    "password": os.getenv("AZURE_PG_PASSWORD", "Lalamoney3!"),
    "host": os.getenv("AZURE_PG_HOST", "enterprisebot.postgres.database.azure.com"),
    "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
    "sslmode": "require"
}

SCHEMA = "enterprise"

# =============================================================================
# GATED DEPARTMENTS
# =============================================================================

# These require explicit access grant - no auto-join
GATED_DEPARTMENTS = {"purchasing", "executive", "hr"}

# Open departments - domain-verified users can auto-join
OPEN_DEPARTMENTS = {"warehouse", "sales", "credit", "transportation"}

# Allowed email domains for auto-provisioning
ALLOWED_DOMAINS = {"driscollfoods.com"}


# =============================================================================
# DATA CLASSES
# =============================================================================

class PermissionTier(Enum):
    USER = 1
    DEPT_HEAD = 2
    SUPER_USER = 3


@dataclass
class User:
    """User record from enterprise.users"""
    id: str
    email: str
    display_name: Optional[str]
    employee_id: Optional[str]
    tenant_id: str
    role: str  # 'user', 'dept_head', 'super_user'
    primary_department_id: Optional[str]
    primary_department_slug: Optional[str] = None
    active: bool = True
    
    @property
    def tier(self) -> PermissionTier:
        if self.role == "super_user":
            return PermissionTier.SUPER_USER
        elif self.role == "dept_head":
            return PermissionTier.DEPT_HEAD
        return PermissionTier.USER
    
    @property
    def is_super_user(self) -> bool:
        return self.role == "super_user"
    
    @property
    def can_manage_users(self) -> bool:
        return self.tier.value >= PermissionTier.DEPT_HEAD.value


@dataclass
class DepartmentAccess:
    """User's access to a specific department"""
    department_id: str
    department_slug: str
    department_name: str
    access_level: str  # 'read', 'write', 'admin'
    is_dept_head: bool
    granted_at: datetime
    expires_at: Optional[datetime] = None


# =============================================================================
# DATABASE HELPERS
# =============================================================================

@contextmanager
def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_db_cursor(conn=None, dict_cursor=True):
    if conn is None:
        with get_db_connection() as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cur = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cur
                conn.commit()
            finally:
                cur.close()
    else:
        cursor_factory = RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
        finally:
            cur.close()


# =============================================================================
# AUTH SERVICE
# =============================================================================

class AuthService:
    """
    Handles user authentication, lookup, and permission checking.
    """
    
    def __init__(self):
        self._user_cache: Dict[str, User] = {}
        self._access_cache: Dict[str, List[DepartmentAccess]] = {}
    
    # -------------------------------------------------------------------------
    # User Lookup
    # -------------------------------------------------------------------------
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Look up user by email address.
        
        Returns None if user doesn't exist.
        Use get_or_create_user() for auto-provisioning.
        """
        email_lower = email.lower().strip()
        
        # Check cache
        if email_lower in self._user_cache:
            return self._user_cache[email_lower]
        
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT 
                    u.id, u.email, u.display_name, u.employee_id,
                    u.tenant_id, u.role, u.primary_department_id, u.active,
                    d.slug as primary_department_slug
                FROM {SCHEMA}.users u
                LEFT JOIN {SCHEMA}.departments d ON u.primary_department_id = d.id
                WHERE LOWER(u.email) = %s AND u.active = TRUE
            """, (email_lower,))
            row = cur.fetchone()
        
        if not row:
            return None
        
        user = User(
            id=str(row["id"]),
            email=row["email"],
            display_name=row["display_name"],
            employee_id=row["employee_id"],
            tenant_id=str(row["tenant_id"]),
            role=row["role"],
            primary_department_id=str(row["primary_department_id"]) if row["primary_department_id"] else None,
            primary_department_slug=row["primary_department_slug"],
            active=row["active"]
        )
        
        self._user_cache[email_lower] = user
        return user
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Look up user by UUID."""
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT 
                    u.id, u.email, u.display_name, u.employee_id,
                    u.tenant_id, u.role, u.primary_department_id, u.active,
                    d.slug as primary_department_slug
                FROM {SCHEMA}.users u
                LEFT JOIN {SCHEMA}.departments d ON u.primary_department_id = d.id
                WHERE u.id = %s AND u.active = TRUE
            """, (user_id,))
            row = cur.fetchone()
        
        if not row:
            return None
        
        return User(
            id=str(row["id"]),
            email=row["email"],
            display_name=row["display_name"],
            employee_id=row["employee_id"],
            tenant_id=str(row["tenant_id"]),
            role=row["role"],
            primary_department_id=str(row["primary_department_id"]) if row["primary_department_id"] else None,
            primary_department_slug=row["primary_department_slug"],
            active=row["active"]
        )
    
    def get_or_create_user(
        self,
        email: str,
        display_name: Optional[str] = None,
        tenant_slug: str = "driscoll",
        default_department: str = "warehouse"
    ) -> Optional[User]:
        """
        Get existing user or create new one if email domain is allowed.
        
        For OPEN departments, auto-assigns based on email patterns.
        For GATED departments, user gets no access until admin grants it.
        
        Returns None if email domain is not allowed.
        """
        email_lower = email.lower().strip()
        
        # Check existing
        existing = self.get_user_by_email(email_lower)
        if existing:
            return existing
        
        # Validate domain
        if "@" not in email_lower:
            return None
        
        domain = email_lower.split("@")[1]
        if domain not in ALLOWED_DOMAINS:
            return None
        
        # Determine department from email patterns
        detected_dept = self._detect_department_from_email(email_lower, default_department)
        
        # Only auto-assign to OPEN departments
        if detected_dept in GATED_DEPARTMENTS:
            detected_dept = default_department  # Fall back to open dept
        
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get tenant ID
            cur.execute(f"""
                SELECT id FROM {SCHEMA}.tenants WHERE slug = %s AND active = TRUE
            """, (tenant_slug,))
            tenant_row = cur.fetchone()
            if not tenant_row:
                return None
            tenant_id = tenant_row["id"]
            
            # Get department ID
            cur.execute(f"""
                SELECT id FROM {SCHEMA}.departments WHERE slug = %s AND active = TRUE
            """, (detected_dept,))
            dept_row = cur.fetchone()
            dept_id = dept_row["id"] if dept_row else None
            
            # Create user
            cur.execute(f"""
                INSERT INTO {SCHEMA}.users 
                    (email, display_name, tenant_id, role, primary_department_id, active)
                VALUES (%s, %s, %s, 'user', %s, TRUE)
                RETURNING id
            """, (email_lower, display_name, tenant_id, dept_id))
            
            user_id = cur.fetchone()["id"]
            
            # Grant access to primary department
            if dept_id:
                cur.execute(f"""
                    INSERT INTO {SCHEMA}.user_department_access
                        (user_id, department_id, access_level, is_dept_head)
                    VALUES (%s, %s, 'read', FALSE)
                    ON CONFLICT (user_id, department_id) DO NOTHING
                """, (user_id, dept_id))
            
            # Log the creation
            cur.execute(f"""
                INSERT INTO {SCHEMA}.access_audit_log
                    (action, target_user_id, target_email, department_slug, new_value)
                VALUES ('user_created', %s, %s, %s, 'auto-provisioned')
            """, (user_id, email_lower, detected_dept))
            
            conn.commit()
            cur.close()
        
        # Return fresh lookup
        return self.get_user_by_email(email_lower)
    
    def _detect_department_from_email(self, email: str, default: str) -> str:
        """Detect department from email address patterns."""
        email_lower = email.lower()
        
        if "transport" in email_lower or "driver" in email_lower or "dispatch" in email_lower:
            return "transportation"
        elif "sales" in email_lower or "account" in email_lower:
            return "sales"
        elif "credit" in email_lower or "ar" in email_lower:
            return "credit"
        elif "warehouse" in email_lower or "ops" in email_lower or "inventory" in email_lower:
            return "warehouse"
        elif "purchasing" in email_lower or "procurement" in email_lower:
            return "purchasing"  # Will be blocked if gated
        elif "exec" in email_lower or "ceo" in email_lower or "cfo" in email_lower:
            return "executive"  # Will be blocked if gated
        
        return default
    
    # -------------------------------------------------------------------------
    # Department Access
    # -------------------------------------------------------------------------
    
    def get_user_department_access(self, user: User) -> List[DepartmentAccess]:
        """Get all departments a user can access."""
        cache_key = user.id
        
        if cache_key in self._access_cache:
            return self._access_cache[cache_key]
        
        # Super users see everything
        if user.is_super_user:
            with get_db_cursor() as cur:
                cur.execute(f"""
                    SELECT id, slug, name FROM {SCHEMA}.departments WHERE active = TRUE
                """)
                rows = cur.fetchall()
            
            access_list = [
                DepartmentAccess(
                    department_id=str(row["id"]),
                    department_slug=row["slug"],
                    department_name=row["name"],
                    access_level="admin",
                    is_dept_head=False,
                    granted_at=datetime.now()
                )
                for row in rows
            ]
            self._access_cache[cache_key] = access_list
            return access_list
        
        # Regular users - check explicit grants
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT 
                    d.id as department_id,
                    d.slug as department_slug,
                    d.name as department_name,
                    uda.access_level,
                    uda.is_dept_head,
                    uda.granted_at,
                    uda.expires_at
                FROM {SCHEMA}.user_department_access uda
                JOIN {SCHEMA}.departments d ON uda.department_id = d.id
                WHERE uda.user_id = %s 
                  AND d.active = TRUE
                  AND (uda.expires_at IS NULL OR uda.expires_at > CURRENT_TIMESTAMP)
                ORDER BY d.name
            """, (user.id,))
            rows = cur.fetchall()
        
        access_list = [
            DepartmentAccess(
                department_id=str(row["department_id"]),
                department_slug=row["department_slug"],
                department_name=row["department_name"],
                access_level=row["access_level"],
                is_dept_head=row["is_dept_head"],
                granted_at=row["granted_at"],
                expires_at=row["expires_at"]
            )
            for row in rows
        ]
        
        self._access_cache[cache_key] = access_list
        return access_list
    
    def can_access_department(self, user: User, department_slug: str) -> bool:
        """Check if user can access a specific department."""
        if user.is_super_user:
            return True
        
        access_list = self.get_user_department_access(user)
        return any(a.department_slug == department_slug for a in access_list)
    
    def get_accessible_department_slugs(self, user: User) -> List[str]:
        """Get list of department slugs user can access."""
        access_list = self.get_user_department_access(user)
        return [a.department_slug for a in access_list]
    
    def is_dept_head_for(self, user: User, department_slug: str) -> bool:
        """Check if user is department head for a specific department."""
        if user.is_super_user:
            return True
        
        access_list = self.get_user_department_access(user)
        return any(
            a.department_slug == department_slug and a.is_dept_head 
            for a in access_list
        )
    
    # -------------------------------------------------------------------------
    # Admin Operations
    # -------------------------------------------------------------------------
    
    def grant_department_access(
        self,
        actor: User,
        target_user: User,
        department_slug: str,
        access_level: str = "read",
        make_dept_head: bool = False,
        reason: Optional[str] = None
    ) -> bool:
        """
        Grant department access to a user.
        
        Permission checks:
        - Super users can grant anything
        - Dept heads can grant access to their department
        - Regular users cannot grant access
        
        Returns True if successful, raises exception on permission error.
        """
        # Permission check
        if not actor.is_super_user:
            if not self.is_dept_head_for(actor, department_slug):
                raise PermissionError(
                    f"User {actor.email} cannot grant access to {department_slug}"
                )
            # Dept heads can't make other dept heads
            if make_dept_head:
                raise PermissionError(
                    "Only super users can assign department head role"
                )
        
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get department ID
            cur.execute(f"""
                SELECT id FROM {SCHEMA}.departments WHERE slug = %s AND active = TRUE
            """, (department_slug,))
            dept_row = cur.fetchone()
            if not dept_row:
                raise ValueError(f"Department not found: {department_slug}")
            dept_id = dept_row["id"]
            
            # Grant access
            cur.execute(f"""
                INSERT INTO {SCHEMA}.user_department_access
                    (user_id, department_id, access_level, is_dept_head, granted_by)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, department_id) DO UPDATE SET
                    access_level = EXCLUDED.access_level,
                    is_dept_head = EXCLUDED.is_dept_head,
                    granted_by = EXCLUDED.granted_by
            """, (target_user.id, dept_id, access_level, make_dept_head, actor.id))
            
            # Audit log
            cur.execute(f"""
                INSERT INTO {SCHEMA}.access_audit_log
                    (action, actor_id, actor_email, target_user_id, target_email,
                     department_id, department_slug, new_value, reason)
                VALUES ('grant', %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                actor.id, actor.email, target_user.id, target_user.email,
                dept_id, department_slug,
                f"access_level={access_level}, dept_head={make_dept_head}",
                reason
            ))
            
            conn.commit()
            cur.close()
        
        # Clear cache
        self._clear_user_cache(target_user.email)
        return True
    
    def revoke_department_access(
        self,
        actor: User,
        target_user: User,
        department_slug: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Revoke department access from a user.
        
        Returns True if successful.
        """
        # Permission check
        if not actor.is_super_user:
            if not self.is_dept_head_for(actor, department_slug):
                raise PermissionError(
                    f"User {actor.email} cannot revoke access to {department_slug}"
                )
        
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get department ID
            cur.execute(f"""
                SELECT id FROM {SCHEMA}.departments WHERE slug = %s
            """, (department_slug,))
            dept_row = cur.fetchone()
            if not dept_row:
                raise ValueError(f"Department not found: {department_slug}")
            dept_id = dept_row["id"]
            
            # Get current access for audit
            cur.execute(f"""
                SELECT access_level, is_dept_head 
                FROM {SCHEMA}.user_department_access
                WHERE user_id = %s AND department_id = %s
            """, (target_user.id, dept_id))
            old_access = cur.fetchone()
            
            if not old_access:
                return False  # Nothing to revoke
            
            # Delete access
            cur.execute(f"""
                DELETE FROM {SCHEMA}.user_department_access
                WHERE user_id = %s AND department_id = %s
            """, (target_user.id, dept_id))
            
            # Audit log
            cur.execute(f"""
                INSERT INTO {SCHEMA}.access_audit_log
                    (action, actor_id, actor_email, target_user_id, target_email,
                     department_id, department_slug, old_value, reason)
                VALUES ('revoke', %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                actor.id, actor.email, target_user.id, target_user.email,
                dept_id, department_slug,
                f"access_level={old_access['access_level']}, dept_head={old_access['is_dept_head']}",
                reason
            ))
            
            conn.commit()
            cur.close()
        
        # Clear cache
        self._clear_user_cache(target_user.email)
        return True
    
    def change_user_role(
        self,
        actor: User,
        target_user: User,
        new_role: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Change a user's global role.

        Only super users can change roles.
        """
        if not actor.is_super_user:
            raise PermissionError("Only super users can change roles")

        if new_role not in ("user", "dept_head", "super_user"):
            raise ValueError(f"Invalid role: {new_role}")

        old_role = target_user.role

        with get_db_connection() as conn:
            cur = conn.cursor()

            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET role = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_role, target_user.id))

            # Audit log
            cur.execute(f"""
                INSERT INTO {SCHEMA}.access_audit_log
                    (action, actor_id, actor_email, target_user_id, target_email,
                     old_value, new_value, reason)
                VALUES ('role_change', %s, %s, %s, %s, %s, %s, %s)
            """, (
                actor.id, actor.email, target_user.id, target_user.email,
                old_role, new_role, reason
            ))

            conn.commit()
            cur.close()

        # Clear cache
        self._clear_user_cache(target_user.email)
        return True

    # -------------------------------------------------------------------------
    # User CRUD Operations (Admin)
    # -------------------------------------------------------------------------

    def create_user(
        self,
        actor: User,
        email: str,
        display_name: Optional[str] = None,
        employee_id: Optional[str] = None,
        role: str = "user",
        primary_department_slug: Optional[str] = None,
        department_access: Optional[List[str]] = None,
        reason: Optional[str] = None
    ) -> User:
        """
        Admin-driven user creation (no domain restriction).

        Unlike get_or_create_user(), this:
        - Allows any email domain
        - Sets custom role/department
        - Requires admin permissions

        Args:
            actor: Admin performing the action
            email: User email address
            display_name: Optional display name
            employee_id: Optional employee ID
            role: 'user', 'dept_head', or 'super_user'
            primary_department_slug: Primary department slug
            department_access: List of department slugs to grant access
            reason: Audit log reason

        Returns:
            Created User object

        Raises:
            PermissionError: If actor lacks permission
            ValueError: If email already exists or invalid data
        """
        # Permission check - only super_users can create users
        if not actor.is_super_user:
            raise PermissionError("Only super users can create users")

        email_lower = email.lower().strip()

        # Check if already exists
        existing = self.get_user_by_email(email_lower)
        if existing:
            raise ValueError(f"User already exists: {email_lower}")

        # Validate role
        if role not in ("user", "dept_head", "super_user"):
            raise ValueError(f"Invalid role: {role}")

        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Get tenant ID (default to driscoll)
            cur.execute(f"""
                SELECT id FROM {SCHEMA}.tenants WHERE slug = 'driscoll' AND active = TRUE
            """)
            tenant_row = cur.fetchone()
            if not tenant_row:
                raise ValueError("Default tenant not found")
            tenant_id = tenant_row["id"]

            # Get primary department ID if specified
            primary_dept_id = None
            if primary_department_slug:
                cur.execute(f"""
                    SELECT id FROM {SCHEMA}.departments
                    WHERE slug = %s AND active = TRUE
                """, (primary_department_slug,))
                dept_row = cur.fetchone()
                if not dept_row:
                    raise ValueError(f"Department not found: {primary_department_slug}")
                primary_dept_id = dept_row["id"]

            # Create user
            cur.execute(f"""
                INSERT INTO {SCHEMA}.users
                    (email, display_name, employee_id, tenant_id, role,
                     primary_department_id, active)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
            """, (email_lower, display_name, employee_id, tenant_id, role, primary_dept_id))

            user_id = cur.fetchone()["id"]

            # Grant department access
            depts_to_grant = department_access or []
            if primary_department_slug and primary_department_slug not in depts_to_grant:
                depts_to_grant.append(primary_department_slug)

            for dept_slug in depts_to_grant:
                cur.execute(f"""
                    SELECT id FROM {SCHEMA}.departments
                    WHERE slug = %s AND active = TRUE
                """, (dept_slug,))
                dept_row = cur.fetchone()
                if dept_row:
                    cur.execute(f"""
                        INSERT INTO {SCHEMA}.user_department_access
                            (user_id, department_id, access_level, is_dept_head, granted_by)
                        VALUES (%s, %s, 'read', FALSE, %s)
                        ON CONFLICT (user_id, department_id) DO NOTHING
                    """, (user_id, dept_row["id"], actor.id))

            # Audit log
            cur.execute(f"""
                INSERT INTO {SCHEMA}.access_audit_log
                    (action, actor_id, actor_email, target_user_id, target_email,
                     department_slug, new_value, reason)
                VALUES ('user_created', %s, %s, %s, %s, %s, %s, %s)
            """, (
                actor.id, actor.email, user_id, email_lower,
                primary_department_slug,
                f"role={role}, admin_created=true",
                reason
            ))

            conn.commit()
            cur.close()

        # Return the created user
        return self.get_user_by_email(email_lower)

    def update_user(
        self,
        actor: User,
        target_user: User,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        employee_id: Optional[str] = None,
        primary_department_slug: Optional[str] = None,
        reason: Optional[str] = None
    ) -> User:
        """
        Update user details.

        Only super_users can update users.
        Pass None for fields that shouldn't change.
        Pass empty string to clear a field.

        Returns:
            Updated User object
        """
        if not actor.is_super_user:
            raise PermissionError("Only super users can update users")

        updates = []
        params = []
        old_values = []
        new_values = []

        if email is not None:
            new_email = email.lower().strip()
            if new_email != target_user.email.lower():
                # Check if new email already exists
                existing = self.get_user_by_email(new_email)
                if existing and existing.id != target_user.id:
                    raise ValueError(f"Email already in use: {new_email}")
                updates.append("email = %s")
                params.append(new_email)
                old_values.append(f"email={target_user.email}")
                new_values.append(f"email={new_email}")

        if display_name is not None:
            updates.append("display_name = %s")
            params.append(display_name if display_name else None)
            old_values.append(f"display_name={target_user.display_name}")
            new_values.append(f"display_name={display_name}")

        if employee_id is not None:
            updates.append("employee_id = %s")
            params.append(employee_id if employee_id else None)
            old_values.append(f"employee_id={target_user.employee_id}")
            new_values.append(f"employee_id={employee_id}")

        if primary_department_slug is not None:
            with get_db_cursor() as cur:
                if primary_department_slug:
                    cur.execute(f"""
                        SELECT id FROM {SCHEMA}.departments
                        WHERE slug = %s AND active = TRUE
                    """, (primary_department_slug,))
                    dept_row = cur.fetchone()
                    if not dept_row:
                        raise ValueError(f"Department not found: {primary_department_slug}")
                    updates.append("primary_department_id = %s")
                    params.append(dept_row["id"])
                else:
                    updates.append("primary_department_id = NULL")
                old_values.append(f"primary_dept={target_user.primary_department_slug}")
                new_values.append(f"primary_dept={primary_department_slug}")

        if not updates:
            return target_user  # Nothing to update

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(target_user.id)

        with get_db_connection() as conn:
            cur = conn.cursor()

            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET {', '.join(updates)}
                WHERE id = %s
            """, params)

            # Audit log
            cur.execute(f"""
                INSERT INTO {SCHEMA}.access_audit_log
                    (action, actor_id, actor_email, target_user_id, target_email,
                     old_value, new_value, reason)
                VALUES ('user_updated', %s, %s, %s, %s, %s, %s, %s)
            """, (
                actor.id, actor.email, target_user.id, target_user.email,
                '; '.join(old_values), '; '.join(new_values), reason
            ))

            conn.commit()
            cur.close()

        # Clear cache and return fresh user
        self._clear_user_cache(target_user.email)
        if email:
            self._clear_user_cache(email)

        return self.get_user_by_id(target_user.id)

    def deactivate_user(
        self,
        actor: User,
        target_user: User,
        reason: Optional[str] = None
    ) -> bool:
        """
        Soft-delete a user (set active=FALSE).

        User data is preserved but they cannot log in.
        """
        if not actor.is_super_user:
            raise PermissionError("Only super users can deactivate users")

        if target_user.id == actor.id:
            raise ValueError("Cannot deactivate yourself")

        with get_db_connection() as conn:
            cur = conn.cursor()

            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (target_user.id,))

            # Audit log
            cur.execute(f"""
                INSERT INTO {SCHEMA}.access_audit_log
                    (action, actor_id, actor_email, target_user_id, target_email,
                     old_value, new_value, reason)
                VALUES ('user_deactivated', %s, %s, %s, %s, 'active=true', 'active=false', %s)
            """, (actor.id, actor.email, target_user.id, target_user.email, reason))

            conn.commit()
            cur.close()

        self._clear_user_cache(target_user.email)
        return True

    def reactivate_user(
        self,
        actor: User,
        user_id: str,
        reason: Optional[str] = None
    ) -> User:
        """
        Reactivate a previously deactivated user.

        Returns the reactivated User object.
        """
        if not actor.is_super_user:
            raise PermissionError("Only super users can reactivate users")

        # Get user including inactive
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT id, email, display_name, employee_id, tenant_id, role,
                       primary_department_id, active
                FROM {SCHEMA}.users
                WHERE id = %s
            """, (user_id,))
            row = cur.fetchone()

        if not row:
            raise ValueError("User not found")

        if row["active"]:
            raise ValueError("User is already active")

        with get_db_connection() as conn:
            cur = conn.cursor()

            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET active = TRUE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (user_id,))

            # Audit log
            cur.execute(f"""
                INSERT INTO {SCHEMA}.access_audit_log
                    (action, actor_id, actor_email, target_user_id, target_email,
                     old_value, new_value, reason)
                VALUES ('user_reactivated', %s, %s, %s, %s, 'active=false', 'active=true', %s)
            """, (actor.id, actor.email, user_id, row["email"], reason))

            conn.commit()
            cur.close()

        return self.get_user_by_id(user_id)

    def batch_create_users(
        self,
        actor: User,
        user_data: List[Dict[str, str]],
        default_department: str = "warehouse",
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Batch create multiple users.

        Args:
            actor: Admin performing the action
            user_data: List of dicts with keys: email, display_name (optional),
                      department (optional)
            default_department: Fallback department if not specified
            reason: Audit log reason

        Returns:
            {
                "created": [list of created emails],
                "already_existed": [list of existing emails],
                "failed": [{"email": str, "error": str}, ...]
            }
        """
        if not actor.is_super_user:
            raise PermissionError("Only super users can batch create users")

        results = {
            "created": [],
            "already_existed": [],
            "failed": []
        }

        for entry in user_data:
            email = entry.get("email", "").lower().strip()
            display_name = entry.get("display_name", "").strip() or None
            department = entry.get("department", "").strip() or default_department

            if not email:
                continue

            # Basic email validation
            if "@" not in email:
                results["failed"].append({
                    "email": email,
                    "error": "Invalid email format"
                })
                continue

            try:
                # Check if exists
                existing = self.get_user_by_email(email)
                if existing:
                    results["already_existed"].append(email)
                    continue

                # Create user
                self.create_user(
                    actor=actor,
                    email=email,
                    display_name=display_name,
                    role="user",
                    primary_department_slug=department,
                    department_access=[department],
                    reason=reason or "batch_import"
                )
                results["created"].append(email)

            except Exception as e:
                results["failed"].append({
                    "email": email,
                    "error": str(e)
                })

        return results

    # -------------------------------------------------------------------------
    # Admin Queries
    # -------------------------------------------------------------------------
    
    def list_users_in_department(
        self,
        actor: User,
        department_slug: str
    ) -> List[Dict[str, Any]]:
        """
        List all users with access to a department.
        
        Dept heads can see their department, super users see all.
        """
        if not actor.is_super_user and not self.is_dept_head_for(actor, department_slug):
            raise PermissionError(
                f"User {actor.email} cannot view users in {department_slug}"
            )
        
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT 
                    u.id, u.email, u.display_name, u.employee_id, u.role,
                    uda.access_level, uda.is_dept_head, uda.granted_at
                FROM {SCHEMA}.users u
                JOIN {SCHEMA}.user_department_access uda ON u.id = uda.user_id
                JOIN {SCHEMA}.departments d ON uda.department_id = d.id
                WHERE d.slug = %s AND u.active = TRUE
                ORDER BY uda.is_dept_head DESC, u.display_name
            """, (department_slug,))
            rows = cur.fetchall()
        
        return [dict(row) for row in rows]
    
    def list_all_users(self, actor: User) -> List[Dict[str, Any]]:
        """
        List all users (super user only).
        """
        if not actor.is_super_user:
            raise PermissionError("Only super users can list all users")
        
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT 
                    u.id, u.email, u.display_name, u.employee_id, u.role,
                    u.active, u.last_login_at,
                    d.name as primary_department
                FROM {SCHEMA}.users u
                LEFT JOIN {SCHEMA}.departments d ON u.primary_department_id = d.id
                ORDER BY u.role DESC, u.email
            """)
            rows = cur.fetchall()
        
        return [dict(row) for row in rows]
    
    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------
    
    # -------------------------------------------------------------------------
    # Azure AD Integration Methods
    # -------------------------------------------------------------------------

    def get_user_by_azure_oid(self, azure_oid: str) -> Optional[User]:
        """Look up user by Azure Object ID."""
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT
                    u.id, u.email, u.display_name, u.employee_id,
                    u.tenant_id, u.role, u.primary_department_id, u.active,
                    d.slug as primary_department_slug
                FROM {SCHEMA}.users u
                LEFT JOIN {SCHEMA}.departments d ON u.primary_department_id = d.id
                WHERE u.azure_oid = %s AND u.active = TRUE
            """, (azure_oid,))
            row = cur.fetchone()

        if not row:
            return None

        return User(
            id=str(row["id"]),
            email=row["email"],
            display_name=row["display_name"],
            employee_id=row["employee_id"],
            tenant_id=str(row["tenant_id"]),
            role=row["role"],
            primary_department_id=str(row["primary_department_id"]) if row["primary_department_id"] else None,
            primary_department_slug=row["primary_department_slug"],
            active=row["active"]
        )

    def create_user_from_azure(
        self,
        email: str,
        display_name: str,
        azure_oid: str,
    ) -> User:
        """
        Create new user from Azure AD login.

        Auto-provisions with 'user' role and no department.
        Admin can upgrade later.
        """
        import uuid
        user_id = str(uuid.uuid4())

        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Get tenant ID (default to driscoll)
            cur.execute(f"""
                SELECT id FROM {SCHEMA}.tenants WHERE slug = 'driscoll' AND active = TRUE
            """)
            tenant_row = cur.fetchone()
            if not tenant_row:
                raise ValueError("Default tenant not found")
            tenant_id = tenant_row["id"]

            cur.execute(f"""
                INSERT INTO {SCHEMA}.users (
                    id, email, display_name, azure_oid,
                    tenant_id, role, active, created_at
                )
                VALUES (%s, %s, %s, %s, %s, 'user', TRUE, NOW())
                RETURNING *
            """, (user_id, email, display_name, azure_oid, tenant_id))

            row = cur.fetchone()
            conn.commit()

            # Log the creation
            cur.execute(f"""
                INSERT INTO {SCHEMA}.access_audit_log
                    (action, target_user_id, target_email, new_value)
                VALUES ('user_created_azure_sso', %s, %s, %s)
            """, (user_id, email, f"azure_oid={azure_oid}"))

            conn.commit()
            cur.close()

            return User(
                id=str(row["id"]),
                email=row["email"],
                display_name=row["display_name"],
                employee_id=row["employee_id"],
                tenant_id=str(row["tenant_id"]),
                role=row["role"],
                primary_department_id=str(row["primary_department_id"]) if row.get("primary_department_id") else None,
                primary_department_slug=None,
                active=row["active"]
            )

    def link_user_to_azure(self, user_id: str, azure_oid: str) -> User:
        """Link existing user to Azure AD account."""
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET azure_oid = %s
                WHERE id = %s
                RETURNING *
            """, (azure_oid, user_id))

            row = cur.fetchone()

            # Log the linking
            cur.execute(f"""
                INSERT INTO {SCHEMA}.access_audit_log
                    (action, target_user_id, target_email, new_value)
                VALUES ('user_linked_azure', %s, %s, %s)
            """, (user_id, row["email"], f"azure_oid={azure_oid}"))

            conn.commit()
            cur.close()

            return User(
                id=str(row["id"]),
                email=row["email"],
                display_name=row["display_name"],
                employee_id=row["employee_id"],
                tenant_id=str(row["tenant_id"]),
                role=row["role"],
                primary_department_id=str(row["primary_department_id"]) if row.get("primary_department_id") else None,
                primary_department_slug=None,
                active=row["active"]
            )

    def update_user_from_azure(
        self,
        user_id: str,
        email: str,
        display_name: str,
        azure_oid: str,
    ) -> User:
        """Update user info from Azure AD on each login."""
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET email = %s, display_name = %s, azure_oid = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *
            """, (email, display_name, azure_oid, user_id))

            row = cur.fetchone()
            conn.commit()
            cur.close()

            # Clear cache
            self._clear_user_cache(email)

            return User(
                id=str(row["id"]),
                email=row["email"],
                display_name=row["display_name"],
                employee_id=row["employee_id"],
                tenant_id=str(row["tenant_id"]),
                role=row["role"],
                primary_department_id=str(row["primary_department_id"]) if row.get("primary_department_id") else None,
                primary_department_slug=None,
                active=row["active"]
            )

    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------

    def _clear_user_cache(self, email: str):
        """Clear cache for a specific user."""
        email_lower = email.lower().strip()
        self._user_cache.pop(email_lower, None)

        # Also clear access cache if we have the user ID
        for user in list(self._user_cache.values()):
            if user.email.lower() == email_lower:
                self._access_cache.pop(user.id, None)
                break
    
    def clear_cache(self):
        """Clear all caches."""
        self._user_cache.clear()
        self._access_cache.clear()
    
    # -------------------------------------------------------------------------
    # Session/Login Tracking
    # -------------------------------------------------------------------------
    
    def record_login(self, user: User, ip_address: Optional[str] = None):
        """Record a user login event."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Update last login
            cur.execute(f"""
                UPDATE {SCHEMA}.users 
                SET last_login_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (user.id,))
            
            # Audit log
            cur.execute(f"""
                INSERT INTO {SCHEMA}.access_audit_log
                    (action, target_user_id, target_email, ip_address)
                VALUES ('login', %s, %s, %s)
            """, (user.id, user.email, ip_address))
            
            conn.commit()
            cur.close()


# =============================================================================
# SINGLETON
# =============================================================================

_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get or create the auth service singleton."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def authenticate_user(email: str, auto_create: bool = True) -> Optional[User]:
    """
    Authenticate a user by email.
    
    If auto_create=True, creates new user for allowed domains.
    Returns None if authentication fails.
    """
    auth = get_auth_service()
    
    if auto_create:
        return auth.get_or_create_user(email)
    else:
        return auth.get_user_by_email(email)


def check_department_access(email: str, department_slug: str) -> bool:
    """
    Quick check if a user can access a department.
    
    Returns False if user doesn't exist.
    """
    auth = get_auth_service()
    user = auth.get_user_by_email(email)
    
    if not user:
        return False
    
    return auth.can_access_department(user, department_slug)


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("Auth Service - User Lookup & Permission Checking")
    print("=" * 60)
    
    auth = get_auth_service()
    
    # Test user lookup
    test_email = sys.argv[1] if len(sys.argv) > 1 else "mhartigan@driscollfoods.com"
    
    print(f"\n[TEST] Looking up user: {test_email}")
    user = auth.get_user_by_email(test_email)
    
    if user:
        print(f"  Found: {user.display_name or user.email}")
        print(f"  Role: {user.role}")
        print(f"  Tier: {user.tier.name}")
        print(f"  Primary dept: {user.primary_department_slug or 'None'}")
        
        print(f"\n[TEST] Department access:")
        access_list = auth.get_user_department_access(user)
        for acc in access_list:
            head_marker = " (DEPT HEAD)" if acc.is_dept_head else ""
            print(f"  - {acc.department_name}: {acc.access_level}{head_marker}")
        
        print(f"\n[TEST] Can access purchasing: {auth.can_access_department(user, 'purchasing')}")
        print(f"[TEST] Can access warehouse: {auth.can_access_department(user, 'warehouse')}")
    else:
        print("  User not found")
        
        # Try auto-create
        print(f"\n[TEST] Auto-creating user...")
        user = auth.get_or_create_user(test_email)
        if user:
            print(f"  Created: {user.email} in {user.primary_department_slug}")
        else:
            print("  Domain not allowed")
    
    print("\n" + "=" * 60)
    print("Tests complete!")