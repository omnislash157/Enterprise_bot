<script lang="ts">
    import { auth, authLoading, googleEnabled, authError } from '$lib/stores/auth';

    let email = '';
    let password = '';
    let confirmPassword = '';
    let displayName = '';
    let showEmailLogin = false;
    let isRegisterMode = false;
    let localError = '';

    async function handleGoogleLogin() {
        await auth.loginWithGoogle();
    }

    async function handleEmailLogin() {
        if (!email.includes('@')) {
            localError = 'Please enter a valid email';
            return;
        }

        if (!password) {
            localError = 'Please enter your password';
            return;
        }

        localError = '';
        await auth.login(email, password);
    }

    async function handleRegister() {
        if (!email.includes('@')) {
            localError = 'Please enter a valid email';
            return;
        }

        if (password.length < 8) {
            localError = 'Password must be at least 8 characters';
            return;
        }

        if (password !== confirmPassword) {
            localError = 'Passwords do not match';
            return;
        }

        localError = '';
        const success = await auth.register(email, password, displayName || undefined);

        if (success) {
            // Switch to login mode
            isRegisterMode = false;
            localError = '';
            password = '';
            confirmPassword = '';
        }
    }

    function toggleMode() {
        isRegisterMode = !isRegisterMode;
        localError = '';
        auth.clearError();
        password = '';
        confirmPassword = '';
    }

    function toggleEmailLogin() {
        showEmailLogin = !showEmailLogin;
        localError = '';
        auth.clearError();
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === 'Enter') {
            if (isRegisterMode) {
                handleRegister();
            } else {
                handleEmailLogin();
            }
        }
    }

    $: displayError = localError || $authError;
</script>

<div class="login-container">
    <div class="login-card">
        <div class="logo">
            <span class="logo-icon">◈</span>
            <h1>Cogzy</h1>
        </div>

        <p class="subtitle">
            {isRegisterMode ? 'Create your account' : 'Sign in to continue'}
        </p>

        {#if $googleEnabled && !showEmailLogin}
            <!-- Google OAuth Button (Primary) -->
            <button
                class="google-btn"
                on:click={handleGoogleLogin}
                disabled={$authLoading}
            >
                <svg viewBox="0 0 24 24" width="24" height="24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                {$authLoading ? 'Signing in...' : 'Continue with Google'}
            </button>

            <!-- Divider -->
            <div class="divider">
                <span>or</span>
            </div>

            <!-- Toggle for email login -->
            <button
                class="text-btn"
                on:click={toggleEmailLogin}
                type="button"
            >
                Sign in with email instead
            </button>
        {:else}
            <!-- Email Login/Register Form -->
            <form on:submit|preventDefault={isRegisterMode ? handleRegister : handleEmailLogin}>
                {#if isRegisterMode}
                    <div class="input-group">
                        <input
                            type="text"
                            bind:value={displayName}
                            placeholder="Display name (optional)"
                            disabled={$authLoading}
                            autocomplete="name"
                        />
                    </div>
                {/if}

                <div class="input-group">
                    <input
                        type="email"
                        bind:value={email}
                        placeholder="you@gmail.com"
                        disabled={$authLoading}
                        on:keydown={handleKeydown}
                        autocomplete="email"
                    />
                </div>

                <div class="input-group">
                    <input
                        type="password"
                        bind:value={password}
                        placeholder="Password"
                        disabled={$authLoading}
                        on:keydown={handleKeydown}
                        autocomplete={isRegisterMode ? 'new-password' : 'current-password'}
                    />
                </div>

                {#if isRegisterMode}
                    <div class="input-group">
                        <input
                            type="password"
                            bind:value={confirmPassword}
                            placeholder="Confirm password"
                            disabled={$authLoading}
                            on:keydown={handleKeydown}
                            autocomplete="new-password"
                        />
                    </div>
                {/if}

                <button type="submit" disabled={$authLoading || !email || !password} class="primary-btn">
                    {#if $authLoading}
                        {isRegisterMode ? 'Creating account...' : 'Signing in...'}
                    {:else}
                        {isRegisterMode ? 'Create Account' : 'Sign In'}
                    {/if}
                </button>
            </form>

            <!-- Toggle register/login -->
            <button
                class="text-btn"
                on:click={toggleMode}
                type="button"
            >
                {isRegisterMode ? 'Already have an account? Sign in' : "Don't have an account? Register"}
            </button>

            {#if $googleEnabled}
                <button
                    class="text-btn"
                    on:click={toggleEmailLogin}
                    type="button"
                >
                    Back to Google sign in
                </button>
            {/if}
        {/if}

        {#if displayError}
            <p class="error">{displayError}</p>
        {/if}

        <p class="hint">Your cognitive companion</p>
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

    /* Google Button */
    .google-btn {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        padding: 0.875rem 1.5rem;
        background: white;
        border: 1px solid #dadce0;
        border-radius: 10px;
        color: #3c4043;
        font-size: 1rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        font-family: inherit;
    }

    .google-btn:hover:not(:disabled) {
        background: #f8f9fa;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }

    .google-btn:active:not(:disabled) {
        transform: translateY(1px);
    }

    .google-btn:disabled {
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

    /* Primary Button */
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

    /* Text Button */
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
