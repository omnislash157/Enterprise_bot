<!--
  System Observability Dashboard

  Real-time system health, RAG performance, LLM costs
-->

<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { metricsStore, metricsConnected, metricsSnapshot, metricsHistory } from '$lib/stores/metrics';
    import SystemHealthPanel from '$lib/components/admin/observability/SystemHealthPanel.svelte';
    import RagPerformancePanel from '$lib/components/admin/observability/RagPerformancePanel.svelte';
    import LlmCostPanel from '$lib/components/admin/observability/LlmCostPanel.svelte';
    import LineChart from '$lib/components/admin/charts/LineChart.svelte';
    import StateMonitor from '$lib/components/nervecenter/StateMonitor.svelte';

    let showStateMonitor = false;

    onMount(() => {
        metricsStore.connect();
    });

    onDestroy(() => {
        metricsStore.disconnect();
    });

    $: uptime = $metricsSnapshot?.uptime_seconds || 0;
    $: wsStats = $metricsSnapshot?.websocket;

    function formatUptime(seconds: number): string {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        return `${h}h ${m}m`;
    }
</script>

<svelte:head>
    <title>System Health | CogTwin Admin</title>
</svelte:head>

<div class="observability-page">
    <header class="page-header">
        <div class="header-left">
            <h1>System Observability</h1>
            <div class="connection-status" class:connected={$metricsConnected}>
                <span class="status-dot"></span>
                {$metricsConnected ? 'Live' : 'Disconnected'}
            </div>
        </div>
        <div class="header-right">
            <span class="uptime">Uptime: {formatUptime(uptime)}</span>
            <button class="toggle-btn" on:click={() => showStateMonitor = !showStateMonitor}>
                {showStateMonitor ? 'Hide' : 'Show'} State Monitor
            </button>
        </div>
    </header>

    <div class="dashboard-grid">
        <!-- Row 1: Health + WebSocket -->
        <div class="grid-item span-2">
            <SystemHealthPanel />
        </div>

        <div class="grid-item">
            <div class="ws-panel">
                <h3>🔌 WebSocket</h3>
                {#if wsStats}
                    <div class="ws-stats">
                        <div class="ws-stat">
                            <span class="value">{wsStats.connections_active}</span>
                            <span class="label">Active</span>
                        </div>
                        <div class="ws-stat">
                            <span class="value">{wsStats.messages_in.toLocaleString()}</span>
                            <span class="label">Messages In</span>
                        </div>
                        <div class="ws-stat">
                            <span class="value">{wsStats.messages_out.toLocaleString()}</span>
                            <span class="label">Messages Out</span>
                        </div>
                    </div>
                {/if}
            </div>
        </div>

        <!-- Row 2: RAG + LLM -->
        <div class="grid-item span-2">
            <RagPerformancePanel />
        </div>

        <div class="grid-item">
            <LlmCostPanel />
        </div>

        <!-- Row 3: Charts -->
        <div class="grid-item span-3">
            <div class="chart-panel">
                <h3>📈 System Resources (Last 5 min)</h3>
                <LineChart
                    labels={$metricsHistory.timestamps}
                    datasets={[
                        { label: 'CPU %', data: $metricsHistory.cpu, borderColor: '#ff0055' },
                        { label: 'Memory %', data: $metricsHistory.memory, borderColor: '#00ffff' },
                    ]}
                />
            </div>
        </div>

        <!-- Row 4: More Charts -->
        <div class="grid-item span-2">
            <div class="chart-panel">
                <h3>🧠 RAG Latency Trend</h3>
                <LineChart
                    labels={$metricsHistory.timestamps}
                    datasets={[
                        { label: 'Latency (ms)', data: $metricsHistory.ragLatency, borderColor: '#00ff41' },
                    ]}
                />
            </div>
        </div>

        <div class="grid-item">
            <div class="chart-panel">
                <h3>💾 Cache Hit Rate</h3>
                <LineChart
                    labels={$metricsHistory.timestamps}
                    datasets={[
                        { label: 'Hit Rate %', data: $metricsHistory.cacheHitRate, borderColor: '#ffc800' },
                    ]}
                />
            </div>
        </div>
    </div>

    {#if showStateMonitor}
        <div class="state-monitor-overlay">
            <StateMonitor />
        </div>
    {/if}
</div>

<style>
    .observability-page {
        padding: 24px;
        min-height: 100vh;
    }

    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
    }

    .header-left {
        display: flex;
        align-items: center;
        gap: 16px;
    }

    .page-header h1 {
        margin: 0;
        font-size: 24px;
        color: #e0e0e0;
    }

    .connection-status {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: #888;
    }

    .connection-status.connected {
        color: #00ff41;
    }

    .connection-status .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #888;
    }

    .connection-status.connected .status-dot {
        background: #00ff41;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    .header-right {
        display: flex;
        align-items: center;
        gap: 16px;
    }

    .uptime {
        font-size: 12px;
        color: #888;
        font-family: 'JetBrains Mono', monospace;
    }

    .toggle-btn {
        padding: 8px 16px;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        color: #e0e0e0;
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s;
    }

    .toggle-btn:hover {
        background: rgba(255, 255, 255, 0.15);
        border-color: #00ff41;
    }

    .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
    }

    .grid-item.span-2 {
        grid-column: span 2;
    }

    .grid-item.span-3 {
        grid-column: span 3;
    }

    .ws-panel, .chart-panel {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 16px;
        height: 100%;
    }

    .ws-panel h3, .chart-panel h3 {
        margin: 0 0 16px 0;
        font-size: 14px;
        color: #888;
    }

    .ws-stats {
        display: flex;
        justify-content: space-around;
    }

    .ws-stat {
        text-align: center;
    }

    .ws-stat .value {
        display: block;
        font-size: 24px;
        font-weight: 600;
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }

    .ws-stat .label {
        font-size: 10px;
        color: #666;
        text-transform: uppercase;
    }

    .state-monitor-overlay {
        position: fixed;
        bottom: 24px;
        right: 24px;
        width: 400px;
        z-index: 1000;
    }

    @media (max-width: 1024px) {
        .dashboard-grid {
            grid-template-columns: 1fr;
        }

        .grid-item.span-2,
        .grid-item.span-3 {
            grid-column: span 1;
        }
    }
</style>
