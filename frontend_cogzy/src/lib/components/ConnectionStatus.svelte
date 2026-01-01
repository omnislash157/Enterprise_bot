<script lang="ts">
	import { session } from '$lib/stores/session';

	$: state = $session.connectionState;
	$: attempts = $session.reconnectAttempts;
	$: maxAttempts = 5;

	$: statusText = {
		'connecting': 'Connecting...',
		'connected': '',
		'reconnecting': `Reconnecting... (${attempts}/${maxAttempts})`,
		'disconnected': 'Disconnected'
	}[state];

	$: statusColor = {
		'connecting': 'text-yellow-400',
		'connected': 'text-green-400',
		'reconnecting': 'text-orange-400',
		'disconnected': 'text-red-400'
	}[state];
</script>

{#if state !== 'connected'}
	<div class="fixed top-0 left-0 right-0 z-50 bg-gray-900/95 border-b border-gray-700 px-4 py-2">
		<div class="flex items-center justify-center gap-2 text-sm {statusColor}">
			{#if state === 'reconnecting'}
				<svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
				</svg>
			{/if}
			<span>{statusText}</span>
			{#if state === 'disconnected'}
				<button
					class="ml-2 px-2 py-1 bg-cyan-600 hover:bg-cyan-500 rounded text-white text-xs"
					on:click={() => window.location.reload()}
				>
					Reload
				</button>
			{/if}
		</div>
	</div>
{/if}
