# Database Schema Map

**Last Updated:** 2025-12-30 (Session: Cogzy Launch)  
**Database:** cogtwin.postgres.database.azure.com  
**Status:** FROZEN - See Commandments Below

---

## COMMANDMENTS

> **These rules are absolute. No exceptions without a dedicated architecture session.**

### I. Schema Integrity
1. **NO NEW TABLES** without a dedicated architecture session
2. **NO NEW COLUMNS** as quick fixes or bandaids
3. **NO COLUMN TYPE CHANGES** without migration plan
4. **NO INDEX CHANGES** without performance justification

### II. Process Requirements
1. Any schema change requires a NEW SESSION with "SCHEMA CHANGE:" prefix
2. All changes must be documented in this file BEFORE deployment
3. Rollback SQL must be prepared for every change
4. Changes must be tested on local/staging before production

### III. Consultation Protocol
1. **ALWAYS** read this file before any database work
2. **ALWAYS** check foreign keys before DELETE operations
3. **ALWAYS** check indexes before new query patterns
4. **NEVER** trust memory - verify against this document

---

## Overview

| Schema | Tables | Rows | Purpose |
|--------|--------|------|---------|
| enterprise | 17 | 22,687 | Driscoll RAG, auth, observability, metrics |
| personal | 5 | 0 | CogTwin/Cogzy user memories + auth |
| public | - | - | Extensions only (pgvector) |

**Total:** 22 tables, 319 columns, 113 indexes, 11 foreign keys

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

# SCHEMA: enterprise

*Driscoll Foods deployment - RAG, Azure AD auth, observability*

---

## enterprise.tenants
Multi-tenant configuration for enterprise customers.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | slug | varchar | NO | | UNIQUE - url identifier |
| 3 | name | varchar | NO | | Display name |
| 4 | domain | varchar | NO | | UNIQUE - email domain |
| 5 | created_at | timestamptz | YES | now() | |
| 6 | azure_tenant_id | varchar | YES | | Azure AD tenant |
| 7 | azure_client_id | varchar | YES | | Azure AD app |
| 8 | azure_client_secret_ref | varchar | YES | | Secret reference (not actual secret) |
| 9 | branding | jsonb | YES | '{}' | Custom branding config |
| 10 | is_active | boolean | YES | true | Soft delete |

**Indexes:** `tenants_pkey`, `tenants_slug_key` (unique), `idx_tenants_domain` (unique), `idx_tenants_slug`
**Row Count:** 2

---

## enterprise.users
Enterprise user accounts (Azure AD authenticated).

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | tenant_id | uuid | YES | | FK → tenants.id |
| 3 | email | varchar | NO | | UNIQUE |
| 4 | display_name | varchar | YES | | |
| 5 | azure_oid | varchar | YES | | UNIQUE - Azure Object ID |
| 6 | department_access | varchar[] | YES | '{}' | Departments user can query |
| 7 | dept_head_for | varchar[] | YES | '{}' | Departments user manages |
| 8 | is_super_user | boolean | YES | false | Full admin access |
| 9 | is_active | boolean | YES | true | Soft delete |
| 10 | created_at | timestamptz | YES | now() | |
| 11 | last_login_at | timestamptz | YES | | |

**Indexes:** `users_pkey`, `users_email_key` (unique), `users_azure_oid_key` (unique), `idx_users_tenant_id`, `idx_users_azure_oid`, `idx_users_email`, `idx_users_active` (partial), `idx_users_dept_access` (GIN), `idx_users_dept_head` (GIN)
**Foreign Keys:** `tenant_id` → `enterprise.tenants.id`
**Row Count:** 13

---

## enterprise.documents
RAG document chunks with dual embeddings (content + synthetic questions).

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | source_file | text | NO | | Original filename |
| 3 | department_id | text | NO | | Owning department |
| 4 | section_title | text | YES | | Section heading |
| 5 | content | text | NO | | Chunk text |
| 6 | content_length | integer | YES | 0 | Character count |
| 7 | token_count | integer | YES | 0 | Token estimate |
| 8 | embedding | vector | YES | | Content embedding (1024d) |
| 9 | synthetic_questions_embedding | vector | YES | | Question embedding (1024d) |
| 10 | query_types | text[] | YES | '{}' | LLM-tagged query types |
| 11 | verbs | text[] | YES | '{}' | Action verbs extracted |
| 12 | entities | text[] | YES | '{}' | Named entities |
| 13 | actors | text[] | YES | '{}' | People/roles mentioned |
| 14 | conditions | text[] | YES | '{}' | Conditional phrases |
| 15 | is_procedure | boolean | YES | false | Step-by-step content |
| 16 | is_policy | boolean | YES | false | Policy/rule content |
| 17 | is_form | boolean | YES | false | Form reference |
| 18 | importance | integer | YES | 5 | 1-10 scale |
| 19 | specificity | integer | YES | 5 | 1-10 scale |
| 20 | complexity | integer | YES | 5 | 1-10 scale |
| 21 | completeness_score | integer | YES | 5 | 1-10 scale |
| 22 | actionability_score | integer | YES | 5 | 1-10 scale |
| 23 | confidence_score | double precision | YES | 0.7 | Embedding quality |
| 24 | acronyms | jsonb | YES | '{}' | {acronym: expansion} |
| 25 | jargon | jsonb | YES | '{}' | {term: definition} |
| 26 | numeric_thresholds | jsonb | YES | '{}' | Important numbers |
| 27 | synthetic_questions | text[] | YES | '{}' | Generated questions |
| 28 | process_name | text | YES | | Parent process |
| 29 | process_step | integer | YES | | Step number |
| 30 | prerequisite_ids | uuid[] | YES | '{}' | Must-read-first docs |
| 31 | see_also_ids | uuid[] | YES | '{}' | Related docs |
| 32 | follows_ids | uuid[] | YES | '{}' | Sequential docs |
| 33 | contradiction_flags | uuid[] | YES | '{}' | Conflicting docs |
| 34 | needs_review | boolean | YES | false | Flagged for review |
| 35 | review_reason | text | YES | | Why flagged |
| 36 | department_access | text[] | YES | '{}' | Cross-dept visibility |
| 37 | requires_role | text[] | YES | | Role-based access |
| 38 | is_active | boolean | YES | true | Soft delete |
| 39 | created_at | timestamptz | YES | now() | |
| 40 | updated_at | timestamptz | YES | now() | |

**Indexes:** `documents_pkey`, `idx_docs_dept`, `idx_docs_active` (partial WHERE is_active=true), `idx_documents_embedding_vector` (ivfflat lists=100), `idx_documents_question_embedding_vector` (ivfflat lists=100)
**Row Count:** 169

---

## enterprise.query_log
User query tracking with NLU analysis.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | user_id | uuid | YES | | FK → users.id |
| 3 | user_email | varchar | YES | | Denormalized |
| 4 | department | varchar | YES | | Active department |
| 5 | session_id | varchar | YES | | Browser session |
| 6 | query_text | text | NO | | Raw query |
| 7 | query_length | integer | YES | | Character count |
| 8 | query_word_count | integer | YES | | Word count |
| 9 | query_category | varchar | YES | | LLM classification |
| 10 | query_keywords | text[] | YES | | Extracted keywords |
| 11 | frustration_signals | text[] | YES | | Detected frustration |
| 12 | is_repeat_question | boolean | YES | false | Seen before? |
| 13 | repeat_of_query_id | uuid | YES | | Original query |
| 14 | response_time_ms | double precision | YES | | Total latency |
| 15 | response_length | integer | YES | | Response chars |
| 16 | tokens_input | integer | YES | | Prompt tokens |
| 17 | tokens_output | integer | YES | | Response tokens |
| 18 | model_used | varchar | YES | | LLM model |
| 19 | query_position_in_session | integer | YES | | Nth query |
| 20 | time_since_last_query_ms | integer | YES | | Gap from previous |
| 21 | created_at | timestamptz | YES | now() | |
| 22 | complexity_score | double precision | YES | | NLU complexity |
| 23 | intent_type | varchar | YES | | Primary intent |
| 24 | specificity_score | double precision | YES | | How specific |
| 25 | temporal_urgency | varchar | YES | | Urgency level |
| 26 | is_multi_part | boolean | YES | false | Multiple questions |
| 27 | department_context_inferred | varchar | YES | | Detected dept |
| 28 | department_context_scores | jsonb | YES | | Dept probabilities |
| 29 | session_pattern | varchar | YES | | Behavior pattern |

**Indexes:** `query_log_pkey`, `idx_query_log_user`, `idx_query_log_dept`, `idx_query_log_session`, `idx_query_log_category`, `idx_query_log_created`, `idx_query_log_dept_context`, `idx_query_log_intent_type`, `idx_query_log_complexity`, `idx_query_log_temporal_urgency`, `idx_query_log_text` (GIN tsvector), `idx_query_log_dept_scores_gin` (GIN)
**Foreign Keys:** `user_id` → `enterprise.users.id`
**Row Count:** 42

---

## enterprise.analytics_events
User behavior events for analytics.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | event_type | varchar | NO | | Event name |
| 3 | user_id | uuid | YES | | FK → users.id |
| 4 | user_email | varchar | YES | | Denormalized |
| 5 | department | varchar | YES | | |
| 6 | session_id | varchar | YES | | |
| 7 | event_data | jsonb | YES | | Event payload |
| 8 | from_department | varchar | YES | | Dept switch from |
| 9 | to_department | varchar | YES | | Dept switch to |
| 10 | error_type | varchar | YES | | Error category |
| 11 | error_message | text | YES | | Error details |
| 12 | created_at | timestamptz | YES | now() | |

**Indexes:** `analytics_events_pkey`, `idx_events_type`, `idx_events_user`, `idx_events_dept`, `idx_events_session`, `idx_events_created`
**Foreign Keys:** `user_id` → `enterprise.users.id`
**Row Count:** 61

---

## enterprise.audit_log
Security and admin action audit trail.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | action | varchar | NO | | Action type |
| 3 | actor_email | varchar | YES | | Who did it |
| 4 | actor_user_id | uuid | YES | | FK → users.id |
| 5 | target_email | varchar | YES | | Affected user |
| 6 | target_user_id | uuid | YES | | FK → users.id |
| 7 | department_slug | varchar | YES | | Affected dept |
| 8 | old_value | text | YES | | Before state |
| 9 | new_value | text | YES | | After state |
| 10 | reason | text | YES | | Why changed |
| 11 | ip_address | inet | YES | | Source IP |
| 12 | user_agent | text | YES | | Browser/client |
| 13 | metadata | jsonb | YES | '{}' | Extra context |
| 14 | created_at | timestamptz | YES | now() | |

**Indexes:** `audit_log_pkey`, `idx_audit_action`, `idx_audit_actor`, `idx_audit_target`, `idx_audit_department`, `idx_audit_created`, `idx_audit_filter_combo` (action, department_slug, created_at)
**Foreign Keys:** `actor_user_id` → `enterprise.users.id`, `target_user_id` → `enterprise.users.id`
**Row Count:** 15

---

## enterprise.traces
Distributed tracing - root traces.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | trace_id | varchar | NO | | UNIQUE - correlation ID |
| 3 | entry_point | varchar | NO | | http/ws/internal |
| 4 | endpoint | varchar | YES | | API path |
| 5 | method | varchar | YES | | HTTP method |
| 6 | session_id | varchar | YES | | |
| 7 | user_email | varchar | YES | | |
| 8 | department | varchar | YES | | |
| 9 | start_time | timestamptz | NO | | |
| 10 | end_time | timestamptz | YES | | |
| 11 | duration_ms | double precision | YES | | |
| 12 | status | varchar | YES | 'in_progress' | |
| 13 | error_message | text | YES | | |
| 14 | tags | jsonb | YES | '{}' | |
| 15 | created_at | timestamptz | YES | now() | |

**Indexes:** `traces_pkey`, `traces_trace_id_key` (unique), `idx_traces_trace_id`, `idx_traces_entry_point`, `idx_traces_session`, `idx_traces_start_time`, `idx_traces_user_email`, `idx_traces_user`, `idx_traces_status`
**Row Count:** 18

---

## enterprise.trace_spans
Distributed tracing - child spans.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | trace_id | varchar | NO | | FK → traces.trace_id |
| 3 | span_id | varchar | NO | | Unique within trace |
| 4 | parent_span_id | varchar | YES | | Parent span |
| 5 | operation_name | varchar | NO | | Function/operation |
| 6 | service_name | varchar | YES | 'enterprise_bot' | |
| 7 | start_time | timestamptz | NO | | |
| 8 | end_time | timestamptz | YES | | |
| 9 | duration_ms | double precision | YES | | |
| 10 | status | varchar | YES | 'in_progress' | |
| 11 | error_message | text | YES | | |
| 12 | tags | jsonb | YES | '{}' | |
| 13 | logs | jsonb | YES | '[]' | |

**Indexes:** `trace_spans_pkey`, `idx_spans_trace_id`, `idx_trace_spans_trace_id`, `idx_spans_span_id`, `idx_spans_parent`, `idx_spans_operation`, `idx_spans_start_time`
**Foreign Keys:** `trace_id` → `enterprise.traces.trace_id`
**Row Count:** 0

---

## enterprise.structured_logs
Structured JSON logging (high volume).

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | timestamp | timestamptz | NO | now() | |
| 3 | level | varchar | NO | | INFO/WARN/ERROR/etc |
| 4 | logger_name | varchar | NO | | Module name |
| 5 | message | text | NO | | Log message |
| 6 | trace_id | varchar | YES | | Correlation ID |
| 7 | span_id | varchar | YES | | |
| 8 | user_email | varchar | YES | | |
| 9 | department | varchar | YES | | |
| 10 | session_id | varchar | YES | | |
| 11 | endpoint | varchar | YES | | |
| 12 | extra | jsonb | YES | '{}' | Additional data |
| 13 | exception_type | varchar | YES | | Error class |
| 14 | exception_message | text | YES | | Error message |
| 15 | exception_traceback | text | YES | | Stack trace |

**Indexes:** `structured_logs_pkey`, `idx_logs_timestamp`, `idx_structured_logs_timestamp`, `idx_logs_level`, `idx_structured_logs_level`, `idx_logs_trace_id`, `idx_structured_logs_trace_id` (partial), `idx_logs_user_email`, `idx_logs_user`, `idx_logs_logger`, `idx_logs_message_search` (GIN tsvector), `idx_structured_logs_security` (partial)
**Triggers:** `log_inserted` → `notify_new_log()` (AFTER INSERT)
**Row Count:** 22,355 ⚠️ HIGH VOLUME

---

## enterprise.alert_rules
Alert rule definitions.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | name | varchar | NO | | Rule name |
| 3 | description | text | YES | | |
| 4 | metric_type | varchar | NO | | What to measure |
| 5 | condition | varchar | NO | | gt/lt/eq/etc |
| 6 | threshold | double precision | NO | | Trigger value |
| 7 | window_minutes | integer | YES | 5 | Evaluation window |
| 8 | evaluation_interval_seconds | integer | YES | 60 | Check frequency |
| 9 | custom_sql | text | YES | | Custom query |
| 10 | severity | varchar | YES | 'warning' | info/warning/critical |
| 11 | notification_channels | jsonb | YES | '["slack"]' | Where to notify |
| 12 | cooldown_minutes | integer | YES | 15 | Re-alert delay |
| 13 | enabled | boolean | YES | true | Active? |
| 14 | last_evaluated_at | timestamptz | YES | | |
| 15 | last_triggered_at | timestamptz | YES | | |
| 16 | created_at | timestamptz | YES | now() | |
| 17 | created_by | varchar | YES | | |
| 18 | updated_at | timestamptz | YES | now() | |

**Indexes:** `alert_rules_pkey`, `idx_alert_rules_enabled`, `idx_alert_rules_metric`
**Row Count:** 10

---

## enterprise.alerts
Triggered alert instances (legacy table).

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | rule_id | uuid | YES | | FK → alert_rules.id |
| 3 | severity | varchar | NO | | |
| 4 | message | text | NO | | |
| 5 | metric_value | double precision | YES | | |
| 6 | threshold | double precision | YES | | |
| 7 | triggered_at | timestamptz | NO | now() | |
| 8 | resolved_at | timestamptz | YES | | |
| 9 | status | varchar | YES | 'active' | |
| 10 | acknowledged_by | varchar | YES | | |
| 11 | acknowledged_at | timestamptz | YES | | |
| 12 | metadata | jsonb | YES | '{}' | |
| 13 | created_at | timestamptz | YES | now() | |

**Indexes:** `alerts_pkey`, `idx_alerts_rule_id`, `idx_alerts_severity`, `idx_alerts_status`, `idx_alerts_triggered_at`
**Foreign Keys:** `rule_id` → `enterprise.alert_rules.id`
**Row Count:** 0

---

## enterprise.alert_instances
Triggered alert instances (current table).

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | rule_id | uuid | NO | | FK → alert_rules.id |
| 3 | triggered_at | timestamptz | NO | now() | |
| 4 | resolved_at | timestamptz | YES | | |
| 5 | status | varchar | YES | 'firing' | firing/resolved/ack |
| 6 | acknowledged_by | varchar | YES | | |
| 7 | acknowledged_at | timestamptz | YES | | |
| 8 | metric_value | double precision | YES | | |
| 9 | threshold_value | double precision | YES | | |
| 10 | message | text | YES | | |
| 11 | context | jsonb | YES | '{}' | |
| 12 | notifications_sent | jsonb | YES | '[]' | |

**Indexes:** `alert_instances_pkey`, `idx_alert_instances_rule`, `idx_alert_instances_rule_id`, `idx_alert_instances_status`, `idx_alert_instances_triggered_at`, `idx_alert_instances_triggered`
**Foreign Keys:** `rule_id` → `enterprise.alert_rules.id`
**Row Count:** 2

---

## enterprise.request_metrics
HTTP request performance.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | timestamp | timestamptz | NO | now() | |
| 3 | endpoint | varchar | NO | | API path |
| 4 | method | varchar | NO | | HTTP method |
| 5 | status_code | integer | NO | | Response code |
| 6 | response_time_ms | double precision | NO | | Latency |
| 7 | user_email | varchar | YES | | |
| 8 | department | varchar | YES | | |
| 9 | request_size_bytes | integer | YES | | |
| 10 | response_size_bytes | integer | YES | | |
| 11 | trace_id | varchar | YES | | |

**Indexes:** `request_metrics_pkey`, `idx_request_metrics_ts`, `idx_request_metrics_endpoint`
**Row Count:** 0

---

## enterprise.llm_call_metrics
LLM API call tracking.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | timestamp | timestamptz | NO | now() | |
| 3 | model | varchar | NO | | Model name |
| 4 | provider | varchar | NO | | anthropic/xai/etc |
| 5 | prompt_tokens | integer | YES | | Input tokens |
| 6 | completion_tokens | integer | YES | | Output tokens |
| 7 | total_tokens | integer | YES | | Sum |
| 8 | elapsed_ms | double precision | NO | | Total time |
| 9 | first_token_ms | double precision | YES | | TTFB |
| 10 | user_email | varchar | YES | | |
| 11 | department | varchar | YES | | |
| 12 | query_category | varchar | YES | | |
| 13 | trace_id | varchar | YES | | |
| 14 | cost_usd | numeric | YES | | Estimated cost |
| 15 | success | boolean | YES | true | |
| 16 | error_message | text | YES | | |

**Indexes:** `llm_call_metrics_pkey`, `idx_llm_metrics_ts`
**Row Count:** 0

---

## enterprise.rag_metrics
RAG pipeline performance.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | timestamp | timestamptz | NO | now() | |
| 3 | trace_id | varchar | YES | | |
| 4 | user_email | varchar | YES | | |
| 5 | department | varchar | YES | | |
| 6 | query_hash | varchar | YES | | Query fingerprint |
| 7 | total_ms | double precision | NO | | End-to-end time |
| 8 | embedding_ms | double precision | YES | | Embed time |
| 9 | vector_search_ms | double precision | YES | | Search time |
| 10 | rerank_ms | double precision | YES | | Rerank time |
| 11 | chunks_retrieved | integer | YES | | Initial results |
| 12 | chunks_used | integer | YES | | After filtering |
| 13 | cache_hit | boolean | YES | false | Full cache hit |
| 14 | embedding_cache_hit | boolean | YES | false | Embedding cached |
| 15 | top_score | double precision | YES | | Best match score |
| 16 | avg_score | double precision | YES | | Mean score |
| 17 | threshold_used | double precision | YES | | Cutoff value |

**Indexes:** `rag_metrics_pkey`, `idx_rag_metrics_ts`
**Row Count:** 0

---

## enterprise.cache_metrics
Redis/cache performance.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | timestamp | timestamptz | NO | now() | |
| 3 | cache_type | varchar | NO | | redis/memory/etc |
| 4 | hits | integer | NO | 0 | |
| 5 | misses | integer | NO | 0 | |
| 6 | hit_rate | double precision | YES | | hits/(hits+misses) |
| 7 | memory_used_bytes | bigint | YES | | |
| 8 | keys_count | integer | YES | | |

**Indexes:** `cache_metrics_pkey`, `idx_cache_metrics_ts`
**Row Count:** 0

---

## enterprise.system_metrics
System-level metrics.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | timestamp | timestamptz | NO | now() | |
| 3 | metric_type | varchar | NO | | cpu/memory/disk/etc |
| 4 | metric_name | varchar | NO | | Specific metric |
| 5 | value | double precision | NO | | |
| 6 | unit | varchar | YES | | percent/bytes/etc |
| 7 | tags | jsonb | YES | '{}' | |

**Indexes:** `system_metrics_pkey`, `idx_system_metrics_ts`
**Row Count:** 0

---

# SCHEMA: personal

*CogTwin/Cogzy personal tier - user memories + authentication*

---

## personal.users
Personal tier user accounts (Google OAuth + Email/Password).

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | email | varchar | NO | | UNIQUE |
| 3 | auth_provider | varchar | NO | | google/email |
| 4 | created_at | timestamptz | YES | now() | |
| 5 | password_hash | text | YES | | bcrypt hash (email auth) |
| 6 | email_verified | boolean | YES | false | Email confirmed |
| 7 | verification_token | varchar | YES | | Email verify token |
| 8 | verification_expires | timestamptz | YES | | Token expiry |
| 9 | reset_token | varchar | YES | | Password reset token |
| 10 | reset_expires | timestamptz | YES | | Reset token expiry |
| 11 | google_id | varchar | YES | | Google OAuth ID |
| 12 | display_name | varchar | YES | | User's name |
| 13 | avatar_url | varchar | YES | | Profile picture |
| 14 | last_login_at | timestamptz | YES | | |
| 15 | is_active | boolean | YES | true | Soft delete |

**Indexes:** `users_pkey`, `users_email_key` (unique), `idx_users_google_id` (unique, partial WHERE NOT NULL)
**Row Count:** 0

---

## personal.memory_nodes
Individual memory entries with embeddings (core CogTwin table).

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | user_id | uuid | NO | | FK → users.id |
| 3 | conversation_id | varchar | NO | | Source conversation |
| 4 | sequence_index | integer | NO | | Position in convo |
| 5 | human_content | text | NO | | User message |
| 6 | assistant_content | text | NO | | AI response |
| 7 | embedding | vector | YES | | Memory embedding |
| 8 | intent_type | varchar | YES | | Query intent |
| 9 | complexity | varchar | YES | | simple/medium/complex |
| 10 | emotional_valence | varchar | YES | | positive/negative/neutral |
| 11 | tags | jsonb | YES | | LLM-extracted tags |
| 12 | cluster_id | integer | YES | | FAISS cluster |
| 13 | cluster_label | varchar | YES | | Cluster name |
| 14 | created_at | timestamptz | YES | now() | |
| 15 | access_count | integer | YES | 0 | Retrieval count |
| 16 | last_accessed | timestamptz | YES | | Last retrieved |

**Indexes:** `memory_nodes_pkey`, `memory_nodes_conversation_id_sequence_index_user_id_key` (unique composite), `idx_memory_user`, `idx_memory_embedding` (ivfflat lists=100)
**Foreign Keys:** `user_id` → `personal.users.id`
**Row Count:** 0

---

## personal.episodes
Conversation episode summaries (episodic memory lane).

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | user_id | uuid | NO | | FK → users.id |
| 3 | title | varchar | YES | | Episode title |
| 4 | summary | text | YES | | Episode summary |
| 5 | messages | jsonb | NO | | Full conversation |
| 6 | embedding | vector | YES | | Summary embedding |
| 7 | created_at | timestamptz | YES | now() | |

**Indexes:** `episodes_pkey`, `idx_episodes_user`, `idx_episodes_embedding` (ivfflat lists=100)
**Foreign Keys:** `user_id` → `personal.users.id`
**Row Count:** 0

---

## personal.conversation_chunks
Chunked conversation segments with topic tagging.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | conversation_id | uuid | NO | | Parent conversation |
| 3 | chunk_index | integer | NO | | Position in convo |
| 4 | primary_topic | text | NO | | Main topic |
| 5 | tags | text[] | NO | '{}' | Topic tags |
| 6 | summary | text | YES | | Chunk summary |
| 7 | messages | jsonb | NO | | Messages in chunk |
| 8 | embedding | vector | YES | | Chunk embedding |
| 9 | start_msg | integer | NO | | First message index |
| 10 | end_msg | integer | NO | | Last message index |
| 11 | conversation_date | date | NO | | Date of conversation |
| 12 | created_at | timestamptz | YES | now() | |

**Indexes:** `conversation_chunks_pkey`, `idx_chunks_embedding` (ivfflat lists=100), `idx_chunks_date`, `idx_chunks_tags` (GIN)
**Row Count:** 0

---

## personal.canonical_tags
Normalized tag hierarchy for memory organization.

| # | Column | Type | Nullable | Default | Notes |
|---|--------|------|----------|---------|-------|
| 1 | id | uuid | NO | gen_random_uuid() | PK |
| 2 | name | text | NO | | UNIQUE - tag name |
| 3 | embedding | vector | YES | | Tag embedding |
| 4 | parent_id | uuid | YES | | FK → canonical_tags.id (self-ref) |
| 5 | chunk_count | integer | YES | 0 | Usage count |
| 6 | months_ago_first | integer | YES | 0 | First seen (months) |
| 7 | months_ago_last | integer | YES | 0 | Last seen (months) |
| 8 | created_at | timestamptz | YES | now() | |

**Indexes:** `canonical_tags_pkey`, `canonical_tags_name_key` (unique), `idx_canonical_name`
**Foreign Keys:** `parent_id` → `personal.canonical_tags.id` (self-referential hierarchy)
**Row Count:** 0

---

# Foreign Key Map

```
ENTERPRISE:
enterprise.users.tenant_id          → enterprise.tenants.id
enterprise.audit_log.actor_user_id  → enterprise.users.id
enterprise.audit_log.target_user_id → enterprise.users.id
enterprise.query_log.user_id        → enterprise.users.id
enterprise.analytics_events.user_id → enterprise.users.id
enterprise.alerts.rule_id           → enterprise.alert_rules.id
enterprise.alert_instances.rule_id  → enterprise.alert_rules.id
enterprise.trace_spans.trace_id     → enterprise.traces.trace_id

PERSONAL:
personal.memory_nodes.user_id       → personal.users.id
personal.episodes.user_id           → personal.users.id
personal.canonical_tags.parent_id   → personal.canonical_tags.id (self-ref)
```

---

# Index Summary by Table

| Schema | Table | Indexes | Notes |
|--------|-------|---------|-------|
| enterprise | tenants | 4 | |
| enterprise | users | 9 | GIN on arrays |
| enterprise | documents | 4 | ivfflat on vectors |
| enterprise | query_log | 12 | Heavy indexing for analytics |
| enterprise | analytics_events | 6 | |
| enterprise | audit_log | 7 | Combo index for filters |
| enterprise | traces | 9 | |
| enterprise | trace_spans | 7 | |
| enterprise | structured_logs | 12 | GIN + partial indexes |
| enterprise | alert_rules | 3 | |
| enterprise | alerts | 5 | |
| enterprise | alert_instances | 6 | |
| enterprise | request_metrics | 3 | |
| enterprise | llm_call_metrics | 2 | |
| enterprise | rag_metrics | 2 | |
| enterprise | cache_metrics | 2 | |
| enterprise | system_metrics | 2 | |
| personal | users | 3 | Partial unique on google_id |
| personal | memory_nodes | 4 | ivfflat + composite unique |
| personal | episodes | 3 | ivfflat |
| personal | conversation_chunks | 4 | ivfflat + GIN on tags |
| personal | canonical_tags | 3 | |
| **TOTAL** | | **113** | |

---

# Row Counts (as of 2025-12-30)

| Schema | Table | Rows |
|--------|-------|------|
| enterprise | structured_logs | 22,355 |
| enterprise | documents | 169 |
| enterprise | analytics_events | 61 |
| enterprise | query_log | 42 |
| enterprise | traces | 18 |
| enterprise | audit_log | 15 |
| enterprise | users | 13 |
| enterprise | alert_rules | 10 |
| enterprise | alert_instances | 2 |
| enterprise | tenants | 2 |
| enterprise | alerts | 0 |
| enterprise | cache_metrics | 0 |
| enterprise | llm_call_metrics | 0 |
| enterprise | rag_metrics | 0 |
| enterprise | request_metrics | 0 |
| enterprise | system_metrics | 0 |
| enterprise | trace_spans | 0 |
| personal | users | 0 |
| personal | memory_nodes | 0 |
| personal | episodes | 0 |
| personal | conversation_chunks | 0 |
| personal | canonical_tags | 0 |

---

# Notes & Warnings

1. **Dual alert tables:** Both `alerts` and `alert_instances` exist - `alert_instances` is current, `alerts` is legacy
2. **Dual user tables:** `enterprise.users` (Azure AD) vs `personal.users` (Google/Email) - completely separate auth
3. **Vector indexes:** Using ivfflat with lists=100 - good for <1M vectors, revisit if scaling beyond
4. **High volume table:** `structured_logs` at 22K+ rows - consider partitioning or retention policy
5. **Trigger active:** `structured_logs` has real-time notification trigger `notify_new_log()`
6. **Personal schema empty:** Ready for first user signup

---

# Custom Functions

```sql
enterprise.check_user_access(p_email VARCHAR, p_department VARCHAR) → BOOLEAN
-- Checks if user has access to a department

enterprise.get_user_departments(p_email VARCHAR) → TABLE(department VARCHAR)
-- Returns all departments a user can access

public.notify_new_log() → TRIGGER
-- Triggers notification on new structured log insert
```

---

**END OF SCHEMA MAP**

*Last verified: 2025-12-30 by Claude (Architecture Session)*