/**
 * Metrics Store - Real-time observability data
 *
 * Connects to /api/metrics/stream for live updates
 * Falls back to polling if WebSocket unavailable
 */

import { writable, derived } from 'svelte/store';
import { auth } from './auth';

// =============================================================================
// TYPES
// =============================================================================

export interface SystemMetrics {
    cpu_percent: number;
    memory_percent: number;
    memory_used_gb: number;
    memory_total_gb: number;
    disk_percent: number;
    disk_used_gb: number;
    process_memory_mb: number;
    process_threads: number;
}

export interface WebSocketMetrics {
    connections_active: number;
    connections_total: number;
    messages_in: number;
    messages_out: number;
}

export interface RagMetrics {
    total_queries: number;
    latency_avg_ms: number;
    latency_p95_ms: number;
    embedding_avg_ms: number;
    search_avg_ms: number;
    avg_chunks: number;
    zero_chunk_rate: number;
}

export interface CacheMetrics {
    rag_hit_rate: number;
    embedding_hit_rate: number;
    rag_hits: number;
    rag_misses: number;
    embedding_hits: number;
    embedding_misses: number;
}

export interface LlmMetrics {
    total_requests: number;
    latency_avg_ms: number;
    latency_p95_ms: number;
    first_token_avg_ms: number;
    tokens_in_total: number;
    tokens_out_total: number;
    cost_total_usd: number;
    error_count: number;
}

export interface MetricsSnapshot {
    timestamp: string;
    uptime_seconds: number;
    system: SystemMetrics;
    websocket: WebSocketMetrics;
    rag: RagMetrics;
    cache: CacheMetrics;
    llm: LlmMetrics;
    api: {
        endpoints: Record<string, {
            requests: number;
            latency_avg_ms: number;
            latency_p95_ms: number;
            errors: number;
        }>;
    };
}

interface MetricsState {
    snapshot: MetricsSnapshot | null;
    connected: boolean;
    error: string | null;
    lastUpdated: Date | null;
    history: {
        timestamps: string[];
        cpu: number[];
        memory: number[];
        ragLatency: number[];
        cacheHitRate: number[];
        wsConnections: number[];
    };
}

// =============================================================================
// STORE
// =============================================================================

const MAX_HISTORY = 60;

function createMetricsStore() {
    const { subscribe, set, update } = writable<MetricsState>({
        snapshot: null,
        connected: false,
        error: null,
        lastUpdated: null,
        history: {
            timestamps: [],
            cpu: [],
            memory: [],
            ragLatency: [],
            cacheHitRate: [],
            wsConnections: [],
        },
    });

    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;

    function getWsUrl(): string {
        const apiUrl = import.meta.env.VITE_API_URL || 'https://lucky-love-production.up.railway.app';
        const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
        const host = new URL(apiUrl).host;
        return `${wsProtocol}://${host}/api/metrics/stream`;
    }

    function appendHistory(state: MetricsState, snapshot: MetricsSnapshot): MetricsState['history'] {
        const time = new Date().toLocaleTimeString();
        return {
            timestamps: [...state.history.timestamps, time].slice(-MAX_HISTORY),
            cpu: [...state.history.cpu, snapshot.system?.cpu_percent || 0].slice(-MAX_HISTORY),
            memory: [...state.history.memory, snapshot.system?.memory_percent || 0].slice(-MAX_HISTORY),
            ragLatency: [...state.history.ragLatency, snapshot.rag?.latency_avg_ms || 0].slice(-MAX_HISTORY),
            cacheHitRate: [...state.history.cacheHitRate, snapshot.cache?.rag_hit_rate || 0].slice(-MAX_HISTORY),
            wsConnections: [...state.history.wsConnections, snapshot.websocket?.connections_active || 0].slice(-MAX_HISTORY),
        };
    }

    const store = {
        subscribe,

        connect() {
            if (ws?.readyState === WebSocket.OPEN) return;

            try {
                ws = new WebSocket(getWsUrl());

                ws.onopen = () => {
                    reconnectAttempts = 0;
                    update(s => ({ ...s, connected: true, error: null }));
                    console.log('[Metrics WS] Connected');
                };

                ws.onmessage = (event) => {
                    try {
                        const msg = JSON.parse(event.data);
                        if (msg.type === 'metrics_snapshot') {
                            update(s => ({
                                ...s,
                                snapshot: msg.data,
                                lastUpdated: new Date(),
                                history: appendHistory(s, msg.data),
                            }));
                        }
                    } catch (e) {
                        console.error('[Metrics WS] Parse error:', e);
                    }
                };

                ws.onerror = (error) => {
                    console.error('[Metrics WS] Error:', error);
                    update(s => ({ ...s, error: 'Connection error' }));
                };

                ws.onclose = () => {
                    update(s => ({ ...s, connected: false }));
                    console.log('[Metrics WS] Disconnected');

                    // Auto-reconnect with backoff
                    if (reconnectAttempts < maxReconnectAttempts) {
                        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
                        reconnectAttempts++;
                        reconnectTimer = setTimeout(() => store.connect(), delay);
                    }
                };
            } catch (e) {
                update(s => ({ ...s, error: `Failed to connect: ${e}` }));
            }
        },

        disconnect() {
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
            if (ws) {
                ws.close();
                ws = null;
            }
            reconnectAttempts = maxReconnectAttempts; // Prevent auto-reconnect
            update(s => ({ ...s, connected: false }));
        },

        // Fallback: manual fetch if WebSocket not available
        async fetchSnapshot() {
            try {
                const apiUrl = import.meta.env.VITE_API_URL || 'https://lucky-love-production.up.railway.app';
                const res = await fetch(`${apiUrl}/api/metrics/snapshot`, {
                    headers: { 'X-User-Email': auth.getEmail() || '' }
                });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                update(s => ({
                    ...s,
                    snapshot: data,
                    lastUpdated: new Date(),
                    history: appendHistory(s, data),
                }));
            } catch (e) {
                update(s => ({ ...s, error: `Fetch failed: ${e}` }));
            }
        },

        reset() {
            store.disconnect();
            set({
                snapshot: null,
                connected: false,
                error: null,
                lastUpdated: null,
                history: {
                    timestamps: [],
                    cpu: [],
                    memory: [],
                    ragLatency: [],
                    cacheHitRate: [],
                    wsConnections: [],
                },
            });
        },
    };

    return store;
}

export const metricsStore = createMetricsStore();

// =============================================================================
// DERIVED STORES
// =============================================================================

export const metricsSnapshot = derived(metricsStore, $s => $s.snapshot);
export const metricsConnected = derived(metricsStore, $s => $s.connected);
export const metricsHistory = derived(metricsStore, $s => $s.history);

export const systemHealth = derived(metricsStore, $s => {
    if (!$s.snapshot) return 'unknown';
    const { system, cache, rag } = $s.snapshot;

    if (system?.cpu_percent > 90 || system?.memory_percent > 90) return 'critical';
    if (cache?.rag_hit_rate < 20 || rag?.latency_p95_ms > 5000) return 'degraded';
    if (system?.cpu_percent > 70 || system?.memory_percent > 70) return 'warning';
    return 'healthy';
});
