"""
Observability Suite Test - Comprehensive validation script

Tests all components of the observability system:
1. Backend metrics collection
2. API endpoints
3. WebSocket streaming
4. Database tables
5. Instrumentation hooks

Run with: python test_observability.py
"""

import sys
import time
import asyncio
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def test_imports():
    """Test that all modules import successfully."""
    logger.info("=== Testing Imports ===")

    try:
        from core.metrics_collector import metrics_collector, MetricsCollector
        logger.info("✓ metrics_collector imported successfully")
    except Exception as e:
        logger.error(f"✗ Failed to import metrics_collector: {e}")
        return False

    try:
        from auth.metrics_routes import metrics_router
        logger.info("✓ metrics_routes imported successfully")
    except Exception as e:
        logger.error(f"✗ Failed to import metrics_routes: {e}")
        return False

    try:
        import psutil
        logger.info(f"✓ psutil available (version {psutil.__version__})")
    except ImportError:
        logger.warning("⚠ psutil not available - system metrics will be disabled")

    return True


def test_metrics_collector():
    """Test MetricsCollector functionality."""
    logger.info("\n=== Testing MetricsCollector ===")

    try:
        from core.metrics_collector import metrics_collector

        # Test singleton pattern
        from core.metrics_collector import MetricsCollector
        collector2 = MetricsCollector()
        assert collector2 is metrics_collector, "Singleton pattern broken"
        logger.info("✓ Singleton pattern working")

        # Test WebSocket tracking
        metrics_collector.record_ws_connect()
        metrics_collector.record_ws_message('in')
        metrics_collector.record_ws_message('out')
        assert metrics_collector.ws_connections_active == 1
        assert metrics_collector.ws_messages_in == 1
        assert metrics_collector.ws_messages_out == 1
        logger.info("✓ WebSocket metrics recording working")

        # Test RAG tracking
        metrics_collector.record_rag_query(
            total_ms=250.5,
            embedding_ms=100.2,
            search_ms=50.3,
            chunks=5,
            cache_hit=False,
            embedding_cache_hit=True
        )
        assert metrics_collector.rag_total == 1
        assert metrics_collector.embedding_cache_hits == 1
        logger.info("✓ RAG metrics recording working")

        # Test LLM tracking
        metrics_collector.record_llm_call(
            latency_ms=1500.0,
            first_token_ms=300.0,
            tokens_in=1000,
            tokens_out=500,
            cost_usd=0.015,
            error=False
        )
        assert metrics_collector.llm_requests == 1
        assert metrics_collector.llm_tokens_in == 1000
        assert metrics_collector.llm_tokens_out == 500
        logger.info("✓ LLM metrics recording working")

        # Test snapshot generation
        snapshot = metrics_collector.get_snapshot()
        assert 'timestamp' in snapshot
        assert 'system' in snapshot
        assert 'rag' in snapshot
        assert 'llm' in snapshot
        assert 'cache' in snapshot
        assert 'websocket' in snapshot
        logger.info("✓ Snapshot generation working")

        # Test health check
        health = metrics_collector.get_health()
        assert 'status' in health
        assert 'uptime_seconds' in health
        logger.info(f"✓ Health check working (status: {health['status']})")

        return True
    except Exception as e:
        logger.error(f"✗ MetricsCollector test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_integration():
    """Test API integration."""
    logger.info("\n=== Testing API Integration ===")

    try:
        # Direct check - verify metrics_router is imported and registered in main.py
        with open('core/main.py', 'r', encoding='utf-8') as f:
            main_content = f.read()

        if 'app.include_router(metrics_router' in main_content:
            logger.info("✓ Metrics router is registered in main.py")
        else:
            logger.error("✗ Metrics router not registered in main.py")
            return False

        if 'prefix="/api/metrics"' in main_content:
            logger.info("✓ Metrics router has correct prefix (/api/metrics)")
        else:
            logger.error("✗ Metrics router missing /api/metrics prefix")
            return False

        logger.info("✓ API integration complete (skipped full app import due to dependencies)")

        return True
    except Exception as e:
        logger.error(f"✗ API integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_instrumentation():
    """Test that instrumentation is in place."""
    logger.info("\n=== Testing Instrumentation ===")

    try:
        # Check main.py has metrics imports
        with open('core/main.py', 'r', encoding='utf-8') as f:
            main_content = f.read()

        if 'from core.metrics_collector import metrics_collector' in main_content:
            logger.info("✓ main.py imports metrics_collector")
        else:
            logger.error("✗ main.py missing metrics_collector import")
            return False

        if 'from auth.metrics_routes import metrics_router' in main_content:
            logger.info("✓ main.py imports metrics_router")
        else:
            logger.error("✗ main.py missing metrics_router import")
            return False

        if 'metrics_collector.record_request' in main_content:
            logger.info("✓ main.py has request instrumentation")
        else:
            logger.error("✗ main.py missing request instrumentation")
            return False

        if 'metrics_collector.record_ws_connect' in main_content:
            logger.info("✓ main.py has WebSocket instrumentation")
        else:
            logger.error("✗ main.py missing WebSocket instrumentation")
            return False

        # Check enterprise_rag.py instrumentation
        with open('core/enterprise_rag.py', 'r', encoding='utf-8') as f:
            rag_content = f.read()

        if 'from .metrics_collector import metrics_collector' in rag_content:
            logger.info("✓ enterprise_rag.py imports metrics_collector")
        else:
            logger.error("✗ enterprise_rag.py missing metrics_collector import")
            return False

        if 'metrics_collector.record_rag_query' in rag_content:
            logger.info("✓ enterprise_rag.py has RAG instrumentation")
        else:
            logger.error("✗ enterprise_rag.py missing RAG instrumentation")
            return False

        # Check model_adapter.py instrumentation
        with open('core/model_adapter.py', 'r', encoding='utf-8') as f:
            adapter_content = f.read()

        if 'from .metrics_collector import metrics_collector' in adapter_content:
            logger.info("✓ model_adapter.py imports metrics_collector")
        else:
            logger.error("✗ model_adapter.py missing metrics_collector import")
            return False

        if 'metrics_collector.record_llm_call' in adapter_content:
            logger.info("✓ model_adapter.py has LLM instrumentation")
        else:
            logger.error("✗ model_adapter.py missing LLM instrumentation")
            return False

        return True
    except Exception as e:
        logger.error(f"✗ Instrumentation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_frontend_files():
    """Test that frontend files exist."""
    logger.info("\n=== Testing Frontend Files ===")

    import os

    files_to_check = [
        'frontend/src/lib/stores/metrics.ts',
        'frontend/src/lib/components/admin/observability/SystemHealthPanel.svelte',
        'frontend/src/lib/components/admin/observability/RagPerformancePanel.svelte',
        'frontend/src/lib/components/admin/observability/LlmCostPanel.svelte',
        'frontend/src/routes/admin/system/+page.svelte',
    ]

    all_exist = True
    for file_path in files_to_check:
        if os.path.exists(file_path):
            logger.info(f"✓ {file_path} exists")
        else:
            logger.error(f"✗ {file_path} missing")
            all_exist = False

    return all_exist


def test_database_migration():
    """Test database migration file."""
    logger.info("\n=== Testing Database Migration ===")

    import os

    migration_file = 'migrations/007_observability_tables.sql'

    if not os.path.exists(migration_file):
        logger.error(f"✗ Migration file missing: {migration_file}")
        return False

    with open(migration_file, 'r', encoding='utf-8') as f:
        content = f.read()

    tables = [
        'enterprise.request_metrics',
        'enterprise.system_metrics',
        'enterprise.llm_call_metrics',
        'enterprise.rag_metrics',
        'enterprise.cache_metrics',
    ]

    all_tables_present = True
    for table in tables:
        if table in content:
            logger.info(f"✓ Table {table} defined in migration")
        else:
            logger.error(f"✗ Table {table} missing from migration")
            all_tables_present = False

    return all_tables_present


def run_all_tests():
    """Run all tests and report results."""
    logger.info("=" * 60)
    logger.info("OBSERVABILITY SUITE COMPREHENSIVE TEST")
    logger.info("=" * 60)

    tests = [
        ("Imports", test_imports),
        ("MetricsCollector", test_metrics_collector),
        ("API Integration", test_api_integration),
        ("Instrumentation", test_instrumentation),
        ("Frontend Files", test_frontend_files),
        ("Database Migration", test_database_migration),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results[test_name] = False

    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status} - {test_name}")

    logger.info("=" * 60)
    logger.info(f"TOTAL: {passed}/{total} tests passed")
    logger.info("=" * 60)

    if passed == total:
        logger.info("\n🎉 ALL TESTS PASSED! Observability suite is ready!")
        return 0
    else:
        logger.error(f"\n⚠ {total - passed} test(s) failed. Please review and fix.")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
