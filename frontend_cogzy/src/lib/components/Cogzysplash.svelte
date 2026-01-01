<script lang="ts">
    import { onMount } from 'svelte';
    
    let email = '';
    let password = '';
    let error = '';
    let loading = false;
    let isLogin = true; // toggle between login/register
    
    // Generate matrix rain particles
    const particles = Array.from({ length: 50 }, (_, i) => ({
      id: i,
      left: Math.random() * 100,
      top: Math.random() * 100,
      height: 20 + Math.random() * 80,
      duration: 2 + Math.random() * 3,
      delay: Math.random() * 2,
    }));
    
    async function handleEmailAuth() {
      if (!email) {
        error = 'Email is required';
        return;
      }
      
      loading = true;
      error = '';
      
      try {
        const endpoint = isLogin 
          ? '/api/personal/auth/login' 
          : '/api/personal/auth/register';
        
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ email, password }),
        });
        
        const data = await res.json();
        
        if (!res.ok) {
          error = data.detail || data.error || 'Authentication failed';
          return;
        }
        
        // Success - redirect to chat
        window.location.href = '/';
      } catch (err) {
        error = 'Connection failed. Please try again.';
      } finally {
        loading = false;
      }
    }
    
    async function handleGoogleAuth() {
      loading = true;
      try {
        const res = await fetch('/api/personal/auth/google');
        const data = await res.json();
        
        if (data.url) {
          // Store state for CSRF validation
          sessionStorage.setItem('oauth_state', data.state);
          window.location.href = data.url;
        }
      } catch (err) {
        error = 'Failed to connect to Google';
        loading = false;
      }
    }
  </script>
  
  <div class="splash-container">
    <!-- Matrix rain background -->
    <div class="matrix-rain">
      {#each particles as p (p.id)}
        <div 
          class="particle"
          style="
            left: {p.left}%;
            top: {p.top}%;
            height: {p.height}px;
            animation-duration: {p.duration}s;
            animation-delay: {p.delay}s;
          "
        />
      {/each}
    </div>
    
    <!-- Subtle grid overlay -->
    <div class="grid-overlay" />
    
    <!-- Main card -->
    <div class="auth-card">
      <!-- Logo -->
      <div class="logo-container">
        <div class="logo-wrapper">
          <svg width="100" height="100" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
            <!-- Filters -->
            <defs>
              <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
              <linearGradient id="neonGreen" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#00ff88"/>
                <stop offset="100%" stop-color="#00cc66"/>
              </linearGradient>
              <linearGradient id="neonCyan" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#00ffff"/>
                <stop offset="100%" stop-color="#00cccc"/>
              </linearGradient>
            </defs>
            
            <!-- Outer cog ring -->
            <g filter="url(#glow)">
              <circle cx="60" cy="60" r="45" fill="none" stroke="url(#neonGreen)" stroke-width="3"/>
              
              <!-- Neural spikes (cog teeth) -->
              {#each Array(12) as _, i}
                {@const angle = (i * 30) * Math.PI / 180}
                {@const x1 = 60 + Math.cos(angle) * 42}
                {@const y1 = 60 + Math.sin(angle) * 42}
                {@const x2 = 60 + Math.cos(angle) * 54}
                {@const y2 = 60 + Math.sin(angle) * 54}
                {@const cx = 60 + Math.cos(angle + 0.1) * 48}
                {@const cy = 60 + Math.sin(angle + 0.1) * 48}
                <path
                  d="M {x1} {y1} Q {cx} {cy} {x2} {y2}"
                  stroke="url(#neonGreen)"
                  stroke-width="4"
                  stroke-linecap="round"
                  fill="none"
                />
              {/each}
              
              <!-- Inner ring -->
              <circle cx="60" cy="60" r="32" fill="none" stroke="url(#neonGreen)" stroke-width="2" opacity="0.6"/>
            </g>
            
            <!-- Brain hemispheres -->
            <g filter="url(#glow)">
              <!-- Left hemisphere -->
              <path
                d="M 45 50 C 38 50 35 55 35 62 C 35 72 42 78 50 78 C 52 78 54 77 56 76 L 56 44 C 54 43 52 42 50 42 C 46 42 45 46 45 50"
                fill="none"
                stroke="url(#neonCyan)"
                stroke-width="2.5"
                stroke-linecap="round"
              />
              <!-- Left brain folds -->
              <path d="M 40 55 Q 45 58 40 62" fill="none" stroke="url(#neonCyan)" stroke-width="1.5" opacity="0.8"/>
              <path d="M 42 66 Q 48 68 44 72" fill="none" stroke="url(#neonCyan)" stroke-width="1.5" opacity="0.8"/>
              
              <!-- Right hemisphere -->
              <path
                d="M 75 50 C 82 50 85 55 85 62 C 85 72 78 78 70 78 C 68 78 66 77 64 76 L 64 44 C 66 43 68 42 70 42 C 74 42 75 46 75 50"
                fill="none"
                stroke="url(#neonCyan)"
                stroke-width="2.5"
                stroke-linecap="round"
              />
              <!-- Right brain folds -->
              <path d="M 80 55 Q 75 58 80 62" fill="none" stroke="url(#neonCyan)" stroke-width="1.5" opacity="0.8"/>
              <path d="M 78 66 Q 72 68 76 72" fill="none" stroke="url(#neonCyan)" stroke-width="1.5" opacity="0.8"/>
              
              <!-- Center connection -->
              <line x1="56" y1="60" x2="64" y2="60" stroke="url(#neonGreen)" stroke-width="2"/>
              <circle cx="60" cy="60" r="2" fill="#00ff88"/>
              
              <!-- Neural circuit nodes -->
              <circle cx="48" cy="52" r="1.5" fill="#00ffff" opacity="0.8"/>
              <circle cx="72" cy="52" r="1.5" fill="#00ffff" opacity="0.8"/>
              <circle cx="46" cy="68" r="1.5" fill="#00ffff" opacity="0.8"/>
              <circle cx="74" cy="68" r="1.5" fill="#00ffff" opacity="0.8"/>
            </g>
          </svg>
          
          <!-- Pulse ring -->
          <div class="pulse-ring" />
        </div>
        
        <!-- Brand name -->
        <h1 class="brand-name">COGZY</h1>
        <p class="tagline">YOUR COGNITIVE TWIN</p>
      </div>
      
      <!-- Sign in text -->
      <p class="sign-in-text">
        {isLogin ? 'Sign in to continue' : 'Create your account'}
      </p>
      
      <!-- Auth form -->
      <form on:submit|preventDefault={handleEmailAuth} class="auth-form">
        <input
          type="email"
          bind:value={email}
          placeholder="you@example.com"
          class="input-field"
          disabled={loading}
        />
        
        <input
          type="password"
          bind:value={password}
          placeholder="Password"
          class="input-field"
          disabled={loading}
        />
        
        <button type="submit" class="btn-primary" disabled={loading}>
          {#if loading}
            Connecting...
          {:else}
            {isLogin ? 'Sign In' : 'Create Account'}
          {/if}
        </button>
      </form>
      
      <!-- Toggle login/register -->
      <button class="toggle-auth" on:click={() => isLogin = !isLogin}>
        {isLogin ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
      </button>
      
      <!-- Divider -->
      <div class="divider">
        <span>or</span>
      </div>
      
      <!-- Google auth -->
      <button class="btn-google" on:click={handleGoogleAuth} disabled={loading}>
        <svg width="18" height="18" viewBox="0 0 18 18">
          <path fill="#4285F4" d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 0 0 2.38-5.88c0-.57-.05-.66-.15-1.18z"/>
          <path fill="#34A853" d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2.01c-.71.48-1.63.77-2.7.77-2.08 0-3.84-1.4-4.47-3.29H1.83v2.07A8 8 0 0 0 8.98 17z"/>
          <path fill="#FBBC05" d="M4.51 10.53c-.16-.48-.25-.99-.25-1.53s.09-1.05.25-1.53V5.4H1.83a8 8 0 0 0 0 7.18l2.68-2.05z"/>
          <path fill="#EA4335" d="M8.98 4.18c1.17 0 2.23.4 3.06 1.2l2.3-2.3A8 8 0 0 0 1.83 5.4L4.5 7.47c.64-1.89 2.4-3.29 4.48-3.29z"/>
        </svg>
        Continue with Google
      </button>
      
      <!-- Error display -->
      {#if error}
        <div class="error-box">
          {error}
        </div>
      {/if}
      
      <!-- Footer -->
      <p class="footer-text">
        Memory that persists. Context that matters.
      </p>
    </div>
  </div>
  
  <style>
    .splash-container {
      min-height: 100vh;
      background: #0a0a0f;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1rem;
      position: relative;
      overflow: hidden;
    }
    
    /* Matrix rain */
    .matrix-rain {
      position: absolute;
      inset: 0;
      opacity: 0.2;
      pointer-events: none;
    }
    
    .particle {
      position: absolute;
      width: 1px;
      background: linear-gradient(to bottom, transparent, #00ff88, transparent);
      animation: fall linear infinite;
    }
    
    @keyframes fall {
      0% { transform: translateY(-100%); opacity: 0; }
      10% { opacity: 1; }
      90% { opacity: 1; }
      100% { transform: translateY(100vh); opacity: 0; }
    }
    
    /* Grid overlay */
    .grid-overlay {
      position: absolute;
      inset: 0;
      opacity: 0.05;
      background-image: 
        linear-gradient(rgba(0,255,136,0.3) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,255,136,0.3) 1px, transparent 1px);
      background-size: 50px 50px;
      pointer-events: none;
    }
    
    /* Main card */
    .auth-card {
      position: relative;
      z-index: 10;
      width: 100%;
      max-width: 400px;
      background: linear-gradient(135deg, rgba(15,20,25,0.95) 0%, rgba(10,15,20,0.98) 100%);
      border: 1px solid rgba(0,255,136,0.2);
      border-radius: 16px;
      box-shadow: 
        8px 8px 0px rgba(0,0,0,0.8),
        0 0 40px rgba(0,255,136,0.1),
        inset 0 1px 0 rgba(255,255,255,0.05);
      padding: 48px 40px;
    }
    
    /* Logo section */
    .logo-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      margin-bottom: 2rem;
    }
    
    .logo-wrapper {
      position: relative;
    }
    
    .pulse-ring {
      position: absolute;
      inset: -10px;
      border: 2px solid rgba(0,255,136,0.3);
      border-radius: 50%;
      animation: pulse 2s ease-in-out infinite;
    }
    
    @keyframes pulse {
      0%, 100% { transform: scale(1); opacity: 0.3; }
      50% { transform: scale(1.1); opacity: 0; }
    }
    
    .brand-name {
      margin-top: 1.5rem;
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: 0.15em;
      color: #00ff88;
      text-shadow: 0 0 20px rgba(0,255,136,0.5), 3px 3px 0px #000;
    }
    
    .tagline {
      margin-top: 0.5rem;
      font-size: 10px;
      letter-spacing: 0.25em;
      color: rgba(0,255,255,0.7);
      text-transform: uppercase;
    }
    
    .sign-in-text {
      text-align: center;
      color: #9ca3af;
      font-size: 0.875rem;
      margin-bottom: 1.5rem;
    }
    
    /* Form */
    .auth-form {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    
    .input-field {
      width: 100%;
      padding: 0.75rem 1rem;
      border-radius: 8px;
      background: rgba(0,0,0,0.4);
      border: 1px solid rgba(0,255,136,0.3);
      box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);
      color: white;
      font-size: 1rem;
      transition: all 0.2s;
    }
    
    .input-field::placeholder {
      color: #6b7280;
    }
    
    .input-field:focus {
      outline: none;
      border-color: rgba(0,255,136,0.6);
      box-shadow: inset 0 2px 4px rgba(0,0,0,0.3), 0 0 10px rgba(0,255,136,0.2);
    }
    
    .input-field:disabled {
      opacity: 0.5;
    }
    
    /* Buttons */
    .btn-primary {
      width: 100%;
      padding: 0.75rem;
      border-radius: 8px;
      border: none;
      background: linear-gradient(135deg, #00ff88 0%, #00cc66 100%);
      color: black;
      font-weight: 600;
      font-size: 1rem;
      cursor: pointer;
      box-shadow: 4px 4px 0px rgba(0,0,0,0.8), 0 0 20px rgba(0,255,136,0.3);
      transition: transform 0.1s;
    }
    
    .btn-primary:hover:not(:disabled) {
      transform: scale(1.02);
    }
    
    .btn-primary:active:not(:disabled) {
      transform: scale(0.98);
    }
    
    .btn-primary:disabled {
      opacity: 0.7;
      cursor: not-allowed;
    }
    
    .toggle-auth {
      background: none;
      border: none;
      color: rgba(0,255,136,0.7);
      font-size: 0.75rem;
      cursor: pointer;
      margin-top: 0.5rem;
      width: 100%;
      text-align: center;
    }
    
    .toggle-auth:hover {
      color: #00ff88;
      text-decoration: underline;
    }
    
    /* Divider */
    .divider {
      display: flex;
      align-items: center;
      gap: 1rem;
      margin: 1.5rem 0;
    }
    
    .divider::before,
    .divider::after {
      content: '';
      flex: 1;
      height: 1px;
      background: linear-gradient(to right, transparent, #4b5563, transparent);
    }
    
    .divider span {
      color: #6b7280;
      font-size: 0.75rem;
    }
    
    /* Google button */
    .btn-google {
      width: 100%;
      padding: 0.75rem;
      border-radius: 8px;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
      color: white;
      font-weight: 500;
      font-size: 1rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.75rem;
      box-shadow: 4px 4px 0px rgba(0,0,0,0.5);
      transition: transform 0.1s;
    }
    
    .btn-google:hover:not(:disabled) {
      transform: scale(1.02);
    }
    
    .btn-google:active:not(:disabled) {
      transform: scale(0.98);
    }
    
    .btn-google:disabled {
      opacity: 0.7;
      cursor: not-allowed;
    }
    
    /* Error box */
    .error-box {
      margin-top: 1rem;
      padding: 0.75rem;
      border-radius: 8px;
      background: rgba(255,50,50,0.1);
      border: 1px solid rgba(255,50,50,0.3);
      color: #ff6666;
      font-size: 0.875rem;
      text-align: center;
    }
    
    /* Footer */
    .footer-text {
      margin-top: 2rem;
      text-align: center;
      font-size: 0.75rem;
      color: #4b5563;
    }
  </style>