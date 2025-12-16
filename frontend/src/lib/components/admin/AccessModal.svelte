<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    import type { Department } from '$lib/stores/admin';

    export let mode: 'grant' | 'revoke' = 'grant';
    export let departments: Department[] = [];
    export let preselectedDepartment: string | null = null;

    const dispatch = createEventDispatcher();

    // Form state
    let selectedDepartment = preselectedDepartment || '';
    let accessLevel = 'read';
    let makeDeptHead = false;
    let reason = '';
    let submitting = false;

    // Access levels
    const accessLevels = [
        { value: 'read', label: 'Read Only', description: 'View department content' },
        { value: 'write', label: 'Read/Write', description: 'View and edit content' },
        { value: 'admin', label: 'Admin', description: 'Full department access' },
    ];

    async function handleSubmit() {
        if (!selectedDepartment) return;

        submitting = true;

        dispatch('submit', {
            departmentSlug: selectedDepartment,
            accessLevel: mode === 'grant' ? accessLevel : undefined,
            makeDeptHead: mode === 'grant' ? makeDeptHead : undefined,
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
</script>

<div class="modal-backdrop" on:click={handleBackdropClick}>
    <div class="modal">
        <header class="modal-header">
            <h2>{mode === 'grant' ? 'Grant Department Access' : 'Revoke Access'}</h2>
            <button class="close-btn" on:click={handleClose}>x</button>
        </header>

        <form on:submit|preventDefault={handleSubmit}>
            <div class="modal-body">
                <!-- Department Selection -->
                <div class="form-group">
                    <label for="department">Department</label>
                    {#if mode === 'revoke' && preselectedDepartment}
                        <div class="static-value">{preselectedDepartment}</div>
                    {:else}
                        <select
                            id="department"
                            bind:value={selectedDepartment}
                            required
                        >
                            <option value="">Select department...</option>
                            {#each departments as dept}
                                <option value={dept.slug}>{dept.name}</option>
                            {/each}
                        </select>
                    {/if}
                </div>

                <!-- Grant-specific fields -->
                {#if mode === 'grant'}
                    <!-- Access Level -->
                    <div class="form-group">
                        <label>Access Level</label>
                        <div class="radio-group">
                            {#each accessLevels as level}
                                <label class="radio-option">
                                    <input
                                        type="radio"
                                        name="accessLevel"
                                        value={level.value}
                                        bind:group={accessLevel}
                                    />
                                    <span class="radio-label">
                                        <span class="radio-title">{level.label}</span>
                                        <span class="radio-desc">{level.description}</span>
                                    </span>
                                </label>
                            {/each}
                        </div>
                    </div>

                    <!-- Dept Head Toggle -->
                    <div class="form-group">
                        <label class="checkbox-option">
                            <input
                                type="checkbox"
                                bind:checked={makeDeptHead}
                            />
                            <span class="checkbox-label">
                                <span class="checkbox-title">Make Department Head</span>
                                <span class="checkbox-desc">
                                    Allows user to manage other users in this department
                                </span>
                            </span>
                        </label>
                    </div>
                {/if}

                <!-- Reason (for audit) -->
                <div class="form-group">
                    <label for="reason">Reason (optional)</label>
                    <textarea
                        id="reason"
                        bind:value={reason}
                        placeholder="Explain why this change is being made..."
                        rows="3"
                    ></textarea>
                    <span class="hint">This will be recorded in the audit log</span>
                </div>

                <!-- Warning for revoke -->
                {#if mode === 'revoke'}
                    <div class="warning">
                        <span class="warning-icon">!</span>
                        <p>This will immediately remove the user's access to this department. They will no longer be able to view or access department content.</p>
                    </div>
                {/if}
            </div>

            <footer class="modal-footer">
                <button type="button" class="cancel-btn" on:click={handleClose}>
                    Cancel
                </button>
                <button
                    type="submit"
                    class="submit-btn"
                    class:danger={mode === 'revoke'}
                    disabled={submitting || !selectedDepartment}
                >
                    {#if submitting}
                        Processing...
                    {:else if mode === 'grant'}
                        Grant Access
                    {:else}
                        Revoke Access
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
        max-width: 480px;
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

    select,
    textarea {
        padding: 0.75rem;
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(0, 255, 65, 0.2);
        border-radius: 8px;
        color: #e0e0e0;
        font-size: 0.95rem;
        font-family: inherit;
    }

    select:focus,
    textarea:focus {
        outline: none;
        border-color: #00ff41;
    }

    textarea {
        resize: vertical;
        min-height: 80px;
    }

    textarea::placeholder {
        color: #555;
    }

    .static-value {
        padding: 0.75rem;
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        color: #e0e0e0;
        font-size: 0.95rem;
        text-transform: capitalize;
    }

    .hint {
        font-size: 0.75rem;
        color: #555;
    }

    /* Radio Group */
    .radio-group {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .radio-option {
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
        padding: 0.75rem;
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s;
    }

    .radio-option:hover {
        border-color: rgba(0, 255, 65, 0.2);
    }

    .radio-option input {
        margin-top: 0.25rem;
        accent-color: #00ff41;
    }

    .radio-label {
        display: flex;
        flex-direction: column;
        gap: 0.125rem;
    }

    .radio-title {
        font-size: 0.9rem;
        color: #e0e0e0;
    }

    .radio-desc {
        font-size: 0.8rem;
        color: #666;
    }

    /* Checkbox */
    .checkbox-option {
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
        padding: 0.75rem;
        background: rgba(245, 158, 11, 0.05);
        border: 1px solid rgba(245, 158, 11, 0.2);
        border-radius: 8px;
        cursor: pointer;
    }

    .checkbox-option input {
        margin-top: 0.25rem;
        accent-color: #f59e0b;
    }

    .checkbox-label {
        display: flex;
        flex-direction: column;
        gap: 0.125rem;
    }

    .checkbox-title {
        font-size: 0.9rem;
        color: #f59e0b;
    }

    .checkbox-desc {
        font-size: 0.8rem;
        color: #666;
    }

    /* Warning */
    .warning {
        display: flex;
        gap: 0.75rem;
        padding: 1rem;
        background: rgba(255, 68, 68, 0.1);
        border: 1px solid rgba(255, 68, 68, 0.3);
        border-radius: 8px;
    }

    .warning-icon {
        flex-shrink: 0;
        width: 24px;
        height: 24px;
        background: rgba(255, 68, 68, 0.2);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ff4444;
        font-weight: bold;
        font-size: 0.9rem;
    }

    .warning p {
        margin: 0;
        font-size: 0.85rem;
        color: #ff6b6b;
        line-height: 1.5;
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

    .submit-btn.danger {
        background: #ff4444;
        color: #fff;
    }

    .submit-btn.danger:hover:not(:disabled) {
        box-shadow: 0 0 20px rgba(255, 68, 68, 0.4);
    }
</style>