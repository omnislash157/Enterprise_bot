<script lang="ts">
    import { onMount } from 'svelte';
    import { loadTenantConfig, tenantConfig, tenantLoading } from '$lib/stores/tenant';
    import '../app.css';

    onMount(() => {
        loadTenantConfig();
    });
</script>

<svelte:head>
    <title>{$tenantConfig?.branding?.title || 'Cogzy'}</title>
</svelte:head>

{#if $tenantLoading}
    <div class="loading-screen">
        <div class="spinner"></div>
    </div>
{:else}
    <div class="app">
        <slot />
    </div>
{/if}

<style>
    .app {
        min-height: 100vh;
        background: var(--color-background, linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%));
    }

    .loading-screen {
        position: fixed;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--color-background, #050505);
    }

    .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid rgba(0, 255, 65, 0.2);
        border-top-color: var(--color-primary, #00ff41);
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }
</style>
