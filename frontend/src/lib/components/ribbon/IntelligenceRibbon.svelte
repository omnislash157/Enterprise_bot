<script lang="ts">
    import { page } from '$app/stores';
    import { currentUser } from '$lib/stores/auth';
    import NavLink from './NavLink.svelte';
    import AdminDropdown from './AdminDropdown.svelte';
    import UserMenu from './UserMenu.svelte';

    // Reactive route detection
    $: currentPath = $page.url.pathname;

    // Admin access check - can see admin section
    $: canAccessAdmin = $currentUser?.can_manage_users || $currentUser?.is_super_user;

    // Navigation items - always visible
    const primaryNav = [
        { href: '/', label: 'Chat', icon: 'chat' as const },
        { href: '/credit', label: 'Credits', icon: 'document' as const },
    ];
</script>

<nav class="intelligence-ribbon">
    <!-- Left Section: Brand + Primary Nav -->
    <div class="ribbon-left">
        <a href="/" class="brand">
            <span class="brand-icon">🧠</span>
            <span class="brand-text">
                <span class="brand-primary">Driscoll</span>
                <span class="brand-secondary">Intelligence</span>
            </span>
        </a>

        <div class="nav-divider"></div>

        <div class="primary-nav">
            {#each primaryNav as item}
                <NavLink
                    href={item.href}
                    active={currentPath === item.href}
                    icon={item.icon}
                >
                    {item.label}
                </NavLink>
            {/each}
        </div>
    </div>

    <!-- Right Section: Admin + User -->
    <div class="ribbon-right">
        {#if canAccessAdmin}
            <AdminDropdown {currentPath} />
        {/if}

        <UserMenu />
    </div>
</nav>

<style>
    .intelligence-ribbon {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 56px;
        z-index: 1000;

        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 1.5rem;

        /* Glass morphism */
        background: rgba(10, 10, 15, 0.85);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);

        /* Subtle border */
        border-bottom: 1px solid rgba(0, 255, 65, 0.15);

        /* Glow effect */
        box-shadow:
            0 4px 30px rgba(0, 0, 0, 0.3),
            0 0 40px rgba(0, 255, 65, 0.05) inset;
    }

    .ribbon-left {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        text-decoration: none;
        padding: 0.5rem;
        border-radius: 8px;
        transition: all 0.2s ease;
    }

    .brand:hover {
        background: rgba(0, 255, 65, 0.08);
    }

    .brand-icon {
        font-size: 1.5rem;
        filter: drop-shadow(0 0 8px rgba(0, 255, 65, 0.5));
    }

    .brand-text {
        display: flex;
        flex-direction: column;
        line-height: 1.1;
    }

    .brand-primary {
        font-size: 0.9rem;
        font-weight: 700;
        color: #fff;
        letter-spacing: 0.5px;
    }

    .brand-secondary {
        font-size: 0.7rem;
        font-weight: 400;
        color: rgba(0, 255, 65, 0.8);
        text-transform: uppercase;
        letter-spacing: 2px;
    }

    .nav-divider {
        width: 1px;
        height: 24px;
        background: linear-gradient(
            to bottom,
            transparent,
            rgba(0, 255, 65, 0.3),
            transparent
        );
        margin: 0 0.5rem;
    }

    .primary-nav {
        display: flex;
        align-items: center;
        gap: 0.25rem;
    }

    .ribbon-right {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    /* Mobile: hide brand text, compact nav */
    @media (max-width: 768px) {
        .intelligence-ribbon {
            padding: 0 1rem;
        }

        .brand-text {
            display: none;
        }

        .nav-divider {
            display: none;
        }
    }
</style>
