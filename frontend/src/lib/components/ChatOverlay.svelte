<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { session } from '$lib/stores/session';
	import { websocket } from '$lib/stores/websocket';
	import { marked } from 'marked';

	// Configure marked
	marked.setOptions({
		breaks: true,
		gfm: true
	});

	// ========================================
	// INPUT STATE
	// ========================================
	let inputValue = '';
	let inputElement: HTMLTextAreaElement;
	let messagesContainer: HTMLDivElement;

	// ========================================
	// 3D ROTATION STATE (The Fun Part)
	// ========================================
	let rotateX = 0;
	let rotateY = 0;
	let velocityX = 0;
	let velocityY = 0;
	let isDragging = false;
	let dragStartX = 0;
	let dragStartY = 0;
	let lastMouseX = 0;
	let lastMouseY = 0;
	let animationFrame: number | null = null;

	// Spring physics constants - tuned for satisfying snap-back
	const SPRING_STIFFNESS = 0.08;   // How hard it pulls back
	const DAMPING = 0.82;            // Energy loss per frame (lower = more bouncy)
	const VELOCITY_SCALE = 0.4;      // How much mouse movement affects rotation
	const SETTLE_THRESHOLD = 0.5;    // When to stop animating

	// ========================================
	// AUTO-SCROLL
	// ========================================
	$: if ($session.messages.length || $session.currentStream) {
		tick().then(() => {
			if (messagesContainer) {
				messagesContainer.scrollTo({
					top: messagesContainer.scrollHeight,
					behavior: 'smooth'
				});
			}
		});
	}

	// ========================================
	// MESSAGE HANDLING
	// ========================================
	function sendMessage() {
		if (!inputValue.trim() || !$websocket.connected) return;
		session.sendMessage(inputValue.trim());
		inputValue = '';
		// Refocus input after sending
		tick().then(() => inputElement?.focus());
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			sendMessage();
		}
	}

	// ========================================
	// 3D ROTATION HANDLERS
	// ========================================
	function handlePointerDown(e: PointerEvent) {
		// Only activate with Shift+click or middle mouse button
		if (!e.shiftKey && e.button !== 1) return;
		
		e.preventDefault();
		isDragging = true;
		dragStartX = e.clientX;
		dragStartY = e.clientY;
		lastMouseX = e.clientX;
		lastMouseY = e.clientY;
		
		// Stop any ongoing spring animation
		if (animationFrame) {
			cancelAnimationFrame(animationFrame);
			animationFrame = null;
		}
		
		// Capture pointer for smooth tracking
		(e.target as HTMLElement).setPointerCapture(e.pointerId);
	}

	function handlePointerMove(e: PointerEvent) {
		if (!isDragging) return;
		
		// Calculate velocity from movement
		const deltaX = e.clientX - lastMouseX;
		const deltaY = e.clientY - lastMouseY;
		
		// Update rotation (Y rotation from X movement, X rotation from Y movement)
		rotateY += deltaX * VELOCITY_SCALE;
		rotateX -= deltaY * VELOCITY_SCALE;
		
		// Clamp to prevent going too crazy (but allow full flip)
		rotateX = Math.max(-180, Math.min(180, rotateX));
		rotateY = Math.max(-180, Math.min(180, rotateY));
		
		// Store velocity for spring release
		velocityX = -deltaY * VELOCITY_SCALE;
		velocityY = deltaX * VELOCITY_SCALE;
		
		lastMouseX = e.clientX;
		lastMouseY = e.clientY;
	}

	function handlePointerUp(e: PointerEvent) {
		if (!isDragging) return;
		
		isDragging = false;
		(e.target as HTMLElement).releasePointerCapture(e.pointerId);
		
		// Start spring animation back to neutral
		animateSpringBack();
	}

	function animateSpringBack() {
		function step() {
			// Spring force pulls toward 0
			const forceX = -SPRING_STIFFNESS * rotateX;
			const forceY = -SPRING_STIFFNESS * rotateY;
			
			// Apply force to velocity
			velocityX += forceX;
			velocityY += forceY;
			
			// Apply damping
			velocityX *= DAMPING;
			velocityY *= DAMPING;
			
			// Update position
			rotateX += velocityX;
			rotateY += velocityY;
			
			// Check if settled
			const totalEnergy = 
				Math.abs(rotateX) + Math.abs(rotateY) + 
				Math.abs(velocityX) + Math.abs(velocityY);
			
			if (totalEnergy < SETTLE_THRESHOLD) {
				// Snap to neutral
				rotateX = 0;
				rotateY = 0;
				velocityX = 0;
				velocityY = 0;
				animationFrame = null;
				return;
			}
			
			animationFrame = requestAnimationFrame(step);
		}
		
		animationFrame = requestAnimationFrame(step);
	}

	// ========================================
	// LIFECYCLE
	// ========================================
	onMount(() => {
		// Focus input on mount
		inputElement?.focus();
		
		return () => {
			if (animationFrame) {
				cancelAnimationFrame(animationFrame);
			}
		};
	});

	// ========================================
	// COMPUTED
	// ========================================
	$: isFlipped = Math.abs(rotateY) > 90 || Math.abs(rotateX) > 90;
	$: cardStyle = `transform: rotateX(${rotateX}deg) rotateY(${rotateY}deg);`;
	
	// Dynamic shadow based on rotation (adds depth)
	$: shadowX = rotateY * 0.3;
	$: shadowY = rotateX * 0.3;
	$: shadowStyle = `filter: drop-shadow(${shadowX}px ${shadowY}px 30px rgba(0, 255, 65, 0.15));`;
</script>

<div class="chat-overlay-container">
	<div class="perspective-wrapper" style={shadowStyle}>
		<div 
			class="chat-card"
			class:dragging={isDragging}
			class:flipped={isFlipped}
			style={cardStyle}
			on:pointerdown={handlePointerDown}
			on:pointermove={handlePointerMove}
			on:pointerup={handlePointerUp}
			on:pointercancel={handlePointerUp}
			role="application"
			aria-label="Chat interface"
		>
			<!-- ====== FRONT FACE: THE CHAT ====== -->
			<div class="card-face card-front">
				<!-- Header -->
				<header class="chat-header">
					<div class="header-left">
						<span class="logo-icon">◈</span>
						<h1>Driscoll Intelligence</h1>
					</div>
					<div class="header-right">
						<div class="connection-indicator" class:connected={$websocket.connected}>
							<span class="pulse-dot"></span>
							<span class="status-text">
								{$websocket.connected ? 'Online' : 'Connecting...'}
							</span>
						</div>
					</div>
				</header>

				<!-- Messages -->
				<div class="messages-area" bind:this={messagesContainer}>
					{#if $session.messages.length === 0 && !$session.currentStream}
						<div class="empty-state">
							<div class="empty-icon">◇</div>
							<p>Ask me anything about company procedures, policies, or operations.</p>
							<p class="hint">I'm here to help you navigate Driscoll systems.</p>
						</div>
					{:else}
						{#each $session.messages as message (message.timestamp)}
							<div class="message {message.role}">
								<div class="message-content">
									{@html marked.parse(message.content)}
								</div>
							</div>
						{/each}
						
						{#if $session.currentStream}
							<div class="message assistant streaming">
								<div class="message-content">
									{@html marked.parse($session.currentStream)}
								</div>
								<span class="typing-cursor">▊</span>
							</div>
						{/if}
					{/if}
				</div>

				<!-- Input Area -->
				<div class="input-area">
					<div class="input-wrapper">
						<textarea
							bind:this={inputElement}
							bind:value={inputValue}
							placeholder="Ask about company procedures, policies, or operations..."
							disabled={!$websocket.connected}
							on:keydown={handleKeydown}
							rows="1"
						></textarea>
						<button 
							class="send-button"
							on:click={sendMessage}
							disabled={!$websocket.connected || !inputValue.trim()}
							aria-label="Send message"
						>
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" />
							</svg>
						</button>
					</div>
					<p class="input-hint">Press Enter to send, Shift+Enter for new line</p>
				</div>
			</div>

			<!-- ====== BACK FACE: THE SHINING ====== -->
			<div class="card-face card-back">
				<div class="shining-container">
					<div class="typewriter-hell">
						<!-- The obsessive, manic repetition -->
						{#each Array(47) as _, i}
							<p class="shining-line variant-{i % 7}" style="--delay: {i * 0.02}s">
								{#if i === 23}
									<span class="redrum">REDRUM</span>
								{:else if i % 11 === 0}
									all work and no play makes jack a dull boy all work and no play makes jack a dull boy all work and no play
								{:else if i % 7 === 0}
									All work and no play makes Jack a dull boy.
								{:else if i % 5 === 0}
									ALL WORK AND NO PLAY MAKES JACK A DULL BOY
								{:else if i % 3 === 0}
									    All work and no play makes Jack a dull boy.
								{:else if i % 2 === 0}
									All work and no play makes Jack a dull boy
								{:else}
									all work and no play makes jack a dull boy
								{/if}
							</p>
						{/each}
					</div>
					<div class="shining-overlay"></div>
				</div>
			</div>
		</div>
	</div>

	<!-- Rotation hint (only shows when hovering near edges) -->
	<div class="rotation-hint" class:visible={!isDragging}>
		<span>Shift + drag to rotate</span>
	</div>
</div>

<style>
	/* ========================================
	   CONTAINER & PERSPECTIVE
	   ======================================== */
	.chat-overlay-container {
		position: fixed;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 2rem;
		pointer-events: none;
		z-index: 100;
	}

	.perspective-wrapper {
		perspective: 2000px;
		perspective-origin: center center;
		width: 100%;
		max-width: 900px;
		height: calc(100vh - 8rem);
		max-height: 800px;
		pointer-events: auto;
	}

	/* ========================================
	   THE CARD (3D Transform Container)
	   ======================================== */
	.chat-card {
		position: relative;
		width: 100%;
		height: 100%;
		transform-style: preserve-3d;
		transition: filter 0.3s ease;
		cursor: default;
	}

	.chat-card.dragging {
		cursor: grabbing;
	}

	.chat-card:not(.dragging):hover {
		cursor: grab;
	}

	/* ========================================
	   CARD FACES (Front & Back)
	   ======================================== */
	.card-face {
		position: absolute;
		inset: 0;
		backface-visibility: hidden;
		border-radius: 16px;
		overflow: hidden;
	}

	/* ========================================
	   FRONT FACE: THE CHAT
	   ======================================== */
	.card-front {
		display: flex;
		flex-direction: column;
		background: rgba(10, 10, 10, 0.85);
		backdrop-filter: blur(20px);
		border: 1px solid rgba(0, 255, 65, 0.2);
		box-shadow: 
			0 0 40px rgba(0, 255, 65, 0.1),
			inset 0 0 60px rgba(0, 255, 65, 0.03);
	}

	/* Header */
	.chat-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem 1.5rem;
		border-bottom: 1px solid rgba(0, 255, 65, 0.15);
		background: rgba(0, 0, 0, 0.3);
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.logo-icon {
		font-size: 1.5rem;
		color: #00ff41;
		text-shadow: 0 0 10px #00ff41;
	}

	.chat-header h1 {
		font-size: 1.25rem;
		font-weight: 600;
		color: #e0e0e0;
		margin: 0;
		letter-spacing: 0.5px;
	}

	.connection-indicator {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: #666;
		font-size: 0.8rem;
	}

	.connection-indicator.connected {
		color: #00ff41;
	}

	.pulse-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: currentColor;
	}

	.connection-indicator.connected .pulse-dot {
		animation: pulse-glow 2s ease-in-out infinite;
		box-shadow: 0 0 8px currentColor;
	}

	@keyframes pulse-glow {
		0%, 100% { opacity: 0.6; transform: scale(1); }
		50% { opacity: 1; transform: scale(1.1); }
	}

	/* Messages Area */
	.messages-area {
		flex: 1;
		overflow-y: auto;
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
		scroll-behavior: smooth;
	}

	.empty-state {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
		color: #666;
		gap: 0.75rem;
	}

	.empty-icon {
		font-size: 3rem;
		color: #00ff41;
		opacity: 0.5;
		margin-bottom: 0.5rem;
	}

	.empty-state p {
		margin: 0;
		max-width: 400px;
		line-height: 1.6;
	}

	.empty-state .hint {
		font-size: 0.85rem;
		opacity: 0.7;
	}

	/* Messages */
	.message {
		max-width: 85%;
		animation: message-in 0.3s ease-out;
	}

	@keyframes message-in {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.message.user {
		align-self: flex-end;
	}

	.message.assistant {
		align-self: flex-start;
	}

	.message-content {
		padding: 1rem 1.25rem;
		border-radius: 12px;
		line-height: 1.6;
		font-size: 0.95rem;
	}

	.message.user .message-content {
		background: rgba(0, 255, 65, 0.1);
		border: 1px solid rgba(0, 255, 65, 0.3);
		color: #e0e0e0;
	}

	.message.assistant .message-content {
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(255, 255, 255, 0.1);
		color: #d0d0d0;
	}

	.message.streaming .typing-cursor {
		display: inline-block;
		color: #00ff41;
		animation: blink 0.8s step-end infinite;
		margin-left: 2px;
	}

	@keyframes blink {
		0%, 100% { opacity: 1; }
		50% { opacity: 0; }
	}

	/* Markdown styling within messages */
	.message-content :global(p) {
		margin: 0.5rem 0;
	}

	.message-content :global(p:first-child) {
		margin-top: 0;
	}

	.message-content :global(p:last-child) {
		margin-bottom: 0;
	}

	.message-content :global(code) {
		background: rgba(0, 255, 65, 0.1);
		padding: 0.15rem 0.4rem;
		border-radius: 4px;
		font-family: 'JetBrains Mono', 'Fira Code', monospace;
		font-size: 0.85em;
		color: #00ff41;
	}

	.message-content :global(pre) {
		background: rgba(0, 0, 0, 0.4);
		border: 1px solid rgba(0, 255, 65, 0.2);
		border-radius: 8px;
		padding: 1rem;
		overflow-x: auto;
		margin: 0.75rem 0;
	}

	.message-content :global(pre code) {
		background: transparent;
		padding: 0;
		color: #e0e0e0;
	}

	.message-content :global(ul),
	.message-content :global(ol) {
		margin: 0.5rem 0;
		padding-left: 1.5rem;
	}

	.message-content :global(li) {
		margin: 0.25rem 0;
	}

	.message-content :global(strong) {
		color: #00ff41;
		font-weight: 600;
	}

	.message-content :global(a) {
		color: #00ffff;
		text-decoration: underline;
	}

	/* Input Area */
	.input-area {
		padding: 1rem 1.5rem 1.25rem;
		border-top: 1px solid rgba(0, 255, 65, 0.15);
		background: rgba(0, 0, 0, 0.3);
	}

	.input-wrapper {
		display: flex;
		gap: 0.75rem;
		align-items: flex-end;
	}

	.input-wrapper textarea {
		flex: 1;
		background: rgba(0, 0, 0, 0.5);
		border: 1px solid rgba(0, 255, 65, 0.3);
		border-radius: 12px;
		padding: 1rem 1.25rem;
		color: #e0e0e0;
		font-size: 1rem;
		font-family: inherit;
		resize: none;
		min-height: 56px;
		max-height: 150px;
		line-height: 1.5;
		transition: border-color 0.2s, box-shadow 0.2s;
	}

	.input-wrapper textarea:focus {
		outline: none;
		border-color: #00ff41;
		box-shadow: 0 0 20px rgba(0, 255, 65, 0.2);
	}

	.input-wrapper textarea::placeholder {
		color: #555;
	}

	.input-wrapper textarea:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.send-button {
		width: 56px;
		height: 56px;
		border-radius: 12px;
		background: #00ff41;
		border: none;
		color: #000;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
		flex-shrink: 0;
	}

	.send-button:hover:not(:disabled) {
		background: #00ff41;
		box-shadow: 0 0 25px rgba(0, 255, 65, 0.5);
		transform: scale(1.02);
	}

	.send-button:active:not(:disabled) {
		transform: scale(0.98);
	}

	.send-button:disabled {
		background: #333;
		color: #666;
		cursor: not-allowed;
	}

	.send-button svg {
		width: 22px;
		height: 22px;
	}

	.input-hint {
		margin: 0.5rem 0 0 0;
		font-size: 0.75rem;
		color: #555;
		text-align: center;
	}

	/* ========================================
	   BACK FACE: THE SHINING
	   ======================================== */
	.card-back {
		transform: rotateY(180deg);
		background: #0a0a0a;
		border: 1px solid #1a1a1a;
	}

	.shining-container {
		position: relative;
		width: 100%;
		height: 100%;
		overflow: hidden;
		padding: 2rem;
	}

	.typewriter-hell {
		font-family: 'Courier New', Courier, monospace;
		font-size: 0.9rem;
		line-height: 1.8;
		color: #00ff41;
		text-shadow: 0 0 5px rgba(0, 255, 65, 0.5);
		animation: subtle-flicker 4s ease-in-out infinite;
	}

	@keyframes subtle-flicker {
		0%, 100% { opacity: 0.9; }
		50% { opacity: 1; }
		73% { opacity: 0.85; }
		77% { opacity: 0.95; }
	}

	.shining-line {
		margin: 0;
		white-space: nowrap;
		overflow: hidden;
		animation: type-in 0.1s ease-out forwards;
		animation-delay: var(--delay, 0s);
		opacity: 0;
	}

	@keyframes type-in {
		from { opacity: 0; }
		to { opacity: 1; }
	}

	/* Variations to simulate manic typing */
	.shining-line.variant-0 {
		text-align: left;
	}

	.shining-line.variant-1 {
		text-align: center;
	}

	.shining-line.variant-2 {
		text-indent: 4rem;
	}

	.shining-line.variant-3 {
		text-align: right;
		padding-right: 2rem;
	}

	.shining-line.variant-4 {
		letter-spacing: 0.3em;
	}

	.shining-line.variant-5 {
		text-transform: uppercase;
		font-size: 0.8rem;
	}

	.shining-line.variant-6 {
		text-indent: 8rem;
		color: rgba(0, 255, 65, 0.7);
	}

	.redrum {
		color: #ff0040;
		text-shadow: 0 0 10px rgba(255, 0, 64, 0.8);
		font-weight: bold;
		letter-spacing: 0.5em;
		animation: redrum-pulse 1s ease-in-out infinite;
	}

	@keyframes redrum-pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.5; }
	}

	/* CRT-style overlay */
	.shining-overlay {
		position: absolute;
		inset: 0;
		pointer-events: none;
		background: 
			repeating-linear-gradient(
				0deg,
				transparent,
				transparent 2px,
				rgba(0, 0, 0, 0.15) 2px,
				rgba(0, 0, 0, 0.15) 4px
			);
	}

	/* ========================================
	   ROTATION HINT
	   ======================================== */
	.rotation-hint {
		position: fixed;
		bottom: 2rem;
		left: 50%;
		transform: translateX(-50%);
		padding: 0.5rem 1rem;
		background: rgba(0, 0, 0, 0.7);
		border: 1px solid rgba(0, 255, 65, 0.3);
		border-radius: 20px;
		color: #666;
		font-size: 0.75rem;
		opacity: 0;
		transition: opacity 0.3s;
		pointer-events: none;
	}

	.chat-overlay-container:hover .rotation-hint.visible {
		opacity: 1;
	}

	/* ========================================
	   SCROLLBAR
	   ======================================== */
	.messages-area::-webkit-scrollbar {
		width: 6px;
	}

	.messages-area::-webkit-scrollbar-track {
		background: transparent;
	}

	.messages-area::-webkit-scrollbar-thumb {
		background: rgba(0, 255, 65, 0.3);
		border-radius: 3px;
	}

	.messages-area::-webkit-scrollbar-thumb:hover {
		background: rgba(0, 255, 65, 0.5);
	}

	/* ========================================
	   RESPONSIVE
	   ======================================== */
	@media (max-width: 768px) {
		.chat-overlay-container {
			padding: 1rem;
		}

		.perspective-wrapper {
			height: calc(100vh - 4rem);
		}

		.chat-header h1 {
			font-size: 1rem;
		}

		.input-wrapper textarea {
			font-size: 0.95rem;
			padding: 0.875rem 1rem;
		}

		.send-button {
			width: 48px;
			height: 48px;
		}
	}
</style>
