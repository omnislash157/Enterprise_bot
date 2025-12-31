"""
Tenant API Routes

Provides tenant configuration to frontend.
"""

from fastapi import APIRouter, Request
from core.tenant_loader import resolve_tenant

router = APIRouter(prefix="/api/tenant", tags=["tenant"])


@router.get("/config")
async def get_tenant_config(request: Request):
    """
    Return tenant configuration based on request origin.

    Frontend calls this on load to determine:
    - Which auth methods to show
    - What branding to use
    - Which features are enabled
    """
    # Get host from Origin header (CORS) or Host header
    origin = request.headers.get("origin", "")
    if origin:
        # Extract host from origin (https://cogzy.ai -> cogzy.ai)
        host = origin.replace("https://", "").replace("http://", "")
    else:
        host = request.headers.get("host", "cogzy.ai")

    tenant = resolve_tenant(host)

    # Return safe subset (don't expose tenant_id, tables, etc.)
    return {
        "mode": tenant.get("mode", "enterprise"),
        "name": tenant.get("name"),
        "slug": tenant.get("slug"),
        "auth": tenant.get("auth", {}),
        "features": tenant.get("features", {}),
        "branding": tenant.get("branding", {})
    }
