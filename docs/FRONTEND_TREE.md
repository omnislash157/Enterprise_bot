# Frontend - SvelteKit File Tree

Cold start reference for AI agents. SvelteKit + Tailwind + Threlte (Three.js).

**Last Updated**: 2025-12-31

Two frontend apps:
- **frontend/** - Enterprise (driscollintel.com) - Full admin suite, Azure SSO
- **frontend-cogzy/** - Personal SaaS (Cogzy) - Email/password + Google OAuth

---

## frontend/ (Enterprise)

```
frontend/
|
+-- package.json                       # Dependencies: svelte, threlte, chart.js
+-- svelte.config.js                   # SvelteKit adapter config
+-- tailwind.config.js                 # Tailwind theme, colors
+-- postcss.config.js                  # PostCSS for Tailwind
+-- tsconfig.json                      # TypeScript config
|
+-- src/
    +-- app.html                       # HTML shell template
    +-- app.css                        # Global styles, Tailwind imports
    |
    +-- routes/                        # SVELTEKIT PAGES
    |   +-- +layout.svelte             # Root layout
    |   +-- +page.svelte               # Home - chat interface
    |   +-- login/+page.svelte         # Login page
    |   +-- credit/+page.svelte        # Credit form
    |   |
    |   +-- admin/                     # ADMIN DASHBOARD
    |   |   +-- +layout.svelte         # Admin nav sidebar
    |   |   +-- +page.svelte           # Admin home
    |   |   +-- users/+page.svelte     # User management
    |   |   +-- analytics/+page.svelte # Analytics charts
    |   |   +-- audit/+page.svelte     # Audit logs
    |   |   +-- queries/+page.svelte   # Query logs
    |   |   +-- system/+page.svelte    # System health
    |   |   +-- traces/+page.svelte    # Distributed tracing
    |   |   +-- logs/+page.svelte      # Structured logs
    |   |   +-- alerts/+page.svelte    # Alert rules
    |   |
    |   +-- auth/
    |       +-- callback/+page.svelte  # Azure SSO callback
    |       +-- google/callback/+page.svelte # Google OAuth
    |
    +-- lib/
        +-- stores/                    # STATE MANAGEMENT
        |   +-- auth.ts                # Azure SSO auth
        |   +-- personalAuth.ts        # Email/password auth
        |   +-- session.ts             # Chat session, WebSocket
        |   +-- websocket.ts           # WebSocket manager
        |   +-- tenant.ts              # Tenant context
        |   +-- admin.ts, analytics.ts, observability.ts
        |   +-- credit.ts, voice.ts, cheeky.ts, theme.ts
        |
        +-- components/
        |   +-- Login.svelte, EnterpriseLogin.svelte
        |   +-- ChatOverlay.svelte, ConnectionStatus.svelte
        |   +-- CreditForm.svelte, ToastProvider.svelte
        |   +-- ribbon/                # Top nav ribbon
        |   +-- admin/                 # Admin components
        |   |   +-- charts/            # Chart.js wrappers
        |   |   +-- observability/     # Health panels
        |   |   +-- threlte/           # 3D nerve center
        |
        +-- cheeky/                    # Status phrases
        +-- threlte/                   # 3D scene components
        +-- utils/                     # Helpers
```

---

## frontend-cogzy/ (Personal SaaS)

Minimal scaffold - shares backend but separate auth flow.

```
frontend-cogzy/
|
+-- package.json
+-- svelte.config.js
+-- tailwind.config.js
+-- postcss.config.js
+-- tsconfig.json
|
+-- src/
    +-- app.html
    +-- app.css
    |
    +-- routes/
    |   +-- +layout.svelte             # Root layout
    |   +-- +page.svelte               # Home - chat interface
    |   +-- login/+page.svelte         # Login (email/password + Google)
    |
    +-- lib/
        +-- stores/
            +-- auth.ts                # Personal auth (email/password, Google)
```

---

## Key Differences

| Feature | frontend/ (Enterprise) | frontend-cogzy/ (Personal) |
|---------|----------------------|---------------------------|
| Auth | Azure AD SSO | Email/password + Google OAuth |
| Admin Portal | Full suite | None |
| Credit Form | Yes | No |
| 3D Visualizations | Threlte/Three.js | None |
| Target Domain | driscollintel.com | app.cogzy.dev |

---

## Routing

### Enterprise (frontend/)
- `/` - Chat interface
- `/login` - Login page
- `/credit` - Credit tools
- `/admin/*` - Admin suite (users, analytics, audit, queries, system, traces, logs, alerts)

### Personal (frontend-cogzy/)
- `/` - Chat interface
- `/login` - Email/password + Google

---

## Build and Deploy

```bash
# Enterprise
cd frontend && npm install && npm run build

# Personal
cd frontend-cogzy && npm install && npm run build
```

Both deploy to Railway with domain-based routing via tenant middleware.
