"""
Tenant Resolution Middleware
Resolves domain -> tenant on every request, injects into request.state

Priority:
1. Database lookup (enterprise tenants)
2. YAML fallback for personal tier (cogzy.ai, localhost)
"""
from fastapi import Request, HTTPException
from typing import Optional
import asyncpg
import logging

from .enterprise_tenant import TenantContext
from .tenant_loader import resolve_tenant as resolve_yaml_tenant

logger = logging.getLogger(__name__)

# Personal tier domains that use YAML config instead of DB
PERSONAL_DOMAINS = {
    "cogzy.ai",
    "localhost",
    "127.0.0.1",
    "lucky-love-production.up.railway.app",
}


async def get_tenant_by_domain(domain: str, pool: asyncpg.Pool) -> Optional[dict]:
    """Lookup tenant by domain (exact match or wildcard subdomain)."""
    # Try exact match first
    row = await pool.fetchrow(
        """
        SELECT id, slug, name, domain, azure_tenant_id, azure_client_id,
               azure_client_secret_ref, branding, is_active
        FROM enterprise.tenants
        WHERE domain = $1 AND is_active = true
        """,
        domain
    )

    if row:
        return dict(row)

    # Try subdomain match (*.entintel.com)
    if '.' in domain:
        parts = domain.split('.')
        if len(parts) >= 2:
            base_domain = '.'.join(parts[-2:])  # entintel.com
            row = await pool.fetchrow(
                """
                SELECT id, slug, name, domain, azure_tenant_id, azure_client_id,
                       azure_client_secret_ref, branding, is_active
                FROM enterprise.tenants
                WHERE domain = $1 AND is_active = true
                """,
                f"*.{base_domain}"
            )
            if row:
                result = dict(row)
                # Override slug with subdomain
                result['slug'] = parts[0]
                return result

    return None


def get_personal_tenant(host: str) -> Optional[TenantContext]:
    """Get tenant from YAML config for personal tier domains."""
    try:
        yaml_tenant = resolve_yaml_tenant(host)
        if yaml_tenant:
            tenant_info = yaml_tenant.get("tenant", {})
            branding = yaml_tenant.get("branding", {})
            return TenantContext(
                tenant_id=tenant_info.get("id", "cogzy"),
                department="personal",  # Personal tier has no departments
                slug=tenant_info.get("slug", "cogzy"),
                name=tenant_info.get("name", "Cogzy"),
                domain=host,
                azure_tenant_id=None,
                azure_client_id=None,
                branding=branding,
            )
    except Exception as e:
        logger.error(f"[TENANT] YAML fallback error for {host}: {e}")
    return None


async def tenant_middleware(request: Request, call_next):
    """
    Middleware to resolve tenant from Host header.
    Sets request.state.tenant with TenantContext or None.
    """
    host = request.headers.get("host", "").split(":")[0]  # Remove port

    # Skip for health checks
    if request.url.path in ["/health", "/api/health"]:
        return await call_next(request)

    # Check if this is a personal tier domain first
    if host in PERSONAL_DOMAINS:
        request.state.tenant = get_personal_tenant(host)
        if request.state.tenant:
            logger.debug(f"[TENANT] Personal tier: {host} -> {request.state.tenant.slug}")
        return await call_next(request)

    # Get DB pool from app state for enterprise tenants
    pool = getattr(request.app.state, 'db_pool', None)

    if pool:
        try:
            tenant_data = await get_tenant_by_domain(host, pool)

            if tenant_data:
                request.state.tenant = TenantContext(
                    tenant_id=str(tenant_data['id']),
                    slug=tenant_data['slug'],
                    name=tenant_data['name'],
                    domain=tenant_data['domain'],
                    azure_tenant_id=tenant_data.get('azure_tenant_id'),
                    azure_client_id=tenant_data.get('azure_client_id'),
                    branding=tenant_data.get('branding', {}),
                )
                logger.debug(f"[TENANT] Resolved {host} -> {tenant_data['slug']}")
            else:
                # No tenant found - could be platform domain or unknown
                request.state.tenant = None
                logger.debug(f"[TENANT] No tenant found for {host}")
        except Exception as e:
            logger.error(f"[TENANT] Error resolving tenant for {host}: {e}")
            request.state.tenant = None
    else:
        # DB pool not available - skip tenant resolution
        logger.warning("[TENANT] DB pool not available, skipping tenant resolution")
        request.state.tenant = None

    return await call_next(request)


def get_current_tenant(request: Request) -> TenantContext:
    """Dependency to get current tenant, raises if not found."""
    tenant = getattr(request.state, 'tenant', None)
    if not tenant:
        raise HTTPException(status_code=400, detail="Unknown tenant domain")
    return tenant


def get_optional_tenant(request: Request) -> Optional[TenantContext]:
    """Dependency to get tenant, returns None if not found."""
    return getattr(request.state, 'tenant', None)
