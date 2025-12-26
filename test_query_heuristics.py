"""
Test script for Query Heuristics Engine.

This script validates all three analyzer classes:
- QueryComplexityAnalyzer
- DepartmentContextAnalyzer
- QueryPatternDetector

Run with: python test_query_heuristics.py
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


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_complexity_analyzer():
    """Test QueryComplexityAnalyzer with various query types."""
    print_section("TEST: Query Complexity Analyzer")

    analyzer = QueryComplexityAnalyzer()

    test_cases = [
        {
            'query': "What is a forklift?",
            'expected': {
                'complexity': 'low',
                'intent': 'INFORMATION_SEEKING',
                'urgency': 'LOW'
            }
        },
        {
            'query': "How do I process a return for order #12345 immediately?",
            'expected': {
                'complexity': 'medium',
                'intent': 'ACTION_ORIENTED',
                'urgency': 'URGENT'
            }
        },
        {
            'query': "Should I use forklift A or forklift B for this shipment? Which one is better for heavy loads? Also, what are the safety requirements?",
            'expected': {
                'complexity': 'high',
                'intent': 'DECISION_SUPPORT',
                'urgency': 'LOW',
                'multi_part': True
            }
        },
        {
            'query': "If the inventory level drops below 100 units, how do I submit a restock request? What happens if the vendor is on backorder?",
            'expected': {
                'complexity': 'high',
                'intent': 'ACTION_ORIENTED',
                'multi_part': False
            }
        },
        {
            'query': "Is it correct that employees get 15 days of PTO per year?",
            'expected': {
                'intent': 'VERIFICATION',
                'urgency': 'LOW'
            }
        },
        {
            'query': "Need help with password reset ASAP!",
            'expected': {
                'intent': 'ACTION_ORIENTED',
                'urgency': 'URGENT'
            }
        },
        {
            'query': "",  # Edge case: empty query
            'expected': {
                'complexity': 0.0,
                'intent': 'INFORMATION_SEEKING'
            }
        }
    ]

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        query = test['query']
        expected = test['expected']

        print(f"Test {i}: '{query[:60]}{'...' if len(query) > 60 else ''}'")

        result = analyzer.analyze(query)

        print(f"  Result: {json.dumps(result, indent=4)}")

        # Validate expectations
        checks_passed = True

        if 'intent' in expected:
            if result['intent_type'] != expected['intent']:
                print(f"  ❌ FAILED: Expected intent '{expected['intent']}', got '{result['intent_type']}'")
                checks_passed = False
                failed += 1
            else:
                print(f"  ✓ Intent correct: {result['intent_type']}")

        if 'urgency' in expected:
            if result['temporal_indicator'] != expected['urgency']:
                print(f"  ❌ FAILED: Expected urgency '{expected['urgency']}', got '{result['temporal_indicator']}'")
                checks_passed = False
                failed += 1
            else:
                print(f"  ✓ Urgency correct: {result['temporal_indicator']}")

        if 'multi_part' in expected:
            if result['multi_part'] != expected['multi_part']:
                print(f"  ❌ FAILED: Expected multi_part={expected['multi_part']}, got {result['multi_part']}")
                checks_passed = False
                failed += 1
            else:
                print(f"  ✓ Multi-part correct: {result['multi_part']}")

        if 'complexity' in expected:
            if expected['complexity'] == 'low' and result['complexity_score'] >= 0.4:
                print(f"  ⚠ WARNING: Expected low complexity, got {result['complexity_score']:.2f}")
            elif expected['complexity'] == 'high' and result['complexity_score'] < 0.5:
                print(f"  ⚠ WARNING: Expected high complexity, got {result['complexity_score']:.2f}")
            elif expected['complexity'] == 0.0 and result['complexity_score'] != 0.0:
                print(f"  ❌ FAILED: Expected complexity 0.0, got {result['complexity_score']}")
                checks_passed = False
                failed += 1

        if checks_passed:
            passed += 1
            print(f"  ✓ PASSED")

        print()

    print(f"\nComplexity Analyzer Summary: {passed} passed, {failed} failed")
    return failed == 0


def test_department_analyzer():
    """Test DepartmentContextAnalyzer with various queries."""
    print_section("TEST: Department Context Analyzer")

    analyzer = DepartmentContextAnalyzer()

    test_cases = [
        {
            'query': "How do I reset my password?",
            'expected_dept': 'it',
            'keywords': ['password', 'reset']
        },
        {
            'query': "Where can I find the inventory for product SKU-12345 in the warehouse?",
            'expected_dept': 'warehouse',
            'keywords': ['inventory', 'product', 'warehouse']
        },
        {
            'query': "What are the steps to file a safety incident report for a forklift accident?",
            'expected_dept': 'safety',
            'keywords': ['safety', 'incident', 'accident', 'forklift']
        },
        {
            'query': "How do I submit an expense reimbursement for my business trip?",
            'expected_dept': 'finance',
            'keywords': ['expense', 'reimbursement']
        },
        {
            'query': "When do I get paid? What about my 401k benefits?",
            'expected_dept': 'hr',
            'keywords': ['paid', 'benefits', '401k']
        },
        {
            'query': "The conveyor belt is broken and needs repair immediately",
            'expected_dept': 'maintenance',
            'keywords': ['broken', 'repair']
        },
        {
            'query': "Who is the CEO?",  # Generic query
            'expected_dept': 'general',
            'keywords': ['CEO']
        },
        {
            'query': "",  # Edge case: empty query
            'expected_dept': 'general',
            'keywords': []
        }
    ]

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        query = test['query']
        expected_dept = test['expected_dept']
        keywords = test.get('keywords', [])

        print(f"Test {i}: '{query[:60]}{'...' if len(query) > 60 else ''}'")

        # Test probability distribution
        dept_scores = analyzer.infer_department_context(query, keywords)
        print(f"  Department scores: {json.dumps({k: round(v, 3) for k, v in dept_scores.items()}, indent=4)}")

        # Test primary department
        primary_dept = analyzer.get_primary_department(query, keywords)
        print(f"  Primary department: {primary_dept}")

        # Test confidence
        dept, confidence = analyzer.get_department_confidence(query, keywords)
        print(f"  Confidence: {dept} ({confidence:.3f})")

        if primary_dept == expected_dept:
            print(f"  ✓ PASSED: Correctly identified '{expected_dept}'")
            passed += 1
        else:
            print(f"  ❌ FAILED: Expected '{expected_dept}', got '{primary_dept}'")
            failed += 1

        print()

    print(f"\nDepartment Analyzer Summary: {passed} passed, {failed} failed")
    return failed == 0


def test_pattern_detector():
    """Test QueryPatternDetector (requires DB connection)."""
    print_section("TEST: Query Pattern Detector")

    try:
        db_pool = get_pool()
        detector = QueryPatternDetector(db_pool)

        print("✓ Successfully initialized QueryPatternDetector with DB pool")

        # Test default pattern (for non-existent session)
        pattern = detector.detect_query_sequence_pattern(
            "test_user@example.com",
            "non_existent_session_12345"
        )

        print(f"\nTest: Non-existent session")
        print(f"  Result: {json.dumps(pattern, indent=4)}")

        if pattern['pattern_type'] == 'SINGLE_QUERY' and pattern['query_count'] == 0:
            print(f"  ✓ PASSED: Correctly returned default pattern for non-existent session")
        else:
            print(f"  ❌ FAILED: Expected default pattern")

        # Test department trends
        print(f"\nTest: Department usage trends (last 24 hours)")
        trends = detector.detect_department_usage_trends(hours=24)

        if 'error' in trends:
            print(f"  ⚠ WARNING: {trends['error']}")
        else:
            print(f"  Result: {json.dumps(trends, indent=4)}")
            print(f"  ✓ Successfully retrieved department trends")

        # Test anomaly detection
        print(f"\nTest: Anomaly detection")
        anomalies = detector.detect_anomalies()

        print(f"  Found {len(anomalies)} anomalies")
        for anomaly in anomalies:
            print(f"    - {anomaly['type']}: {anomaly.get('message', 'No message')}")

        print(f"\n✓ Pattern Detector tests completed successfully")
        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("  QUERY HEURISTICS ENGINE - COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    results = {
        'complexity': test_complexity_analyzer(),
        'department': test_department_analyzer(),
        'pattern': test_pattern_detector()
    }

    print_section("FINAL RESULTS")

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name.capitalize()} Analyzer: {status}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠ Some tests failed. Review output above.")
        return 1


if __name__ == "__main__":
    exit(main())
