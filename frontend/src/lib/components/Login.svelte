<script lang="ts">
    import { auth, authLoading, azureEnabled } from '$lib/stores/auth';

    let email = '';
    let error = '';
    let showEmailLogin = false;

    async function handleMicrosoftLogin() {
        await auth.loginWithMicrosoft();
    }

    async function handleEmailLogin() {
        if (!email.includes('@')) {
            error = 'Please enter a valid email';
            return;
        }

        error = '';
        const success = await auth.login(email);

        if (!success) {
            // Error is set in store, but we can also show locally
            auth.subscribe(s => {
                if (s.error) error = s.error;
            })();
        }
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === 'Enter') {
            handleEmailLogin();
        }
    }
</script>

<div class="login-container">
    <div class="login-card">
        <div class="logo">
            <span class="logo-icon">◈</span>
            <h1>Driscoll Intelligence</h1>
        </div>

        <p class="subtitle">Sign in to continue</p>

        {#if $azureEnabled}
            <!-- Microsoft SSO Button -->
            <button
                class="microsoft-btn"
                on:click={handleMicrosoftLogin}
                disabled={$authLoading}
            >
                <svg viewBox="0 0 21 21" width="21" height="21">
                    <rect x="1" y="1" width="9" height="9" fill="#f25022"/>
                    <rect x="11" y="1" width="9" height="9" fill="#7fba00"/>
                    <rect x="1" y="11" width="9" height="9" fill="#00a4ef"/>
                    <rect x="11" y="11" width="9" height="9" fill="#ffb900"/>
                </svg>
                {$authLoading ? 'Signing in...' : 'Sign in with Microsoft'}
            </button>

            <!-- Divider -->
            <div class="divider">
                <span>or</span>
            </div>

            <!-- Toggle for email login -->
            {#if !showEmailLogin}
                <button
                    class="text-btn"
                    on:click={() => showEmailLogin = true}
                    type="button"
                >
                    Sign in with email instead
                </button>
            {/if}
        {/if}

        {#if !$azureEnabled || showEmailLogin}
            <!-- Email Login Form -->
            <form on:submit|preventDefault={handleEmailLogin}>
                <div class="input-group">
                    <input
                        type="email"
                        bind:value={email}
                        placeholder="you@driscollfoods.com"
                        disabled={$authLoading}
                        on:keydown={handleKeydown}
                        autocomplete="email"
                    />
                </div>

                <button type="submit" disabled={$authLoading || !email} class="primary-btn">
                    {$authLoading ? 'Signing in...' : 'Sign In'}
                </button>
            </form>

            {#if $azureEnabled && showEmailLogin}
                <button
                    class="text-btn"
                    on:click={() => { showEmailLogin = false; error = ''; }}
                    type="button"
                >
                    Back to Microsoft login
                </button>
            {/if}
        {/if}

        {#if error}
            <p class="error">{error}</p>
        {/if}

        <p class="hint">
            {#if $azureEnabled}
                Enterprise SSO enabled
            {:else}
                Allowed domains: driscollfoods.com
            {/if}
        </p>
    </div>
</div>

<style>
    .login-container {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #0f0f1a 100%);
        padding: 1rem;
    }

    .login-card {
        width: 100%;
        max-width: 420px;
        padding: 2.5rem;
        background: rgba(10, 10, 10, 0.9);
        border: 1px solid rgba(0, 255, 65, 0.2);
        border-radius: 16px;
        box-shadow:
            0 0 40px rgba(0, 255, 65, 0.1),
            inset 0 0 60px rgba(0, 255, 65, 0.02);
        text-align: center;
    }

    .logo {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        margin-bottom: 0.5rem;
    }

    .logo-icon {
        font-size: 2rem;
        color: #00ff41;
        text-shadow: 0 0 15px #00ff41;
    }

    h1 {
        font-size: 1.5rem;
        font-weight: 600;
        color: #e0e0e0;
        margin: 0;
        letter-spacing: 0.5px;
    }

    .subtitle {
        color: #888;
        margin: 1rem 0 2rem 0;
        font-size: 0.95rem;
    }

    /* Microsoft Button */
    .microsoft-btn {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        padding: 0.875rem 1.5rem;
        background: white;
        border: 1px solid #8c8c8c;
        border-radius: 10px;
        color: #5e5e5e;
        font-size: 1rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        font-family: inherit;
    }

    .microsoft-btn:hover:not(:disabled) {
        background: #f3f3f3;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }

    .microsoft-btn:active:not(:disabled) {
        transform: translateY(1px);
    }

    .microsoft-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    /* Divider */
    .divider {
        margin: 1.5rem 0;
        text-align: center;
        position: relative;
    }

    .divider::before {
        content: '';
        position: absolute;
        top: 50%;
        left: 0;
        right: 0;
        height: 1px;
        background: rgba(136, 136, 136, 0.3);
    }

    .divider span {
        position: relative;
        padding: 0 1rem;
        background: rgba(10, 10, 10, 0.9);
        color: #666;
        font-size: 0.85rem;
    }

    /* Form */
    form {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .input-group {
        width: 100%;
    }

    input {
        width: 100%;
        padding: 1rem 1.25rem;
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(0, 255, 65, 0.3);
        border-radius: 10px;
        color: #e0e0e0;
        font-size: 1rem;
        font-family: inherit;
        transition: border-color 0.2s, box-shadow 0.2s;
        box-sizing: border-box;
    }

    input:focus {
        outline: none;
        border-color: #00ff41;
        box-shadow: 0 0 20px rgba(0, 255, 65, 0.2);
    }

    input::placeholder {
        color: #555;
    }

    input:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    /* Primary Button (Email login) */
    .primary-btn {
        width: 100%;
        padding: 1rem;
        background: #00ff41;
        border: none;
        border-radius: 10px;
        color: #000;
        font-size: 1rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }

    .primary-btn:hover:not(:disabled) {
        box-shadow: 0 0 25px rgba(0, 255, 65, 0.5);
        transform: translateY(-1px);
    }

    .primary-btn:active:not(:disabled) {
        transform: translateY(0);
    }

    .primary-btn:disabled {
        background: #333;
        color: #666;
        cursor: not-allowed;
    }

    /* Text Button (toggle) */
    .text-btn {
        background: none;
        border: none;
        color: #00ff41;
        font-size: 0.9rem;
        cursor: pointer;
        padding: 0.5rem;
        margin-top: 0.5rem;
        transition: color 0.2s;
    }

    .text-btn:hover {
        color: #00cc33;
        text-decoration: underline;
    }

    /* Error */
    .error {
        color: #ff4444;
        margin-top: 1rem;
        font-size: 0.9rem;
        padding: 0.75rem;
        background: rgba(255, 68, 68, 0.1);
        border: 1px solid rgba(255, 68, 68, 0.3);
        border-radius: 8px;
    }

    /* Hint */
    .hint {
        color: #555;
        font-size: 0.8rem;
        margin-top: 2rem;
        margin-bottom: 0;
    }
</style>
