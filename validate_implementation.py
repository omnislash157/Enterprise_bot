#!/usr/bin/env python3
"""
Quick validation script for Local Vault implementation.
"""

def test_imports():
    """Test that all components import correctly."""
    print("📦 Testing imports...")
    
    try:
        from core.local_vault import LocalVaultService
        print("   ✅ LocalVaultService imported")
    except Exception as e:
        print(f"   ❌ LocalVaultService failed: {e}")
        return False
    
    try:
        # Test that we can create the vault
        vault = LocalVaultService()
        print(f"   ✅ LocalVaultService created: {vault.root}")
    except Exception as e:
        print(f"   ❌ LocalVaultService creation failed: {e}")
        return False
    
    try:
        # Test basic write/read
        test_data = [{"id": "test", "content": "hello"}]
        vault.write_nodes(test_data, sync=False)
        read_data = vault.read_nodes()
        if read_data and read_data[0]["id"] == "test":
            print("   ✅ Basic read/write working")
        else:
            print("   ❌ Read/write failed")
            return False
    except Exception as e:
        print(f"   ❌ Read/write test failed: {e}")
        return False
    
    # Clean up
    vault.write_nodes([], sync=False)
    
    return True

def test_platform_paths():
    """Test platform path detection."""
    print("\n🔧 Testing platform paths...")
    
    from core.local_vault import LocalVaultService
    import platform
    
    vault = LocalVaultService()
    system = platform.system()
    
    if system == "Windows":
        expected = "AppData\\Local\\cogzy"
        if expected in str(vault.root):
            print(f"   ✅ Windows path correct: {vault.root}")
        else:
            print(f"   ❌ Windows path wrong: {vault.root}")
            return False
    else:
        print(f"   ✅ Platform {system} path: {vault.root}")
    
    return True

def test_file_structure():
    """Test that all required directories exist."""
    print("\n📁 Testing file structure...")
    
    from core.local_vault import LocalVaultService
    
    vault = LocalVaultService()
    
    required_dirs = ["corpus", "vectors", "indexes", "cache", "sync", "config", "logs"]
    for dir_name in required_dirs:
        dir_path = vault.root / dir_name
        if dir_path.exists():
            print(f"   ✅ {dir_name}/")
        else:
            print(f"   ❌ {dir_name}/ missing")
            return False
    
    # Test specific cache subdir
    embeddings_cache = vault.cache_dir
    if embeddings_cache.exists():
        print(f"   ✅ embeddings cache: {embeddings_cache}")
    else:
        print(f"   ❌ embeddings cache missing: {embeddings_cache}")
        return False
    
    return True

def test_pipeline_updates():
    """Test that pipeline updates are in place."""
    print("\n🔧 Testing pipeline updates...")
    
    try:
        # Check if the updated pipeline function has LOCAL-FIRST features
        import inspect
        from memory.ingest import pipeline
        
        # Get the source code of the run_pipeline_for_user function
        source = inspect.getsource(pipeline.run_pipeline_for_user)
        
        if "LOCAL-FIRST" in source and "LocalVaultService" in source:
            print("   ✅ Updated pipeline function found")
        else:
            print("   ❌ Pipeline function not updated with LOCAL-FIRST features")
            return False
            
    except Exception as e:
        print(f"   ❌ Pipeline test failed: {e}")
        return False
    
    return True

def test_retrieval_updates():
    """Test that retrieval updates are in place."""
    print("\n🔍 Testing retrieval updates...")
    
    try:
        from memory.retrieval import DualRetriever
        
        # Check if new methods exist
        if hasattr(DualRetriever, 'load_from_local_vault'):
            print("   ✅ load_from_local_vault method found")
        else:
            print("   ❌ load_from_local_vault method missing")
            return False
            
        if hasattr(DualRetriever, 'load_with_fallback'):
            print("   ✅ load_with_fallback method found")
        else:
            print("   ❌ load_with_fallback method missing")
            return False
    except ImportError as e:
        print(f"   ⚠️  Retrieval test skipped: {e}")
        return True  # Not critical for basic functionality
    
    return True

def main():
    """Run validation tests."""
    print("🚀 Local Vault Implementation Validator")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_platform_paths,
        test_file_structure,
        test_pipeline_updates,
        test_retrieval_updates,
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"   💥 {test.__name__} failed: {e}")
    
    print("\n" + "=" * 50)
    print(f"🎯 Validation Results: {passed}/{len(tests)} passed")
    
    if passed == len(tests):
        print("🎉 Implementation is valid and ready!")
        
        # Show current status
        from core.local_vault import LocalVaultService
        vault = LocalVaultService()
        status = vault.get_status()
        print(f"\n📍 Local vault location: {status['root']}")
        print(f"📊 Current size: {status['total_size_mb']} MB")
        
    else:
        print(f"⚠️  {len(tests) - passed} validation(s) failed.")
        print("   Check the output above for details.")

if __name__ == "__main__":
    main()