<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { fade } from 'svelte/transition';
	import { page } from '$app/stores';
	import { theme } from '$lib/stores/theme';
	import { loadConfig, configLoading } from '$lib/stores/config';
	import { auth, isAuthenticated, authInitialized, authLoading } from '$lib/stores/auth';
	import { tenant, tenantLoading } from '$lib/stores/tenant';
	import CogzySplash from '$lib/components/Cogzysplash.svelte';
	import IntelligenceRibbon from '$lib/components/ribbon/IntelligenceRibbon.svelte';
	import ToastProvider from '$lib/components/ToastProvider.svelte';
	import ConnectionStatus from '$lib/components/ConnectionStatus.svelte';

	// NO static import of AmbientBackground - it contains Canvas which breaks SSR
	let AmbientBackground: any = null;

	// Allow callback page to render without auth
	$: isAuthCallback = $page.url.pathname.startsWith('/auth/');

	// Track route changes for transitions
	$: key = $page.url.pathname;

	// Show ambient only when component loaded and authenticated
	$: showAmbient = AmbientBackground && $isAuthenticated;

	onMount(async () => {
		const apiBase = import.meta.env.VITE_API_URL || 'https://lucky-love-production.up.railway.app';

		// Load tenant first (determines auth config)
		await tenant.load();

		// Then load config and init auth
		loadConfig(apiBase).catch(console.warn);

		if (!isAuthCallback) {
			await auth.init();
		} else {
			auth.markInitialized();
		}

		// Dynamic import ONLY in browser - prevents SSR crash
		if (browser) {
			try {
				const module = await import('$lib/threlte/AmbientBackground.svelte');
				AmbientBackground = module.default;
			} catch (err) {
				console.warn('[Layout] Failed to load AmbientBackground:', err);
			}
		}
	});
</script>

<!-- Persistent Ambient Background Layer - dynamically loaded, SSR-safe -->
{#if showAmbient}
	<svelte:component this={AmbientBackground} />
{/if}

{#if isAuthCallback}
	<slot />
{:else if $tenantLoading || $configLoading || !$authInitialized}
	<div class="loading-screen">
		<div class="spinner"></div>
		<p>{$tenantLoading ? 'Loading tenant...' : $authLoading ? 'Authenticating...' : 'Loading...'}</p>
	</div>
{:else if !$isAuthenticated}
	<CogzySplash />
{:else}
	<!-- AUTHENTICATED: Show Ribbon + Content -->
	<div class="app-shell" class:normie-mode={$theme === 'normie'}>
		<!-- Connection status indicator -->
		<ConnectionStatus />

		<IntelligenceRibbon />

		{#key key}
			<main class="main-content" in:fade={{ duration: 150, delay: 50 }} out:fade={{ duration: 100 }}>
				<slot />
			</main>
		{/key}

		<!-- Global toast notifications -->
		<ToastProvider />
	</div>
{/if}

<style>
	/* Ensure content is above ambient layer */
	.app-shell {
		position: relative;
		z-index: 1;
		min-height: 100vh;
	}

	.main-content {
		/* Account for fixed ribbon height */
		padding-top: 56px;
		min-height: 100vh;
	}

	/* Loading screen styles */
	.loading-screen {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
		color: #888;
	}

	.loading-screen .spinner {
		width: 40px;
		height: 40px;
		border: 3px solid rgba(255, 255, 255, 0.1);
		border-top-color: #00ff88;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
		margin-bottom: 1rem;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}
</style>
