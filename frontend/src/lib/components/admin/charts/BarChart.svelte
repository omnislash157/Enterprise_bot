<!--
  BarChart - Department comparison visualization

  Usage:
    <BarChart data={departments} labelKey="department" valueKey="query_count" />
-->

<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { Chart, registerables } from 'chart.js';
    import { chartColors, barChartOptions } from './chartTheme';

    Chart.register(...registerables);

    export let data: Array<Record<string, any>> = [];
    export let labelKey: string = 'label';
    export let valueKey: string = 'value';
    export let height: string = '200px';
    export let horizontal: boolean = false;

    let canvas: HTMLCanvasElement;
    let chart: Chart | null = null;

    function createChart() {
        if (!canvas) return;

        if (chart) chart.destroy();

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d[labelKey]),
                datasets: [{
                    data: data.map(d => d[valueKey]),
                    backgroundColor: chartColors.primary,
                    borderColor: chartColors.primary,
                    borderWidth: 1,
                    borderRadius: 4,
                }],
            },
            options: {
                ...barChartOptions,
                indexAxis: horizontal ? 'y' : 'x',
            } as any,
        });
    }

    $: if (data && canvas) createChart();

    onMount(() => {
        createChart();
    });

    onDestroy(() => {
        if (chart) chart.destroy();
    });
</script>

<div class="chart-container" style="height: {height}">
    <canvas bind:this={canvas}></canvas>
</div>

<style>
    .chart-container {
        position: relative;
        width: 100%;
    }
</style>
