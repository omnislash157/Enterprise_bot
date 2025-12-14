# Enterprise Bot - QuickStart Guide

**Forked from:** `cog_twin`
**Date:** December 9, 2024
**Status:** Dumb chatbot mode (all smart features OFF)

---

## What This Is

A clean fork of CogTwin with all cognitive features disabled. Ships as a "dumb" chatbot that loads Driscoll manuals into the context window.

```
CogTwin (your personal)     Enterprise Bot (Driscoll)
├── 22K+ memories           ├── Empty data/ (no memories)
├── 5 memory lanes          ├── Memory pipelines: OFF
├── Metacognitive mirror    ├── All cognitive: OFF
├── Port 8000               ├── Port 8001
└── Full experience         └── Manual-stuffed chatbot
```

---

## Quick Verification

```powershell
cd C:\Users\mthar\projects\enterprise_bot
C:\Users\mthar\projects\cog_twin\.venv311\Scripts\python.exe test_setup.py
```

Expected output:
- Mode: enterprise
- Memory Enabled: False
- Context Stuffing: True

---

## Setup (One Time)

### Option A: Use cog_twin's venv (Quick)

```powershell
cd C:\Users\mthar\projects\enterprise_bot
C:\Users\mthar\projects\cog_twin\.venv311\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8001
```

### Option B: Create dedicated venv (Cleaner)

```powershell
cd C:\Users\mthar\projects\enterprise_bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt  # or: pip install -e .
python -m uvicorn backend.app.main:app --reload --port 8001
```

---

## Running Both Systems

**Terminal 1 - Your CogTwin (port 8000):**
```powershell
cd C:\Users\mthar\projects\cog_twin
.venv311\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

**Terminal 2 - Enterprise Bot (port 8001):**
```powershell
cd C:\Users\mthar\projects\enterprise_bot
C:\Users\mthar\projects\cog_twin\.venv311\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8001
```

**Frontend:**
```powershell
cd C:\Users\mthar\projects\enterprise_bot\frontend
npm run dev -- --port 5174
```
(Use 5174 to not conflict with cog_twin frontend on 5173)

---

## Config Comparison

| Setting | CogTwin (Personal) | Enterprise Bot |
|---------|-------------------|----------------|
| `deployment.mode` | personal | enterprise |
| `deployment.tier` | full | basic |
| `features.memory_pipelines` | true | **false** |
| `features.context_stuffing` | false | **true** |
| `features.metacognitive_mirror` | true | **false** |
| Port | 8000 | 8001 |

---

## Key Files

```
enterprise_bot/
├── config.yaml              # ALL FEATURES OFF
├── config_loader.py         # Same code, reads config.yaml
├── enterprise_twin.py       # Switches to context-stuffing mode
├── doc_loader.py            # Loads DOCX files
├── data/                    # EMPTY (no memories)
├── manuals/Driscoll/        # 21 operational manuals
└── backend/app/main.py      # Same code, uses EnterpriseTwin
```

---

## Feature Flags Explained

```yaml
features:
  memory_pipelines: false     # No FAISS, no embedding, no recall
  context_stuffing: true      # Load docs into 2M token window
  metacognitive_mirror: false # No phase detection
  cognitive_profiler: false   # No user profiling
  evolution_engine: false     # No self-improvement
```

When `memory_pipelines: false`, the startup path in `main.py` creates:
- `EnterpriseTwin` instead of `CogTwin`
- Which uses `doc_loader.py` to stuff manuals into context
- No FAISS index loaded, no embeddings computed

---

## Upgrading to Pro Tier

When ready to enable memory for Driscoll execs:

1. Edit `config.yaml`:
```yaml
deployment:
  tier: pro                   # was: basic

features:
  memory_pipelines: true      # flip this ON
  context_stuffing: true      # keep both
```

2. Restart backend. Their conversations will start building memory organically.

---

## Troubleshooting

### "python-docx required"
```powershell
pip install python-docx
```

### Port 8001 already in use
```powershell
netstat -ano | findstr ":8001"
taskkill /F /PID <pid>
```

### Config not loading
Make sure you're in `enterprise_bot/` directory when running. The config loader looks for `config.yaml` in current working directory.

---

## API Endpoints

Same as CogTwin, but returns enterprise config:

```bash
curl http://localhost:8001/api/config
```
Returns:
```json
{
  "features": {
    "swarm_loop": false,
    "memory_space_3d": false,
    "chat_basic": true,
    "dark_mode": true,
    "analytics_dashboard": false
  },
  "tier": "basic",
  "mode": "enterprise",
  "memory_enabled": false
}
```

---

## Next Steps for Production

1. **Hosting**: Deploy to Railway/Render/Azure
2. **Auth**: Add domain validation (@driscollfoods.com)
3. **Usage Logging**: Track tokens per user
4. **Doc Refresh**: Hot-reload DOCX files
5. **Voice Tuning**: Customize corporate/troll voices

---

*Created: December 9, 2024*
*Strategy: Fork everything, flags off, ship dumb, add smart later*
