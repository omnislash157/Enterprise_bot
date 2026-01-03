"""
Local-first vault storage with B2 sync.

All reads from local ~/.cogzy/
All writes to local first, then async sync to B2.
"""

import os
import json
import platform
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

class LocalVaultService:
    """
    Local-first storage with B2 sync.
    
    Single-user structure (no user_id nesting locally).
    B2 sync uses user_id from sync/last_sync.json.
    """
    
    def __init__(self, user_id: Optional[str] = None, b2_config: Optional[dict] = None):
        self.root = self._get_platform_path()
        self.user_id = user_id  # For B2 sync mapping
        self.b2_service = None
        if b2_config:
            try:
                from core.vault_service import VaultService
                self.b2_service = VaultService(b2_config)
            except ImportError:
                logger.warning("VaultService not available, B2 sync disabled")
        
        # Ensure directories exist
        self._init_directories()
        logger.info(f"LocalVaultService initialized: {self.root}")
        
    def _get_platform_path(self) -> Path:
        """Get platform-specific cogzy folder."""
        system = platform.system()
        
        if system == "Windows":
            base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            return Path(base) / "cogzy"
        elif system == "Darwin":  # macOS
            return Path.home() / "Library" / "Application Support" / "cogzy"
        else:  # Linux and others
            xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
            return Path(xdg_data) / "cogzy"
    
    def _init_directories(self):
        """Create directory structure if not exists."""
        dirs = [
            self.root / "corpus",
            self.root / "vectors", 
            self.root / "indexes",
            self.root / "cache" / "embeddings",
            self.root / "sync",
            self.root / "config",
            self.root / "logs",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    # === Path Properties ===
    @property
    def corpus_dir(self) -> Path:
        return self.root / "corpus"
    
    @property
    def vectors_dir(self) -> Path:
        return self.root / "vectors"
    
    @property
    def indexes_dir(self) -> Path:
        return self.root / "indexes"
    
    @property
    def cache_dir(self) -> Path:
        return self.root / "cache" / "embeddings"
    
    @property
    def sync_dir(self) -> Path:
        return self.root / "sync"
    
    @property
    def config_dir(self) -> Path:
        return self.root / "config"
    
    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"
    
    # === File Paths ===
    def nodes_json(self) -> Path:
        return self.corpus_dir / "nodes.json"
    
    def episodes_json(self) -> Path:
        return self.corpus_dir / "episodes.json"
    
    def dedup_index_json(self) -> Path:
        return self.corpus_dir / "dedup_index.json"
    
    def nodes_npy(self) -> Path:
        return self.vectors_dir / "nodes.npy"
    
    def episodes_npy(self) -> Path:
        return self.vectors_dir / "episodes.npy"
    
    def faiss_index(self) -> Path:
        return self.indexes_dir / "faiss.index"
    
    def clusters_json(self) -> Path:
        return self.indexes_dir / "clusters.json"
    
    def cluster_schema_json(self) -> Path:
        return self.indexes_dir / "cluster_schema.json"
    
    def manifest_json(self) -> Path:
        return self.root / "manifest.json"
    
    def last_sync_json(self) -> Path:
        return self.sync_dir / "last_sync.json"
    
    # === Core Read Operations ===
    def read_nodes(self) -> List[dict]:
        """Read memory nodes from local."""
        path = self.nodes_json()
        if not path.exists():
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read nodes from {path}: {e}")
            return []
    
    def read_episodes(self) -> List[dict]:
        """Read episodes from local."""
        path = self.episodes_json()
        if not path.exists():
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read episodes from {path}: {e}")
            return []
    
    def read_dedup_index(self) -> Dict[str, Any]:
        """Read dedup index from local."""
        path = self.dedup_index_json()
        if not path.exists():
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read dedup index from {path}: {e}")
            return {}
    
    def read_node_embeddings(self) -> Optional[np.ndarray]:
        """Read node embeddings from local."""
        path = self.nodes_npy()
        if not path.exists():
            return None
        try:
            return np.load(path)
        except Exception as e:
            logger.error(f"Failed to load node embeddings from {path}: {e}")
            return None
    
    def read_episode_embeddings(self) -> Optional[np.ndarray]:
        """Read episode embeddings from local."""
        path = self.episodes_npy()
        if not path.exists():
            return None
        try:
            return np.load(path)
        except Exception as e:
            logger.error(f"Failed to load episode embeddings from {path}: {e}")
            return None
    
    def read_clusters(self) -> Dict[str, Any]:
        """Read cluster assignments from local."""
        path = self.clusters_json()
        if not path.exists():
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read clusters from {path}: {e}")
            return {}
    
    def read_cluster_schema(self) -> Dict[str, Any]:
        """Read cluster schema from local."""
        path = self.cluster_schema_json()
        if not path.exists():
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read cluster schema from {path}: {e}")
            return {}
    
    def read_manifest(self) -> Dict[str, Any]:
        """Read manifest from local."""
        path = self.manifest_json()
        if not path.exists():
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read manifest from {path}: {e}")
            return {}
    
    # === Core Write Operations ===
    def write_nodes(self, nodes: List[dict], sync: bool = True):
        """Write nodes to local, optionally sync to B2."""
        try:
            with open(self.nodes_json(), 'w', encoding='utf-8') as f:
                json.dump(nodes, f, default=str, indent=2)
            logger.info(f"Wrote {len(nodes)} nodes to local vault")
            if sync:
                self._queue_sync("corpus/nodes.json")
        except Exception as e:
            logger.error(f"Failed to write nodes: {e}")
    
    def write_episodes(self, episodes: List[dict], sync: bool = True):
        """Write episodes to local, optionally sync to B2."""
        try:
            with open(self.episodes_json(), 'w', encoding='utf-8') as f:
                json.dump(episodes, f, default=str, indent=2)
            logger.info(f"Wrote {len(episodes)} episodes to local vault")
            if sync:
                self._queue_sync("corpus/episodes.json")
        except Exception as e:
            logger.error(f"Failed to write episodes: {e}")
    
    def write_dedup_index(self, dedup_index: Dict[str, Any], sync: bool = True):
        """Write dedup index to local, optionally sync to B2."""
        try:
            with open(self.dedup_index_json(), 'w', encoding='utf-8') as f:
                json.dump(dedup_index, f, default=str, indent=2)
            logger.info(f"Wrote dedup index to local vault")
            if sync:
                self._queue_sync("corpus/dedup_index.json")
        except Exception as e:
            logger.error(f"Failed to write dedup index: {e}")
    
    def write_node_embeddings(self, embeddings: np.ndarray, sync: bool = True):
        """Write node embeddings to local, optionally sync to B2."""
        try:
            np.save(self.nodes_npy(), embeddings)
            logger.info(f"Wrote node embeddings {embeddings.shape} to local vault")
            if sync:
                self._queue_sync("vectors/nodes.npy")
        except Exception as e:
            logger.error(f"Failed to write node embeddings: {e}")
    
    def write_episode_embeddings(self, embeddings: np.ndarray, sync: bool = True):
        """Write episode embeddings to local, optionally sync to B2."""
        try:
            np.save(self.episodes_npy(), embeddings)
            logger.info(f"Wrote episode embeddings {embeddings.shape} to local vault")
            if sync:
                self._queue_sync("vectors/episodes.npy")
        except Exception as e:
            logger.error(f"Failed to write episode embeddings: {e}")
    
    def write_clusters(self, clusters: Dict[str, Any], sync: bool = True):
        """Write cluster assignments to local, optionally sync to B2."""
        try:
            with open(self.clusters_json(), 'w', encoding='utf-8') as f:
                json.dump(clusters, f, default=str, indent=2)
            logger.info(f"Wrote clusters to local vault")
            if sync:
                self._queue_sync("indexes/clusters.json")
        except Exception as e:
            logger.error(f"Failed to write clusters: {e}")
    
    def write_cluster_schema(self, schema: Dict[str, Any], sync: bool = True):
        """Write cluster schema to local, optionally sync to B2."""
        try:
            with open(self.cluster_schema_json(), 'w', encoding='utf-8') as f:
                json.dump(schema, f, default=str, indent=2)
            logger.info(f"Wrote cluster schema to local vault")
            if sync:
                self._queue_sync("indexes/cluster_schema.json")
        except Exception as e:
            logger.error(f"Failed to write cluster schema: {e}")
    
    def write_manifest(self, manifest: Dict[str, Any], sync: bool = False):
        """Write manifest to local (typically not synced)."""
        try:
            with open(self.manifest_json(), 'w', encoding='utf-8') as f:
                json.dump(manifest, f, default=str, indent=2)
            logger.info(f"Wrote manifest to local vault")
        except Exception as e:
            logger.error(f"Failed to write manifest: {e}")
    
    def write_faiss_index(self, faiss_index, sync: bool = True):
        """Write FAISS index to local, optionally sync to B2."""
        try:
            import faiss
            faiss.write_index(faiss_index, str(self.faiss_index()))
            logger.info(f"Wrote FAISS index to local vault")
            if sync:
                self._queue_sync("indexes/faiss.index")
        except Exception as e:
            logger.error(f"Failed to write FAISS index: {e}")
    
    # === Sync Operations ===
    def _queue_sync(self, relative_path: str):
        """Queue a file for B2 sync (async background)."""
        # For now, we'll just track what needs syncing
        # In production, this would use a proper queue/worker
        sync_queue_file = self.sync_dir / "sync_queue.json"
        
        queue = []
        if sync_queue_file.exists():
            try:
                with open(sync_queue_file, 'r') as f:
                    queue = json.load(f)
            except:
                queue = []
        
        # Add to queue if not already there
        if relative_path not in queue:
            queue.append(relative_path)
            
        with open(sync_queue_file, 'w') as f:
            json.dump(queue, f)
        
        logger.debug(f"Queued for sync: {relative_path}")
    
    async def sync_to_b2(self):
        """Push all local changes to B2."""
        if not self.b2_service or not self.user_id:
            logger.warning("B2 sync not available (no service or user_id)")
            return
        
        # Upload each file type
        files_to_sync = [
            (self.nodes_json(), f"users/{self.user_id}/corpus/nodes.json"),
            (self.episodes_json(), f"users/{self.user_id}/corpus/episodes.json"),
            (self.dedup_index_json(), f"users/{self.user_id}/corpus/dedup_index.json"),
            (self.nodes_npy(), f"users/{self.user_id}/vectors/nodes.npy"),
            (self.episodes_npy(), f"users/{self.user_id}/vectors/episodes.npy"),
            (self.clusters_json(), f"users/{self.user_id}/indexes/clusters.json"),
            (self.cluster_schema_json(), f"users/{self.user_id}/indexes/cluster_schema.json"),
            (self.faiss_index(), f"users/{self.user_id}/indexes/faiss.index"),
        ]
        
        synced_count = 0
        for local_path, b2_path in files_to_sync:
            if local_path.exists():
                try:
                    with open(local_path, 'rb') as f:
                        await self.b2_service.upload_bytes(self.user_id, b2_path.split('/', 2)[2], f.read())
                    synced_count += 1
                    logger.debug(f"Synced to B2: {b2_path}")
                except Exception as e:
                    logger.error(f"Failed to sync {b2_path}: {e}")
        
        self._update_sync_timestamp()
        logger.info(f"Synced {synced_count} files to B2")
        
        # Clear sync queue
        sync_queue_file = self.sync_dir / "sync_queue.json"
        if sync_queue_file.exists():
            sync_queue_file.unlink()
    
    async def sync_from_b2(self):
        """Pull all data from B2 to local."""
        if not self.b2_service or not self.user_id:
            logger.warning("B2 sync not available (no service or user_id)")
            return
        
        files_to_pull = [
            (f"users/{self.user_id}/corpus/nodes.json", self.nodes_json()),
            (f"users/{self.user_id}/corpus/episodes.json", self.episodes_json()),
            (f"users/{self.user_id}/corpus/dedup_index.json", self.dedup_index_json()),
            (f"users/{self.user_id}/vectors/nodes.npy", self.nodes_npy()),
            (f"users/{self.user_id}/vectors/episodes.npy", self.episodes_npy()),
            (f"users/{self.user_id}/indexes/clusters.json", self.clusters_json()),
            (f"users/{self.user_id}/indexes/cluster_schema.json", self.cluster_schema_json()),
            (f"users/{self.user_id}/indexes/faiss.index", self.faiss_index()),
        ]
        
        pulled_count = 0
        for b2_path, local_path in files_to_pull:
            try:
                content = await self.b2_service.download_file(b2_path)
                local_path.parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, 'wb') as f:
                    if isinstance(content, str):
                        f.write(content.encode('utf-8'))
                    else:
                        f.write(content)
                pulled_count += 1
                logger.debug(f"Pulled from B2: {b2_path}")
            except Exception as e:
                logger.debug(f"Could not pull {b2_path}: {e}")  # Many files won't exist yet
        
        self._update_sync_timestamp()
        logger.info(f"Pulled {pulled_count} files from B2")
    
    async def reset_from_b2(self):
        """Nuke local and re-pull everything from B2."""
        import shutil
        
        logger.warning("Resetting local vault from B2 backup")
        
        # Clear local data (keep config)
        for subdir in ["corpus", "vectors", "indexes", "cache", "sync"]:
            path = self.root / subdir
            if path.exists():
                shutil.rmtree(path)
        
        # Re-init directories
        self._init_directories()
        
        # Pull from B2
        await self.sync_from_b2()
        logger.info("Local vault reset complete")
    
    def _update_sync_timestamp(self):
        """Update last sync timestamp."""
        sync_file = self.last_sync_json()
        try:
            with open(sync_file, 'w') as f:
                json.dump({
                    "user_id": self.user_id,
                    "last_sync": datetime.utcnow().isoformat(),
                    "platform": platform.system(),
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to update sync timestamp: {e}")
    
    # === Status & Utilities ===
    def get_status(self) -> dict:
        """Get vault status and stats."""
        nodes = self.read_nodes()
        episodes = self.read_episodes()
        
        sync_file = self.last_sync_json()
        last_sync = None
        if sync_file.exists():
            try:
                with open(sync_file) as f:
                    last_sync = json.load(f)
            except:
                pass
        
        # Calculate storage size
        total_size = 0
        for root, dirs, files in os.walk(self.root):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    pass
        
        return {
            "root": str(self.root),
            "platform": platform.system(),
            "node_count": len(nodes),
            "episode_count": len(episodes),
            "last_sync": last_sync,
            "has_embeddings": self.nodes_npy().exists(),
            "has_faiss": self.faiss_index().exists(),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "files": {
                "nodes": self.nodes_json().exists(),
                "episodes": self.episodes_json().exists(),
                "dedup_index": self.dedup_index_json().exists(),
                "node_embeddings": self.nodes_npy().exists(),
                "episode_embeddings": self.episodes_npy().exists(),
                "clusters": self.clusters_json().exists(),
                "cluster_schema": self.cluster_schema_json().exists(),
                "faiss_index": self.faiss_index().exists(),
            }
        }
    
    def clear_local(self):
        """Clear all local data (for reset)."""
        import shutil
        logger.warning("Clearing all local vault data")
        
        for subdir in ["corpus", "vectors", "indexes", "cache", "sync"]:
            path = self.root / subdir
            if path.exists():
                shutil.rmtree(path)
        
        self._init_directories()
        logger.info("Local vault cleared and re-initialized")
    
    def migrate_from_legacy_data_dir(self, legacy_data_dir: Path):
        """Migrate data from old ./data structure to local vault."""
        legacy_data_dir = Path(legacy_data_dir)
        
        if not legacy_data_dir.exists():
            logger.info(f"No legacy data directory found at {legacy_data_dir}")
            return
        
        logger.info(f"Migrating legacy data from {legacy_data_dir}")
        
        # Migrate corpus files
        legacy_corpus = legacy_data_dir / "corpus"
        if legacy_corpus.exists():
            for file in ["nodes.json", "episodes.json", "dedup_index.json"]:
                src = legacy_corpus / file
                dst = self.corpus_dir / file
                if src.exists():
                    import shutil
                    shutil.copy2(src, dst)
                    logger.info(f"Migrated {file}")
        
        # Migrate vector files
        legacy_vectors = legacy_data_dir / "vectors"
        if legacy_vectors.exists():
            for file in ["nodes.npy", "episodes.npy"]:
                src = legacy_vectors / file
                dst = self.vectors_dir / file
                if src.exists():
                    import shutil
                    shutil.copy2(src, dst)
                    logger.info(f"Migrated {file}")
        
        # Migrate index files
        legacy_indexes = legacy_data_dir / "indexes"
        if legacy_indexes.exists():
            for file in ["faiss.index", "clusters.json", "cluster_schema.json"]:
                src = legacy_indexes / file
                dst = self.indexes_dir / file
                if src.exists():
                    import shutil
                    shutil.copy2(src, dst)
                    logger.info(f"Migrated {file}")
        
        # Migrate embedding cache
        legacy_cache = legacy_data_dir / "embedding_cache"
        if legacy_cache.exists():
            import shutil
            shutil.copytree(legacy_cache, self.cache_dir, dirs_exist_ok=True)
            logger.info("Migrated embedding cache")
        
        logger.info("Legacy data migration complete")