<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { fade, fly } from 'svelte/transition';
    import { cheeky, type PhraseCategory, SPINNERS } from '$lib/cheeky';

    // Props
    export let category: PhraseCategory = 'searching';
    export let spinnerType: keyof typeof SPINNERS = 'food';
    export let showProgress: boolean = false;
    export let progress: number = 0;
    export let rotationMs: number = 3000;
    export let size: 'sm' | 'md' | 'lg' = 'md';

    // State
    let phrase = '';
    let spinnerFrame = 0;
    let phraseKey = 0; // For transition keying

    // Get spinner frames
    $: spinner = SPINNERS[spinnerType] || SPINNERS.dots;

    // Intervals
    let phraseInterval: ReturnType<typeof setInterval>;
    let spinnerInterval: ReturnType<typeof setInterval>;

    function updatePhrase() {
        phrase = cheeky.get(category);
        phraseKey++; // Trigger transition
    }

    function updateSpinner() {
        spinnerFrame = (spinnerFrame + 1) % spinner.length;
    }

    onMount(() => {
        // Initial phrase
        updatePhrase();

        // Rotate phrase
        phraseInterval = setInterval(updatePhrase, rotationMs);

        // Animate spinner (100ms per frame)
        spinnerInterval = setInterval(updateSpinner, 100);
    });

    onDestroy(() => {
        clearInterval(phraseInterval);
        clearInterval(spinnerInterval);
    });

    // Size classes
    $: sizeClasses = {
        sm: 'loader-sm',
        md: 'loader-md',
        lg: 'loader-lg',
    }[size];
</script>

<div class="cheeky-loader {sizeClasses}" role="status" aria-live="polite">
    <div class="spinner-container">
        <span class="spinner">{spinner[spinnerFrame]}</span>
    </div>

    <div class="content">
        {#key phraseKey}
            <p
                class="phrase"
                in:fly={{ y: 10, duration: 200 }}
                out:fade={{ duration: 100 }}
            >
                {phrase}
            </p>
        {/key}

        {#if showProgress}
            <div class="progress-container">
                <div class="progress-bar">
                    <div
                        class="progress-fill"
                        style="width: {Math.min(100, Math.max(0, progress))}%"
                    ></div>
                </div>
                <span class="progress-text">{Math.round(progress)}%</span>
            </div>
        {/if}
    </div>
</div>

<style>
    .cheeky-loader {
        display: flex;
        align-items: flex-start;
        gap: 1rem;
        padding: 1rem 1.25rem;

        background: rgba(0, 255, 65, 0.05);
        border: 1px solid rgba(0, 255, 65, 0.15);
        border-radius: 12px;

        animation: pulse-border 2s ease-in-out infinite;
    }

    @keyframes pulse-border {
        0%, 100% { border-color: rgba(0, 255, 65, 0.15); }
        50% { border-color: rgba(0, 255, 65, 0.3); }
    }

    .spinner-container {
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .spinner {
        font-size: 1.5rem;
        line-height: 1;
        filter: drop-shadow(0 0 8px rgba(0, 255, 65, 0.5));
    }

    .content {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }

    .phrase {
        margin: 0;
        color: rgba(255, 255, 255, 0.7);
        font-size: 0.9rem;
        font-style: italic;
        line-height: 1.4;
        min-height: 1.4em;
    }

    .progress-container {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .progress-bar {
        flex: 1;
        height: 6px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 3px;
        overflow: hidden;
    }

    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #00ff41 0%, #00cc33 100%);
        border-radius: 3px;
        transition: width 0.3s ease;
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.5);
    }

    .progress-text {
        font-size: 0.75rem;
        font-weight: 600;
        color: #00ff41;
        min-width: 3ch;
        text-align: right;
        font-variant-numeric: tabular-nums;
    }

    /* Size variants */
    .loader-sm {
        padding: 0.75rem 1rem;
        gap: 0.75rem;
    }

    .loader-sm .spinner {
        font-size: 1.25rem;
    }

    .loader-sm .phrase {
        font-size: 0.8rem;
    }

    .loader-lg {
        padding: 1.5rem 2rem;
        gap: 1.25rem;
    }

    .loader-lg .spinner {
        font-size: 2rem;
    }

    .loader-lg .phrase {
        font-size: 1rem;
    }
</style>
