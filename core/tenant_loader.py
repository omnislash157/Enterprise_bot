"""
Tenant Configuration Loader

Loads tenant configs from YAML files in bot/clients/
Merges with _base.yaml for enterprise clients.
"""

from pathlib import Path
from typing import Optional
import yaml
from functools import lru_cache

CLIENTS_DIR = Path(__file__).parent.parent / "clients"


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base, override wins."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@lru_cache(maxsize=32)
def load_base() -> dict:
    """Load enterprise base config."""
    base_file = CLIENTS_DIR / "_base.yaml"
    if not base_file.exists():
        return {}
    with open(base_file) as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=32)
def load_personal() -> dict:
    """Load personal tier config."""
    personal_file = CLIENTS_DIR / "_personal.yaml"
    if not personal_file.exists():
        raise FileNotFoundError("_personal.yaml not found")
    with open(personal_file) as f:
        return yaml.safe_load(f)


def load_tenant_yaml(slug: str) -> dict:
    """Load a tenant YAML with _extends inheritance support."""
    tenant_file = CLIENTS_DIR / f"{slug}.yaml"

    if not tenant_file.exists():
        raise ValueError(f"Unknown tenant: {slug}")

    with open(tenant_file) as f:
        tenant = yaml.safe_load(f) or {}

    # Handle _extends inheritance
    if "_extends" in tenant:
        extends = tenant["_extends"].replace(".yaml", "")
        if extends == "_personal":
            base = load_personal()
        elif extends == "_base":
            base = load_base()
        else:
            base = load_tenant_yaml(extends)
        merged = deep_merge(base, tenant)
        del merged["_extends"]
        return merged

    return tenant


@lru_cache(maxsize=32)
def load_tenant(slug: str) -> dict:
    """Load tenant config by slug, with inheritance and base merging."""
    tenant = load_tenant_yaml(slug)

    # If mode is not personal and no explicit _extends, merge with enterprise base
    if tenant.get("mode") != "personal":
        base = load_base()
        return deep_merge(base, tenant)

    return tenant


def get_tenant_by_domain(domain: str) -> Optional[dict]:
    """Find tenant by custom domain."""
    for yaml_file in CLIENTS_DIR.glob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue
        with open(yaml_file) as f:
            tenant = yaml.safe_load(f)
            if tenant and tenant.get("domain") == domain:
                return load_tenant(tenant["slug"])
    return None


def get_tenant_by_subdomain(subdomain: str) -> Optional[dict]:
    """Find tenant by subdomain (e.g., 'sysco' from sysco.cogzy.ai)."""
    for yaml_file in CLIENTS_DIR.glob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue
        with open(yaml_file) as f:
            tenant = yaml.safe_load(f)
            if tenant and tenant.get("subdomain") == subdomain:
                return load_tenant(tenant["slug"])
    return None


def resolve_tenant(host: str) -> dict:
    """
    Resolve tenant from request host.

    Logic:
    1. cogzy.ai (exact) -> cogzy.yaml (personal tier)
    2. *.cogzy.ai -> extract subdomain -> enterprise tenant
    3. custom domain -> enterprise tenant by domain
    4. fallback -> personal config
    """
    host = host.lower().split(":")[0]  # Remove port if present

    # Personal tier domains: cogzy.ai, localhost, 127.0.0.1
    if host in ("cogzy.ai", "localhost", "127.0.0.1"):
        try:
            return load_tenant("cogzy")
        except ValueError:
            return load_personal()

    # Subdomain: xxx.cogzy.ai
    if host.endswith(".cogzy.ai"):
        subdomain = host.replace(".cogzy.ai", "")
        tenant = get_tenant_by_subdomain(subdomain)
        if tenant:
            return tenant
        # Unknown subdomain, fall back to personal
        return load_personal()

    # Custom domain lookup
    tenant = get_tenant_by_domain(host)
    if tenant:
        return tenant

    # Fallback: treat as personal
    return load_personal()


def clear_cache():
    """Clear LRU caches (call after YAML changes in dev)."""
    load_base.cache_clear()
    load_personal.cache_clear()
    load_tenant.cache_clear()
