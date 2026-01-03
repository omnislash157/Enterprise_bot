# Addition to main.py startup event for local vault initialization

# Add this to the startup_event() function in main.py:

# Initialize local vault structure
logger.info("[STARTUP] Initializing local vault structure...")
try:
    from core.local_vault import LocalVaultService
    
    # Create the local vault directories (platform-specific)
    local_vault = LocalVaultService()
    status = local_vault.get_status()
    
    logger.info(f"[STARTUP] Local vault initialized: {status['root']}")
    logger.info(f"[STARTUP] Platform: {status['platform']}")
    logger.info(f"[STARTUP] Current vault size: {status['total_size_mb']} MB")
    
    if status['node_count'] > 0:
        logger.info(f"[STARTUP] Found existing data: {status['node_count']} nodes, {status['episode_count']} episodes")
    else:
        logger.info("[STARTUP] Local vault is empty - ready for first sync")
    
    # Store local vault reference in app state for routes
    app.state.local_vault = local_vault
    
except Exception as e:
    logger.warning(f"[STARTUP] Local vault initialization failed (continuing): {e}")

# Migration check for legacy data
try:
    from pathlib import Path
    legacy_data_dir = Path("./data")
    
    if legacy_data_dir.exists() and any(legacy_data_dir.iterdir()):
        logger.warning(f"[STARTUP] Legacy data directory detected: {legacy_data_dir}")
        logger.warning("[STARTUP] Use /api/personal/vault/migrate-legacy to migrate to local vault")
        
        # Auto-migrate if vault is empty and legacy has data
        if status['node_count'] == 0:
            logger.info("[STARTUP] Auto-migrating legacy data...")
            try:
                local_vault.migrate_from_legacy_data_dir(legacy_data_dir)
                new_status = local_vault.get_status()
                logger.info(f"[STARTUP] Migration complete: {new_status['node_count']} nodes migrated")
            except Exception as e:
                logger.error(f"[STARTUP] Auto-migration failed: {e}")
                
except Exception as e:
    logger.warning(f"[STARTUP] Legacy migration check failed: {e}")