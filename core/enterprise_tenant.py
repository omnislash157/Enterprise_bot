"""
Enterprise Tenant Context - Lightweight request context for enterprise mode.

This is a simple dataclass that carries tenant/department/user context
through the request lifecycle. It does NOT manage auth or access control -
that's handled by Entra ID + the admin portal + RLS policies.

Usage:
    from enterprise_tenant import TenantContext
    
    # From authenticated request
    tenant = TenantContext(
        tenant_id="driscoll",
        department="warehouse",
        user_email="alice@driscollfoods.com",
        user_id="uuid-here",
    )
    
    # Pass to EnterpriseTwin
    response = await twin.think(
        user_input=message,
        user_email=tenant.user_email,
        department=tenant.department,
        session_id=session_id,
    )

Version: 2.0.0 (post-merge, Entra ID auth)

DEPRECATED:
- SimpleTenantManager - replaced by Entra ID + admin portal
- Division detection from email - use database user_department_access
- Domain whitelist - use Entra ID tenant restrictions
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class TenantContext:
    """
    Request context for enterprise mode.

    Carries tenant/department/user info through the request lifecycle.
    Created from authenticated request, passed to EnterpriseTwin.

    Auth and access control are NOT handled here - that's:
    - Entra ID for authentication
    - RLS policies for data access
    - Admin portal for user management
    """
    # Required
    tenant_id: str                          # Company ID (e.g., "driscoll")
    department: str                         # User's primary department

    # User info (from auth)
    user_email: Optional[str] = None
    user_id: Optional[str] = None           # UUID from users table
    display_name: Optional[str] = None

    # Access info (from database)
    role: str = "user"                      # user | dept_head | admin | super_user
    departments: List[str] = field(default_factory=list)  # All accessible depts

    # Multi-tenant fields (from tenants table)
    slug: Optional[str] = None              # Tenant slug (e.g., "driscoll")
    name: Optional[str] = None              # Tenant display name
    domain: Optional[str] = None            # Domain (e.g., "driscollintel.com")
    azure_tenant_id: Optional[str] = None   # Azure AD Tenant ID for SSO
    azure_client_id: Optional[str] = None   # Azure AD Client ID for SSO
    branding: Dict[str, Any] = field(default_factory=dict)  # Logo, colors, etc.

    # Session
    session_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/debugging."""
        return {
            "tenant_id": self.tenant_id,
            "department": self.department,
            "user_email": self.user_email,
            "user_id": self.user_id,
            "role": self.role,
            "departments": self.departments,
            "session_id": self.session_id,
        }
    
    @property
    def has_azure_sso(self) -> bool:
        """Check if tenant has Azure SSO configured."""
        return bool(self.azure_tenant_id and self.azure_client_id)

    @property
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.role in ("admin", "super_user")

    @property
    def is_dept_head(self) -> bool:
        """Check if user is a department head."""
        return self.role in ("dept_head", "admin", "super_user")

    def can_access_department(self, dept: str) -> bool:
        """Check if user can access a specific department."""
        if self.is_admin:
            return True
        return dept in self.departments or dept == self.department


@dataclass
class DataConnection:
    """
    Connection info for external data sources.
    
    Separate from RAG - this is for querying Driscoll's business data
    (credits, inventory, etc.) not for process manual retrieval.
    """
    tenant_id: str
    source_type: str                        # "direct_sql" | "etl" | "api"
    
    # For direct_sql (Driscoll SQL Server)
    sql_server: Optional[str] = None
    sql_database: Optional[str] = None
    sql_username: Optional[str] = None
    sql_password: Optional[str] = None
    
    # For etl (data replicated to our PostgreSQL)
    pg_schema: Optional[str] = None
    
    # For api (external API access)
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None


def create_tenant_context_from_auth(
    auth_payload: Dict[str, Any],
    db_user: Optional[Dict[str, Any]] = None,
    tenant_id: str = "driscoll",
) -> TenantContext:
    """
    Create TenantContext from Entra ID auth payload + database user record.
    
    Args:
        auth_payload: Decoded JWT from Entra ID
        db_user: User record from enterprise.users table
        tenant_id: Tenant ID (default driscoll)
        
    Returns:
        TenantContext ready for use
    """
    # Extract from Entra ID token
    email = auth_payload.get("preferred_username") or auth_payload.get("email", "")
    display_name = auth_payload.get("name", "")
    
    # Extract from database user record
    if db_user:
        user_id = db_user.get("id")
        role = "super_user" if db_user.get("is_super_user") else "user"
        primary_dept = db_user.get("primary_department", "default")
        departments = db_user.get("departments", [primary_dept])
        
        # Check for dept head status
        if db_user.get("is_dept_head"):
            role = "dept_head"
    else:
        user_id = None
        role = "user"
        primary_dept = "default"
        departments = [primary_dept]
    
    return TenantContext(
        tenant_id=tenant_id,
        department=primary_dept,
        user_email=email,
        user_id=user_id,
        display_name=display_name,
        role=role,
        departments=departments,
    )


# =============================================================================
# DEPRECATED - Kept for reference, do not use
# =============================================================================

# SimpleTenantManager - DEPRECATED
# Auth is now via Entra ID + admin portal
# Domain whitelist is legacy fallback only

# TenantContext.from_email() - DEPRECATED  
# Division detection should use database user_department_access table
# Not email pattern matching


if __name__ == "__main__":
    # Quick test
    ctx = TenantContext(
        tenant_id="driscoll",
        department="warehouse",
        user_email="alice@driscollfoods.com",
        role="user",
        departments=["warehouse", "shipping"],
    )
    
    print(f"Context: {ctx.to_dict()}")
    print(f"Is admin: {ctx.is_admin}")
    print(f"Can access sales: {ctx.can_access_department('sales')}")
    print(f"Can access warehouse: {ctx.can_access_department('warehouse')}")
    
    print("\n[OK] Enterprise tenant context working")