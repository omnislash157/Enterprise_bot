<script lang="ts">
	import { auth, authError, authLoading } from '$lib/stores/auth';
	
	let email = '';
	let password = '';
	let mode: 'login' | 'signup' | 'magic' = 'login';
	let message = '';
	
	async function handleSubmit() {
		message = '';
		
		if (mode === 'login') {
			const result = await auth.signIn(email, password);
			if (!result.success) {
				message = result.error || 'Login failed';
			}
		} else if (mode === 'signup') {
			const result = await auth.signUp(email, password);
			if (result.success) {
				message = 'Check your email to confirm your account';
				mode = 'login';
			} else {
				message = result.error || 'Signup failed';
			}
		} else if (mode === 'magic') {
			const result = await auth.signInWithMagicLink(email);
			if (result.success) {
				message = 'Check your email for a login link';
			} else {
				message = result.error || 'Failed to send magic link';
			}
		}
	}
</script>

<div class="login-container">
	<div class="login-card">
		<div class="logo">
			<span class="logo-icon">🧠</span>
			<h1>CogTwin</h1>
		</div>
		
		<p class="subtitle">
			{#if mode === 'login'}
				Sign in to your workspace
			{:else if mode === 'signup'}
				Create your account
			{:else}
				Sign in with email link
			{/if}
		</p>
		
		<form on:submit|preventDefault={handleSubmit}>
			<div class="field">
				<label for="email">Email</label>
				<input
					id="email"
					type="email"
					bind:value={email}
					placeholder="you@company.com"
					required
				/>
			</div>
			
			{#if mode !== 'magic'}
				<div class="field">
					<label for="password">Password</label>
					<input
						id="password"
						type="password"
						bind:value={password}
						placeholder="••••••••"
						required
					/>
				</div>
			{/if}
			
			{#if message}
				<div class="message" class:error={$authError}>
					{message}
				</div>
			{/if}
			
			<button type="submit" class="submit-btn" disabled={$authLoading}>
				{#if $authLoading}
					<span class="spinner"></span>
				{:else if mode === 'login'}
					Sign In
				{:else if mode === 'signup'}
					Create Account
				{:else}
					Send Magic Link
				{/if}
			</button>
		</form>
		
		<div class="mode-switch">
			{#if mode === 'login'}
				<button on:click={() => mode = 'signup'}>Create account</button>
				<span>•</span>
				<button on:click={() => mode = 'magic'}>Use magic link</button>
			{:else if mode === 'signup'}
				<button on:click={() => mode = 'login'}>Back to sign in</button>
			{:else}
				<button on:click={() => mode = 'login'}>Back to sign in</button>
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
		background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
		padding: 1rem;
	}
	
	.login-card {
		background: rgba(30, 30, 50, 0.9);
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 12px;
		padding: 2.5rem;
		width: 100%;
		max-width: 400px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
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
	}
	
	.logo h1 {
		font-size: 1.75rem;
		font-weight: 600;
		color: #e0e0e0;
		margin: 0;
	}
	
	.subtitle {
		text-align: center;
		color: #888;
		margin-bottom: 2rem;
		font-size: 0.95rem;
	}
	
	.field {
		margin-bottom: 1.25rem;
	}
	
	.field label {
		display: block;
		color: #aaa;
		font-size: 0.85rem;
		margin-bottom: 0.5rem;
	}
	
	.field input {
		width: 100%;
		padding: 0.75rem 1rem;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(255, 255, 255, 0.15);
		border-radius: 8px;
		color: #e0e0e0;
		font-size: 1rem;
		transition: border-color 0.2s, background 0.2s;
	}
	
	.field input:focus {
		outline: none;
		border-color: #00ff88;
		background: rgba(255, 255, 255, 0.08);
	}
	
	.field input::placeholder {
		color: #666;
	}
	
	.message {
		padding: 0.75rem 1rem;
		border-radius: 8px;
		margin-bottom: 1rem;
		font-size: 0.9rem;
		background: rgba(0, 255, 136, 0.1);
		color: #00ff88;
		border: 1px solid rgba(0, 255, 136, 0.2);
	}
	
	.message.error {
		background: rgba(255, 100, 100, 0.1);
		color: #ff6b6b;
		border-color: rgba(255, 100, 100, 0.2);
	}
	
	.submit-btn {
		width: 100%;
		padding: 0.875rem 1rem;
		background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
		border: none;
		border-radius: 8px;
		color: #1a1a2e;
		font-size: 1rem;
		font-weight: 600;
		cursor: pointer;
		transition: transform 0.2s, box-shadow 0.2s;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
	}
	
	.submit-btn:hover:not(:disabled) {
		transform: translateY(-1px);
		box-shadow: 0 4px 12px rgba(0, 255, 136, 0.3);
	}
	
	.submit-btn:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}
	
	.spinner {
		width: 18px;
		height: 18px;
		border: 2px solid #1a1a2e;
		border-top-color: transparent;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	
	@keyframes spin {
		to { transform: rotate(360deg); }
	}
	
	.mode-switch {
		margin-top: 1.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		font-size: 0.85rem;
	}
	
	.mode-switch button {
		background: none;
		border: none;
		color: #00ff88;
		cursor: pointer;
		font-size: inherit;
		padding: 0;
	}
	
	.mode-switch button:hover {
		text-decoration: underline;
	}
	
	.mode-switch span {
		color: #555;
	}
</style>
