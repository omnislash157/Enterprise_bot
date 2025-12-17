<script lang="ts">
    import { page } from '$app/stores';
    import { goto } from '$app/navigation';
    import { onMount } from 'svelte';
    import { auth, currentUser, isSuperUser } from '$lib/stores/auth';
    import { adminStore } from '$lib/stores/admin';

    // Check access based on user permissions
    $: canAccess = $currentUser?.can_manage_users || $currentUser?.is_super_user;
    $: isSuperRoute = $page.url.pathname === '/admin/audit';
    $: needsSuperAccess = isSuperRoute && !$isSuperUser;

    // Redirect unauthorized users
    $: if ($currentUser && !canAccess) {
        goto('/');
    }

    // Redirect non-super users from audit
    $: if ($currentUser && needsSuperAccess) {
        goto('/admin');
    }

    // Load admin data on mount
    onMount(() => {
        if (canAccess) {
            adminStore.loadDepartments();
            adminStore.loadStats();
        }
    });

    // Admin navigation sidebar items
    const adminNav = [
        {
            href: '/admin',
            label: 'Nerve Center',
            icon: '🎛️',
            description: 'System overview dashboard'
        },
        {
            href: '/admin/analytics',
            label: 'Analytics',
            icon: '📊',
            description: 'Usage and performance metrics'
        },
        {
            href: '/admin/users',
            label: 'Users',
            icon: '👥',
            description: 'Manage user access'
        },
        {
            href: '/admin/audit',
            label: 'Audit Log',
            icon: '🔒',
            superOnly: true,
            description: 'Security and change history'
        },
    ];

    $: currentPath = $page.url.pathname;
</script>

{#if !$currentUser}
    <!-- Loading state while auth resolves -->
    <div class="admin-loading">
        <div class="spinner"></div>
        <p>Verifying access...</p>
    </div>
{:else if !canAccess}
    <!-- Redirect happening, show nothing -->
    <div class="admin-loading">
        <p>Access denied. Redirecting...</p>
    </div>
{:else}
    <div class="admin-layout">
        <!-- Sidebar Navigation -->
        <aside class="admin-sidebar">
            <div class="sidebar-header">
                <span class="header-icon">⚡</span>
                <span class="header-text">Admin Portal</span>
            </div>

            <nav class="sidebar-nav">
                {#each adminNav as item}
                    {#if !item.superOnly || $isSuperUser}
                        <a
                            href={item.href}
                            class="nav-item"
                            class:active={currentPath === item.href}
                        >
                            <span class="nav-icon">{item.icon}</span>
                            <div class="nav-content">
                                <span class="nav-label">{item.label}</span>
                                <span class="nav-desc">{item.description}</span>
                            </div>
                            {#if item.superOnly}
                                <span class="super-badge">SUPER</span>
                            {/if}
                        </a>
                    {/if}
                {/each}
            </nav>

            <div class="sidebar-footer">
                <a href="/" class="back-link">
                    ← Back to Chat
                </a>
            </div>
        </aside>

        <!-- Main Content Area -->
        <main class="admin-main">
            <slot />
        </main>
    </div>
{/if}

<style>
    .admin-layout {
        display: flex;
        min-height: calc(100vh - 56px);
        background: #0a0a0f;
    }

    .admin-sidebar {
        width: 280px;
        flex-shrink: 0;

        display: flex;
        flex-direction: column;

        background: rgba(15, 15, 20, 0.95);
        border-right: 1px solid rgba(255, 200, 0, 0.1);
    }

    .sidebar-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 1.5rem;

        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .header-icon {
        font-size: 1.25rem;
    }

    .header-text {
        font-size: 1rem;
        font-weight: 600;
        color: #ffc800;
        letter-spacing: 0.5px;
    }

    .sidebar-nav {
        flex: 1;
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .nav-item {
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
        padding: 0.875rem 1rem;

        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;

        color: rgba(255, 255, 255, 0.7);
        text-decoration: none;

        transition: all 0.2s ease;
    }

    .nav-item:hover {
        background: rgba(255, 200, 0, 0.05);
        border-color: rgba(255, 200, 0, 0.1);
        color: #fff;
    }

    .nav-item.active {
        background: rgba(255, 200, 0, 0.1);
        border-color: rgba(255, 200, 0, 0.3);
        color: #ffc800;
    }

    .nav-icon {
        font-size: 1.25rem;
        width: 28px;
        text-align: center;
        flex-shrink: 0;
    }

    .nav-content {
        flex: 1;
        min-width: 0;
    }

    .nav-label {
        display: block;
        font-size: 0.9rem;
        font-weight: 500;
    }

    .nav-desc {
        display: block;
        font-size: 0.75rem;
        color: rgba(255, 255, 255, 0.4);
        margin-top: 2px;
    }

    .nav-item.active .nav-desc {
        color: rgba(255, 200, 0, 0.6);
    }

    .super-badge {
        align-self: center;
        font-size: 0.55rem;
        font-weight: 700;
        padding: 2px 6px;
        background: rgba(255, 0, 85, 0.2);
        color: #ff0055;
        border-radius: 3px;
        letter-spacing: 0.5px;
    }

    .sidebar-footer {
        padding: 1rem 1.5rem;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
    }

    .back-link {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;

        color: rgba(255, 255, 255, 0.5);
        text-decoration: none;
        font-size: 0.85rem;

        transition: color 0.2s ease;
    }

    .back-link:hover {
        color: #00ff41;
    }

    .admin-main {
        flex: 1;
        padding: 2rem;
        overflow-y: auto;
    }

    .admin-loading {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: calc(100vh - 56px);
        color: rgba(255, 255, 255, 0.5);
    }

    .spinner {
        width: 32px;
        height: 32px;
        border: 3px solid rgba(255, 200, 0, 0.2);
        border-top-color: #ffc800;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
        margin-bottom: 1rem;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    /* Mobile: Collapsible sidebar */
    @media (max-width: 1024px) {
        .admin-sidebar {
            width: 72px;
        }

        .sidebar-header .header-text,
        .nav-content,
        .super-badge,
        .back-link {
            display: none;
        }

        .nav-item {
            justify-content: center;
            padding: 0.75rem;
        }

        .nav-icon {
            width: auto;
        }
    }
</style>
