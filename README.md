# Enterprise Bot (Driscoll Assistant)

Enterprise fork of CogTwin - a context-stuffing chatbot for company documentation.

## What It Does

Loads `.docx` files from `manuals/Driscoll/` and stuffs them into the LLM context window. Users ask questions, bot answers from the docs. No memory, no extraction, no agents - just fast, accurate answers from your documentation.

## Architecture

```
backend/
├── app/
│   ├── main.py          # FastAPI + WebSocket streaming
│   └── config.py        # Settings loader
├── enterprise_twin.py   # Chat engine (context stuffing)
├── enterprise_tenant.py # Tenant context (division-aware)
├── doc_loader.py        # DOCX loading + caching
├── model_adapter.py     # Grok/OpenAI/Anthropic abstraction
└── config.yaml          # Runtime config

frontend/
└── src/routes/+page.svelte  # Chat UI (Svelte + cyberpunk theme)

manuals/
└── Driscoll/
    ├── Warehouse/       # Division folders
    ├── HR/
    └── Shared/          # Accessible by all divisions
```

## Running Locally

```bash
# Backend
cd backend
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Deploying to Railway

1. Connect repo to Railway
2. Set branch to `elegant-borg`
3. Add env vars: `XAI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`
4. Railway auto-detects `Procfile`

## Future: Memory Tier (v2)

Infrastructure is stubbed for adding memory:
- `config.yaml` has `memory_enabled: false`
- Stores exist in `frontend/src/lib/stores/`
- `enterprise_twin.py` has `_memory_mode` flag

When ready, flip the flags and add the memory pipeline.
