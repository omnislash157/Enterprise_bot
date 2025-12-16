<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { theme } from '$lib/stores/theme';
	import { loadConfig, configLoading } from '$lib/stores/config';
	import { auth, isAuthenticated, authInitialized, authLoading } from '$lib/stores/auth';
	import Login from '$lib/components/Login.svelte';

	onMount(async () => {
		// Load config
		const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
		loadConfig(apiBase).catch(console.warn);

		// Try to restore auth session
		await auth.restore();
	});
</script>

{#if $configLoading || !$authInitialized}
	<div class="loading-screen">
		<div class="spinner"></div>
		<p>{$authLoading ? 'Authenticating...' : 'Loading...'}</p>
	</div>
{:else if !$isAuthenticated}
	<Login />
{:else}
	<div class:normie-mode={$theme === 'normie'}>
		<slot />
	</div>
{/if}

<style>
	div {
		min-height: 100vh;
	}

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
