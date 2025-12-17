<script lang="ts">
    import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { auth } from '$lib/stores/auth';

    let error: string | null = null;
    let processing = true;

    onMount(async () => {
        const code = $page.url.searchParams.get('code');
        const state = $page.url.searchParams.get('state');
        const errorParam = $page.url.searchParams.get('error');
        const errorDesc = $page.url.searchParams.get('error_description');

        if (errorParam) {
            error = errorDesc || errorParam;
            processing = false;
            return;
        }

        if (!code || !state) {
            error = 'Missing authorization code or state parameter';
            processing = false;
            return;
        }

        const success = await auth.handleCallback(code, state);

        if (success) {
            // Redirect to main app
            goto('/');
        } else {
            processing = false;
            // Error is in auth store
            auth.subscribe(s => {
                if (s.error) error = s.error;
            })();
        }
    });
</script>

<div class="callback-container">
    {#if processing}
        <div class="processing">
            <div class="spinner"></div>
            <h2>Completing sign in...</h2>
            <p>Please wait while we authenticate you with Microsoft</p>
        </div>
    {:else if error}
        <div class="error-container">
            <div class="error-icon">⚠</div>
            <h2>Sign in failed</h2>
            <p class="error-message">{error}</p>
            <button on:click={() => goto('/')}>
                Back to Login
            </button>
        </div>
    {/if}
</div>

<style>
    .callback-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #0f0f1a 100%);
        padding: 2rem;
    }

    .processing,
    .error-container {
        text-align: center;
        max-width: 500px;
        padding: 3rem 2rem;
        background: rgba(10, 10, 10, 0.9);
        border: 1px solid rgba(0, 255, 65, 0.2);
        border-radius: 16px;
        box-shadow:
            0 0 40px rgba(0, 255, 65, 0.1),
            inset 0 0 60px rgba(0, 255, 65, 0.02);
    }

    .spinner {
        width: 50px;
        height: 50px;
        border: 3px solid rgba(0, 255, 65, 0.1);
        border-top-color: #00ff41;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto 2rem auto;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    h2 {
        font-size: 1.5rem;
        font-weight: 600;
        color: #e0e0e0;
        margin: 0 0 1rem 0;
    }

    p {
        color: #888;
        margin: 0;
        font-size: 0.95rem;
    }

    .error-container {
        border-color: rgba(255, 68, 68, 0.3);
        box-shadow:
            0 0 40px rgba(255, 68, 68, 0.1),
            inset 0 0 60px rgba(255, 68, 68, 0.02);
    }

    .error-icon {
        font-size: 3rem;
        color: #ff4444;
        margin-bottom: 1rem;
        text-shadow: 0 0 15px rgba(255, 68, 68, 0.5);
    }

    .error-message {
        color: #ff8888;
        padding: 1rem;
        background: rgba(255, 68, 68, 0.1);
        border: 1px solid rgba(255, 68, 68, 0.2);
        border-radius: 8px;
        margin: 1.5rem 0;
        font-size: 0.9rem;
    }

    button {
        margin-top: 1.5rem;
        padding: 0.75rem 2rem;
        background: #00ff41;
        border: none;
        border-radius: 10px;
        color: #000;
        font-size: 1rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }

    button:hover {
        box-shadow: 0 0 25px rgba(0, 255, 65, 0.5);
        transform: translateY(-2px);
    }

    button:active {
        transform: translateY(0);
    }
</style>
