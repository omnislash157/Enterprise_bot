/**
 * Personal Auth Store - Email/Password + Google OAuth
 *
 * Uses HTTP-only cookies for sessions (no localStorage tokens).
 * Backend manages session in Redis.
 */

import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

// =============================================================================
// TYPES
// =============================================================================

interface PersonalUser {
    id: string;
    email: string;
    display_name: string | null;
    auth_provider: 'email' | 'google';
}

interface PersonalAuthState {
    user: PersonalUser | null;
    loading: boolean;
    error: string | null;
    initialized: boolean;
}

// =============================================================================
// STORE
// =============================================================================

const initialState: PersonalAuthState = {
    user: null,
    loading: false,
    error: null,
    initialized: false,
};

function createPersonalAuthStore() {
    const { subscribe, set, update } = writable<PersonalAuthState>(initialState);

    const API_URL = import.meta.env.VITE_API_URL || '';

    return {
        subscribe,

        /**
         * Initialize - check if user has valid session
         */
        async init() {
            if (!browser) return;

            update(s => ({ ...s, loading: true }));

            try {
                const res = await fetch(`${API_URL}/api/personal/auth/me`, {
                    credentials: 'include',  // Send cookies
                });

                if (res.ok) {
                    const user = await res.json();
                    update(s => ({
                        ...s,
                        user,
                        loading: false,
                        initialized: true,
                    }));
                } else {
                    update(s => ({
                        ...s,
                        user: null,
                        loading: false,
                        initialized: true,
                    }));
                }
            } catch (e) {
                update(s => ({
                    ...s,
                    user: null,
                    loading: false,
                    initialized: true,
                    error: 'Failed to check authentication',
                }));
            }
        },

        /**
         * Register with email/password
         */
        async register(email: string, password: string, displayName?: string) {
            update(s => ({ ...s, loading: true, error: null }));

            try {
                const res = await fetch(`${API_URL}/api/personal/auth/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password, display_name: displayName }),
                    credentials: 'include',
                });

                const data = await res.json();

                if (!res.ok) {
                    throw new Error(data.detail || 'Registration failed');
                }

                update(s => ({ ...s, loading: false }));
                return { success: true, message: data.message };

            } catch (e: any) {
                update(s => ({ ...s, loading: false, error: e.message }));
                return { success: false, error: e.message };
            }
        },

        /**
         * Login with email/password
         */
        async login(email: string, password: string) {
            update(s => ({ ...s, loading: true, error: null }));

            try {
                const res = await fetch(`${API_URL}/api/personal/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password }),
                    credentials: 'include',
                });

                const data = await res.json();

                if (!res.ok) {
                    throw new Error(data.detail || 'Login failed');
                }

                update(s => ({
                    ...s,
                    user: data.user,
                    loading: false,
                }));

                return { success: true };

            } catch (e: any) {
                update(s => ({ ...s, loading: false, error: e.message }));
                return { success: false, error: e.message };
            }
        },

        /**
         * Start Google OAuth flow
         */
        async startGoogleLogin() {
            try {
                const redirectUri = `${window.location.origin}/auth/google/callback`;
                const res = await fetch(
                    `${API_URL}/api/personal/auth/google?redirect_uri=${encodeURIComponent(redirectUri)}`,
                    { credentials: 'include' }
                );

                if (!res.ok) throw new Error('Failed to get Google login URL');

                const { url, state } = await res.json();

                // Store state for validation
                sessionStorage.setItem('google_oauth_state', state);

                // Redirect to Google
                window.location.href = url;

            } catch (e: any) {
                update(s => ({ ...s, error: e.message }));
            }
        },

        /**
         * Complete Google OAuth (called from callback page)
         */
        async completeGoogleLogin(code: string, state: string) {
            update(s => ({ ...s, loading: true, error: null }));

            // Validate state
            const storedState = sessionStorage.getItem('google_oauth_state');
            if (state !== storedState) {
                update(s => ({ ...s, loading: false, error: 'Invalid OAuth state' }));
                return { success: false, error: 'Invalid OAuth state' };
            }
            sessionStorage.removeItem('google_oauth_state');

            try {
                const redirectUri = `${window.location.origin}/auth/google/callback`;
                const res = await fetch(`${API_URL}/api/personal/auth/google/callback`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code, redirect_uri: redirectUri }),
                    credentials: 'include',
                });

                const data = await res.json();

                if (!res.ok) {
                    throw new Error(data.detail || 'Google login failed');
                }

                update(s => ({
                    ...s,
                    user: data.user,
                    loading: false,
                }));

                return { success: true };

            } catch (e: any) {
                update(s => ({ ...s, loading: false, error: e.message }));
                return { success: false, error: e.message };
            }
        },

        /**
         * Logout
         */
        async logout() {
            try {
                await fetch(`${API_URL}/api/personal/auth/logout`, {
                    method: 'POST',
                    credentials: 'include',
                });
            } catch (e) {
                // Ignore errors, clear local state anyway
            }

            set({ ...initialState, initialized: true });
        },

        /**
         * Request password reset
         */
        async forgotPassword(email: string) {
            try {
                const res = await fetch(`${API_URL}/api/personal/auth/forgot`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email }),
                    credentials: 'include',
                });

                const data = await res.json();
                return { success: true, message: data.message };

            } catch (e: any) {
                return { success: false, error: e.message };
            }
        },

        /**
         * Reset password with token
         */
        async resetPassword(token: string, newPassword: string) {
            try {
                const res = await fetch(`${API_URL}/api/personal/auth/reset`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token, new_password: newPassword }),
                    credentials: 'include',
                });

                const data = await res.json();

                if (!res.ok) {
                    throw new Error(data.detail || 'Password reset failed');
                }

                return { success: true, message: data.message };

            } catch (e: any) {
                return { success: false, error: e.message };
            }
        },

        clearError() {
            update(s => ({ ...s, error: null }));
        },
    };
}

export const personalAuthStore = createPersonalAuthStore();

// Derived stores
export const isAuthenticated = derived(
    personalAuthStore,
    $store => $store.user !== null
);

export const currentUser = derived(
    personalAuthStore,
    $store => $store.user
);
