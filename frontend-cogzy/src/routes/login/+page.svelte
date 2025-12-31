<script lang="ts">
    import { goto } from '$app/navigation';

    const API_URL = import.meta.env.VITE_API_URL || '';

    let email = '';
    let password = '';
    let isLogin = true;
    let loading = false;
    let error = '';

    function loginGoogle() {
        window.location.href = `${API_URL}/api/personal/auth/google`;
    }

    async function handleEmailAuth() {
        loading = true;
        error = '';

        const endpoint = isLogin ? 'login' : 'register';

        try {
            const res = await fetch(`${API_URL}/api/personal/auth/${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ email, password })
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || 'Authentication failed');
            }

            goto('/');
        } catch (e) {
            error = e instanceof Error ? e.message : 'Something went wrong';
        } finally {
            loading = false;
        }
    }
</script>

<div class="login-container">
    <div class="login-card">
        <div class="logo-section">
            <img src="/cogzy-logo.svg" alt="Cogzy" class="logo" />
            <h1>Cogzy</h1>
            <p class="tagline">Your cognitive companion</p>
        </div>

        {#if error}
            <div class="error">{error}</div>
        {/if}

        <div class="auth-section">
            <button class="auth-btn google" on:click={loginGoogle}>
                <svg class="icon" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
            </button>

            <div class="divider">
                <span>or</span>
            </div>

            <form on:submit|preventDefault={handleEmailAuth}>
                <input
                    type="email"
                    bind:value={email}
                    placeholder="Email address"
                    required
                />
                <input
                    type="password"
                    bind:value={password}
                    placeholder="Password"
                    required
                    minlength="8"
                />
                <button type="submit" class="auth-btn email" disabled={loading}>
                    {loading ? 'Loading...' : (isLogin ? 'Sign In' : 'Create Account')}
                </button>
            </form>

            <button class="toggle-mode" on:click={() => isLogin = !isLogin}>
                {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
            </button>
        </div>

        <div class="enterprise-link">
            <p>Enterprise SSO?</p>
            <a href="/enterprise">Sign in with your organization</a>
        </div>
    </div>
</div>

<style>
    .login-container {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    }

    .login-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 20px;
        padding: 3rem;
        max-width: 420px;
        width: 90%;
    }

    .logo-section {
        text-align: center;
        margin-bottom: 2rem;
    }

    .logo {
        width: 72px;
        height: 72px;
        margin-bottom: 1rem;
    }

    h1 {
        color: white;
        font-size: 2rem;
        margin: 0;
        background: linear-gradient(135deg, #8b5cf6, #6366f1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .tagline {
        color: rgba(255,255,255,0.5);
        margin: 0.5rem 0 0;
    }

    .error {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #fca5a5;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        font-size: 0.875rem;
    }

    .auth-section {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .auth-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        padding: 0.875rem 1.5rem;
        border-radius: 10px;
        font-size: 1rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        border: none;
        width: 100%;
    }

    .auth-btn .icon {
        width: 20px;
        height: 20px;
    }

    .auth-btn.google {
        background: white;
        color: #333;
    }

    .auth-btn.google:hover {
        background: #f5f5f5;
        transform: translateY(-1px);
    }

    .auth-btn.email {
        background: linear-gradient(135deg, #8b5cf6, #6366f1);
        color: white;
    }

    .auth-btn.email:hover:not(:disabled) {
        filter: brightness(1.1);
        transform: translateY(-1px);
    }

    .auth-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    .divider {
        display: flex;
        align-items: center;
        gap: 1rem;
        color: rgba(255,255,255,0.3);
        font-size: 0.875rem;
    }

    .divider::before,
    .divider::after {
        content: '';
        flex: 1;
        height: 1px;
        background: rgba(255,255,255,0.1);
    }

    form {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    input {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 0.875rem 1rem;
        color: white;
        font-size: 1rem;
        transition: border-color 0.2s;
    }

    input::placeholder {
        color: rgba(255,255,255,0.4);
    }

    input:focus {
        outline: none;
        border-color: #8b5cf6;
    }

    .toggle-mode {
        background: none;
        border: none;
        color: rgba(255,255,255,0.5);
        font-size: 0.875rem;
        cursor: pointer;
        padding: 0.5rem;
    }

    .toggle-mode:hover {
        color: white;
    }

    .enterprise-link {
        margin-top: 2rem;
        padding-top: 1.5rem;
        border-top: 1px solid rgba(255,255,255,0.1);
        text-align: center;
    }

    .enterprise-link p {
        color: rgba(255,255,255,0.4);
        font-size: 0.875rem;
        margin: 0 0 0.5rem;
    }

    .enterprise-link a {
        color: #8b5cf6;
        text-decoration: none;
        font-size: 0.875rem;
    }

    .enterprise-link a:hover {
        text-decoration: underline;
    }
</style>
