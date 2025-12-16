<!--
  Admin Dashboard - Nerve Center Overview
-->

<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { analyticsStore, overview, categories, departments, realtimeSessions } from '$lib/stores/analytics';
    import StatCard from '$lib/components/admin/charts/StatCard.svelte';
    import LineChart from '$lib/components/admin/charts/LineChart.svelte';
    import DoughnutChart from '$lib/components/admin/charts/DoughnutChart.svelte';
    import BarChart from '$lib/components/admin/charts/BarChart.svelte';
    import RealtimeSessions from '$lib/components/admin/charts/RealtimeSessions.svelte';

    let queriesByHour: Array<{ hour: string; count: number }> = [];

    onMount(async () => {
        await analyticsStore.loadAll();
        analyticsStore.startAutoRefresh();

        // Subscribe to queries data
        analyticsStore.subscribe(s => {
            queriesByHour = s.queriesByHour;
        });
    });

    onDestroy(() => {
        analyticsStore.stopAutoRefresh();
    });
</script>

<svelte:head>
    <title>Nerve Center | Driscoll Intelligence</title>
</svelte:head>

<div class="dashboard p-6">
    <!-- Header -->
    <div class="header flex items-center justify-between mb-6">
        <div>
            <h1 class="text-2xl font-bold text-[#00ff41] glow-text">
                DRISCOLL INTELLIGENCE - NERVE CENTER
            </h1>
            <p class="text-sm text-[#808080] mt-1">Operational Intelligence Dashboard</p>
        </div>
        <div class="status flex items-center gap-2">
            <span class="live-indicator"></span>
            <span class="text-sm text-[#00ff41]">Live</span>
        </div>
    </div>

    <!-- Overview Stats Row -->
    <div class="stats-row grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard
            label="Active Now"
            value={$overview?.active_users ?? 0}
            color="green"
            loading={!$overview}
        />
        <StatCard
            label="Today's Queries"
            value={$overview?.total_queries ?? 0}
            color="cyan"
            loading={!$overview}
        />
        <StatCard
            label="Avg Response"
            value={$overview?.avg_response_time_ms ?? 0}
            format="ms"
            color="amber"
            loading={!$overview}
        />
        <StatCard
            label="Error Rate"
            value={$overview?.error_rate_percent ?? 0}
            format="percent"
            color={($overview?.error_rate_percent ?? 0) > 1 ? 'red' : 'green'}
            loading={!$overview}
        />
    </div>

    <!-- Charts Row -->
    <div class="charts-row grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Queries by Hour -->
        <div class="chart-panel panel p-4">
            <h3 class="text-sm font-semibold text-[#808080] mb-4">QUERIES BY HOUR (Today)</h3>
            <LineChart data={queriesByHour} label="Queries" height="200px" />
        </div>

        <!-- Query Categories -->
        <div class="chart-panel panel p-4">
            <h3 class="text-sm font-semibold text-[#808080] mb-4">QUERY CATEGORIES</h3>
            <DoughnutChart data={$categories} height="200px" />
        </div>
    </div>

    <!-- Bottom Row -->
    <div class="bottom-row grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Department Stats -->
        <div class="chart-panel panel p-4 lg:col-span-2">
            <h3 class="text-sm font-semibold text-[#808080] mb-4">DEPARTMENT ACTIVITY</h3>
            <BarChart
                data={$departments}
                labelKey="department"
                valueKey="query_count"
                height="180px"
            />
        </div>

        <!-- Realtime Sessions -->
        <RealtimeSessions sessions={$realtimeSessions} loading={false} />
    </div>
</div>

<style>
    .dashboard {
        min-height: 100vh;
        background: var(--bg-primary);
    }

    .glow-text {
        text-shadow: 0 0 10px rgba(0, 255, 65, 0.5);
    }

    .live-indicator {
        width: 10px;
        height: 10px;
        background: #00ff41;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(0, 255, 65, 0.7); }
        50% { box-shadow: 0 0 0 6px rgba(0, 255, 65, 0); }
    }

    .chart-panel {
        background: var(--bg-secondary);
        border: 1px solid var(--border-dim);
        border-radius: 8px;
    }
</style>
