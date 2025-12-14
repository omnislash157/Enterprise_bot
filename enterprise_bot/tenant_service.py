"""
Tenant Service - Routes authenticated users to their data sources.

This is the bridge between:
- Auth (Azure AD) → "who is this person, what tenant?"
- Data (SQL Server / Supabase) → "here's their data connection"

Usage:
    from tenant_service import TenantService
    
    tenant_svc = TenantService()
    tenant = await tenant_svc.get_tenant_by_slug("driscoll")
    conn = tenant_svc.get_data_connection(tenant)
"""

import os
from dataclasses import dataclass
from typing import Optional, Literal
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


@dataclass
class Tenant:
    id: str
    name: str
    slug: str
    data_source_type: Literal["direct_sql", "etl", "api"]
    connection_config: dict
    features: dict
    active: bool


@dataclass 
class DataConnection:
    """Returned to callers - contains everything needed to query tenant data"""
    tenant_id: str
    source_type: str
    # For direct_sql
    sql_server: Optional[str] = None
    sql_database: Optional[str] = None
    sql_username: Optional[str] = None
    sql_password: Optional[str] = None
    # For etl (data lives in your Supabase)
    supabase_schema: Optional[str] = None


class TenantService:
    def __init__(self):
        self.supabase: Client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        # Cache tenants to avoid repeated lookups
        self._cache: dict[str, Tenant] = {}
    
    async def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Look up tenant config by slug (e.g., 'driscoll')"""
        # Check cache first
        if slug in self._cache:
            return self._cache[slug]
        
        # Query Supabase
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
        
        # Cache it
        self._cache[slug] = tenant
        return tenant
    
    async def get_tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """Look up tenant by UUID"""
        response = self.supabase.table("tenants").select("*").eq("id", tenant_id).eq("active", True).execute()
        
        if not response.data:
            return None
        
        row = response.data[0]
        return Tenant(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            data_source_type=row["data_source_type"],
            connection_config=row["connection_config"] or {},
            features=row["features"] or {},
            active=row["active"]
        )
    
    def get_data_connection(self, tenant: Tenant) -> DataConnection:
        """
        Returns connection details for a tenant's data source.
        
        For direct_sql: Returns SQL Server credentials (from env vars, NOT from DB)
        For etl: Returns Supabase schema name where their data lives
        """
        if tenant.data_source_type == "direct_sql":
            # SECURITY: Real credentials come from env vars, not Supabase
            # The connection_config in DB just tells us which env vars to use
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
            # Data lives in your Supabase, in a tenant-specific schema
            return DataConnection(
                tenant_id=tenant.id,
                source_type="etl",
                supabase_schema=f"tenant_{tenant.slug}",  # e.g., "tenant_acme"
            )
        
        elif tenant.data_source_type == "api":
            # Future: real-time API integration
            return DataConnection(
                tenant_id=tenant.id,
                source_type="api",
            )
        
        else:
            raise ValueError(f"Unknown data source type: {tenant.data_source_type}")
    
    def has_feature(self, tenant: Tenant, feature: str) -> bool:
        """Check if tenant has a feature enabled (e.g., 'credit_pipeline')"""
        return tenant.features.get(feature, False)
    
    def clear_cache(self):
        """Clear tenant cache (call after config changes)"""
        self._cache.clear()


# Singleton instance
_tenant_service: Optional[TenantService] = None

def get_tenant_service() -> TenantService:
    """Get or create the tenant service singleton"""
    global _tenant_service
    if _tenant_service is None:
        _tenant_service = TenantService()
    return _tenant_service


# === Helper for your existing credit.py ===

async def get_driscoll_connection() -> DataConnection:
    """
    Convenience function for the transition period.
    Your existing code can call this instead of hardcoding connection details.
    """
    svc = get_tenant_service()
    tenant = await svc.get_tenant_by_slug("driscoll")
    if not tenant:
        raise ValueError("Driscoll tenant not found in database")
    return svc.get_data_connection(tenant)                                                                                          