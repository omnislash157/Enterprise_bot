/**
 * Vault Store - Personal Memory Vault Management
 *
 * Handles:
 * - Vault status (node count, total bytes, status)
 * - Upload chat exports (Anthropic, OpenAI, Grok, Gemini)
 * - Track upload progress
 */

import { writable, derived } from 'svelte/store';

interface VaultUpload {
    id: string;
    source_type: string;
    filename: string;
    status: 'pending' | 'processing' | 'complete' | 'failed';
    progress_pct: number;
    nodes_created: number;
    uploaded_at: string | null;
}

interface VaultStatus {
    node_count: number;
    total_bytes: number;
    status: 'empty' | 'syncing' | 'ready' | 'error';
    last_sync_at: string | null;
    uploads: VaultUpload[];
}

interface VaultState {
    status: VaultStatus | null;
    loading: boolean;
    uploading: boolean;
    error: string | null;
    activeUploadId: string | null;
}

function getApiBase(): string {
    return import.meta.env.VITE_API_URL || 'https://lucky-love-production.up.railway.app';
}

function createVaultStore() {
    const { subscribe, set, update } = writable<VaultState>({
        status: null,
        loading: false,
        uploading: false,
        error: null,
        activeUploadId: null,
    });

    let pollInterval: ReturnType<typeof setInterval> | null = null;

    const store = {
        subscribe,

        /**
         * Load vault status
         */
        async loadStatus() {
            update(s => ({ ...s, loading: true, error: null }));

            try {
                const apiBase = getApiBase();
                const res = await fetch(`${apiBase}/api/personal/vault/status`, {
                    credentials: 'include',
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Failed to load vault status');
                }

                const status: VaultStatus = await res.json();
                update(s => ({ ...s, status, loading: false }));
            } catch (e) {
                update(s => ({ ...s, loading: false, error: String(e) }));
            }
        },

        /**
         * Upload a chat export file
         */
        async uploadFile(file: File): Promise<string | null> {
            update(s => ({ ...s, uploading: true, error: null }));

            try {
                const apiBase = getApiBase();
                const formData = new FormData();
                formData.append('file', file);

                const res = await fetch(`${apiBase}/api/personal/vault/upload`, {
                    method: 'POST',
                    credentials: 'include',
                    body: formData,
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Upload failed');
                }

                const result = await res.json();
                const uploadId = result.upload_id;

                update(s => ({
                    ...s,
                    uploading: false,
                    activeUploadId: uploadId,
                }));

                // Start polling for progress
                this.startProgressPolling(uploadId);

                // Reload status to get new upload in list
                await this.loadStatus();

                return uploadId;
            } catch (e) {
                update(s => ({ ...s, uploading: false, error: String(e) }));
                return null;
            }
        },

        /**
         * Get progress for a specific upload
         */
        async getUploadProgress(uploadId: string) {
            try {
                const apiBase = getApiBase();
                const res = await fetch(`${apiBase}/api/personal/vault/upload/${uploadId}`, {
                    credentials: 'include',
                });

                if (!res.ok) {
                    return null;
                }

                return await res.json();
            } catch (e) {
                console.error('Failed to get upload progress:', e);
                return null;
            }
        },

        /**
         * Poll for upload progress until complete
         */
        startProgressPolling(uploadId: string) {
            // Clear any existing poll
            if (pollInterval) {
                clearInterval(pollInterval);
            }

            pollInterval = setInterval(async () => {
                const progress = await this.getUploadProgress(uploadId);

                if (!progress) {
                    this.stopProgressPolling();
                    return;
                }

                // Update the upload in status if we have it
                update(s => {
                    if (!s.status) return s;

                    const uploads = s.status.uploads.map(u =>
                        u.id === uploadId
                            ? { ...u, ...progress }
                            : u
                    );

                    return {
                        ...s,
                        status: { ...s.status, uploads },
                    };
                });

                // Stop polling when complete or failed
                if (progress.status === 'complete' || progress.status === 'failed') {
                    this.stopProgressPolling();
                    // Reload full status to get updated node count
                    await this.loadStatus();
                }
            }, 2000); // Poll every 2 seconds
        },

        /**
         * Stop polling
         */
        stopProgressPolling() {
            if (pollInterval) {
                clearInterval(pollInterval);
                pollInterval = null;
            }
            update(s => ({ ...s, activeUploadId: null }));
        },

        /**
         * Clear error
         */
        clearError() {
            update(s => ({ ...s, error: null }));
        },
    };

    return store;
}

export const vault = createVaultStore();

// Derived stores
export const vaultStatus = derived(vault, $v => $v.status);
export const vaultLoading = derived(vault, $v => $v.loading);
export const vaultUploading = derived(vault, $v => $v.uploading);
export const vaultError = derived(vault, $v => $v.error);
export const vaultNodeCount = derived(vault, $v => $v.status?.node_count ?? 0);
export const vaultReady = derived(vault, $v => $v.status?.status === 'ready');

// Upload helpers
export const recentUploads = derived(vault, $v => $v.status?.uploads ?? []);
export const hasActiveUpload = derived(vault, $v => $v.activeUploadId !== null);
