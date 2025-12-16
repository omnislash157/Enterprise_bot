<!--
  ExportButton - Small download button for charts

  Usage:
    <ExportButton on:click={() => exportQueries(data)} />
-->

<script lang="ts">
    import { createEventDispatcher } from 'svelte';

    export let disabled: boolean = false;
    export let title: string = 'Export CSV';

    const dispatch = createEventDispatcher();

    function handleClick() {
        dispatch('click');
    }
</script>

<button class="export-btn" on:click={handleClick} {disabled} {title}>
    <svg
        xmlns="http://www.w3.org/2000/svg"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
    >
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="7 10 12 15 17 10" />
        <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
</button>

<style>
    .export-btn {
        padding: 4px 8px;
        background: transparent;
        border: 1px solid var(--border-dim);
        border-radius: 4px;
        color: var(--text-muted);
        cursor: pointer;
        transition: all 0.2s;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .export-btn:hover:not(:disabled) {
        border-color: var(--neon-green);
        color: var(--neon-green);
    }

    .export-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
</style>
