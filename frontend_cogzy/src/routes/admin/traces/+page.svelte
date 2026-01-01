<!--
  Trace Viewer - Distributed tracing waterfall
-->

<script lang="ts">
    import { onMount } from 'svelte';
    import { observabilityStore, traces, selectedTrace } from '$lib/stores/observability';

    let filters = {
        hours: 24,
        status: '',
        min_duration_ms: 0,
    };

    onMount(() => {
        observabilityStore.loadTraces(filters);
    });

    function applyFilters() {
        observabilityStore.loadTraces(filters);
    }

    function selectTrace(traceId: string) {
        observabilityStore.loadTrace(traceId);
    }

    function getStatusColor(status: string): string {
        switch (status) {
            case 'completed': return '#00ff41';
            case 'error': return '#ff0055';
            default: return '#ffc800';
        }
    }

    function formatDuration(ms: number): string {
        if (ms < 1000) return `${ms.toFixed(0)}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    }

    // Calculate span position for waterfall
    function getSpanStyle(span: any, trace: any): string {
        if (!trace.duration_ms) return '';
        const start = new Date(span.start_time).getTime() - new Date(trace.start_time).getTime();
        const left = (start / trace.duration_ms) * 100;
        const width = (span.duration_ms / trace.duration_ms) * 100;
        return `left: ${left}%; width: ${Math.max(width, 1)}%;`;
    }

    function getSpanColor(operation: string): string {
        if (operation.includes('rag')) return '#00ffff';
        if (operation.includes('llm')) return '#ff00ff';
        if (operation.includes('http')) return '#00ff41';
        return '#ffc800';
    }
</script>

<svelte:head>
    <title>Traces | CogTwin Admin</title>
</svelte:head>

<div class="traces-page">
    <header class="page-header">
        <h1>Distributed Traces</h1>
        <div class="filters">
            <select bind:value={filters.hours} on:change={applyFilters}>
                <option value={1}>Last 1 hour</option>
                <option value={6}>Last 6 hours</option>
                <option value={24}>Last 24 hours</option>
                <option value={72}>Last 3 days</option>
            </select>
            <select bind:value={filters.status} on:change={applyFilters}>
                <option value="">All Status</option>
                <option value="completed">Completed</option>
                <option value="error">Error</option>
            </select>
            <input
                type="number"
                placeholder="Min duration (ms)"
                bind:value={filters.min_duration_ms}
                on:change={applyFilters}
            />
        </div>
    </header>

    <div class="content">
        <!-- Trace List -->
        <div class="trace-list">
            <div class="list-header">
                <span>Endpoint</span>
                <span>Duration</span>
                <span>Status</span>
                <span>Time</span>
            </div>

            {#each $traces as trace}
                <button
                    class="trace-row"
                    class:selected={$selectedTrace?.trace_id === trace.trace_id}
                    on:click={() => selectTrace(trace.trace_id)}
                >
                    <span class="endpoint">{trace.endpoint || '/'}</span>
                    <span class="duration">{formatDuration(trace.duration_ms)}</span>
                    <span class="status" style="color: {getStatusColor(trace.status)}">
                        {trace.status}
                    </span>
                    <span class="time">
                        {new Date(trace.start_time).toLocaleTimeString()}
                    </span>
                </button>
            {/each}

            {#if $traces.length === 0}
                <div class="empty">No traces found</div>
            {/if}
        </div>

        <!-- Trace Detail / Waterfall -->
        <div class="trace-detail">
            {#if $selectedTrace}
                <div class="detail-header">
                    <h2>{$selectedTrace.endpoint}</h2>
                    <span class="trace-id">Trace: {$selectedTrace.trace_id}</span>
                </div>

                <div class="trace-meta">
                    <span>Duration: <strong>{formatDuration($selectedTrace.duration_ms)}</strong></span>
                    <span>User: <strong>{$selectedTrace.user_email || 'N/A'}</strong></span>
                    <span>Status: <strong style="color: {getStatusColor($selectedTrace.status)}">{$selectedTrace.status}</strong></span>
                </div>

                <!-- Waterfall -->
                <div class="waterfall">
                    <div class="waterfall-header">
                        <span>Operation</span>
                        <span>Duration</span>
                        <span class="timeline-header">Timeline</span>
                    </div>

                    {#each $selectedTrace.spans as span}
                        <div class="span-row">
                            <span class="span-name" style="padding-left: {span.parent_span_id ? '20px' : '0'}">
                                {span.operation_name}
                            </span>
                            <span class="span-duration">{formatDuration(span.duration_ms)}</span>
                            <div class="span-timeline">
                                <div
                                    class="span-bar"
                                    style="{getSpanStyle(span, $selectedTrace)} background: {getSpanColor(span.operation_name)}"
                                ></div>
                            </div>
                        </div>
                    {/each}
                </div>

                {#if $selectedTrace.error_message}
                    <div class="error-box">
                        <strong>Error:</strong> {$selectedTrace.error_message}
                    </div>
                {/if}
            {:else}
                <div class="no-selection">
                    Select a trace to view details
                </div>
            {/if}
        </div>
    </div>
</div>

<style>
    .traces-page {
        padding: 24px;
        height: 100%;
        display: flex;
        flex-direction: column;
    }

    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
    }

    .page-header h1 {
        margin: 0;
        font-size: 24px;
        color: #e0e0e0;
    }

    .filters {
        display: flex;
        gap: 12px;
    }

    .filters select, .filters input {
        padding: 8px 12px;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        color: #e0e0e0;
        font-size: 13px;
    }

    .content {
        display: grid;
        grid-template-columns: 400px 1fr;
        gap: 24px;
        flex: 1;
        overflow: hidden;
    }

    .trace-list {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        overflow-y: auto;
    }

    .list-header, .trace-row {
        display: grid;
        grid-template-columns: 1fr 80px 80px 80px;
        padding: 12px 16px;
        gap: 12px;
        font-size: 13px;
    }

    .list-header {
        color: #888;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        position: sticky;
        top: 0;
        background: rgba(0, 0, 0, 0.8);
    }

    .trace-row {
        width: 100%;
        background: none;
        border: none;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        color: #e0e0e0;
        cursor: pointer;
        text-align: left;
        transition: background 0.2s;
    }

    .trace-row:hover {
        background: rgba(255, 255, 255, 0.05);
    }

    .trace-row.selected {
        background: rgba(0, 255, 65, 0.1);
        border-left: 3px solid #00ff41;
    }

    .endpoint {
        font-family: 'JetBrains Mono', monospace;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .trace-detail {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 20px;
        overflow-y: auto;
    }

    .detail-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }

    .detail-header h2 {
        margin: 0;
        font-size: 18px;
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }

    .trace-id {
        font-size: 11px;
        color: #666;
        font-family: 'JetBrains Mono', monospace;
    }

    .trace-meta {
        display: flex;
        gap: 24px;
        margin-bottom: 24px;
        font-size: 13px;
        color: #888;
    }

    .trace-meta strong {
        color: #e0e0e0;
    }

    .waterfall {
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        overflow: hidden;
    }

    .waterfall-header, .span-row {
        display: grid;
        grid-template-columns: 150px 80px 1fr;
        padding: 10px 12px;
        gap: 12px;
        font-size: 12px;
    }

    .waterfall-header {
        background: rgba(255, 255, 255, 0.05);
        color: #888;
    }

    .span-row {
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .span-name {
        font-family: 'JetBrains Mono', monospace;
        color: #e0e0e0;
    }

    .span-duration {
        color: #888;
        text-align: right;
    }

    .span-timeline {
        position: relative;
        height: 16px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 3px;
    }

    .span-bar {
        position: absolute;
        top: 2px;
        height: 12px;
        border-radius: 2px;
        min-width: 2px;
    }

    .error-box {
        margin-top: 16px;
        padding: 12px;
        background: rgba(255, 0, 85, 0.1);
        border: 1px solid rgba(255, 0, 85, 0.3);
        border-radius: 6px;
        color: #ff4444;
        font-size: 13px;
    }

    .no-selection, .empty {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 200px;
        color: #666;
    }
</style>
