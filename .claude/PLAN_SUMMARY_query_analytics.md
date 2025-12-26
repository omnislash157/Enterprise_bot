# Query Analytics Redesign - Executive Summary

**Date:** 2025-12-26
**Status:** 📋 Plan Complete - Awaiting Approval

---

## 🎯 Objective

Transform analytics from tracking **dropdown selections** to analyzing **actual query content and patterns** with a rotating 3D memory graph visualization.

---

## 🔍 Current Problem

- Analytics tracks which **department dropdown** users select
- This doesn't show which **department knowledge** is actually being queried
- Limited insight into query complexity, intent, or patterns
- 3D visualization exists but underutilized

---

## ✨ Proposed Solution

### 1. **Heuristics-Based Query Analysis**
Analyze actual query content to determine:
- **Complexity score** (0-1): How complex is the question?
- **Intent type**: Information seeking, action-oriented, decision support, verification
- **Specificity score** (0-1): Generic vs specific (uses product codes, dates, technical terms)
- **Temporal urgency**: LOW, MEDIUM, HIGH, URGENT
- **Inferred department context**: Which dept's knowledge is needed based on content (not dropdown)

### 2. **Pattern Detection**
- **Session patterns**: Exploratory, focused, troubleshooting escalation, onboarding
- **Temporal trends**: Peak usage times per department
- **Anomaly detection**: Sudden spikes, repeated failures, emerging topics
- **Query flows**: Common sequences (e.g., LOOKUP → TROUBLESHOOTING → ESCALATION)

### 3. **Rotating Memory Graph (t3d)**
Enhanced 3D visualization with:
- **Inner sphere**: Query category nodes (existing, enhanced)
- **Outer rotating orbit**: Department memory nodes showing:
  - Size = Inferred usage volume
  - Color = Query complexity (cyan=simple, red=complex)
- **Flow lines**: Show query journey from categories to departments
- **Memory persistence**: Rotating orbit represents "brain" remembering patterns

---

## 🏗️ Architecture Overview

```
Query Received
    ↓
[EXISTING]
├─ Category classification (PROCEDURAL, LOOKUP, etc.)
├─ Keyword extraction
├─ Frustration detection
└─ Repeat question detection
    ↓
[NEW]
├─ QueryComplexityAnalyzer
│   ├─ complexity_score
│   ├─ intent_type
│   ├─ specificity_score
│   └─ temporal_urgency
│
├─ DepartmentContextAnalyzer
│   ├─ department_context_inferred (primary)
│   └─ department_context_scores (probability distribution)
│
└─ QueryPatternDetector
    ├─ session_pattern
    ├─ temporal_trends
    └─ anomaly_detection
    ↓
Store in PostgreSQL (new columns added via migration)
    ↓
New Dashboard Endpoints
├─ /api/admin/analytics/department-usage-inferred
├─ /api/admin/analytics/query-intents
├─ /api/admin/analytics/complexity-distribution
├─ /api/admin/analytics/temporal-patterns
└─ /api/admin/analytics/memory-graph-data
    ↓
Frontend Analytics Store (enhanced)
    ↓
Nerve Center - Rotating Memory Graph (3D visualization)
```

---

## 📊 Key Metrics Tracked

### Query Heuristics
| Metric | Description | Values |
|--------|-------------|--------|
| `complexity_score` | Question complexity | 0.0-1.0 |
| `intent_type` | Query purpose | INFORMATION_SEEKING, ACTION_ORIENTED, DECISION_SUPPORT, VERIFICATION |
| `specificity_score` | Generic vs specific | 0.0-1.0 |
| `temporal_urgency` | Urgency level | LOW, MEDIUM, HIGH, URGENT |
| `is_multi_part` | Multiple questions in one | true/false |

### Department Context (Content-Based)
| Metric | Description | Example |
|--------|-------------|---------|
| `department_context_inferred` | Primary department from content | "warehouse" (even if user selected "hr" in dropdown) |
| `department_context_scores` | Probability distribution | `{"warehouse": 0.8, "safety": 0.15, "hr": 0.05}` |

### Session Patterns
| Pattern | Description | Detection Criteria |
|---------|-------------|-------------------|
| EXPLORATORY | User exploring, asking diverse questions | High category diversity, low repeat rate |
| FOCUSED | User drilling into specific topic | Low diversity, high related queries |
| TROUBLESHOOTING_ESCALATION | Problem getting worse | Increasing complexity + frustration signals |
| ONBOARDING | Learning procedures | Sequential procedural queries |

---

## 🎨 Visual: Rotating Memory Graph

```
                    [PROCEDURAL]
                   /     |      \
                  /      |       \
            [LOOKUP]  [POLICY]  [TROUBLESHOOTING]
               |         |            |
          _____|_________|____________|______
         /  ROTATING OUTER ORBIT (Depts)    \
        /                                     \
       | [WAREHOUSE] [IT] [HR] [SAFETY] [FIN] |
        \            (rotating slowly)        /
         \___________________________________/
                        |
                  [Central Core]
              (pulses with activity)

Legend:
- Inner nodes = Query categories (sized by volume)
- Outer orbit = Department memory (sized by inferred usage, colored by complexity)
- Flow lines = Query journey (category → department)
- Rotation = Memory persistence visualization
```

---

## 🔗 Integration with Observability

### Traces
- New span: `query_heuristics`
- Tags: `complexity_score`, `inferred_department`, `intent_type`

### Logs
- `[PATTERN] Detected spike in TROUBLESHOOTING queries for IT department`
- `[ANOMALY] Repeat question rate exceeds 30%`

### Metrics (metrics_collector.py)
- `record_query_complexity(score)`
- `record_department_inference(dept, confidence)`

### Alerts
- `high_complexity_queries`: Avg complexity >0.8 for 10min
- `repeat_question_spike`: Repeat rate >40%
- `department_inference_low_confidence`: <50% queries have >0.5 confidence

---

## 📅 Implementation Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 1: Backend Heuristics** | Week 1 | `query_heuristics.py`, DB migration, updated `analytics_service.py` |
| **Phase 2: Enhanced Analytics** | Week 1-2 | New API endpoints, query methods, performance tests |
| **Phase 3: Frontend Integration** | Week 2 | Analytics store updates, new dashboard widgets |
| **Phase 4: Memory Graph** | Week 2-3 | `MemoryOrbit.svelte`, enhanced `NeuralNetwork.svelte`, legend |
| **Phase 5: Testing & Refinement** | Week 3-4 | Load testing, tuning, documentation |

**Total: 3-4 weeks**

---

## ✅ Success Criteria

### Quantitative
- ✅ **Heuristic accuracy**: >85% department inference matches manual review
- ✅ **Performance**: <50ms overhead for heuristics processing
- ✅ **Dashboard speed**: <500ms to load memory graph data
- ✅ **Visualization**: >30 FPS on mid-range hardware
- ✅ **Storage**: <10% database size increase

### Qualitative
- ✅ Admins identify which departments need more content
- ✅ Query flow patterns visible (e.g., troubleshooting → escalation)
- ✅ Anomalies detected automatically
- ✅ Memory graph is intuitive and visually appealing
- ✅ Actionable insights, not vanity metrics

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Inaccurate department inference | Conservative weights, manual override UI, feedback loop |
| Performance overhead | Profile early, use caching, async processing |
| 3D graph too complex | 2D fallback, interactive tutorial, simplified initial state |
| DB migration fails | Test on staging, rollback script, nullable columns |

---

## 🚀 Future Enhancements (Post-MVP)

1. **Machine Learning**: Train classifier on historical data for better department inference
2. **Real-time Collaboration**: Show multiple users querying same topic
3. **Time-travel Mode**: Replay past 24 hours of query patterns
4. **Query Recommendations**: "Users who asked X also asked Y"
5. **Knowledge Base Health Score**: Per-department score based on repeat rates, frustration

---

## 📝 Files to Create/Modify

### New Files
- `auth/analytics_engine/query_heuristics.py` (new heuristics engine)
- `migrations/add_query_heuristics_columns.sql` (DB schema)
- `frontend/src/lib/components/admin/threlte/MemoryOrbit.svelte` (rotating orbit)

### Modified Files
- `auth/analytics_engine/analytics_service.py` (integrate heuristics)
- `auth/analytics_engine/analytics_routes.py` (new endpoints)
- `frontend/src/lib/stores/analytics.ts` (new data fetching)
- `frontend/src/lib/components/admin/threlte/NeuralNetwork.svelte` (add dept nodes + orbit)
- `frontend/src/lib/components/admin/charts/NerveCenterWidget.svelte` (consume new data)

---

## 💡 Key Insight

**Current State:**
"This query was made while the user had 'HR' selected in the dropdown"

**Proposed State:**
"This query is 0.82 complex, action-oriented, with HIGH urgency, and 78% likely requesting warehouse knowledge (despite HR dropdown selection). User is in a TROUBLESHOOTING_ESCALATION pattern. Similar queries have increased 45% in the last hour."

---

## 🎯 Next Steps

1. **Review this plan** with stakeholders
2. **Approve** implementation approach
3. **Begin Phase 1**: Backend heuristics engine
4. **Iterate** based on real-world usage data

---

**Full technical details:** See `IMPLEMENTATION_PLAN_query_analytics_redesign.md`
