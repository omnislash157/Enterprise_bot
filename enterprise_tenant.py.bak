"""
Enterprise Tenant - Simplified for context-stuffing mode.

No SQL, no filesystem vaults - just tenant context for division-aware docs.

Usage:
    from enterprise_tenant import TenantContext
    
    tenant = TenantContext(
        tenant_id="driscoll",
        division="warehouse",
        zone="night_shift",
        role="user",
    )

Version: 1.0.0 (enterprise-lite)
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class TenantContext:
    """
    Lightweight tenant context for enterprise mode.
    
    Used to scope doc loading and voice selection.
    No SQL dependency in basic tier.
    """
    tenant_id: str          # Company ID (e.g., "driscoll")
    division: str           # User's division (e.g., "warehouse", "hr")
    zone: Optional[str] = None      # Shift/region (e.g., "night_shift", "west_region")
    role: str = "user"      # user | manager | admin
    email: Optional[str] = None     # User's email (for logging)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "division": self.division,
            "zone": self.zone,
            "role": self.role,
            "email": self.email,
        }
    
    @classmethod
    def from_email(cls, email: str, tenant_id: str = "driscoll", default_division: str = "warehouse") -> "TenantContext":
        """Create tenant context from email with division detection."""
        email_lower = email.lower()
        
        # Simple division detection from email
        if "transport" in email_lower or "driver" in email_lower or "dispatch" in email_lower:
            division = "transportation"
        elif "hr" in email_lower or "human" in email_lower:
            division = "hr"
        elif "sales" in email_lower or "account" in email_lower:
            division = "sales"
        elif "ops" in email_lower or "warehouse" in email_lower or "inventory" in email_lower:
            division = "warehouse"
        else:
            division = default_division
        
        return cls(
            tenant_id=tenant_id,
            division=division,
            email=email,
        )


# For backward compatibility with SQL version
class SimpleTenantManager:
    """
    Simple in-memory tenant management for basic tier.
    
    No SQL required - just domain validation.
    """
    
    def __init__(self, allowed_domains: list = None):
        self.allowed_domains = set(d.lower() for d in (allowed_domains or []))
        self._tenants: Dict[str, TenantContext] = {}
    
    def is_allowed(self, email: str) -> bool:
        """Check if email domain is allowed."""
        if not self.allowed_domains:
            return True  # No restrictions
        
        email_lower = email.lower().strip()
        if "@" not in email_lower:
            return False
        
        domain = email_lower.split("@")[1]
        return domain in self.allowed_domains
    
    def get_or_create(self, email: str, tenant_id: str = "driscoll") -> TenantContext:
        """Get or create tenant context for email."""
        email_lower = email.lower().strip()
        
        if email_lower not in self._tenants:
            self._tenants[email_lower] = TenantContext.from_email(
                email=email_lower,
                tenant_id=tenant_id,
            )
        
        return self._tenants[email_lower]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get simple stats."""
        divisions = {}
        for tenant in self._tenants.values():
            divisions[tenant.division] = divisions.get(tenant.division, 0) + 1
        
        return {
            "total_tenants": len(self._tenants),
            "by_division": divisions,
            "allowed_domains": list(self.allowed_domains),
        }


if __name__ == "__main__":
    # Quick test
    tenant = TenantContext.from_email("warehouse_ops@driscollfoods.com")
    print(f"Tenant: {tenant}")
    print(f"Division detected: {tenant.division}")
    
    manager = SimpleTenantManager(allowed_domains=["driscollfoods.com", "gmail.com"])
    print(f"alice@driscollfoods.com allowed: {manager.is_allowed('alice@driscollfoods.com')}")
    print(f"bob@random.com allowed: {manager.is_allowed('bob@random.com')}")
