<script lang="ts">
    import { auth, currentUser } from '$lib/stores/auth';
    import { theme } from '$lib/stores/theme';
    import { clickOutside } from '$lib/utils/clickOutside';

    let open = false;

    // Get initials for avatar
    $: initials = $currentUser?.display_name
        ?.split(' ')
        .map(n => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2) || $currentUser?.email?.[0]?.toUpperCase() || '?';

    $: roleBadge = $currentUser?.is_super_user
        ? 'Super Admin'
        : $currentUser?.can_manage_users
            ? 'Admin'
            : 'User';

    function toggle() {
        open = !open;
    }

    function close() {
        open = false;
    }

    function toggleTheme() {
        theme.toggle();
    }

    async function handleLogout() {
        close();
        await auth.logout();
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

<div class="user-menu" use:clickOutside={close}>
    <button class="user-trigger" on:click={toggle} on:keydown={handleKeydown} aria-haspopup="true" aria-expanded={open}>
        <div class="avatar">
            {initials}
        </div>
        <svg class="chevron" class:open viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg>
    </button>

    {#if open}
        <div class="dropdown-menu">
            <!-- User Info Section -->
            <div class="user-info">
                <div class="user-avatar-large">{initials}</div>
                <div class="user-details">
                    <div class="user-name">{$currentUser?.display_name || 'User'}</div>
                    <div class="user-email">{$currentUser?.email}</div>
                    <div class="user-role">{roleBadge}</div>
                </div>
            </div>

            <div class="menu-divider"></div>

            <!-- Department -->
            {#if $currentUser?.primary_department}
                <div class="menu-section">
                    <div class="section-label">Department</div>
                    <div class="department-badge">
                        {$currentUser.primary_department}
                    </div>
                </div>
                <div class="menu-divider"></div>
            {/if}

            <!-- Actions -->
            <button class="menu-item" on:click={toggleTheme}>
                <span class="item-icon">{$theme === 'cyber' ? '🌙' : '⚡'}</span>
                <span class="item-label">
                    {$theme === 'cyber' ? 'Normie Mode' : 'Cyber Mode'}
                </span>
            </button>

            <div class="menu-divider"></div>

            <button class="menu-item logout" on:click={handleLogout}>
                <span class="item-icon">🚪</span>
                <span class="item-label">Sign Out</span>
            </button>
        </div>
    {/if}
</div>

<style>
    .user-menu {
        position: relative;
    }

    .user-trigger {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 4px;

        background: transparent;
        border: none;
        border-radius: 8px;
        cursor: pointer;

        transition: all 0.2s ease;
    }

    .user-trigger:hover {
        background: rgba(255, 255, 255, 0.08);
    }

    .avatar {
        width: 36px;
        height: 36px;

        display: flex;
        align-items: center;
        justify-content: center;

        background: linear-gradient(135deg, #00ff41 0%, #00aa2a 100%);
        border-radius: 8px;

        color: #000;
        font-size: 0.8rem;
        font-weight: 700;

        box-shadow: 0 0 15px rgba(0, 255, 65, 0.3);
    }

    .chevron {
        width: 16px;
        height: 16px;
        color: rgba(255, 255, 255, 0.5);
        transition: transform 0.2s ease;
    }

    .chevron.open {
        transform: rotate(180deg);
    }

    .dropdown-menu {
        position: absolute;
        top: calc(100% + 8px);
        right: 0;
        width: 280px;

        background: rgba(15, 15, 20, 0.95);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(0, 255, 65, 0.2);
        border-radius: 12px;

        box-shadow:
            0 10px 40px rgba(0, 0, 0, 0.5),
            0 0 30px rgba(0, 255, 65, 0.1);

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

    .user-info {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1rem;
    }

    .user-avatar-large {
        width: 48px;
        height: 48px;
        flex-shrink: 0;

        display: flex;
        align-items: center;
        justify-content: center;

        background: linear-gradient(135deg, #00ff41 0%, #00aa2a 100%);
        border-radius: 10px;

        color: #000;
        font-size: 1.1rem;
        font-weight: 700;
    }

    .user-details {
        flex: 1;
        min-width: 0;
    }

    .user-name {
        font-size: 0.95rem;
        font-weight: 600;
        color: #fff;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .user-email {
        font-size: 0.75rem;
        color: rgba(255, 255, 255, 0.5);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .user-role {
        display: inline-block;
        margin-top: 0.25rem;
        padding: 2px 8px;

        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;

        background: rgba(0, 255, 65, 0.15);
        color: #00ff41;
        border-radius: 4px;
    }

    .menu-divider {
        height: 1px;
        background: rgba(255, 255, 255, 0.08);
        margin: 0.25rem 0;
    }

    .menu-section {
        padding: 0.75rem 1rem;
    }

    .section-label {
        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: rgba(255, 255, 255, 0.4);
        margin-bottom: 0.5rem;
    }

    .department-badge {
        display: inline-block;
        padding: 0.35rem 0.75rem;

        background: rgba(0, 200, 255, 0.15);
        color: #00c8ff;
        border-radius: 6px;

        font-size: 0.8rem;
        font-weight: 500;
        text-transform: capitalize;
    }

    .menu-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        width: 100%;
        padding: 0.75rem 1rem;

        background: none;
        border: none;

        color: rgba(255, 255, 255, 0.8);
        font-size: 0.875rem;
        text-align: left;
        cursor: pointer;

        transition: all 0.15s ease;
    }

    .menu-item:hover {
        background: rgba(255, 255, 255, 0.08);
        color: #fff;
    }

    .menu-item.logout {
        color: rgba(255, 100, 100, 0.8);
    }

    .menu-item.logout:hover {
        background: rgba(255, 100, 100, 0.1);
        color: #ff6464;
    }

    .item-icon {
        font-size: 1rem;
        width: 20px;
        text-align: center;
    }
</style>
