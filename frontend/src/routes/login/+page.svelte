<script lang="ts">
    import { goto } from '$app/navigation';
    import { personalAuthStore, isAuthenticated } from '$lib/stores/personalAuth';

    let email = '';
    let password = '';
    let isRegister = false;
    let displayName = '';
    let loading = false;
    let message = '';
    let error = '';

    // Redirect if already logged in
    $: if ($isAuthenticated) {
        goto('/');
    }

    async function handleSubmit() {
        loading = true;
        error = '';
        message = '';

        if (isRegister) {
            const result = await personalAuthStore.register(email, password, displayName || undefined);
            if (result.success) {
                message = result.message || 'Registration successful!';
                isRegister = false;  // Switch to login view
            } else {
                error = result.error || 'Registration failed';
            }
        } else {
            const result = await personalAuthStore.login(email, password);
            if (result.success) {
                goto('/');
            } else {
                error = result.error || 'Login failed';
            }
        }

        loading = false;
    }

    function handleGoogleLogin() {
        personalAuthStore.startGoogleLogin();
    }
</script>

<div class="min-h-screen flex items-center justify-center bg-gray-900 px-4">
    <div class="max-w-md w-full space-y-8">
        <!-- Header -->
        <div class="text-center">
            <h1 class="text-3xl font-bold text-white">CogTwin</h1>
            <p class="mt-2 text-gray-400">Your cognitive memory system</p>
        </div>

        <!-- Card -->
        <div class="bg-gray-800 rounded-xl shadow-xl p-8">
            <h2 class="text-xl font-semibold text-white mb-6">
                {isRegister ? 'Create Account' : 'Sign In'}
            </h2>

            <!-- Google Button -->
            <button
                on:click={handleGoogleLogin}
                class="w-full flex items-center justify-center gap-3 px-4 py-3
                       bg-white text-gray-800 rounded-lg font-medium
                       hover:bg-gray-100 transition-colors"
            >
                <svg class="w-5 h-5" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
            </button>

            <!-- Divider -->
            <div class="relative my-6">
                <div class="absolute inset-0 flex items-center">
                    <div class="w-full border-t border-gray-700"></div>
                </div>
                <div class="relative flex justify-center text-sm">
                    <span class="px-2 bg-gray-800 text-gray-500">or</span>
                </div>
            </div>

            <!-- Email Form -->
            <form on:submit|preventDefault={handleSubmit} class="space-y-4">
                {#if isRegister}
                    <div>
                        <label for="displayName" class="block text-sm font-medium text-gray-300">
                            Name (optional)
                        </label>
                        <input
                            type="text"
                            id="displayName"
                            bind:value={displayName}
                            class="mt-1 block w-full px-4 py-3 bg-gray-700 border border-gray-600
                                   rounded-lg text-white placeholder-gray-400
                                   focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            placeholder="Your name"
                        />
                    </div>
                {/if}

                <div>
                    <label for="email" class="block text-sm font-medium text-gray-300">
                        Email
                    </label>
                    <input
                        type="email"
                        id="email"
                        bind:value={email}
                        required
                        class="mt-1 block w-full px-4 py-3 bg-gray-700 border border-gray-600
                               rounded-lg text-white placeholder-gray-400
                               focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        placeholder="you@example.com"
                    />
                </div>

                <div>
                    <label for="password" class="block text-sm font-medium text-gray-300">
                        Password
                    </label>
                    <input
                        type="password"
                        id="password"
                        bind:value={password}
                        required
                        minlength="8"
                        class="mt-1 block w-full px-4 py-3 bg-gray-700 border border-gray-600
                               rounded-lg text-white placeholder-gray-400
                               focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        placeholder="Min 8 characters"
                    />
                </div>

                {#if error}
                    <div class="bg-red-900/50 border border-red-500 rounded-lg p-3">
                        <p class="text-red-400 text-sm">{error}</p>
                    </div>
                {/if}

                {#if message}
                    <div class="bg-green-900/50 border border-green-500 rounded-lg p-3">
                        <p class="text-green-400 text-sm">{message}</p>
                    </div>
                {/if}

                <button
                    type="submit"
                    disabled={loading}
                    class="w-full px-4 py-3 bg-blue-600 text-white rounded-lg font-medium
                           hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
                           transition-colors"
                >
                    {#if loading}
                        <span class="inline-flex items-center gap-2">
                            <span class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                            {isRegister ? 'Creating account...' : 'Signing in...'}
                        </span>
                    {:else}
                        {isRegister ? 'Create Account' : 'Sign In'}
                    {/if}
                </button>
            </form>

            <!-- Toggle Register/Login -->
            <p class="mt-6 text-center text-sm text-gray-400">
                {#if isRegister}
                    Already have an account?
                    <button
                        on:click={() => { isRegister = false; error = ''; message = ''; }}
                        class="text-blue-400 hover:underline"
                    >
                        Sign in
                    </button>
                {:else}
                    Don't have an account?
                    <button
                        on:click={() => { isRegister = true; error = ''; message = ''; }}
                        class="text-blue-400 hover:underline"
                    >
                        Create one
                    </button>
                {/if}
            </p>

            {#if !isRegister}
                <p class="mt-2 text-center">
                    <a href="/forgot-password" class="text-sm text-gray-500 hover:text-gray-400">
                        Forgot password?
                    </a>
                </p>
            {/if}
        </div>
    </div>
</div>
