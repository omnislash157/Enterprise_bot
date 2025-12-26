"""
Auth Service - User Lookup and Permission Checking

AUTHENTICATION: Microsoft Entra ID (Azure AD) via SSO
AUTHORIZATION: Database (enterprise.users table, department_access array)

This service handles:
- User lookup (by email, Azure OID)
- Department access verification (from department_access array)
- Admin operations (grant/revoke access via admin portal)

SCHEMA (2 tables only):
1. enterprise.tenants: id, slug, name, domain
2. enterprise.users: id, tenant_id, email, display_name, azure_oid,
   department_access[], dept_head_for[], is_super_user, is_active,
   created_at, last_login_at

The flow is simple:
1. User logs in via Microsoft SSO â†’ token validated by azure_auth.py
2. User looked up or created here â†’ NO automatic department access
3. Super user / dept head grants access via admin portal
4. department_access array is the source of truth

Usage:
    from auth_service import AuthService, get_auth_service

    auth = get_auth_service()

    # Look up user (returns None if not found)
    user = auth.get_user_by_email("alice@driscollfoods.com")

    # Check department access (simple array check)
    if user.can_access("purchasing"):
        # User has "purchasing" in their department_access array
        ...

    # Admin operations (requires is_super_user or dept in dept_head_for)
    auth.grant_department_access(
        granter=admin_user,
        target_email="newuser@driscollfoods.com",
        department="warehouse"
    )
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE CONFIG
# =============================================================================

DB_CONFIG = {
    "user": os.getenv("AZURE_PG_USER", "mhartigan"),
    "password": os.getenv("AZURE_PG_PASSWORD", "Lalamoney3!"),
    "host": os.getenv("AZURE_PG_HOST", "cogtwin.postgres.database.azure.com"),
    "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
    "sslmode": "require"
}

SCHEMA = "enterprise"

# =============================================================================
# AUTH NOTES
# =============================================================================
# Authentication: Microsoft Entra ID (Azure AD) validates users via SSO
# Authorization: Database (department_access array) controls access
# Admin Portal: Super users and dept heads manage access grants
#
# NO domain whitelists or email pattern detection needed - if they have
# a valid Microsoft token, they're authenticated. Access is granted
# explicitly by admins via the portal.


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class User:
    """User record from enterprise.users"""
    id: str
    email: str
    display_name: Optional[str]
    tenant_id: str
    azure_oid: Optional[str]
    department_access: List[str]      # ['sales', 'purchasing']
    dept_head_for: List[str]          # ['sales']
    is_super_user: bool
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    def can_access(self, department: str) -> bool:
        """Check if user can access a department."""
        return self.is_super_user or department in self.department_access

    def can_grant_access(self, department: str) -> bool:
        """Check if user can grant access to a department."""
        return self.is_super_user or department in self.dept_head_for

    @property
    def active(self) -> bool:
        """Alias for backwards compatibility"""
        return self.is_active


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

    Uses ONLY 2 tables:
    - enterprise.tenants
    - enterprise.users
    """

    def __init__(self):
        self._user_cache: Dict[str, User] = {}

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
                    id, email, display_name, tenant_id, azure_oid,
                    department_access, dept_head_for, is_super_user, is_active,
                    created_at, last_login_at
                FROM {SCHEMA}.users
                WHERE LOWER(email) = %s AND is_active = TRUE
            """, (email_lower,))
            row = cur.fetchone()

        if not row:
            return None

        user = User(
            id=str(row["id"]),
            email=row["email"],
            display_name=row["display_name"],
            tenant_id=str(row["tenant_id"]),
            azure_oid=row["azure_oid"],
            department_access=row["department_access"] or [],
            dept_head_for=row["dept_head_for"] or [],
            is_super_user=row["is_super_user"] or False,
            is_active=row["is_active"] or True,
            created_at=row["created_at"],
            last_login_at=row["last_login_at"]
        )

        self._user_cache[email_lower] = user
        return user

    def get_user_by_azure_oid(self, azure_oid: str) -> Optional[User]:
        """Look up user by Azure Object ID."""
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT
                    id, email, display_name, tenant_id, azure_oid,
                    department_access, dept_head_for, is_super_user, is_active,
                    created_at, last_login_at
                FROM {SCHEMA}.users
                WHERE azure_oid = %s AND is_active = TRUE
            """, (azure_oid,))
            row = cur.fetchone()

        if not row:
            return None

        user = User(
            id=str(row["id"]),
            email=row["email"],
            display_name=row["display_name"],
            tenant_id=str(row["tenant_id"]),
            azure_oid=row["azure_oid"],
            department_access=row["department_access"] or [],
            dept_head_for=row["dept_head_for"] or [],
            is_super_user=row["is_super_user"] or False,
            is_active=row["is_active"] or True,
            created_at=row["created_at"],
            last_login_at=row["last_login_at"]
        )

        # Cache by email
        email_lower = user.email.lower()
        self._user_cache[email_lower] = user

        return user

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Look up user by UUID."""
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT
                    id, email, display_name, tenant_id, azure_oid,
                    department_access, dept_head_for, is_super_user, is_active,
                    created_at, last_login_at
                FROM {SCHEMA}.users
                WHERE id = %s AND is_active = TRUE
            """, (user_id,))
            row = cur.fetchone()

        if not row:
            return None

        user = User(
            id=str(row["id"]),
            email=row["email"],
            display_name=row["display_name"],
            tenant_id=str(row["tenant_id"]),
            azure_oid=row["azure_oid"],
            department_access=row["department_access"] or [],
            dept_head_for=row["dept_head_for"] or [],
            is_super_user=row["is_super_user"] or False,
            is_active=row["is_active"] or True,
            created_at=row["created_at"],
            last_login_at=row["last_login_at"]
        )

        # Cache by email
        email_lower = user.email.lower()
        self._user_cache[email_lower] = user

        return user

    def get_or_create_user(
        self,
        email: str,
        display_name: Optional[str] = None,
        azure_oid: Optional[str] = None
    ) -> Optional[User]:
        """
        Get existing user or create new one.

        Authentication is handled by Microsoft SSO - if we get here, the user
        has a valid token. New users are created with NO department access;
        admins must explicitly grant access via the admin portal.

        Returns User object (existing or newly created).
        """
        email_lower = email.lower().strip()

        # Check existing
        existing = self.get_user_by_email(email_lower)
        if existing:
            return existing

        # Basic validation
        if "@" not in email_lower:
            return None

        # Extract domain from email
        domain = email_lower.split("@")[1]

        # Create user with NO department access
        # Admin must grant access via admin portal
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Get tenant ID by domain
            cur.execute(f"""
                SELECT id FROM {SCHEMA}.tenants WHERE domain = %s
            """, (domain,))
            tenant_row = cur.fetchone()
            if not tenant_row:
                return None
            tenant_id = tenant_row["id"]

            # Create user with no department access
            cur.execute(f"""
                INSERT INTO {SCHEMA}.users
                    (tenant_id, email, display_name, azure_oid,
                     department_access, dept_head_for, is_super_user, is_active)
                VALUES (%s, %s, %s, %s, '{{}}', '{{}}', FALSE, TRUE)
                RETURNING id, email, display_name, tenant_id, azure_oid,
                          department_access, dept_head_for, is_super_user, is_active,
                          created_at, last_login_at
            """, (tenant_id, email_lower, display_name, azure_oid))

            row = cur.fetchone()
            conn.commit()
            cur.close()

        # Return fresh user object
        user = User(
            id=str(row["id"]),
            email=row["email"],
            display_name=row["display_name"],
            tenant_id=str(row["tenant_id"]),
            azure_oid=row["azure_oid"],
            department_access=row["department_access"] or [],
            dept_head_for=row["dept_head_for"] or [],
            is_super_user=row["is_super_user"] or False,
            is_active=row["is_active"] or True,
            created_at=row["created_at"],
            last_login_at=row["last_login_at"]
        )

        # Cache it
        self._user_cache[email_lower] = user
        return user

    # -------------------------------------------------------------------------
    # Session/Login Tracking
    # -------------------------------------------------------------------------

    def update_last_login(self, user_id: str) -> None:
        """Update the last_login_at timestamp for a user."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET last_login_at = now()
                WHERE id = %s
            """, (user_id,))
            conn.commit()
            cur.close()

    def update_user(
        self,
        updater: User,
        target_email: str,
        display_name: Optional[str] = None,
        email: Optional[str] = None
    ) -> bool:
        """
        Update user details (email and/or display_name).

        Args:
            updater: User performing the update (for permission check)
            target_email: Email of user to update
            display_name: New display name (optional)
            email: New email address (optional)

        Returns:
            True if user was updated, False if not found

        Raises:
            PermissionError: If updater lacks permission to update target
        """
        target_email_lower = target_email.lower().strip()

        # Get target user
        target = self.get_user_by_email(target_email_lower)
        if not target:
            return False

        # Permission check
        # Super users can update anyone
        # Dept heads can update users in their departments
        # Users can update themselves
        is_self = updater.email.lower() == target_email_lower
        if not updater.is_super_user and not is_self:
            # Check if updater is dept head for any of target's departments
            if not updater.dept_head_for:
                raise PermissionError(f"User {updater.email} cannot update {target_email}")

            # Check if target has any departments managed by updater
            has_permission = any(
                dept in updater.dept_head_for
                for dept in target.department_access
            )
            if not has_permission:
                raise PermissionError(
                    f"User {updater.email} cannot update {target_email} "
                    "(no shared department authority)"
                )

        # Nothing to update?
        if not display_name and not email:
            return True

        # Build update fields
        update_fields = []
        params = []

        if display_name:
            update_fields.append("display_name = %s")
            params.append(display_name)

        if email:
            update_fields.append("email = %s")
            params.append(email.lower().strip())

        params.append(target_email_lower)

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET {', '.join(update_fields)}
                WHERE LOWER(email) = %s
            """, tuple(params))

            rows_affected = cur.rowcount
            conn.commit()
            cur.close()

        # Clear cache
        self._clear_user_cache(target_email_lower)
        if email:
            self._clear_user_cache(email)

        return rows_affected > 0

    def deactivate_user(
        self,
        deactivator: User,
        target_email: str
    ) -> bool:
        """
        Deactivate a user (soft delete by setting is_active = false).

        Args:
            deactivator: User performing the deactivation (for permission check)
            target_email: Email of user to deactivate

        Returns:
            True if user was deactivated, False if not found

        Raises:
            PermissionError: If deactivator lacks permission or tries to self-deactivate
        """
        target_email_lower = target_email.lower().strip()

        # Get target user
        target = self.get_user_by_email(target_email_lower)
        if not target:
            return False

        # Permission checks
        # Cannot deactivate yourself
        if deactivator.email.lower() == target_email_lower:
            raise PermissionError("Cannot deactivate your own account")

        # Super users can deactivate anyone (except themselves)
        if deactivator.is_super_user:
            pass  # Permission granted
        # Dept heads can deactivate users in departments they head
        elif deactivator.dept_head_for:
            has_permission = any(
                dept in deactivator.dept_head_for
                for dept in target.department_access
            )
            if not has_permission:
                raise PermissionError(
                    f"User {deactivator.email} cannot deactivate {target_email} "
                    "(no shared department authority)"
                )
        else:
            raise PermissionError(
                f"User {deactivator.email} does not have deactivation privileges"
            )

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET is_active = FALSE
                WHERE LOWER(email) = %s
            """, (target_email_lower,))

            rows_affected = cur.rowcount
            conn.commit()
            cur.close()

        # Clear cache
        self._clear_user_cache(target_email_lower)

        return rows_affected > 0

    def reactivate_user(
        self,
        reactivator: User,
        target_email: str
    ) -> bool:
        """
        Reactivate a previously deactivated user (set is_active = true).

        Args:
            reactivator: User performing the reactivation (for permission check)
            target_email: Email of user to reactivate

        Returns:
            True if user was reactivated, False if not found

        Raises:
            PermissionError: If reactivator lacks permission
        """
        target_email_lower = target_email.lower().strip()

        # For reactivation, we need to query the user even if inactive
        # So we can't use get_user_by_email (which filters is_active=TRUE)
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Get target user (including inactive ones)
            cur.execute(f"""
                SELECT
                    id, email, display_name, tenant_id, azure_oid,
                    department_access, dept_head_for, is_super_user, is_active,
                    created_at, last_login_at
                FROM {SCHEMA}.users
                WHERE LOWER(email) = %s
            """, (target_email_lower,))
            row = cur.fetchone()

            if not row:
                cur.close()
                return False

            target = User(
                id=str(row["id"]),
                email=row["email"],
                display_name=row["display_name"],
                tenant_id=str(row["tenant_id"]),
                azure_oid=row["azure_oid"],
                department_access=row["department_access"] or [],
                dept_head_for=row["dept_head_for"] or [],
                is_super_user=row["is_super_user"] or False,
                is_active=row["is_active"] or False,
                created_at=row["created_at"],
                last_login_at=row["last_login_at"]
            )

            # Permission checks
            # Super users can reactivate anyone
            if reactivator.is_super_user:
                pass  # Permission granted
            # Dept heads can reactivate users in departments they head
            elif reactivator.dept_head_for:
                has_permission = any(
                    dept in reactivator.dept_head_for
                    for dept in target.department_access
                )
                if not has_permission:
                    raise PermissionError(
                        f"User {reactivator.email} cannot reactivate {target_email} "
                        "(no shared department authority)"
                    )
            else:
                raise PermissionError(
                    f"User {reactivator.email} does not have reactivation privileges"
                )

            # Reactivate
            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET is_active = TRUE
                WHERE LOWER(email) = %s
            """, (target_email_lower,))

            rows_affected = cur.rowcount
            conn.commit()
            cur.close()

        # Clear cache
        self._clear_user_cache(target_email_lower)

        return rows_affected > 0

    # -------------------------------------------------------------------------
    # Department Access Checks (Simple!)
    # -------------------------------------------------------------------------

    def can_access_department(self, user: User, department: str) -> bool:
        """Check if user can access a specific department."""
        return user.can_access(department)

    def can_grant_access_to(self, user: User, department: str) -> bool:
        """Check if user can grant access to a specific department."""
        return user.can_grant_access(department)

    # -------------------------------------------------------------------------
    # Admin Operations
    # -------------------------------------------------------------------------

    def grant_department_access(
        self,
        granter: User,
        target_email: str,
        department: str
    ) -> bool:
        """
        Grant department access to a user.

        Permission checks:
        - Super users can grant anything
        - Dept heads can grant access to departments they head
        - Regular users cannot grant access

        Returns True if successful, raises exception on permission error.
        """
        # Permission check
        if not granter.can_grant_access(department):
            raise PermissionError(
                f"User {granter.email} cannot grant access to {department}"
            )

        target_email_lower = target_email.lower().strip()

        with get_db_connection() as conn:
            cur = conn.cursor()

            # Grant access (array append, skip if already exists)
            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET department_access = array_append(department_access, %s)
                WHERE LOWER(email) = %s AND NOT (%s = ANY(department_access))
            """, (department, target_email_lower, department))

            rows_affected = cur.rowcount
            conn.commit()
            cur.close()

        # Clear cache
        self._clear_user_cache(target_email_lower)

        return rows_affected > 0

    def revoke_department_access(
        self,
        revoker: User,
        target_email: str,
        department: str
    ) -> bool:
        """
        Revoke department access from a user.

        Returns True if successful.
        """
        # Permission check
        if not revoker.can_grant_access(department):
            raise PermissionError(
                f"User {revoker.email} cannot revoke access to {department}"
            )

        target_email_lower = target_email.lower().strip()

        with get_db_connection() as conn:
            cur = conn.cursor()

            # Revoke access (array remove)
            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET department_access = array_remove(department_access, %s)
                WHERE LOWER(email) = %s
            """, (department, target_email_lower))

            rows_affected = cur.rowcount
            conn.commit()
            cur.close()

        # Clear cache
        self._clear_user_cache(target_email_lower)

        return rows_affected > 0

    def promote_to_dept_head(
        self,
        promoter: User,
        target_email: str,
        department: str
    ) -> bool:
        """
        Promote a user to department head.

        SUPER USER ONLY - dept_heads cannot promote others.

        Args:
            promoter: User doing the promotion (must be super_user)
            target_email: User to promote
            department: Department they will head

        Returns True if successful.
        """
        if not promoter.is_super_user:
            raise PermissionError("Only super users can promote department heads")

        target_email_lower = target_email.lower().strip()

        with get_db_connection() as conn:
            cur = conn.cursor()

            # Add department to dept_head_for array (skip if already exists)
            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET dept_head_for = array_append(dept_head_for, %s)
                WHERE LOWER(email) = %s AND NOT (%s = ANY(dept_head_for))
            """, (department, target_email_lower, department))

            # Also ensure they have access to the department
            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET department_access = array_append(department_access, %s)
                WHERE LOWER(email) = %s AND NOT (%s = ANY(department_access))
            """, (department, target_email_lower, department))

            rows_affected = cur.rowcount
            conn.commit()
            cur.close()

        self._clear_user_cache(target_email_lower)
        logger.info(f"[AuthService] {promoter.email} promoted {target_email} to dept_head for {department}")

        return rows_affected > 0

    def revoke_dept_head(
        self,
        revoker: User,
        target_email: str,
        department: str
    ) -> bool:
        """
        Remove department head status from a user.

        SUPER USER ONLY.

        Note: Does NOT remove their access to the department, just their
        ability to grant access to others.
        """
        if not revoker.is_super_user:
            raise PermissionError("Only super users can revoke department head status")

        target_email_lower = target_email.lower().strip()

        with get_db_connection() as conn:
            cur = conn.cursor()

            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET dept_head_for = array_remove(dept_head_for, %s)
                WHERE LOWER(email) = %s
            """, (department, target_email_lower))

            rows_affected = cur.rowcount
            conn.commit()
            cur.close()

        self._clear_user_cache(target_email_lower)
        logger.info(f"[AuthService] {revoker.email} revoked dept_head from {target_email} for {department}")

        return rows_affected > 0

    def grant_expanded_power(
        self,
        granter: User,
        target_email: str,
        department: str
    ) -> bool:
        """
        Grant a dept_head the ability to grant access to another department.

        SUPER USER ONLY.

        Use case: Priscilla is purchasing head but owner wants her to also
        be able to grant sales, credit access. This adds those departments
        to her dept_head_for array WITHOUT making her "head" of that department.

        Args:
            granter: Super user doing the grant
            target_email: User to grant expanded power to
            department: Additional department they can grant access to
        """
        if not granter.is_super_user:
            raise PermissionError("Only super users can grant expanded powers")

        # Same implementation as promote_to_dept_head - the distinction is semantic
        # (dept_head_for means "can grant access to this department")
        return self.promote_to_dept_head(granter, target_email, department)

    def make_super_user(
        self,
        maker: User,
        target_email: str
    ) -> bool:
        """
        Promote a user to super_user status.

        SUPER USER ONLY. Use carefully - super_users have full access.
        """
        if not maker.is_super_user:
            raise PermissionError("Only super users can create other super users")

        target_email_lower = target_email.lower().strip()

        with get_db_connection() as conn:
            cur = conn.cursor()

            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET is_super_user = TRUE
                WHERE LOWER(email) = %s
            """, (target_email_lower,))

            rows_affected = cur.rowcount
            conn.commit()
            cur.close()

        self._clear_user_cache(target_email_lower)
        logger.info(f"[AuthService] {maker.email} promoted {target_email} to super_user")

        return rows_affected > 0

    def revoke_super_user(
        self,
        revoker: User,
        target_email: str
    ) -> bool:
        """
        Revoke super_user status from a user.

        SUPER USER ONLY. Cannot revoke your own super_user status.
        """
        if not revoker.is_super_user:
            raise PermissionError("Only super users can revoke super_user status")

        target_email_lower = target_email.lower().strip()

        # Prevent self-demotion
        if target_email_lower == revoker.email.lower():
            raise PermissionError("Cannot revoke your own super_user status")

        with get_db_connection() as conn:
            cur = conn.cursor()

            cur.execute(f"""
                UPDATE {SCHEMA}.users
                SET is_super_user = FALSE
                WHERE LOWER(email) = %s
            """, (target_email_lower,))

            rows_affected = cur.rowcount
            conn.commit()
            cur.close()

        self._clear_user_cache(target_email_lower)
        logger.info(f"[AuthService] {revoker.email} revoked super_user from {target_email}")

        return rows_affected > 0

    def list_all_users(self, requester: User) -> List[User]:
        """
        List all users in the company directory.

        Dept heads and super users can see the full directory.
        Regular users cannot.

        Returns list of User objects (limited fields for privacy).
        """
        if not requester.is_super_user and not requester.dept_head_for:
            raise PermissionError("Only department heads and super users can view the company directory")

        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT
                    id, email, display_name, tenant_id, azure_oid,
                    department_access, dept_head_for, is_super_user, is_active,
                    created_at, last_login_at
                FROM {SCHEMA}.users
                WHERE is_active = TRUE
                ORDER BY display_name, email
            """)
            rows = cur.fetchall()

        users = []
        for row in rows:
            users.append(User(
                id=str(row["id"]),
                email=row["email"],
                display_name=row["display_name"],
                tenant_id=str(row["tenant_id"]),
                azure_oid=row["azure_oid"],
                department_access=row["department_access"] or [],
                dept_head_for=row["dept_head_for"] or [],
                is_super_user=row["is_super_user"] or False,
                is_active=row["is_active"],
                created_at=row["created_at"],
                last_login_at=row["last_login_at"],
            ))

        return users

    def list_users_by_department(self, requester: User, department: str) -> List[User]:
        """
        List all users with access to a specific department.

        Dept heads can see users in departments they head.
        Super users can see any department.
        """
        if not requester.is_super_user and department not in (requester.dept_head_for or []):
            raise PermissionError(f"Cannot view users for department: {department}")

        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT
                    id, email, display_name, tenant_id, azure_oid,
                    department_access, dept_head_for, is_super_user, is_active,
                    created_at, last_login_at
                FROM {SCHEMA}.users
                WHERE is_active = TRUE AND %s = ANY(department_access)
                ORDER BY display_name, email
            """, (department,))
            rows = cur.fetchall()

        users = []
        for row in rows:
            users.append(User(
                id=str(row["id"]),
                email=row["email"],
                display_name=row["display_name"],
                tenant_id=str(row["tenant_id"]),
                azure_oid=row["azure_oid"],
                department_access=row["department_access"] or [],
                dept_head_for=row["dept_head_for"] or [],
                is_super_user=row["is_super_user"] or False,
                is_active=row["is_active"],
                created_at=row["created_at"],
                last_login_at=row["last_login_at"],
            ))

        return users

    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------

    def _clear_user_cache(self, email: str):
        """Clear cache for a specific user."""
        email_lower = email.lower().strip()
        self._user_cache.pop(email_lower, None)

    def clear_cache(self):
        """Clear all caches."""
        self._user_cache.clear()


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
    Look up user by email, optionally creating if not found.

    Note: This doesn't actually authenticate - Microsoft SSO does that.
    This just looks up the user record in our database.

    If auto_create=True and user doesn't exist, creates with NO department access.
    Admin must grant access via portal.
    """
    auth = get_auth_service()

    if auto_create:
        return auth.get_or_create_user(email)
    else:
        return auth.get_user_by_email(email)


def check_department_access(email: str, department: str) -> bool:
    """
    Quick check if a user can access a department.

    Returns False if user doesn't exist.
    """
    auth = get_auth_service()
    user = auth.get_user_by_email(email)

    if not user:
        return False

    return user.can_access(department)


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
        print(f"  Super User: {user.is_super_user}")
        print(f"  Department Access: {user.department_access}")
        print(f"  Dept Head For: {user.dept_head_for}")

        print(f"\n[TEST] Can access purchasing: {user.can_access('purchasing')}")
        print(f"[TEST] Can access warehouse: {user.can_access('warehouse')}")
        print(f"[TEST] Can grant access to sales: {user.can_grant_access('sales')}")
    else:
        print("  User not found")

        # Try auto-create
        print(f"\n[TEST] Auto-creating user...")
        user = auth.get_or_create_user(test_email)
        if user:
            print(f"  Created: {user.email}")
            print(f"  Department Access: {user.department_access} (empty - admin must grant)")
        else:
            print("  Domain not allowed")

    print("\n" + "=" * 60)
    print("Tests complete!")
