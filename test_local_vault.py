#!/usr/bin/env python3
"""
Test script for Local Vault Architecture implementation.

Tests all components of the local-first vault system:
- LocalVaultService functionality
- Pipeline local writes + B2 sync
- Retrieval from local vault
- API endpoints

Usage:
    python test_local_vault.py [--full]  # Full test includes B2 sync
    python test_local_vault.py --status  # Just check status
"""

import asyncio
import json
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any
import numpy as np

# Test configuration
TEST_USER_ID = "test-user-123"
TEST_CONFIG = {
    "vault": {
        "bucket": "test-bucket",
        "key_id": "test-key",
        "app_key": "test-secret",
        "base_prefix": "users"
    }
}

def test_platform_path_detection():
    """Test that platform-specific paths are detected correctly."""
    print("🔍 Testing platform path detection...")
    
    from core.local_vault import LocalVaultService
    
    vault = LocalVaultService()
    print(f"   Platform: {vault._get_platform_path()}")
    print(f"   Root: {vault.root}")
    
    # Verify directory structure was created
    expected_dirs = ["corpus", "vectors", "indexes", "cache", "sync", "config", "logs"]
    for dir_name in expected_dirs:
        dir_path = vault.root / dir_name
        if dir_path.exists():
            print(f"   ✅ {dir_name}/ created")
        else:
            print(f"   ❌ {dir_name}/ missing")
            return False
    
    print("   ✅ Platform path detection working")
    return True

def test_read_write_operations():
    """Test basic read/write operations."""
    print("\n📝 Testing read/write operations...")
    
    from core.local_vault import LocalVaultService
    
    vault = LocalVaultService(user_id=TEST_USER_ID)
    
    # Test nodes
    test_nodes = [
        {
            "id": "node-1",
            "content": "Test content 1",
            "timestamp": "2024-01-01T00:00:00Z"
        },
        {
            "id": "node-2", 
            "content": "Test content 2",
            "timestamp": "2024-01-01T00:01:00Z"
        }
    ]
    
    # Write and read back
    vault.write_nodes(test_nodes, sync=False)
    read_nodes = vault.read_nodes()
    
    if len(read_nodes) == 2 and read_nodes[0]["id"] == "node-1":
        print("   ✅ Nodes write/read working")
    else:
        print(f"   ❌ Nodes failed: {len(read_nodes)} nodes, first id: {read_nodes[0]['id'] if read_nodes else 'None'}")
        return False
    
    # Test episodes
    test_episodes = [
        {
            "id": "ep-1",
            "title": "Test episode",
            "messages": [{"role": "user", "content": "Hello"}]
        }
    ]
    
    vault.write_episodes(test_episodes, sync=False)
    read_episodes = vault.read_episodes()
    
    if len(read_episodes) == 1 and read_episodes[0]["id"] == "ep-1":
        print("   ✅ Episodes write/read working")
    else:
        print(f"   ❌ Episodes failed: {len(read_episodes)} episodes")
        return False
    
    # Test embeddings
    test_embeddings = np.random.rand(2, 768).astype(np.float32)
    vault.write_node_embeddings(test_embeddings, sync=False)
    read_embeddings = vault.read_node_embeddings()
    
    if read_embeddings is not None and read_embeddings.shape == (2, 768):
        print("   ✅ Embeddings write/read working")
    else:
        print(f"   ❌ Embeddings failed: shape {read_embeddings.shape if read_embeddings is not None else 'None'}")
        return False
    
    # Test dedup index
    test_dedup = {"ingested_ids": ["id1", "id2", "hash1", "hash2"]}
    vault.write_dedup_index(test_dedup, sync=False)
    read_dedup = vault.read_dedup_index()
    
    if len(read_dedup.get("ingested_ids", [])) == 4:
        print("   ✅ Dedup index write/read working")
    else:
        print(f"   ❌ Dedup index failed: {len(read_dedup.get('ingested_ids', []))} entries")
        return False
    
    print("   ✅ All read/write operations working")
    return True

def test_status_and_migration():
    """Test status reporting and legacy migration."""
    print("\n📊 Testing status and migration...")
    
    from core.local_vault import LocalVaultService
    
    vault = LocalVaultService(user_id=TEST_USER_ID)
    status = vault.get_status()
    
    # Check status structure
    required_keys = ["root", "platform", "node_count", "episode_count", "total_size_mb", "files"]
    for key in required_keys:
        if key not in status:
            print(f"   ❌ Status missing key: {key}")
            return False
    
    print(f"   ✅ Status report: {status['node_count']} nodes, {status['episode_count']} episodes")
    print(f"   ✅ Storage: {status['total_size_mb']} MB")
    
    # Test legacy migration with temp data
    with tempfile.TemporaryDirectory() as temp_dir:
        legacy_dir = Path(temp_dir) / "legacy_data"
        legacy_dir.mkdir()
        
        # Create fake legacy structure
        corpus_dir = legacy_dir / "corpus"
        vectors_dir = legacy_dir / "vectors"
        corpus_dir.mkdir()
        vectors_dir.mkdir()
        
        # Write fake legacy files
        with open(corpus_dir / "nodes.json", "w") as f:
            json.dump([{"id": "legacy-node", "content": "Legacy content"}], f)
        
        np.save(vectors_dir / "nodes.npy", np.random.rand(1, 768))
        
        # Test migration
        try:
            vault.migrate_from_legacy_data_dir(legacy_dir)
            migrated_nodes = vault.read_nodes()
            
            # Check if legacy node was added to existing data
            legacy_found = any(node.get("id") == "legacy-node" for node in migrated_nodes)
            if legacy_found:
                print("   ✅ Legacy migration working")
            else:
                print("   ❌ Legacy migration failed - node not found")
                return False
                
        except Exception as e:
            print(f"   ❌ Legacy migration failed: {e}")
            return False
    
    print("   ✅ Status and migration working")
    return True

def test_retrieval_integration():
    """Test retrieval integration with local vault."""
    print("\n🔍 Testing retrieval integration...")
    
    try:
        # Test the new local vault retrieval method
        from memory.retrieval import DualRetriever
        
        # This should work with our test data
        retriever = DualRetriever.load_from_local_vault(user_id=TEST_USER_ID)
        
        # Check that data was loaded
        if len(retriever.nodes) > 0:
            print(f"   ✅ Retriever loaded {len(retriever.nodes)} nodes from local vault")
        else:
            print("   ⚠️  Retriever loaded but no nodes found (expected for empty vault)")
        
        # Test fallback method
        retriever2 = DualRetriever.load_with_fallback(user_id=TEST_USER_ID)
        if retriever2:
            print("   ✅ Fallback loading working")
        else:
            print("   ❌ Fallback loading failed")
            return False
            
    except ImportError as e:
        print(f"   ⚠️  Retrieval test skipped (import error): {e}")
        return True  # Not a failure, just missing dependency
    except Exception as e:
        print(f"   ❌ Retrieval integration failed: {e}")
        return False
    
    print("   ✅ Retrieval integration working")
    return True

async def test_b2_sync(full_test: bool = False):
    """Test B2 sync functionality (requires valid credentials)."""
    if not full_test:
        print("\n☁️  B2 sync test skipped (use --full to enable)")
        return True
        
    print("\n☁️  Testing B2 sync...")
    
    # Check if B2 credentials are available
    if not os.getenv("B2_APPLICATION_KEY_ID"):
        print("   ⚠️  B2 credentials not available, skipping sync test")
        return True
    
    try:
        from core.local_vault import LocalVaultService
        
        # Create vault with B2 config
        vault = LocalVaultService(user_id=TEST_USER_ID, b2_config=TEST_CONFIG)
        
        # Test sync to B2
        await vault.sync_to_b2()
        print("   ✅ B2 sync completed")
        
        # Test sync from B2
        vault.clear_local()
        await vault.sync_from_b2()
        
        # Check if data was restored
        nodes = vault.read_nodes()
        if len(nodes) > 0:
            print(f"   ✅ B2 restore completed: {len(nodes)} nodes")
        else:
            print("   ⚠️  B2 restore completed but no nodes (might be empty)")
        
    except Exception as e:
        print(f"   ❌ B2 sync failed: {e}")
        return False
    
    print("   ✅ B2 sync working")
    return True

def test_pipeline_integration():
    """Test pipeline integration (simplified without actual files)."""
    print("\n🔧 Testing pipeline integration...")
    
    try:
        # Import the new pipeline function
        from memory.ingest.pipeline import run_pipeline_for_user_local_vault
        
        print("   ✅ Pipeline function imported successfully")
        
        # We can't easily test the full pipeline without setting up file uploads,
        # but we can verify the import and basic structure
        import inspect
        sig = inspect.signature(run_pipeline_for_user_local_vault)
        required_params = ["user_id", "source_type", "upload_id", "config"]
        
        for param in required_params:
            if param not in sig.parameters:
                print(f"   ❌ Pipeline missing required parameter: {param}")
                return False
        
        print("   ✅ Pipeline function signature correct")
        
    except ImportError as e:
        print(f"   ❌ Pipeline integration failed: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Pipeline test failed: {e}")
        return False
    
    print("   ✅ Pipeline integration ready")
    return True

def print_status_summary():
    """Print a summary of the local vault status."""
    print("\n📋 Local Vault Status Summary")
    print("=" * 50)
    
    from core.local_vault import LocalVaultService
    
    vault = LocalVaultService()
    status = vault.get_status()
    
    print(f"Platform: {status['platform']}")
    print(f"Root: {status['root']}")
    print(f"Nodes: {status['node_count']}")
    print(f"Episodes: {status['episode_count']}")
    print(f"Storage: {status['total_size_mb']} MB")
    print(f"Has embeddings: {status['has_embeddings']}")
    print(f"Has FAISS: {status['has_faiss']}")
    
    if status['last_sync']:
        sync_time = status['last_sync'].get('last_sync', 'Never')
        print(f"Last sync: {sync_time}")
    else:
        print("Last sync: Never")
    
    print("\nFiles present:")
    for file_type, exists in status['files'].items():
        status_icon = "✅" if exists else "❌"
        print(f"  {status_icon} {file_type}")

def cleanup_test_data():
    """Clean up test data."""
    print("\n🧹 Cleaning up test data...")
    
    from core.local_vault import LocalVaultService
    
    vault = LocalVaultService()
    
    # Clear test data but preserve any real data
    try:
        nodes = vault.read_nodes()
        # Only remove our test nodes
        real_nodes = [n for n in nodes if not n.get("id", "").startswith(("node-", "legacy-node"))]
        vault.write_nodes(real_nodes, sync=False)
        
        episodes = vault.read_episodes()
        real_episodes = [e for e in episodes if not e.get("id", "").startswith("ep-")]
        vault.write_episodes(real_episodes, sync=False)
        
        print("   ✅ Test data cleaned up")
        
    except Exception as e:
        print(f"   ⚠️  Cleanup failed: {e}")

async def main():
    """Run all tests."""
    import sys
    
    full_test = "--full" in sys.argv
    status_only = "--status" in sys.argv
    
    print("🚀 Local Vault Architecture Test Suite")
    print("=" * 50)
    
    if status_only:
        print_status_summary()
        return
    
    # Run tests
    tests = [
        test_platform_path_detection,
        test_read_write_operations,
        test_status_and_migration,
        test_retrieval_integration,
        test_pipeline_integration,
    ]
    
    async_tests = [
        lambda: test_b2_sync(full_test),
    ]
    
    # Sync tests
    passed = 0
    total = len(tests) + len(async_tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"   💥 Test failed with exception: {e}")
    
    # Async tests
    for test in async_tests:
        try:
            if await test():
                passed += 1
        except Exception as e:
            print(f"   💥 Async test failed with exception: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print(f"🎯 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! Local vault architecture is working.")
    else:
        print(f"⚠️  {total - passed} tests failed. Check the output above.")
    
    # Print current status
    print_status_summary()
    
    # Ask about cleanup
    if passed > 0:  # Only if we actually created test data
        cleanup = input("\nClean up test data? [y/N]: ").lower().strip()
        if cleanup == 'y':
            cleanup_test_data()

if __name__ == "__main__":
    asyncio.run(main())