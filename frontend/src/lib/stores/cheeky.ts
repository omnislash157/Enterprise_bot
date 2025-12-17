/**
 * Cheeky Store
 * =============
 * Reactive store for managing cheeky status across the app.
 */

import { writable, derived, get } from 'svelte/store';
import { cheeky as cheekyEngine, type PhraseCategory } from '$lib/cheeky';

interface CheekyState {
    isLoading: boolean;
    category: PhraseCategory;
    progress: number;
    customMessage: string | null;
}

const initialState: CheekyState = {
    isLoading: false,
    category: 'waiting',
    progress: 0,
    customMessage: null,
};

function createCheekyStore() {
    const { subscribe, set, update } = writable<CheekyState>(initialState);

    return {
        subscribe,

        /**
         * Start a loading state with category.
         */
        start(category: PhraseCategory = 'searching') {
            update(s => ({
                ...s,
                isLoading: true,
                category,
                progress: 0,
                customMessage: null,
            }));
        },

        /**
         * Update progress (0-100).
         */
        progress(value: number, category?: PhraseCategory) {
            update(s => ({
                ...s,
                progress: Math.min(100, Math.max(0, value)),
                ...(category && { category }),
            }));
        },

        /**
         * Set a specific phase with category.
         */
        phase(category: PhraseCategory, progress?: number) {
            update(s => ({
                ...s,
                category,
                ...(progress !== undefined && { progress }),
            }));
        },

        /**
         * Complete with success.
         */
        success(message?: string) {
            update(s => ({
                ...s,
                category: 'success',
                progress: 100,
                customMessage: message || null,
            }));

            // Auto-clear after delay
            setTimeout(() => {
                update(s => ({
                    ...s,
                    isLoading: false,
                    progress: 0,
                    customMessage: null,
                }));
            }, 2000);
        },

        /**
         * Complete with error.
         */
        error(message?: string) {
            update(s => ({
                ...s,
                category: 'error',
                customMessage: message || null,
            }));

            // Auto-clear after delay
            setTimeout(() => {
                update(s => ({
                    ...s,
                    isLoading: false,
                    progress: 0,
                    customMessage: null,
                }));
            }, 3000);
        },

        /**
         * Stop loading immediately.
         */
        stop() {
            set(initialState);
        },

        /**
         * Get a phrase for current category.
         */
        getPhrase(): string {
            const state = get({ subscribe });

            if (state.customMessage) {
                return state.customMessage;
            }

            return cheekyEngine.get(state.category);
        },
    };
}

export const cheekyStore = createCheekyStore();

// Derived stores
export const isCheekyLoading = derived(cheekyStore, $s => $s.isLoading);
export const cheekyCategory = derived(cheekyStore, $s => $s.category);
export const cheekyProgress = derived(cheekyStore, $s => $s.progress);
