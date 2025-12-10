<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { theme, toggleTheme } from '$lib/stores/theme';
	import { websocket } from '$lib/stores/websocket';
	import { session } from '$lib/stores/session';
	import { visibleArtifacts, panels, closedPanels } from '$lib/stores';
	import ArtifactPane from '$lib/components/ArtifactPane.svelte';
	import FloatingPanel from '$lib/components/FloatingPanel.svelte';
	import { marked } from 'marked';

	// Configure marked for safe inline rendering
	marked.setOptions({
		breaks: true,
		gfm: true
	});

	// Local input state
	let inputValue = '';

	// Generate session ID on mount
	onMount(() => {
		const sessionId = crypto.randomUUID();
		session.init(sessionId);
	});

	onDestroy(() => {
		session.cleanup();
	});

	// Send message handler
	function sendMessage() {
		if (!inputValue.trim() || !$websocket.connected) return;

		// Send message with local input value
		session.sendMessage(inputValue.trim());
		inputValue = '';
	}

	// Panel label map for closed panels menu (enterprise: chat + artifacts only)
	const panelLabels: Record<string, { label: string; icon: string }> = {
		chat: { label: 'Chat', icon: '💬' },
		artifacts: { label: 'Artifacts', icon: '📦' }
	};

	// Filter closed panels to only show enterprise-relevant ones
	$: enterpriseClosedPanels = $closedPanels.filter(id => id === 'chat' || id === 'artifacts');
</script>

<svelte:head>
	<title>Driscoll Assistant</title>
</svelte:head>

<div class="dashboard">
	<!-- Header -->
	<header class="header">
		<div class="logo">
			<span class="glow-text font-mono text-xl">DRISCOLL</span>
			<span class="text-text-muted text-sm ml-2">Assistant</span>
		</div>

		<div class="header-controls">
			<!-- Closed panels menu -->
			{#if enterpriseClosedPanels.length > 0}
				<div class="closed-panels-menu">
					{#each enterpriseClosedPanels as panelId}
						<button
							class="btn restore-btn"
							on:click={() => panels.open(panelId)}
							title="Restore {panelLabels[panelId]?.label}"
						>
							{panelLabels[panelId]?.icon} {panelLabels[panelId]?.label}
						</button>
					{/each}
				</div>
			{/if}

			<div class="connection-status" class:connected={$websocket.connected}>
				<span class="status-dot"></span>
				<span class="text-sm">{$websocket.connected ? 'Connected' : 'Disconnected'}</span>
			</div>

			<button class="btn" on:click={toggleTheme} title="Toggle theme">
				{$theme === 'cyber' ? '👔' : '🌙'}
			</button>

			<!-- Reset layout button -->
			<button class="btn" on:click={() => panels.reset()} title="Reset panel layout">
				⟲
			</button>
		</div>
	</header>

	<!-- Main Content -->
	<main class="dashboard-main">
		<!-- Right side container for docked panels -->
		<div class="right-panels" class:has-docked={$panels.chat.mode === 'docked' || $panels.artifacts.mode === 'docked'}>
			<!-- Chat Panel -->
			<FloatingPanel panelId="chat" title="Chat" icon="💬">
				<div class="chat-section">
					<div class="messages-container">
						{#each $session.messages as message}
							<div class="message {message.role}">
								<div class="message-content">{@html marked.parse(message.content)}</div>
							</div>
						{/each}
						{#if $session.currentStream}
							<div class="message assistant streaming">
								<div class="message-content">{@html marked.parse($session.currentStream)}</div>
								<span class="cursor">▊</span>
							</div>
						{/if}
					</div>
					<form class="chat-input" on:submit|preventDefault={sendMessage}>
						<input
							type="text"
							bind:value={inputValue}
							placeholder="Ask about company procedures..."
							disabled={!$websocket.connected}
							on:keydown={(e) => e.key === 'Enter' && sendMessage()}
						/>
						<button type="submit" disabled={!$websocket.connected || !inputValue.trim()}>
							Send
						</button>
					</form>
				</div>
			</FloatingPanel>

			<!-- Artifacts Panel -->
			<FloatingPanel panelId="artifacts" title="Artifacts ({$visibleArtifacts.length})" icon="📦">
				<div class="artifacts-section">
					<div class="artifact-list">
						{#each $visibleArtifacts as item (item.id)}
							<ArtifactPane {item} />
						{/each}
						{#if $visibleArtifacts.length === 0}
							<p class="empty">No artifacts yet.</p>
						{/if}
					</div>
				</div>
			</FloatingPanel>
		</div>
	</main>

	<!-- Bottom: Status Bar -->
	<footer class="status-bar">
		<div class="status-item">
			<span class="text-text-muted">Mode:</span>
			<span class="text-neon-green font-mono">Enterprise</span>
		</div>
		<div class="status-item">
			<span class="text-text-muted">Session:</span>
			<span class="font-mono">{$websocket.sessionId || 'none'}</span>
		</div>
	</footer>
</div>

<style>
	.dashboard {
		display: flex;
		flex-direction: column;
		height: 100vh;
		padding: 1rem;
		gap: 1rem;
		overflow: hidden;
	}

	.header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.5rem 1rem;
		background: var(--bg-secondary);
		border: 1px solid var(--border-dim);
		border-radius: 8px;
		flex-shrink: 0;
	}

	.logo {
		display: flex;
		align-items: baseline;
	}

	.header-controls {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.closed-panels-menu {
		display: flex;
		gap: 0.5rem;
	}

	.restore-btn {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.25rem 0.5rem;
		background: var(--bg-tertiary);
		border: 1px solid var(--neon-cyan, #00ffff);
		color: var(--neon-cyan, #00ffff);
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.75rem;
		transition: all 0.2s;
	}

	.restore-btn:hover {
		background: var(--neon-cyan, #00ffff);
		color: black;
	}

	.connection-status {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--text-muted);
	}

	.connection-status.connected {
		color: var(--neon-green);
	}

	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--text-muted);
	}

	.connection-status.connected .status-dot {
		background: var(--neon-green);
		box-shadow: 0 0 10px var(--neon-green);
	}

	.dashboard-main {
		display: flex;
		flex: 1;
		gap: 1rem;
		overflow: hidden;
		min-height: 0;
		justify-content: center;
	}

	.right-panels {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		width: 100%;
		max-width: 800px;
		flex-shrink: 0;
		min-height: 0;
	}

	.right-panels:not(.has-docked) {
		display: none;
	}

	.right-panels > :global(.floating-panel.mode-docked) {
		flex: 1;
		min-height: 0;
	}

	/* Hide docked panels container content when panels are floating/closed */
	.right-panels > :global(.floating-panel.mode-floating),
	.right-panels > :global(.floating-panel.mode-fullscreen),
	.right-panels > :global(.floating-panel.mode-closed) {
		position: fixed;
	}

	.chat-section {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 200px;
	}

	.messages-container {
		flex: 1;
		overflow-y: auto;
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.artifacts-section {
		height: 100%;
		min-height: 150px;
	}

	.artifact-list {
		height: 100%;
		overflow-y: auto;
		padding: 0.75rem;
	}

	.empty {
		color: var(--text-muted, #888);
		text-align: center;
		padding: 2rem 1rem;
		font-size: 0.875rem;
	}

	.message {
		padding: 0.75rem 1rem;
		border-radius: 8px;
		max-width: 85%;
	}

	.message.user {
		background: var(--bg-tertiary);
		align-self: flex-end;
		border: 1px solid var(--border-dim);
	}

	.message.assistant {
		background: var(--bg-secondary);
		align-self: flex-start;
		border: 1px solid var(--border-glow);
	}

	.message.streaming .cursor {
		animation: blink 1s infinite;
		color: var(--neon-green);
	}

	@keyframes blink {
		0%, 50% { opacity: 1; }
		51%, 100% { opacity: 0; }
	}

	.chat-input {
		display: flex;
		gap: 0.5rem;
		padding: 0.75rem;
		border-top: 1px solid var(--border-dim);
		flex-shrink: 0;
	}

	.chat-input input {
		flex: 1;
	}

	.status-bar {
		display: flex;
		gap: 2rem;
		padding: 0.5rem 1rem;
		background: var(--bg-secondary);
		border: 1px solid var(--border-dim);
		border-radius: 8px;
		flex-shrink: 0;
	}

	.status-item {
		display: flex;
		gap: 0.5rem;
		font-size: 0.875rem;
	}
</style>
