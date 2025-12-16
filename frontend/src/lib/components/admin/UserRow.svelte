<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    import type { AdminUser, UserDetail } from '$lib/stores/admin';

    export let user: AdminUser;
    export let expanded = false;
    export let loading = false;
    export let selectedUserDetail: UserDetail | null = null;
    export let isSuperUser = false;

    const dispatch = createEventDispatcher();

    // Role badge styling
    function getRoleBadgeClass(role: string): string {
        switch (role) {
            case 'super_user': return 'badge-super';
            case 'dept_head': return 'badge-head';
            default: return 'badge-user';
        }
    }

    function getRoleLabel(role: string): string {
        switch (role) {
            case 'super_user': return 'Super User';
            case 'dept_head': return 'Dept Head';
            default: return 'User';
        }
    }

    function handleClick() {
        dispatch('click');
    }

    function handleGrant(e: Event) {
        e.stopPropagation();
        dispatch('grant');
    }

    function handleRevoke(e: Event, deptSlug: string) {
        e.stopPropagation();
        dispatch('revoke', deptSlug);
    }

    function handleChangeRole(e: Event) {
        e.stopPropagation();
        dispatch('changeRole');
    }
</script>

<div class="user-row" class:expanded on:click={handleClick}>
    <!-- Main Row -->
    <div class="row-content">
        <div class="col-email">
            <span class="email">{user.email}</span>
            {#if !user.active}
                <span class="inactive-badge">Inactive</span>
            {/if}
        </div>

        <div class="col-name">
            <span class="name">{user.display_name || '-'}</span>
            {#if user.employee_id}
                <span class="employee-id">({user.employee_id})</span>
            {/if}
        </div>

        <div class="col-role">
            <span class="role-badge {getRoleBadgeClass(user.role)}">
                {getRoleLabel(user.role)}
            </span>
        </div>

        <div class="col-dept">
            <span class="dept">{user.primary_department || '-'}</span>
        </div>

        <div class="col-actions">
            <button
                class="action-btn expand-btn"
                title={expanded ? 'Collapse' : 'Expand'}
            >
                {expanded ? '▼' : '▶'}
            </button>
        </div>
    </div>

    <!-- Expanded Detail -->
    {#if expanded}
        <div class="detail-panel">
            {#if loading}
                <div class="detail-loading">
                    <div class="spinner"></div>
                    Loading details...
                </div>
            {:else if selectedUserDetail}
                <div class="detail-content">
                    <!-- User Info -->
                    <div class="detail-section">
                        <h4>User Information</h4>
                        <div class="info-grid">
                            <div class="info-item">
                                <span class="info-label">Email</span>
                                <span class="info-value">{selectedUserDetail.email}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Display Name</span>
                                <span class="info-value">{selectedUserDetail.display_name || '-'}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Employee ID</span>
                                <span class="info-value">{selectedUserDetail.employee_id || '-'}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Role</span>
                                <span class="info-value">
                                    <span class="role-badge {getRoleBadgeClass(selectedUserDetail.role)}">
                                        {getRoleLabel(selectedUserDetail.role)}
                                    </span>
                                    {#if isSuperUser && selectedUserDetail.role !== 'super_user'}
                                        <button class="inline-action" on:click={handleChangeRole}>
                                            Change
                                        </button>
                                    {/if}
                                </span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Permission Tier</span>
                                <span class="info-value">{selectedUserDetail.tier}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Department Access -->
                    <div class="detail-section">
                        <div class="section-header">
                            <h4>Department Access</h4>
                            <button class="grant-btn" on:click={handleGrant}>
                                + Grant Access
                            </button>
                        </div>

                        {#if selectedUserDetail.departments.length > 0}
                            <div class="dept-list">
                                {#each selectedUserDetail.departments as dept}
                                    <div class="dept-item">
                                        <div class="dept-info">
                                            <span class="dept-name">{dept.name}</span>
                                            <span class="dept-meta">
                                                {dept.access_level}
                                                {#if dept.is_dept_head}
                                                    <span class="head-badge">HEAD</span>
                                                {/if}
                                            </span>
                                        </div>
                                        <button
                                            class="revoke-btn"
                                            on:click={(e) => handleRevoke(e, dept.slug)}
                                        >
                                            Revoke
                                        </button>
                                    </div>
                                {/each}
                            </div>
                        {:else}
                            <p class="no-access">No department access granted</p>
                        {/if}
                    </div>
                </div>
            {:else}
                <div class="detail-error">
                    Failed to load user details
                </div>
            {/if}
        </div>
    {/if}
</div>

<style>
    .user-row {
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        cursor: pointer;
        transition: background 0.2s;
    }

    .user-row:hover {
        background: rgba(0, 255, 65, 0.03);
    }

    .user-row.expanded {
        background: rgba(0, 255, 65, 0.05);
    }

    .row-content {
        display: grid;
        grid-template-columns: 2fr 1.5fr 1fr 1.5fr 1fr;
        gap: 1rem;
        padding: 1rem 1.5rem;
        align-items: center;
    }

    .email {
        font-size: 0.95rem;
        color: #e0e0e0;
    }

    .inactive-badge {
        margin-left: 0.5rem;
        padding: 0.125rem 0.5rem;
        background: rgba(255, 68, 68, 0.2);
        border-radius: 4px;
        font-size: 0.7rem;
        color: #ff4444;
    }

    .name {
        font-size: 0.9rem;
        color: #888;
    }

    .employee-id {
        font-size: 0.8rem;
        color: #555;
        margin-left: 0.25rem;
    }

    .dept {
        font-size: 0.9rem;
        color: #888;
        text-transform: capitalize;
    }

    /* Role Badges */
    .role-badge {
        display: inline-block;
        padding: 0.25rem 0.625rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
    }

    .badge-super {
        background: rgba(0, 255, 65, 0.15);
        color: #00ff41;
        border: 1px solid rgba(0, 255, 65, 0.3);
    }

    .badge-head {
        background: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }

    .badge-user {
        background: rgba(59, 130, 246, 0.15);
        color: #3b82f6;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }

    /* Action Buttons */
    .action-btn {
        background: none;
        border: none;
        color: #666;
        cursor: pointer;
        padding: 0.25rem 0.5rem;
        transition: color 0.2s;
    }

    .action-btn:hover {
        color: #00ff41;
    }

    /* Detail Panel */
    .detail-panel {
        background: rgba(0, 0, 0, 0.3);
        border-top: 1px solid rgba(0, 255, 65, 0.1);
        padding: 1.5rem;
    }

    .detail-loading {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        color: #888;
        font-size: 0.9rem;
    }

    .detail-loading .spinner {
        width: 20px;
        height: 20px;
        border: 2px solid rgba(255, 255, 255, 0.1);
        border-top-color: #00ff88;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    .detail-content {
        display: grid;
        gap: 1.5rem;
    }

    .detail-section {
        background: rgba(20, 20, 20, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 1rem 1.25rem;
    }

    .detail-section h4 {
        font-size: 0.85rem;
        font-weight: 600;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 0 0 1rem 0;
    }

    .section-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }

    .section-header h4 {
        margin: 0;
    }

    .info-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 1rem;
    }

    .info-item {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .info-label {
        font-size: 0.75rem;
        color: #555;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .info-value {
        font-size: 0.9rem;
        color: #e0e0e0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .inline-action {
        background: none;
        border: none;
        color: #00ff41;
        font-size: 0.8rem;
        cursor: pointer;
        padding: 0;
        text-decoration: underline;
    }

    .inline-action:hover {
        text-decoration: none;
    }

    /* Department Access List */
    .dept-list {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .dept-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem;
        background: rgba(0, 0, 0, 0.3);
        border-radius: 6px;
    }

    .dept-info {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .dept-name {
        font-size: 0.9rem;
        color: #e0e0e0;
        text-transform: capitalize;
    }

    .dept-meta {
        font-size: 0.8rem;
        color: #666;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .head-badge {
        padding: 0.125rem 0.375rem;
        background: rgba(245, 158, 11, 0.2);
        border-radius: 3px;
        font-size: 0.65rem;
        color: #f59e0b;
    }

    .grant-btn {
        padding: 0.375rem 0.75rem;
        background: rgba(0, 255, 65, 0.1);
        border: 1px solid rgba(0, 255, 65, 0.3);
        border-radius: 4px;
        color: #00ff41;
        font-size: 0.8rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .grant-btn:hover {
        background: rgba(0, 255, 65, 0.2);
    }

    .revoke-btn {
        padding: 0.25rem 0.5rem;
        background: rgba(255, 68, 68, 0.1);
        border: 1px solid rgba(255, 68, 68, 0.3);
        border-radius: 4px;
        color: #ff4444;
        font-size: 0.75rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .revoke-btn:hover {
        background: rgba(255, 68, 68, 0.2);
    }

    .no-access {
        color: #555;
        font-size: 0.9rem;
        font-style: italic;
        margin: 0;
    }

    .detail-error {
        color: #ff4444;
        font-size: 0.9rem;
    }

    /* Responsive */
    @media (max-width: 1024px) {
        .row-content {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }

        .col-email {
            flex: 1 1 100%;
        }

        .col-name, .col-role, .col-dept {
            flex: 1;
        }

        .col-actions {
            position: absolute;
            right: 1rem;
            top: 1rem;
        }
    }
</style>
