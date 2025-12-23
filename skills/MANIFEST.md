# 🎯 SKILLS MANIFEST
**Always in context. Load full docs on demand.**

---

## 📚 INDEX (20-token max descriptions)

| ID | Skill | Description | When to Use |
|----|-------|-------------|-------------|
| **T1** | sdk-tools | SDK tool decorator, async, MCP server setup | Tool import fails, decorator errors |
| **T2** | railway | Railway GraphQL API, deploy, logs, env vars | Deploy issues, need service status |
| **T3** | postgres | PostgreSQL queries, psycopg2, schema ops | Database queries, table operations |
| **T4** | memory-rag | FAISS vector, BM25 grep, episodic, squirrel | Search memory, retrieve context |
| **T5** | grok | Grok-beta via OpenAI client, streaming, cheap | Fast/cheap LLM needs, fallback |
| **T6** | claude-sdk | Agent options, streaming, tool permissions | Configure Claude SDK agent |

---

## ⚡ INLINE PATTERNS
**Memorize these - no file read needed for 80% of cases**

### SDK Tool Pattern
```python
@tool(
    name="tool_name",
    description="What it does",
    input_schema={"param": str}
)
async def tool_name(args: dict) -> dict:
    result = do_work(args["param"])
    return {"content": [{"type": "text", "text": str(result)}]}
```

### Database
```python
# Execute SQL
db_query({"query": "SELECT * FROM table", "limit": 100})
→ {columns: [...], rows: [...], execution_time_ms: 42}

# List tables
db_tables({"schema": "enterprise"})
→ {tables: [{name, size, estimated_rows, column_count}]}

# Schema
db_describe({"table": "users", "schema": "enterprise"})
→ {columns: [...], indexes: [...], row_count: 1000}
```

### Memory RAG
```python
# Unified search (all lanes)
memory_search({"query": "Railway deploy", "lanes": "all"})
→ {vector: {...}, grep: {...}, episodic: {...}, squirrel: {...}}

# Vector search (semantic)
memory_vector({"query": "async patterns", "top_k": 10})
→ {results: [{id, score, human_content, assistant_content, timestamp}]}

# Recent session
memory_squirrel({"hours_back": 2, "search": "database"})
→ {items: [{timestamp, content, type}]}
```

### Railway
```python
# List services
railway_services({"project_id": "optional"})
→ {services: [{id, name, updated_at}], environments: [...]}

# Logs
railway_logs({"service_name": "backend", "lines": 100})
→ {logs: [...], deployment_id, deployment_status}

# Status
railway_status({"service_name": "backend"})
→ {current_status, last_deploy, recent_deployments: [...]}
```

### Grok API
```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

response = client.chat.completions.create(
    model="grok-beta",
    messages=[{"role": "user", "content": "..."}],
    stream=True
)
```

---

## 📖 LOAD FULL DOCUMENTATION

### From filesystem:
```bash
cat skills/T1_sdk-tools.md
cat skills/T2_railway.md
cat skills/T3_postgres.md
cat skills/T4_memory-rag.md
cat skills/T5_grok.md
cat skills/T6_claude-sdk.md
```

### From zip:
```bash
unzip -p skills.zip T1_sdk-tools.md | head -200
```

---

## 🔧 ENVIRONMENT VARIABLES

```bash
# Railway (for T2)
RAILWAY_TOKEN=rxxx...
RAILWAY_PROJECT_ID=xxx-xxx-xxx

# Database (for T3)
AZURE_PG_HOST=cogtwin.postgres.database.azure.com
AZURE_PG_USER=mhartigan
AZURE_PG_PASSWORD=xxx
AZURE_PG_DATABASE=postgres
AZURE_PG_PORT=5432
AZURE_PG_SSLMODE=require

# Memory/Embeddings (for T4)
DEEPINFRA_API_KEY=xxx

# Grok (for T5)
XAI_API_KEY=xai-xxx

# Claude (for T6)
ANTHROPIC_API_KEY=sk-ant-xxx
```

---

## 🎯 USAGE STRATEGY

1. **MANIFEST always in context** (~500 tokens)
2. **Check inline patterns first** (80% of cases covered)
3. **Load full doc on demand** when needed
4. **Skills auto-loaded from .env** (python-dotenv)

---

## 📊 TOKEN BUDGET

| Component | Tokens | Strategy |
|-----------|--------|----------|
| MANIFEST.md | ~500 | Always present |
| Inline patterns | ~300 | Memorized |
| Full skill doc | ~2000 | On-demand |
| **Total persistent** | **~800** | **vs 12K for all docs** |

**Savings: 93% token reduction with lazy loading**

---

## 🚀 QUICK REFERENCE

**Tool broken?** → Load T1 (sdk-tools)
**Deploy failing?** → Load T2 (railway)
**Query syntax?** → Load T3 (postgres)
**Search memory?** → Use inline patterns (T4)
**Need cheap LLM?** → Use inline patterns (T5)

---

*Version: 1.0 | Last updated: 2024-12-22 | Auto-generated via recursive self-improvement*
