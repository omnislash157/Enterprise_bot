<script lang="ts">
    import { auth, userDepartments, isSuperUser } from '$lib/stores/auth';
    import { createEventDispatcher, onMount } from 'svelte';

    export let selected: string = '';

    const dispatch = createEventDispatcher();

    interface Department {
        slug: string;
        name: string;
        description: string | null;
    }

    let departments: Department[] = [];
    let loading = true;
    let error = '';
    let initialized = false;  // Track if we've done initial setup

    function getApiBase(): string {
        return import.meta.env.VITE_API_URL || 'http://localhost:8000';
    }

    onMount(async () => {
        const headers = auth.getAuthHeader();

        try {
            const apiBase = getApiBase();
            const res = await fetch(`${apiBase}/api/departments`, { headers });

            if (res.ok) {
                const data = await res.json();
                departments = data.departments;

                // Auto-select first if none selected, but DON'T dispatch
                // The initial division is handled by session.init()
                if (!selected && departments.length > 0) {
                    selected = departments[0].slug;
                    // Don't dispatch on initial load - session.init handles this
                }
            } else {
                error = 'Failed to load departments';
            }
        } catch (e) {
            error = 'Failed to load departments';
            console.error('[DepartmentSelector]', e);
        }

        loading = false;
        initialized = true;
    });

    function handleChange() {
        // Only dispatch after initialization (user-triggered changes)
        if (initialized) {
            dispatch('change', selected);
        }
    }
</script>

{#if loading}
    <span class="loading">Loading...</span>
{:else if error}
    <span class="error">{error}</span>
{:else if departments.length > 0}
    <div class="selector-wrapper">
        <select bind:value={selected} on:change={handleChange}>
            {#each departments as dept}
                <option value={dept.slug}>{dept.name}</option>
            {/each}
        </select>
        <span class="dropdown-arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" width="12" height="12"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
{:else}
    <span class="no-access">No departments available</span>
{/if}

<style>
    .selector-wrapper {
        position: relative;
        display: inline-block;
    }

    select {
        appearance: none;
        -webkit-appearance: none;
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(0, 255, 65, 0.3);
        border-radius: 8px;
        padding: 0.5rem 2rem 0.5rem 0.75rem;
        color: #e0e0e0;
        font-size: 0.9rem;
        font-family: inherit;
        cursor: pointer;
        transition: border-color 0.2s, box-shadow 0.2s;
        min-width: 150px;
    }

    select:focus {
        outline: none;
        border-color: #00ff41;
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.2);
    }

    select:hover {
        border-color: rgba(0, 255, 65, 0.5);
    }

    select option {
        background: #1a1a1a;
        color: #e0e0e0;
        padding: 0.5rem;
    }

    .dropdown-arrow {
        position: absolute;
        right: 0.75rem;
        top: 50%;
        transform: translateY(-50%);
        color: #00ff41;
        font-size: 0.6rem;
        pointer-events: none;
    }

    .loading, .error, .no-access {
        color: #666;
        font-size: 0.85rem;
    }

    .error {
        color: #ff4444;
    }
</style>