<script lang="ts">
    import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { auth } from '$lib/stores/auth';

    let error: string | null = null;

    onMount(async () => {
        const code = $page.url.searchParams.get('code');
        const state = $page.url.searchParams.get('state');
        const errorParam = $page.url.searchParams.get('error');

        if (errorParam) {
            error = `Google login failed: ${errorParam}`;
            return;
        }

        if (!code || !state) {
            error = 'Missing authorization code';
            return;
        }

        const success = await auth.handleGoogleCallback(code, state);

        if (success) {
            goto('/');
        } else {
            // Error is in store, but we can show a generic message
            error = 'Login failed. Please try again.';
        }
    });
</script>

<div class="callback-container">
    <div class="callback-card">
        {#if error}
            <div class="error-state">
                <span class="error-icon">!</span>
                <h2>Authentication Failed</h2>
                <p>{error}</p>
                <a href="/" class="retry-link">Try again</a>
            </div>
        {:else}
            <div class="loading-state">
                <div class="spinner"></div>
                <p>Completing sign in...</p>
            </div>
        {/if}
    </div>
</div>

<style>
    .callback-container {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #0f0f1a 100%);
        padding: 1rem;
    }

    .callback-card {
        background: rgba(10, 10, 10, 0.9);
        border: 1px solid rgba(0, 255, 65, 0.2);
        border-radius: 16px;
        padding: 2.5rem;
        text-align: center;
        min-width: 300px;
    }

    .loading-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1rem;
    }

    .spinner {
        width: 48px;
        height: 48px;
        border: 3px solid rgba(0, 255, 65, 0.2);
        border-top-color: #00ff41;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    .loading-state p {
        color: #888;
        font-size: 0.95rem;
    }

    .error-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.75rem;
    }

    .error-icon {
        width: 48px;
        height: 48px;
        background: rgba(255, 68, 68, 0.2);
        border: 2px solid #ff4444;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ff4444;
        font-size: 1.5rem;
        font-weight: bold;
    }

    .error-state h2 {
        color: #ff4444;
        font-size: 1.25rem;
        margin: 0;
    }

    .error-state p {
        color: #888;
        font-size: 0.9rem;
        margin: 0;
    }

    .retry-link {
        color: #00ff41;
        text-decoration: none;
        margin-top: 0.5rem;
    }

    .retry-link:hover {
        text-decoration: underline;
    }
</style>
