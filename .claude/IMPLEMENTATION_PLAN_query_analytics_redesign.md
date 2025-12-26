# Query Analytics Redesign - Implementation Plan

**Date:** 2025-12-26
**Objective:** Redesign metrics and analytics to be heuristics-based on actual query content/patterns rather than dropdown selections, integrate with existing observability infrastructure, and connect to the 3D rotating memory graph in Nerve Center.

---

## Current State Analysis

### Problem Identified
The current analytics system tracks queries based on the **dropdown division selector** in the chat pane. This provides limited insight because:
- **Division/department selection is manual** - Users select from `DepartmentSelector.svelte` which feeds `session.currentDivision`
- **Query classification happens on query text** - Already implemented via regex patterns in `analytics_service.py` (PROCEDURAL, LOOKUP, TROUBLESHOOTING, etc.)
- **But dashboard categories show query classifications, not divisions** - The existing `get_category_breakdown()` groups by `query_category`

### Current Data Flow (for context)
```
User sends message → ChatOverlay → session.sendMessage()
    ↓
WebSocket payload: { type: 'message', content, division, file_ids, language }
    ↓
Backend websocket handler
    ↓
analytics_service.log_query(user_email, department, query_text, ...)
    ↓
classify_query(query_text) → (category, keywords)
detect_frustration(query_text) → signals[]
is_repeat_question(user_email, query_text) → (bool, query_id)
    ↓
Stored in enterprise.query_log table with:
- query_category (PROCEDURAL, LOOKUP, etc.)
- query_keywords (extracted nouns)
- frustration_signals
- is_repeat_question, repeat_of_query_id
- query_position_in_session, time_since_last_query_ms
```

### What's Already Good
- ✅ **Query classification** - Already heuristics-based via regex patterns
- ✅ **Keyword extraction** - Nouns extracted from query text
- ✅ **Frustration detection** - Pattern matching for user frustration
- ✅ **Repeat question detection** - Jaccard similarity on recent queries
- ✅ **Session tracking** - Query position, time between queries
- ✅ **Observability infrastructure** - Traces, logs, metrics collectors all wired up
- ✅ **3D Nerve Center** - Already visualizes query categories as neural nodes

### What Needs Enhancement
1. **Department usage tracking** - Currently tracks `department` field (from division dropdown), but we want to track which **department's knowledge base** is actually being queried, not just which dropdown was selected
2. **Query intent analysis** - Expand heuristics beyond categories to include:
   - Query complexity (simple lookup vs multi-step reasoning)
   - Information seeking vs action-oriented
   - Specificity scores
3. **Pattern detection** - Add temporal patterns:
   - Peak usage times per department
   - Common query flows/sequences
   - Anomaly detection
4. **Memory graph integration** - Connect query patterns to rotating memory graph (t3d asset)

---

## Proposed Architecture

### 1. Enhanced Query Heuristics Engine

**New File:** `auth/analytics_engine/query_heuristics.py`

**Purpose:** Deep analysis of query content beyond simple categorization

**Components:**

#### A. Query Complexity Analyzer
```python
class QueryComplexityAnalyzer:
    """Analyze query complexity and intent."""

    def analyze(self, query_text: str) -> Dict[str, Any]:
        return {
            'complexity_score': self._calculate_complexity(query_text),
            'intent_type': self._detect_intent(query_text),
            'specificity_score': self._calculate_specificity(query_text),
            'temporal_indicator': self._detect_temporal_urgency(query_text),
            'multi_part': self._detect_multi_part(query_text),
        }

    def _calculate_complexity(self, query_text: str) -> float:
        """Score 0-1 based on:
        - Sentence count
        - Question depth (how many sub-questions)
        - Conditional phrases ("if...then", "depending on")
        - Multi-criteria requests
        """

    def _detect_intent(self, query_text: str) -> str:
        """Categorize intent:
        - INFORMATION_SEEKING: "what is", "tell me about"
        - ACTION_ORIENTED: "how do i", "steps to"
        - DECISION_SUPPORT: "should i", "which option"
        - VERIFICATION: "is it correct", "confirm"
        """

    def _calculate_specificity(self, query_text: str) -> float:
        """Score 0-1 based on:
        - Named entities (product codes, names, dates)
        - Numerical values
        - Specific technical terms vs generic terms
        """

    def _detect_temporal_urgency(self, query_text: str) -> str:
        """LOW, MEDIUM, HIGH, URGENT based on keywords:
        - URGENT: "immediately", "asap", "emergency"
        - HIGH: "today", "now", "urgent"
        - MEDIUM: "soon", "this week"
        - LOW: no temporal indicators
        """

    def _detect_multi_part(self, query_text: str) -> bool:
        """Detect if query has multiple parts:
        - Multiple questions
        - "and also", "additionally"
        - Numbered lists
        """
```

#### B. Department Knowledge Context Analyzer
```python
class DepartmentContextAnalyzer:
    """Infer which department's knowledge is being queried based on content."""

    # Department-specific keyword dictionaries
    DEPARTMENT_SIGNALS = {
        'warehouse': ['inventory', 'stock', 'shipping', 'receiving', 'pallet', 'forklift'],
        'hr': ['payroll', 'benefits', 'vacation', 'pto', 'onboarding', 'performance review'],
        'it': ['password', 'laptop', 'vpn', 'network', 'software', 'access', 'ticket'],
        'finance': ['invoice', 'payment', 'expense', 'budget', 'reimbursement', 'po'],
        'safety': ['accident', 'injury', 'hazard', 'ppe', 'osha', 'incident', 'lockout'],
        'maintenance': ['repair', 'equipment', 'breakdown', 'preventive', 'work order'],
    }

    def infer_department_context(self, query_text: str, keywords: List[str]) -> Dict[str, float]:
        """Return probability distribution over departments based on query content.

        Returns:
            {'warehouse': 0.8, 'safety': 0.15, 'hr': 0.05, ...}
        """
        scores = {}
        query_lower = query_text.lower()

        for dept, signals in self.DEPARTMENT_SIGNALS.items():
            # Count signal matches
            match_count = sum(1 for signal in signals if signal in query_lower)
            # Normalize by signal count
            scores[dept] = match_count / len(signals)

        # Normalize to probability distribution
        total = sum(scores.values())
        if total > 0:
            scores = {k: v/total for k, v in scores.items()}

        return scores

    def get_primary_department(self, query_text: str, keywords: List[str]) -> str:
        """Return most likely department based on content."""
        scores = self.infer_department_context(query_text, keywords)
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return 'general'
```

#### C. Query Pattern Detector
```python
class QueryPatternDetector:
    """Detect temporal patterns and anomalies in query behavior."""

    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.pattern_cache = {}  # Cache recent pattern analysis

    def detect_query_sequence_pattern(self, user_email: str, session_id: str) -> Dict[str, Any]:
        """Analyze the sequence of queries in a session.

        Returns patterns like:
        - EXPLORATORY: many diverse questions
        - FOCUSED: repeated queries on same topic
        - TROUBLESHOOTING_ESCALATION: questions getting more frustrated
        - ONBOARDING: procedural questions in sequence
        """

    def detect_department_usage_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze department query trends over time.

        Returns:
        - Peak usage times per department
        - Emerging topics (sudden spike in category)
        - Declining topics
        - Cross-department query flows
        """

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalous query patterns:
        - Sudden spike in error rate
        - Unusual query volume
        - New query categories appearing
        - Repeated failed queries (same user, same question)
        """
```

---

### 2. Enhanced Analytics Service

**Modify:** `auth/analytics_engine/analytics_service.py`

**Changes:**

```python
from .query_heuristics import (
    QueryComplexityAnalyzer,
    DepartmentContextAnalyzer,
    QueryPatternDetector
)

class AnalyticsService:
    def __init__(self):
        self._session_cache = {}

        # NEW: Heuristics engines
        self.complexity_analyzer = QueryComplexityAnalyzer()
        self.dept_context_analyzer = DepartmentContextAnalyzer()
        self.pattern_detector = QueryPatternDetector(get_pool())

    def log_query(
        self,
        user_email: str,
        department: str,  # This is dropdown selection
        query_text: str,
        session_id: str,
        response_time_ms: int,
        response_length: int,
        tokens_input: int,
        tokens_output: int,
        model_used: str,
        user_id: Optional[str] = None,
    ) -> str:
        """Enhanced query logging with deep heuristics."""

        # Existing classification
        category, keywords = self.classify_query(query_text)
        frustration = self.detect_frustration(query_text)
        is_repeat, repeat_of = self.is_repeat_question(user_email, query_text)

        # NEW: Deep analysis
        complexity = self.complexity_analyzer.analyze(query_text)
        dept_context = self.dept_context_analyzer.infer_department_context(query_text, keywords)
        primary_dept_inferred = self.dept_context_analyzer.get_primary_department(query_text, keywords)

        # Session tracking (existing)
        session_data = self._session_cache.get(session_id, {"query_count": 0, "last_query_time": None})
        query_position = session_data["query_count"] + 1

        # NEW: Pattern detection
        sequence_pattern = self.pattern_detector.detect_query_sequence_pattern(user_email, session_id)

        # Update session cache
        self._session_cache[session_id] = {
            "query_count": query_position,
            "last_query_time": datetime.utcnow()
        }

        with self._get_cursor() as cur:
            cur.execute(f"""
                INSERT INTO {SCHEMA}.query_log (
                    user_id, user_email, department, session_id,
                    query_text, query_length, query_word_count,
                    query_category, query_keywords,
                    frustration_signals, is_repeat_question, repeat_of_query_id,
                    response_time_ms, response_length, tokens_input, tokens_output, model_used,
                    query_position_in_session, time_since_last_query_ms,
                    -- NEW FIELDS
                    complexity_score, intent_type, specificity_score, temporal_urgency,
                    is_multi_part, department_context_inferred, department_context_scores,
                    session_pattern
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s
                )
                RETURNING id
            """, (
                user_id, user_email, department, session_id,
                query_text, len(query_text), len(query_text.split()),
                category, keywords,
                frustration if frustration else None, is_repeat, repeat_of,
                response_time_ms, response_length, tokens_input, tokens_output, model_used,
                query_position, time_since_last,
                # NEW VALUES
                complexity['complexity_score'], complexity['intent_type'],
                complexity['specificity_score'], complexity['temporal_indicator'],
                complexity['multi_part'], primary_dept_inferred, json.dumps(dept_context),
                sequence_pattern['pattern_type']
            ))

            result = cur.fetchone()
            query_id = str(result['id'])

            logger.info(f"[ANALYTICS] Query logged: {category} | complexity={complexity['complexity_score']:.2f} | inferred_dept={primary_dept_inferred}")
            return query_id
```

**New Dashboard Query Methods:**

```python
@timed
def get_department_usage_by_content(self, hours: int = 24) -> List[Dict[str, Any]]:
    """Get department usage based on INFERRED content, not dropdown selection."""
    with self._get_cursor() as cur:
        cur.execute(f"""
            SELECT
                department_context_inferred as department,
                COUNT(*) as query_count,
                COUNT(DISTINCT user_email) as unique_users,
                AVG(complexity_score) as avg_complexity,
                AVG(response_time_ms) as avg_response_time
            FROM {SCHEMA}.query_log
            WHERE created_at > NOW() - INTERVAL '{hours} hours'
              AND department_context_inferred IS NOT NULL
            GROUP BY department_context_inferred
            ORDER BY query_count DESC
        """)

        return [{
            "department": row['department'],
            "query_count": row['query_count'],
            "unique_users": row['unique_users'],
            "avg_complexity": round(row['avg_complexity'] or 0, 2),
            "avg_response_time_ms": round(row['avg_response_time'] or 0, 0)
        } for row in cur.fetchall()]

@timed
def get_query_intent_breakdown(self, hours: int = 24) -> List[Dict[str, Any]]:
    """Get breakdown by query intent type."""
    with self._get_cursor() as cur:
        cur.execute(f"""
            SELECT
                intent_type,
                COUNT(*) as count,
                AVG(complexity_score) as avg_complexity
            FROM {SCHEMA}.query_log
            WHERE created_at > NOW() - INTERVAL '{hours} hours'
            GROUP BY intent_type
            ORDER BY count DESC
        """)

        return [{"intent": row['intent_type'], "count": row['count'], "complexity": round(row['avg_complexity'], 2)} for row in cur.fetchall()]

@timed
def get_temporal_urgency_distribution(self, hours: int = 24) -> Dict[str, int]:
    """Get distribution of query urgency."""
    with self._get_cursor() as cur:
        cur.execute(f"""
            SELECT
                temporal_urgency,
                COUNT(*) as count
            FROM {SCHEMA}.query_log
            WHERE created_at > NOW() - INTERVAL '{hours} hours'
            GROUP BY temporal_urgency
        """)

        return {row['temporal_urgency']: row['count'] for row in cur.fetchall()}
```

---

### 3. Database Schema Migration

**New File:** `migrations/add_query_heuristics_columns.sql`

```sql
-- Add new columns to query_log table for enhanced heuristics

ALTER TABLE enterprise.query_log
ADD COLUMN IF NOT EXISTS complexity_score FLOAT,
ADD COLUMN IF NOT EXISTS intent_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS specificity_score FLOAT,
ADD COLUMN IF NOT EXISTS temporal_urgency VARCHAR(20),
ADD COLUMN IF NOT EXISTS is_multi_part BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS department_context_inferred VARCHAR(100),
ADD COLUMN IF NOT EXISTS department_context_scores JSONB,
ADD COLUMN IF NOT EXISTS session_pattern VARCHAR(50);

-- Add indexes for new query patterns
CREATE INDEX IF NOT EXISTS idx_query_log_dept_context ON enterprise.query_log(department_context_inferred);
CREATE INDEX IF NOT EXISTS idx_query_log_intent_type ON enterprise.query_log(intent_type);
CREATE INDEX IF NOT EXISTS idx_query_log_complexity ON enterprise.query_log(complexity_score);
CREATE INDEX IF NOT EXISTS idx_query_log_temporal_urgency ON enterprise.query_log(temporal_urgency);

-- Add GIN index for JSONB department context scores (for efficient JSON queries)
CREATE INDEX IF NOT EXISTS idx_query_log_dept_scores_gin ON enterprise.query_log USING GIN(department_context_scores);

COMMENT ON COLUMN enterprise.query_log.complexity_score IS 'Query complexity score (0-1) based on sentence count, depth, conditionals';
COMMENT ON COLUMN enterprise.query_log.intent_type IS 'Query intent: INFORMATION_SEEKING, ACTION_ORIENTED, DECISION_SUPPORT, VERIFICATION';
COMMENT ON COLUMN enterprise.query_log.specificity_score IS 'Query specificity score (0-1) based on named entities, numbers, technical terms';
COMMENT ON COLUMN enterprise.query_log.temporal_urgency IS 'Urgency level: LOW, MEDIUM, HIGH, URGENT';
COMMENT ON COLUMN enterprise.query_log.is_multi_part IS 'Whether query contains multiple questions or parts';
COMMENT ON COLUMN enterprise.query_log.department_context_inferred IS 'Department inferred from query content (primary)';
COMMENT ON COLUMN enterprise.query_log.department_context_scores IS 'Probability distribution over all departments (JSON)';
COMMENT ON COLUMN enterprise.query_log.session_pattern IS 'Detected session pattern: EXPLORATORY, FOCUSED, TROUBLESHOOTING_ESCALATION, ONBOARDING';
```

---

### 4. Nerve Center - Rotating Memory Graph Integration

**Concept:** The 3D neural network already visualizes query categories. We'll enhance it to become a "rotating memory graph" that shows:
- **Query flow through departments** (based on inferred context)
- **Memory persistence** (frequently queried topics)
- **Temporal patterns** (peak usage times, emerging topics)

**Modify:** `frontend/src/lib/components/admin/threlte/NeuralNetwork.svelte`

**Changes:**

```svelte
<script lang="ts">
    import { T } from '@threlte/core';
    import NeuralNode from './NeuralNode.svelte';
    import DataSynapse from './DataSynapse.svelte';
    import MemoryOrbit from './MemoryOrbit.svelte';  // NEW

    export let categories: Array<{ category: string; count: number }> = [];
    export let totalQueries: number = 0;
    export let activeUsers: number = 0;
    export let departmentUsage: Array<{ department: string; query_count: number; avg_complexity: number }> = [];  // NEW
    export let queryIntents: Array<{ intent: string; count: number; complexity: number }> = [];  // NEW
    export let temporalPatterns: any = null;  // NEW

    // Existing category node positions (unchanged)
    const categoryPositions: Record<string, [number, number, number]> = { ... };

    // NEW: Department memory nodes (outer orbit)
    const departmentPositions: Record<string, [number, number, number]> = {
        'warehouse': [5, 2, 0],
        'hr': [3.5, 3.5, 3.5],
        'it': [-3.5, 3.5, 3.5],
        'finance': [-5, 2, 0],
        'safety': [-3.5, -3.5, 3.5],
        'maintenance': [3.5, -3.5, 3.5],
        'general': [0, 0, 5]
    };

    // NEW: Memory orbit rotation
    let orbitRotation = 0;
    $: orbitRotation += 0.001;  // Slow rotation

    // Calculate department node sizes based on INFERRED usage
    function getDepartmentNodeSize(dept: string): number {
        const usage = departmentUsage.find(d => d.department === dept);
        if (!usage) return 0.3;
        const totalDeptQueries = departmentUsage.reduce((sum, d) => sum + d.query_count, 0);
        const ratio = usage.query_count / totalDeptQueries;
        return 0.5 + ratio * 2;  // Scale between 0.5 and 2.5
    }

    // Calculate department node color based on complexity
    function getDepartmentColor(dept: string): string {
        const usage = departmentUsage.find(d => d.department === dept);
        if (!usage) return '#888888';

        // Color gradient: low complexity = cyan, high complexity = red
        const complexity = usage.avg_complexity || 0;
        if (complexity < 0.3) return '#00ffff';  // Cyan (simple)
        if (complexity < 0.6) return '#ffaa00';  // Orange (medium)
        return '#ff0055';  // Red (complex)
    }

    // Flow connections: category nodes → department memory nodes
    function getCategoryToDeptFlows(): Array<[string, string, number]> {
        // This would be calculated from actual query logs showing
        // which categories led to which department contexts
        // For now, hardcode some logical flows
        return [
            ['PROCEDURAL', 'warehouse', 0.6],
            ['LOOKUP', 'it', 0.7],
            ['TROUBLESHOOTING', 'it', 0.8],
            ['SAFETY', 'safety', 0.9],
            ['POLICY', 'hr', 0.7],
            // ... more flows
        ];
    }
</script>

<T.Group>
    <!-- Existing central core (unchanged) -->
    <T.Group position={[0, 0, 0]}>
        <!-- ... existing core visualization ... -->
    </T.Group>

    <!-- Existing category nodes (inner sphere) -->
    {#each Object.entries(categoryPositions) as [category, position]}
        <NeuralNode
            {position}
            color={categoryColors[category] || '#888888'}
            size={getNodeSize(category)}
            activity={getActivity(category)}
            pulseSpeed={1 + networkActivity}
        />
    {/each}

    <!-- NEW: Department memory nodes (outer orbit - ROTATING) -->
    <T.Group rotation={[0, orbitRotation, 0]}>
        {#each Object.entries(departmentPositions) as [dept, position]}
            <NeuralNode
                {position}
                color={getDepartmentColor(dept)}
                size={getDepartmentNodeSize(dept)}
                activity={getDepartmentActivity(dept)}
                pulseSpeed={0.5}
                label={dept.toUpperCase()}
            />
        {/each}

        <!-- Memory orbit ring -->
        <MemoryOrbit
            radius={6}
            segments={64}
            color="#00ff41"
            opacity={0.2}
        />
    </T.Group>

    <!-- Existing category synapses (unchanged) -->
    {#each synapseConnections as [from, to]}
        <DataSynapse
            start={categoryPositions[from]}
            end={categoryPositions[to]}
            color={categoryColors[from]}
            activity={Math.max(getActivity(from), getActivity(to)) * networkActivity}
        />
    {/each}

    <!-- NEW: Category → Department flow lines (shows query journey) -->
    {#each getCategoryToDeptFlows() as [category, dept, strength]}
        <DataSynapse
            start={categoryPositions[category]}
            end={departmentPositions[dept]}
            color={categoryColors[category]}
            activity={strength}
            flowSpeed={1.5}
            dashed={true}
        />
    {/each}
</T.Group>
```

**New Component:** `frontend/src/lib/components/admin/threlte/MemoryOrbit.svelte`

```svelte
<!--
  MemoryOrbit - Rotating orbital ring showing "memory persistence"

  Props:
    radius: number - orbit radius
    segments: number - smoothness of circle
    color: string - line color
    opacity: number - transparency
-->

<script lang="ts">
    import { T } from '@threlte/core';
    import * as THREE from 'three';

    export let radius: number = 5;
    export let segments: number = 64;
    export let color: string = '#00ff41';
    export let opacity: number = 0.3;

    // Create circle geometry
    const curve = new THREE.EllipseCurve(
        0, 0,           // center x, y
        radius, radius, // xRadius, yRadius
        0, 2 * Math.PI, // start, end angle
        false,          // clockwise
        0               // rotation
    );

    const points = curve.getPoints(segments);
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
</script>

<T.Group rotation={[Math.PI / 2, 0, 0]}>
    <T.Line {geometry}>
        <T.LineBasicMaterial {color} transparent {opacity} />
    </T.Line>
</T.Group>
```

---

### 5. Enhanced Analytics Dashboard Routes

**Modify:** `auth/analytics_engine/analytics_routes.py`

**Add new endpoints:**

```python
@router.get("/api/admin/analytics/department-usage-inferred")
async def get_department_usage_inferred(
    hours: int = Query(24, ge=1, le=168),
    user: dict = Depends(require_admin)
):
    """
    Get department usage based on INFERRED content analysis,
    not dropdown selection.
    """
    analytics = get_analytics_service()
    return analytics.get_department_usage_by_content(hours)

@router.get("/api/admin/analytics/query-intents")
async def get_query_intents(
    hours: int = Query(24, ge=1, le=168),
    user: dict = Depends(require_admin)
):
    """Get breakdown of query intents (INFORMATION_SEEKING, ACTION_ORIENTED, etc.)."""
    analytics = get_analytics_service()
    return analytics.get_query_intent_breakdown(hours)

@router.get("/api/admin/analytics/complexity-distribution")
async def get_complexity_distribution(
    hours: int = Query(24, ge=1, le=168),
    user: dict = Depends(require_admin)
):
    """Get distribution of query complexity scores."""
    analytics = get_analytics_service()
    # Implementation similar to get_category_breakdown but for complexity bins
    return analytics.get_complexity_distribution(hours)

@router.get("/api/admin/analytics/temporal-patterns")
async def get_temporal_patterns(
    hours: int = Query(24, ge=1, le=168),
    user: dict = Depends(require_admin)
):
    """Get temporal usage patterns (peak hours, emerging topics, etc.)."""
    analytics = get_analytics_service()
    pattern_detector = analytics.pattern_detector
    return pattern_detector.detect_department_usage_trends(hours)

@router.get("/api/admin/analytics/memory-graph-data")
async def get_memory_graph_data(
    hours: int = Query(24, ge=1, le=168),
    user: dict = Depends(require_admin)
):
    """
    Combined endpoint for rotating memory graph (t3d asset).
    Returns all data needed for Nerve Center visualization.
    """
    analytics = get_analytics_service()

    return {
        "categories": analytics.get_category_breakdown(hours),
        "departments": analytics.get_department_usage_by_content(hours),
        "intents": analytics.get_query_intent_breakdown(hours),
        "temporal_patterns": analytics.pattern_detector.detect_department_usage_trends(hours),
        "overview": analytics.get_overview_stats(hours),
        "urgency_distribution": analytics.get_temporal_urgency_distribution(hours),
    }
```

---

### 6. Frontend Store Updates

**Modify:** `frontend/src/lib/stores/analytics.ts`

**Add new derived stores:**

```typescript
export interface DepartmentUsageInferred {
    department: string;
    query_count: number;
    unique_users: number;
    avg_complexity: number;
    avg_response_time_ms: number;
}

export interface QueryIntent {
    intent: string;
    count: number;
    complexity: number;
}

export interface MemoryGraphData {
    categories: Array<{ category: string; count: number }>;
    departments: DepartmentUsageInferred[];
    intents: QueryIntent[];
    temporal_patterns: any;
    overview: OverviewStats;
    urgency_distribution: Record<string, number>;
}

class AnalyticsStore {
    // ... existing code ...

    departmentUsageInferred = writable<DepartmentUsageInferred[]>([]);
    queryIntents = writable<QueryIntent[]>([]);
    memoryGraphData = writable<MemoryGraphData | null>(null);

    async loadDepartmentUsageInferred(hours: number = 24) {
        try {
            const res = await fetch(`/api/admin/analytics/department-usage-inferred?hours=${hours}`, {
                credentials: 'include'
            });
            if (res.ok) {
                const data = await res.json();
                this.departmentUsageInferred.set(data);
            }
        } catch (err) {
            console.error('[Analytics] Failed to load inferred department usage:', err);
        }
    }

    async loadQueryIntents(hours: number = 24) {
        try {
            const res = await fetch(`/api/admin/analytics/query-intents?hours=${hours}`, {
                credentials: 'include'
            });
            if (res.ok) {
                const data = await res.json();
                this.queryIntents.set(data);
            }
        } catch (err) {
            console.error('[Analytics] Failed to load query intents:', err);
        }
    }

    async loadMemoryGraphData(hours: number = 24) {
        try {
            const res = await fetch(`/api/admin/analytics/memory-graph-data?hours=${hours}`, {
                credentials: 'include'
            });
            if (res.ok) {
                const data = await res.json();
                this.memoryGraphData.set(data);
            }
        } catch (err) {
            console.error('[Analytics] Failed to load memory graph data:', err);
        }
    }
}
```

**Update auto-refresh to include new endpoints:**

```typescript
async refreshAll() {
    await Promise.all([
        this.loadOverview(this.periodHours),
        this.loadQueriesByHour(this.periodHours),
        this.loadCategories(this.periodHours),
        this.loadDepartments(this.periodHours),
        this.loadDepartmentUsageInferred(this.periodHours),  // NEW
        this.loadQueryIntents(this.periodHours),  // NEW
        this.loadMemoryGraphData(this.periodHours),  // NEW
        this.loadErrors(),
        this.loadRealtime()
    ]);
}
```

---

### 7. Nerve Center Widget Update

**Modify:** `frontend/src/lib/components/admin/charts/NerveCenterWidget.svelte`

```svelte
<script lang="ts">
    import { analyticsStore } from '$lib/stores/analytics';
    import NerveCenterScene from '../threlte/NerveCenterScene.svelte';

    $: memoryGraphData = $analyticsStore.memoryGraphData;
    $: categories = memoryGraphData?.categories || [];
    $: departments = memoryGraphData?.departments || [];
    $: intents = memoryGraphData?.intents || [];
    $: overview = memoryGraphData?.overview || { active_users: 0, total_queries: 0 };
</script>

<div class="nerve-center-widget">
    <div class="widget-header">
        <h3>🧠 Nerve Center - Rotating Memory Graph</h3>
        <div class="stats">
            <span>{overview.total_queries} queries</span>
            <span>{overview.active_users} active users</span>
        </div>
    </div>

    <div class="scene-container">
        <NerveCenterScene
            {categories}
            departmentUsage={departments}
            queryIntents={intents}
            totalQueries={overview.total_queries}
            activeUsers={overview.active_users}
            temporalPatterns={memoryGraphData?.temporal_patterns}
        />
    </div>

    <!-- Legend -->
    <div class="legend">
        <div class="legend-section">
            <h4>Inner Sphere: Query Categories</h4>
            <p>Size = query volume | Color = category type</p>
        </div>
        <div class="legend-section">
            <h4>Outer Orbit (Rotating): Department Memory</h4>
            <p>Size = inferred usage | Color = complexity (cyan=simple, red=complex)</p>
        </div>
        <div class="legend-section">
            <h4>Flow Lines: Query Journey</h4>
            <p>Shows how query categories map to department contexts</p>
        </div>
    </div>
</div>

<style>
    .nerve-center-widget {
        background: rgba(0, 0, 0, 0.8);
        border: 1px solid #00ff41;
        border-radius: 8px;
        padding: 1rem;
    }

    .widget-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }

    .widget-header h3 {
        color: #00ff41;
        font-family: 'Courier New', monospace;
        margin: 0;
    }

    .stats {
        display: flex;
        gap: 1rem;
        font-size: 0.9rem;
        color: #00ffff;
    }

    .scene-container {
        height: 500px;
        border-radius: 4px;
        overflow: hidden;
    }

    .legend {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid rgba(0, 255, 65, 0.3);
    }

    .legend-section h4 {
        color: #00ff41;
        font-size: 0.85rem;
        margin: 0 0 0.25rem 0;
    }

    .legend-section p {
        color: #888;
        font-size: 0.75rem;
        margin: 0;
    }
</style>
```

---

## Implementation Steps

### Phase 1: Backend Heuristics Engine (Week 1)
1. ✅ Create `query_heuristics.py` with:
   - `QueryComplexityAnalyzer`
   - `DepartmentContextAnalyzer`
   - `QueryPatternDetector`
2. ✅ Run database migration to add new columns
3. ✅ Update `analytics_service.log_query()` to call heuristics
4. ✅ Add unit tests for heuristics analyzers
5. ✅ Verify data is being collected correctly (check PostgreSQL logs)

### Phase 2: Enhanced Analytics Queries (Week 1-2)
1. ✅ Add new dashboard query methods to `AnalyticsService`
2. ✅ Add new API routes in `analytics_routes.py`
3. ✅ Test endpoints with Postman/curl
4. ✅ Verify query performance (should be <100ms)
5. ✅ Add indexes if needed

### Phase 3: Frontend Integration (Week 2)
1. ✅ Update `analytics.ts` store with new methods
2. ✅ Create new dashboard widgets for:
   - Department usage (inferred)
   - Query intent breakdown
   - Complexity distribution
3. ✅ Test data flow: backend → store → UI
4. ✅ Add loading states and error handling

### Phase 4: Nerve Center Memory Graph (Week 2-3)
1. ✅ Create `MemoryOrbit.svelte` component
2. ✅ Update `NeuralNetwork.svelte` with:
   - Department memory nodes
   - Rotating orbit
   - Flow lines
3. ✅ Update `NerveCenterWidget.svelte` to consume new data
4. ✅ Fine-tune 3D positioning and animations
5. ✅ Add legend and tooltips

### Phase 5: Testing & Refinement (Week 3-4)
1. ✅ Load test with synthetic query data
2. ✅ Verify memory graph rotates smoothly
3. ✅ Tune heuristic weights based on real usage
4. ✅ Add anomaly detection alerts
5. ✅ Performance profiling (ensure <5% CPU overhead)
6. ✅ Documentation and user guide

---

## Success Metrics

### Quantitative
- **Heuristic accuracy**: >85% department context inference matches manual review
- **Query response time**: <50ms overhead for heuristics processing
- **Dashboard load time**: <500ms for memory graph data endpoint
- **Memory graph FPS**: >30 FPS on mid-range hardware
- **Data storage growth**: <10% increase in database size

### Qualitative
- ✅ Admins can identify which departments need more knowledge base content
- ✅ Patterns visible in query flows (e.g., troubleshooting → escalation)
- ✅ Anomalies detected automatically (sudden spike in errors)
- ✅ Memory graph is intuitive and visually appealing
- ✅ System provides actionable insights, not just vanity metrics

---

## Integration with Observability Stack

### Traces
- Each heuristic analysis gets a trace span
- `create_span('query_heuristics')` with tags:
  - `complexity_score`
  - `inferred_department`
  - `intent_type`

### Logs
- Structured logs for pattern detection:
  - `logger.info('[PATTERN] Detected spike in TROUBLESHOOTING queries for IT department')`
  - `logger.warning('[ANOMALY] Repeat question rate exceeds 30%')`

### Metrics
- Add to `metrics_collector.py`:
  - `record_query_complexity(score: float)`
  - `record_department_inference(dept: str, confidence: float)`
  - Ring buffers for complexity distribution

### Alerts
- New alert rules (via `alerting_routes.py`):
  - `high_complexity_queries`: Trigger if avg complexity >0.8 for 10 minutes
  - `department_inference_low_confidence`: Trigger if <50% queries have >0.5 confidence
  - `repeat_question_spike`: Trigger if repeat rate >40%

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Heuristics produce inaccurate department inferences | Medium | Start with conservative weights, add manual override UI for admins to correct misclassifications, implement feedback loop |
| Performance overhead from complex analysis | Medium | Profile early, use caching for repeated patterns, make heuristics async if needed |
| 3D memory graph is too complex for users | Low | Provide 2D fallback view, add interactive tutorial, simplify initial state |
| Database schema migration fails on production | High | Test migration on staging first, add rollback script, make columns nullable initially |
| New metrics overwhelm observability dashboard | Low | Use progressive disclosure, hide advanced metrics behind toggle, provide presets |

---

## Future Enhancements (Post-MVP)

1. **Machine Learning Integration**
   - Train classifier on historical data for better department inference
   - Predict query intent with higher accuracy
   - Anomaly detection using ML (Isolation Forest)

2. **Real-time Collaboration Insights**
   - Show multiple users querying same topic
   - Suggest related queries from other users
   - Knowledge gap detection (many queries, few answers)

3. **Memory Graph Enhancements**
   - Time-travel mode (replay past 24 hours)
   - Heatmap overlay showing peak usage
   - Predictive mode (forecast next query patterns)

4. **Query Recommendation Engine**
   - "Users who asked X also asked Y"
   - Proactive suggestions based on session pattern
   - Auto-complete powered by heuristics

5. **Knowledge Base Health Score**
   - Per-department score based on:
     - Repeat question rate
     - Avg response time
     - Frustration signals
   - Automated alerts to content owners

---

## Conclusion

This plan transforms the analytics system from tracking **dropdown selections** to tracking **actual query content and patterns**. The rotating memory graph in Nerve Center becomes a true "digital twin brain" showing:
- **What departments are actually being queried** (inferred from content)
- **How complex queries are** (requiring different levels of response)
- **Where knowledge gaps exist** (high repeat rates, frustration signals)
- **Temporal patterns** (peak usage, emerging topics)

The implementation fits seamlessly into the existing observability infrastructure (traces, logs, metrics, alerts) and provides actionable insights for improving knowledge base content and user experience.

**Next Steps:** Review this plan, get stakeholder approval, then begin Phase 1 implementation.
