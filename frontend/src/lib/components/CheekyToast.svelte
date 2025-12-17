<script lang="ts">
    import { fly, fade } from 'svelte/transition';
    import { flip } from 'svelte/animate';
    import { cheeky, type PhraseCategory } from '$lib/cheeky';

    interface Toast {
        id: string;
        category: PhraseCategory;
        message: string;
        duration: number;
    }

    let toasts: Toast[] = [];

    export function show(
        category: PhraseCategory,
        message?: string,
        duration: number = 3000
    ) {
        const id = crypto.randomUUID();
        const toast: Toast = {
            id,
            category,
            message: message || cheeky.get(category),
            duration,
        };

        toasts = [...toasts, toast];

        // Auto remove
        setTimeout(() => {
            remove(id);
        }, duration);

        return id;
    }

    export function remove(id: string) {
        toasts = toasts.filter(t => t.id !== id);
    }

    export function success(message?: string) {
        return show('success', message);
    }

    export function error(message?: string) {
        return show('error', message, 5000);
    }

    // Icon mapping
    const icons: Record<PhraseCategory, string> = {
        searching: '🔍',
        thinking: '🤔',
        creating: '✨',
        executing: '⚡',
        waiting: '⏳',
        success: '✅',
        error: '❌',
    };
</script>

<div class="toast-container">
    {#each toasts as toast (toast.id)}
        <div
            class="toast toast-{toast.category}"
            in:fly={{ y: 50, duration: 200 }}
            out:fade={{ duration: 150 }}
            animate:flip={{ duration: 200 }}
        >
            <span class="toast-icon">{icons[toast.category]}</span>
            <span class="toast-message">{toast.message}</span>
            <button
                class="toast-close"
                on:click={() => remove(toast.id)}
                aria-label="Dismiss"
            >
                ×
            </button>
        </div>
    {/each}
</div>

<style>
    .toast-container {
        position: fixed;
        bottom: 1.5rem;
        right: 1.5rem;
        z-index: 9999;

        display: flex;
        flex-direction: column;
        gap: 0.75rem;

        pointer-events: none;
    }

    .toast {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.875rem 1rem;

        background: rgba(20, 20, 25, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 10px;

        box-shadow:
            0 4px 20px rgba(0, 0, 0, 0.4),
            0 0 0 1px rgba(255, 255, 255, 0.1);

        pointer-events: auto;
        max-width: 400px;
    }

    .toast-success {
        border-left: 3px solid #00ff41;
    }

    .toast-error {
        border-left: 3px solid #ff4141;
    }

    .toast-icon {
        font-size: 1.25rem;
        flex-shrink: 0;
    }

    .toast-message {
        flex: 1;
        color: rgba(255, 255, 255, 0.9);
        font-size: 0.9rem;
        line-height: 1.4;
    }

    .toast-close {
        flex-shrink: 0;
        width: 24px;
        height: 24px;

        display: flex;
        align-items: center;
        justify-content: center;

        background: none;
        border: none;
        border-radius: 4px;

        color: rgba(255, 255, 255, 0.5);
        font-size: 1.25rem;
        cursor: pointer;

        transition: all 0.15s ease;
    }

    .toast-close:hover {
        background: rgba(255, 255, 255, 0.1);
        color: #fff;
    }

    /* Mobile */
    @media (max-width: 480px) {
        .toast-container {
            left: 1rem;
            right: 1rem;
            bottom: 1rem;
        }

        .toast {
            max-width: none;
        }
    }
</style>
