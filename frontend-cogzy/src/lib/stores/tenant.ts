import { writable, derived } from 'svelte/store';

const API_URL = import.meta.env.VITE_API_URL || '';

export interface TenantConfig {
    mode: 'personal' | 'enterprise';
    name: string;
    slug: string;
    auth: {
        google?: boolean;
        email?: boolean;
        azure_ad?: boolean;
    };
    features: Record<string, boolean>;
    branding: {
        logo?: string;
        logo_alt?: string;
        title?: string;
        tagline?: string;
        primary_color?: string;
        accent_color?: string;
        background?: string;
    };
}

export const tenantConfig = writable<TenantConfig | null>(null);
export const tenantLoading = writable(true);
export const tenantError = writable<string | null>(null);

// Derived stores
export const branding = derived(tenantConfig, $c => $c?.branding);
export const features = derived(tenantConfig, $c => $c?.features || {});
export const authProviders = derived(tenantConfig, $c => $c?.auth || {});
export const isPersonalMode = derived(tenantConfig, $c => $c?.mode === 'personal');

export async function loadTenantConfig(): Promise<void> {
    tenantLoading.set(true);
    tenantError.set(null);

    try {
        const response = await fetch(`${API_URL}/api/tenant/config`);

        if (!response.ok) {
            throw new Error(`Config load failed: ${response.status}`);
        }

        const data = await response.json();
        tenantConfig.set(data);

        // Apply branding to CSS custom properties
        if (data.branding) {
            applyBranding(data.branding);
        }

        console.log(`[Tenant] Loaded: ${data.name} (${data.mode})`);
    } catch (err) {
        console.error('[Tenant] Config load failed:', err);
        tenantError.set(err instanceof Error ? err.message : 'Unknown error');
        // Apply defaults
        applyDefaultBranding();
    } finally {
        tenantLoading.set(false);
    }
}

function applyBranding(branding: TenantConfig['branding']): void {
    if (branding.title) {
        document.title = branding.title;
    }

    const root = document.documentElement;
    if (branding.primary_color) {
        root.style.setProperty('--color-primary', branding.primary_color);
    }
    if (branding.accent_color) {
        root.style.setProperty('--color-accent', branding.accent_color);
    }
    if (branding.background) {
        root.style.setProperty('--color-background', branding.background);
    }
}

function applyDefaultBranding(): void {
    document.title = 'Cogzy';
    const root = document.documentElement;
    root.style.setProperty('--color-primary', '#00ff41');
    root.style.setProperty('--color-accent', '#ff0055');
    root.style.setProperty('--color-background', '#050505');
}
