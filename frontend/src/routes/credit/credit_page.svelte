<script lang="ts">
    import { goto } from '$app/navigation';
    import CreditForm from '$lib/components/CreditForm.svelte';
    import { credit } from '$lib/stores/credit';
    import CreditAmbientOrbs from '$lib/threlte/CreditAmbientOrbs.svelte';
    import { Canvas } from '@threlte/core';
    import { onMount } from 'svelte';
  
    let showForm = true;
  
    onMount(() => {
      // Initialize credit store if needed
      credit.reset();
    });
  
    function handleClose() {
      // Navigate back or close
      goto('/');
    }
  
    function handleComplete(e: CustomEvent<{ requestId: string }>) {
      const { requestId } = e.detail;
      // Success handling - could show toast, navigate, etc.
      console.log('Credit request submitted:', requestId);
      goto(`/credit/success?id=${requestId}`);
    }
  </script>
  
  <svelte:head>
    <title>Credit Request | Driscoll Intelligence</title>
  </svelte:head>
  
  <div class="credit-page">
    <!-- 3D Ambient Background -->
    <div class="ambient-layer">
      <Canvas>
        <CreditAmbientOrbs />
      </Canvas>
    </div>
  
    <!-- Subtle CSS glow accents -->
    <div class="glow-accent glow-top-left"></div>
    <div class="glow-accent glow-bottom-right"></div>
  
    <!-- The Form -->
    {#if showForm}
      <CreditForm
        on:close={handleClose}
        on:complete={handleComplete}
      />
    {/if}
  </div>
  
  <style>
    .credit-page {
      position: fixed;
      inset: 0;
      background: #050505;
      overflow: hidden;
    }
  
    /* 3D orbs behind everything */
    .ambient-layer {
      position: absolute;
      inset: 0;
      z-index: 1;
      opacity: 0.6;
      pointer-events: none;
    }
  
    /* CSS glow accents - cheap atmosphere */
    .glow-accent {
      position: absolute;
      border-radius: 50%;
      filter: blur(100px);
      pointer-events: none;
      z-index: 2;
    }
  
    .glow-top-left {
      width: 500px;
      height: 500px;
      background: radial-gradient(circle, rgba(0, 255, 65, 0.12) 0%, transparent 70%);
      top: -150px;
      left: -150px;
      animation: drift 25s ease-in-out infinite;
    }
  
    .glow-bottom-right {
      width: 400px;
      height: 400px;
      background: radial-gradient(circle, rgba(0, 255, 65, 0.08) 0%, transparent 70%);
      bottom: -100px;
      right: -100px;
      animation: drift 20s ease-in-out infinite reverse;
    }
  
    @keyframes drift {
      0%, 100% { transform: translate(0, 0); }
      50% { transform: translate(30px, 20px); }
    }
  </style>