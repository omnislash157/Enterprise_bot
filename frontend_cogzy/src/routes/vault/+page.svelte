<script lang="ts">
    import { onMount } from 'svelte';
    import {
        vault,
        vaultStatus,
        vaultLoading,
        vaultUploading,
        vaultError,
        vaultNodeCount,
        recentUploads,
        hasActiveUpload,
    } from '$lib/stores/vault';

    let fileInput: HTMLInputElement;
    let dragOver = false;

    onMount(() => {
        vault.loadStatus();
    });

    function openFileDialog() {
        fileInput?.click();
    }

    async function handleFileSelect(event: Event) {
        const target = event.target as HTMLInputElement;
        const files = target.files;
        if (!files || files.length === 0) return;

        await vault.uploadFile(files[0]);
        target.value = '';
    }

    function handleDrop(event: DragEvent) {
        event.preventDefault();
        dragOver = false;

        const files = event.dataTransfer?.files;
        if (!files || files.length === 0) return;

        vault.uploadFile(files[0]);
    }

    function handleDragOver(event: DragEvent) {
        event.preventDefault();
        dragOver = true;
    }

    function handleDragLeave() {
        dragOver = false;
    }

    function formatBytes(bytes: number): string {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function formatDate(dateStr: string | null): string {
        if (!dateStr) return 'Never';
        const date = new Date(dateStr);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function getSourceIcon(sourceType: string): string {
        switch (sourceType) {
            case 'anthropic': return '🧠';
            case 'openai': return '🤖';
            case 'grok': return '⚡';
            case 'gemini': return '💎';
            default: return '📄';
        }
    }

    function getSourceLabel(sourceType: string): string {
        switch (sourceType) {
            case 'anthropic': return 'Claude';
            case 'openai': return 'ChatGPT';
            case 'grok': return 'Grok';
            case 'gemini': return 'Gemini';
            default: return 'Unknown';
        }
    }

    function getStatusClass(status: string): string {
        switch (status) {
            case 'complete': return 'status-complete';
            case 'processing': return 'status-processing';
            case 'pending': return 'status-pending';
            case 'failed': return 'status-failed';
            default: return '';
        }
    }
</script>

<svelte:head>
    <title>Memory Vault - Cogzy</title>
</svelte:head>

<div class="vault-page">
    <div class="vault-container">
        <!-- Header -->
        <header class="vault-header">
            <div class="header-content">
                <h1>
                    <span class="icon">🧠</span>
                    Memory Vault
                </h1>
                <p class="subtitle">
                    Upload your chat history from Claude, ChatGPT, Grok, or Gemini to enhance Cogzy's memory.
                </p>
            </div>
        </header>

        <!-- Stats Cards -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">📊</div>
                <div class="stat-content">
                    <div class="stat-value">{$vaultNodeCount.toLocaleString()}</div>
                    <div class="stat-label">Memory Nodes</div>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-icon">💾</div>
                <div class="stat-content">
                    <div class="stat-value">{formatBytes($vaultStatus?.total_bytes ?? 0)}</div>
                    <div class="stat-label">Total Data</div>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-icon">🔄</div>
                <div class="stat-content">
                    <div class="stat-value status-{$vaultStatus?.status ?? 'empty'}">
                        {$vaultStatus?.status ?? 'Empty'}
                    </div>
                    <div class="stat-label">Vault Status</div>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-icon">📅</div>
                <div class="stat-content">
                    <div class="stat-value">{formatDate($vaultStatus?.last_sync_at ?? null)}</div>
                    <div class="stat-label">Last Sync</div>
                </div>
            </div>
        </div>

        <!-- Upload Zone -->
        <div
            class="upload-zone"
            class:drag-over={dragOver}
            class:uploading={$vaultUploading}
            on:drop={handleDrop}
            on:dragover={handleDragOver}
            on:dragleave={handleDragLeave}
            role="button"
            tabindex="0"
            on:click={openFileDialog}
            on:keydown={(e) => e.key === 'Enter' && openFileDialog()}
        >
            {#if $vaultUploading}
                <div class="upload-spinner"></div>
                <p>Processing upload...</p>
            {:else}
                <div class="upload-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M4 14v6a2 2 0 002 2h12a2 2 0 002-2v-6" />
                        <polyline points="16 6 12 2 8 6" />
                        <line x1="12" y1="2" x2="12" y2="15" />
                    </svg>
                </div>
                <p class="upload-text">
                    <strong>Drop your chat export here</strong>
                    <br />
                    or click to browse
                </p>
                <div class="supported-formats">
                    <span class="format">Claude (conversations.json)</span>
                    <span class="format">ChatGPT (.zip or .json)</span>
                    <span class="format">Grok</span>
                    <span class="format">Gemini</span>
                </div>
            {/if}

            <input
                type="file"
                bind:this={fileInput}
                on:change={handleFileSelect}
                accept=".json,.zip"
                style="display: none;"
            />
        </div>

        <!-- Error Display -->
        {#if $vaultError}
            <div class="error-banner">
                <span class="error-icon">⚠️</span>
                <span class="error-text">{$vaultError}</span>
                <button class="error-dismiss" on:click={() => vault.clearError()}>×</button>
            </div>
        {/if}

        <!-- Recent Uploads -->
        <section class="uploads-section">
            <h2>Recent Uploads</h2>

            {#if $vaultLoading}
                <div class="loading-state">
                    <div class="spinner"></div>
                    <span>Loading...</span>
                </div>
            {:else if $recentUploads.length === 0}
                <div class="empty-state">
                    <p>No uploads yet. Upload your first chat export to get started!</p>
                </div>
            {:else}
                <div class="uploads-list">
                    {#each $recentUploads as upload (upload.id)}
                        <div class="upload-item {getStatusClass(upload.status)}">
                            <div class="upload-icon-cell">
                                <span class="source-icon">{getSourceIcon(upload.source_type)}</span>
                            </div>
                            <div class="upload-info">
                                <div class="upload-filename">{upload.filename}</div>
                                <div class="upload-meta">
                                    <span class="source-label">{getSourceLabel(upload.source_type)}</span>
                                    <span class="sep">•</span>
                                    <span class="upload-date">{formatDate(upload.uploaded_at)}</span>
                                </div>
                            </div>
                            <div class="upload-status-cell">
                                {#if upload.status === 'processing'}
                                    <div class="progress-bar">
                                        <div class="progress-fill" style="width: {upload.progress_pct}%"></div>
                                    </div>
                                    <span class="progress-text">{upload.progress_pct}%</span>
                                {:else if upload.status === 'complete'}
                                    <span class="status-badge complete">
                                        ✓ {upload.nodes_created} nodes
                                    </span>
                                {:else if upload.status === 'failed'}
                                    <span class="status-badge failed">Failed</span>
                                {:else}
                                    <span class="status-badge pending">Pending</span>
                                {/if}
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        </section>

        <!-- Info Section -->
        <section class="info-section">
            <h3>How it works</h3>
            <div class="info-grid">
                <div class="info-card">
                    <div class="info-icon">1️⃣</div>
                    <div class="info-content">
                        <strong>Export your chats</strong>
                        <p>Download your conversation history from Claude, ChatGPT, Grok, or Gemini.</p>
                    </div>
                </div>
                <div class="info-card">
                    <div class="info-icon">2️⃣</div>
                    <div class="info-content">
                        <strong>Upload here</strong>
                        <p>Drop the exported file. We detect the format automatically.</p>
                    </div>
                </div>
                <div class="info-card">
                    <div class="info-icon">3️⃣</div>
                    <div class="info-content">
                        <strong>Enhanced memory</strong>
                        <p>Your conversations become searchable context for Cogzy to reference.</p>
                    </div>
                </div>
            </div>
        </section>
    </div>
</div>

<style>
    .vault-page {
        min-height: calc(100vh - 56px);
        background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
        padding: 2rem;
    }

    .vault-container {
        max-width: 900px;
        margin: 0 auto;
    }

    /* Header */
    .vault-header {
        margin-bottom: 2rem;
    }

    .vault-header h1 {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-size: 1.75rem;
        font-weight: 700;
        color: #fff;
        margin: 0 0 0.5rem 0;
    }

    .vault-header .icon {
        font-size: 1.5rem;
    }

    .vault-header .subtitle {
        color: #888;
        font-size: 0.95rem;
        margin: 0;
    }

    /* Stats Grid */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 1rem;
        margin-bottom: 2rem;
    }

    .stat-card {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1.25rem;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
    }

    .stat-icon {
        font-size: 1.5rem;
    }

    .stat-value {
        font-size: 1.25rem;
        font-weight: 600;
        color: #fff;
    }

    .stat-value.status-ready { color: #00ff41; }
    .stat-value.status-syncing { color: #ffcc00; }
    .stat-value.status-empty { color: #666; }
    .stat-value.status-error { color: #ff4444; }

    .stat-label {
        font-size: 0.8rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Upload Zone */
    .upload-zone {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 3rem 2rem;
        background: rgba(0, 255, 65, 0.02);
        border: 2px dashed rgba(0, 255, 65, 0.3);
        border-radius: 16px;
        cursor: pointer;
        transition: all 0.2s ease;
        margin-bottom: 2rem;
    }

    .upload-zone:hover {
        background: rgba(0, 255, 65, 0.05);
        border-color: rgba(0, 255, 65, 0.5);
    }

    .upload-zone.drag-over {
        background: rgba(0, 255, 65, 0.1);
        border-color: #00ff41;
        box-shadow: 0 0 30px rgba(0, 255, 65, 0.2);
    }

    .upload-zone.uploading {
        pointer-events: none;
        opacity: 0.7;
    }

    .upload-icon {
        width: 64px;
        height: 64px;
        color: #00ff41;
        opacity: 0.7;
        margin-bottom: 1rem;
    }

    .upload-icon svg {
        width: 100%;
        height: 100%;
    }

    .upload-text {
        color: #ccc;
        text-align: center;
        margin: 0 0 1rem 0;
        line-height: 1.6;
    }

    .upload-text strong {
        color: #fff;
    }

    .supported-formats {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        justify-content: center;
    }

    .format {
        font-size: 0.75rem;
        padding: 0.25rem 0.75rem;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        color: #888;
    }

    .upload-spinner {
        width: 40px;
        height: 40px;
        border: 3px solid rgba(0, 255, 65, 0.2);
        border-top-color: #00ff41;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
        margin-bottom: 1rem;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    /* Error Banner */
    .error-banner {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 1rem 1.25rem;
        background: rgba(255, 68, 68, 0.1);
        border: 1px solid rgba(255, 68, 68, 0.3);
        border-radius: 8px;
        margin-bottom: 2rem;
    }

    .error-icon {
        font-size: 1.25rem;
    }

    .error-text {
        flex: 1;
        color: #ff6666;
        font-size: 0.9rem;
    }

    .error-dismiss {
        background: none;
        border: none;
        color: #ff6666;
        font-size: 1.5rem;
        cursor: pointer;
        padding: 0;
        line-height: 1;
    }

    /* Uploads Section */
    .uploads-section {
        margin-bottom: 2rem;
    }

    .uploads-section h2 {
        font-size: 1.1rem;
        font-weight: 600;
        color: #fff;
        margin: 0 0 1rem 0;
    }

    .loading-state,
    .empty-state {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        padding: 2rem;
        color: #666;
        font-size: 0.9rem;
    }

    .loading-state .spinner {
        width: 20px;
        height: 20px;
        border: 2px solid rgba(255, 255, 255, 0.1);
        border-top-color: #00ff41;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
    }

    .uploads-list {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .upload-item {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1rem 1.25rem;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        transition: all 0.15s ease;
    }

    .upload-item:hover {
        background: rgba(255, 255, 255, 0.05);
    }

    .upload-item.status-processing {
        border-color: rgba(255, 204, 0, 0.3);
    }

    .upload-item.status-complete {
        border-color: rgba(0, 255, 65, 0.2);
    }

    .upload-item.status-failed {
        border-color: rgba(255, 68, 68, 0.3);
    }

    .upload-icon-cell {
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
    }

    .source-icon {
        font-size: 1.25rem;
    }

    .upload-info {
        flex: 1;
        min-width: 0;
    }

    .upload-filename {
        color: #fff;
        font-size: 0.9rem;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .upload-meta {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.8rem;
        color: #666;
        margin-top: 0.25rem;
    }

    .sep {
        opacity: 0.5;
    }

    .source-label {
        color: #888;
    }

    .upload-status-cell {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .progress-bar {
        width: 80px;
        height: 6px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 3px;
        overflow: hidden;
    }

    .progress-fill {
        height: 100%;
        background: #ffcc00;
        transition: width 0.3s ease;
    }

    .progress-text {
        font-size: 0.75rem;
        color: #ffcc00;
        min-width: 35px;
    }

    .status-badge {
        font-size: 0.75rem;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-weight: 500;
    }

    .status-badge.complete {
        background: rgba(0, 255, 65, 0.1);
        color: #00ff41;
    }

    .status-badge.pending {
        background: rgba(255, 255, 255, 0.05);
        color: #888;
    }

    .status-badge.failed {
        background: rgba(255, 68, 68, 0.1);
        color: #ff6666;
    }

    /* Info Section */
    .info-section {
        margin-top: 3rem;
        padding-top: 2rem;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
    }

    .info-section h3 {
        font-size: 1rem;
        font-weight: 600;
        color: #fff;
        margin: 0 0 1.5rem 0;
    }

    .info-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 1rem;
    }

    .info-card {
        display: flex;
        gap: 1rem;
        padding: 1rem;
        background: rgba(255, 255, 255, 0.02);
        border-radius: 10px;
    }

    .info-icon {
        font-size: 1.25rem;
        flex-shrink: 0;
    }

    .info-content strong {
        display: block;
        color: #fff;
        font-size: 0.9rem;
        margin-bottom: 0.25rem;
    }

    .info-content p {
        color: #666;
        font-size: 0.8rem;
        margin: 0;
        line-height: 1.5;
    }

    /* Responsive */
    @media (max-width: 768px) {
        .vault-page {
            padding: 1rem;
        }

        .stats-grid {
            grid-template-columns: repeat(2, 1fr);
        }

        .upload-zone {
            padding: 2rem 1rem;
        }

        .upload-item {
            flex-wrap: wrap;
        }

        .upload-status-cell {
            width: 100%;
            margin-top: 0.5rem;
            padding-left: 56px;
        }
    }
</style>
