<script lang="ts">
    import { createEventDispatcher } from 'svelte';

    export let currentRole: string = 'user';

    const dispatch = createEventDispatcher();

    // Form state
    let newRole = currentRole;
    let reason = '';
    let submitting = false;

    // Role options
    const roles = [
        {
            value: 'user',
            label: 'User',
            description: 'Standard user access. Can only view their own data.',
            color: '#3b82f6',
        },
        {
            value: 'dept_head',
            label: 'Department Head',
            description: 'Can view all department data and manage users in their department.',
            color: '#f59e0b',
        },
        {
            value: 'super_user',
            label: 'Super User',
            description: 'Full admin access. Can view all data and manage all users.',
            color: '#00ff41',
        },
    ];

    function getRoleInfo(role: string) {
        return roles.find(r => r.value === role) || roles[0];
    }

    async function handleSubmit() {
        if (newRole === currentRole) {
            handleClose();
            return;
        }

        submitting = true;

        dispatch('submit', {
            newRole,
            reason: reason || undefined,
        });
    }

    function handleClose() {
        dispatch('close');
    }

    function handleBackdropClick(e: MouseEvent) {
        if (e.target === e.currentTarget) {
            handleClose();
        }
    }

    $: isEscalation = roles.findIndex(r => r.value === newRole) > roles.findIndex(r => r.value === currentRole);
    $: isDemotion = roles.findIndex(r => r.value === newRole) < roles.findIndex(r => r.value === currentRole);
</script>

<div class="modal-backdrop" on:click={handleBackdropClick}>
    <div class="modal">
        <header class="modal-header">
            <h2>Change User Role</h2>
            <button class="close-btn" on:click={handleClose}>x</button>
        </header>

        <form on:submit|preventDefault={handleSubmit}>
            <div class="modal-body">
                <!-- Current Role -->
                <div class="current-role">
                    <span class="label">Current Role:</span>
                    <span
                        class="role-badge"
                        style="--role-color: {getRoleInfo(currentRole).color}"
                    >
                        {getRoleInfo(currentRole).label}
                    </span>
                </div>

                <!-- New Role Selection -->
                <div class="form-group">
                    <label>New Role</label>
                    <div class="role-options">
                        {#each roles as role}
                            <label
                                class="role-option"
                                class:selected={newRole === role.value}
                                class:current={currentRole === role.value}
                            >
                                <input
                                    type="radio"
                                    name="newRole"
                                    value={role.value}
                                    bind:group={newRole}
                                />
                                <span class="role-content" style="--role-color: {role.color}">
                                    <span class="role-header">
                                        <span class="role-title">{role.label}</span>
                                        {#if currentRole === role.value}
                                            <span class="current-badge">Current</span>
                                        {/if}
                                    </span>
                                    <span class="role-desc">{role.description}</span>
                                </span>
                            </label>
                        {/each}
                    </div>
                </div>

                <!-- Escalation Warning -->
                {#if isEscalation}
                    <div class="warning escalation">
                        <span class="warning-icon">!</span>
                        <div class="warning-content">
                            <strong>Privilege Escalation</strong>
                            <p>This will grant the user additional permissions. Make sure this is intentional and authorized.</p>
                        </div>
                    </div>
                {/if}

                <!-- Demotion Warning -->
                {#if isDemotion}
                    <div class="warning demotion">
                        <span class="warning-icon">!</span>
                        <div class="warning-content">
                            <strong>Role Demotion</strong>
                            <p>This will remove permissions from the user. They may lose access to data and features they currently use.</p>
                        </div>
                    </div>
                {/if}

                <!-- Reason -->
                <div class="form-group">
                    <label for="reason">Reason {#if isEscalation || isDemotion}(required){:else}(optional){/if}</label>
                    <textarea
                        id="reason"
                        bind:value={reason}
                        placeholder="Explain why this role change is being made..."
                        rows="3"
                        required={isEscalation || isDemotion}
                    ></textarea>
                    <span class="hint">This will be recorded in the audit log</span>
                </div>
            </div>

            <footer class="modal-footer">
                <button type="button" class="cancel-btn" on:click={handleClose}>
                    Cancel
                </button>
                <button
                    type="submit"
                    class="submit-btn"
                    class:escalation={isEscalation}
                    class:demotion={isDemotion}
                    disabled={submitting || newRole === currentRole || ((isEscalation || isDemotion) && !reason)}
                >
                    {#if submitting}
                        Processing...
                    {:else if newRole === currentRole}
                        No Change
                    {:else}
                        Change Role
                    {/if}
                </button>
            </footer>
        </form>
    </div>
</div>

<style>
    .modal-backdrop {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        padding: 1rem;
    }

    .modal {
        width: 100%;
        max-width: 500px;
        background: #1a1a1a;
        border: 1px solid rgba(0, 255, 65, 0.2);
        border-radius: 12px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
    }

    .modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1.25rem 1.5rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }

    .modal-header h2 {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
        color: #e0e0e0;
    }

    .close-btn {
        background: none;
        border: none;
        color: #666;
        font-size: 1.25rem;
        cursor: pointer;
        padding: 0.25rem;
        line-height: 1;
    }

    .close-btn:hover {
        color: #e0e0e0;
    }

    .modal-body {
        padding: 1.5rem;
        display: flex;
        flex-direction: column;
        gap: 1.25rem;
    }

    /* Current Role */
    .current-role {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.75rem 1rem;
        background: rgba(0, 0, 0, 0.3);
        border-radius: 8px;
    }

    .current-role .label {
        font-size: 0.85rem;
        color: #888;
    }

    .role-badge {
        padding: 0.25rem 0.75rem;
        background: color-mix(in srgb, var(--role-color) 15%, transparent);
        border: 1px solid var(--role-color);
        border-radius: 4px;
        font-size: 0.85rem;
        color: var(--role-color);
    }

    /* Form */
    .form-group {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .form-group > label {
        font-size: 0.85rem;
        color: #888;
        font-weight: 500;
    }

    /* Role Options */
    .role-options {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .role-option {
        position: relative;
        cursor: pointer;
    }

    .role-option input {
        position: absolute;
        opacity: 0;
    }

    .role-content {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        padding: 0.875rem 1rem;
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        transition: all 0.2s;
    }

    .role-option:hover .role-content {
        border-color: rgba(255, 255, 255, 0.2);
    }

    .role-option.selected .role-content {
        border-color: var(--role-color);
        background: color-mix(in srgb, var(--role-color) 5%, transparent);
    }

    .role-option.current .role-content {
        opacity: 0.7;
    }

    .role-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .role-title {
        font-size: 0.95rem;
        color: #e0e0e0;
    }

    .role-option.selected .role-title {
        color: var(--role-color);
    }

    .current-badge {
        padding: 0.125rem 0.5rem;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 3px;
        font-size: 0.7rem;
        color: #888;
        text-transform: uppercase;
    }

    .role-desc {
        font-size: 0.8rem;
        color: #666;
        line-height: 1.4;
    }

    /* Warnings */
    .warning {
        display: flex;
        gap: 0.75rem;
        padding: 1rem;
        border-radius: 8px;
    }

    .warning.escalation {
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
    }

    .warning.demotion {
        background: rgba(255, 68, 68, 0.1);
        border: 1px solid rgba(255, 68, 68, 0.3);
    }

    .warning-icon {
        flex-shrink: 0;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 0.9rem;
    }

    .escalation .warning-icon {
        background: rgba(245, 158, 11, 0.2);
        color: #f59e0b;
    }

    .demotion .warning-icon {
        background: rgba(255, 68, 68, 0.2);
        color: #ff4444;
    }

    .warning-content strong {
        display: block;
        margin-bottom: 0.25rem;
        font-size: 0.9rem;
    }

    .escalation .warning-content strong {
        color: #f59e0b;
    }

    .demotion .warning-content strong {
        color: #ff4444;
    }

    .warning-content p {
        margin: 0;
        font-size: 0.85rem;
        color: #888;
        line-height: 1.4;
    }

    /* Textarea */
    textarea {
        padding: 0.75rem;
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(0, 255, 65, 0.2);
        border-radius: 8px;
        color: #e0e0e0;
        font-size: 0.95rem;
        font-family: inherit;
        resize: vertical;
        min-height: 80px;
    }

    textarea:focus {
        outline: none;
        border-color: #00ff41;
    }

    textarea::placeholder {
        color: #555;
    }

    .hint {
        font-size: 0.75rem;
        color: #555;
    }

    /* Footer */
    .modal-footer {
        display: flex;
        justify-content: flex-end;
        gap: 0.75rem;
        padding: 1.25rem 1.5rem;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }

    .cancel-btn {
        padding: 0.625rem 1.25rem;
        background: transparent;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        color: #888;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .cancel-btn:hover {
        border-color: rgba(255, 255, 255, 0.4);
        color: #e0e0e0;
    }

    .submit-btn {
        padding: 0.625rem 1.25rem;
        background: #00ff41;
        border: none;
        border-radius: 6px;
        color: #000;
        font-size: 0.9rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
    }

    .submit-btn:hover:not(:disabled) {
        box-shadow: 0 0 20px rgba(0, 255, 65, 0.4);
    }

    .submit-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .submit-btn.escalation {
        background: #f59e0b;
    }

    .submit-btn.escalation:hover:not(:disabled) {
        box-shadow: 0 0 20px rgba(245, 158, 11, 0.4);
    }

    .submit-btn.demotion {
        background: #ff4444;
        color: #fff;
    }

    .submit-btn.demotion:hover:not(:disabled) {
        box-shadow: 0 0 20px rgba(255, 68, 68, 0.4);
    }
</style>
