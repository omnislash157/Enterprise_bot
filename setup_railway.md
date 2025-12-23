# Railway Setup Guide

## 🚂 Getting Railway API Credentials

Your Railway tools are SDK-ready but need two environment variables:
- `RAILWAY_TOKEN`
- `RAILWAY_PROJECT_ID`

---

## Step 1: Get Your Railway API Token

### Option A: Via Railway Dashboard (Recommended)
1. Go to https://railway.app
2. Log in to your account
3. Click your profile icon (top right)
4. Go to **Account Settings**
5. Click **Tokens** in left sidebar
6. Click **Create Token**
7. Give it a name (e.g., "enterprise-bot-sdk")
8. Copy the token (starts with something like `rxxx...`)

### Option B: Via Railway CLI (if installed)
```bash
railway login
railway whoami --token
```

---

## Step 2: Get Your Project ID

### Via Dashboard:
1. Go to https://railway.app
2. Open your project (e.g., "enterprise-bot")
3. Look at the URL: `https://railway.app/project/{PROJECT_ID}`
4. Copy the PROJECT_ID from the URL

### Via CLI:
```bash
railway status
# Look for "Project: <name> (<project-id>)"
```

---

## Step 3: Add to .env File

Edit `C:\Users\mthar\projects\enterprise_bot\.env` and add:

```bash
# Railway API
RAILWAY_TOKEN=your_token_here
RAILWAY_PROJECT_ID=your_project_id_here
```

**Example:**
```bash
RAILWAY_TOKEN=rxxx-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
RAILWAY_PROJECT_ID=abc123de-f456-7890-abcd-ef1234567890
```

---

## Step 4: Test It Works

```bash
cd claude_sdk_toolkit
python -c "
from __init___sdk import print_tool_inventory
print_tool_inventory()
"
```

You should see:
```
📦 RAILWAY (3/3 available) ✅
  ✅ railway_services
  ✅ railway_logs
  ✅ railway_status
```

---

## What You'll Be Able to Do

Once Railway tools are active, Claude can:
- 🔍 **List services** - See all deployed services in your project
- 📊 **Check status** - Get deployment status and health
- 📝 **Read logs** - Pull recent logs from services
- 🔄 **Redeploy** - Trigger redeployments (when we add that tool)
- ⚙️ **Manage env vars** - Get/set environment variables (when we add that tool)

All without leaving the conversation! 🎯

---

## Security Notes

- Railway tokens have **full access** to your account
- Keep them secret (never commit to git)
- The `.env` file is in `.gitignore` ✅
- Rotate tokens periodically for security
- Use separate tokens for different environments if needed

---

## Current Status

After adding credentials, you'll have:
- ✅ Memory tools (5/5) - ACTIVE
- ✅ Database tools (4/4) - ACTIVE
- ✅ Railway tools (3/3) - ACTIVE after setup

**Total: 12/12 tools operational** 🎉

---

## Troubleshooting

### Token doesn't work
- Make sure there are no spaces or quotes around the token in `.env`
- Check token hasn't expired (tokens don't expire by default, but can be revoked)
- Verify you copied the full token

### Project ID not found
- Double-check the URL or CLI output
- Make sure you're using the project ID, not the service ID
- Try listing projects: `railway projects`

### Still not loading
Restart your Python session after adding to `.env`:
```python
# The auto-loader runs on import
import importlib
import claude_sdk_toolkit
importlib.reload(claude_sdk_toolkit)
```

---

Need help? The toolkit will show helpful error messages if credentials are missing or invalid.
