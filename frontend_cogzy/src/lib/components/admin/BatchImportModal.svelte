<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    import { adminStore, adminDepartments } from '$lib/stores/admin';

    export let open = false;

    const dispatch = createEventDispatcher();

    let inputText = '';
    let defaultDepartment = 'warehouse';
    let reason = 'batch_import';

    let loading = false;
    let error = '';
    let results: {
        created: string[];
        already_existed: string[];
        failed: Array<{ email: string; error: string }>;
    } | null = null;

    // Load departments when modal opens
    $: if (open && $adminDepartments.length === 0) {
        adminStore.loadDepartments();
    }

    function reset() {
        inputText = '';
        defaultDepartment = 'warehouse';
        reason = 'batch_import';
        error = '';
        results = null;
    }

    function close() {
        reset();
        open = false;
        dispatch('close');
    }

    function parseInput(text: string): Array<{ email: string; display_name?: string; department?: string }> {
        const lines = text.split('\n').filter(line => line.trim());
        const users: Array<{ email: string; display_name?: string; department?: string }> = [];

        for (const line of lines) {
            // Support formats:
            // email@domain.com
            // email@domain.com, Display Name
            // email@domain.com, Display Name, department
            const parts = line.split(',').map(p => p.trim());

            if (parts.length > 0 && parts[0]) {
                const entry: { email: string; display_name?: string; department?: string } = {
                    email: parts[0]
                };

                if (parts.length > 1 && parts[1]) {
                    entry.display_name = parts[1];
                }

                if (parts.length > 2 && parts[2]) {
                    entry.department = parts[2];
                }

                users.push(entry);
            }
        }

        return users;
    }

    async function submit() {
        const users = parseInput(inputText);

        if (users.length === 0) {
            error = 'No valid entries found. Enter one email per line.';
            return;
        }

        loading = true;
        error = '';
        results = null;

        const result = await adminStore.batchCreateUsers({
            users,
            default_department: defaultDepartment,
            reason: reason.trim() || 'batch_import',
        });

        loading = false;

        if (result.success && result.data) {
            results = {
                created: result.data.created,
                already_existed: result.data.already_existed,
                failed: result.data.failed,
            };

            // If all succeeded, dispatch and close after delay
            if (result.data.failed_count === 0) {
                dispatch('imported', result.data);
            }
        } else {
            error = result.error || 'Failed to import users';
        }
    }

    function handleFileUpload(event: Event) {
        const input = event.target as HTMLInputElement;
        const file = input.files?.[0];

        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                inputText = e.target?.result as string || '';
            };
            reader.readAsText(file);
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
            <h2>Batch Import Users</h2>
            <button class="close-btn" on:click={close}>&times;</button>
        </div>

        {#if !results}
            <div class="instructions">
                <p>Enter one user per line. Supported formats:</p>
                <code>
                    email@domain.com<br/>
                    email@domain.com, Display Name<br/>
                    email@domain.com, Display Name, department
                </code>
            </div>

            <div class="form-group">
                <label>Upload CSV (optional)</label>
                <input
                    type="file"
                    accept=".csv,.txt"
                    on:change={handleFileUpload}
                />
            </div>

            <div class="form-group">
                <label for="inputText">Users (one per line)</label>
                <textarea
                    id="inputText"
                    bind:value={inputText}
                    rows="10"
                    placeholder="jdoe@gmail.com, John Doe
jsmith@example.com, Jane Smith
bob@company.com"
                ></textarea>
            </div>

            <div class="form-group">
                <label for="defaultDepartment">Default Department</label>
                <select id="defaultDepartment" bind:value={defaultDepartment}>
                    {#each $adminDepartments as dept}
                        <option value={dept.slug}>{dept.name}</option>
                    {/each}
                </select>
            </div>

            <div class="form-group">
                <label for="reason">Reason</label>
                <input
                    type="text"
                    id="reason"
                    bind:value={reason}
                    placeholder="batch_import"
                />
            </div>

            {#if error}
                <div class="error-message">{error}</div>
            {/if}

            <div class="modal-actions">
                <button type="button" class="btn-secondary" on:click={close}>
                    Cancel
                </button>
                <button
                    type="button"
                    class="btn-primary"
                    disabled={loading || !inputText.trim()}
                    on:click={submit}
                >
                    {loading ? 'Importing...' : 'Import Users'}
                </button>
            </div>
        {:else}
            <div class="results">
                <div class="result-section success">
                    <h3>Created ({results.created.length})</h3>
                    {#if results.created.length > 0}
                        <ul>
                            {#each results.created as email}
                                <li>{email}</li>
                            {/each}
                        </ul>
                    {:else}
                        <p class="empty">None</p>
                    {/if}
                </div>

                <div class="result-section warning">
                    <h3>Already Existed ({results.already_existed.length})</h3>
                    {#if results.already_existed.length > 0}
                        <ul>
                            {#each results.already_existed as email}
                                <li>{email}</li>
                            {/each}
                        </ul>
                    {:else}
                        <p class="empty">None</p>
                    {/if}
                </div>

                <div class="result-section error">
                    <h3>Failed ({results.failed.length})</h3>
                    {#if results.failed.length > 0}
                        <ul>
                            {#each results.failed as item}
                                <li>{item.email}: {item.error}</li>
                            {/each}
                        </ul>
                    {:else}
                        <p class="empty">None</p>
                    {/if}
                </div>
            </div>

            <div class="modal-actions">
                <button type="button" class="btn-primary" on:click={close}>
                    Done
                </button>
            </div>
        {/if}
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
        max-width: 600px;
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

    .instructions {
        background: #0a0a0a;
        border: 1px solid #333;
        border-radius: 4px;
        padding: 12px;
        margin-bottom: 16px;
    }

    .instructions p {
        color: #888;
        margin: 0 0 8px 0;
        font-size: 0.875rem;
    }

    .instructions code {
        color: #00d4ff;
        font-size: 0.75rem;
        line-height: 1.5;
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
    .form-group select,
    .form-group textarea {
        width: 100%;
        padding: 8px 12px;
        background: #0a0a0a;
        border: 1px solid #333;
        border-radius: 4px;
        color: #fff;
        font-size: 0.875rem;
        font-family: inherit;
    }

    .form-group textarea {
        resize: vertical;
        font-family: 'Consolas', 'Monaco', monospace;
    }

    .form-group input[type="file"] {
        padding: 4px;
    }

    .form-group input:focus,
    .form-group select:focus,
    .form-group textarea:focus {
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

    .results {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .result-section {
        padding: 12px;
        border-radius: 4px;
    }

    .result-section h3 {
        margin: 0 0 8px 0;
        font-size: 0.875rem;
    }

    .result-section.success {
        background: rgba(0, 255, 65, 0.1);
        border: 1px solid rgba(0, 255, 65, 0.3);
    }

    .result-section.success h3 {
        color: #00ff41;
    }

    .result-section.warning {
        background: rgba(255, 170, 0, 0.1);
        border: 1px solid rgba(255, 170, 0, 0.3);
    }

    .result-section.warning h3 {
        color: #ffaa00;
    }

    .result-section.error {
        background: rgba(255, 68, 68, 0.1);
        border: 1px solid rgba(255, 68, 68, 0.3);
    }

    .result-section.error h3 {
        color: #ff4444;
    }

    .result-section ul {
        margin: 0;
        padding-left: 20px;
        color: #ccc;
        font-size: 0.75rem;
        max-height: 150px;
        overflow-y: auto;
    }

    .result-section .empty {
        color: #666;
        font-size: 0.75rem;
        margin: 0;
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
