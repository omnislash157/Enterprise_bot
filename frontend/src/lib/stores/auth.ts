/**
 * Auth Store - User Authentication & Session Management
 * Supports both Azure AD SSO and legacy email authentication
 */

import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

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
    accessToken: string | null;
    loading: boolean;
    error: string | null;
    initialized: boolean;
    azureEnabled: boolean;
    authMethod: 'azure_ad' | 'email' | null;
}

interface TokenResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
    expires_in: number;
    user: User;
}

const REFRESH_TOKEN_KEY = 'refresh_token';
const ACCESS_TOKEN_KEY = 'access_token';
const AUTH_METHOD_KEY = 'auth_method';
const EMAIL_KEY = 'user_email'; // Legacy

function getApiBase(): string {
    return import.meta.env.VITE_API_URL || 'http://localhost:8000';
}

function createAuthStore() {
    const { subscribe, set, update } = writable<AuthState>({
        user: null,
        accessToken: null,
        loading: false,
        error: null,
        initialized: false,
        azureEnabled: false,
        authMethod: null,
    });

    let refreshToken: string | null = browser ? localStorage.getItem(REFRESH_TOKEN_KEY) : null;
    let refreshTimeout: number | null = null;

    function scheduleRefresh(expiresIn: number) {
        // Refresh 1 minute before expiry
        const refreshMs = (expiresIn - 60) * 1000;
        if (refreshTimeout) clearTimeout(refreshTimeout);
        if (refreshMs > 0) {
            refreshTimeout = window.setTimeout(() => store.refresh(), refreshMs);
        }
    }

    const store = {
        subscribe,

        /**
         * Initialize - check auth config and restore session
         */
        async init() {
            try {
                // Check if Azure AD is enabled
                const apiBase = getApiBase();
                const configRes = await fetch(`${apiBase}/api/auth/config`);
                const config = await configRes.json();

                update(s => ({ ...s, azureEnabled: config.azure_ad_enabled }));

                // Try to restore session
                await this.restore();
            } catch (e) {
                console.error('Auth init failed:', e);
                update(s => ({ ...s, initialized: true }));
            }
        },

        /**
         * Start Microsoft login flow
         */
        async loginWithMicrosoft() {
            update(s => ({ ...s, loading: true, error: null }));

            try {
                const apiBase = getApiBase();
                const res = await fetch(`${apiBase}/api/auth/login-url`);
                const { url, state } = await res.json();

                // Store state for validation
                sessionStorage.setItem('oauth_state', state);

                // Redirect to Microsoft
                window.location.href = url;
            } catch (e) {
                update(s => ({ ...s, loading: false, error: String(e) }));
            }
        },

        /**
         * Handle callback from Microsoft login
         * Call this from /auth/callback page
         */
        async handleCallback(code: string, state: string): Promise<boolean> {
            update(s => ({ ...s, loading: true, error: null }));

            // Validate state
            const storedState = sessionStorage.getItem('oauth_state');
            if (state !== storedState) {
                update(s => ({ ...s, loading: false, error: 'Invalid state parameter' }));
                return false;
            }
            sessionStorage.removeItem('oauth_state');

            try {
                const apiBase = getApiBase();
                const res = await fetch(`${apiBase}/api/auth/callback`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code, state }),
                });

                if (!res.ok) {
                    const err = await res.json();
                    update(s => ({ ...s, loading: false, error: err.detail || 'Login failed' }));
                    return false;
                }

                const tokens: TokenResponse = await res.json();

                // Store tokens
                refreshToken = tokens.refresh_token;
                localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
                localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
                localStorage.setItem(AUTH_METHOD_KEY, 'azure_ad');

                // Schedule refresh
                scheduleRefresh(tokens.expires_in);

                update(s => ({
                    ...s,
                    user: tokens.user,
                    accessToken: tokens.access_token,
                    loading: false,
                    initialized: true,
                    authMethod: 'azure_ad',
                }));

                return true;
            } catch (e) {
                update(s => ({ ...s, loading: false, error: String(e), initialized: true }));
                return false;
            }
        },

        /**
         * Refresh access token (Azure AD only)
         */
        async refresh(): Promise<boolean> {
            if (!refreshToken) {
                update(s => ({ ...s, initialized: true }));
                return false;
            }

            try {
                const apiBase = getApiBase();
                const res = await fetch(`${apiBase}/api/auth/refresh`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh_token: refreshToken }),
                });

                if (!res.ok) {
                    // Refresh failed - clear session
                    this.logout();
                    return false;
                }

                const tokens: TokenResponse = await res.json();

                refreshToken = tokens.refresh_token;
                localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
                localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);

                scheduleRefresh(tokens.expires_in);

                update(s => ({
                    ...s,
                    user: tokens.user,
                    accessToken: tokens.access_token,
                    initialized: true,
                    authMethod: 'azure_ad',
                }));

                return true;
            } catch (e) {
                console.error('Refresh failed:', e);
                return false;
            }
        },

        /**
         * Legacy email-based login
         */
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
                    update(s => ({
                        ...s,
                        user: data.user,
                        loading: false,
                        initialized: true,
                        authMethod: 'email',
                    }));
                    // Store email for future requests
                    localStorage.setItem(EMAIL_KEY, email);
                    localStorage.setItem(AUTH_METHOD_KEY, 'email');
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

        /**
         * Logout
         */
        async logout() {
            if (refreshTimeout) clearTimeout(refreshTimeout);

            const authMethod = localStorage.getItem(AUTH_METHOD_KEY);

            // Clear all auth data
            refreshToken = null;
            localStorage.removeItem(REFRESH_TOKEN_KEY);
            localStorage.removeItem(ACCESS_TOKEN_KEY);
            localStorage.removeItem(EMAIL_KEY);
            localStorage.removeItem(AUTH_METHOD_KEY);

            update(s => ({
                user: null,
                accessToken: null,
                loading: false,
                error: null,
                initialized: true,
                azureEnabled: s.azureEnabled,
                authMethod: null,
            }));

            // Optional: Full Microsoft logout
            // Uncomment to logout from Microsoft as well
            // if (authMethod === 'azure_ad') {
            //     window.location.href = 'https://login.microsoftonline.com/common/oauth2/v2.0/logout';
            // }
        },

        /**
         * Restore session from stored tokens
         */
        async restore(): Promise<boolean> {
            const authMethod = localStorage.getItem(AUTH_METHOD_KEY) as 'azure_ad' | 'email' | null;

            if (authMethod === 'azure_ad') {
                // Try to use existing access token, will refresh if needed
                const storedAccessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
                if (storedAccessToken && refreshToken) {
                    return this.refresh();
                }
            } else if (authMethod === 'email') {
                // Restore email-based session
                const email = localStorage.getItem(EMAIL_KEY);
                if (email) {
                    return this.login(email);
                }
            }

            update(s => ({ ...s, initialized: true }));
            return false;
        },

        /**
         * Get access token for API calls
         */
        getAccessToken(): string | null {
            const state = { user: null, accessToken: null } as AuthState;
            subscribe(s => Object.assign(state, s))();
            return state.accessToken;
        },

        /**
         * Get email for API calls (legacy)
         */
        getEmail(): string | null {
            return localStorage.getItem(EMAIL_KEY);
        },

        /**
         * Get auth header for API calls
         */
        getAuthHeader(): Record<string, string> {
            const authMethod = localStorage.getItem(AUTH_METHOD_KEY);

            if (authMethod === 'azure_ad') {
                const token = localStorage.getItem(ACCESS_TOKEN_KEY);
                return token ? { 'Authorization': `Bearer ${token}` } : {};
            } else if (authMethod === 'email') {
                const email = localStorage.getItem(EMAIL_KEY);
                return email ? { 'X-User-Email': email } : {};
            }

            return {};
        },

        /**
         * Mark as initialized (for cases where we skip auth)
         */
        markInitialized() {
            update(s => ({ ...s, initialized: true }));
        }
    };

    return store;
}

export const auth = createAuthStore();

// Derived stores for convenience
export const isAuthenticated = derived(auth, $auth => $auth.user !== null);
export const currentUser = derived(auth, $auth => $auth.user);
export const userDepartments = derived(auth, $auth => $auth.user?.departments || []);
export const isSuperUser = derived(auth, $auth => $auth.user?.is_super_user || false);
export const authInitialized = derived(auth, $auth => $auth.initialized);
export const authLoading = derived(auth, $auth => $auth.loading);
export const azureEnabled = derived(auth, $auth => $auth.azureEnabled);
export const authMethod = derived(auth, $auth => $auth.authMethod);
