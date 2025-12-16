/**
 * Auth Store - User Authentication & Session Management
 */

import { writable, derived } from 'svelte/store';

interface User {
    id: string;
    email: string;
    display_name: string | null;
    role: string;
    tier: string;
    employee_id: string | null;
    primary_department: string | null;
    departments: string[];
    is_super_user: boolean;
    can_manage_users: boolean;
}

interface AuthState {
    user: User | null;
    loading: boolean;
    error: string | null;
    initialized: boolean;
}

function getApiBase(): string {
    return import.meta.env.VITE_API_URL || 'http://localhost:8000';
}

function createAuthStore() {
    const { subscribe, set, update } = writable<AuthState>({
        user: null,
        loading: false,
        error: null,
        initialized: false,
    });

    return {
        subscribe,

        async login(email: string): Promise<boolean> {
            update(s => ({ ...s, loading: true, error: null }));

            try {
                const apiBase = getApiBase();
                const res = await fetch(`${apiBase}/api/whoami`, {
                    headers: { 'X-User-Email': email }
                });

                if (!res.ok) {
                    const err = await res.json();
                    update(s => ({ ...s, loading: false, error: err.detail || 'Login failed' }));
                    return false;
                }

                const data = await res.json();
                if (data.authenticated) {
                    update(s => ({ ...s, user: data.user, loading: false, initialized: true }));
                    // Store email for future requests
                    localStorage.setItem('user_email', email);
                    return true;
                } else {
                    update(s => ({ ...s, loading: false, error: data.message || 'Not authenticated', initialized: true }));
                    return false;
                }
            } catch (e) {
                update(s => ({ ...s, loading: false, error: String(e), initialized: true }));
                return false;
            }
        },

        logout() {
            localStorage.removeItem('user_email');
            set({ user: null, loading: false, error: null, initialized: true });
        },

        // Restore session from localStorage
        async restore(): Promise<boolean> {
            const email = localStorage.getItem('user_email');
            if (email) {
                return this.login(email);
            }
            update(s => ({ ...s, initialized: true }));
            return false;
        },

        getEmail(): string | null {
            return localStorage.getItem('user_email');
        },

        // Mark as initialized (for cases where we skip auth)
        markInitialized() {
            update(s => ({ ...s, initialized: true }));
        }
    };
}

export const auth = createAuthStore();

// Derived stores for convenience
export const isAuthenticated = derived(auth, $auth => $auth.user !== null);
export const currentUser = derived(auth, $auth => $auth.user);
export const userDepartments = derived(auth, $auth => $auth.user?.departments || []);
export const isSuperUser = derived(auth, $auth => $auth.user?.is_super_user || false);
export const authInitialized = derived(auth, $auth => $auth.initialized);
export const authLoading = derived(auth, $auth => $auth.loading);
