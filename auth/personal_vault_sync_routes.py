# New sync routes to add to personal_vault_routes.py

# =============================================================================
# LOCAL VAULT SYNC ENDPOINTS (NEW v3.0)
# =============================================================================

class LocalVaultStatus(BaseModel):
    """Local vault status response."""
    root: str
    platform: str
    node_count: int
    episode_count: int
    total_size_mb: float
    last_sync: Optional[dict]
    has_embeddings: bool
    has_faiss: bool
    files: dict

class SyncResponse(BaseModel):
    """Sync operation response."""
    status: str
    message: str
    files_synced: int
    local_vault_status: dict
    sync_duration_ms: int

@router.get("/local-status", response_model=LocalVaultStatus)
async def get_local_vault_status(user: SessionData = Depends(get_current_user)):
    """
    Get local vault status and statistics.
    
    Shows what's stored locally in ~/.cogzy/ without requiring B2 access.
    """
    try:
        from core.local_vault import LocalVaultService
        
        local_vault = LocalVaultService(user_id=str(user.user_id))
        status = local_vault.get_status()
        
        return LocalVaultStatus(
            root=status["root"],
            platform=status["platform"],
            node_count=status["node_count"],
            episode_count=status["episode_count"],
            total_size_mb=status["total_size_mb"],
            last_sync=status["last_sync"],
            has_embeddings=status["has_embeddings"],
            has_faiss=status["has_faiss"],
            files=status["files"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get local vault status: {e}")
        raise HTTPException(500, f"Failed to get local vault status: {str(e)}")

@router.post("/sync", response_model=SyncResponse)
async def force_sync_to_b2(
    request: Request,
    user: SessionData = Depends(get_current_user)
):
    """
    Force sync local vault data to B2 backup.
    
    Uploads all local ~/.cogzy/ data to users/{user_id}/ in B2.
    """
    import time
    start_time = time.time()
    
    try:
        from core.local_vault import LocalVaultService
        
        config = request.app.state.config
        local_vault = LocalVaultService(user_id=str(user.user_id), b2_config=config)
        
        # Get status before sync
        status_before = local_vault.get_status()
        
        # Perform sync
        await local_vault.sync_to_b2()
        
        # Get status after sync
        status_after = local_vault.get_status()
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return SyncResponse(
            status="completed",
            message=f"Successfully synced {status_after['node_count']} nodes and {status_after['episode_count']} episodes to B2",
            files_synced=sum(1 for v in status_after["files"].values() if v),
            local_vault_status=status_after,
            sync_duration_ms=duration_ms
        )
        
    except Exception as e:
        logger.error(f"Failed to sync to B2: {e}")
        raise HTTPException(500, f"Sync failed: {str(e)}")

@router.post("/reset", response_model=SyncResponse)
async def reset_from_b2(
    request: Request,
    user: SessionData = Depends(get_current_user)
):
    """
    Reset local vault from B2 backup.
    
    **WARNING**: This will DELETE all local data and re-download from B2.
    Use this to recover from corruption or sync between devices.
    """
    import time
    start_time = time.time()
    
    try:
        from core.local_vault import LocalVaultService
        
        config = request.app.state.config
        local_vault = LocalVaultService(user_id=str(user.user_id), b2_config=config)
        
        # Reset and pull from B2
        await local_vault.reset_from_b2()
        
        # Get final status
        status_after = local_vault.get_status()
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return SyncResponse(
            status="reset_completed",
            message=f"Reset complete: pulled {status_after['node_count']} nodes and {status_after['episode_count']} episodes from B2 backup",
            files_synced=sum(1 for v in status_after["files"].values() if v),
            local_vault_status=status_after,
            sync_duration_ms=duration_ms
        )
        
    except Exception as e:
        logger.error(f"Failed to reset from B2: {e}")
        raise HTTPException(500, f"Reset failed: {str(e)}")

@router.post("/migrate-legacy")
async def migrate_legacy_data(
    request: Request, 
    user: SessionData = Depends(get_current_user),
    legacy_path: str = "./data"
):
    """
    Migrate data from legacy ./data structure to local vault.
    
    One-time migration tool for existing users.
    """
    try:
        from core.local_vault import LocalVaultService
        from pathlib import Path
        
        local_vault = LocalVaultService(user_id=str(user.user_id))
        
        # Perform migration
        local_vault.migrate_from_legacy_data_dir(Path(legacy_path))
        
        # Get final status
        status = local_vault.get_status()
        
        return {
            "status": "migration_completed",
            "message": f"Migrated legacy data from {legacy_path}",
            "local_vault_status": status
        }
        
    except Exception as e:
        logger.error(f"Failed to migrate legacy data: {e}")
        raise HTTPException(500, f"Migration failed: {str(e)}")

@router.delete("/clear")
async def clear_local_vault(
    user: SessionData = Depends(get_current_user),
    confirm: bool = False
):
    """
    Clear all local vault data.
    
    **WARNING**: This permanently deletes local data. B2 backup is preserved.
    Requires confirm=true parameter.
    """
    if not confirm:
        raise HTTPException(400, "Must set confirm=true to clear local vault")
        
    try:
        from core.local_vault import LocalVaultService
        
        local_vault = LocalVaultService(user_id=str(user.user_id))
        local_vault.clear_local()
        
        return {
            "status": "cleared",
            "message": "Local vault cleared successfully",
            "note": "B2 backup preserved - use /reset to restore"
        }
        
    except Exception as e:
        logger.error(f"Failed to clear local vault: {e}")
        raise HTTPException(500, f"Clear failed: {str(e)}")