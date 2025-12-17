<script lang="ts">
    export let href: string;
    export let active: boolean = false;
    export let icon: 'chat' | 'document' | 'chart' | 'users' | 'shield' = 'chat';

    // Icon SVG paths (inline for performance)
    const icons = {
        chat: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
        document: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
        chart: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
        users: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
        shield: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
    };
</script>

<a
    {href}
    class="nav-link"
    class:active
    data-sveltekit-preload-data="hover"
>
    <svg
        class="nav-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
    >
        <path d={icons[icon]} />
    </svg>
    <span class="nav-label"><slot /></span>

    {#if active}
        <div class="active-indicator"></div>
    {/if}
</a>

<style>
    .nav-link {
        position: relative;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 6px;

        color: rgba(255, 255, 255, 0.7);
        text-decoration: none;
        font-size: 0.875rem;
        font-weight: 500;

        transition: all 0.2s ease;
    }

    .nav-link:hover {
        color: #fff;
        background: rgba(255, 255, 255, 0.08);
    }

    .nav-link.active {
        color: #00ff41;
        background: rgba(0, 255, 65, 0.1);
    }

    .nav-icon {
        width: 18px;
        height: 18px;
        flex-shrink: 0;
    }

    .nav-label {
        white-space: nowrap;
    }

    .active-indicator {
        position: absolute;
        bottom: -1px;
        left: 50%;
        transform: translateX(-50%);
        width: 60%;
        height: 2px;
        background: linear-gradient(90deg, transparent, #00ff41, transparent);
        border-radius: 1px;
    }

    /* Mobile: icon only */
    @media (max-width: 640px) {
        .nav-link {
            padding: 0.5rem 0.75rem;
        }

        .nav-label {
            display: none;
        }
    }
</style>
