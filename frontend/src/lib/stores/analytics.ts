/**
 * Analytics Store - Dashboard data and real-time stats
 *
 * Fetches from analytics endpoints:
 * - /api/admin/analytics/overview
 * - /api/admin/analytics/queries
 * - /api/admin/analytics/categories
 * - /api/admin/analytics/departments
 * - /api/admin/analytics/department-usage-inferred (NEW - Phase 3)
 * - /api/admin/analytics/query-intents (NEW - Phase 3)
 * - /api/admin/analytics/memory-graph-data (NEW - Phase 3)
 * - /api/admin/analytics/errors
 * - /api/admin/analytics/realtime
 */

import { writable, derived } from 'svelte/store';
import { auth } from './auth';

// =============================================================================
// TYPES
// =============================================================================

export interface OverviewStats {
    active_users: number;
    total_queries: number;
    avg_response_time_ms: number;
    error_rate_percent: number;
    period_hours: number;
}

export interface HourlyData {
    hour: string;
    count: number;
}

export interface CategoryData {
    category: string;
    count: number;
}

export interface DepartmentStats {
    department: string;
    query_count: number;
    unique_users: number;
    avg_response_time_ms: number;
}

export interface DepartmentUsageInferred {
    department: string;
    query_count: number;
    unique_users: number;
    avg_complexity: number;
    avg_response_time_ms: number;
}

export interface QueryIntent {
    intent: string;
    count: number;
    complexity: number;
}

export interface MemoryGraphData {
    categories: CategoryData[];
    departments: DepartmentUsageInferred[];
    intents: QueryIntent[];
    temporal_patterns: any;
    overview: OverviewStats;
    urgency_distribution: Record<string, number>;
}

export interface ErrorEntry {
    id: string;
    user_email: string | null;
    department: string | null;
    error_type: string | null;
    error_message: string | null;
    created_at: string;
}

export interface RealtimeSession {
    session_id: string;
    user_email: string;
    department: string;
    query_count: number;
    last_activity: string;
}

interface AnalyticsState {
    // Overview
    overview: OverviewStats | null;
    overviewLoading: boolean;

    // Time series
    queriesByHour: HourlyData[];
    queriesByHourLoading: boolean;

    // Categories
    categories: CategoryData[];
    categoriesLoading: boolean;

    // Departments
    departments: DepartmentStats[];
    departmentsLoading: boolean;

    // New: Inferred Department Usage
    departmentUsageInferred: DepartmentUsageInferred[];
    departmentUsageInferredLoading: boolean;

    // New: Query Intents
    queryIntents: QueryIntent[];
    queryIntentsLoading: boolean;

    // New: Memory Graph Data
    memoryGraphData: MemoryGraphData | null;
    memoryGraphDataLoading: boolean;

    // Errors
    errors: ErrorEntry[];
    errorsLoading: boolean;

    // Realtime
    realtimeSessions: RealtimeSession[];
    realtimeLoading: boolean;

    // Settings
    periodHours: number;
    autoRefresh: boolean;
    refreshInterval: number; // ms
}

// =============================================================================
// INITIAL STATE
// =============================================================================

const initialState: AnalyticsState = {
    overview: null,
    overviewLoading: false,

    queriesByHour: [],
    queriesByHourLoading: false,

    categories: [],
    categoriesLoading: false,

    departments: [],
    departmentsLoading: false,

    departmentUsageInferred: [],
    departmentUsageInferredLoading: false,

    queryIntents: [],
    queryIntentsLoading: false,

    memoryGraphData: null,
    memoryGraphDataLoading: false,

    errors: [],
    errorsLoading: false,

    realtimeSessions: [],
    realtimeLoading: false,

    periodHours: 24,
    autoRefresh: true,
    refreshInterval: 30000,
};

// =============================================================================
// STORE
// =============================================================================

function createAnalyticsStore() {
    const { subscribe, set, update } = writable<AnalyticsState>(initialState);

    let refreshTimer: ReturnType<typeof setInterval> | null = null;
    let currentPeriodHours = initialState.periodHours;

    function getApiBase(): string {
        return import.meta.env.VITE_API_URL || 'http://localhost:8000';
    }

    function getHeaders(): Record<string, string> {
        const email = auth.getEmail();
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        };
        if (email) {
            headers['X-User-Email'] = email;
        }
        return headers;
    }

    async function fetchJson<T>(path: string): Promise<T | null> {
        try {
            const res = await fetch(`${getApiBase()}${path}`, {
                headers: getHeaders(),
            });
            if (!res.ok) return null;
            return await res.json();
        } catch (e) {
            console.error('[Analytics] Fetch error:', e);
            return null;
        }
    }

    const store = {
        subscribe,

        // =====================================================================
        // DATA LOADING
        // =====================================================================

        async loadOverview() {
            update(s => ({ ...s, overviewLoading: true }));
            const data = await fetchJson<OverviewStats>(
                `/api/admin/analytics/overview?hours=${currentPeriodHours}`
            );
            update(s => ({
                ...s,
                overview: data,
                overviewLoading: false,
            }));
        },

        async loadQueriesByHour() {
            update(s => ({ ...s, queriesByHourLoading: true }));
            const data = await fetchJson<{ period_hours: number; data: HourlyData[] }>(
                `/api/admin/analytics/queries?hours=${currentPeriodHours}`
            );
            update(s => ({
                ...s,
                queriesByHour: data?.data || [],
                queriesByHourLoading: false,
            }));
        },

        async loadCategories() {
            update(s => ({ ...s, categoriesLoading: true }));
            const data = await fetchJson<{ period_hours: number; data: CategoryData[] }>(
                `/api/admin/analytics/categories?hours=${currentPeriodHours}`
            );
            update(s => ({
                ...s,
                categories: data?.data || [],
                categoriesLoading: false,
            }));
        },

        async loadDepartments() {
            update(s => ({ ...s, departmentsLoading: true }));
            const data = await fetchJson<{ period_hours: number; data: DepartmentStats[] }>(
                `/api/admin/analytics/departments?hours=${currentPeriodHours}`
            );
            update(s => ({
                ...s,
                departments: data?.data || [],
                departmentsLoading: false,
            }));
        },

        async loadErrors() {
            update(s => ({ ...s, errorsLoading: true }));
            const data = await fetchJson<{ limit: number; data: ErrorEntry[] }>(
                `/api/admin/analytics/errors?limit=20`
            );
            update(s => ({
                ...s,
                errors: data?.data || [],
                errorsLoading: false,
            }));
        },

        async loadRealtime() {
            update(s => ({ ...s, realtimeLoading: true }));
            const data = await fetchJson<{ sessions: RealtimeSession[] }>(
                `/api/admin/analytics/realtime`
            );
            update(s => ({
                ...s,
                realtimeSessions: data?.sessions || [],
                realtimeLoading: false,
            }));
        },

        async loadDepartmentUsageInferred() {
            update(s => ({ ...s, departmentUsageInferredLoading: true }));
            try {
                const data = await fetchJson<DepartmentUsageInferred[]>(
                    `/api/admin/analytics/department-usage-inferred?hours=${currentPeriodHours}`
                );
                update(s => ({
                    ...s,
                    departmentUsageInferred: data || [],
                    departmentUsageInferredLoading: false,
                }));
            } catch (err) {
                console.error('[Analytics] Failed to load inferred department usage:', err);
                update(s => ({
                    ...s,
                    departmentUsageInferred: [],
                    departmentUsageInferredLoading: false,
                }));
            }
        },

        async loadQueryIntents() {
            update(s => ({ ...s, queryIntentsLoading: true }));
            try {
                const data = await fetchJson<QueryIntent[]>(
                    `/api/admin/analytics/query-intents?hours=${currentPeriodHours}`
                );
                update(s => ({
                    ...s,
                    queryIntents: data || [],
                    queryIntentsLoading: false,
                }));
            } catch (err) {
                console.error('[Analytics] Failed to load query intents:', err);
                update(s => ({
                    ...s,
                    queryIntents: [],
                    queryIntentsLoading: false,
                }));
            }
        },

        async loadMemoryGraphData() {
            update(s => ({ ...s, memoryGraphDataLoading: true }));
            try {
                const data = await fetchJson<MemoryGraphData>(
                    `/api/admin/analytics/memory-graph-data?hours=${currentPeriodHours}`
                );
                update(s => ({
                    ...s,
                    memoryGraphData: data,
                    memoryGraphDataLoading: false,
                }));
            } catch (err) {
                console.error('[Analytics] Failed to load memory graph data:', err);
                update(s => ({
                    ...s,
                    memoryGraphData: null,
                    memoryGraphDataLoading: false,
                }));
            }
        },

        // Load all dashboard data
        async loadAll() {
            await Promise.all([
                store.loadOverview(),
                store.loadQueriesByHour(),
                store.loadCategories(),
                store.loadDepartments(),
                store.loadDepartmentUsageInferred(),
                store.loadQueryIntents(),
                store.loadMemoryGraphData(),
                store.loadErrors(),
                store.loadRealtime(),
            ]);
        },

        // =====================================================================
        // SETTINGS
        // =====================================================================

        setPeriodHours(hours: number) {
            currentPeriodHours = hours;
            update(s => ({ ...s, periodHours: hours }));
            store.loadAll();
        },

        // Reload all data with a new time period
        async reloadWithPeriod(hours: number) {
            currentPeriodHours = hours;
            update(s => ({ ...s, periodHours: hours }));
            await Promise.all([
                store.loadOverview(),
                store.loadQueriesByHour(),
                store.loadCategories(),
                store.loadDepartments(),
                store.loadDepartmentUsageInferred(),
                store.loadQueryIntents(),
                store.loadMemoryGraphData(),
            ]);
        },

        // =====================================================================
        // AUTO-REFRESH
        // =====================================================================

        startAutoRefresh() {
            if (refreshTimer) return;

            update(s => ({ ...s, autoRefresh: true }));

            refreshTimer = setInterval(() => {
                store.loadOverview();
                store.loadRealtime();
            }, initialState.refreshInterval);
        },

        stopAutoRefresh() {
            if (refreshTimer) {
                clearInterval(refreshTimer);
                refreshTimer = null;
            }
            update(s => ({ ...s, autoRefresh: false }));
        },

        // =====================================================================
        // CLEANUP
        // =====================================================================

        reset() {
            store.stopAutoRefresh();
            set(initialState);
        },
    };

    return store;
}

export const analyticsStore = createAnalyticsStore();

// =============================================================================
// DERIVED STORES
// =============================================================================

export const overview = derived(analyticsStore, $s => $s.overview);
export const overviewLoading = derived(analyticsStore, $s => $s.overviewLoading);

export const queriesByHour = derived(analyticsStore, $s => $s.queriesByHour);
export const categories = derived(analyticsStore, $s => $s.categories);
export const departments = derived(analyticsStore, $s => $s.departments);
export const departmentUsageInferred = derived(analyticsStore, $s => $s.departmentUsageInferred);
export const queryIntents = derived(analyticsStore, $s => $s.queryIntents);
export const memoryGraphData = derived(analyticsStore, $s => $s.memoryGraphData);
export const errors = derived(analyticsStore, $s => $s.errors);
export const realtimeSessions = derived(analyticsStore, $s => $s.realtimeSessions);

export const isLoading = derived(
    analyticsStore,
    $s => $s.overviewLoading || $s.queriesByHourLoading || $s.categoriesLoading
);

export const periodHours = derived(analyticsStore, $s => $s.periodHours);
