<!--
  StateMonitor - Real-time state debugging panel for CogTwin

  Phase 0 of Nerve Center Observability Suite
  Watches: isStreaming, currentStream.length, cognitiveState.phase, websocket.connected
-->

<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { session } from '$lib/stores/session';
    import { websocket } from '$lib/stores/websocket';

    interface LogEntry {
        timestamp: string;
        key: string;
        value: string;
        id: number;
    }

    // State tracking
    let logs: LogEntry[] = [];
    let logIdCounter = 0;
    const MAX_LOGS = 50;

    // Previous state for change detection
    let prevState = {
        isStreaming: false,
        streamLen: 0,
        phase: 'idle',
        wsConnected: false,
    };

    // Current live values
    let isStreaming = false;
    let streamLen = 0;
    let phase = 'idle';
    let wsConnected = false;

    // Computed: CheekyLoader visibility condition
    $: cheekyLoaderShouldShow = isStreaming && streamLen === 0;

    function formatTimestamp(): string {
        const now = new Date();
        const hours = now.getHours().toString().padStart(2, '0');
        const mins = now.getMinutes().toString().padStart(2, '0');
        const secs = now.getSeconds().toString().padStart(2, '0');
        const ms = now.getMilliseconds().toString().padStart(3, '0');
        return `${hours}:${mins}:${secs}.${ms}`;
    }

    function addLog(key: string, value: string) {
        const entry: LogEntry = {
            timestamp: formatTimestamp(),
            key,
            value,
            id: logIdCounter++,
        };
        logs = [entry, ...logs].slice(0, MAX_LOGS);
    }

    function clearLogs() {
        logs = [];
    }

    function getPhaseClass(p: string): string {
        switch (p) {
            case 'idle':
                return 'phase-idle';
            case 'searching':
                return 'phase-searching';
            case 'synthesizing':
                return 'phase-synthesizing';
            case 'generating':
                return 'phase-generating';
            default:
                return 'phase-idle';
        }
    }

    // Subscribe to stores
    const unsubSession = session.subscribe((state) => {
        const newIsStreaming = state.isStreaming;
        const newStreamLen = state.currentStream.length;
        const newPhase = state.cognitiveState.phase;

        // Detect changes and log them
        if (newIsStreaming !== prevState.isStreaming) {
            addLog('isStreaming', String(newIsStreaming));
            prevState.isStreaming = newIsStreaming;
        }

        // Only log streamLen when transitioning to/from 0
        if ((newStreamLen === 0) !== (prevState.streamLen === 0)) {
            addLog('streamLen', newStreamLen === 0 ? '0' : `${newStreamLen} (non-zero)`);
            prevState.streamLen = newStreamLen;
        }

        if (newPhase !== prevState.phase) {
            addLog('phase', newPhase);
            prevState.phase = newPhase;
        }

        // Update current values
        isStreaming = newIsStreaming;
        streamLen = newStreamLen;
        phase = newPhase;
    });

    const unsubWebsocket = websocket.subscribe((state) => {
        const newConnected = state.connected;

        if (newConnected !== prevState.wsConnected) {
            addLog('wsConnected', String(newConnected));
            prevState.wsConnected = newConnected;
        }

        wsConnected = newConnected;
    });

    onDestroy(() => {
        unsubSession();
        unsubWebsocket();
    });
</script>

<div class="state-monitor">
    <div class="monitor-header">
        <h3>
            <span class="pulse-dot"></span>
            STATE MONITOR
        </h3>
        <button class="clear-btn" on:click={clearLogs}>Clear</button>
    </div>

    <div class="state-values">
        <div class="state-row">
            <span class="state-key">isStreaming:</span>
            <span class="state-value" class:active={isStreaming}>{isStreaming}</span>
        </div>
        <div class="state-row">
            <span class="state-key">streamLen:</span>
            <span class="state-value">{streamLen}</span>
        </div>
        <div class="state-row">
            <span class="state-key">phase:</span>
            <span class="state-value {getPhaseClass(phase)}">{phase}</span>
        </div>
        <div class="state-row">
            <span class="state-key">wsConnected:</span>
            <span class="state-value" class:connected={wsConnected} class:disconnected={!wsConnected}>
                {wsConnected}
            </span>
        </div>
        <div class="state-row computed">
            <span class="state-key">CheekyLoader visible:</span>
            <span class="state-value" class:active={cheekyLoaderShouldShow}>
                {cheekyLoaderShouldShow}
                <span class="hint">(isStreaming && streamLen=0)</span>
            </span>
        </div>
    </div>

    <div class="log-header">
        <span>State Change Log</span>
        <span class="log-count">{logs.length}/{MAX_LOGS}</span>
    </div>

    <div class="log-container">
        {#each logs as log (log.id)}
            <div class="log-entry flash-in">
                <span class="log-timestamp">{log.timestamp}</span>
                <span class="log-separator">|</span>
                <span class="log-key">{log.key}</span>
                <span class="log-separator">|</span>
                <span class="log-value">{log.value}</span>
            </div>
        {/each}
        {#if logs.length === 0}
            <div class="log-empty">No state changes yet...</div>
        {/if}
    </div>
</div>

<style>
    .state-monitor {
        background: rgba(0, 0, 0, 0.6);
        border: 1px solid #00ff41;
        border-radius: 8px;
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 12px;
        color: #e0e0e0;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        max-height: 400px;
    }

    .monitor-header {
        padding: 10px 12px;
        border-bottom: 1px solid #00ff41;
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: rgba(0, 255, 65, 0.05);
    }

    .monitor-header h3 {
        margin: 0;
        font-size: 12px;
        font-weight: 600;
        color: #00ff41;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .pulse-dot {
        width: 8px;
        height: 8px;
        background: #00ff41;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% {
            opacity: 1;
            box-shadow: 0 0 0 0 rgba(0, 255, 65, 0.7);
        }
        50% {
            opacity: 0.7;
            box-shadow: 0 0 0 4px rgba(0, 255, 65, 0);
        }
    }

    .clear-btn {
        padding: 4px 10px;
        font-size: 10px;
        font-family: inherit;
        background: transparent;
        border: 1px solid #666;
        border-radius: 4px;
        color: #999;
        cursor: pointer;
        transition: all 0.2s;
    }

    .clear-btn:hover {
        border-color: #00ff41;
        color: #00ff41;
    }

    .state-values {
        padding: 10px 12px;
        border-bottom: 1px solid rgba(0, 255, 65, 0.3);
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .state-row {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .state-row.computed {
        margin-top: 4px;
        padding-top: 6px;
        border-top: 1px dashed rgba(0, 255, 65, 0.2);
    }

    .state-key {
        color: #808080;
        min-width: 120px;
    }

    .state-value {
        color: #e0e0e0;
    }

    .state-value.active {
        color: #00ff41;
        font-weight: 600;
    }

    .state-value.connected {
        color: #00ff41;
    }

    .state-value.disconnected {
        color: #ff4444;
    }

    .hint {
        color: #555;
        font-size: 10px;
        margin-left: 8px;
    }

    /* Phase colors */
    .phase-idle {
        color: #666;
    }

    .phase-searching {
        color: #00ffff;
    }

    .phase-synthesizing {
        color: #ff00ff;
    }

    .phase-generating {
        color: #ffff00;
    }

    .log-header {
        padding: 8px 12px;
        background: rgba(0, 0, 0, 0.3);
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #808080;
        font-size: 11px;
    }

    .log-count {
        color: #555;
    }

    .log-container {
        flex: 1;
        overflow-y: auto;
        padding: 8px 12px;
        display: flex;
        flex-direction: column;
        gap: 4px;
        min-height: 100px;
    }

    .log-entry {
        display: flex;
        gap: 8px;
        padding: 4px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .log-timestamp {
        color: #555;
        min-width: 85px;
    }

    .log-separator {
        color: #333;
    }

    .log-key {
        color: #00ff41;
        min-width: 100px;
    }

    .log-value {
        color: #e0e0e0;
    }

    .log-empty {
        color: #444;
        font-style: italic;
        text-align: center;
        padding: 20px;
    }

    .flash-in {
        animation: flashIn 0.3s ease-out;
    }

    @keyframes flashIn {
        0% {
            background: rgba(0, 255, 65, 0.3);
        }
        100% {
            background: transparent;
        }
    }

    /* Scrollbar styling */
    .log-container::-webkit-scrollbar {
        width: 6px;
    }

    .log-container::-webkit-scrollbar-track {
        background: rgba(0, 0, 0, 0.3);
    }

    .log-container::-webkit-scrollbar-thumb {
        background: #00ff41;
        border-radius: 3px;
    }
</style>
