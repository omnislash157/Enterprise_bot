# INVARIANTS - If these break, stop and fix

1. ALL cross-module imports go through protocols.py (except cog_twin.py circular)
2. Twin selection uses get_twin() ONLY - config.yaml is source of truth
3. TenantContext.user_email is the field name (not .email)
4. config_loader.py is active, config.py is DEAD (delete if exists)
5. Enterprise schema is 2 tables: tenants + users (no departments table)
6. Email login rejects non-whitelisted domains (no silent accept)