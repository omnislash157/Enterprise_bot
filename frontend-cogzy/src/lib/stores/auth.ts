import { writable, derived } from 'svelte/store';

const API_URL = import.meta.env.VITE_API_URL || '';

export interface User {
    id: string;
    email: string;
    display_name?: string;
    avatar_url?: string;
}

export const user = writable<User | null>(null);
export const authLoading = writable(true);
export const isAuthenticated = derived(user, $user => $user !== null);

export async function checkAuth(): Promise<boolean> {
    authLoading.set(true);
    try {
        const res = await fetch(`${API_URL}/api/personal/auth/me`, {
            credentials: 'include'
        });

        if (res.ok) {
            const data = await res.json();
            user.set(data.user);
            return true;
        } else {
            user.set(null);
            return false;
        }
    } catch {
        user.set(null);
        return false;
    } finally {
        authLoading.set(false);
    }
}

export async function logout(): Promise<void> {
    try {
        await fetch(`${API_URL}/api/personal/auth/logout`, {
            method: 'POST',
            credentials: 'include'
        });
    } finally {
        user.set(null);
    }
}
