<script lang="ts">
    import { fly } from 'svelte/transition';
    import { page } from '$app/stores';
    import { currentUser, isSuperUser } from '$lib/stores/auth';
    import NavLink from './NavLink.svelte';
    import AdminDropdown from './AdminDropdown.svelte';
    import UserMenu from './UserMenu.svelte';

    // Reactive route detection
    $: currentPath = $page.url.pathname;

    // Admin access check - can see admin section
    $: canAccessAdmin = $currentUser?.can_manage_users || $currentUser?.is_super_user;

    // Mobile menu state
    let mobileMenuOpen = false;

    function toggleMobileMenu() {
        mobileMenuOpen = !mobileMenuOpen;
    }

    function closeMobileMenu() {
        mobileMenuOpen = false;
    }

    // Navigation items - always visible
    const primaryNav = [
        { href: '/', label: 'Chat', icon: 'chat' as const },
        { href: '/vault', label: 'Memory', icon: 'vault' as const },
    ];

    // Admin navigation for mobile menu
    const adminNav = [
        { href: '/admin', label: 'Nerve Center', icon: '🎛️' },
        { href: '/admin/analytics', label: 'Analytics', icon: '📊' },
        { href: '/admin/users', label: 'Users', icon: '👥' },
        { href: '/admin/audit', label: 'Audit Log', icon: '🔒', superOnly: true },
    ];
</script>

<nav class="intelligence-ribbon">
    <!-- Mobile hamburger (visible < 768px) -->
    <button class="mobile-toggle" on:click={toggleMobileMenu} aria-label="Menu">
        <span class="hamburger" class:open={mobileMenuOpen}>
            <span></span>
            <span></span>
            <span></span>
        </span>
    </button>

    <!-- Left Section: Brand + Primary Nav -->
    <div class="ribbon-left">
        <a href="/" class="brand">
            <span class="brand-icon">🧠</span>
            <span class="brand-text">
                <span class="brand-primary">Cogzy</span>
                <span class="brand-secondary"></span>
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

<!-- Mobile menu overlay -->
{#if mobileMenuOpen}
    <div
        class="mobile-overlay"
        on:click={closeMobileMenu}
        on:keydown={(e) => e.key === 'Escape' && closeMobileMenu()}
        role="button"
        tabindex="-1"
        aria-label="Close menu"
    ></div>
    <div class="mobile-menu" transition:fly={{ x: -280, duration: 200 }}>
        <div class="mobile-header">
            <span class="mobile-brand-icon">🧠</span>
            <span class="mobile-brand-text">Cogzy</span>
        </div>

        <nav class="mobile-nav">
            {#each primaryNav as item}
                <a
                    href={item.href}
                    class="mobile-link"
                    class:active={currentPath === item.href}
                    on:click={closeMobileMenu}
                >
                    <span class="mobile-link-label">{item.label}</span>
                </a>
            {/each}

            {#if canAccessAdmin}
                <div class="mobile-divider"></div>
                <div class="mobile-section-label">Admin Portal</div>
                {#each adminNav as item}
                    {#if !item.superOnly || $isSuperUser}
                        <a
                            href={item.href}
                            class="mobile-link admin"
                            class:active={currentPath === item.href}
                            on:click={closeMobileMenu}
                        >
                            <span class="mobile-link-icon">{item.icon}</span>
                            <span class="mobile-link-label">{item.label}</span>
                            {#if item.superOnly}
                                <span class="mobile-super-badge">SUPER</span>
                            {/if}
                        </a>
                    {/if}
                {/each}
            {/if}
        </nav>

        <div class="mobile-footer">
            <a href="/" class="mobile-back" on:click={closeMobileMenu}>
                ← Back to Chat
            </a>
        </div>
    </div>
{/if}

<style>
    .intelligence-ribbon {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: var(--ribbon-height, 56px);
        z-index: 1000;

        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 1.5rem;

        /* Glass morphism */
        background: var(--ribbon-bg, rgba(10, 10, 15, 0.85));
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);

        /* Subtle border */
        border-bottom: 1px solid var(--ribbon-border, rgba(0, 255, 65, 0.15));

        /* Glow effect */
        box-shadow:
            0 4px 30px rgba(0, 0, 0, 0.3),
            0 0 40px rgba(0, 255, 65, 0.05) inset;
    }

    /* Mobile toggle - hidden on desktop */
    .mobile-toggle {
        display: none;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        background: none;
        border: none;
        cursor: pointer;
        padding: 0;
        margin-right: 0.5rem;
    }

    .hamburger {
        display: flex;
        flex-direction: column;
        gap: 5px;
        width: 20px;
    }

    .hamburger span {
        display: block;
        height: 2px;
        width: 100%;
        background: #fff;
        border-radius: 1px;
        transition: all 0.3s ease;
        transform-origin: center;
    }

    .hamburger.open span:nth-child(1) {
        transform: rotate(45deg) translate(5px, 5px);
    }

    .hamburger.open span:nth-child(2) {
        opacity: 0;
    }

    .hamburger.open span:nth-child(3) {
        transform: rotate(-45deg) translate(5px, -5px);
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

    /* Mobile overlay */
    .mobile-overlay {
        position: fixed;
        top: 56px;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.6);
        z-index: 999;
    }

    /* Mobile slide-out menu */
    .mobile-menu {
        position: fixed;
        top: 56px;
        left: 0;
        bottom: 0;
        width: 280px;

        background: rgba(10, 10, 15, 0.98);
        border-right: 1px solid rgba(0, 255, 65, 0.2);
        z-index: 1000;

        display: flex;
        flex-direction: column;
    }

    .mobile-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 1.25rem 1.5rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .mobile-brand-icon {
        font-size: 1.25rem;
    }

    .mobile-brand-text {
        font-size: 0.95rem;
        font-weight: 600;
        color: #00ff41;
    }

    .mobile-nav {
        flex: 1;
        padding: 1rem;
        overflow-y: auto;
    }

    .mobile-link {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.875rem 1rem;
        margin-bottom: 0.25rem;

        color: rgba(255, 255, 255, 0.8);
        text-decoration: none;
        font-size: 0.95rem;
        border-radius: 8px;

        transition: all 0.15s ease;
    }

    .mobile-link:hover {
        background: rgba(0, 255, 65, 0.08);
        color: #fff;
    }

    .mobile-link.active {
        background: rgba(0, 255, 65, 0.15);
        color: #00ff41;
    }

    .mobile-link.admin {
        color: rgba(255, 255, 255, 0.7);
    }

    .mobile-link.admin:hover {
        background: rgba(255, 200, 0, 0.08);
    }

    .mobile-link.admin.active {
        background: rgba(255, 200, 0, 0.15);
        color: #ffc800;
    }

    .mobile-link-icon {
        font-size: 1.1rem;
        width: 24px;
        text-align: center;
    }

    .mobile-link-label {
        flex: 1;
    }

    .mobile-super-badge {
        font-size: 0.55rem;
        font-weight: 700;
        padding: 2px 6px;
        background: rgba(255, 0, 85, 0.2);
        color: #ff0055;
        border-radius: 3px;
        letter-spacing: 0.5px;
    }

    .mobile-divider {
        height: 1px;
        background: rgba(255, 255, 255, 0.08);
        margin: 0.75rem 0;
    }

    .mobile-section-label {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: rgba(255, 200, 0, 0.6);
        padding: 0.5rem 1rem;
    }

    .mobile-footer {
        padding: 1rem 1.5rem;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
    }

    .mobile-back {
        color: rgba(255, 255, 255, 0.5);
        text-decoration: none;
        font-size: 0.85rem;
        transition: color 0.2s ease;
    }

    .mobile-back:hover {
        color: #00ff41;
    }

    /* Tablet: compact nav */
    @media (max-width: 1024px) {
        .brand-text {
            display: none;
        }
    }

    /* Mobile: hamburger menu */
    @media (max-width: 768px) {
        .intelligence-ribbon {
            padding: 0 1rem;
        }

        .mobile-toggle {
            display: flex;
        }

        .brand-text {
            display: none;
        }

        .nav-divider {
            display: none;
        }

        .primary-nav {
            display: none;
        }

        .ribbon-right :global(.admin-dropdown) {
            display: none;
        }
    }
</style>
