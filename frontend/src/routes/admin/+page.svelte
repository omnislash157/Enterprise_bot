<script lang="ts">
    import { onMount } from 'svelte';
    import { adminStore, adminStats, adminStatsLoading, adminDepartments } from '$lib/stores/admin';
    import { isSuperUser } from '$lib/stores/auth';

    onMount(() => {
        adminStore.loadStats();
    });

    // Role labels for display
    const roleLabels: Record<string, string> = {
        user: 'Users',
        dept_head: 'Dept Heads',
        super_user: 'Super Users',
    };

    // Role colors
    const roleColors: Record<string, string> = {
        user: '#3b82f6',
        dept_head: '#f59e0b',
        super_user: '#00ff41',
    };
</script>

<svelte:head>
    <title>Admin Dashboard - Driscoll Intelligence</title>
</svelte:head>

<div class="dashboard">
    <header class="page-header">
        <h1>Admin Dashboard</h1>
        <p class="subtitle">System overview and quick actions</p>
    </header>

    {#if $adminStatsLoading}
        <div class="loading">
            <div class="spinner"></div>
            <p>Loading statistics...</p>
        </div>
    {:else if $adminStats}
        <!-- Quick Stats Grid -->
        <div class="stats-grid">
            <div class="stat-card primary">
                <div class="stat-icon">&#128101;</div>
                <div class="stat-content">
                    <span class="stat-value">{$adminStats.total_users}</span>
                    <span class="stat-label">Total Users</span>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-icon">&#128736;</div>
                <div class="stat-content">
                    <span class="stat-value">{$adminStats.users_by_role?.super_user || 0}</span>
                    <span class="stat-label">Super Users</span>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-icon">&#128100;</div>
                <div class="stat-content">
                    <span class="stat-value">{$adminStats.users_by_role?.dept_head || 0}</span>
                    <span class="stat-label">Dept Heads</span>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-icon">&#128200;</div>
                <div class="stat-content">
                    <span class="stat-value">{$adminStats.recent_logins_7d}</span>
                    <span class="stat-label">Logins (7 days)</span>
                </div>
            </div>
        </div>

        <!-- Users by Role Chart (simple bar) -->
        <div class="section">
            <h2>Users by Role</h2>
            <div class="role-bars">
                {#each Object.entries($adminStats.users_by_role || {}) as [role, count]}
                    <div class="role-bar-row">
                        <span class="role-label">{roleLabels[role] || role}</span>
                        <div class="role-bar-container">
                            <div
                                class="role-bar"
                                style="width: {Math.min(100, (count / $adminStats.total_users) * 100)}%; background: {roleColors[role] || '#666'}"
                            ></div>
                        </div>
                        <span class="role-count">{count}</span>
                    </div>
                {/each}
            </div>
        </div>

        <!-- Users by Department -->
        <div class="section">
            <h2>Users by Department</h2>
            <div class="department-grid">
                {#each $adminStats.users_by_department || [] as dept}
                    <div class="dept-card">
                        <div class="dept-name">{dept.name}</div>
                        <div class="dept-count">{dept.user_count}</div>
                        <div class="dept-label">users</div>
                    </div>
                {/each}
            </div>
        </div>

        <!-- Recent Activity -->
        <div class="section">
            <h2>Recent Activity</h2>
            <div class="activity-summary">
                <div class="activity-item">
                    <span class="activity-icon">&#128275;</span>
                    <div class="activity-content">
                        <span class="activity-value">{$adminStats.recent_logins_7d}</span>
                        <span class="activity-label">User logins in the last 7 days</span>
                    </div>
                </div>
                <div class="activity-item">
                    <span class="activity-icon">&#128221;</span>
                    <div class="activity-content">
                        <span class="activity-value">{$adminStats.recent_access_changes_7d}</span>
                        <span class="activity-label">Access changes in the last 7 days</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="section">
            <h2>Quick Actions</h2>
            <div class="actions-grid">
                <a href="/admin/users" class="action-card">
                    <span class="action-icon">&#128101;</span>
                    <span class="action-label">Manage Users</span>
                </a>
                {#if $isSuperUser}
                    <a href="/admin/audit" class="action-card">
                        <span class="action-icon">&#128737;</span>
                        <span class="action-label">View Audit Log</span>
                    </a>
                {/if}
            </div>
        </div>
    {:else}
        <div class="error">
            <p>Failed to load statistics</p>
            <button on:click={() => adminStore.loadStats()}>Retry</button>
        </div>
    {/if}
</div>

<style>
    .dashboard {
        max-width: 1200px;
        margin: 0 auto;
    }

    .page-header {
        margin-bottom: 2rem;
    }

    .page-header h1 {
        font-size: 1.75rem;
        font-weight: 600;
        color: #e0e0e0;
        margin: 0 0 0.5rem 0;
    }

    .subtitle {
        color: #666;
        margin: 0;
    }

    .loading {
        text-align: center;
        padding: 4rem 2rem;
        color: #888;
    }

    .loading .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid rgba(255, 255, 255, 0.1);
        border-top-color: #00ff88;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
        margin: 0 auto 1rem;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    /* Stats Grid */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-bottom: 2rem;
    }

    .stat-card {
        background: rgba(20, 20, 20, 0.8);
        border: 1px solid rgba(0, 255, 65, 0.15);
        border-radius: 12px;
        padding: 1.25rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .stat-card.primary {
        border-color: rgba(0, 255, 65, 0.3);
        background: rgba(0, 255, 65, 0.05);
    }

    .stat-icon {
        font-size: 2rem;
        opacity: 0.7;
    }

    .stat-content {
        display: flex;
        flex-direction: column;
    }

    .stat-value {
        font-size: 1.75rem;
        font-weight: 600;
        color: #e0e0e0;
    }

    .stat-card.primary .stat-value {
        color: #00ff41;
    }

    .stat-label {
        font-size: 0.85rem;
        color: #666;
    }

    /* Sections */
    .section {
        background: rgba(20, 20, 20, 0.8);
        border: 1px solid rgba(0, 255, 65, 0.15);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }

    .section h2 {
        font-size: 1.1rem;
        font-weight: 600;
        color: #e0e0e0;
        margin: 0 0 1.25rem 0;
    }

    /* Role Bars */
    .role-bars {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }

    .role-bar-row {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .role-label {
        width: 100px;
        font-size: 0.9rem;
        color: #888;
    }

    .role-bar-container {
        flex: 1;
        height: 24px;
        background: rgba(0, 0, 0, 0.3);
        border-radius: 4px;
        overflow: hidden;
    }

    .role-bar {
        height: 100%;
        border-radius: 4px;
        transition: width 0.5s ease;
    }

    .role-count {
        width: 40px;
        text-align: right;
        font-size: 0.9rem;
        color: #e0e0e0;
        font-weight: 500;
    }

    /* Department Grid */
    .department-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: 1rem;
    }

    .dept-card {
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }

    .dept-name {
        font-size: 0.85rem;
        color: #888;
        margin-bottom: 0.5rem;
        text-transform: capitalize;
    }

    .dept-count {
        font-size: 1.5rem;
        font-weight: 600;
        color: #00ff41;
    }

    .dept-label {
        font-size: 0.75rem;
        color: #555;
    }

    /* Activity Summary */
    .activity-summary {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .activity-item {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1rem;
        background: rgba(0, 0, 0, 0.3);
        border-radius: 8px;
    }

    .activity-icon {
        font-size: 1.5rem;
        opacity: 0.7;
    }

    .activity-content {
        display: flex;
        flex-direction: column;
    }

    .activity-value {
        font-size: 1.25rem;
        font-weight: 600;
        color: #e0e0e0;
    }

    .activity-label {
        font-size: 0.85rem;
        color: #666;
    }

    /* Actions Grid */
    .actions-grid {
        display: flex;
        gap: 1rem;
        flex-wrap: wrap;
    }

    .action-card {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 1rem 1.5rem;
        background: rgba(0, 255, 65, 0.1);
        border: 1px solid rgba(0, 255, 65, 0.3);
        border-radius: 8px;
        color: #00ff41;
        text-decoration: none;
        transition: all 0.2s;
    }

    .action-card:hover {
        background: rgba(0, 255, 65, 0.15);
        box-shadow: 0 0 20px rgba(0, 255, 65, 0.2);
    }

    .action-icon {
        font-size: 1.25rem;
    }

    .action-label {
        font-size: 0.95rem;
        font-weight: 500;
    }

    /* Error State */
    .error {
        text-align: center;
        padding: 4rem 2rem;
        color: #ff4444;
    }

    .error button {
        margin-top: 1rem;
        padding: 0.75rem 1.5rem;
        background: rgba(255, 68, 68, 0.2);
        border: 1px solid rgba(255, 68, 68, 0.5);
        border-radius: 6px;
        color: #ff4444;
        cursor: pointer;
    }

    .error button:hover {
        background: rgba(255, 68, 68, 0.3);
    }
</style>
