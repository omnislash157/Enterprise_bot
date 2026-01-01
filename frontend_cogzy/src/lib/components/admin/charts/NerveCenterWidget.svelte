<!--
  NerveCenterWidget - 3D visualization widget for the dashboard

  Wraps the Threlte canvas and connects to analytics store
  Displays rotating memory graph with department usage and query intents
-->

<script lang="ts">
    import { Canvas } from '@threlte/core';
    import { analyticsStore } from '$lib/stores/analytics';
    import NerveCenterScene from '../threlte/NerveCenterScene.svelte';

    export let height: string = '500px';

    // Extract memoryGraphData from store
    $: memoryGraphData = $analyticsStore.memoryGraphData;
    $: categories = memoryGraphData?.categories || [];
    $: departments = memoryGraphData?.departments || [];
    $: intents = memoryGraphData?.intents || [];
    $: overview = memoryGraphData?.overview || { active_users: 0, total_queries: 0 };
</script>

<div class="nerve-center-widget" style="height: {height}">
    <div class="widget-header">
        <div class="header-title">
            <h3>
                <span class="pulse-dot"></span>
                NERVE CENTER - ROTATING MEMORY GRAPH
            </h3>
        </div>
        <div class="header-stats">
            <span class="stat">{overview.total_queries} queries</span>
            <span class="stat-divider">|</span>
            <span class="stat">{overview.active_users} active users</span>
        </div>
    </div>

    <div class="canvas-container">
        <Canvas>
            <NerveCenterScene
                {categories}
                departmentUsage={departments}
                queryIntents={intents}
                totalQueries={overview.total_queries}
                activeUsers={overview.active_users}
                temporalPatterns={memoryGraphData?.temporal_patterns}
            />
        </Canvas>
    </div>

    <!-- Enhanced Legend -->
    <div class="legend">
        <div class="legend-section">
            <h4>Inner Sphere: Query Categories</h4>
            <p>Size = query volume | Color = category type</p>
        </div>
        <div class="legend-section">
            <h4>Outer Orbit (Rotating): Department Memory</h4>
            <p>Size = inferred usage | Color = complexity (cyan=simple, red=complex)</p>
        </div>
        <div class="legend-section">
            <h4>Flow Lines: Query Journey</h4>
            <p>Shows how query categories map to department contexts</p>
        </div>
    </div>
</div>

<style>
    .nerve-center-widget {
        background: rgba(0, 0, 0, 0.8);
        border: 1px solid #00ff41;
        border-radius: 8px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }

    .widget-header {
        padding: 12px 16px;
        border-bottom: 1px solid rgba(0, 255, 65, 0.3);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .header-title h3 {
        color: #00ff41;
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
        font-weight: 600;
        margin: 0;
        letter-spacing: 0.05em;
    }

    .header-stats {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .stat {
        color: #00ffff;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
    }

    .stat-divider {
        color: #00ff41;
        opacity: 0.5;
    }

    .canvas-container {
        flex: 1;
        min-height: 0;
    }

    .legend {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        padding: 1rem;
        border-top: 1px solid rgba(0, 255, 65, 0.3);
        background: rgba(0, 0, 0, 0.4);
    }

    .legend-section h4 {
        color: #00ff41;
        font-family: 'Courier New', monospace;
        font-size: 0.75rem;
        font-weight: 600;
        margin: 0 0 0.25rem 0;
        letter-spacing: 0.05em;
    }

    .legend-section p {
        color: #888;
        font-size: 0.7rem;
        margin: 0;
        line-height: 1.4;
    }

    .pulse-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        background: #00ff41;
        border-radius: 50%;
        margin-right: 8px;
        vertical-align: middle;
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

    /* Responsive layout for smaller screens */
    @media (max-width: 768px) {
        .legend {
            grid-template-columns: 1fr;
            gap: 0.75rem;
        }

        .header-stats {
            flex-direction: column;
            gap: 0.25rem;
            align-items: flex-end;
        }

        .stat-divider {
            display: none;
        }
    }
</style>
