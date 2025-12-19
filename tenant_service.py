"""
Tenant Service - Direct Azure PostgreSQL Implementation

Routes authenticated users to their data sources with 3-tier permission system.
Replaces Supabase with direct psycopg2 connection to Azure PostgreSQL.

Tier 1: User
    - Sees only their department's content
    - Data filtered to their employee_id
    
Tier 2: Department Head
    - Sees their department's content
    - Sees ALL data in their department (no employee filter)
    - Can manage users in their department
    
Tier 3: Super User
    - Sees everything across all departments
    - Full admin access

Usage:
    from tenant_service import TenantService, get_user_context
    
    # Simple lookup
    tenant_svc = TenantService()
    tenant = tenant_svc.get_tenant_by_slug("driscoll")
    
    # Full context for API requests
    ctx = get_user_context(authorization, tenant_slug)
    content = ctx.get_department_content()  # Returns manuals for user's dept
"""

import os
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


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
# ENUMS
# =============================================================================

class PermissionTier(Enum):
    USER = 1            # Tier 1: Regular employee
    DEPT_HEAD = 2       # Tier 2: Department head
    SUPER_USER = 3      # Tier 3: Owner/admin


class DataSourceType(Enum):
    DIRECT_SQL = "direct_sql"   # Driscoll - direct SQL Server access
    ETL = "etl"                 # Other clients - data in our PostgreSQL
    API = "api"                 # Future: real-time API integration


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
    description: Optional[str] = None
    config: dict = field(default_factory=dict)


@dataclass 
class DataConnection:
    """Returned to callers - contains everything needed to query tenant data"""
    tenant_id: str
    source_type: str
    # For direct_sql (Driscoll SQL Server)
    sql_server: Optional[str] = None
    sql_database: Optional[str] = None
    sql_username: Optional[str] = None
    sql_password: Optional[str] = None
    # For etl (data in our PostgreSQL)
    pg_schema: Optional[str] = None


@dataclass
class UserContext:
    """
    Complete context for serving a user request.
    This is the main object your API endpoints will use.
    """
    # Identity
    user_id: Optional[str]
    user_email: Optional[str]
    tenant: Tenant
    
    # Permission tier
    tier: PermissionTier
    role: str  # Raw role string: 'user', 'dept_head', 'super_user'
    
    # Department (None for super_users viewing all)
    department: Optional[Department]
    
    # Employee ID for data filtering (e.g., 'JA' for Jafflerbach)
    employee_id: Optional[str] = None
    
    # Loaded content for AI prompts
    _content_cache: List[str] = field(default_factory=list)
    
    # Convenience flags
    @property
    def can_view_all_department_data(self) -> bool:
        """Dept heads and super users see all data (no employee filter)"""
        return self.tier.value >= PermissionTier.DEPT_HEAD.value
    
    @property
    def can_manage_users(self) -> bool:
        """Dept heads can manage their dept, super users can manage all"""
        return self.tier.value >= PermissionTier.DEPT_HEAD.value
    
    @property
    def is_super_user(self) -> bool:
        return self.tier == PermissionTier.SUPER_USER
    
    def has_feature(self, feature: str) -> bool:
        """Check if user's tenant has a feature enabled"""
        if self.is_super_user:
            return True
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
# DATABASE HELPERS
# =============================================================================

@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_db_cursor(conn=None, dict_cursor=True):
    """Context manager for database cursors."""
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
# TENANT SERVICE
# =============================================================================

class TenantService:
    def __init__(self):
        # Caches to avoid repeated DB hits
        self._tenant_cache: Dict[str, Tenant] = {}
        self._department_cache: Dict[str, Department] = {}
    
    # -------------------------------------------------------------------------
    # Tenant Lookups
    # -------------------------------------------------------------------------
    
    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Look up tenant config by slug (e.g., 'driscoll')"""
        if slug in self._tenant_cache:
            return self._tenant_cache[slug]
        
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT id, name, slug, data_source_type, 
                       connection_config, features, active
                FROM {SCHEMA}.tenants 
                WHERE slug = %s AND active = TRUE
            """, (slug,))
            row = cur.fetchone()
        
        if not row:
            return None
        
        tenant = Tenant(
            id=str(row["id"]),
            name=row["name"],
            slug=row["slug"],
            data_source_type=row["data_source_type"],
            connection_config=row["connection_config"] or {},
            features=row["features"] or {},
            active=row["active"]
        )
        
        self._tenant_cache[slug] = tenant
        return tenant
    
    def get_tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """Look up tenant by UUID"""
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT id, name, slug, data_source_type,
                       connection_config, features, active
                FROM {SCHEMA}.tenants 
                WHERE id = %s AND active = TRUE
            """, (tenant_id,))
            row = cur.fetchone()
        
        if not row:
            return None
        
        return Tenant(
            id=str(row["id"]),
            name=row["name"],
            slug=row["slug"],
            data_source_type=row["data_source_type"],
            connection_config=row["connection_config"] or {},
            features=row["features"] or {},
            active=row["active"]
        )
    
    # -------------------------------------------------------------------------
    # Department Lookups
    # -------------------------------------------------------------------------
    
    def get_department_by_slug(self, slug: str) -> Optional[Department]:
        """Look up department by slug"""
        cache_key = slug
        if cache_key in self._department_cache:
            return self._department_cache[cache_key]
        
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT id, slug, name, description
                FROM {SCHEMA}.departments 
                WHERE slug = %s AND active = TRUE
            """, (slug,))
            row = cur.fetchone()
        
        if not row:
            return None
        
        dept = Department(
            id=str(row["id"]),
            slug=row["slug"],
            name=row["name"],
            description=row.get("description")
        )
        
        self._department_cache[cache_key] = dept
        return dept
    
    def get_department_by_id(self, dept_id: str) -> Optional[Department]:
        """Look up department by UUID"""
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT id, slug, name, description
                FROM {SCHEMA}.departments 
                WHERE id = %s AND active = TRUE
            """, (dept_id,))
            row = cur.fetchone()
        
        if not row:
            return None
        
        return Department(
            id=str(row["id"]),
            slug=row["slug"],
            name=row["name"],
            description=row.get("description")
        )
    
    def list_departments(self) -> List[Department]:
        """List all active departments"""
        with get_db_cursor() as cur:
            cur.execute(f"""
                SELECT id, slug, name, description
                FROM {SCHEMA}.departments 
                WHERE active = TRUE
                ORDER BY name
            """)
            rows = cur.fetchall()
        
        return [
            Department(
                id=str(row["id"]),
                slug=row["slug"],
                name=row["name"],
                description=row.get("description")
            )
            for row in rows
        ]
    
    # -------------------------------------------------------------------------
    # Department Content
    # -------------------------------------------------------------------------
    
    def get_department_content(
        self, 
        department_id: str,
        content_type: Optional[str] = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all content for a department (manuals, procedures, etc.)
        
        Returns list of dicts with: id, title, content, content_type, version
        """
        with get_db_cursor() as cur:
            query = f"""
                SELECT id, title, content, content_type, version, updated_at
                FROM {SCHEMA}.department_content 
                WHERE department_id = %s
            """
            params = [department_id]
            
            if active_only:
                query += " AND active = TRUE"
            
            if content_type:
                query += " AND content_type = %s"
                params.append(content_type)
            
            query += " ORDER BY title"
            
            cur.execute(query, params)
            rows = cur.fetchall()
        
        return [dict(row) for row in rows]
    
    def get_all_content_for_context(
        self,
        department_slug: Optional[str] = None
    ) -> str:
        """
        Get all content formatted for LLM context stuffing.
        
        If department_slug is provided, returns only that department's content.
        If None, returns all content (for super users).
        
        Returns a single string ready to inject into system prompt.
        """
        with get_db_cursor() as cur:
            if department_slug:
                cur.execute(f"""
                    SELECT d.name as dept_name, dc.title, dc.content
                    FROM {SCHEMA}.department_content dc
                    JOIN {SCHEMA}.departments d ON dc.department_id = d.id
                    WHERE d.slug = %s AND dc.active = TRUE AND d.active = TRUE
                    ORDER BY d.name, dc.title
                """, (department_slug,))
            else:
                cur.execute(f"""
                    SELECT d.name as dept_name, dc.title, dc.content
                    FROM {SCHEMA}.department_content dc
                    JOIN {SCHEMA}.departments d ON dc.department_id = d.id
                    WHERE dc.active = TRUE AND d.active = TRUE
                    ORDER BY d.name, dc.title
                """)
            
            rows = cur.fetchall()
        
        if not rows:
            return ""
        
        # Format for context stuffing
        parts = ["=== COMPANY KNOWLEDGE BASE ===\n"]
        current_dept = None
        
        for row in rows:
            if row["dept_name"] != current_dept:
                current_dept = row["dept_name"]
                parts.append(f"\n## {current_dept} Department\n")
            
            parts.append(f"\n### {row['title']}\n")
            parts.append(row["content"])
            parts.append("\n")
        
        return "\n".join(parts)
    
    # -------------------------------------------------------------------------
    # Data Connection
    # -------------------------------------------------------------------------
    
    def get_data_connection(self, tenant: Tenant) -> DataConnection:
        """
        Returns connection details for a tenant's data source.
        
        For direct_sql (Driscoll): Returns SQL Server credentials from env vars
        For etl: Returns PostgreSQL schema name where their data lives
        """
        if tenant.data_source_type == "direct_sql":
            # SECURITY: Real credentials come from env vars, not DB
            env_prefix = tenant.slug.upper()  # e.g., "DRISCOLL"
            
            return DataConnection(
                tenant_id=tenant.id,
                source_type="direct_sql",
                sql_server=os.getenv(f"{env_prefix}_SQL_SERVER"),
                sql_database=os.getenv(f"{env_prefix}_SQL_DATABASE"),
                sql_username=os.getenv(f"{env_prefix}_SQL_USERNAME"),
                sql_password=os.getenv(f"{env_prefix}_SQL_PASSWORD"),
            )
        
        elif tenant.data_source_type == "etl":
            # Data lives in our PostgreSQL, in a tenant-specific schema
            return DataConnection(
                tenant_id=tenant.id,
                source_type="etl",
                pg_schema=f"tenant_{tenant.slug}",
            )
        
        elif tenant.data_source_type == "api":
            return DataConnection(
                tenant_id=tenant.id,
                source_type="api",
            )
        
        else:
            raise ValueError(f"Unknown data source type: {tenant.data_source_type}")
    
    # -------------------------------------------------------------------------
    # User Context Builder
    # -------------------------------------------------------------------------
    
    def build_user_context(
        self,
        tenant_slug: str,
        department_slug: Optional[str] = None,
        role: str = "user",
        employee_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None
    ) -> UserContext:
        """
        Build a UserContext for API requests.
        
        For now, this is simplified - in production you'd verify JWT tokens
        and look up user assignments from the database.
        
        Args:
            tenant_slug: Which tenant (e.g., 'driscoll')
            department_slug: Which department, or None for super_user
            role: 'user', 'dept_head', or 'super_user'
            employee_id: For data filtering (e.g., 'JA')
            user_id: Optional user UUID
            user_email: Optional user email
        """
        tenant = self.get_tenant_by_slug(tenant_slug)
        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_slug}")
        
        # Determine permission tier
        if role == "super_user":
            tier = PermissionTier.SUPER_USER
        elif role == "dept_head":
            tier = PermissionTier.DEPT_HEAD
        else:
            tier = PermissionTier.USER
        
        # Get department if specified
        department = None
        if department_slug:
            department = self.get_department_by_slug(department_slug)
        
        return UserContext(
            user_id=user_id,
            user_email=user_email,
            tenant=tenant,
            tier=tier,
            role=role,
            department=department,
            employee_id=employee_id
        )
    
    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------
    
    def clear_cache(self):
        """Clear all caches (call after config changes)"""
        self._tenant_cache.clear()
        self._department_cache.clear()
    
    def has_feature(self, tenant: Tenant, feature: str) -> bool:
        """Check if tenant has a feature enabled"""
        return tenant.features.get(feature, False)


# =============================================================================
# SINGLETON & CONVENIENCE FUNCTIONS
# =============================================================================

_tenant_service: Optional[TenantService] = None


def get_tenant_service() -> TenantService:
    """Get or create the tenant service singleton"""
    global _tenant_service
    if _tenant_service is None:
        _tenant_service = TenantService()
    return _tenant_service


def get_user_context(
    tenant_slug: str,
    department_slug: Optional[str] = None,
    role: str = "user",
    employee_id: Optional[str] = None
) -> UserContext:
    """
    Convenience function to build user context.
    
    Usage in FastAPI:
        @app.get("/api/chat")
        async def chat(
            x_tenant: str = Header(alias="X-Tenant-Slug"),
            x_department: str = Header(None, alias="X-Department-Slug"),
            x_role: str = Header("user", alias="X-Role")
        ):
            ctx = get_user_context(x_tenant, x_department, x_role)
            content = get_tenant_service().get_all_content_for_context(ctx.department.slug)
            # ... build prompt with content
    """
    svc = get_tenant_service()
    return svc.build_user_context(
        tenant_slug=tenant_slug,
        department_slug=department_slug,
        role=role,
        employee_id=employee_id
    )


# =============================================================================
# DRISCOLL CONVENIENCE (backwards compatibility)
# =============================================================================

def get_driscoll_connection() -> DataConnection:
    """
    Convenience function for the transition period.
    Returns SQL Server connection details for Driscoll.
    """
    svc = get_tenant_service()
    tenant = svc.get_tenant_by_slug("driscoll")
    if not tenant:
        raise ValueError("Driscoll tenant not found in database")
    return svc.get_data_connection(tenant)


def get_driscoll_content(department_slug: Optional[str] = None) -> str:
    """
    Get Driscoll manual content for context stuffing.
    
    Args:
        department_slug: Optional - 'warehouse', 'sales', 'credit', etc.
                        If None, returns ALL content (for super users)
    
    Returns:
        Formatted string ready for LLM system prompt
    """
    svc = get_tenant_service()
    return svc.get_all_content_for_context(department_slug)


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_tenant_tables():
    """
    Create the tenants table if it doesn't exist.
    Safe to run multiple times.
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # Create tenants table
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.tenants (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(100) NOT NULL,
                slug VARCHAR(50) UNIQUE NOT NULL,
                data_source_type VARCHAR(20) DEFAULT 'etl',
                connection_config JSONB DEFAULT '{{}}'::jsonb,
                features JSONB DEFAULT '{{}}'::jsonb,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Seed Driscoll tenant
        cur.execute(f"""
            INSERT INTO {SCHEMA}.tenants (name, slug, data_source_type, features)
            VALUES (
                'Driscoll Foods', 
                'driscoll', 
                'direct_sql',
                '{{"credit_lookup": true, "memory_pipeline": false}}'::jsonb
            )
            ON CONFLICT (slug) DO NOTHING;
        """)
        
        conn.commit()
        cur.close()
        
        print(f"[OK] Tenant tables initialized in {SCHEMA} schema")


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if "--init" in sys.argv:
        print("Initializing tenant tables...")
        init_tenant_tables()
        sys.exit(0)
    
    print("Tenant Service - Direct PostgreSQL")
    print("=" * 60)
    
    svc = get_tenant_service()
    
    # Test tenant lookup
    print("\n[TEST] Looking up Driscoll tenant...")
    tenant = svc.get_tenant_by_slug("driscoll")
    if tenant:
        print(f"  Found: {tenant.name} ({tenant.slug})")
        print(f"  Data source: {tenant.data_source_type}")
        print(f"  Features: {tenant.features}")
    else:
        print("  Not found - run with --init to create")
    
    # Test department lookup
    print("\n[TEST] Listing departments...")
    departments = svc.list_departments()
    for dept in departments:
        print(f"  - {dept.name} ({dept.slug})")
    
    # Test content retrieval
    print("\n[TEST] Getting warehouse content...")
    content = svc.get_all_content_for_context("warehouse")
    if content:
        print(f"  Content length: {len(content):,} chars")
        print(f"  Preview: {content[:200]}...")
    else:
        print("  No content found")
    
    print("\n[TEST] Getting ALL content (super user view)...")
    all_content = svc.get_all_content_for_context(None)
    if all_content:
        print(f"  Total content length: {len(all_content):,} chars")
    else:
        print("  No content found")
    
    print("\n" + "=" * 60)
    print("Tests complete!")