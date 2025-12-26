# Query Heuristics Engine - Quick Reference

## Import

```python
from auth.analytics_engine.query_heuristics import (
    QueryComplexityAnalyzer,
    DepartmentContextAnalyzer,
    QueryPatternDetector
)
```

---

## QueryComplexityAnalyzer

### Initialize
```python
complexity_analyzer = QueryComplexityAnalyzer()
```

### Analyze Query
```python
result = complexity_analyzer.analyze(query_text)
# Returns:
{
    'complexity_score': 0.65,        # 0-1 (0=simple, 1=complex)
    'intent_type': 'ACTION_ORIENTED', # See intent types below
    'specificity_score': 0.8,        # 0-1 (0=generic, 1=specific)
    'temporal_indicator': 'URGENT',   # See urgency levels below
    'multi_part': False               # True if multiple questions/parts
}
```

### Intent Types
- `INFORMATION_SEEKING` - "what is", "tell me about", "explain"
- `ACTION_ORIENTED` - "how do i", "steps to", "guide me"
- `DECISION_SUPPORT` - "should i", "which option", "recommend"
- `VERIFICATION` - "is it correct", "confirm", "verify"

### Urgency Levels
- `URGENT` - "emergency", "asap", "immediately"
- `HIGH` - "today", "now", "urgent"
- `MEDIUM` - "soon", "this week"
- `LOW` - no temporal indicators

---

## DepartmentContextAnalyzer

### Initialize
```python
dept_analyzer = DepartmentContextAnalyzer()
```

### Get Probability Distribution
```python
scores = dept_analyzer.infer_department_context(query_text, keywords)
# Returns: {'warehouse': 0.65, 'safety': 0.20, 'it': 0.15}
```

### Get Primary Department
```python
primary = dept_analyzer.get_primary_department(query_text, keywords)
# Returns: 'warehouse' (or 'general' if no match)
```

### Get Department + Confidence
```python
dept, confidence = dept_analyzer.get_department_confidence(query_text, keywords)
# Returns: ('warehouse', 0.65)
```

### Supported Departments
- `warehouse` - inventory, stock, shipping, receiving, forklift, etc.
- `hr` - payroll, benefits, vacation, pto, onboarding, etc.
- `it` - password, laptop, vpn, network, software, etc.
- `finance` - invoice, payment, expense, budget, reimbursement, etc.
- `safety` - accident, injury, hazard, ppe, osha, incident, etc.
- `maintenance` - repair, equipment, breakdown, preventive, work order, etc.
- `purchasing` - order, supplier, quote, rfq, procurement, etc.
- `general` - fallback when no department matches

---

## QueryPatternDetector

### Initialize (requires DB pool)
```python
from auth.analytics_engine.analytics_service import get_pool

pattern_detector = QueryPatternDetector(get_pool())
```

### Detect Session Pattern
```python
pattern = pattern_detector.detect_query_sequence_pattern(user_email, session_id)
# Returns:
{
    'pattern_type': 'TROUBLESHOOTING_ESCALATION',
    'confidence': 0.85,
    'query_count': 5,
    'details': {'frustration_signals': 2, 'repeat_queries': 3}
}
```

### Pattern Types
- `EXPLORATORY` - Diverse questions across different topics
- `FOCUSED` - Repeated queries on same topic
- `TROUBLESHOOTING_ESCALATION` - Increasing frustration signals
- `ONBOARDING` - Sequential procedural questions
- `MIXED` - No clear pattern
- `SINGLE_QUERY` - Only one query in session

### Detect Department Trends
```python
trends = pattern_detector.detect_department_usage_trends(hours=24)
# Returns:
{
    'peak_hours': [
        {'department': 'warehouse', 'peak_hour': '2025-12-26T14:00:00', 'peak_count': 45}
    ],
    'emerging_topics': [
        {'category': 'TROUBLESHOOTING', 'increase_factor': 2.3}
    ]
}
```

### Detect Anomalies
```python
anomalies = pattern_detector.detect_anomalies()
# Returns:
[
    {
        'type': 'HIGH_REPEAT_RATE',
        'severity': 'WARNING',
        'message': 'Repeat question rate spiked to 45% (normal: 20%)'
    }
]
```

---

## Complete Example

```python
from auth.analytics_engine.query_heuristics import (
    QueryComplexityAnalyzer,
    DepartmentContextAnalyzer,
    QueryPatternDetector
)
from auth.analytics_engine.analytics_service import get_pool

# Initialize analyzers
complexity_analyzer = QueryComplexityAnalyzer()
dept_analyzer = DepartmentContextAnalyzer()
pattern_detector = QueryPatternDetector(get_pool())

# Analyze a query
query = "How do I reset my password ASAP?"
user_email = "user@example.com"
session_id = "session_12345"
keywords = ['reset', 'password']  # From existing keyword extraction

# Get complexity
complexity = complexity_analyzer.analyze(query)
print(f"Complexity: {complexity['complexity_score']:.2f}")
print(f"Intent: {complexity['intent_type']}")
print(f"Urgency: {complexity['temporal_indicator']}")

# Get department
dept_scores = dept_analyzer.infer_department_context(query, keywords)
primary_dept = dept_analyzer.get_primary_department(query, keywords)
print(f"Primary Department: {primary_dept}")
print(f"Confidence: {dept_scores.get(primary_dept, 0):.2f}")

# Get session pattern
pattern = pattern_detector.detect_query_sequence_pattern(user_email, session_id)
print(f"Session Pattern: {pattern['pattern_type']}")
print(f"Query Count: {pattern['query_count']}")

# Store results in database (see Phase 2 implementation)
```

---

## Integration with AnalyticsService

```python
class AnalyticsService:
    def __init__(self):
        self._session_cache = {}

        # Add heuristics analyzers
        self.complexity_analyzer = QueryComplexityAnalyzer()
        self.dept_context_analyzer = DepartmentContextAnalyzer()
        self.pattern_detector = QueryPatternDetector(get_pool())

    def log_query(self, user_email, department, query_text, session_id, ...):
        # Existing classification
        category, keywords = self.classify_query(query_text)

        # NEW: Deep heuristics analysis
        complexity = self.complexity_analyzer.analyze(query_text)
        dept_context = self.dept_context_analyzer.infer_department_context(
            query_text, keywords
        )
        primary_dept = self.dept_context_analyzer.get_primary_department(
            query_text, keywords
        )
        pattern = self.pattern_detector.detect_query_sequence_pattern(
            user_email, session_id
        )

        # Insert into database with new fields
        # complexity['complexity_score']
        # complexity['intent_type']
        # complexity['specificity_score']
        # complexity['temporal_indicator']
        # complexity['multi_part']
        # primary_dept
        # json.dumps(dept_context)
        # pattern['pattern_type']
```

---

## Performance Notes

- **QueryComplexityAnalyzer:** ~1ms per query (regex-based)
- **DepartmentContextAnalyzer:** ~2ms per query (keyword matching)
- **QueryPatternDetector:** ~5ms (cached), ~50ms (DB query)
- **Memory:** Minimal (~100KB for patterns + cache)
- **Cache:** 60s TTL, max 1000 entries

---

## Error Handling

All analyzers handle edge cases gracefully:

```python
# Empty queries
result = complexity_analyzer.analyze("")
# Returns: {'complexity_score': 0.0, 'intent_type': 'INFORMATION_SEEKING', ...}

# Generic queries
dept = dept_analyzer.get_primary_department("Hello")
# Returns: 'general'

# Non-existent sessions
pattern = pattern_detector.detect_query_sequence_pattern("user@x.com", "fake_session")
# Returns: {'pattern_type': 'SINGLE_QUERY', 'query_count': 0, ...}

# Database errors
trends = pattern_detector.detect_department_usage_trends(24)
# Returns: {'error': 'error message'} (if DB connection fails)
```

---

## Testing

Run the test suite:

```bash
python test_query_heuristics.py
```

Expected results:
- Complexity Analyzer: 5/7 tests passing
- Department Analyzer: 8/8 tests passing
- Pattern Detector: Works (requires DB migration)

---

## Next Steps

1. **Phase 2:** Run database migration to add new columns
2. **Phase 3:** Update `analytics_service.log_query()` to use heuristics
3. **Phase 4:** Add new API routes for dashboard
4. **Phase 5:** Update frontend to display new insights

---

**Reference:** See `PHASE1_IMPLEMENTATION_SUMMARY.md` for detailed documentation
