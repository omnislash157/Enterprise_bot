<!--
  Analytics Deep Dive - Detailed charts and insights
-->

<script lang="ts">
    import { onMount } from 'svelte';
    import { analyticsStore, categories, departments, errors } from '$lib/stores/analytics';
    import LineChart from '$lib/components/admin/charts/LineChart.svelte';
    import DoughnutChart from '$lib/components/admin/charts/DoughnutChart.svelte';
    import BarChart from '$lib/components/admin/charts/BarChart.svelte';

    let queriesByHour: Array<{ hour: string; count: number }> = [];
    let periodHours = 24;

    const periodOptions = [
        { value: 24, label: '24 Hours' },
        { value: 72, label: '3 Days' },
        { value: 168, label: '7 Days' },
    ];

    async function changePeriod(hours: number) {
        periodHours = hours;
        analyticsStore.setPeriodHours(hours);
    }

    onMount(async () => {
        await analyticsStore.loadAll();

        analyticsStore.subscribe(s => {
            queriesByHour = s.queriesByHour;
        });
    });
</script>

<svelte:head>
    <title>Analytics | Driscoll Intelligence</title>
</svelte:head>

<div class="analytics-page p-6">
    <!-- Header -->
    <div class="header flex items-center justify-between mb-6">
        <div>
            <h1 class="text-xl font-bold text-[#00ff41]">Analytics Deep Dive</h1>
            <p class="text-sm text-[#808080]">Query patterns, performance, and insights</p>
        </div>

        <!-- Period Selector -->
        <div class="period-selector flex gap-2">
            {#each periodOptions as opt}
                <button
                    class="px-3 py-1 text-sm rounded {periodHours === opt.value ? 'bg-[#00ff41] text-black' : 'bg-[#1a1a1a] text-[#808080]'}"
                    on:click={() => changePeriod(opt.value)}
                >
                    {opt.label}
                </button>
            {/each}
        </div>
    </div>

    <!-- Query Volume Trend -->
    <div class="chart-section panel p-4 mb-6">
        <h3 class="text-sm font-semibold text-[#808080] mb-4">QUERY VOLUME TREND</h3>
        <LineChart data={queriesByHour} label="Queries" height="250px" />
    </div>

    <!-- Two Column Layout -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Category Breakdown -->
        <div class="chart-section panel p-4">
            <h3 class="text-sm font-semibold text-[#808080] mb-4">QUERY CATEGORIES</h3>
            <DoughnutChart data={$categories} height="280px" />
        </div>

        <!-- Department Comparison -->
        <div class="chart-section panel p-4">
            <h3 class="text-sm font-semibold text-[#808080] mb-4">DEPARTMENT COMPARISON</h3>
            <BarChart
                data={$departments}
                labelKey="department"
                valueKey="query_count"
                height="280px"
            />
        </div>
    </div>

    <!-- Response Time by Department -->
    <div class="chart-section panel p-4 mb-6">
        <h3 class="text-sm font-semibold text-[#808080] mb-4">RESPONSE TIME BY DEPARTMENT</h3>
        <BarChart
            data={$departments}
            labelKey="department"
            valueKey="avg_response_time_ms"
            height="200px"
        />
    </div>

    <!-- Recent Errors -->
    <div class="errors-section panel p-4">
        <h3 class="text-sm font-semibold text-[#808080] mb-4">RECENT ERRORS</h3>

        {#if $errors.length === 0}
            <div class="text-center text-[#808080] py-8">
                No errors in the selected period
            </div>
        {:else}
            <div class="errors-table overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="text-left text-[#808080] border-b border-[#222]">
                            <th class="pb-2">Time</th>
                            <th class="pb-2">User</th>
                            <th class="pb-2">Type</th>
                            <th class="pb-2">Message</th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each $errors as error}
                            <tr class="border-b border-[#1a1a1a]">
                                <td class="py-2 text-[#808080]">
                                    {new Date(error.created_at).toLocaleTimeString()}
                                </td>
                                <td class="py-2 text-[#e0e0e0]">
                                    {error.user_email || '-'}
                                </td>
                                <td class="py-2 text-[#ff4444]">
                                    {error.error_type || 'Unknown'}
                                </td>
                                <td class="py-2 text-[#808080] truncate max-w-[300px]">
                                    {error.error_message || '-'}
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        {/if}
    </div>
</div>

<style>
    .analytics-page {
        min-height: 100vh;
        background: var(--bg-primary);
    }

    .chart-section {
        background: var(--bg-secondary);
        border: 1px solid var(--border-dim);
        border-radius: 8px;
    }
</style>
