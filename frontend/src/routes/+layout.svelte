<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { fade } from 'svelte/transition';
	import { page } from '$app/stores';
	import { theme } from '$lib/stores/theme';
	import { loadConfig, configLoading } from '$lib/stores/config';
	import { auth, isAuthenticated, authInitialized, authLoading } from '$lib/stores/auth';
	import Login from '$lib/components/Login.svelte';
	import IntelligenceRibbon from '$lib/components/ribbon/IntelligenceRibbon.svelte';
	import ToastProvider from '$lib/components/ToastProvider.svelte';
	import ConnectionStatus from '$lib/components/ConnectionStatus.svelte';
	
	// Static import - Svelte will handle SSR correctly
	import AmbientBackground from '$lib/threlte/AmbientBackground.svelte';

	// Allow callback page to render without auth
	$: isAuthCallback = $page.url.pathname.startsWith('/auth/');

	// Track route changes for transitions
	$: key = $page.url.pathname;

	// Show ambient only when authenticated and in browser
	$: showAmbient = browser && $isAuthenticated;

	onMount(async () => {
		const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
		loadConfig(apiBase).catch(console.warn);

		if (!isAuthCallback) {
			await auth.init();
		} else {
			auth.markInitialized();
		}
	});
</script>

<!-- Persistent Ambient Background Layer - only in browser when authenticated -->
{#if showAmbient}
	<AmbientBackground />
{/if}

{#if isAuthCallback}
	<slot />
{:else if $configLoading || !$authInitialized}
	<div class="loading-screen">
		<div class="spinner"></div>
		<p>{$authLoading ? 'Authenticating...' : 'Loading...'}</p>
	</div>
{:else if !$isAuthenticated}
	<Login />
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

	/* Normie mode - handled in AmbientBackground if needed */
</style>