<!--
  NerveCenterWidget - 3D visualization widget for the dashboard

  Wraps the Threlte canvas and connects to analytics store
-->

<script lang="ts">
    import { Canvas } from '@threlte/core';
    import { categories, overview } from '$lib/stores/analytics';
    import NerveCenterScene from '../threlte/NerveCenterScene.svelte';

    export let height: string = '400px';
</script>

<div class="nerve-center-widget" style="height: {height}">
    <div class="widget-header">
        <h3 class="text-sm font-semibold text-[#00ff41]">
            <span class="pulse-dot"></span>
            NEURAL ACTIVITY
        </h3>
        <span class="text-xs text-[#808080]">Query flow visualization</span>
    </div>

    <div class="canvas-container">
        <Canvas>
            <NerveCenterScene
                categories={$categories}
                totalQueries={$overview?.total_queries ?? 0}
                activeUsers={$overview?.active_users ?? 0}
            />
        </Canvas>
    </div>
</div>

<style>
    .nerve-center-widget {
        background: var(--bg-secondary);
        border: 1px solid var(--border-dim);
        border-radius: 8px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }

    .widget-header {
        padding: 12px 16px;
        border-bottom: 1px solid var(--border-dim);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .canvas-container {
        flex: 1;
        min-height: 0;
    }

    .pulse-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        background: #00ff41;
        border-radius: 50%;
        margin-right: 8px;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%,
        100% {
            opacity: 1;
            box-shadow: 0 0 0 0 rgba(0, 255, 65, 0.7);
        }
        50% {
            opacity: 0.7;
            box-shadow: 0 0 0 4px rgba(0, 255, 65, 0);
        }
    }
</style>
