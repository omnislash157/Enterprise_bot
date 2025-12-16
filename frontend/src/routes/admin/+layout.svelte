<script lang="ts">
    import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { auth, isSuperUser } from '$lib/stores/auth';
    import { adminStore, adminStats, adminStatsLoading } from '$lib/stores/admin';

    // Check admin access on mount
    let hasAccess = false;
    let checking = true;

    onMount(async () => {
        // Check if user has admin permissions
        const email = auth.getEmail();
        if (!email) {
            goto('/');
            return;
        }

        // Fetch whoami to verify permissions
        try {
            const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const res = await fetch(`${apiBase}/api/whoami`, {
                headers: { 'X-User-Email': email }
            });

            if (res.ok) {
                const data = await res.json();
                const user = data.user;
                const canAdmin = user?.can_manage_users ||
                                 user?.is_super_user ||
                                 user?.tier === 'SUPER_USER' ||
                                 user?.role === 'super_user' ||
                                 user?.role === 'dept_head';

                if (canAdmin) {
                    hasAccess = true;
                    // Load initial data
                    adminStore.loadDepartments();
                    adminStore.loadStats();
                } else {
                    goto('/');
                }
            } else {
                goto('/');
            }
        } catch (e) {
            console.error('[Admin] Auth check failed:', e);
            goto('/');
        }

        checking = false;
    });

    // Navigation items
    const navItems = [
        { path: '/admin', label: 'Nerve Center', icon: 'chart' },
        { path: '/admin/analytics', label: 'Analytics', icon: 'analytics' },
        { path: '/admin/users', label: 'Users', icon: 'users' },
        { path: '/admin/audit', label: 'Audit Log', icon: 'shield', superOnly: true },
    ];

    $: currentPath = $page.url.pathname;
</script>

{#if checking}
    <div class="loading-screen">
        <div class="spinner"></div>
        <p>Verifying access...</p>
    </div>
{:else if hasAccess}
    <div class="admin-layout">
        <!-- Sidebar -->
        <aside class="sidebar">
            <div class="sidebar-header">
                <span class="logo-icon">&#9881;</span>
                <h2>Admin Portal</h2>
            </div>

            <nav class="sidebar-nav">
                {#each navItems as item}
                    {#if !item.superOnly || $isSuperUser}
                        <a
                            href={item.path}
                            class="nav-item"
                            class:active={currentPath === item.path}
                        >
                            <span class="nav-icon">
                                {#if item.icon === 'chart'}
                                    &#128202;
                                {:else if item.icon === 'users'}
                                    &#128101;
                                {:else if item.icon === 'analytics'}
                                    &#128200;
                                {:else if item.icon === 'shield'}
                                    &#128737;
                                {/if}
                            </span>
                            <span class="nav-label">{item.label}</span>
                        </a>
                    {/if}
                {/each}
            </nav>

            <!-- Quick Stats -->
            {#if $adminStats && !$adminStatsLoading}
                <div class="sidebar-stats">
                    <div class="stat-item">
                        <span class="stat-value">{$adminStats.total_users}</span>
                        <span class="stat-label">Total Users</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-value">{$adminStats.recent_logins_7d}</span>
                        <span class="stat-label">Logins (7d)</span>
                    </div>
                </div>
            {/if}

            <!-- Back to Chat -->
            <div class="sidebar-footer">
                <a href="/" class="back-link">
                    <span>&#8592;</span> Back to Chat
                </a>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="main-content">
            <slot />
        </main>
    </div>
{:else}
    <div class="access-denied">
        <h1>Access Denied</h1>
        <p>You don't have permission to access the admin portal.</p>
        <a href="/">Return to Chat</a>
    </div>
{/if}

<style>
    .loading-screen {
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
        color: #888;
    }

    .loading-screen .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid rgba(255, 255, 255, 0.1);
        border-top-color: #00ff88;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
        margin-bottom: 1rem;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    .admin-layout {
        display: flex;
        min-height: 100vh;
        background: #0a0a0a;
    }

    /* Sidebar */
    .sidebar {
        width: 260px;
        background: rgba(10, 10, 10, 0.95);
        border-right: 1px solid rgba(0, 255, 65, 0.2);
        display: flex;
        flex-direction: column;
        position: fixed;
        top: 0;
        left: 0;
        height: 100vh;
        z-index: 100;
    }

    .sidebar-header {
        padding: 1.5rem;
        border-bottom: 1px solid rgba(0, 255, 65, 0.1);
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .logo-icon {
        font-size: 1.5rem;
        color: #00ff41;
    }

    .sidebar-header h2 {
        font-size: 1.1rem;
        font-weight: 600;
        color: #e0e0e0;
        margin: 0;
    }

    .sidebar-nav {
        flex: 1;
        padding: 1rem 0;
    }

    .nav-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.875rem 1.5rem;
        color: #888;
        text-decoration: none;
        transition: all 0.2s;
        border-left: 3px solid transparent;
    }

    .nav-item:hover {
        color: #e0e0e0;
        background: rgba(0, 255, 65, 0.05);
    }

    .nav-item.active {
        color: #00ff41;
        background: rgba(0, 255, 65, 0.1);
        border-left-color: #00ff41;
    }

    .nav-icon {
        font-size: 1.1rem;
        width: 24px;
        text-align: center;
    }

    .nav-label {
        font-size: 0.95rem;
    }

    .sidebar-stats {
        padding: 1rem 1.5rem;
        border-top: 1px solid rgba(0, 255, 65, 0.1);
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
    }

    .stat-item {
        text-align: center;
    }

    .stat-value {
        display: block;
        font-size: 1.5rem;
        font-weight: 600;
        color: #00ff41;
    }

    .stat-label {
        font-size: 0.75rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .sidebar-footer {
        padding: 1rem 1.5rem;
        border-top: 1px solid rgba(0, 255, 65, 0.1);
    }

    .back-link {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: #666;
        text-decoration: none;
        font-size: 0.9rem;
        transition: color 0.2s;
    }

    .back-link:hover {
        color: #00ff41;
    }

    /* Main Content */
    .main-content {
        flex: 1;
        margin-left: 260px;
        padding: 2rem;
        min-height: 100vh;
    }

    /* Access Denied */
    .access-denied {
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: #0a0a0a;
        color: #e0e0e0;
        text-align: center;
    }

    .access-denied h1 {
        color: #ff4444;
        margin-bottom: 1rem;
    }

    .access-denied p {
        color: #888;
        margin-bottom: 2rem;
    }

    .access-denied a {
        color: #00ff41;
        text-decoration: none;
    }

    .access-denied a:hover {
        text-decoration: underline;
    }

    /* Responsive */
    @media (max-width: 768px) {
        .sidebar {
            width: 60px;
        }

        .sidebar-header h2,
        .nav-label,
        .sidebar-stats,
        .sidebar-footer {
            display: none;
        }

        .sidebar-header {
            justify-content: center;
        }

        .nav-item {
            justify-content: center;
            padding: 1rem;
        }

        .main-content {
            margin-left: 60px;
            padding: 1rem;
        }
    }
</style>
