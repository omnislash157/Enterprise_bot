<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    import { adminStore, adminDepartments } from '$lib/stores/admin';

    export let open = false;

    const dispatch = createEventDispatcher();

    let email = '';
    let displayName = '';
    let employeeId = '';
    let role = 'user';
    let primaryDepartment = '';
    let selectedDepartments: string[] = [];
    let reason = '';

    let loading = false;
    let error = '';

    // Load departments when modal opens
    $: if (open && $adminDepartments.length === 0) {
        adminStore.loadDepartments();
    }

    function reset() {
        email = '';
        displayName = '';
        employeeId = '';
        role = 'user';
        primaryDepartment = '';
        selectedDepartments = [];
        reason = '';
        error = '';
    }

    function close() {
        reset();
        open = false;
        dispatch('close');
    }

    async function submit() {
        if (!email.trim()) {
            error = 'Email is required';
            return;
        }

        loading = true;
        error = '';

        const result = await adminStore.createUser({
            email: email.trim(),
            display_name: displayName.trim() || undefined,
            employee_id: employeeId.trim() || undefined,
            role,
            primary_department: primaryDepartment || undefined,
            department_access: selectedDepartments.length > 0 ? selectedDepartments : undefined,
            reason: reason.trim() || undefined,
        });

        loading = false;

        if (result.success) {
            dispatch('created', result.data);
            close();
        } else {
            error = result.error || 'Failed to create user';
        }
    }

    function toggleDepartment(slug: string) {
        if (selectedDepartments.includes(slug)) {
            selectedDepartments = selectedDepartments.filter(s => s !== slug);
        } else {
            selectedDepartments = [...selectedDepartments, slug];
        }
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === 'Escape') {
            close();
        }
    }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
<div class="modal-backdrop" on:click={close} on:keypress={() => {}}>
    <div class="modal-content" on:click|stopPropagation on:keypress|stopPropagation>
        <div class="modal-header">
            <h2>Create New User</h2>
            <button class="close-btn" on:click={close}>&times;</button>
        </div>

        <form on:submit|preventDefault={submit}>
            <div class="form-group">
                <label for="email">Email *</label>
                <input
                    type="email"
                    id="email"
                    bind:value={email}
                    placeholder="user@driscollfoods.com"
                    required
                />
            </div>

            <div class="form-group">
                <label for="displayName">Display Name</label>
                <input
                    type="text"
                    id="displayName"
                    bind:value={displayName}
                    placeholder="John Doe"
                />
            </div>

            <div class="form-group">
                <label for="employeeId">Employee ID</label>
                <input
                    type="text"
                    id="employeeId"
                    bind:value={employeeId}
                    placeholder="EMP-12345"
                />
            </div>

            <div class="form-group">
                <label for="role">Role</label>
                <select id="role" bind:value={role}>
                    <option value="user">User</option>
                    <option value="dept_head">Department Head</option>
                    <option value="super_user">Super User</option>
                </select>
            </div>

            <div class="form-group">
                <label for="primaryDepartment">Primary Department</label>
                <select id="primaryDepartment" bind:value={primaryDepartment}>
                    <option value="">-- Select --</option>
                    {#each $adminDepartments as dept}
                        <option value={dept.slug}>{dept.name}</option>
                    {/each}
                </select>
            </div>

            <div class="form-group">
                <label>Additional Department Access</label>
                <div class="checkbox-group">
                    {#each $adminDepartments as dept}
                        <label class="checkbox-label">
                            <input
                                type="checkbox"
                                checked={selectedDepartments.includes(dept.slug)}
                                on:change={() => toggleDepartment(dept.slug)}
                            />
                            {dept.name}
                        </label>
                    {/each}
                </div>
            </div>

            <div class="form-group">
                <label for="reason">Reason (optional)</label>
                <input
                    type="text"
                    id="reason"
                    bind:value={reason}
                    placeholder="New hire, department transfer, etc."
                />
            </div>

            {#if error}
                <div class="error-message">{error}</div>
            {/if}

            <div class="modal-actions">
                <button type="button" class="btn-secondary" on:click={close}>
                    Cancel
                </button>
                <button type="submit" class="btn-primary" disabled={loading}>
                    {loading ? 'Creating...' : 'Create User'}
                </button>
            </div>
        </form>
    </div>
</div>
{/if}

<style>
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

    .checkbox-group {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }

    .checkbox-label {
        display: flex;
        align-items: center;
        gap: 4px;
        color: #ccc;
        font-size: 0.875rem;
        cursor: pointer;
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

    .btn-primary {
        background: #00ff41;
        color: #000;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
        font-weight: 600;
    }

    .btn-primary:hover {
        background: #00cc33;
    }

    .btn-primary:disabled {
        background: #004d00;
        cursor: not-allowed;
    }

    .btn-secondary {
        background: transparent;
        color: #888;
        border: 1px solid #444;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
    }

    .btn-secondary:hover {
        border-color: #666;
        color: #ccc;
    }
</style>
