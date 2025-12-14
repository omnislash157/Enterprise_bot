# Railway Deployment Spec Sheet - Enterprise Bot

**Last Updated:** December 9, 2024
**Project:** Enterprise_bot (Driscoll chatbot)
**Status:** Deployed

---

## URLs

| Service | URL |
|---------|-----|
| Backend API | `https://lucky-love-production.up.railway.app` |
| Frontend UI | `https://[your-frontend-url].up.railway.app` |
| GitHub Repo | `https://github.com/omnislash157/Enterprise_bot` |

---

## Service Configuration

### Backend Service

**Source:**
- Repo: `omnislash157/Enterprise_bot`
- Branch: `main`
- Root Directory: `/` (empty/default)

**Build:**
- Builder: Nixpacks (auto-detected Python)
- Reads from: `requirements.txt`, `runtime.txt`

**Deploy:**
- Procfile: `web: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Networking:**
- Public domain: `lucky-love-production.up.railway.app`
- Port: 8080 (Railway maps internally)

**Variables:**
| Variable | Value | Required |
|----------|-------|----------|
| `XAI_API_KEY` | `xai-xxxx...` | YES |
| `COGTWIN_CONFIG` | `config.yaml` | YES |
| `ANTHROPIC_API_KEY` | (optional) | No |

---

### Frontend Service

**Source:**
- Repo: `omnislash157/Enterprise_bot` (same repo)
- Branch: `main`
- Root Directory: `/frontend`

**Build:**
- Build Command: `npm install && npm run build`
- Builder: Nixpacks (auto-detected Node.js)

**Deploy:**
- Start Command: `node build`

**Networking:**
- Public domain: Generate one in Settings → Networking
- Port: 8080

**Variables:**
| Variable | Value | Required |
|----------|-------|----------|
| `VITE_API_URL` | `https://lucky-love-production.up.railway.app` | YES |

---

## Required Files (in repo)

### `/Procfile`
```
web: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### `/runtime.txt`
```
python-3.11.9
```

### `/requirements.txt`
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-dotenv>=1.0.0
pydantic>=2.5.0
httpx>=0.25.0
python-docx>=1.0.0
PyYAML>=6.0
numpy>=1.24.0
faiss-cpu>=1.7.4
openai>=1.0.0
anthropic>=0.18.0
```

### `/frontend/svelte.config.js`
```javascript
import adapter from '@sveltejs/adapter-node';

export default {
  kit: {
    adapter: adapter()
  }
};
```

**Note:** Uses `@sveltejs/adapter-node@1.3.1` (compatible with SvelteKit 1.x)

---

## Common Errors & Fixes

### Error: `ModuleNotFoundError: No module named 'app'`
**Cause:** Procfile path wrong
**Fix:** Change Procfile to:
```
web: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Error: `Application failed to respond`
**Cause:** Usually wrong start command or port
**Fix:** 
- Backend: Use Procfile with `$PORT`
- Frontend: Use `node build` not `vite preview`

### Error: `ERESOLVE unable to resolve dependency tree`
**Cause:** Package version mismatch
**Fix:** For SvelteKit 1.x, use:
```
npm install @sveltejs/adapter-node@1.3.1
```

### Error: `src refspec main does not match any`
**Cause:** Nothing committed yet
**Fix:**
```bash
git add .
git commit -m "message"
git branch -M main
git push -u origin main
```

### Error: `Repository not found`
**Cause:** Case-sensitive URL or repo doesn't exist
**Fix:** Check exact URL at github.com, match case exactly:
```bash
git remote remove origin
git remote add origin https://github.com/EXACT/URL.git
```

### Variables disappeared
**Cause:** Unknown (Railway bug?)
**Fix:** Re-add them manually in Variables tab. Each service has its own variables.

---

## Deploy Commands (Local → Railway)

```powershell
cd C:\Users\mthar\projects\enterprise_bot

# Make changes, then:
git add .
git commit -m "Description of change"
git push

# Railway auto-deploys on push
```

---

## Rollback

In Railway dashboard:
1. Click service
2. Go to **Deployments**
3. Find previous working deployment
4. Click **⋮** menu → **Rollback**

---

## Logs

1. Click service in Railway dashboard
2. Click **Deployments** tab
3. Click on a deployment
4. Click **View Logs**

Or click the **Observability** tab for live logs.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      RAILWAY                             │
│                                                          │
│  ┌──────────────────┐      ┌──────────────────┐        │
│  │ Frontend Service │      │ Backend Service  │        │
│  │ (SvelteKit/Node) │ ───► │ (FastAPI/Python) │        │
│  │                  │      │                  │        │
│  │ adapter-node     │      │ uvicorn          │        │
│  │ port 8080        │      │ port 8080        │        │
│  └──────────────────┘      └────────┬─────────┘        │
│                                      │                  │
└──────────────────────────────────────┼──────────────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │   Grok API      │
                              │   (xAI)         │
                              └─────────────────┘
```

---

## Local vs Production

| Setting | Local (Windows) | Production (Railway) |
|---------|-----------------|----------------------|
| Backend cmd | `.venv311\Scripts\python.exe -m uvicorn backend.app.main:app --port 8001` | `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Frontend cmd | `npm run dev` | `node build` |
| Backend port | 8001 | $PORT (dynamic) |
| Frontend port | 5173 | $PORT (dynamic) |
| API URL | `http://localhost:8001` | `https://lucky-love-production.up.railway.app` |
| Env vars | `.env` file | Railway Variables tab |

---

## Quick Recovery Checklist

If deployment breaks:

- [ ] Check logs for actual error
- [ ] Verify Variables still exist (both services)
- [ ] Check Procfile syntax
- [ ] Verify requirements.txt is clean (no `agi_engine` etc)
- [ ] Check frontend svelte.config.js has `adapter-node`
- [ ] Try rollback to previous deployment
- [ ] Re-push: `git commit --allow-empty -m "trigger redeploy" && git push`

---

## Costs

| Usage | Estimated Cost |
|-------|----------------|
| Low (demo) | ~$5/month |
| Moderate | ~$10-20/month |
| Heavy | ~$20-50/month |

Railway bills by CPU/memory usage, not fixed tiers.

---

*Keep this file - you WILL need it again.*
