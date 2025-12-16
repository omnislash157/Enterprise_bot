<script lang="ts">
    import { auth, authLoading } from '$lib/stores/auth';

    let email = '';
    let error = '';

    async function handleLogin() {
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
            handleLogin();
        }
    }
</script>

<div class="login-container">
    <div class="login-card">
        <div class="logo">
            <span class="logo-icon">◈</span>
            <h1>Driscoll Intelligence</h1>
        </div>

        <p class="subtitle">Enter your company email to continue</p>

        <form on:submit|preventDefault={handleLogin}>
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

            <button type="submit" disabled={$authLoading || !email}>
                {$authLoading ? 'Signing in...' : 'Sign In'}
            </button>
        </form>

        {#if error}
            <p class="error">{error}</p>
        {/if}

        <p class="hint">
            Allowed domains: driscollfoods.com
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

    button {
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

    button:hover:not(:disabled) {
        box-shadow: 0 0 25px rgba(0, 255, 65, 0.5);
        transform: translateY(-1px);
    }

    button:active:not(:disabled) {
        transform: translateY(0);
    }

    button:disabled {
        background: #333;
        color: #666;
        cursor: not-allowed;
    }

    .error {
        color: #ff4444;
        margin-top: 1rem;
        font-size: 0.9rem;
        padding: 0.75rem;
        background: rgba(255, 68, 68, 0.1);
        border: 1px solid rgba(255, 68, 68, 0.3);
        border-radius: 8px;
    }

    .hint {
        color: #555;
        font-size: 0.8rem;
        margin-top: 2rem;
        margin-bottom: 0;
    }
</style>
