<!--
  StatCard - Single metric display with optional trend indicator

  Usage:
    <StatCard
      label="Active Users"
      value={47}
      trend={12}
      trendLabel="↑ from yesterday"
      color="green"
    />
-->

<script lang="ts">
    export let label: string;
    export let value: number | string;
    export let trend: number | null = null;
    export let trendLabel: string = '';
    export let color: 'green' | 'cyan' | 'amber' | 'red' = 'green';
    export let loading: boolean = false;
    export let format: 'number' | 'ms' | 'percent' = 'number';

    function formatValue(v: number | string): string {
        if (typeof v === 'string') return v;
        if (format === 'ms') return `${(v / 1000).toFixed(1)}s`;
        if (format === 'percent') return `${v.toFixed(1)}%`;
        return v.toLocaleString();
    }

    const colorClasses = {
        green: 'text-[#00ff41] border-[#00ff41]/30',
        cyan: 'text-[#00ffff] border-[#00ffff]/30',
        amber: 'text-[#ffaa00] border-[#ffaa00]/30',
        red: 'text-[#ff4444] border-[#ff4444]/30',
    };
</script>

<div class="stat-card panel p-4 {colorClasses[color]}">
    {#if loading}
        <div class="animate-pulse">
            <div class="h-8 bg-[#222] rounded w-20 mb-2"></div>
            <div class="h-4 bg-[#222] rounded w-16"></div>
        </div>
    {:else}
        <div class="value text-3xl font-bold {colorClasses[color].split(' ')[0]}">
            {formatValue(value)}
        </div>
        <div class="label text-sm text-[#808080] mt-1">{label}</div>

        {#if trend !== null}
            <div class="trend text-xs mt-2 {trend >= 0 ? 'text-[#00ff41]' : 'text-[#ff4444]'}">
                {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)} {trendLabel}
            </div>
        {/if}
    {/if}
</div>

<style>
    .stat-card {
        background: var(--bg-secondary);
        border: 1px solid var(--border-dim);
        border-radius: 8px;
        min-width: 140px;
    }

    .stat-card:hover {
        box-shadow: 0 0 15px var(--border-glow);
    }
</style>
