<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Canvas } from '@threlte/core';
	import { session } from '$lib/stores/session';
	import ChatOverlay from '$lib/components/ChatOverlay.svelte';
	import Scene from '$lib/threlte/Scene.svelte';
	import CoreBrain from '$lib/threlte/CoreBrain.svelte';

	// Generate session ID on mount
	onMount(() => {
		const sessionId = crypto.randomUUID();
		session.init(sessionId);
	});

	onDestroy(() => {
		session.cleanup();
	});
</script>

<svelte:head>
	<title>Driscoll Intelligence</title>
	<meta name="description" content="Driscoll Intelligence - Your AI-powered assistant for company procedures and operations" />
</svelte:head>

<div class="app-container">
	<!-- 3D Background Scene -->
	<div class="scene-container">
		<Canvas>
			<Scene />
			<CoreBrain />
		</Canvas>
	</div>

	<!-- Ambient Glow Effects -->
	<div class="ambient-glow glow-1"></div>
	<div class="ambient-glow glow-2"></div>
	<div class="ambient-glow glow-3"></div>

	<!-- Scanlines overlay for that CRT feel -->
	<div class="scanlines"></div>

	<!-- The Chat Interface -->
	<ChatOverlay />
</div>

<style>
	.app-container {
		position: fixed;
		inset: 0;
		background: #050505;
		overflow: hidden;
	}

	/* 3D Scene Background */
	.scene-container {
		position: absolute;
		inset: 0;
		z-index: 1;
		opacity: 0.6;
	}

	/* Ambient Glow Effects */
	.ambient-glow {
		position: absolute;
		border-radius: 50%;
		filter: blur(80px);
		pointer-events: none;
		z-index: 2;
		opacity: 0.4;
	}

	.glow-1 {
		width: 600px;
		height: 600px;
		background: radial-gradient(circle, rgba(0, 255, 65, 0.15) 0%, transparent 70%);
		top: -200px;
		left: -200px;
		animation: drift-1 20s ease-in-out infinite;
	}

	.glow-2 {
		width: 500px;
		height: 500px;
		background: radial-gradient(circle, rgba(255, 0, 85, 0.1) 0%, transparent 70%);
		bottom: -150px;
		right: -150px;
		animation: drift-2 25s ease-in-out infinite;
	}

	.glow-3 {
		width: 400px;
		height: 400px;
		background: radial-gradient(circle, rgba(0, 255, 255, 0.08) 0%, transparent 70%);
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		animation: pulse-ambient 15s ease-in-out infinite;
	}

	@keyframes drift-1 {
		0%, 100% { transform: translate(0, 0); }
		33% { transform: translate(50px, 30px); }
		66% { transform: translate(-30px, 50px); }
	}

	@keyframes drift-2 {
		0%, 100% { transform: translate(0, 0); }
		33% { transform: translate(-40px, -30px); }
		66% { transform: translate(30px, -40px); }
	}

	@keyframes pulse-ambient {
		0%, 100% { opacity: 0.3; transform: translate(-50%, -50%) scale(1); }
		50% { opacity: 0.5; transform: translate(-50%, -50%) scale(1.1); }
	}

	/* CRT Scanlines */
	.scanlines {
		position: absolute;
		inset: 0;
		z-index: 3;
		pointer-events: none;
		background: repeating-linear-gradient(
			0deg,
			transparent,
			transparent 2px,
			rgba(0, 0, 0, 0.03) 2px,
			rgba(0, 0, 0, 0.03) 4px
		);
	}
</style>