# Database Schema Index

**Database:** cogtwin.postgres.database.azure.com  
**Full Schema:** DATABASE_SCHEMA_MAP.md  
**Status:** FROZEN (see Commandments in full map)

---

## Quick Stats
- **Tables:** 22
- **Columns:** 319
- **Indexes:** 113
- **Foreign Keys:** 11

---

## ENTERPRISE SCHEMA (Driscoll)

| Table | Cols | Rows | Purpose |
|-------|------|------|---------|
| tenants | 10 | 2 | Multi-tenant config, Azure AD settings |
| users | 11 | 13 | Enterprise users (Azure AD auth) |
| documents | 40 | 169 | RAG chunks + dual embeddings |
| query_log | 29 | 42 | User queries + NLU analysis |
| analytics_events | 12 | 61 | User behavior events |
| audit_log | 14 | 15 | Security/admin audit trail |
| traces | 15 | 18 | Distributed tracing roots |
| trace_spans | 13 | 0 | Distributed tracing children |
| structured_logs | 15 | 22K | JSON logs (HIGH VOLUME) |
| alert_rules | 18 | 10 | Alert definitions |
| alerts | 13 | 0 | Triggered alerts (LEGACY) |
| alert_instances | 12 | 2 | Triggered alerts (CURRENT) |
| request_metrics | 11 | 0 | HTTP performance |
| llm_call_metrics | 16 | 0 | LLM API tracking |
| rag_metrics | 17 | 0 | RAG pipeline perf |
| cache_metrics | 8 | 0 | Redis/cache stats |
| system_metrics | 7 | 0 | System-level metrics |

---

## PERSONAL SCHEMA (Cogzy)

| Table | Cols | Rows | Purpose |
|-------|------|------|---------|
| users | 15 | 0 | Personal auth (Google/Email) |
| memory_nodes | 16 | 0 | Core memories + embeddings |
| episodes | 7 | 0 | Conversation summaries |
| conversation_chunks | 12 | 0 | Chunked convos + topics |
| canonical_tags | 8 | 0 | Tag hierarchy (self-ref) |

---

## Key Relationships

```
enterprise: tenants → users → [query_log, analytics_events, audit_log]
enterprise: alert_rules → [alerts, alert_instances]
enterprise: traces → trace_spans

personal: users → [memory_nodes, episodes]
personal: canonical_tags → canonical_tags (hierarchy)
```

---

## Vector Tables (ivfflat indexes)

| Table | Embedding Column | Dimension |
|-------|------------------|-----------|
| enterprise.documents | embedding | 1024 |
| enterprise.documents | synthetic_questions_embedding | 1024 |
| personal.memory_nodes | embedding | 1024 |
| personal.episodes | embedding | 1024 |
| personal.conversation_chunks | embedding | 1024 |
| personal.canonical_tags | embedding | 1024 |

---

## Usage

To see full table details:
> "Show me the enterprise.documents table"
> "What columns are in personal.users?"

Claude will load the relevant section from DATABASE_SCHEMA_MAP.md

---

**Last Updated:** 2025-12-30