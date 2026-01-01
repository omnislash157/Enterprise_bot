<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { cheeky, type PhraseCategory, SPINNERS } from '$lib/cheeky';

    export let category: PhraseCategory = 'searching';
    export let spinnerType: keyof typeof SPINNERS = 'dots';
    export let rotationMs: number = 3000;

    let phrase = '';
    let spinnerFrame = 0;

    $: spinner = SPINNERS[spinnerType] || SPINNERS.dots;

    let phraseInterval: ReturnType<typeof setInterval>;
    let spinnerInterval: ReturnType<typeof setInterval>;

    onMount(() => {
        phrase = cheeky.get(category);
        phraseInterval = setInterval(() => {
            phrase = cheeky.get(category);
        }, rotationMs);
        spinnerInterval = setInterval(() => {
            spinnerFrame = (spinnerFrame + 1) % spinner.length;
        }, 100);
    });

    onDestroy(() => {
        clearInterval(phraseInterval);
        clearInterval(spinnerInterval);
    });
</script>

<span class="cheeky-inline">
    <span class="spinner">{spinner[spinnerFrame]}</span>
    <span class="phrase">{phrase}</span>
</span>

<style>
    .cheeky-inline {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        color: rgba(255, 255, 255, 0.6);
        font-size: 0.875rem;
    }

    .spinner {
        flex-shrink: 0;
    }

    .phrase {
        font-style: italic;
    }
</style>
