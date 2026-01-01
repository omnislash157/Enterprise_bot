/**
 * Tenant Store - Current tenant context from domain
 *
 * Resolves the current tenant based on the domain and provides
 * tenant-specific configuration (branding, SSO settings, etc.)
 */
import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

export interface Tenant {
    tenant_id: string;
    slug: string;
    name: string;
    domain: string;
    branding: {
        logo_url?: string;
        primary_color?: string;
        accent_color?: string;
    };
    has_azure_sso: boolean;
}

interface TenantState {
    tenant: Tenant | null;
    loading: boolean;
    error: string | null;
}

function createTenantStore() {
    const { subscribe, set, update } = writable<TenantState>({
        tenant: null,
        loading: true,
        error: null,
    });

    return {
        subscribe,

        async load() {
            if (!browser) return;

            update(state => ({ ...state, loading: true, error: null }));

            try {
                const apiBase = import.meta.env.VITE_API_URL || 'https://lucky-love-production.up.railway.app';
                const res = await fetch(`${apiBase}/api/tenant/config`, {
                    credentials: 'include',
                });

                if (res.ok) {
                    const tenant = await res.json();
                    set({ tenant, loading: false, error: null });
                    console.log('[TENANT] Loaded tenant:', tenant.slug);
                } else if (res.status === 400) {
                    // Unknown domain
                    set({ tenant: null, loading: false, error: 'Unknown domain' });
                    console.warn('[TENANT] Unknown domain - no tenant found');
                } else {
                    const errorText = await res.text();
                    set({ tenant: null, loading: false, error: 'Failed to load tenant' });
                    console.error('[TENANT] Load failed:', errorText);
                }
            } catch (e) {
                const errorMsg = e instanceof Error ? e.message : String(e);
                set({ tenant: null, loading: false, error: errorMsg });
                console.error('[TENANT] Load error:', e);
            }
        },

        reset() {
            set({ tenant: null, loading: false, error: null });
        },
    };
}

export const tenant = createTenantStore();

// Derived stores for convenience
export const currentTenant = derived(tenant, $t => $t.tenant);
export const tenantLoading = derived(tenant, $t => $t.loading);
export const tenantBranding = derived(tenant, $t => $t.tenant?.branding || {});
export const tenantSlug = derived(tenant, $t => $t.tenant?.slug);
export const tenantHasSSO = derived(tenant, $t => $t.tenant?.has_azure_sso ?? false);
