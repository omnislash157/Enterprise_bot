<!--
  DoughnutChart - Category breakdown visualization

  Usage:
    <DoughnutChart data={categories} />
-->

<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { Chart, registerables } from 'chart.js';
    import { categoryColors, doughnutOptions } from './chartTheme';

    Chart.register(...registerables);

    export let data: Array<{ category: string; count: number }> = [];
    export let height: string = '250px';

    let canvas: HTMLCanvasElement;
    let chart: Chart | null = null;

    function createChart() {
        if (!canvas) return;

        if (chart) chart.destroy();

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(d => d.category),
                datasets: [{
                    data: data.map(d => d.count),
                    backgroundColor: categoryColors.slice(0, data.length),
                    borderColor: '#0a0a0a',
                    borderWidth: 2,
                }],
            },
            options: doughnutOptions as any,
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
