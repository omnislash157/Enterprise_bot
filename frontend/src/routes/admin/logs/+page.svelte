<!--
  Log Viewer - Searchable logs with real-time streaming
-->

<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { observabilityStore, logs } from '$lib/stores/observability';

    let filters = {
        hours: 24,
        level: '',
        search: '',
        trace_id: '',
    };

    let streaming = false;

    onMount(() => {
        observabilityStore.loadLogs(filters);
    });

    onDestroy(() => {
        observabilityStore.disconnectLogStream();
    });

    function applyFilters() {
        observabilityStore.loadLogs(filters);
    }

    function toggleStreaming() {
        if (streaming) {
            observabilityStore.disconnectLogStream();
        } else {
            observabilityStore.connectLogStream();
        }
        streaming = !streaming;
    }

    function getLevelColor(level: string): string {
        switch (level) {
            case 'DEBUG': return '#888';
            case 'INFO': return '#00ff41';
            case 'WARNING': return '#ffc800';
            case 'ERROR': return '#ff0055';
            case 'CRITICAL': return '#ff0000';
            default: return '#e0e0e0';
        }
    }

    function filterByTrace(traceId: string) {
        filters.trace_id = traceId;
        applyFilters();
    }
</script>

<svelte:head>
    <title>Logs | CogTwin Admin</title>
</svelte:head>

<div class="logs-page">
    <header class="page-header">
        <h1>Structured Logs</h1>
        <div class="controls">
            <button
                class="stream-btn"
                class:active={streaming}
                on:click={toggleStreaming}
            >
                {streaming ? 'Pause' : 'Stream Live'}
            </button>
        </div>
    </header>

    <div class="filters">
        <select bind:value={filters.level} on:change={applyFilters}>
            <option value="">All Levels</option>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
            <option value="CRITICAL">CRITICAL</option>
        </select>

        <input
            type="text"
            placeholder="Search logs..."
            bind:value={filters.search}
            on:keyup={(e) => e.key === 'Enter' && applyFilters()}
        />

        <input
            type="text"
            placeholder="Trace ID..."
            bind:value={filters.trace_id}
            on:keyup={(e) => e.key === 'Enter' && applyFilters()}
        />

        <button class="apply-btn" on:click={applyFilters}>Apply</button>

        {#if filters.trace_id}
            <button class="clear-btn" on:click={() => { filters.trace_id = ''; applyFilters(); }}>
                Clear Trace Filter
            </button>
        {/if}
    </div>

    <div class="log-container">
        <div class="log-header">
            <span class="col-time">Time</span>
            <span class="col-level">Level</span>
            <span class="col-logger">Logger</span>
            <span class="col-message">Message</span>
            <span class="col-trace">Trace</span>
        </div>

        <div class="log-list">
            {#each $logs as log}
                <div class="log-row" class:error={log.level === 'ERROR' || log.level === 'CRITICAL'}>
                    <span class="col-time">
                        {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                    <span class="col-level" style="color: {getLevelColor(log.level)}">
                        {log.level}
                    </span>
                    <span class="col-logger">{log.logger_name.split('.').pop()}</span>
                    <span class="col-message">{log.message}</span>
                    <span class="col-trace">
                        {#if log.trace_id}
                            <button class="trace-link" on:click={() => filterByTrace(log.trace_id)}>
                                {log.trace_id.slice(0, 8)}...
                            </button>
                        {/if}
                    </span>
                </div>
            {/each}

            {#if $logs.length === 0}
                <div class="empty">No logs found</div>
            {/if}
        </div>
    </div>
</div>

<style>
    .logs-page {
        padding: 24px;
        height: 100%;
        display: flex;
        flex-direction: column;
    }

    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }

    .page-header h1 {
        margin: 0;
        font-size: 24px;
        color: #e0e0e0;
    }

    .stream-btn {
        padding: 8px 16px;
        background: rgba(0, 255, 65, 0.1);
        border: 1px solid rgba(0, 255, 65, 0.3);
        border-radius: 6px;
        color: #00ff41;
        cursor: pointer;
        transition: all 0.2s;
    }

    .stream-btn.active {
        background: rgba(0, 255, 65, 0.2);
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }

    .filters {
        display: flex;
        gap: 12px;
        margin-bottom: 16px;
    }

    .filters select, .filters input {
        padding: 8px 12px;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        color: #e0e0e0;
        font-size: 13px;
    }

    .filters input[type="text"] {
        flex: 1;
    }

    .apply-btn, .clear-btn {
        padding: 8px 16px;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        color: #e0e0e0;
        cursor: pointer;
    }

    .clear-btn {
        background: rgba(255, 0, 85, 0.1);
        border-color: rgba(255, 0, 85, 0.3);
        color: #ff4444;
    }

    .log-container {
        flex: 1;
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }

    .log-header, .log-row {
        display: grid;
        grid-template-columns: 100px 80px 120px 1fr 100px;
        padding: 10px 16px;
        gap: 12px;
        font-size: 12px;
        font-family: 'JetBrains Mono', monospace;
    }

    .log-header {
        background: rgba(255, 255, 255, 0.05);
        color: #888;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }

    .log-list {
        flex: 1;
        overflow-y: auto;
    }

    .log-row {
        border-bottom: 1px solid rgba(255, 255, 255, 0.03);
        color: #e0e0e0;
    }

    .log-row.error {
        background: rgba(255, 0, 85, 0.05);
    }

    .col-time {
        color: #666;
    }

    .col-logger {
        color: #888;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .col-message {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .trace-link {
        background: none;
        border: none;
        color: #00ffff;
        cursor: pointer;
        font-family: inherit;
        font-size: inherit;
    }

    .trace-link:hover {
        text-decoration: underline;
    }

    .empty {
        padding: 40px;
        text-align: center;
        color: #666;
    }
</style>
