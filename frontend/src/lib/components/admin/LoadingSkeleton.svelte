<script lang="ts">
    export let lines: number = 3;
    export let height: string = '1rem';
</script>

<div class="skeleton-container">
    {#each Array(lines) as _, i}
        <div
            class="skeleton-line"
            style="
                height: {height};
                width: {90 - (i * 15)}%;
                animation-delay: {i * 0.1}s;
            "
        ></div>
    {/each}
</div>

<style>
    .skeleton-container {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }

    .skeleton-line {
        background: linear-gradient(
            90deg,
            rgba(255, 255, 255, 0.05) 0%,
            rgba(255, 255, 255, 0.1) 50%,
            rgba(255, 255, 255, 0.05) 100%
        );
        background-size: 200% 100%;
        border-radius: 4px;
        animation: shimmer 1.5s ease-in-out infinite;
    }

    @keyframes shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
</style>
