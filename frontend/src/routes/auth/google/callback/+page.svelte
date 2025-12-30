<script lang="ts">
    import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { personalAuthStore } from '$lib/stores/personalAuth';

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

        const result = await personalAuthStore.completeGoogleLogin(code, state);

        if (result.success) {
            goto('/');
        } else {
            error = result.error || 'Login failed';
        }
    });
</script>

<div class="min-h-screen flex items-center justify-center bg-gray-900">
    <div class="text-center">
        {#if error}
            <div class="bg-red-900/50 border border-red-500 rounded-lg p-6 max-w-md">
                <h2 class="text-xl font-semibold text-red-400 mb-2">Authentication Failed</h2>
                <p class="text-gray-300">{error}</p>
                <a href="/login" class="mt-4 inline-block text-blue-400 hover:underline">
                    Try again
                </a>
            </div>
        {:else}
            <div class="animate-pulse">
                <div class="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                <p class="mt-4 text-gray-400">Completing sign in...</p>
            </div>
        {/if}
    </div>
</div>
