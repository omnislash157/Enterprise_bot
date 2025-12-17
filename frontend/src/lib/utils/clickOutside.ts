/**
 * Svelte action for detecting clicks outside an element
 * Usage: <div use:clickOutside={handleClose}>
 */
export function clickOutside(node: HTMLElement, callback: () => void) {
    const handleClick = (event: MouseEvent) => {
        if (
            node &&
            !node.contains(event.target as Node) &&
            !event.defaultPrevented
        ) {
            callback();
        }
    };

    // Delay adding listener to avoid immediate trigger
    setTimeout(() => {
        document.addEventListener('click', handleClick, true);
    }, 0);

    return {
        destroy() {
            document.removeEventListener('click', handleClick, true);
        }
    };
}
