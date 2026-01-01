-- Seed wildcard tenant for enterprise subdomains (*.cogzy.ai)
-- Run once in DBeaver or psql

-- Enable *.cogzy.ai subdomains for enterprise free tier
INSERT INTO enterprise.tenants (slug, name, domain, branding, is_active)
VALUES (
    'cogzy-enterprise',
    'Cogzy Enterprise',
    '*.cogzy.ai',
    '{"tier": "free", "title": "Enterprise Portal", "tagline": "Sign in to continue"}'::jsonb,
    true
)
ON CONFLICT (domain) DO NOTHING;

-- Verify insertion
SELECT slug, name, domain, branding, is_active
FROM enterprise.tenants
WHERE domain = '*.cogzy.ai';
