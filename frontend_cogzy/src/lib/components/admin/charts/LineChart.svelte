<!--
  LineChart - Queries over time visualization

  Usage:
    <LineChart data={queriesByHour} label="Queries" />
-->

<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { Chart, registerables } from 'chart.js';
    import { chartColors, lineChartOptions } from './chartTheme';

    Chart.register(...registerables);

    export let data: Array<{ hour: string; count: number }> = [];
    export let label: string = 'Queries';
    export let height: string = '200px';

    let canvas: HTMLCanvasElement;
    let chart: Chart | null = null;

    function formatHour(isoString: string): string {
        const d = new Date(isoString);
        return d.toLocaleTimeString('en-US', { hour: 'numeric', hour12: true });
    }

    function createChart() {
        if (!canvas) return;

        if (chart) chart.destroy();

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Create gradient fill
        const gradient = ctx.createLinearGradient(0, 0, 0, 200);
        gradient.addColorStop(0, 'rgba(0, 255, 65, 0.3)');
        gradient.addColorStop(1, 'rgba(0, 255, 65, 0)');

        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => formatHour(d.hour)),
                datasets: [{
                    label,
                    data: data.map(d => d.count),
                    borderColor: chartColors.primary,
                    backgroundColor: gradient,
                    fill: true,
                }],
            },
            options: lineChartOptions as any,
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
