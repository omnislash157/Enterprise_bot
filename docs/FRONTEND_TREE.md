# Frontend - SvelteKit File Tree

Cold start reference for AI agents. SvelteKit + Tailwind + Threlte (Three.js).

```
frontend/
│
├── package.json                       # Dependencies: svelte, threlte, chart.js
├── svelte.config.js                   # SvelteKit adapter config
├── vite.config.ts                     # Vite bundler config
├── tailwind.config.js                 # Tailwind theme, colors
├── postcss.config.js                  # PostCSS for Tailwind
├── tsconfig.json                      # TypeScript config
│
└── src/
    ├── app.html                       # HTML shell template
    ├── app.css                        # Global styles, Tailwind imports
    │
    ├── routes/                        # SVELTEKIT PAGES (file-based routing)
    │   ├── +layout.svelte             # Root layout - ribbon, providers
    │   ├── +page.svelte               # Home page - chat interface
    │   │
    │   ├── credit/                    # CREDIT DEPARTMENT TOOLS
    │   │   └── +page.svelte           # Credit form - customer lookup, AR
    │   │
    │   ├── admin/                     # ADMIN DASHBOARD
    │   │   ├── +layout.svelte         # Admin nav sidebar
    │   │   ├── +page.svelte           # Admin home - stats overview
    │   │   ├── users/
    │   │   │   └── +page.svelte       # User management - CRUD, roles
    │   │   ├── analytics/
    │   │   │   └── +page.svelte       # Analytics charts, metrics
    │   │   └── audit/
    │   │       └── +page.svelte       # Audit log viewer
    │   │
    │   ├── auth/
    │   │   └── callback/
    │   │       └── +page.svelte       # Azure SSO callback handler
    │   │
    │   └── archive/                   # (deprecated pages)
    │       └── *.svelteold
    │
    └── lib/                           # SHARED LIBRARY
        │
        ├── stores/                    # SVELTE STORES (state management)
        │   ├── index.ts               # Store exports barrel
        │   ├── auth.ts                # Auth state, user, token, Azure SSO
        │   ├── session.ts             # Chat session, messages, WebSocket
        │   ├── websocket.ts           # WebSocket connection manager
        │   ├── admin.ts               # Admin data, users list, roles
        │   ├── analytics.ts           # Analytics data, charts
        │   ├── credit.ts              # Credit form state, AR data
        │   ├── config.ts              # Runtime config, feature flags
        │   ├── cheeky.ts              # Cheeky status phrases
        │   ├── artifacts.ts           # Artifact rendering state
        │   ├── panels.ts              # Panel visibility toggles
        │   ├── workspaces.ts          # Workspace tabs
        │   └── theme.ts               # Dark/light theme
        │
        ├── components/                # SVELTE COMPONENTS
        │   │
        │   ├── Login.svelte           # Login page - Azure SSO button
        │   ├── ChatOverlay.svelte     # Main chat interface, messages
        │   ├── DepartmentSelector.svelte # Department dropdown
        │   ├── DupeOverrideModal.svelte # Duplicate handling modal
        │   ├── CreditForm.svelte      # Credit dept form - 50KB, complex
        │   ├── ToastProvider.svelte   # Toast notification system
        │   │
        │   ├── Cheeky*.svelte         # Cheeky status components
        │   │   ├── CheekyLoader.svelte    # Loading spinner with phrases
        │   │   ├── CheekyInline.svelte    # Inline status text
        │   │   └── CheekyToast.svelte     # Toast with personality
        │   │
        │   ├── ribbon/                # TOP NAVIGATION RIBBON
        │   │   ├── index.ts           # Barrel export
        │   │   ├── IntelligenceRibbon.svelte # Main ribbon container
        │   │   ├── NavLink.svelte     # Nav item component
        │   │   ├── UserMenu.svelte    # User dropdown (logout, settings)
        │   │   └── AdminDropdown.svelte # Admin tools dropdown
        │   │
        │   ├── admin/                 # ADMIN COMPONENTS
        │   │   ├── UserRow.svelte     # User table row, actions
        │   │   ├── CreateUserModal.svelte # Create user form
        │   │   ├── RoleModal.svelte   # Role assignment modal
        │   │   ├── AccessModal.svelte # Department access modal
        │   │   ├── BatchImportModal.svelte # Bulk user import
        │   │   ├── LoadingSkeleton.svelte # Loading placeholder
        │   │   │
        │   │   ├── charts/            # ANALYTICS CHARTS
        │   │   │   ├── chartTheme.ts  # Chart.js theme config
        │   │   │   ├── LineChart.svelte    # Line chart wrapper
        │   │   │   ├── BarChart.svelte     # Bar chart wrapper
        │   │   │   ├── DoughnutChart.svelte # Donut chart wrapper
        │   │   │   ├── StatCard.svelte     # Metric card
        │   │   │   ├── DateRangePicker.svelte # Date filter
        │   │   │   ├── ExportButton.svelte # CSV export
        │   │   │   ├── RealtimeSessions.svelte # Live session count
        │   │   │   └── NerveCenterWidget.svelte # 3D brain widget
        │   │   │
        │   │   └── threlte/           # 3D NERVE CENTER (Three.js)
        │   │       ├── NerveCenterScene.svelte # Scene container
        │   │       ├── NeuralNetwork.svelte    # Network visualization
        │   │       ├── NeuralNode.svelte       # Single node
        │   │       └── DataSynapse.svelte      # Connection line
        │   │
        │   ├── nervecenter/
        │   │   └── StateMonitor.svelte # Real-time state monitor
        │   │
        │   └── archive/               # (deprecated components)
        │
        ├── cheeky/                    # CHEEKY STATUS SYSTEM
        │   ├── index.ts               # Exports
        │   ├── CheekyStatus.ts        # Status state machine
        │   └── phrases.ts             # 500+ contextual phrases
        │
        ├── artifacts/
        │   └── registry.ts            # Artifact type registry
        │
        ├── threlte/                   # 3D SCENE COMPONENTS
        │   ├── Scene.svelte           # Main 3D scene
        │   ├── CoreBrain.svelte       # Rotating brain model
        │   ├── CreditAmbientOrbs.svelte # Ambient orb effects
        │   └── archive/               # (deprecated 3D)
        │
        ├── transitions/
        │   └── pageTransition.ts      # Page transition animation
        │
        └── utils/
            ├── clickOutside.ts        # Click outside directive
            └── csvExport.ts           # CSV download helper
```

## Key Patterns

### State Management
```typescript
// Stores are reactive Svelte stores
import { authStore } from '$lib/stores/auth';
import { sessionStore } from '$lib/stores/session';

// Subscribe to state
$authStore.user  // Current user
$sessionStore.messages  // Chat messages
```

### WebSocket Chat
```typescript
// WebSocket handles real-time chat
import { websocketStore } from '$lib/stores/websocket';

websocketStore.send({ type: 'chat', message: '...' });
```

### Routing
- `/` - Main chat interface
- `/credit` - Credit department tools
- `/admin` - Admin dashboard (requires admin role)
- `/admin/users` - User management
- `/admin/analytics` - Usage analytics
- `/admin/audit` - Audit logs

### Auth Flow
1. User clicks "Sign in with Microsoft"
2. Redirects to Azure AD
3. Returns to `/auth/callback`
4. Token validated, user loaded
5. Redirect to home
