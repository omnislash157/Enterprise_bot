<script lang="ts">
    export let tenantName: string;
    export let logo: string | undefined;
    export let primaryColor: string | undefined;
    export let showAzureAd: boolean = false;
    export let showGoogle: boolean = false;
    export let showEmail: boolean = false;

    const API_URL = import.meta.env.VITE_API_URL || '';

    function loginAzure() {
        window.location.href = `${API_URL}/api/auth/azure/login`;
    }

    function loginGoogle() {
        window.location.href = `${API_URL}/api/auth/google/login`;
    }
</script>

<div class="login-container" style="--primary: {primaryColor || '#6366f1'}">
    <div class="login-card">
        {#if logo}
            <img src={logo} alt="{tenantName} logo" class="logo" />
        {/if}

        <h1>{tenantName}</h1>
        <p class="subtitle">Sign in to continue</p>

        <div class="auth-buttons">
            {#if showAzureAd}
                <button class="auth-btn azure" on:click={loginAzure}>
                    <svg class="icon" viewBox="0 0 23 23">
                        <path fill="currentColor" d="M11 0H0v11h11V0zm12 0H12v11h11V0zM11 12H0v11h11V12zm12 0H12v11h11V12z"/>
                    </svg>
                    Sign in with Microsoft
                </button>
            {/if}

            {#if showGoogle}
                <button class="auth-btn google" on:click={loginGoogle}>
                    <svg class="icon" viewBox="0 0 24 24">
                        <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                        <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                        <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                        <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                    </svg>
                    Sign in with Google
                </button>
            {/if}

            {#if showEmail}
                <a href="/login/email" class="auth-btn email">
                    <svg class="icon" viewBox="0 0 24 24">
                        <path fill="currentColor" d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
                    </svg>
                    Sign in with Email
                </a>
            {/if}
        </div>
    </div>
</div>

<style>
    .login-container {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
    }

    .login-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px;
        padding: 3rem;
        text-align: center;
        max-width: 400px;
        width: 90%;
    }

    .logo {
        width: 64px;
        height: 64px;
        margin-bottom: 1.5rem;
    }

    h1 {
        color: white;
        font-size: 1.75rem;
        margin: 0 0 0.5rem;
    }

    .subtitle {
        color: rgba(255,255,255,0.6);
        margin: 0 0 2rem;
    }

    .auth-buttons {
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
        border-radius: 8px;
        font-size: 1rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        text-decoration: none;
        border: none;
    }

    .auth-btn .icon {
        width: 20px;
        height: 20px;
    }

    .auth-btn.azure {
        background: var(--primary);
        color: white;
    }

    .auth-btn.azure:hover {
        filter: brightness(1.1);
    }

    .auth-btn.google {
        background: white;
        color: #333;
    }

    .auth-btn.google:hover {
        background: #f5f5f5;
    }

    .auth-btn.email {
        background: rgba(255,255,255,0.1);
        color: white;
        border: 1px solid rgba(255,255,255,0.2);
    }

    .auth-btn.email:hover {
        background: rgba(255,255,255,0.15);
    }
</style>
