<script lang="ts">
    import { onMount } from 'svelte';
    import { goto } from '$app/navigation';

    let checking = true;

    onMount(async () => {
        // Check if user is authenticated
        try {
            const API_URL = import.meta.env.VITE_API_URL || '';
            const res = await fetch(`${API_URL}/api/personal/auth/me`, {
                credentials: 'include'
            });

            if (res.ok) {
                // User is authenticated, go to chat
                goto('/chat');
            } else {
                // Not authenticated, go to login
                goto('/login');
            }
        } catch {
            // Error checking auth, go to login
            goto('/login');
        }
    });
</script>

{#if checking}
<div class="loading">
    <div class="spinner"></div>
    <p>Loading Cogzy...</p>
</div>
{/if}

<style>
    .loading {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100vh;
        color: white;
        gap: 1rem;
    }

    .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid rgba(255,255,255,0.1);
        border-top-color: #8b5cf6;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }
</style>
