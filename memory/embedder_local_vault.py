# Updated embedder initialization to use LocalVaultService

def __init__(
    self,
    provider: str = "deepinfra",
    api_key: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    batch_size: int = 128,
    max_concurrent: int = 8,
):
    """
    Initialize async embedder with local vault cache support.

    Args:
        provider: Embedding provider
        api_key: API key for provider  
        cache_dir: Cache directory (defaults to local vault cache)
        batch_size: Default batch size
        max_concurrent: Max concurrent requests
    """
    self.provider = provider
    self.batch_size = batch_size
    self.max_concurrent = max_concurrent
    
    # Use local vault cache by default
    if cache_dir is None:
        try:
            from core.local_vault import LocalVaultService
            local_vault = LocalVaultService()
            self.cache_dir = local_vault.cache_dir
            logger.info(f"Using local vault cache: {self.cache_dir}")
        except Exception as e:
            logger.warning(f"Failed to use local vault cache, falling back to ./data/embedding_cache: {e}")
            self.cache_dir = Path("./data/embedding_cache")
    else:
        self.cache_dir = Path(cache_dir)
    
    self.cache_dir.mkdir(parents=True, exist_ok=True)

# ... rest of methods remain the same ...