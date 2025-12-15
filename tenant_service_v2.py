"""
Tenant Service v2 - Full 3-Tier Permission System

Tier 1: User
    - Sees only their department's content (sales manual, warehouse manual, etc.)
    - Data filtered to their employee_id (sales rep sees only their customers)
    - No admin access

Tier 2: Department Head
    - Sees their department's content
    - Sees ALL data in their department (not filtered by employee_id)
    - Can view (but not edit) user assignments in their department
    - Eventually: admin portal access for their department

Tier 3: Super User
    - Sees everything across all departments
    - Full admin access: add/remove users, assign department heads
    - Creator access to all features

Usage:
    from tenant_service_v2 import get_user_context, UserContext, PermissionTier
    
    ctx = await get_user_context(authorization, tenant_slug)
    
    if ctx.tier == PermissionTier.SUPER_USER:
        # Full access
    elif ctx.can_view_all_department_data:
        # Department head - no employee filter
    else:
        # Regular user - apply employee_id filter
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Literal, List
from enum import Enum
from dotenv import load_dotenv
from supabase import create_client, Client
import jwt

load_dotenv()


# =============================================================================
# ENUMS & TYPES
# =============================================================================

class PermissionTier(Enum):
    USER = 1            # Tier 1: Regular employee
    DEPT_HEAD = 2       # Tier 2: Department head
    SUPER_USER = 3      # Tier 3: Owner/admin


class DataSourceType(Enum):
    DIRECT_SQL = "direct_sql"
    ETL = "etl"
    API = "api"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Tenant:
    id: str
    name: str
    slug: str
    data_source_type: str
    connection_config: dict
    features: dict
    active: bool


@dataclass
class Department:
    id: str
    slug: str
    name: str
    config: dict  # AI personality, enabled features, etc.


@dataclass
class DataConnection:
    """Everything needed to query tenant data"""
    tenant_id: str
    source_type: str
    sql_server: Optional[str] = None
    sql_database: Optional[str] = None
    sql_username: Optional[str] = None
    sql_password: Optional[str] = None
    supabase_schema: Optional[str] = None


@dataclass
class AuthenticatedUser:
    """User info from Supabase JWT"""
    id: str
    email: str
    jwt_role: str  # 'authenticated', 'anon', etc.


@dataclass
class UserContext:
    """
    Complete context for serving a user request.
    This is the main object your API endpoints will use.
    """
    # Identity
    user: AuthenticatedUser
    tenant: Tenant
    
    # Permission tier
    tier: PermissionTier
    role: str  # Raw role string: 'user', 'dept_head', 'super_user'
    
    # Department (None for super_users who aren't dept-specific)
    department: Optional[Department]
    
    # Employee ID for data filtering (e.g., 'JA' for Jafflerbach)
    employee_id: Optional[str]
    
    # Granular permissions (for future fine-tuning)
    permissions: dict = field(default_factory=dict)
    
    # Content to inject into AI prompts
    context_content: List[str] = field(default_factory=list)
    
    # Convenience flags
    @property
    def can_view_all_department_data(self) -> bool:
        """Dept heads and super users see all data (no employee filter)"""
        return self.tier.value >= PermissionTier.DEPT_HEAD.value
    
    @property
    def can_manage_department_users(self) -> bool:
        """Dept heads can view users in their dept, super users can edit"""
        return self.tier.value >= PermissionTier.DEPT_HEAD.value
    
    @property
    def can_manage_all_users(self) -> bool:
        """Only super users can add/remove users and assign dept heads"""
        return self.tier == PermissionTier.SUPER_USER
    
    @property
    def can_access_admin_portal(self) -> bool:
        """Dept heads get limited admin, super users get full admin"""
        return self.tier.value >= PermissionTier.DEPT_HEAD.value
    
    @property
    def is_super_user(self) -> bool:
        return self.tier == PermissionTier.SUPER_USER
    
    def has_feature(self, feature: str) -> bool:
        """Check if user's department or tenant has a feature enabled"""
        # Super users have all features
        if self.is_super_user:
            return True
        
        # Check department config first
        if self.department and feature in self.department.config.get("features", []):
            return True
        
        # Fall back to tenant-level features
        return self.tenant.features.get(feature, False)
    
    def get_data_filter(self) -> dict:
        """
        Returns filter dict to apply to data queries.
        Empty dict = no filter (see everything)
        """
        if self.can_view_all_department_data:
            return {}
        
        if self.employee_id:
            return {"sales_rep_id": self.employee_id}
        
        return {}


# =============================================================================
# TENANT SERVICE
# =============================================================================

class TenantService:
    def __init__(self):
        self.supabase: Client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        self.jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        
        # Caches
        self._tenant_cache: dict[str, Tenant] = {}
        self._department_cache: dict[str, Department] = {}
    
    # -------------------------------------------------------------------------
    # JWT Verification
    # -------------------------------------------------------------------------
    
    def verify_token(self, token: str) -> Optional[AuthenticatedUser]:
        """Verify Supabase JWT and extract user info"""
        if not token:
            return None
        
        if token.startswith("Bearer "):
            token = token[7:]
        
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
            
            return AuthenticatedUser(
                id=payload.get("sub"),
                email=payload.get("email", ""),
                jwt_role=payload.get("role", "authenticated"),
            )
        except jwt.ExpiredSignatureError:
            print("[Auth] Token expired")
            return None
        except jwt.InvalidTokenError as e:
            print(f"[Auth] Invalid token: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # Tenant Lookups
    # -------------------------------------------------------------------------
    
    async def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        if slug in self._tenant_cache:
            return self._tenant_cache[slug]
        
        response = self.supabase.table("tenants").select("*").eq("slug", slug).eq("active", True).execute()
        
        if not response.data:
            return None
        
        row = response.data[0]
        tenant = Tenant(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            data_source_type=row["data_source_type"],
            connection_config=row["connection_config"] or {},
            features=row["features"] or {},
            active=row["active"]
        )
        
        self._tenant_cache[slug] = tenant
        return tenant
    
    # -------------------------------------------------------------------------
    # User Context Resolution (THE MAIN METHOD)
    # -------------------------------------------------------------------------
    
    async def get_user_context(
        self,
        authorization: Optional[str],
        tenant_slug: Optional[str]
    ) -> UserContext:
        """
        Master method: Authenticate user and build complete context.
        
        This is what your API endpoints call.
        """
        # 1. Verify JWT
        user = self.verify_token(authorization)
        if not user:
            raise PermissionError("Invalid or expired authentication token")
        
        # 2. Get user's tenant mapping with department
        if not tenant_slug:
            # Get first available tenant
            response = self.supabase.table("user_tenants").select(
                "*, tenants!inner(*), tenant_departments(*)"
            ).eq("user_id", user.id).limit(1).execute()
        else:
            response = self.supabase.table("user_tenants").select(
                "*, tenants!inner(*), tenant_departments(*)"
            ).eq("user_id", user.id).eq("tenants.slug", tenant_slug).execute()
        
        if not response.data:
            raise PermissionError(f"User does not have access to tenant: {tenant_slug or 'any'}")
        
        row = response.data[0]
        tenant_data = row["tenants"]
        dept_data = row.get("tenant_departments")
        
        # 3. Build Tenant object
        tenant = Tenant(
            id=tenant_data["id"],
            name=tenant_data["name"],
            slug=tenant_data["slug"],
            data_source_type=tenant_data["data_source_type"],
            connection_config=tenant_data["connection_config"] or {},
            features=tenant_data["features"] or {},
            active=tenant_data["active"]
        )
        
        # 4. Build Department object (if assigned)
        department = None
        if dept_data:
            department = Department(
                id=dept_data["id"],
                slug=dept_data["slug"],
                name=dept_data["name"],
                config=dept_data.get("config") or {}
            )
        
        # 5. Determine permission tier
        role = row.get("role", "user")
        tier = self._resolve_tier(role)
        
        # 6. Load context content (department manuals, etc.)
        context_content = await self._load_context_content(user.id, department, tier)
        
        # 7. Build and return UserContext
        return UserContext(
            user=user,
            tenant=tenant,
            tier=tier,
            role=role,
            department=department,
            employee_id=row.get("employee_id"),
            permissions=row.get("permissions") or {},
            context_content=context_content,
        )
    
    def _resolve_tier(self, role: str) -> PermissionTier:
        """Map role string to PermissionTier enum"""
        role_map = {
            "user": PermissionTier.USER,
            "readonly": PermissionTier.USER,
            "dept_head": PermissionTier.DEPT_HEAD,
            "department_head": PermissionTier.DEPT_HEAD,
            "super_user": PermissionTier.SUPER_USER,
            "admin": PermissionTier.SUPER_USER,
            "owner": PermissionTier.SUPER_USER,
        }
        return role_map.get(role.lower(), PermissionTier.USER)
    
    async def _load_context_content(
        self,
        user_id: str,
        department: Optional[Department],
        tier: PermissionTier
    ) -> List[str]:
        """Load manuals/context docs to inject into AI prompts"""
        content = []
        
        # Super users get a general overview, not all manuals
        if tier == PermissionTier.SUPER_USER:
            response = self.supabase.table("department_content").select(
                "content, title"
            ).eq("content_type", "executive_summary").eq("active", True).execute()
            
            content = [f"# {c['title']}\n{c['content']}" for c in response.data]
            return content
        
        # Regular users and dept heads get their department's content
        if department:
            response = self.supabase.table("department_content").select(
                "content, title, content_type"
            ).eq("department_id", department.id).eq("active", True).execute()
            
            # Sort: manuals first, then prompts, then FAQs
            type_order = {"manual": 0, "prompt_context": 1, "faq": 2}
            sorted_content = sorted(
                response.data,
                key=lambda x: type_order.get(x.get("content_type", ""), 99)
            )
            
            content = [f"# {c['title']}\n{c['content']}" for c in sorted_content]
        
        return content
    
    # -------------------------------------------------------------------------
    # Data Connection
    # -------------------------------------------------------------------------
    
    def get_data_connection(self, tenant: Tenant) -> DataConnection:
        """Get database connection details for a tenant"""
        if tenant.data_source_type == "direct_sql":
            env_prefix = tenant.slug.upper()
            
            return DataConnection(
                tenant_id=tenant.id,
                source_type="direct_sql",
                sql_server=os.getenv(f"{env_prefix}_SQL_SERVER"),
                sql_database=os.getenv(f"{env_prefix}_SQL_DATABASE"),
                sql_username=os.getenv(f"{env_prefix}_SQL_USERNAME"),
                sql_password=os.getenv(f"{env_prefix}_SQL_PASSWORD"),
            )
        
        elif tenant.data_source_type == "etl":
            return DataConnection(
                tenant_id=tenant.id,
                source_type="etl",
                supabase_schema=f"tenant_{tenant.slug}",
            )
        
        else:
            return DataConnection(
                tenant_id=tenant.id,
                source_type=tenant.data_source_type,
            )
    
    # -------------------------------------------------------------------------
    # Admin Functions (Tier 3 only)
    # -------------------------------------------------------------------------
    
    async def list_tenant_users(
        self,
        ctx: UserContext,
        department_slug: Optional[str] = None
    ) -> List[dict]:
        """
        List users in tenant. Filtered by department for dept heads.
        
        Returns list of {email, role, department, employee_id}
        """
        if not ctx.can_manage_department_users:
            raise PermissionError("Insufficient permissions to view users")
        
        query = self.supabase.table("user_tenants").select(
            "role, employee_id, auth_users:user_id(email), tenant_departments(slug, name)"
        ).eq("tenant_id", ctx.tenant.id)
        
        # Dept heads can only see their own department
        if ctx.tier == PermissionTier.DEPT_HEAD and ctx.department:
            query = query.eq("department_id", ctx.department.id)
        elif department_slug:
            # Super user filtering by department
            dept_response = self.supabase.table("tenant_departments").select("id").eq("slug", department_slug).execute()
            if dept_response.data:
                query = query.eq("department_id", dept_response.data[0]["id"])
        
        response = query.execute()
        
        return [
            {
                "email": row.get("auth_users", {}).get("email"),
                "role": row["role"],
                "employee_id": row.get("employee_id"),
                "department": row.get("tenant_departments", {}).get("slug") if row.get("tenant_departments") else None,
            }
            for row in response.data
        ]
    
    async def add_user_to_tenant(
        self,
        ctx: UserContext,
        user_email: str,
        department_slug: str,
        role: str = "user",
        employee_id: Optional[str] = None
    ) -> bool:
        """
        Add a user to tenant.

        Permissions:
        - Super users: can add users to any department with any role
        - Dept heads: can add users to THEIR department only, role='user' only
        - Users: cannot add anyone

        The user must already exist in Supabase Auth (they need to sign up first).
        """
        # Validate email domain (Driscoll emails only for dept heads)
        if ctx.tier == PermissionTier.DEPT_HEAD:
            if not user_email.lower().endswith("@driscollfoods.com"):
                raise PermissionError("Department heads can only add @driscollfoods.com emails")

        # Check permissions
        if ctx.tier == PermissionTier.SUPER_USER:
            # Super users can do anything
            pass
        elif ctx.tier == PermissionTier.DEPT_HEAD:
            # Dept heads can only add to their own department
            if not ctx.department or ctx.department.slug != department_slug:
                raise PermissionError("Department heads can only add users to their own department")
            # Dept heads can only assign 'user' role
            if role != "user":
                raise PermissionError("Department heads can only assign 'user' role")
        else:
            raise PermissionError("Insufficient permissions to add users")

        # Look up user by email
        user_response = self.supabase.auth.admin.list_users()
        target_user = None
        for u in user_response:
            if u.email == user_email:
                target_user = u
                break

        if not target_user:
            raise ValueError(f"User not found in auth system: {user_email}")

        # Look up department
        dept_response = self.supabase.table("tenant_departments").select("id").eq(
            "tenant_id", ctx.tenant.id
        ).eq("slug", department_slug).execute()

        if not dept_response.data:
            raise ValueError(f"Department not found: {department_slug}")

        dept_id = dept_response.data[0]["id"]

        # Insert user_tenant mapping
        self.supabase.table("user_tenants").upsert({
            "user_id": target_user.id,
            "tenant_id": ctx.tenant.id,
            "department_id": dept_id,
            "role": role,
            "employee_id": employee_id,
        }).execute()

        return True
    
    async def update_user_role(
        self,
        ctx: UserContext,
        user_email: str,
        new_role: str
    ) -> bool:
        """
        Change a user's role. Super users only.
        Valid roles: 'user', 'dept_head', 'super_user'
        """
        if not ctx.can_manage_all_users:
            raise PermissionError("Only super users can change roles")
        
        if new_role not in ("user", "dept_head", "super_user"):
            raise ValueError(f"Invalid role: {new_role}")
        
        # Look up user
        user_response = self.supabase.rpc("get_user_by_email", {"email": user_email}).execute()
        if not user_response.data:
            raise ValueError(f"User not found: {user_email}")
        
        user_id = user_response.data[0]["id"]
        
        # Update role
        self.supabase.table("user_tenants").update({
            "role": new_role
        }).eq("user_id", user_id).eq("tenant_id", ctx.tenant.id).execute()
        
        return True
    
    async def remove_user_from_tenant(
        self,
        ctx: UserContext,
        user_email: str
    ) -> bool:
        """
        Remove a user's access to tenant.

        Permissions:
        - Super users: can remove anyone
        - Dept heads: can remove users from THEIR department only (not dept_heads or super_users)
        - Users: cannot remove anyone
        """
        if not ctx.can_manage_department_users:
            raise PermissionError("Insufficient permissions to remove users")

        # Look up user's current assignment
        user_response = self.supabase.rpc("get_user_by_email", {"email": user_email}).execute()
        if not user_response.data:
            raise ValueError(f"User not found: {user_email}")

        user_id = user_response.data[0]["id"]

        # Get the user's tenant mapping to check their role and department
        mapping_response = self.supabase.table("user_tenants").select(
            "role, department_id"
        ).eq("user_id", user_id).eq("tenant_id", ctx.tenant.id).execute()

        if not mapping_response.data:
            raise ValueError(f"User not in this tenant: {user_email}")

        target_mapping = mapping_response.data[0]
        target_role = target_mapping.get("role", "user")
        target_dept_id = target_mapping.get("department_id")

        # Dept heads have restrictions
        if ctx.tier == PermissionTier.DEPT_HEAD:
            # Can only remove from their own department
            if not ctx.department or target_dept_id != ctx.department.id:
                raise PermissionError("Department heads can only remove users from their own department")
            # Cannot remove dept_heads or super_users
            if target_role in ("dept_head", "super_user", "admin", "owner"):
                raise PermissionError("Department heads cannot remove other department heads or admins")

        # Delete mapping
        self.supabase.table("user_tenants").delete().eq(
            "user_id", user_id
        ).eq("tenant_id", ctx.tenant.id).execute()

        return True
    
    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------
    
    def clear_cache(self):
        self._tenant_cache.clear()
        self._department_cache.clear()


# =============================================================================
# SINGLETON & CONVENIENCE FUNCTIONS
# =============================================================================

_tenant_service: Optional[TenantService] = None

def get_tenant_service() -> TenantService:
    global _tenant_service
    if _tenant_service is None:
        _tenant_service = TenantService()
    return _tenant_service


async def get_user_context(
    authorization: Optional[str],
    tenant_slug: Optional[str] = None
) -> UserContext:
    """
    Main entry point for API endpoints.
    
    Usage:
        @app.get("/api/credit")
        async def get_credit(
            authorization: str = Header(None),
            x_tenant_slug: str = Header(None, alias="X-Tenant-Slug")
        ):
            ctx = await get_user_context(authorization, x_tenant_slug)
            
            # Check permissions
            if not ctx.has_feature("credit_lookup"):
                raise HTTPException(403, "Feature not available")
            
            # Get data with appropriate filters
            filters = ctx.get_data_filter()  # {'sales_rep_id': 'JA'} for Jafflerbach
            
            # Build AI prompt with department content
            system_prompt = BASE_PROMPT + "\\n".join(ctx.context_content)
    """
    svc = get_tenant_service()
    return await svc.get_user_context(authorization, tenant_slug)


# =============================================================================
# DRISCOLL CONVENIENCE (backwards compatibility)
# =============================================================================

async def get_driscoll_connection() -> DataConnection:
    """Legacy helper for transition period"""
    svc = get_tenant_service()
    tenant = await svc.get_tenant_by_slug("driscoll")
    if not tenant:
        raise ValueError("Driscoll tenant not found")
    return svc.get_data_connection(tenant)
