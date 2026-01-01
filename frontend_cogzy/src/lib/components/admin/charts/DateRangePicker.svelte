<!--
  DateRangePicker - Period selector for analytics

  Usage:
    <DateRangePicker bind:hours on:change={handleChange} />
-->

<script lang="ts">
    import { createEventDispatcher } from 'svelte';

    export let hours: number = 24;

    const dispatch = createEventDispatcher();

    const options = [
        { value: 1, label: '1 Hour' },
        { value: 6, label: '6 Hours' },
        { value: 24, label: '24 Hours' },
        { value: 72, label: '3 Days' },
        { value: 168, label: '7 Days' }
    ];

    function select(value: number) {
        hours = value;
        dispatch('change', { hours: value });
    }
</script>

<div class="date-range-picker">
    {#each options as opt}
        <button class="range-btn" class:active={hours === opt.value} on:click={() => select(opt.value)}>
            {opt.label}
        </button>
    {/each}
</div>

<style>
    .date-range-picker {
        display: flex;
        gap: 4px;
        background: var(--bg-tertiary);
        padding: 4px;
        border-radius: 6px;
    }

    .range-btn {
        padding: 6px 12px;
        font-size: 12px;
        background: transparent;
        border: none;
        border-radius: 4px;
        color: var(--text-muted);
        cursor: pointer;
        transition: all 0.2s;
    }

    .range-btn:hover {
        color: var(--text-primary);
    }

    .range-btn.active {
        background: var(--neon-green);
        color: var(--bg-primary);
        font-weight: 600;
    }
</style>
