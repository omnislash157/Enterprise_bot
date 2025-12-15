/**
 * Auth Store - Supabase Authentication for CogTwin
 * 
 * Handles login, logout, session management, and tenant resolution.
 * Works with tenant_service.py on the backend.
 */

import { writable, derived, get } from 'svelte/store';
import { createClient, type User, type Session } from '@supabase/supabase-js';

// Initialize Supabase client
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
    console.error('[Auth] Missing Supabase env vars. Check VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Types
export interface UserTenant {
    tenant_id: string;
    tenant_slug: string;
    tenant_name: string;
    role: 'admin' | 'user' | 'readonly';
}

export interface AuthState {
    user: User | null;
    session: Session | null;
    tenants: UserTenant[];
    activeTenant: UserTenant | null;
    loading: boolean;
    error: string | null;
}

// Initial state
const initialState: AuthState = {
    user: null,
    session: null,
    tenants: [],
    activeTenant: null,
    loading: true,
    error: null,
};

// Create the store
function createAuthStore() {
    const store = writable<AuthState>(initialState);
    const { subscribe, set, update } = store;

    // Fetch user's tenants after login
    async function loadUserTenants(userId: string): Promise<UserTenant[]> {
        const { data, error } = await supabase
            .from('user_tenants')
            .select(`
                tenant_id,
                role,
                tenants!inner (
                    slug,
                    name
                )
            `)
            .eq('user_id', userId);

        if (error) {
            console.error('[Auth] Failed to load tenants:', error);
            return [];
        }

        return data.map((row: any) => ({
            tenant_id: row.tenant_id,
            tenant_slug: row.tenants.slug,
            tenant_name: row.tenants.name,
            role: row.role,
        }));
    }

    // Initialize auth state
    async function init() {
        update(s => ({ ...s, loading: true, error: null }));

        // Check for existing session
        const { data: { session }, error } = await supabase.auth.getSession();

        if (error) {
            update(s => ({ ...s, loading: false, error: error.message }));
            return;
        }

        if (session?.user) {
            const tenants = await loadUserTenants(session.user.id);
            const savedTenantSlug = localStorage.getItem('cogtwin_active_tenant');
            const activeTenant = tenants.find(t => t.tenant_slug === savedTenantSlug) || tenants[0] || null;

            update(s => ({
                ...s,
                user: session.user,
                session,
                tenants,
                activeTenant,
                loading: false,
            }));
        } else {
            update(s => ({ ...s, loading: false }));
        }

        // Listen for auth changes
        supabase.auth.onAuthStateChange(async (event, session) => {
            console.log('[Auth] State change:', event);

            if (event === 'SIGNED_IN' && session?.user) {
                const tenants = await loadUserTenants(session.user.id);
                const savedTenantSlug = localStorage.getItem('cogtwin_active_tenant');
                const activeTenant = tenants.find(t => t.tenant_slug === savedTenantSlug) || tenants[0] || null;

                update(s => ({
                    ...s,
                    user: session.user,
                    session,
                    tenants,
                    activeTenant,
                    error: null,
                }));
            } else if (event === 'SIGNED_OUT') {
                set(initialState);
                update(s => ({ ...s, loading: false }));
            }
        });
    }

    return {
        subscribe,

        init,

        // Email/password login
        async signIn(email: string, password: string): Promise<{ success: boolean; error?: string }> {
            update(s => ({ ...s, loading: true, error: null }));

            const { data, error } = await supabase.auth.signInWithPassword({
                email,
                password,
            });

            if (error) {
                update(s => ({ ...s, loading: false, error: error.message }));
                return { success: false, error: error.message };
            }

            // Auth state listener will handle the rest
            return { success: true };
        },

        // Magic link login (passwordless)
        async signInWithMagicLink(email: string): Promise<{ success: boolean; error?: string }> {
            update(s => ({ ...s, loading: true, error: null }));

            const { error } = await supabase.auth.signInWithOtp({
                email,
                options: {
                    emailRedirectTo: window.location.origin,
                },
            });

            if (error) {
                update(s => ({ ...s, loading: false, error: error.message }));
                return { success: false, error: error.message };
            }

            update(s => ({ ...s, loading: false }));
            return { success: true };
        },

        // Sign up new user
        async signUp(email: string, password: string): Promise<{ success: boolean; error?: string }> {
            update(s => ({ ...s, loading: true, error: null }));

            const { data, error } = await supabase.auth.signUp({
                email,
                password,
            });

            if (error) {
                update(s => ({ ...s, loading: false, error: error.message }));
                return { success: false, error: error.message };
            }

            update(s => ({ ...s, loading: false }));
            return { success: true };
        },

        // Sign out
        async signOut() {
            await supabase.auth.signOut();
            localStorage.removeItem('cogtwin_active_tenant');
            set(initialState);
            update(s => ({ ...s, loading: false }));
        },

        // Switch active tenant (for users with multiple tenants)
        setActiveTenant(tenant: UserTenant) {
            localStorage.setItem('cogtwin_active_tenant', tenant.tenant_slug);
            update(s => ({ ...s, activeTenant: tenant }));
        },

        // Get JWT for API calls (backend uses this to identify user/tenant)
        async getAccessToken(): Promise<string | null> {
            const { data: { session } } = await supabase.auth.getSession();
            return session?.access_token ?? null;
        },

        // Clear error
        clearError() {
            update(s => ({ ...s, error: null }));
        },
    };
}

export const auth = createAuthStore();

// Derived stores for easy access
export const isAuthenticated = derived(auth, $auth => !!$auth.user);
export const currentUser = derived(auth, $auth => $auth.user);
export const currentTenant = derived(auth, $auth => $auth.activeTenant);
export const userTenants = derived(auth, $auth => $auth.tenants);
export const authLoading = derived(auth, $auth => $auth.loading);
export const authError = derived(auth, $auth => $auth.error);

// Helper to get auth headers for fetch calls
export async function getAuthHeaders(): Promise<Record<string, string>> {
    const token = await auth.getAccessToken();
    const tenant = get(currentTenant);
    
    return {
        'Authorization': token ? `Bearer ${token}` : '',
        'X-Tenant-Slug': tenant?.tenant_slug ?? '',
    };
}
