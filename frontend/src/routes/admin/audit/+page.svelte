<script lang="ts">
    import { onMount } from 'svelte';
    import {
        adminStore,
        auditEntries,
        auditTotal,
        auditLoading,
        adminDepartments,
    } from '$lib/stores/admin';

    // Filters
    let actionFilter = '';
    let targetEmailFilter = '';
    let departmentFilter = '';
    let currentOffset = 0;
    const limit = 50;

    // Action types for filter dropdown
    const actionTypes = [
        { value: '', label: 'All Actions' },
        { value: 'grant', label: 'Access Granted' },
        { value: 'revoke', label: 'Access Revoked' },
        { value: 'role_change', label: 'Role Changed' },
        { value: 'login', label: 'Login' },
        { value: 'user_created', label: 'User Created' },
    ];

    // Action labels and colors
    const actionLabels: Record<string, { label: string; color: string }> = {
        grant: { label: 'Access Granted', color: '#00ff41' },
        revoke: { label: 'Access Revoked', color: '#ff4444' },
        role_change: { label: 'Role Changed', color: '#f59e0b' },
        login: { label: 'Login', color: '#3b82f6' },
        user_created: { label: 'User Created', color: '#8b5cf6' },
    };

    function loadAuditLog() {
        adminStore.loadAuditLog({
            action: actionFilter || undefined,
            targetEmail: targetEmailFilter || undefined,
            department: departmentFilter || undefined,
            limit,
            offset: currentOffset,
        });
    }

    function applyFilters() {
        currentOffset = 0;
        loadAuditLog();
    }

    function clearFilters() {
        actionFilter = '';
        targetEmailFilter = '';
        departmentFilter = '';
        currentOffset = 0;
        loadAuditLog();
    }

    function nextPage() {
        if (currentOffset + limit < $auditTotal) {
            currentOffset += limit;
            loadAuditLog();
        }
    }

    function prevPage() {
        if (currentOffset > 0) {
            currentOffset = Math.max(0, currentOffset - limit);
            loadAuditLog();
        }
    }

    function formatDate(dateStr: string): string {
        const date = new Date(dateStr);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    }

    function getActionInfo(action: string) {
        return actionLabels[action] || { label: action, color: '#666' };
    }

    onMount(() => {
        adminStore.loadDepartments();
        loadAuditLog();
    });
</script>

<svelte:head>
    <title>Audit Log - Admin Portal</title>
</svelte:head>

<div class="audit-page">
    <header class="page-header">
        <h1>Audit Log</h1>
        <p class="subtitle">Track all access changes and admin actions</p>
    </header>

    <div class="filters">
        <div class="filter-group">
            <label for="action-filter">Action:</label>
            <select id="action-filter" bind:value={actionFilter}>
                {#each actionTypes as type}
                    <option value={type.value}>{type.label}</option>
                {/each}
            </select>
        </div>

        <div class="filter-group">
            <label for="email-filter">Target Email:</label>
            <input
                type="text"
                id="email-filter"
                placeholder="Search email..."
                bind:value={targetEmailFilter}
            />
        </div>

        <div class="filter-group">
            <label for="dept-filter">Department:</label>
            <select id="dept-filter" bind:value={departmentFilter}>
                <option value="">All Departments</option>
                {#each $adminDepartments as dept}
                    <option value={dept.slug}>{dept.name}</option>
                {/each}
            </select>
        </div>

        <div class="filter-actions">
            <button class="apply-btn" on:click={applyFilters}>Apply Filters</button>
            <button class="clear-btn" on:click={clearFilters}>Clear</button>
        </div>
    </div>

    <div class="audit-container">
        {#if $auditLoading}
            <div class="loading">
                <div class="spinner"></div>
                <p>Loading audit log...</p>
            </div>
        {:else if $auditEntries.length === 0}
            <div class="empty">
                <p>No audit entries found</p>
            </div>
        {:else}
            <div class="audit-table">
                <div class="table-header">
                    <div class="col-time">Timestamp</div>
                    <div class="col-action">Action</div>
                    <div class="col-actor">Actor</div>
                    <div class="col-target">Target</div>
                    <div class="col-dept">Department</div>
                    <div class="col-details">Details</div>
                </div>

                {#each $auditEntries as entry (entry.id)}
                    <div class="table-row">
                        <div class="col-time">
                            <span class="time-value">{formatDate(entry.created_at)}</span>
                        </div>

                        <div class="col-action">
                            <span
                                class="action-badge"
                                style="--action-color: {getActionInfo(entry.action).color}"
                            >
                                {getActionInfo(entry.action).label}
                            </span>
                        </div>

                        <div class="col-actor">
                            <span class="email-text">{entry.actor_email || 'System'}</span>
                        </div>

                        <div class="col-target">
                            <span class="email-text">{entry.target_email || '-'}</span>
                        </div>

                        <div class="col-dept">
                            <span class="dept-text">{entry.department_slug || '-'}</span>
                        </div>

                        <div class="col-details">
                            {#if entry.old_value || entry.new_value}
                                <div class="change-detail">
                                    {#if entry.old_value}
                                        <span class="old-value">{entry.old_value}</span>
                                        <span class="arrow">-></span>
                                    {/if}
                                    {#if entry.new_value}
                                        <span class="new-value">{entry.new_value}</span>
                                    {/if}
                                </div>
                            {/if}
                            {#if entry.reason}
                                <div class="reason">
                                    <span class="reason-label">Reason:</span>
                                    {entry.reason}
                                </div>
                            {/if}
                        </div>
                    </div>
                {/each}
            </div>

            <div class="pagination">
                <span class="page-info">
                    Showing {currentOffset + 1} - {Math.min(currentOffset + limit, $auditTotal)} of {$auditTotal}
                </span>
                <div class="page-controls">
                    <button
                        class="page-btn"
                        disabled={currentOffset === 0}
                        on:click={prevPage}
                    >
                        Previous
                    </button>
                    <button
                        class="page-btn"
                        disabled={currentOffset + limit >= $auditTotal}
                        on:click={nextPage}
                    >
                        Next
                    </button>
                </div>
            </div>
        {/if}
    </div>
</div>

<style>
    .audit-page {
        max-width: 1400px;
        margin: 0 auto;
    }

    .page-header {
        margin-bottom: 1.5rem;
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

    .filters {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
        flex-wrap: wrap;
        align-items: flex-end;
        background: rgba(20, 20, 20, 0.8);
        border: 1px solid rgba(0, 255, 65, 0.15);
        border-radius: 12px;
        padding: 1.25rem;
    }

    .filter-group {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .filter-group label {
        font-size: 0.8rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .filter-group select,
    .filter-group input {
        padding: 0.625rem 0.875rem;
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(0, 255, 65, 0.2);
        border-radius: 6px;
        color: #e0e0e0;
        font-size: 0.9rem;
        min-width: 160px;
    }

    .filter-group select:focus,
    .filter-group input:focus {
        outline: none;
        border-color: #00ff41;
    }

    .filter-group input::placeholder {
        color: #555;
    }

    .filter-actions {
        display: flex;
        gap: 0.5rem;
        margin-left: auto;
    }

    .apply-btn {
        padding: 0.625rem 1rem;
        background: #00ff41;
        border: none;
        border-radius: 6px;
        color: #000;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
    }

    .apply-btn:hover {
        box-shadow: 0 0 15px rgba(0, 255, 65, 0.4);
    }

    .clear-btn {
        padding: 0.625rem 1rem;
        background: transparent;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        color: #888;
        cursor: pointer;
        transition: all 0.2s;
    }

    .clear-btn:hover {
        border-color: rgba(255, 255, 255, 0.4);
        color: #e0e0e0;
    }

    .audit-container {
        background: rgba(20, 20, 20, 0.8);
        border: 1px solid rgba(0, 255, 65, 0.15);
        border-radius: 12px;
        overflow: hidden;
    }

    .loading, .empty {
        padding: 4rem 2rem;
        text-align: center;
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

    .audit-table {
        width: 100%;
    }

    .table-header {
        display: grid;
        grid-template-columns: 160px 140px 1fr 1fr 100px 1.5fr;
        gap: 1rem;
        padding: 1rem 1.5rem;
        background: rgba(0, 0, 0, 0.3);
        border-bottom: 1px solid rgba(0, 255, 65, 0.1);
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #666;
    }

    .table-row {
        display: grid;
        grid-template-columns: 160px 140px 1fr 1fr 100px 1.5fr;
        gap: 1rem;
        padding: 1rem 1.5rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        align-items: start;
    }

    .table-row:hover {
        background: rgba(0, 255, 65, 0.03);
    }

    .time-value {
        font-size: 0.85rem;
        color: #888;
        font-family: 'SF Mono', monospace;
    }

    .action-badge {
        display: inline-block;
        padding: 0.25rem 0.625rem;
        background: color-mix(in srgb, var(--action-color) 15%, transparent);
        border: 1px solid var(--action-color);
        border-radius: 4px;
        font-size: 0.75rem;
        color: var(--action-color);
        white-space: nowrap;
    }

    .email-text {
        font-size: 0.85rem;
        color: #e0e0e0;
        word-break: break-all;
    }

    .dept-text {
        font-size: 0.85rem;
        color: #888;
        text-transform: capitalize;
    }

    .change-detail {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.85rem;
        flex-wrap: wrap;
    }

    .old-value {
        color: #ff6b6b;
        text-decoration: line-through;
        opacity: 0.7;
    }

    .arrow {
        color: #666;
    }

    .new-value {
        color: #00ff41;
    }

    .reason {
        margin-top: 0.5rem;
        font-size: 0.8rem;
        color: #666;
        font-style: italic;
    }

    .reason-label {
        color: #555;
    }

    .pagination {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 1.5rem;
        border-top: 1px solid rgba(0, 255, 65, 0.1);
    }

    .page-info {
        font-size: 0.85rem;
        color: #666;
    }

    .page-controls {
        display: flex;
        gap: 0.5rem;
    }

    .page-btn {
        padding: 0.5rem 1rem;
        background: rgba(0, 255, 65, 0.1);
        border: 1px solid rgba(0, 255, 65, 0.3);
        border-radius: 6px;
        color: #00ff41;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .page-btn:hover:not(:disabled) {
        background: rgba(0, 255, 65, 0.2);
    }

    .page-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }

    @media (max-width: 1200px) {
        .table-header,
        .table-row {
            grid-template-columns: 140px 120px 1fr 1fr 1fr;
        }

        .col-details {
            grid-column: 1 / -1;
            margin-top: 0.5rem;
            padding-top: 0.5rem;
            border-top: 1px dashed rgba(255, 255, 255, 0.1);
        }
    }

    @media (max-width: 768px) {
        .filters {
            flex-direction: column;
            align-items: stretch;
        }

        .filter-group {
            width: 100%;
        }

        .filter-group select,
        .filter-group input {
            width: 100%;
        }

        .filter-actions {
            margin-left: 0;
            width: 100%;
        }

        .filter-actions button {
            flex: 1;
        }

        .table-header {
            display: none;
        }

        .table-row {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            padding: 1rem;
        }

        .pagination {
            flex-direction: column;
            gap: 1rem;
        }
    }
</style>