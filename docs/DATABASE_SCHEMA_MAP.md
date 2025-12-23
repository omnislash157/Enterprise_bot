# Database Schema Map

**Last Updated:** 2025-12-23 16:30 UTC  
**Database:** cogtwin.postgres.database.azure.com  
**Extracted By:** SCHEMA_EXTRACTION.sql  

---

## Overview

| Schema | Tables | Purpose |
|--------|--------|---------|
| enterprise | 15 | Main application (auth, RAG, observability, metrics) |
| personal | 3 | User memory system (episodes, memory nodes) |
| cron | 2 | pg_cron job scheduling |
| public | - | Extensions only (pgvector functions) |

---

## Extensions

| Extension | Version | Purpose |
|-----------|---------|---------|
| vector | 0.8.0 | pgvector - embeddings & similarity search |
| pg_cron | 1.6 | Scheduled jobs |
| azure | 1.1 | Azure integration |
| pgaadauth | 1.9 | Azure AD authentication |
| plpgsql | 1.0 | PL/pgSQL |

---

## Schema: enterprise

### enterprise.users
Core user table for authentication.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | tenant_id | uuid | YES | | FK → tenants.id |
| 3 | email | varchar(255) | NO | | UNIQUE |
| 4 | display_name | varchar(255) | YES | | |
| 5 | azure_oid | varchar(255) | YES | | UNIQUE |
| 6 | department_access | varchar[] | YES | '{}' | |
| 7 | dept_head_for | varchar[] | YES | '{}' | |
| 8 | is_super_user | boolean | YES | false | |
| 9 | is_active | boolean | YES | true | |
| 10 | created_at | timestamptz | YES | now() | |
| 11 | last_login_at | timestamptz | YES | | |

**Indexes:** email, azure_oid, tenant_id, department_access (GIN), dept_head_for (GIN), is_active (partial)

---

### enterprise.tenants
Multi-tenant configuration.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | slug | varchar(50) | NO | | UNIQUE |
| 3 | name | varchar(255) | NO | | |
| 4 | domain | varchar(255) | NO | | |
| 5 | created_at | timestamptz | YES | now() | |

---

### enterprise.documents
RAG document chunks with dual embeddings (40 columns - the big one).

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | source_file | text | NO | | |
| 3 | department_id | text | NO | | |
| 4 | section_title | text | YES | | |
| 5 | content | text | NO | | |
| 6 | content_length | integer | YES | 0 | |
| 7 | token_count | integer | YES | 0 | |
| 8 | embedding | vector | YES | | |
| 9 | synthetic_questions_embedding | vector | YES | | |
| 10 | query_types | text[] | YES | '{}' | |
| 11 | verbs | text[] | YES | '{}' | |
| 12 | entities | text[] | YES | '{}' | |
| 13 | actors | text[] | YES | '{}' | |
| 14 | conditions | text[] | YES | '{}' | |
| 15 | is_procedure | boolean | YES | false | |
| 16 | is_policy | boolean | YES | false | |
| 17 | is_form | boolean | YES | false | |
| 18 | importance | integer | YES | 5 | |
| 19 | specificity | integer | YES | 5 | |
| 20 | complexity | integer | YES | 5 | |
| 21 | completeness_score | integer | YES | 5 | |
| 22 | actionability_score | integer | YES | 5 | |
| 23 | confidence_score | float | YES | 0.7 | |
| 24 | acronyms | jsonb | YES | '{}' | |
| 25 | jargon | jsonb | YES | '{}' | |
| 26 | numeric_thresholds | jsonb | YES | '{}' | |
| 27 | synthetic_questions | text[] | YES | '{}' | |
| 28 | process_name | text | YES | | |
| 29 | process_step | integer | YES | | |
| 30 | prerequisite_ids | uuid[] | YES | '{}' | |
| 31 | see_also_ids | uuid[] | YES | '{}' | |
| 32 | follows_ids | uuid[] | YES | '{}' | |
| 33 | contradiction_flags | uuid[] | YES | '{}' | |
| 34 | needs_review | boolean | YES | false | |
| 35 | review_reason | text | YES | | |
| 36 | department_access | text[] | YES | '{}' | |
| 37 | requires_role | text[] | YES | | |
| 38 | is_active | boolean | YES | true | |
| 39 | created_at | timestamptz | YES | now() | |
| 40 | updated_at | timestamptz | YES | now() | |

**Indexes:** 
- `idx_docs_dept` (department_id)
- `idx_docs_active` (is_active) WHERE is_active = true
- `idx_documents_embedding_vector` (embedding) USING ivfflat
- `idx_documents_question_embedding_vector` (synthetic_questions_embedding) USING ivfflat

---

### enterprise.traces
Distributed tracing - root traces.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | trace_id | varchar(32) | NO | | UNIQUE |
| 3 | entry_point | varchar(20) | NO | | |
| 4 | endpoint | varchar(255) | YES | | |
| 5 | method | varchar(10) | YES | | |
| 6 | session_id | varchar(64) | YES | | |
| 7 | user_email | varchar(255) | YES | | |
| 8 | department | varchar(50) | YES | | |
| 9 | start_time | timestamptz | NO | | |
| 10 | end_time | timestamptz | YES | | |
| 11 | duration_ms | float | YES | | |
| 12 | status | varchar(20) | YES | 'in_progress' | |
| 13 | error_message | text | YES | | |
| 14 | tags | jsonb | YES | '{}' | |
| 15 | created_at | timestamptz | YES | now() | |

**Indexes:** trace_id (unique), entry_point, session_id, start_time DESC, status, user_email

---

### enterprise.trace_spans
Distributed tracing - child spans.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | trace_id | varchar(32) | NO | | FK → traces.trace_id |
| 3 | span_id | varchar(16) | NO | | |
| 4 | parent_span_id | varchar(16) | YES | | |
| 5 | operation_name | varchar(100) | NO | | |
| 6 | service_name | varchar(50) | YES | 'enterprise_bot' | |
| 7 | start_time | timestamptz | NO | | |
| 8 | end_time | timestamptz | YES | | |
| 9 | duration_ms | float | YES | | |
| 10 | status | varchar(20) | YES | 'in_progress' | |
| 11 | error_message | text | YES | | |
| 12 | tags | jsonb | YES | '{}' | |
| 13 | logs | jsonb | YES | '[]' | |

**Indexes:** trace_id, span_id, parent_span_id, operation_name, start_time DESC

---

### enterprise.structured_logs
Structured JSON logging.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | timestamp | timestamptz | NO | now() | |
| 3 | level | varchar(10) | NO | | |
| 4 | logger_name | varchar(100) | NO | | |
| 5 | message | text | NO | | |
| 6 | trace_id | varchar(32) | YES | | |
| 7 | span_id | varchar(16) | YES | | |
| 8 | user_email | varchar(255) | YES | | |
| 9 | department | varchar(50) | YES | | |
| 10 | session_id | varchar(64) | YES | | |
| 11 | endpoint | varchar(255) | YES | | |
| 12 | extra | jsonb | YES | '{}' | |
| 13 | exception_type | varchar(255) | YES | | |
| 14 | exception_message | text | YES | | |
| 15 | exception_traceback | text | YES | | |

**Indexes:** timestamp DESC, level, trace_id, user_email, logger_name, message (GIN tsvector)
**Triggers:** `log_inserted` → `notify_new_log()` (AFTER INSERT)

---

### enterprise.alert_rules
Alert rule definitions.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | name | varchar(255) | NO | | |
| 3 | description | text | YES | | |
| 4 | metric_type | varchar(50) | NO | | |
| 5 | condition | varchar(20) | NO | | |
| 6 | threshold | float | NO | | |
| 7 | window_minutes | integer | YES | 5 | |
| 8 | evaluation_interval_seconds | integer | YES | 60 | |
| 9 | custom_sql | text | YES | | |
| 10 | severity | varchar(20) | YES | 'warning' | |
| 11 | notification_channels | jsonb | YES | '["slack"]' | |
| 12 | cooldown_minutes | integer | YES | 15 | |
| 13 | enabled | boolean | YES | true | |
| 14 | last_evaluated_at | timestamptz | YES | | |
| 15 | last_triggered_at | timestamptz | YES | | |
| 16 | created_at | timestamptz | YES | now() | |
| 17 | created_by | varchar(255) | YES | | |
| 18 | updated_at | timestamptz | YES | now() | |

**Indexes:** enabled, metric_type

---

### enterprise.alerts
Triggered alert instances.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | rule_id | uuid | YES | | FK → alert_rules.id |
| 3 | severity | varchar(20) | NO | | |
| 4 | message | text | NO | | |
| 5 | metric_value | float | YES | | |
| 6 | threshold | float | YES | | |
| 7 | triggered_at | timestamptz | NO | now() | |
| 8 | resolved_at | timestamptz | YES | | |
| 9 | status | varchar(20) | YES | 'active' | |
| 10 | acknowledged_by | varchar(255) | YES | | |
| 11 | acknowledged_at | timestamptz | YES | | |
| 12 | metadata | jsonb | YES | '{}' | |
| 13 | created_at | timestamptz | YES | now() | |

**Indexes:** rule_id, status, severity, triggered_at DESC

---

### enterprise.alert_instances
Alternative alert storage (12 columns).

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | rule_id | uuid | NO | | FK → alert_rules.id |
| 3 | status | varchar(20) | NO | 'active' | |
| 4 | triggered_at | timestamptz | NO | now() | |
| 5 | resolved_at | timestamptz | YES | | |
| 6 | acknowledged_at | timestamptz | YES | | |
| 7 | acknowledged_by | varchar(255) | YES | | |
| 8 | current_value | float | YES | | |
| 9 | threshold_value | float | YES | | |
| 10 | message | text | YES | | |
| 11 | context | jsonb | YES | '{}' | |
| 12 | notifications_sent | jsonb | YES | '[]' | |

**Indexes:** rule_id, status, triggered_at DESC

---

### enterprise.audit_log
Compliance audit trail.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | action | varchar(100) | NO | | |
| 3 | actor_email | varchar(255) | YES | | |
| 4 | actor_user_id | uuid | YES | | FK → users.id |
| 5 | target_email | varchar(255) | YES | | |
| 6 | target_user_id | uuid | YES | | FK → users.id |
| 7 | department_slug | varchar(50) | YES | | |
| 8 | old_value | text | YES | | |
| 9 | new_value | text | YES | | |
| 10 | reason | text | YES | | |
| 11 | ip_address | inet | YES | | |
| 12 | user_agent | text | YES | | |
| 13 | metadata | jsonb | YES | '{}' | |
| 14 | created_at | timestamptz | YES | now() | |

**Indexes:** action, actor_email, target_email, department_slug, created_at DESC, (action, department_slug, created_at) combo

---

### enterprise.request_metrics
HTTP request performance metrics.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | timestamp | timestamptz | NO | now() | |
| 3 | endpoint | varchar(255) | NO | | |
| 4 | method | varchar(10) | NO | | |
| 5 | status_code | integer | NO | | |
| 6 | response_time_ms | float | NO | | |
| 7 | user_email | varchar(255) | YES | | |
| 8 | department | varchar(50) | YES | | |
| 9 | request_size_bytes | integer | YES | | |
| 10 | response_size_bytes | integer | YES | | |
| 11 | trace_id | varchar(32) | YES | | |

**Indexes:** timestamp DESC, endpoint

---

### enterprise.llm_call_metrics
LLM API call tracking.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | timestamp | timestamptz | NO | now() | |
| 3 | model | varchar(100) | NO | | |
| 4 | provider | varchar(50) | NO | | |
| 5 | prompt_tokens | integer | YES | | |
| 6 | completion_tokens | integer | YES | | |
| 7 | total_tokens | integer | YES | | |
| 8 | elapsed_ms | float | NO | | |
| 9 | first_token_ms | float | YES | | |
| 10 | user_email | varchar(255) | YES | | |
| 11 | department | varchar(50) | YES | | |
| 12 | query_category | varchar(50) | YES | | |
| 13 | trace_id | varchar(32) | YES | | |
| 14 | cost_usd | numeric(10,6) | YES | | |
| 15 | success | boolean | YES | true | |
| 16 | error_message | text | YES | | |

**Indexes:** timestamp DESC

---

### enterprise.rag_metrics
RAG pipeline performance.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | timestamp | timestamptz | NO | now() | |
| 3 | trace_id | varchar(32) | YES | | |
| 4 | user_email | varchar(255) | YES | | |
| 5 | department | varchar(50) | YES | | |
| 6 | query_hash | varchar(64) | YES | | |
| 7 | total_ms | float | NO | | |
| 8 | embedding_ms | float | YES | | |
| 9 | vector_search_ms | float | YES | | |
| 10 | rerank_ms | float | YES | | |
| 11 | chunks_retrieved | integer | YES | | |
| 12 | chunks_used | integer | YES | | |
| 13 | cache_hit | boolean | YES | false | |
| 14 | embedding_cache_hit | boolean | YES | false | |
| 15 | top_score | float | YES | | |
| 16 | avg_score | float | YES | | |
| 17 | threshold_used | float | YES | | |

**Indexes:** timestamp DESC

---

### enterprise.cache_metrics
Redis/cache performance.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | timestamp | timestamptz | NO | now() | |
| 3 | cache_type | varchar(50) | NO | | |
| 4 | hits | integer | NO | 0 | |
| 5 | misses | integer | NO | 0 | |
| 6 | hit_rate | float | YES | | |
| 7 | memory_used_bytes | bigint | YES | | |
| 8 | keys_count | integer | YES | | |

**Indexes:** timestamp DESC

---

### enterprise.system_metrics
System-level metrics.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | timestamp | timestamptz | NO | now() | |
| 3 | metric_type | varchar(50) | NO | | |
| 4 | metric_name | varchar(100) | NO | | |
| 5 | value | float | NO | | |
| 6 | unit | varchar(20) | YES | | |
| 7 | tags | jsonb | YES | '{}' | |

**Indexes:** timestamp DESC

---

## Schema: personal

### personal.users
Personal memory system users (separate from enterprise.users).

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | email | varchar(255) | NO | | UNIQUE |
| 3 | auth_provider | varchar(50) | NO | | |
| 4 | created_at | timestamptz | YES | now() | |

---

### personal.memory_nodes
Individual memory entries with embeddings.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | user_id | uuid | NO | | FK → users.id |
| 3 | conversation_id | varchar(255) | NO | | |
| 4 | sequence_index | integer | NO | | |
| 5 | human_content | text | NO | | |
| 6 | assistant_content | text | NO | | |
| 7 | embedding | vector | YES | | |
| 8 | intent_type | varchar(100) | YES | | |
| 9 | complexity | varchar(50) | YES | | |
| 10 | emotional_valence | varchar(50) | YES | | |
| 11 | tags | jsonb | YES | | |
| 12 | cluster_id | integer | YES | | |
| 13 | cluster_label | varchar(255) | YES | | |
| 14 | created_at | timestamptz | YES | now() | |
| 15 | access_count | integer | YES | 0 | |
| 16 | last_accessed | timestamptz | YES | | |

**Indexes:** user_id, embedding (ivfflat), (conversation_id, sequence_index, user_id) UNIQUE

---

### personal.episodes
Conversation episode summaries.

| # | Column | Type | Nullable | Default | Key |
|---|--------|------|----------|---------|-----|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | user_id | uuid | NO | | FK → users.id |
| 3 | title | varchar(500) | YES | | |
| 4 | summary | text | YES | | |
| 5 | messages | jsonb | NO | | |
| 6 | embedding | vector | YES | | |
| 7 | created_at | timestamptz | YES | now() | |

**Indexes:** user_id, embedding (ivfflat)

---

## Custom Functions

### enterprise.check_user_access
```sql
check_user_access(p_email VARCHAR, p_department VARCHAR) → BOOLEAN
```
Checks if user has access to a department.

### enterprise.get_user_departments
```sql
get_user_departments(p_email VARCHAR) → TABLE(department VARCHAR)
```
Returns all departments a user can access.

### public.notify_new_log
```sql
notify_new_log() → TRIGGER
```
Triggers notification on new structured log insert.

---

## Triggers

| Schema | Table | Trigger | Event | Function |
|--------|-------|---------|-------|----------|
| enterprise | structured_logs | log_inserted | AFTER INSERT | notify_new_log() |

---

## Index Summary

| Schema | Table | Index Count |
|--------|-------|-------------|
| enterprise | users | 9 |
| enterprise | documents | 4 |
| enterprise | traces | 7 |
| enterprise | trace_spans | 6 |
| enterprise | structured_logs | 8 |
| enterprise | alert_rules | 3 |
| enterprise | alerts | 5 |
| enterprise | alert_instances | 4 |
| enterprise | audit_log | 7 |
| enterprise | request_metrics | 3 |
| enterprise | llm_call_metrics | 2 |
| enterprise | rag_metrics | 2 |
| enterprise | cache_metrics | 2 |
| enterprise | system_metrics | 2 |
| enterprise | tenants | 2 |
| personal | users | 2 |
| personal | memory_nodes | 4 |
| personal | episodes | 3 |
| **TOTAL** | | **82** |

---

## Foreign Key Map

```
enterprise.users.tenant_id → enterprise.tenants.id
enterprise.audit_log.actor_user_id → enterprise.users.id
enterprise.audit_log.target_user_id → enterprise.users.id
enterprise.alerts.rule_id → enterprise.alert_rules.id
enterprise.alert_instances.rule_id → enterprise.alert_rules.id
enterprise.trace_spans.trace_id → enterprise.traces.trace_id
personal.memory_nodes.user_id → personal.users.id
personal.episodes.user_id → personal.users.id
```

---

## Notes

1. **Dual alert tables:** Both `alerts` and `alert_instances` exist - may need consolidation
2. **Dual user tables:** `enterprise.users` vs `personal.users` - different auth contexts
3. **Vector indexes:** Using ivfflat with lists=100 for embedding search
4. **Trigger active:** structured_logs has real-time notification trigger

---

**END OF SCHEMA MAP**
