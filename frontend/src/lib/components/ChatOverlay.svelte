<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { session } from '$lib/stores/session';
	import { websocket } from '$lib/stores/websocket';
	import { auth, currentUser } from '$lib/stores/auth';
	import { voice, speakText, queueSentenceAudio, streamingSentenceDetector, clearAudioQueue, userLanguage, voiceSpeed } from '$lib/stores/voice';
	import { marked } from 'marked';
	import DepartmentSelector from './DepartmentSelector.svelte';
	import CheekyLoader from './CheekyLoader.svelte';
	import type { PhraseCategory } from '$lib/cheeky';

	// Configure marked
	marked.setOptions({
		breaks: true,
		gfm: true
	});

	// ========================================
	// CHEEKY PHASE MAPPING
	// ========================================
	function mapPhaseToCategory(phase: string): PhraseCategory {
		switch (phase) {
			case 'searching':
			case 'retrieval':
			case 'memory':
				return 'searching';
			case 'thinking':
			case 'reasoning':
			case 'synthesis':
				return 'thinking';
			case 'generating':
			case 'creating':
			case 'writing':
				return 'creating';
			case 'executing':
			case 'tool_use':
				return 'executing';
			default:
				return 'searching';
		}
	}

	// Reactive cheeky category based on cognitive state
	$: cheekyCategory = mapPhaseToCategory($session.cognitiveState.phase);

	// ========================================
	// INPUT STATE
	// ========================================
	let inputValue = '';
	let inputElement: HTMLTextAreaElement;
	let messagesContainer: HTMLDivElement;

	// ========================================
	// FILE UPLOAD STATE
	// ========================================
	let attachedFiles: Array<{file_id: string, file_name: string, file_size: number}> = [];
	let fileInput: HTMLInputElement;
	let uploadingFile = false;

	// ========================================
	// VOICE OUTPUT (TTS) STATE - Synchronized text/audio
	// ========================================
	let voiceMode = false;
	let sentenceBuffer = '';
	let previousStreamLength = 0;
	let voiceSyncedText = '';  // Text that has started playing (synced with audio)

	// ========================================
	// SETTINGS POPOVER STATE
	// ========================================
	let showSettings = false;

	function openFileDialog() {
		fileInput?.click();
	}

	async function handleFileSelect(event: Event) {
		const target = event.target as HTMLInputElement;
		const files = target.files;
		if (!files || files.length === 0) return;

		uploadingFile = true;

		for (const file of Array.from(files)) {
			try {
				const formData = new FormData();
				formData.append('file', file);
				formData.append('department', $session.currentDivision || 'warehouse');

				const response = await fetch('/api/upload/file', {
					method: 'POST',
					body: formData,
					headers: {
						'X-User-Email': $currentUser?.email || '',
					}
				});

				if (!response.ok) {
					const err = await response.json();
					throw new Error(err.detail || 'Upload failed');
				}

				const result = await response.json();
				attachedFiles = [...attachedFiles, result];
			} catch (err) {
				console.error('File upload failed:', err);
				// TODO: Show error toast
			}
		}

		uploadingFile = false;
		target.value = '';
	}

	function removeFile(file_id: string) {
		attachedFiles = attachedFiles.filter(f => f.file_id !== file_id);
	}

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
	// VOICE OUTPUT (TTS) - Synchronized text/audio streaming
	// ========================================
	let wasStreaming = false;

	// Process streaming chunks for sentence detection
	$: if (voiceMode && $session.currentStream) {
		const currentLength = $session.currentStream.length;
		if (currentLength > previousStreamLength) {
			// Extract new chunk
			const newChunk = $session.currentStream.slice(previousStreamLength);
			previousStreamLength = currentLength;

			// Detect complete sentences
			const { buffer: newBuffer, sentence } = streamingSentenceDetector(newChunk, sentenceBuffer);
			sentenceBuffer = newBuffer;

			if (sentence) {
				// Clean markdown and queue for TTS with sync callback
				const cleanSentence = sentence
					.replace(/[#*_`]/g, '')
					.trim();
				if (cleanSentence) {
					// Capture sentence and language for closure
					const sentenceToReveal = sentence;
					const lang = $userLanguage;
					queueSentenceAudio(cleanSentence, () => {
						// Callback fires when audio STARTS playing - reveal text
						voiceSyncedText += sentenceToReveal + ' ';
					}, lang);
				}
			}
		}
	}

	// Handle end of stream - speak any remaining buffer
	$: {
		if (wasStreaming && !$session.isStreaming && voiceMode) {
			// Flush remaining buffer
			if (sentenceBuffer.trim()) {
				const remainingText = sentenceBuffer;
				const cleanText = remainingText
					.replace(/\n__METADATA__:.*/s, '')
					.replace(/[#*_`]/g, '')
					.trim();
				if (cleanText) {
					const lang = $userLanguage;
					queueSentenceAudio(cleanText, () => {
						voiceSyncedText += remainingText;
					}, lang);
				}
			}
			// Reset for next message
			sentenceBuffer = '';
			previousStreamLength = 0;
		}
		wasStreaming = $session.isStreaming;
	}

	// ========================================
	// MESSAGE HANDLING
	// ========================================
	function sendMessage() {
		if (!inputValue.trim() || !$websocket.connected) return;

		// Clear any pending audio and synced text when sending new message
		clearAudioQueue();
		sentenceBuffer = '';
		previousStreamLength = 0;
		voiceSyncedText = '';

		const file_ids = attachedFiles.map(f => f.file_id);
		session.sendMessage(inputValue.trim(), file_ids);

		inputValue = '';
		attachedFiles = [];  // Clear after sending
		// Refocus input after sending
		tick().then(() => inputElement?.focus());
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			sendMessage();
		}
	}

	async function toggleRecording() {
		await voice.toggle();
	}

	// Reactive: when finalTranscript updates, append to input
	$: if ($voice.finalTranscript && $voice.finalTranscript.trim()) {
		inputValue = (inputValue + ' ' + $voice.finalTranscript).trim();
		voice.clearTranscript();
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
	// AUTH HANDLERS
	// ========================================
	function handleDepartmentChange(department: string) {
		// Use session store method to handle division change properly
		// This queues the change if not verified yet, or sends immediately if verified
		session.setDivision(department);
	}

	function handleLogout() {
		auth.logout();
		// Page will redirect to login via +layout.svelte
	}

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
						<svg class="logo-icon" viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
							<path d="M12 2L2 12l10 10 10-10L12 2zm0 3l7 7-7 7-7-7 7-7z"/>
						</svg>
						<h1>Driscoll Intelligence</h1>
					</div>
					<div class="header-center">
						<DepartmentSelector on:change={(e) => handleDepartmentChange(e.detail)} />
					</div>
					<div class="header-right">
						<div class="connection-indicator" class:connected={$websocket.connected}>
							<span class="pulse-dot"></span>
							<span class="status-text">
								{$websocket.connected ? 'Online' : 'Connecting...'}
							</span>
						</div>
						{#if $currentUser}
							<button class="logout-btn" on:click={handleLogout} title="Sign out">
								<span class="user-email">{$currentUser.email.split('@')[0]}</span>
								<svg class="logout-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>
							</button>
						{/if}
					</div>
				</header>

				<!-- Messages -->
				<div class="messages-area" bind:this={messagesContainer}>
					{#if $session.messages.length === 0 && !$session.currentStream}
						<div class="empty-state">
							<div class="empty-icon">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
									<path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
								</svg>
							</div>
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

					{#if $session.isStreaming && !$session.currentStream && !(voiceMode && voiceSyncedText)}
						<div class="cheeky-thinking">
							<CheekyLoader category={cheekyCategory} spinnerType="food" size="sm" />
						</div>
					{:else if $session.currentStream || (voiceMode && voiceSyncedText)}
							<div class="message assistant streaming">
								<div class="message-content">
									{#if voiceMode}
										<!-- Voice mode: show text synced with audio playback -->
										{@html marked.parse(voiceSyncedText || '')}
									{:else}
										<!-- Normal mode: show text as it streams -->
										{@html marked.parse($session.currentStream)}
									{/if}
								</div>
								<span class="typing-cursor"></span>
							</div>
						{/if}
					{/if}
				</div>

				<!-- Input Area -->
				<div class="input-area">
					{#if attachedFiles.length > 0}
						<div class="attached-files">
							{#each attachedFiles as file}
								<div class="file-chip">
									<span class="file-name">{file.file_name}</span>
									<button class="remove-file" on:click={() => removeFile(file.file_id)}>x</button>
								</div>
							{/each}
						</div>
					{/if}

					<div class="input-wrapper">
						<textarea
							bind:this={inputElement}
							bind:value={inputValue}
							placeholder="Ask about company procedures, policies, or operations..."
							disabled={!$websocket.connected}
							on:keydown={handleKeydown}
							rows="1"
						></textarea>

						<!-- Voice Input Button (STT) -->
						<button
							class="mic-button"
							class:recording={$voice.isRecording}
							on:click={toggleRecording}
							disabled={!$websocket.connected}
							aria-label={$voice.isRecording ? 'Stop recording' : 'Start voice input'}
							data-tooltip={$voice.isRecording ? 'Recording...' : 'Voice input'}
						>
							<svg viewBox="0 0 24 24" fill={$voice.isRecording ? 'currentColor' : 'none'} stroke="currentColor" stroke-width="2">
								<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
								<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
								<line x1="12" y1="19" x2="12" y2="23"/>
								<line x1="8" y1="23" x2="16" y2="23"/>
							</svg>
						</button>

						<!-- Voice Output Button (TTS) -->
						<button
							class="speaker-button"
							class:active={voiceMode}
							on:click={() => voiceMode = !voiceMode}
							aria-label={voiceMode ? 'Disable voice output' : 'Enable voice output'}
							title={voiceMode ? 'Voice output ON' : 'Voice output OFF'}
						>
							<svg viewBox="0 0 24 24" fill={voiceMode ? 'currentColor' : 'none'} stroke="currentColor" stroke-width="2">
								<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
								{#if voiceMode}
									<path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
									<path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
								{:else}
									<line x1="23" y1="9" x2="17" y2="15"/>
									<line x1="17" y1="9" x2="23" y2="15"/>
								{/if}
							</svg>
						</button>

						<!-- Settings Button + Popover -->
						<div class="settings-container">
							<button
								class="settings-button"
								class:active={showSettings}
								on:click={() => showSettings = !showSettings}
								aria-label="Voice settings"
								title="Voice settings"
							>
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<circle cx="12" cy="12" r="3"/>
									<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
								</svg>
							</button>

							{#if showSettings}
								<div class="settings-popover">
									<!-- Language Toggle -->
									<div class="setting-row">
										<span class="setting-label">Language</span>
										<button
											class="lang-toggle"
											on:click={() => userLanguage.toggle()}
										>
											<span class="lang-option" class:active={$userLanguage === 'en'}>EN</span>
											<span class="lang-option" class:active={$userLanguage === 'es'}>ES</span>
										</button>
									</div>

									<!-- Speed Slider -->
									<div class="setting-row">
										<span class="setting-label">Speed</span>
										<div class="speed-control">
											<input
												type="range"
												min="0.75"
												max="2"
												step="0.05"
												value={$voiceSpeed}
												on:input={(e) => voiceSpeed.set(parseFloat(e.currentTarget.value))}
												class="speed-slider"
											/>
											<span class="speed-value">{$voiceSpeed.toFixed(2)}x</span>
										</div>
									</div>
								</div>
							{/if}
						</div>

						<!-- File Upload Button -->
						<button
							class="file-button"
							class:has-files={attachedFiles.length > 0}
							class:uploading={uploadingFile}
							on:click={openFileDialog}
							disabled={!$websocket.connected || uploadingFile}
							aria-label="Attach files"
						>
							{#if uploadingFile}
								<svg class="spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<circle cx="12" cy="12" r="10" stroke-dasharray="30 70"/>
								</svg>
							{:else}
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
								</svg>
							{/if}
							{#if attachedFiles.length > 0}
								<span class="file-count">{attachedFiles.length}</span>
							{/if}
						</button>

						<!-- Hidden file input -->
						<input
							type="file"
							bind:this={fileInput}
							on:change={handleFileSelect}
							accept=".pdf,.docx,.xlsx,.txt,.csv,.png,.jpg,.jpeg"
							multiple
							style="display: none;"
						/>

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

					{#if $voice.transcript}
						<div class="voice-preview">{$voice.transcript}</div>
					{/if}
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

	.header-center {
		display: flex;
		align-items: center;
	}

	.header-right {
		display: flex;
		align-items: center;
		gap: 1rem;
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

	.logout-btn {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.35rem 0.75rem;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 6px;
		color: #888;
		font-size: 0.8rem;
		cursor: pointer;
		transition: all 0.2s;
	}

	.logout-btn:hover {
		background: rgba(255, 68, 68, 0.1);
		border-color: rgba(255, 68, 68, 0.3);
		color: #ff4444;
	}

	.user-email {
		max-width: 100px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.logout-icon {
		font-size: 0.9rem;
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
		transform: translateZ(0);
		-webkit-overflow-scrolling: touch;
		overscroll-behavior: contain;
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

	.cheeky-thinking {
		align-self: flex-start;
		max-width: 85%;
		animation: message-in 0.3s ease-out;
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
		width: 2px;
		height: 1em;
		background: #00ff41;
		animation: blink 0.8s step-end infinite;
		margin-left: 2px;
		vertical-align: text-bottom;
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

	/* Voice Input Button */
	.mic-button {
		width: 56px;
		height: 56px;
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(0, 255, 65, 0.3);
		color: #00ff41;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
		flex-shrink: 0;
		position: relative;
	}

	.mic-button:hover:not(:disabled):not(.recording) {
		background: rgba(0, 255, 65, 0.1);
		border-color: #00ff41;
		box-shadow: 0 0 20px rgba(0, 255, 65, 0.3);
		transform: scale(1.02);
	}

	.mic-button.recording {
		background: rgba(255, 0, 64, 0.15);
		border-color: #ff0040;
		color: #ff0040;
		animation: pulse-recording 1.5s ease-in-out infinite;
	}

	.mic-button:disabled {
		background: #333;
		color: #666;
		cursor: not-allowed;
		border-color: #333;
	}

	.mic-button svg {
		width: 22px;
		height: 22px;
	}

	@keyframes pulse-recording {
		0%, 100% {
			box-shadow: 0 0 20px rgba(255, 0, 64, 0.4);
			transform: scale(1);
		}
		50% {
			box-shadow: 0 0 30px rgba(255, 0, 64, 0.6);
			transform: scale(1.05);
		}
	}

	/* Voice Output Button (TTS) */
	.speaker-button {
		width: 56px;
		height: 56px;
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(0, 255, 65, 0.3);
		color: #00ff41;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
		flex-shrink: 0;
		position: relative;
	}

	.speaker-button:hover {
		background: rgba(0, 255, 65, 0.1);
		border-color: #00ff41;
		box-shadow: 0 0 20px rgba(0, 255, 65, 0.3);
		transform: scale(1.02);
	}

	.speaker-button.active {
		background: rgba(0, 255, 65, 0.15);
		border-color: #00ff41;
		box-shadow: 0 0 15px rgba(0, 255, 65, 0.4);
	}

	.speaker-button svg {
		width: 22px;
		height: 22px;
	}

	/* Settings Button + Popover */
	.settings-container {
		position: relative;
	}

	.settings-button {
		width: 56px;
		height: 56px;
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(0, 255, 65, 0.3);
		color: #00ff41;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
		flex-shrink: 0;
	}

	.settings-button:hover {
		background: rgba(0, 255, 65, 0.1);
		border-color: #00ff41;
		box-shadow: 0 0 20px rgba(0, 255, 65, 0.3);
		transform: scale(1.02);
	}

	.settings-button.active {
		background: rgba(0, 255, 65, 0.15);
		border-color: #00ff41;
		box-shadow: 0 0 15px rgba(0, 255, 65, 0.4);
	}

	.settings-button svg {
		width: 22px;
		height: 22px;
	}

	.settings-popover {
		position: absolute;
		bottom: calc(100% + 0.75rem);
		right: 0;
		min-width: 200px;
		background: rgba(10, 10, 10, 0.95);
		border: 1px solid rgba(0, 255, 65, 0.3);
		border-radius: 12px;
		padding: 1rem;
		box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
		z-index: 1000;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.setting-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}

	.setting-label {
		color: #888;
		font-size: 0.85rem;
		font-weight: 500;
	}

	/* Language Toggle Pills */
	.lang-toggle {
		display: flex;
		background: rgba(0, 0, 0, 0.4);
		border: 1px solid rgba(0, 255, 65, 0.2);
		border-radius: 8px;
		padding: 2px;
		cursor: pointer;
	}

	.lang-option {
		padding: 0.35rem 0.6rem;
		font-size: 0.8rem;
		font-weight: 600;
		color: #666;
		border-radius: 6px;
		transition: all 0.2s;
	}

	.lang-option.active {
		background: rgba(0, 255, 65, 0.2);
		color: #00ff41;
	}

	/* Speed Slider */
	.speed-control {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.speed-slider {
		width: 80px;
		height: 4px;
		-webkit-appearance: none;
		appearance: none;
		background: rgba(0, 255, 65, 0.2);
		border-radius: 2px;
		outline: none;
		cursor: pointer;
	}

	.speed-slider::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 14px;
		height: 14px;
		background: #00ff41;
		border-radius: 50%;
		cursor: pointer;
		box-shadow: 0 0 8px rgba(0, 255, 65, 0.5);
	}

	.speed-slider::-moz-range-thumb {
		width: 14px;
		height: 14px;
		background: #00ff41;
		border: none;
		border-radius: 50%;
		cursor: pointer;
		box-shadow: 0 0 8px rgba(0, 255, 65, 0.5);
	}

	.speed-value {
		color: #00ff41;
		font-size: 0.8rem;
		font-weight: 600;
		min-width: 40px;
		text-align: right;
	}

	/* Voice Preview (interim transcript) */
	.voice-preview {
		padding: 0.75rem 1rem;
		background: rgba(0, 0, 0, 0.9);
		border: 1px solid rgba(0, 255, 65, 0.3);
		border-radius: 8px;
		margin-top: 0.5rem;
		color: #00ff41;
		font-size: 0.9rem;
		font-style: italic;
	}

	/* Tooltip */
	.mic-button[data-tooltip]:hover::before {
		content: attr(data-tooltip);
		position: absolute;
		bottom: calc(100% + 0.5rem);
		left: 50%;
		transform: translateX(-50%);
		padding: 0.5rem 0.75rem;
		background: rgba(0, 0, 0, 0.9);
		border: 1px solid rgba(0, 255, 65, 0.3);
		border-radius: 6px;
		font-size: 0.75rem;
		color: #e0e0e0;
		white-space: nowrap;
		pointer-events: none;
		z-index: 1000;
	}

	.input-hint {
		margin: 0.5rem 0 0 0;
		font-size: 0.75rem;
		color: #555;
		text-align: center;
	}

	/* ========================================
	   FILE UPLOAD
	   ======================================== */
	.file-button {
		width: 56px;
		height: 56px;
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(0, 255, 65, 0.3);
		color: #00ff41;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
		flex-shrink: 0;
		position: relative;
	}

	.file-button:hover:not(:disabled) {
		background: rgba(0, 255, 65, 0.1);
		border-color: #00ff41;
	}

	.file-button.has-files {
		background: rgba(0, 255, 65, 0.15);
	}

	.file-button.uploading {
		opacity: 0.7;
	}

	.file-button:disabled {
		background: #333;
		color: #666;
		cursor: not-allowed;
		border-color: #333;
	}

	.file-button svg {
		width: 22px;
		height: 22px;
	}

	.file-button .spinner {
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.file-count {
		position: absolute;
		top: -4px;
		right: -4px;
		background: #00ff41;
		color: #000;
		font-size: 0.7rem;
		font-weight: 600;
		width: 18px;
		height: 18px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.attached-files {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
		background: rgba(0, 0, 0, 0.3);
		border-bottom: 1px solid rgba(0, 255, 65, 0.15);
	}

	.file-chip {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.4rem 0.75rem;
		background: rgba(0, 255, 65, 0.1);
		border: 1px solid rgba(0, 255, 65, 0.3);
		border-radius: 8px;
		font-size: 0.85rem;
		color: #e0e0e0;
	}

	.file-name {
		max-width: 150px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.remove-file {
		background: none;
		border: none;
		color: #ff4444;
		font-size: 1.2rem;
		cursor: pointer;
		padding: 0;
		line-height: 1;
	}

	.remove-file:hover {
		color: #ff6666;
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