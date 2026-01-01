/**
 * Auth Store - Personal Tier Authentication
 *
 * Supports:
 * - Google OAuth (primary)
 * - Email/password (secondary)
 * - Cookie-based sessions (no JWT)
 */

import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

interface User {
    id: string;
    email: string;
    display_name: string | null;
    auth_provider: 'email' | 'google';
    tier?: string;
}

interface AuthState {
    user: User | null;
    loading: boolean;
    error: string | null;
    initialized: boolean;
    googleEnabled: boolean;
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
        googleEnabled: true, // Personal tier always has Google
    });

    const store = {
        subscribe,

        /**
         * Initialize - check if already logged in via session cookie
         */
        async init() {
            try {
                await this.checkSession();
            } catch (e) {
                console.error('Auth init failed:', e);
                update(s => ({ ...s, initialized: true }));
            }
        },

        /**
         * Check if session cookie exists and is valid
         */
        async checkSession(): Promise<boolean> {
            try {
                const apiBase = getApiBase();
                const res = await fetch(`${apiBase}/api/personal/auth/me`, {
                    credentials: 'include', // Include cookies
                });

                if (res.ok) {
                    const user = await res.json();
                    update(s => ({
                        ...s,
                        user: user,
                        initialized: true,
                    }));
                    return true;
                }

                update(s => ({ ...s, initialized: true }));
                return false;
            } catch (e) {
                update(s => ({ ...s, initialized: true }));
                return false;
            }
        },

        /**
         * Start Google OAuth flow
         */
        async loginWithGoogle() {
            update(s => ({ ...s, loading: true, error: null }));

            try {
                const apiBase = getApiBase();
                // Determine callback URL based on current location
                const callbackUrl = browser
                    ? `${window.location.origin}/auth/google/callback`
                    : `${apiBase}/auth/google/callback`;

                const res = await fetch(
                    `${apiBase}/api/personal/auth/google?redirect_uri=${encodeURIComponent(callbackUrl)}`
                );
                const { url, state } = await res.json();

                // Store state for CSRF validation
                if (browser) {
                    sessionStorage.setItem('oauth_state', state);
                }

                // Redirect to Google
                window.location.href = url;
            } catch (e) {
                update(s => ({ ...s, loading: false, error: String(e) }));
            }
        },

        /**
         * Handle Google OAuth callback
         */
        async handleGoogleCallback(code: string, state: string): Promise<boolean> {
            update(s => ({ ...s, loading: true, error: null }));

            // Validate state
            if (browser) {
                const storedState = sessionStorage.getItem('oauth_state');
                if (state !== storedState) {
                    update(s => ({ ...s, loading: false, error: 'Invalid state - possible CSRF attack' }));
                    return false;
                }
                sessionStorage.removeItem('oauth_state');
            }

            try {
                const apiBase = getApiBase();
                const callbackUrl = browser
                    ? `${window.location.origin}/auth/google/callback`
                    : `${apiBase}/auth/google/callback`;

                const res = await fetch(`${apiBase}/api/personal/auth/google/callback`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ code, redirect_uri: callbackUrl }),
                });

                if (!res.ok) {
                    const err = await res.json();
                    update(s => ({ ...s, loading: false, error: err.detail || 'Google login failed' }));
                    return false;
                }

                const data = await res.json();

                update(s => ({
                    ...s,
                    user: data.user,
                    loading: false,
                    initialized: true,
                }));

                return true;
            } catch (e) {
                update(s => ({ ...s, loading: false, error: String(e), initialized: true }));
                return false;
            }
        },

        /**
         * Register with email/password
         */
        async register(email: string, password: string, displayName?: string): Promise<boolean> {
            update(s => ({ ...s, loading: true, error: null }));

            try {
                const apiBase = getApiBase();
                const res = await fetch(`${apiBase}/api/personal/auth/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        email,
                        password,
                        display_name: displayName || null,
                    }),
                });

                const data = await res.json();

                if (!res.ok) {
                    update(s => ({ ...s, loading: false, error: data.detail || 'Registration failed' }));
                    return false;
                }

                update(s => ({ ...s, loading: false }));
                return true;
            } catch (e) {
                update(s => ({ ...s, loading: false, error: String(e) }));
                return false;
            }
        },

        /**
         * Login with email/password
         */
        async login(email: string, password: string): Promise<boolean> {
            update(s => ({ ...s, loading: true, error: null }));

            try {
                const apiBase = getApiBase();
                const res = await fetch(`${apiBase}/api/personal/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ email, password }),
                });

                const data = await res.json();

                if (!res.ok) {
                    update(s => ({ ...s, loading: false, error: data.detail || 'Login failed' }));
                    return false;
                }

                update(s => ({
                    ...s,
                    user: data.user,
                    loading: false,
                    initialized: true,
                }));

                return true;
            } catch (e) {
                update(s => ({ ...s, loading: false, error: String(e) }));
                return false;
            }
        },

        /**
         * Logout - clear session cookie
         */
        async logout() {
            try {
                const apiBase = getApiBase();
                await fetch(`${apiBase}/api/personal/auth/logout`, {
                    method: 'POST',
                    credentials: 'include',
                });
            } catch (e) {
                console.error('Logout error:', e);
            }

            update(s => ({
                user: null,
                loading: false,
                error: null,
                initialized: true,
                googleEnabled: true,
            }));
        },

        /**
         * Request password reset
         */
        async forgotPassword(email: string): Promise<boolean> {
            update(s => ({ ...s, loading: true, error: null }));

            try {
                const apiBase = getApiBase();
                const res = await fetch(`${apiBase}/api/personal/auth/forgot`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email }),
                });

                update(s => ({ ...s, loading: false }));
                return res.ok;
            } catch (e) {
                update(s => ({ ...s, loading: false, error: String(e) }));
                return false;
            }
        },

        /**
         * Reset password with token
         */
        async resetPassword(token: string, newPassword: string): Promise<boolean> {
            update(s => ({ ...s, loading: true, error: null }));

            try {
                const apiBase = getApiBase();
                const res = await fetch(`${apiBase}/api/personal/auth/reset`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token, new_password: newPassword }),
                });

                const data = await res.json();

                if (!res.ok) {
                    update(s => ({ ...s, loading: false, error: data.detail || 'Reset failed' }));
                    return false;
                }

                update(s => ({ ...s, loading: false }));
                return true;
            } catch (e) {
                update(s => ({ ...s, loading: false, error: String(e) }));
                return false;
            }
        },

        /**
         * Clear error
         */
        clearError() {
            update(s => ({ ...s, error: null }));
        },

        /**
         * Mark as initialized (for cases where we skip auth)
         */
        markInitialized() {
            update(s => ({ ...s, initialized: true }));
        },

        /**
         * Get email (for backwards compatibility with enterprise stores)
         * Personal tier uses cookies, so this returns the user email from state
         */
        getEmail(): string | null {
            let email: string | null = null;
            subscribe(s => { email = s.user?.email || null; })();
            return email;
        },

        /**
         * Get auth header (for backwards compatibility)
         * Personal tier uses cookies, so this returns empty object
         * (browser includes cookies automatically with credentials: 'include')
         */
        getAuthHeader(): Record<string, string> {
            return {};
        }
    };

    return store;
}

export const auth = createAuthStore();

// Derived stores for convenience
export const isAuthenticated = derived(auth, $auth => $auth.user !== null);
export const currentUser = derived(auth, $auth => $auth.user);
export const authInitialized = derived(auth, $auth => $auth.initialized);
export const authLoading = derived(auth, $auth => $auth.loading);
export const authError = derived(auth, $auth => $auth.error);
export const googleEnabled = derived(auth, $auth => $auth.googleEnabled);

// Backwards compatibility exports (empty for personal tier)
export const userDepartments = derived(auth, () => []);
export const userDeptHeadFor = derived(auth, () => []);
export const isSuperUser = derived(auth, () => false);
export const canSeeAdminDerived = derived(auth, () => false);
export const azureEnabled = derived(auth, () => false);
export const authMethod = derived(auth, $auth => $auth.user?.auth_provider || null);

// Permission helpers (no-ops for personal tier)
export function canGrantAccessTo(): boolean { return false; }
export function canSeeAdmin(): boolean { return false; }
export function canManageDeptHeads(): boolean { return false; }
export function canManageSuperUsers(): boolean { return false; }
export function getGrantableDepartments(): string[] { return []; }
