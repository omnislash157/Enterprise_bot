# Frontend - SvelteKit File Tree

Cold start reference for AI agents. SvelteKit + Tailwind + Threlte (Three.js).

**Last Updated**: 2025-12-23 (Post-Observability Suite & Voice Integration)

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
    │   ├── +layout.svelte             # Root layout - ribbon, providers, ConnectionStatus
    │   ├── +page.svelte               # Home page - chat interface
    │   │
    │   ├── credit/                    # CREDIT DEPARTMENT TOOLS
    │   │   └── +page.svelte           # Credit form - customer lookup, AR
    │   │
    │   ├── admin/                     # ADMIN DASHBOARD
    │   │   ├── +layout.svelte         # Admin nav sidebar
    │   │   ├── +page.svelte           # Admin home - nerve center, stats
    │   │   │
    │   │   ├── users/
    │   │   │   └── +page.svelte       # User management - CRUD, roles, batch import
    │   │   │
    │   │   ├── analytics/
    │   │   │   └── +page.svelte       # Analytics charts, metrics
    │   │   │
    │   │   ├── audit/
    │   │   │   └── +page.svelte       # Audit log viewer
    │   │   │
    │   │   │── # OBSERVABILITY PAGES (Phase 2 - 2025-12-23) ──────────
    │   │   │
    │   │   ├── system/
    │   │   │   └── +page.svelte       # System health, metrics panels
    │   │   │
    │   │   ├── traces/
    │   │   │   └── +page.svelte       # Distributed tracing viewer
    │   │   │
    │   │   ├── logs/
    │   │   │   └── +page.svelte       # Structured logs viewer
    │   │   │
    │   │   └── alerts/
    │   │       └── +page.svelte       # Alert rules, history
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
        │   ├── session.ts             # Chat session, messages, WebSocket, connectionState
        │   ├── websocket.ts           # WebSocket connection manager with reconnect
        │   ├── admin.ts               # Admin data, users list, roles
        │   ├── analytics.ts           # Analytics data, charts
        │   ├── observability.ts       # Observability data - metrics, traces, logs, alerts
        │   ├── metrics.ts             # System metrics collection
        │   ├── credit.ts              # Credit form state, AR data
        │   ├── config.ts              # Runtime config, feature flags
        │   ├── voice.ts               # Voice transcription state (Deepgram)
        │   ├── cheeky.ts              # Cheeky status phrases
        │   ├── artifacts.ts           # Artifact rendering state
        │   ├── panels.ts              # Panel visibility toggles
        │   ├── workspaces.ts          # Workspace tabs
        │   └── theme.ts               # Dark/light theme
        │
        ├── components/                # SVELTE COMPONENTS
        │   │
        │   ├── Login.svelte           # Login page - Azure SSO button
        │   ├── ChatOverlay.svelte     # Main chat interface, messages, voice button
        │   ├── ConnectionStatus.svelte # Connection status banner with reconnect
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
        │   ├── nervecenter/
        │   │   └── StateMonitor.svelte # Real-time state monitor
        │   │
        │   ├── admin/                 # ADMIN COMPONENTS
        │   │   ├── UserRow.svelte     # User table row, actions
        │   │   ├── CreateUserModal.svelte # Create user form
        │   │   ├── RoleModal.svelte   # Role assignment modal
        │   │   ├── AccessModal.svelte # Department access modal
        │   │   ├── BatchImportModal.svelte # Bulk user import (CSV upload)
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
        │   │   ├── observability/     # OBSERVABILITY PANELS (Phase 2)
        │   │   │   ├── SystemHealthPanel.svelte # Health checks, uptime
        │   │   │   ├── RagPerformancePanel.svelte # RAG metrics, latency
        │   │   │   └── LlmCostPanel.svelte # LLM cost tracking
        │   │   │
        │   │   └── threlte/           # 3D NERVE CENTER (Three.js)
        │   │       ├── NerveCenterScene.svelte # Scene container
        │   │       ├── NeuralNetwork.svelte    # Network visualization
        │   │       ├── NeuralNode.svelte       # Single node
        │   │       └── DataSynapse.svelte      # Connection line
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
        │       ├── AgentNode.svelte
        │       ├── ConnectionLines.svelte
        │       ├── MemoryNode.svelte
        │       └── MemorySpace.svelte
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
import { observabilityStore } from '$lib/stores/observability';

// Subscribe to state
$authStore.user  // Current user
$sessionStore.messages  // Chat messages
$sessionStore.connectionState  // Connection status: connected|reconnecting|disconnected
$observabilityStore.metrics  // System metrics
```

### WebSocket Chat with Reconnection
```typescript
// WebSocket handles real-time chat with automatic reconnection
import { websocketStore } from '$lib/stores/websocket';

websocketStore.send({ type: 'chat', message: '...' });

// Connection state tracked in session store
$sessionStore.connectionState  // 'connected' | 'reconnecting' | 'disconnected'
```

### Voice Transcription (Deepgram)
```typescript
// Voice store manages Deepgram WebSocket for real-time STT
import { voiceStore } from '$lib/stores/voice';

voiceStore.start();  // Begin recording
voiceStore.stop();   // End recording
$voiceStore.transcript  // Real-time transcript
$voiceStore.isRecording  // Recording state
```

### Session Persistence
```typescript
// Session persisted to localStorage with TTL
import { sessionStore } from '$lib/stores/session';

// Automatic persistence on state changes
sessionStore.restoreSession();  // On app load
sessionStore.clearSession();    // On logout
```

### Routing
- `/` - Main chat interface
- `/credit` - Credit department tools
- `/admin` - Admin dashboard (requires admin role)
- `/admin/users` - User management with batch import
- `/admin/analytics` - Usage analytics
- `/admin/audit` - Audit logs
- `/admin/system` - System health & metrics *(new)*
- `/admin/traces` - Distributed tracing *(new)*
- `/admin/logs` - Structured logs viewer *(new)*
- `/admin/alerts` - Alert rules & history *(new)*

### Auth Flow
1. User clicks "Sign in with Microsoft"
2. Redirects to Azure AD
3. Returns to `/auth/callback`
4. Token validated, user loaded
5. Redirect to home

### Observability Data Flow
```typescript
// Observability store aggregates metrics, traces, logs, alerts
import { observabilityStore } from '$lib/stores/observability';

await observabilityStore.fetchMetrics();
await observabilityStore.fetchTraces(filters);
await observabilityStore.fetchLogs(query);
await observabilityStore.fetchAlerts();
```

## Component Architecture

### Main Chat Interface
- **ChatOverlay.svelte** - Primary chat UI
  - Message rendering with streaming
  - Voice button for STT (Deepgram)
  - Department selector
  - Cognitive state display

### Admin Portal
- **Admin Layout** - Sidebar navigation
- **Users Page** - CRUD + batch CSV import
- **Analytics Page** - Chart.js visualizations
- **Audit Page** - Compliance log viewer
- **System Page** - Health panels (SystemHealthPanel, RagPerformancePanel, LlmCostPanel)
- **Traces Page** - Distributed tracing UI
- **Logs Page** - Structured log search
- **Alerts Page** - Alert rules management

### 3D Visualizations
- **Nerve Center** - Three.js neural network
  - NerveCenterScene.svelte - Container
  - NeuralNetwork.svelte - Graph layout
  - NeuralNode.svelte - Individual nodes
  - DataSynapse.svelte - Edge connections

### Connection Resilience
- **ConnectionStatus.svelte** - Banner component
  - Displays connection state
  - Reconnect button
  - Exponential backoff retry logic

## Recent Major Changes (2025-12-21 to 2025-12-23)

### Phase 2 Observability Suite
- New admin pages: `/admin/traces`, `/admin/logs`, `/admin/alerts`
- `observabilityStore` for metrics aggregation
- Observability panels: SystemHealthPanel, RagPerformancePanel, LlmCostPanel
- Real-time metrics streaming

### Voice Transcription (Deepgram)
- `voiceStore` for real-time STT
- Mic button in ChatOverlay.svelte
- WebSocket bridge to Deepgram API
- Transcript streaming to chat

### Session Persistence & Reconnect
- localStorage session management with TTL
- ConnectionStatus.svelte banner component
- Automatic reconnection with exponential backoff
- Connection state tracking in session store

### Bulk User Import
- BatchImportModal.svelte - CSV upload UI
- Integrated into `/admin/users` page
- User provisioning with division access

### Admin Navigation Updates
- New dropdown items for Traces/Logs/Alerts
- System health dashboard
- Enhanced metrics visualization

### Type Safety Improvements
- Division IDs standardized to strings
- Connection state enum typing
- WebSocket message type definitions

## Store Dependencies

```
auth.ts → Core authentication state
  ├─> session.ts → Chat session + connection state
  │     ├─> websocket.ts → WebSocket connection manager
  │     └─> voice.ts → Deepgram voice transcription
  │
  ├─> admin.ts → Admin data (users, roles)
  │     └─> analytics.ts → Usage analytics
  │
  ├─> observability.ts → System observability
  │     └─> metrics.ts → Metrics collection
  │
  └─> config.ts → Runtime configuration

theme.ts → UI theme (independent)
credit.ts → Credit form state (independent)
cheeky.ts → Status phrases (independent)
artifacts.ts → Artifact rendering (independent)
panels.ts → Panel visibility (independent)
workspaces.ts → Workspace tabs (independent)
```

## Key Libraries

- **SvelteKit** - Framework (file-based routing, SSR)
- **Threlte** - Three.js for Svelte (3D visualizations)
- **Chart.js** - Analytics charts
- **Tailwind CSS** - Utility-first styling
- **TypeScript** - Type safety

## Build & Deploy

```bash
npm install          # Install dependencies
npm run dev          # Dev server (port 5173)
npm run build        # Production build
npm run preview      # Preview production build
```

## Environment Variables

```bash
PUBLIC_API_URL=https://cogtwin.up.railway.app
PUBLIC_AZURE_CLIENT_ID=...
PUBLIC_AZURE_TENANT_ID=...
# Voice features require backend DEEPGRAM_API_KEY
```

## Performance Optimizations

- **Code Splitting** - Route-based automatic splitting
- **Lazy Loading** - Chart.js loaded on-demand
- **WebSocket Pooling** - Connection reuse with warmup
- **LocalStorage Caching** - Session persistence reduces backend calls
- **Debounced Search** - Search inputs debounced 300ms
- **Virtual Scrolling** - Large lists (logs, traces) virtualized
