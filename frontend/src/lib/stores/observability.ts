/**
 * Observability Store - Tracing, Logging, Alerts
 */

import { writable, derived } from 'svelte/store';
import { auth } from './auth';

// =============================================================================
// TYPES
// =============================================================================

export interface Trace {
    trace_id: string;
    entry_point: string;
    endpoint: string;
    method: string;
    session_id: string;
    user_email: string;
    department: string;
    start_time: string;
    end_time: string;
    duration_ms: number;
    status: string;
    error_message: string | null;
}

export interface Span {
    span_id: string;
    trace_id: string;
    parent_span_id: string | null;
    operation_name: string;
    start_time: string;
    end_time: string;
    duration_ms: number;
    status: string;
    tags: Record<string, any>;
    logs: Array<{ timestamp: string; message: string }>;
}

export interface LogEntry {
    id: string;
    timestamp: string;
    level: string;
    logger_name: string;
    message: string;
    trace_id: string | null;
    user_email: string | null;
    extra: Record<string, any>;
}

export interface AlertRule {
    id: string;
    name: string;
    description: string;
    metric_type: string;
    condition: string;
    threshold: number;
    severity: string;
    enabled: boolean;
    last_triggered_at: string | null;
}

export interface AlertInstance {
    id: string;
    rule_id: string;
    rule_name: string;
    severity: string;
    triggered_at: string;
    status: string;
    metric_value: number;
    threshold_value: number;
    message: string;
}

// =============================================================================
// STORE
// =============================================================================

function createObservabilityStore() {
    const { subscribe, set, update } = writable({
        // Traces
        traces: [] as Trace[],
        tracesLoading: false,
        selectedTrace: null as (Trace & { spans: Span[] }) | null,

        // Logs
        logs: [] as LogEntry[],
        logsLoading: false,
        logStreamConnected: false,

        // Alerts
        alertRules: [] as AlertRule[],
        alertInstances: [] as AlertInstance[],
        alertsLoading: false,
    });

    let logWs: WebSocket | null = null;

    function getApiBase(): string {
        return import.meta.env.VITE_API_URL || 'http://localhost:8000';
    }

    function getHeaders(): Record<string, string> {
        return {
            'Content-Type': 'application/json',
            ...auth.getAuthHeader(),
        };
    }

    const store = {
        subscribe,

        // =================================================================
        // TRACES
        // =================================================================

        async loadTraces(filters: {
            hours?: number;
            status?: string;
            user_email?: string;
            min_duration_ms?: number;
        } = {}) {
            update(s => ({ ...s, tracesLoading: true }));

            try {
                const params = new URLSearchParams();
                if (filters.hours) params.set('hours', String(filters.hours));
                if (filters.status) params.set('status', filters.status);
                if (filters.user_email) params.set('user_email', filters.user_email);
                if (filters.min_duration_ms) params.set('min_duration_ms', String(filters.min_duration_ms));

                const res = await fetch(`${getApiBase()}/api/observability/traces?${params}`, {
                    headers: getHeaders()
                });
                const data = await res.json();

                update(s => ({
                    ...s,
                    traces: data.traces || [],
                    tracesLoading: false,
                }));
            } catch (e) {
                console.error('[Observability] Load traces error:', e);
                update(s => ({ ...s, tracesLoading: false }));
            }
        },

        async loadTrace(traceId: string) {
            try {
                const res = await fetch(`${getApiBase()}/api/observability/traces/${traceId}`, {
                    headers: getHeaders()
                });
                const data = await res.json();

                update(s => ({
                    ...s,
                    selectedTrace: {
                        ...data.trace,
                        spans: data.spans || [],
                    },
                }));
            } catch (e) {
                console.error('[Observability] Load trace error:', e);
            }
        },

        clearSelectedTrace() {
            update(s => ({ ...s, selectedTrace: null }));
        },

        // =================================================================
        // LOGS
        // =================================================================

        async loadLogs(filters: {
            hours?: number;
            level?: string;
            trace_id?: string;
            search?: string;
        } = {}) {
            update(s => ({ ...s, logsLoading: true }));

            try {
                const params = new URLSearchParams();
                if (filters.hours) params.set('hours', String(filters.hours));
                if (filters.level) params.set('level', filters.level);
                if (filters.trace_id) params.set('trace_id', filters.trace_id);
                if (filters.search) params.set('search', filters.search);

                const res = await fetch(`${getApiBase()}/api/observability/logs?${params}`, {
                    headers: getHeaders()
                });
                const data = await res.json();

                update(s => ({
                    ...s,
                    logs: data.logs || [],
                    logsLoading: false,
                }));
            } catch (e) {
                console.error('[Observability] Load logs error:', e);
                update(s => ({ ...s, logsLoading: false }));
            }
        },

        connectLogStream() {
            if (logWs) return;

            const apiUrl = getApiBase();
            const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
            const host = new URL(apiUrl).host;
            const url = `${wsProtocol}://${host}/api/observability/logs/stream`;

            logWs = new WebSocket(url);

            logWs.onopen = () => {
                update(s => ({ ...s, logStreamConnected: true }));
            };

            logWs.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'new_log') {
                    update(s => ({
                        ...s,
                        logs: [msg.data, ...s.logs].slice(0, 500),
                    }));
                }
            };

            logWs.onclose = () => {
                update(s => ({ ...s, logStreamConnected: false }));
                logWs = null;
            };
        },

        disconnectLogStream() {
            if (logWs) {
                logWs.close();
                logWs = null;
            }
        },

        // =================================================================
        // ALERTS
        // =================================================================

        async loadAlertRules() {
            update(s => ({ ...s, alertsLoading: true }));

            try {
                const res = await fetch(`${getApiBase()}/api/observability/alerts/rules`, {
                    headers: getHeaders()
                });
                const data = await res.json();

                update(s => ({
                    ...s,
                    alertRules: data.rules || [],
                    alertsLoading: false,
                }));
            } catch (e) {
                console.error('[Observability] Load alert rules error:', e);
                update(s => ({ ...s, alertsLoading: false }));
            }
        },

        async loadAlertInstances(hours: number = 24) {
            try {
                const res = await fetch(`${getApiBase()}/api/observability/alerts/instances?hours=${hours}`, {
                    headers: getHeaders()
                });
                const data = await res.json();

                update(s => ({
                    ...s,
                    alertInstances: data.instances || [],
                }));
            } catch (e) {
                console.error('[Observability] Load alert instances error:', e);
            }
        },

        async toggleAlertRule(ruleId: string, enabled: boolean) {
            try {
                await fetch(`${getApiBase()}/api/observability/alerts/rules/${ruleId}`, {
                    method: 'PUT',
                    headers: getHeaders(),
                    body: JSON.stringify({ enabled }),
                });

                // Update locally
                update(s => ({
                    ...s,
                    alertRules: s.alertRules.map(r =>
                        r.id === ruleId ? { ...r, enabled } : r
                    ),
                }));
            } catch (e) {
                console.error('[Observability] Toggle alert rule error:', e);
            }
        },

        async acknowledgeAlert(instanceId: string) {
            try {
                await fetch(`${getApiBase()}/api/observability/alerts/instances/${instanceId}/acknowledge`, {
                    method: 'POST',
                    headers: getHeaders(),
                });

                // Update locally
                update(s => ({
                    ...s,
                    alertInstances: s.alertInstances.map(a =>
                        a.id === instanceId ? { ...a, status: 'acknowledged' } : a
                    ),
                }));
            } catch (e) {
                console.error('[Observability] Acknowledge alert error:', e);
            }
        },

        // =================================================================
        // CLEANUP
        // =================================================================

        reset() {
            store.disconnectLogStream();
            set({
                traces: [],
                tracesLoading: false,
                selectedTrace: null,
                logs: [],
                logsLoading: false,
                logStreamConnected: false,
                alertRules: [],
                alertInstances: [],
                alertsLoading: false,
            });
        },
    };

    return store;
}

export const observabilityStore = createObservabilityStore();

// Derived stores
export const traces = derived(observabilityStore, $s => $s.traces);
export const selectedTrace = derived(observabilityStore, $s => $s.selectedTrace);
export const logs = derived(observabilityStore, $s => $s.logs);
export const alertRules = derived(observabilityStore, $s => $s.alertRules);
export const alertInstances = derived(observabilityStore, $s => $s.alertInstances);
export const firingAlerts = derived(observabilityStore, $s =>
    $s.alertInstances.filter(a => a.status === 'firing')
);
