    # =================================================================
    # LOCAL VAULT METHODS (v3.0)
    # =================================================================

    @classmethod
    def load_from_local_vault(cls, user_id: Optional[str] = None) -> "DualRetriever":
        """
        Load retriever from LocalVaultService.
        
        **NEW VERSION 3.0: LOCAL-FIRST**
        
        Reads all data from ~/.cogzy/ instead of arbitrary data_dir.
        No more manifest file dependencies or path confusion.

        Args:
            user_id: Optional user ID for B2 sync (if needed)

        Returns:
            Initialized DualRetriever with local vault data
        """
        from core.local_vault import LocalVaultService
        
        local_vault = LocalVaultService(user_id=user_id)
        logger.info(f"Loading from local vault: {local_vault.root}")
        
        # Load memory nodes from local vault
        nodes_data = local_vault.read_nodes()
        nodes = [MemoryNode.from_dict(d) for d in nodes_data]
        logger.info(f"Loaded {len(nodes)} nodes from local vault")
        
        # Load episodes from local vault  
        episodes_data = local_vault.read_episodes()
        episodes = [EpisodicMemory.from_dict(d) for d in episodes_data]
        logger.info(f"Loaded {len(episodes)} episodes from local vault")
        
        # Load embeddings from local vault
        node_embeddings = local_vault.read_node_embeddings()
        if node_embeddings is None:
            logger.warning("No node embeddings found in local vault")
            node_embeddings = np.array([]).reshape(0, 768)  # Empty array with correct shape
        else:
            logger.info(f"Loaded node embeddings: {node_embeddings.shape}")
            
        episode_embeddings = local_vault.read_episode_embeddings()
        if episode_embeddings is None:
            logger.warning("No episode embeddings found in local vault")
            episode_embeddings = np.array([]).reshape(0, 768)  # Empty array with correct shape
        else:
            logger.info(f"Loaded episode embeddings: {episode_embeddings.shape}")
        
        # Load cluster info from local vault
        cluster_info = local_vault.read_clusters()
        if cluster_info:
            # Convert string keys to int
            cluster_info = {int(k) if k.lstrip('-').isdigit() else k: v for k, v in cluster_info.items()}
            logger.info(f"Loaded cluster info with {len(cluster_info)} clusters")
        else:
            cluster_info = {}
            logger.info("No cluster info found in local vault")
        
        # Load FAISS index from local vault
        faiss_index = None
        if FAISS_AVAILABLE:
            faiss_file = local_vault.faiss_index()
            if faiss_file.exists():
                try:
                    faiss_index = faiss.read_index(str(faiss_file))
                    logger.info(f"Loaded FAISS index: {faiss_index.ntotal} vectors")
                except Exception as e:
                    logger.warning(f"Failed to load FAISS index: {e}")
                    faiss_index = None
            else:
                logger.info("No FAISS index found in local vault")
        
        # Initialize components if we have data
        if len(nodes) > 0 and len(node_embeddings) > 0:
            process_retriever = ProcessMemoryRetriever(nodes, node_embeddings, cluster_info)
        else:
            process_retriever = ProcessMemoryRetriever([], np.array([]).reshape(0, 768), {})
            
        if len(episodes) > 0 and len(episode_embeddings) > 0:
            episodic_retriever = EpisodicMemoryRetriever(episodes, episode_embeddings, faiss_index)
        else:
            episodic_retriever = EpisodicMemoryRetriever([], np.array([]).reshape(0, 768), None)
        
        # Initialize embedder
        embedder = AsyncEmbedder(cache_dir=local_vault.cache_dir)
        
        # Initialize additional components
        memory_grep = None
        cluster_schema = None
        hybrid_search = None
        
        if len(nodes) > 0:
            try:
                memory_grep = MemoryGrep(nodes + episodes)
            except:
                pass
                
            try:
                schema_data = local_vault.read_cluster_schema()
                if schema_data:
                    cluster_schema = ClusterSchemaEngine(local_vault.root)
                    cluster_schema.nodes = nodes
                    cluster_schema.embeddings = node_embeddings
                    cluster_schema.cluster_info = cluster_info
                    if "profiles" in schema_data:
                        cluster_schema.profiles = {int(k): ClusterProfile(**v) for k, v in schema_data["profiles"].items()}
            except:
                pass
                
            try:
                hybrid_search = create_hybrid_search(
                    nodes=nodes,
                    embeddings=node_embeddings,
                    episodes=episodes,
                    episode_embeddings=episode_embeddings,
                )
            except:
                pass
        
        # Create retriever instance
        retriever = cls(
            process_retriever=process_retriever,
            episodic_retriever=episodic_retriever,
            embedder=embedder,
            cluster_schema=cluster_schema,
            grep_engine=memory_grep,
            hybrid_search=hybrid_search,
        )
        
        # Store reference to local vault for future operations
        retriever._local_vault = local_vault
        
        logger.info(f"DualRetriever loaded successfully from local vault")
        logger.info(f"Stats: {len(nodes)} nodes, {len(episodes)} episodes, {len(cluster_info)} clusters")
        
        return retriever

    @classmethod  
    def load_with_fallback(cls, data_dir: Optional[Path] = None, user_id: Optional[str] = None) -> "DualRetriever":
        """
        Load retriever with fallback logic.
        
        Priority:
        1. Try LocalVaultService first (NEW)
        2. Fall back to legacy data_dir if provided
        3. Fail with helpful error
        
        Args:
            data_dir: Legacy data directory (optional)
            user_id: User ID for local vault (optional)
            
        Returns:
            Initialized DualRetriever
        """
        # Try local vault first
        try:
            return cls.load_from_local_vault(user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to load from local vault: {e}")
            
        # Fall back to legacy data_dir if provided
        if data_dir:
            logger.info(f"Falling back to legacy data_dir: {data_dir}")
            return cls.load(data_dir)
            
        # No options left
        raise FileNotFoundError(
            "Could not load retriever:\n"
            "- Local vault is empty or corrupted\n"
            "- No legacy data_dir provided\n"
            "- Try running ingestion first or provide a data_dir"
        )

    def get_local_vault_status(self) -> dict:
        """Get status of the local vault."""
        if hasattr(self, '_local_vault') and self._local_vault:
            return self._local_vault.get_status()
        else:
            from core.local_vault import LocalVaultService
            local_vault = LocalVaultService()
            return local_vault.get_status()

    def sync_to_b2(self, user_id: str, config: dict) -> None:
        """Sync local vault data to B2 backup."""
        if hasattr(self, '_local_vault') and self._local_vault:
            asyncio.run(self._local_vault.sync_to_b2())
        else:
            from core.local_vault import LocalVaultService
            local_vault = LocalVaultService(user_id=user_id, b2_config=config)
            asyncio.run(local_vault.sync_to_b2())


# ═══════════════════════════════════════════════════════════════════════════