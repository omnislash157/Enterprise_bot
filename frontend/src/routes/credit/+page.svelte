<script lang="ts">
    import { onMount } from 'svelte';
    import { Canvas } from '@threlte/core';
    import { goto } from '$app/navigation';
    import CreditForm from '$lib/components/CreditForm.svelte';
    import CreditAmbientOrbs from '$lib/threlte/CreditAmbientOrbs.svelte';
    import { credit } from '$lib/stores/credit';

    onMount(() => {
        // Reset credit form state on mount
        credit.reset();
    });

    function handleClose() {
        goto('/');
    }

    function handleComplete(event: CustomEvent<{ requestId: string }>) {
        // Show success state briefly, then redirect
        setTimeout(() => {
            goto('/');
        }, 2000);
    }
</script>

<svelte:head>
    <title>Credit Request - Driscoll Intelligence</title>
</svelte:head>

<div class="credit-page">
    <!-- Subtle 3D Background -->
    <div class="scene-container">
        <Canvas>
            <CreditAmbientOrbs />
        </Canvas>
    </div>

    <!-- Ambient Glows - softer than chat page -->
    <div class="ambient-glow glow-cyan"></div>
    <div class="ambient-glow glow-green"></div>

    <!-- Page Header -->
    <header class="page-header">
        <div class="header-content">
            <h1 class="page-title">
                <span class="title-icon">📋</span>
                Credit Request
            </h1>
            <p class="page-subtitle">
                Submit customer credit requests for processing
            </p>
        </div>
    </header>

    <!-- Credit Form Container -->
    <div class="form-container">
        <CreditForm
            standalone={true}
            on:close={handleClose}
            on:complete={handleComplete}
        />
    </div>
</div>

<style>
    .credit-page {
        position: fixed;
        top: 56px;
        left: 0;
        right: 0;
        bottom: 0;

        background: linear-gradient(135deg, #0a0a0f 0%, #0f1015 100%);
        overflow-y: auto;
    }

    .scene-container {
        position: fixed;
        top: 56px;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 0;
        opacity: 0.4;
        pointer-events: none;
    }

    .ambient-glow {
        position: fixed;
        border-radius: 50%;
        filter: blur(100px);
        pointer-events: none;
        z-index: 1;
    }

    .glow-cyan {
        width: 500px;
        height: 500px;
        background: radial-gradient(circle, rgba(0, 200, 255, 0.12) 0%, transparent 70%);
        top: 10%;
        right: -100px;
        animation: float-1 25s ease-in-out infinite;
    }

    .glow-green {
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(0, 255, 65, 0.1) 0%, transparent 70%);
        bottom: 10%;
        left: -100px;
        animation: float-2 30s ease-in-out infinite;
    }

    @keyframes float-1 {
        0%, 100% { transform: translate(0, 0); }
        50% { transform: translate(-30px, 20px); }
    }

    @keyframes float-2 {
        0%, 100% { transform: translate(0, 0); }
        50% { transform: translate(20px, -30px); }
    }

    .page-header {
        position: relative;
        z-index: 10;
        padding: 2rem 2rem 0;
    }

    .header-content {
        max-width: 1200px;
        margin: 0 auto;
    }

    .page-title {
        display: flex;
        align-items: center;
        gap: 0.75rem;

        font-size: 1.75rem;
        font-weight: 600;
        color: #fff;
        margin: 0;
    }

    .title-icon {
        font-size: 1.5rem;
    }

    .page-subtitle {
        margin: 0.5rem 0 0;
        color: rgba(255, 255, 255, 0.5);
        font-size: 0.95rem;
    }

    .form-container {
        position: relative;
        z-index: 10;
        padding: 1.5rem 2rem 2rem;
        max-width: 1400px;
        margin: 0 auto;
    }

    /* Mobile adjustments */
    @media (max-width: 768px) {
        .page-header {
            padding: 1.5rem 1rem 0;
        }

        .page-title {
            font-size: 1.4rem;
        }

        .form-container {
            padding: 1rem;
        }
    }
</style>
