/**
 * Auth Store - Stub (auth disabled for now)
 * Supabase removed - will add proper auth later
 */

import { writable } from 'svelte/store';

export const user = writable(null);
export const isAuthenticated = writable(true);

export function signIn() {}
export function signOut() {}
