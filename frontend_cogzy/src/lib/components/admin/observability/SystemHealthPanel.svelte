<!--
  SystemHealthPanel - Real-time system health gauges

  Displays: CPU, Memory, Disk, Process stats
-->

<script lang="ts">
    import { metricsSnapshot, systemHealth } from '$lib/stores/metrics';

    $: systemRaw = $metricsSnapshot?.system;
    // Handle case where system metrics return an error object
    $: system = systemRaw && !systemRaw.error ? systemRaw : null;
    $: systemError = systemRaw?.error || null;
    $: health = $systemHealth;

    function getHealthColor(status: string): string {
        switch (status) {
            case 'healthy': return '#00ff41';
            case 'warning': return '#ffc800';
            case 'degraded': return '#ff8c00';
            case 'critical': return '#ff0055';
            default: return '#666';
        }
    }

    function getGaugeColor(value: number): string {
        if (value > 90) return '#ff0055';
        if (value > 70) return '#ffc800';
        return '#00ff41';
    }
</script>

<div class="health-panel">
    <div class="panel-header">
        <h3>
            <span class="status-dot" style="background: {getHealthColor(health)}"></span>
            System Health
        </h3>
        <span class="status-text" style="color: {getHealthColor(health)}">
            {health.toUpperCase()}
        </span>
    </div>

    {#if system}
        <div class="gauges">
            <div class="gauge">
                <div class="gauge-label">CPU</div>
                <div class="gauge-bar">
                    <div
                        class="gauge-fill"
                        style="width: {system.cpu_percent}%; background: {getGaugeColor(system.cpu_percent)}"
                    ></div>
                </div>
                <div class="gauge-value">{system.cpu_percent.toFixed(1)}%</div>
            </div>

            <div class="gauge">
                <div class="gauge-label">Memory</div>
                <div class="gauge-bar">
                    <div
                        class="gauge-fill"
                        style="width: {system.memory_percent}%; background: {getGaugeColor(system.memory_percent)}"
                    ></div>
                </div>
                <div class="gauge-value">{system.memory_percent.toFixed(1)}%</div>
            </div>

            <div class="gauge">
                <div class="gauge-label">Disk</div>
                <div class="gauge-bar">
                    <div
                        class="gauge-fill"
                        style="width: {system.disk_percent}%; background: {getGaugeColor(system.disk_percent)}"
                    ></div>
                </div>
                <div class="gauge-value">{system.disk_percent.toFixed(1)}%</div>
            </div>
        </div>

        <div class="stats-row">
            <div class="stat">
                <span class="stat-value">{system.process_memory_mb.toFixed(0)}</span>
                <span class="stat-label">MB Process</span>
            </div>
            <div class="stat">
                <span class="stat-value">{system.process_threads}</span>
                <span class="stat-label">Threads</span>
            </div>
            <div class="stat">
                <span class="stat-value">{system.memory_used_gb.toFixed(1)}</span>
                <span class="stat-label">GB Used</span>
            </div>
        </div>
    {:else if systemError}
        <div class="error">System metrics unavailable: {systemError}</div>
    {:else}
        <div class="loading">Loading system metrics...</div>
    {/if}
</div>

<style>
    .health-panel {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(0, 255, 65, 0.3);
        border-radius: 8px;
        padding: 16px;
    }

    .panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }

    .panel-header h3 {
        margin: 0;
        font-size: 14px;
        color: #00ff41;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    .status-text {
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 1px;
    }

    .gauges {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .gauge {
        display: grid;
        grid-template-columns: 60px 1fr 50px;
        align-items: center;
        gap: 12px;
    }

    .gauge-label {
        font-size: 12px;
        color: #888;
    }

    .gauge-bar {
        height: 8px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 4px;
        overflow: hidden;
    }

    .gauge-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.3s ease;
    }

    .gauge-value {
        font-size: 12px;
        font-family: 'JetBrains Mono', monospace;
        color: #e0e0e0;
        text-align: right;
    }

    .stats-row {
        display: flex;
        justify-content: space-around;
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }

    .stat {
        text-align: center;
    }

    .stat-value {
        display: block;
        font-size: 18px;
        font-weight: 600;
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }

    .stat-label {
        font-size: 10px;
        color: #666;
        text-transform: uppercase;
    }

    .loading {
        color: #666;
        text-align: center;
        padding: 20px;
    }

    .error {
        color: #ff8c00;
        text-align: center;
        padding: 20px;
        font-size: 12px;
    }
</style>
