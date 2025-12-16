<!--
  Analytics Deep Dive - Detailed charts and insights
-->

<script lang="ts">
    import { onMount } from 'svelte';
    import {
        analyticsStore,
        categories,
        departments,
        errors,
        periodHours as periodHoursStore
    } from '$lib/stores/analytics';
    import LineChart from '$lib/components/admin/charts/LineChart.svelte';
    import DoughnutChart from '$lib/components/admin/charts/DoughnutChart.svelte';
    import BarChart from '$lib/components/admin/charts/BarChart.svelte';
    import ExportButton from '$lib/components/admin/charts/ExportButton.svelte';
    import DateRangePicker from '$lib/components/admin/charts/DateRangePicker.svelte';
    import {
        exportQueries,
        exportCategories,
        exportDepartments,
        exportErrors
    } from '$lib/utils/csvExport';

    let queriesByHour: Array<{ hour: string; count: number }> = [];

    onMount(async () => {
        await analyticsStore.loadAll();

        analyticsStore.subscribe((s) => {
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
        <DateRangePicker
            hours={$periodHoursStore}
            on:change={(e) => analyticsStore.reloadWithPeriod(e.detail.hours)}
        />
    </div>

    <!-- Query Volume Trend -->
    <div class="chart-section panel p-4 mb-6">
        <div class="chart-header flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-[#808080]">QUERY VOLUME TREND</h3>
            <ExportButton on:click={() => exportQueries(queriesByHour)} />
        </div>
        <LineChart data={queriesByHour} label="Queries" height="250px" />
    </div>

    <!-- Two Column Layout -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Category Breakdown -->
        <div class="chart-section panel p-4">
            <div class="chart-header flex items-center justify-between mb-4">
                <h3 class="text-sm font-semibold text-[#808080]">QUERY CATEGORIES</h3>
                <ExportButton on:click={() => exportCategories($categories)} />
            </div>
            <DoughnutChart data={$categories} height="280px" />
        </div>

        <!-- Department Comparison -->
        <div class="chart-section panel p-4">
            <div class="chart-header flex items-center justify-between mb-4">
                <h3 class="text-sm font-semibold text-[#808080]">DEPARTMENT COMPARISON</h3>
                <ExportButton on:click={() => exportDepartments($departments)} />
            </div>
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
        <div class="chart-header flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-[#808080]">RESPONSE TIME BY DEPARTMENT</h3>
            <ExportButton on:click={() => exportDepartments($departments)} />
        </div>
        <BarChart
            data={$departments}
            labelKey="department"
            valueKey="avg_response_time_ms"
            height="200px"
        />
    </div>

    <!-- Recent Errors -->
    <div class="errors-section panel p-4">
        <div class="chart-header flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-[#808080]">RECENT ERRORS</h3>
            <ExportButton
                on:click={() => exportErrors($errors)}
                disabled={$errors.length === 0}
            />
        </div>

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
