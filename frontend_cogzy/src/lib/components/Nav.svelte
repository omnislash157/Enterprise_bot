<script lang="ts">
    import { tenant } from '$lib/stores/tenant';

    // Feature check helper
    $: features = $tenant.features || {};
</script>

<nav>
    <div class="nav-brand">
        {#if $tenant.branding?.logo}
            <img src={$tenant.branding.logo} alt="" class="nav-logo" />
        {/if}
        <span>{$tenant.name}</span>
    </div>

    <div class="nav-links">
        <a href="/chat">Chat</a>

        {#if features.department_switching}
            <a href="/departments">Departments</a>
        {/if}

        {#if features.analytics}
            <a href="/analytics">Analytics</a>
        {/if}

        {#if features.credit_page}
            <a href="/credit">Credit</a>
        {/if}

        {#if features.custom_reports}
            <a href="/reports">Reports</a>
        {/if}

        <a href="/admin">Admin</a>
    </div>
</nav>

<style>
    nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 2rem;
        background: rgba(0,0,0,0.3);
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }

    .nav-brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        color: white;
        font-weight: 600;
    }

    .nav-logo {
        width: 32px;
        height: 32px;
    }

    .nav-links {
        display: flex;
        gap: 1.5rem;
    }

    .nav-links a {
        color: rgba(255,255,255,0.7);
        text-decoration: none;
        transition: color 0.2s;
    }

    .nav-links a:hover {
        color: white;
    }
</style>
