<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { theme } from '$lib/stores/theme';
	import { loadConfig } from '$lib/stores/config';

	onMount(async () => {
		// Load config from backend in background (non-blocking)
		const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
		loadConfig(apiBase).catch(console.warn);
	});
</script>

<div class:normie-mode={$theme === 'normie'}>
	<slot />
</div>

<style>
	div {
		min-height: 100vh;
	}
</style>