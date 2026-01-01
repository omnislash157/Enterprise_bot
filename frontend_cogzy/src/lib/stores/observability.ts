/**
 * Observability Store - Tracing, Logging, Alerts, Query Log
 * 
 * Merged: Original observability + Query Log viewer functionality
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

// NEW: Query Log types
export interface QueryLogEntry {
    id: string;
    session_id: string;
    user_email: string;
    department: string | null;
    inferred_department: string | null;
    query_text: string;
    response_text: string;
    response_time_ms: number;
    chunks_used: number;
    complexity_score: number;
    intent_type: string | null;
    urgency: string | null;
    query_category: string | null;
    trace_id: string | null;
    created_at: string;
}

export interface QueryLogStats {
    total_queries: number;
    unique_users: number;
    departments_used: number;
    avg_response_time_ms: number;
    avg_complexity: number;
    avg_chunks_used: number;
    by_department: Array<{ department: string; count: number }>;
    by_intent: Array<{ intent: string; count: number }>;
}

// =============================================================================
// STORE
// =============================================================================

function createObservabilityStore() {
    const { subscribe, set, update } = writable({
        // Traces
        traces: [] as Trace[],
        tracesTotal: 0,
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

        // Query Log (NEW)
        queries: [] as QueryLogEntry[],
        queriesTotal: 0,
        queriesLoading: false,
        queryStats: null as QueryLogStats | null,
        selectedQuery: null as QueryLogEntry | null,
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
                    tracesTotal: data.total || 0,
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
        // QUERY LOG (NEW)
        // =================================================================

        async loadQueries(filters: {
            hours?: number;
            department?: string;
            user_email?: string;
            search?: string;
            min_response_time?: number;
            limit?: number;
            offset?: number;
        } = {}) {
            update(s => ({ ...s, queriesLoading: true }));

            try {
                const params = new URLSearchParams();
                if (filters.hours) params.set('hours', String(filters.hours));
                if (filters.department) params.set('department', filters.department);
                if (filters.user_email) params.set('user_email', filters.user_email);
                if (filters.search) params.set('search', filters.search);
                if (filters.min_response_time) params.set('min_response_time', String(filters.min_response_time));
                if (filters.limit) params.set('limit', String(filters.limit));
                if (filters.offset) params.set('offset', String(filters.offset));

                const res = await fetch(`${getApiBase()}/api/admin/queries?${params}`, {
                    headers: getHeaders()
                });

                if (!res.ok) {
                    console.error('[Observability] Queries fetch failed:', res.status);
                    update(s => ({ ...s, queriesLoading: false }));
                    return;
                }

                const data = await res.json();

                update(s => ({
                    ...s,
                    queries: data.queries || [],
                    queriesTotal: data.total || 0,
                    queriesLoading: false,
                }));
            } catch (e) {
                console.error('[Observability] Load queries error:', e);
                update(s => ({ ...s, queriesLoading: false }));
            }
        },

        async loadQueryStats(hours: number = 24) {
            try {
                const res = await fetch(`${getApiBase()}/api/admin/queries/stats?hours=${hours}`, {
                    headers: getHeaders()
                });

                if (!res.ok) return;

                const data = await res.json();
                update(s => ({ ...s, queryStats: data }));
            } catch (e) {
                console.error('[Observability] Load query stats error:', e);
            }
        },

        async loadQueryDetail(queryId: string) {
            try {
                const res = await fetch(`${getApiBase()}/api/admin/queries/${queryId}`, {
                    headers: getHeaders()
                });

                if (!res.ok) return;

                const data = await res.json();
                update(s => ({ ...s, selectedQuery: data }));
            } catch (e) {
                console.error('[Observability] Load query detail error:', e);
            }
        },

        clearSelectedQuery() {
            update(s => ({ ...s, selectedQuery: null }));
        },

        getQueryExportUrl(hours: number = 24, department?: string): string {
            const params = new URLSearchParams({ hours: String(hours) });
            if (department) params.set('department', department);
            return `${getApiBase()}/api/admin/queries/export/csv?${params}`;
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
                tracesTotal: 0,
                tracesLoading: false,
                selectedTrace: null,
                logs: [],
                logsLoading: false,
                logStreamConnected: false,
                alertRules: [],
                alertInstances: [],
                alertsLoading: false,
                queries: [],
                queriesTotal: 0,
                queriesLoading: false,
                queryStats: null,
                selectedQuery: null,
            });
        },
    };

    return store;
}

export const observabilityStore = createObservabilityStore();

// Derived stores - Original
export const traces = derived(observabilityStore, $s => $s.traces);
export const tracesTotal = derived(observabilityStore, $s => $s.tracesTotal);
export const selectedTrace = derived(observabilityStore, $s => $s.selectedTrace);
export const logs = derived(observabilityStore, $s => $s.logs);
export const alertRules = derived(observabilityStore, $s => $s.alertRules);
export const alertInstances = derived(observabilityStore, $s => $s.alertInstances);
export const firingAlerts = derived(observabilityStore, $s =>
    $s.alertInstances.filter(a => a.status === 'firing')
);

// Derived stores - Query Log (NEW)
export const queries = derived(observabilityStore, $s => $s.queries);
export const queriesTotal = derived(observabilityStore, $s => $s.queriesTotal);
export const queryStats = derived(observabilityStore, $s => $s.queryStats);
export const selectedQuery = derived(observabilityStore, $s => $s.selectedQuery);