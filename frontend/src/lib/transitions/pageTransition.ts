import { cubicOut } from 'svelte/easing';

export const pageTransition = {
    duration: 200,
    easing: cubicOut,
};

export function fadeSlide(node: HTMLElement, { delay = 0, duration = 200 }) {
    return {
        delay,
        duration,
        css: (t: number) => `
            opacity: ${t};
            transform: translateY(${(1 - t) * 10}px);
        `
    };
}
