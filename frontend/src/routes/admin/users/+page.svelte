<script lang="ts">
    import { onMount } from 'svelte';
    import {
        adminStore,
        adminUsers,
        adminUsersLoading,
        adminUsersError,
        adminDepartments,
        selectedUser,
        selectedUserLoading,
        filteredUsers,
        type AdminUser,
    } from '$lib/stores/admin';
    import { isSuperUser } from '$lib/stores/auth';
    import UserRow from '$lib/components/admin/UserRow.svelte';
    import AccessModal from '$lib/components/admin/AccessModal.svelte';
    import RoleModal from '$lib/components/admin/RoleModal.svelte';
    import CreateUserModal from '$lib/components/admin/CreateUserModal.svelte';
    import BatchImportModal from '$lib/components/admin/BatchImportModal.svelte';

    // Local state
    let searchQuery = '';
    let departmentFilter = '';
    let showAccessModal = false;
    let showRoleModal = false;
    let showCreateModal = false;
    let showBatchModal = false;
    let showEditModal = false;
    let accessModalMode: 'grant' | 'revoke' = 'grant';
    let selectedUserId: string | null = null;
    let selectedDeptSlug: string | null = null;
    let editingUser: AdminUser | null = null;

    // Edit form state
    let editEmail = '';
    let editDisplayName = '';
    let editEmployeeId = '';
    let editPrimaryDepartment = '';
    let editLoading = false;
    let editError = '';

    // Debounced search
    let searchTimeout: ReturnType<typeof setTimeout>;

    function handleSearch(e: Event) {
        const value = (e.target as HTMLInputElement).value;
        searchQuery = value;

        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            adminStore.setSearchQuery(value);
        }, 300);
    }

    function handleDepartmentChange() {
        adminStore.setDepartmentFilter(departmentFilter || null);
        loadUsers();
    }

    function loadUsers() {
        adminStore.loadUsers(departmentFilter || undefined, searchQuery || undefined);
    }

    onMount(() => {
        adminStore.loadDepartments();
        loadUsers();
    });

    // Handle user row click
    function handleUserClick(userId: string) {
        if ($selectedUser?.id === userId) {
            adminStore.clearSelectedUser();
        } else {
            adminStore.loadUserDetail(userId);
        }
    }

    // Access modal handlers
    function openGrantModal(userId: string) {
        selectedUserId = userId;
        accessModalMode = 'grant';
        showAccessModal = true;
    }

    function openRevokeModal(userId: string, deptSlug: string) {
        selectedUserId = userId;
        selectedDeptSlug = deptSlug;
        accessModalMode = 'revoke';
        showAccessModal = true;
    }

    function closeAccessModal() {
        showAccessModal = false;
        selectedUserId = null;
        selectedDeptSlug = null;
    }

    async function handleAccessSubmit(e: CustomEvent<{
        departmentSlug: string;
        accessLevel?: string;
        makeDeptHead?: boolean;
        reason?: string;
    }>) {
        if (!selectedUserId) return;

        const { departmentSlug, accessLevel, makeDeptHead, reason } = e.detail;

        if (accessModalMode === 'grant') {
            await adminStore.grantAccess(
                selectedUserId,
                departmentSlug,
                accessLevel || 'read',
                makeDeptHead || false,
                reason
            );
        } else {
            await adminStore.revokeAccess(selectedUserId, departmentSlug, reason);
        }

        closeAccessModal();
        loadUsers();
    }

    // Role modal handlers
    function openRoleModal(userId: string) {
        selectedUserId = userId;
        showRoleModal = true;
    }

    function closeRoleModal() {
        showRoleModal = false;
        selectedUserId = null;
    }

    async function handleRoleSubmit(e: CustomEvent<{ newRole: string; reason?: string }>) {
        if (!selectedUserId) return;

        await adminStore.changeUserRole(selectedUserId, e.detail.newRole, e.detail.reason);
        closeRoleModal();
        loadUsers();
    }

    // Role badge colors
    function getRoleBadgeClass(role: string): string {
        switch (role) {
            case 'super_user': return 'badge-super';
            case 'dept_head': return 'badge-head';
            default: return 'badge-user';
        }
    }

    // Edit user handlers
    function openEditModal(user: AdminUser) {
        editingUser = user;
        editEmail = user.email;
        editDisplayName = user.display_name || '';
        editEmployeeId = user.employee_id || '';
        editPrimaryDepartment = user.primary_department || '';
        editError = '';
        showEditModal = true;
    }

    function closeEditModal() {
        showEditModal = false;
        editingUser = null;
        editError = '';
    }

    async function handleEditSubmit() {
        if (!editingUser) return;

        editLoading = true;
        editError = '';

        const result = await adminStore.updateUser(editingUser.id, {
            email: editEmail !== editingUser.email ? editEmail : undefined,
            display_name: editDisplayName,
            employee_id: editEmployeeId,
            primary_department: editPrimaryDepartment || undefined,
        });

        editLoading = false;

        if (result.success) {
            closeEditModal();
            loadUsers();
        } else {
            editError = result.error || 'Failed to update user';
        }
    }

    // Deactivate/Reactivate handlers
    async function handleDeactivate(user: AdminUser) {
        if (!confirm(`Deactivate user "${user.email}"? They will not be able to log in.`)) {
            return;
        }

        const result = await adminStore.deactivateUser(user.id, 'Admin deactivation');
        if (!result.success) {
            alert(result.error || 'Failed to deactivate user');
        }
    }

    async function handleReactivate(user: AdminUser) {
        if (!confirm(`Reactivate user "${user.email}"?`)) {
            return;
        }

        const result = await adminStore.reactivateUser(user.id, 'Admin reactivation');
        if (!result.success) {
            alert(result.error || 'Failed to reactivate user');
        }
    }
</script>

<svelte:head>
    <title>User Management - Admin Portal</title>
</svelte:head>

<div class="users-page">
    <header class="page-header">
        <div class="header-content">
            <h1>User Management</h1>
            <p class="subtitle">View and manage user access</p>
        </div>
        {#if $isSuperUser}
            <div class="header-actions">
                <button class="btn-secondary" on:click={() => showBatchModal = true}>
                    Batch Import
                </button>
                <button class="btn-primary" on:click={() => showCreateModal = true}>
                    + Add User
                </button>
            </div>
        {/if}
    </header>

    <!-- Filters -->
    <div class="filters">
        <div class="search-box">
            <span class="search-icon">&#128269;</span>
            <input
                type="text"
                placeholder="Search by email or name..."
                value={searchQuery}
                on:input={handleSearch}
            />
        </div>

        <div class="filter-group">
            <label for="dept-filter">Department:</label>
            <select
                id="dept-filter"
                bind:value={departmentFilter}
                on:change={handleDepartmentChange}
            >
                <option value="">All Departments</option>
                {#each $adminDepartments as dept}
                    <option value={dept.slug}>{dept.name}</option>
                {/each}
            </select>
        </div>

        <button class="refresh-btn" on:click={loadUsers}>
            &#8635; Refresh
        </button>
    </div>

    <!-- Users Table -->
    <div class="users-container">
        {#if $adminUsersLoading}
            <div class="loading">
                <div class="spinner"></div>
                <p>Loading users...</p>
            </div>
        {:else if $adminUsersError}
            <div class="error">
                <p>{$adminUsersError}</p>
                <button on:click={loadUsers}>Retry</button>
            </div>
        {:else if $filteredUsers.length === 0}
            <div class="empty">
                <p>No users found</p>
            </div>
        {:else}
            <div class="users-table">
                <div class="table-header">
                    <div class="col-email">Email</div>
                    <div class="col-name">Name</div>
                    <div class="col-role">Role</div>
                    <div class="col-dept">Department</div>
                    <div class="col-actions">Actions</div>
                </div>

                {#each $filteredUsers as user (user.id)}
                    <UserRow
                        {user}
                        expanded={$selectedUser?.id === user.id}
                        loading={$selectedUserLoading && selectedUserId === user.id}
                        selectedUserDetail={$selectedUser}
                        on:click={() => handleUserClick(user.id)}
                        on:grant={() => openGrantModal(user.id)}
                        on:revoke={(e) => openRevokeModal(user.id, e.detail)}
                        on:changeRole={() => openRoleModal(user.id)}
                        isSuperUser={$isSuperUser}
                        onEdit={openEditModal}
                        onDeactivate={handleDeactivate}
                        onReactivate={handleReactivate}
                    />
                {/each}
            </div>

            <div class="table-footer">
                <span class="count">Showing {$filteredUsers.length} users</span>
            </div>
        {/if}
    </div>
</div>

<!-- Modals -->
{#if showAccessModal}
    <AccessModal
        mode={accessModalMode}
        departments={$adminDepartments}
        preselectedDepartment={selectedDeptSlug}
        on:submit={handleAccessSubmit}
        on:close={closeAccessModal}
    />
{/if}

{#if showRoleModal && selectedUserId}
    <RoleModal
        currentRole={$adminUsers.find(u => u.id === selectedUserId)?.role || 'user'}
        on:submit={handleRoleSubmit}
        on:close={closeRoleModal}
    />
{/if}

<CreateUserModal
    bind:open={showCreateModal}
    on:created={() => loadUsers()}
/>

<BatchImportModal
    bind:open={showBatchModal}
    on:imported={() => loadUsers()}
/>

<!-- Edit User Modal -->
{#if showEditModal && editingUser}
<div class="modal-backdrop" on:click={closeEditModal} on:keypress={() => {}}>
    <div class="modal-content" on:click|stopPropagation on:keypress|stopPropagation>
        <div class="modal-header">
            <h2>Edit User</h2>
            <button class="close-btn" on:click={closeEditModal}>&times;</button>
        </div>

        <form on:submit|preventDefault={handleEditSubmit}>
            <div class="form-group">
                <label for="editEmail">Email</label>
                <input
                    type="email"
                    id="editEmail"
                    bind:value={editEmail}
                    required
                />
            </div>

            <div class="form-group">
                <label for="editDisplayName">Display Name</label>
                <input
                    type="text"
                    id="editDisplayName"
                    bind:value={editDisplayName}
                    placeholder="John Doe"
                />
            </div>

            <div class="form-group">
                <label for="editEmployeeId">Employee ID</label>
                <input
                    type="text"
                    id="editEmployeeId"
                    bind:value={editEmployeeId}
                    placeholder="EMP-12345"
                />
            </div>

            <div class="form-group">
                <label for="editPrimaryDepartment">Primary Department</label>
                <select id="editPrimaryDepartment" bind:value={editPrimaryDepartment}>
                    <option value="">-- Select --</option>
                    {#each $adminDepartments as dept}
                        <option value={dept.slug}>{dept.name}</option>
                    {/each}
                </select>
            </div>

            {#if editError}
                <div class="error-message">{editError}</div>
            {/if}

            <div class="modal-actions">
                <button type="button" class="btn-secondary" on:click={closeEditModal}>
                    Cancel
                </button>
                <button type="submit" class="btn-primary" disabled={editLoading}>
                    {editLoading ? 'Saving...' : 'Save Changes'}
                </button>
            </div>
        </form>
    </div>
</div>
{/if}

<style>
    .users-page {
        max-width: 1400px;
        margin: 0 auto;
    }

    .page-header {
        margin-bottom: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        flex-wrap: wrap;
        gap: 1rem;
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

    .header-actions {
        display: flex;
        gap: 0.75rem;
    }

    .btn-primary {
        padding: 0.75rem 1.25rem;
        background: #00ff41;
        border: none;
        border-radius: 8px;
        color: #000;
        font-size: 0.95rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }

    .btn-primary:hover {
        background: #00cc33;
    }

    .btn-primary:disabled {
        background: #004d00;
        cursor: not-allowed;
    }

    .btn-secondary {
        padding: 0.75rem 1.25rem;
        background: transparent;
        border: 1px solid rgba(0, 255, 65, 0.3);
        border-radius: 8px;
        color: #00ff41;
        font-size: 0.95rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .btn-secondary:hover {
        background: rgba(0, 255, 65, 0.1);
    }

    /* Filters */
    .filters {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
        flex-wrap: wrap;
        align-items: center;
    }

    .search-box {
        flex: 1;
        min-width: 250px;
        position: relative;
    }

    .search-icon {
        position: absolute;
        left: 1rem;
        top: 50%;
        transform: translateY(-50%);
        color: #555;
    }

    .search-box input {
        width: 100%;
        padding: 0.75rem 1rem 0.75rem 2.5rem;
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(0, 255, 65, 0.2);
        border-radius: 8px;
        color: #e0e0e0;
        font-size: 0.95rem;
    }

    .search-box input:focus {
        outline: none;
        border-color: #00ff41;
    }

    .search-box input::placeholder {
        color: #555;
    }

    .filter-group {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .filter-group label {
        color: #888;
        font-size: 0.9rem;
    }

    .filter-group select {
        padding: 0.75rem 1rem;
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(0, 255, 65, 0.2);
        border-radius: 8px;
        color: #e0e0e0;
        font-size: 0.95rem;
        cursor: pointer;
    }

    .filter-group select:focus {
        outline: none;
        border-color: #00ff41;
    }

    .refresh-btn {
        padding: 0.75rem 1.25rem;
        background: rgba(0, 255, 65, 0.1);
        border: 1px solid rgba(0, 255, 65, 0.3);
        border-radius: 8px;
        color: #00ff41;
        font-size: 0.95rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .refresh-btn:hover {
        background: rgba(0, 255, 65, 0.2);
    }

    /* Users Container */
    .users-container {
        background: rgba(20, 20, 20, 0.8);
        border: 1px solid rgba(0, 255, 65, 0.15);
        border-radius: 12px;
        overflow: hidden;
    }

    .loading, .error, .empty {
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

    .error {
        color: #ff4444;
    }

    .error button {
        margin-top: 1rem;
        padding: 0.5rem 1rem;
        background: rgba(255, 68, 68, 0.2);
        border: 1px solid rgba(255, 68, 68, 0.5);
        border-radius: 6px;
        color: #ff4444;
        cursor: pointer;
    }

    /* Table */
    .users-table {
        width: 100%;
    }

    .table-header {
        display: grid;
        grid-template-columns: 2fr 1.5fr 1fr 1.5fr 1fr;
        gap: 1rem;
        padding: 1rem 1.5rem;
        background: rgba(0, 0, 0, 0.3);
        border-bottom: 1px solid rgba(0, 255, 65, 0.1);
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #666;
    }

    .table-footer {
        padding: 1rem 1.5rem;
        border-top: 1px solid rgba(0, 255, 65, 0.1);
    }

    .count {
        font-size: 0.85rem;
        color: #666;
    }

    /* Responsive */
    @media (max-width: 1024px) {
        .table-header {
            display: none;
        }
    }

    @media (max-width: 768px) {
        .filters {
            flex-direction: column;
        }

        .search-box {
            width: 100%;
        }

        .filter-group {
            width: 100%;
        }

        .filter-group select {
            flex: 1;
        }
    }

    /* Modal Styles */
    .modal-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    }

    .modal-content {
        background: #1a1a1a;
        border: 1px solid #00ff41;
        border-radius: 8px;
        padding: 24px;
        width: 100%;
        max-width: 500px;
        max-height: 90vh;
        overflow-y: auto;
    }

    .modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }

    .modal-header h2 {
        color: #00ff41;
        margin: 0;
        font-size: 1.25rem;
    }

    .close-btn {
        background: none;
        border: none;
        color: #666;
        font-size: 1.5rem;
        cursor: pointer;
    }

    .close-btn:hover {
        color: #ff4444;
    }

    .form-group {
        margin-bottom: 16px;
    }

    .form-group label {
        display: block;
        color: #888;
        margin-bottom: 4px;
        font-size: 0.875rem;
    }

    .form-group input,
    .form-group select {
        width: 100%;
        padding: 8px 12px;
        background: #0a0a0a;
        border: 1px solid #333;
        border-radius: 4px;
        color: #fff;
        font-size: 0.875rem;
    }

    .form-group input:focus,
    .form-group select:focus {
        outline: none;
        border-color: #00ff41;
    }

    .error-message {
        color: #ff4444;
        font-size: 0.875rem;
        margin-bottom: 16px;
        padding: 8px;
        background: rgba(255, 68, 68, 0.1);
        border-radius: 4px;
    }

    .modal-actions {
        display: flex;
        justify-content: flex-end;
        gap: 12px;
        margin-top: 20px;
    }
</style>
