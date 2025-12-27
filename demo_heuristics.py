"""
Interactive Demo - Query Heuristics Engine

This script provides an interactive demonstration of the heuristics engine
with real-world query examples.

Run with: python demo_heuristics.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth.analytics_engine.query_heuristics import (
    QueryComplexityAnalyzer,
    DepartmentContextAnalyzer,
    QueryPatternDetector
)
from auth.analytics_engine.analytics_service import get_pool
import json


def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(label, value, indent=2):
    """Print formatted result."""
    spaces = " " * indent
    if isinstance(value, dict):
        print(f"{spaces}{label}:")
        for k, v in value.items():
            if isinstance(v, float):
                print(f"{spaces}  {k}: {v:.3f}")
            else:
                print(f"{spaces}  {k}: {v}")
    elif isinstance(value, float):
        print(f"{spaces}{label}: {value:.3f}")
    else:
        print(f"{spaces}{label}: {value}")


def demo_complexity_analyzer():
    """Demonstrate QueryComplexityAnalyzer with real-world examples."""
    print_header("QueryComplexityAnalyzer - Real-World Examples")

    analyzer = QueryComplexityAnalyzer()

    examples = [
        ("Simple Lookup", "What is a forklift?"),
        ("Action Request", "How do I reset my password?"),
        ("Urgent Request", "Need to process return #12345 ASAP!"),
        ("Complex Multi-Part", "How do I file a safety incident? Also, who do I contact? And what forms do I need?"),
        ("Decision Support", "Should I use vendor A or vendor B for this purchase?"),
        ("Verification", "Is it correct that new hires get 15 days PTO?"),
        ("Conditional Query", "If the stock level drops below 100, how do I trigger an automatic reorder?"),
    ]

    for title, query in examples:
        print(f"\n📝 {title}")
        print(f"   Query: \"{query}\"")
        print()

        result = analyzer.analyze(query)

        print_result("Complexity Score", result['complexity_score'])
        print_result("Intent Type", result['intent_type'])
        print_result("Specificity Score", result['specificity_score'])
        print_result("Temporal Urgency", result['temporal_indicator'])
        print_result("Multi-Part Query", result['multi_part'])


def demo_department_analyzer():
    """Demonstrate DepartmentContextAnalyzer with real-world examples."""
    print_header("DepartmentContextAnalyzer - Real-World Examples")

    analyzer = DepartmentContextAnalyzer()

    examples = [
        ("IT Request", "Can't access VPN, need password reset for laptop login", ['vpn', 'password', 'laptop']),
        ("Warehouse Query", "Where is the inventory for SKU-9876 located? Which bin and aisle?", ['inventory', 'sku', 'bin', 'aisle']),
        ("Safety Incident", "Worker injured by forklift, need to file incident report immediately", ['injured', 'forklift', 'incident']),
        ("HR Question", "When do I get paid? Also need info on 401k enrollment", ['paid', '401k', 'enrollment']),
        ("Finance Request", "Need to submit expense reimbursement for business travel", ['expense', 'reimbursement']),
        ("Maintenance Issue", "Conveyor belt broken, needs repair ASAP", ['broken', 'repair']),
        ("Multi-Department", "Forklift needs maintenance inspection per safety regulations", ['forklift', 'maintenance', 'inspection', 'safety']),
        ("Generic Query", "What time does the building open?", ['time', 'open']),
    ]

    for title, query, keywords in examples:
        print(f"\n📝 {title}")
        print(f"   Query: \"{query}\"")
        print(f"   Keywords: {keywords}")
        print()

        # Get probability distribution
        scores = analyzer.infer_department_context(query, keywords)

        # Get primary department
        primary_dept = analyzer.get_primary_department(query, keywords)

        # Get confidence
        dept, confidence = analyzer.get_department_confidence(query, keywords)

        print_result("Primary Department", primary_dept)
        print_result("Confidence", confidence)

        if scores:
            print("  Department Probability Distribution:")
            for dept_name, score in sorted(scores.items(), key=lambda x: -x[1])[:3]:
                print(f"    {dept_name}: {score:.3f}")
        else:
            print("  Department Probability Distribution: (none - generic query)")


def demo_pattern_detector():
    """Demonstrate QueryPatternDetector capabilities."""
    print_header("QueryPatternDetector - Capabilities Demo")

    try:
        db_pool = get_pool()
        detector = QueryPatternDetector(db_pool)

        print("\n✓ Successfully connected to database")
        print()

        # Demo 1: Session pattern detection
        print("📊 Session Pattern Detection")
        print("   Analyzes query sequences to identify user behavior patterns:")
        print("   - EXPLORATORY: Diverse questions across topics")
        print("   - FOCUSED: Repeated queries on same topic")
        print("   - TROUBLESHOOTING_ESCALATION: Increasing frustration")
        print("   - ONBOARDING: Sequential procedural questions")
        print()

        pattern = detector.detect_query_sequence_pattern(
            "demo_user@example.com",
            "demo_session_123"
        )

        print_result("Pattern Detection Result", pattern)

        # Demo 2: Department trends
        print("\n\n📈 Department Usage Trends (Last 24 Hours)")
        print("   Analyzes temporal patterns in department queries:")
        print("   - Peak usage hours per department")
        print("   - Emerging topics (sudden spikes)")
        print()

        trends = detector.detect_department_usage_trends(hours=24)

        if 'error' in trends:
            print(f"   ⚠ Note: Database columns need migration")
            print(f"   Error: {trends['error']}")
        else:
            print(f"   Analyzed: {trends['hours_analyzed']} hours")
            print(f"   Peak hours identified: {len(trends.get('peak_hours', []))}")
            print(f"   Emerging topics: {len(trends.get('emerging_topics', []))}")

        # Demo 3: Anomaly detection
        print("\n\n🚨 Anomaly Detection")
        print("   Detects unusual patterns:")
        print("   - Sudden spike in repeat questions")
        print("   - Unusual query volume")
        print("   - High error rates")
        print()

        anomalies = detector.detect_anomalies()

        if anomalies:
            print(f"   Found {len(anomalies)} anomalies:")
            for anomaly in anomalies:
                print(f"     • {anomaly['type']}: {anomaly.get('message', 'N/A')}")
        else:
            print("   ✓ No anomalies detected")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("   Note: Pattern detector requires database connection")
        print("   Ensure PostgreSQL is running and accessible")


def demo_complete_workflow():
    """Demonstrate complete workflow with a single query."""
    print_header("Complete Workflow - Single Query Analysis")

    # Initialize all analyzers
    complexity_analyzer = QueryComplexityAnalyzer()
    dept_analyzer = DepartmentContextAnalyzer()

    # Sample query
    query = "How do I submit a safety incident report for a warehouse forklift accident that happened today?"
    user_email = "worker@example.com"
    session_id = "session_xyz_789"
    keywords = ['submit', 'safety', 'incident', 'report', 'warehouse', 'forklift', 'accident']

    print(f"\n📝 Query: \"{query}\"")
    print(f"👤 User: {user_email}")
    print(f"🔑 Session: {session_id}")
    print(f"🏷️  Keywords: {keywords}")

    print("\n" + "-" * 80)
    print("ANALYSIS RESULTS")
    print("-" * 80)

    # Step 1: Complexity Analysis
    print("\n1️⃣  COMPLEXITY ANALYSIS")
    complexity = complexity_analyzer.analyze(query)
    for key, value in complexity.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.3f}")
        else:
            print(f"   {key}: {value}")

    # Step 2: Department Context
    print("\n2️⃣  DEPARTMENT CONTEXT")
    dept_scores = dept_analyzer.infer_department_context(query, keywords)
    primary_dept, confidence = dept_analyzer.get_department_confidence(query, keywords)

    print(f"   Primary Department: {primary_dept}")
    print(f"   Confidence: {confidence:.3f}")
    print(f"   All Departments:")
    for dept, score in sorted(dept_scores.items(), key=lambda x: -x[1]):
        print(f"     • {dept}: {score:.3f}")

    # Step 3: Session Pattern (if available)
    print("\n3️⃣  SESSION PATTERN")
    try:
        db_pool = get_pool()
        detector = QueryPatternDetector(db_pool)
        pattern = detector.detect_query_sequence_pattern(user_email, session_id)

        print(f"   Pattern Type: {pattern['pattern_type']}")
        print(f"   Confidence: {pattern['confidence']:.3f}")
        print(f"   Query Count: {pattern['query_count']}")
        if pattern['details']:
            print(f"   Details: {pattern['details']}")
    except Exception as e:
        print(f"   ⚠ Pattern detection unavailable: {e}")

    # Summary
    print("\n" + "-" * 80)
    print("SUMMARY")
    print("-" * 80)
    print(f"""
This query should be:
  • Routed to: {primary_dept.upper()} department
  • Priority: {complexity['temporal_indicator']}
  • Response complexity: {'HIGH' if complexity['complexity_score'] > 0.5 else 'MEDIUM' if complexity['complexity_score'] > 0.3 else 'LOW'}
  • Intent: {complexity['intent_type']}
  • Multi-part: {'Yes' if complexity['multi_part'] else 'No'}

Recommended actions:
  • Tag as {primary_dept.upper()} query in database
  • Apply urgency filter: {complexity['temporal_indicator']}
  • Consider related departments: {', '.join([d for d, s in sorted(dept_scores.items(), key=lambda x: -x[1])[1:3]])}
""")


def main():
    """Run interactive demo."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                   QUERY HEURISTICS ENGINE - INTERACTIVE DEMO                 ║
║                                                                              ║
║  This demo showcases the three analyzer classes with real-world examples:   ║
║                                                                              ║
║    1. QueryComplexityAnalyzer  - Intent, complexity, urgency detection      ║
║    2. DepartmentContextAnalyzer - Department inference from content         ║
║    3. QueryPatternDetector     - Session patterns and trends                ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    # Run all demos
    demo_complexity_analyzer()
    print("\n\n")

    demo_department_analyzer()
    print("\n\n")

    demo_pattern_detector()
    print("\n\n")

    demo_complete_workflow()

    print("\n" + "=" * 80)
    print("  Demo Complete!")
    print("=" * 80)
    print("\nFor more information:")
    print("  • Implementation details: PHASE1_IMPLEMENTATION_SUMMARY.md")
    print("  • Quick reference: HEURISTICS_QUICK_REFERENCE.md")
    print("  • Test suite: python test_query_heuristics.py")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
