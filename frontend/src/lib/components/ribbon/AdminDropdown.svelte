<script lang="ts">
    import { isSuperUser, canSeeAdminDerived, userDeptHeadFor } from '$lib/stores/auth';
    import { clickOutside } from '$lib/utils/clickOutside';

    export let currentPath: string;

    let open = false;

    $: isAdminRoute = currentPath.startsWith('/admin');
    
    // User can see admin if they're a super user or dept head
    $: canSeeAdmin = $canSeeAdminDerived;

    const adminLinks = [
        { href: '/admin', label: 'Nerve Center', icon: '⚡', superOnly: false },
        { href: '/admin/analytics', label: 'Analytics', icon: '📊', superOnly: false },
        { href: '/admin/users', label: 'User Management', icon: '👥', superOnly: false },
        { href: '/admin/audit', label: 'Audit Log', icon: '📋', superOnly: true },
    ];

    function toggle() {
        open = !open;
    }

    function close() {
        open = false;
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === 'Escape') {
            close();
        }
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggle();
        }
    }
</script>

{#if canSeeAdmin}
<div class="admin-dropdown" use:clickOutside={close}>
    <button
        class="admin-trigger"
        class:active={isAdminRoute}
        on:click={toggle}
        on:keydown={handleKeydown}
        aria-haspopup="true"
        aria-expanded={open}
    >
        <span class="trigger-icon">⚡</span>
        <span class="trigger-label">Admin</span>
        <svg class="chevron" class:open viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg>
    </button>

    {#if open}
        <div class="dropdown-menu">
            <div class="dropdown-header">Admin Portal</div>

            {#each adminLinks as link}
                {#if !link.superOnly || $isSuperUser}
                    <a
                        href={link.href}
                        class="dropdown-item"
                        class:active={currentPath === link.href}
                        on:click={close}
                    >
                        <span class="item-icon">{link.icon}</span>
                        <span class="item-label">{link.label}</span>
                        {#if link.superOnly}
                            <span class="super-badge">SUPER</span>
                        {/if}
                    </a>
                {/if}
            {/each}
        </div>
    {/if}
</div>
{/if}

<style>
    .admin-dropdown {
        position: relative;
    }

    .admin-trigger {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 0.75rem;

        background: rgba(255, 200, 0, 0.1);
        border: 1px solid rgba(255, 200, 0, 0.2);
        border-radius: 6px;

        color: #ffc800;
        font-size: 0.875rem;
        font-weight: 500;
        cursor: pointer;

        transition: all 0.2s ease;
    }

    .admin-trigger:hover {
        background: rgba(255, 200, 0, 0.15);
        border-color: rgba(255, 200, 0, 0.4);
    }

    .admin-trigger.active {
        background: rgba(255, 200, 0, 0.2);
        border-color: rgba(255, 200, 0, 0.5);
        box-shadow: 0 0 15px rgba(255, 200, 0, 0.2);
    }

    .trigger-icon {
        font-size: 1rem;
    }

    .chevron {
        width: 16px;
        height: 16px;
        transition: transform 0.2s ease;
    }

    .chevron.open {
        transform: rotate(180deg);
    }

    .dropdown-menu {
        position: absolute;
        top: calc(100% + 8px);
        right: 0;
        min-width: 200px;

        background: rgba(15, 15, 20, 0.95);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 200, 0, 0.2);
        border-radius: 8px;

        box-shadow:
            0 10px 40px rgba(0, 0, 0, 0.5),
            0 0 20px rgba(255, 200, 0, 0.1);

        overflow: hidden;
        animation: dropIn 0.15s ease-out;
    }

    @keyframes dropIn {
        from {
            opacity: 0;
            transform: translateY(-8px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .dropdown-header {
        padding: 0.75rem 1rem;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: rgba(255, 200, 0, 0.6);
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .dropdown-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.75rem 1rem;

        color: rgba(255, 255, 255, 0.8);
        text-decoration: none;
        font-size: 0.875rem;

        transition: all 0.15s ease;
    }

    .dropdown-item:hover {
        background: rgba(255, 200, 0, 0.1);
        color: #fff;
    }

    .dropdown-item.active {
        background: rgba(255, 200, 0, 0.15);
        color: #ffc800;
    }

    .item-icon {
        font-size: 1rem;
        width: 20px;
        text-align: center;
    }

    .item-label {
        flex: 1;
    }

    .super-badge {
        font-size: 0.6rem;
        font-weight: 700;
        padding: 2px 6px;
        background: rgba(255, 0, 85, 0.2);
        color: #ff0055;
        border-radius: 3px;
        letter-spacing: 0.5px;
    }

    /* Mobile */
    @media (max-width: 640px) {
        .trigger-label {
            display: none;
        }
    }
</style>