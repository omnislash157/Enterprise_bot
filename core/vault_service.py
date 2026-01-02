"""
Vault Service - Per-user B2 storage management

Handles:
- Vault provisioning on signup
- Path resolution for user data
- Upload streaming to B2
- Download/sync for pipeline access

Uses b2sdk for direct B2 API access (no FUSE mount needed).

Version: 1.0.0
"""

import os
import logging
from pathlib import Path
from typing import Optional, BinaryIO
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor
import re

from dotenv import load_dotenv
from b2sdk.v2 import B2Api, InMemoryAccountInfo

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Thread pool for blocking B2 operations
_executor = ThreadPoolExecutor(max_workers=4)


def _expand_env_vars(value: str) -> str:
    """Expand ${VAR_NAME} placeholders with environment variables."""
    if not isinstance(value, str):
        return value
    # Replace ${VAR_NAME} with environment variable value
    pattern = r'\$\{([^}]+)\}'
    def replacer(match):
        env_var = match.group(1)
        return os.getenv(env_var, match.group(0))  # Return original if not found
    return re.sub(pattern, replacer, value)


@dataclass
class VaultPaths:
    """Resolved paths for a user's vault."""
    prefix: str           # users/{uuid}
    uploads: str          # users/{uuid}/uploads
    corpus: str           # users/{uuid}/corpus
    vectors: str          # users/{uuid}/vectors
    indexes: str          # users/{uuid}/indexes

    def nodes_json(self) -> str:
        return f"{self.corpus}/nodes.json"

    def embeddings_npy(self) -> str:
        return f"{self.vectors}/nodes.npy"

    def upload_path(self, source_type: str, filename: str) -> str:
        return f"{self.uploads}/{source_type}/{filename}"


class VaultService:
    """
    B2-backed per-user vault management.

    Each user gets isolated storage:
        b2://bucket/users/{user_uuid}/
            ├── uploads/anthropic/
            ├── uploads/openai/
            ├── corpus/nodes.json
            ├── vectors/nodes.npy
            └── indexes/clusters.json
    """

    def __init__(self, config: dict):
        """
        Initialize with vault config from config.yaml.

        Expected config:
            vault:
              bucket: cogzy-vaults
              key_id: ${B2_APPLICATION_KEY_ID}
              app_key: ${B2_APPLICATION_KEY}
              base_prefix: users
        """
        vault_config = config.get("vault", {})

        # Expand environment variables in config values
        self.bucket_name = _expand_env_vars(vault_config.get("bucket")) or os.getenv("B2_BUCKET_NAME")
        key_id = _expand_env_vars(vault_config.get("key_id")) or os.getenv("B2_APPLICATION_KEY_ID")
        app_key = _expand_env_vars(vault_config.get("app_key")) or os.getenv("B2_APPLICATION_KEY")
        self.base_prefix = vault_config.get("base_prefix", "users")
        self.structure = vault_config.get("structure", {
            "uploads": "uploads",
            "corpus": "corpus",
            "vectors": "vectors",
            "indexes": "indexes"
        })

        if not all([self.bucket_name, key_id, app_key]):
            raise ValueError(
                "B2 credentials not configured. Set B2_BUCKET_NAME, "
                "B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY in .env"
            )

        # Initialize B2 API
        info = InMemoryAccountInfo()
        self.b2_api = B2Api(info)
        self.b2_api.authorize_account("production", key_id, app_key)
        self.bucket = self.b2_api.get_bucket_by_name(self.bucket_name)

        logger.info(f"VaultService initialized: bucket={self.bucket_name}")

    def get_paths(self, user_id: str) -> VaultPaths:
        """Get all vault paths for a user."""
        prefix = f"{self.base_prefix}/{user_id}"
        return VaultPaths(
            prefix=prefix,
            uploads=f"{prefix}/{self.structure['uploads']}",
            corpus=f"{prefix}/{self.structure['corpus']}",
            vectors=f"{prefix}/{self.structure['vectors']}",
            indexes=f"{prefix}/{self.structure['indexes']}"
        )

    async def create_vault(self, user_id: str) -> VaultPaths:
        """
        Provision a new vault for a user.

        Creates the directory structure by uploading placeholder files.
        B2 doesn't have real directories - they're implied by file paths.

        Returns VaultPaths for the new vault.
        """
        paths = self.get_paths(user_id)

        # Create placeholder files to establish directory structure
        # (B2 directories only exist if files exist within them)
        placeholders = [
            f"{paths.uploads}/.keep",
            f"{paths.corpus}/.keep",
            f"{paths.vectors}/.keep",
            f"{paths.indexes}/.keep",
        ]

        def _create_placeholders():
            for path in placeholders:
                self.bucket.upload_bytes(
                    data_bytes=b"",
                    file_name=path,
                    content_type="application/octet-stream"
                )
            logger.info(f"Created vault for user {user_id}: {paths.prefix}")

        # Run blocking B2 operation in thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, _create_placeholders)

        return paths

    async def upload_file(
        self,
        user_id: str,
        source_type: str,
        filename: str,
        file_data: BinaryIO,
        content_type: str = "application/json"
    ) -> str:
        """
        Upload a file to user's vault.

        Args:
            user_id: User UUID
            source_type: anthropic, openai, grok, gemini
            filename: Original filename
            file_data: File-like object to upload
            content_type: MIME type

        Returns:
            B2 file path where uploaded
        """
        paths = self.get_paths(user_id)
        dest_path = paths.upload_path(source_type, filename)

        def _upload():
            # Read all data (for small files) or use upload_stream for large
            data = file_data.read()
            self.bucket.upload_bytes(
                data_bytes=data,
                file_name=dest_path,
                content_type=content_type
            )
            return dest_path

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _upload)

        logger.info(f"Uploaded {filename} to {dest_path} ({len(file_data.read()) if hasattr(file_data, 'read') else 'stream'} bytes)")
        return result

    async def download_file(self, file_path: str) -> bytes:
        """Download a file from B2."""
        def _download():
            from io import BytesIO
            buffer = BytesIO()
            self.bucket.download_file_by_name(file_path).save(buffer)
            buffer.seek(0)
            return buffer.read()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _download)

    async def upload_bytes(
        self,
        user_id: str,
        relative_path: str,
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        Upload raw bytes to user's vault.

        Used by pipeline to write processed files:
            vault.upload_bytes(user_id, "corpus/nodes.json", json_bytes)
        """
        paths = self.get_paths(user_id)
        full_path = f"{paths.prefix}/{relative_path}"

        def _upload():
            self.bucket.upload_bytes(
                data_bytes=data,
                file_name=full_path,
                content_type=content_type
            )
            return full_path

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _upload)

        logger.info(f"Uploaded {len(data)} bytes to {full_path}")
        return result

    async def file_exists(self, file_path: str) -> bool:
        """Check if a file exists in B2."""
        def _check():
            try:
                self.bucket.get_file_info_by_name(file_path)
                return True
            except Exception:
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _check)

    async def list_files(self, prefix: str) -> list[str]:
        """List all files under a prefix."""
        def _list():
            files = []
            for file_version, _ in self.bucket.ls(prefix, recursive=True):
                files.append(file_version.file_name)
            return files

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _list)

    async def get_vault_stats(self, user_id: str) -> dict:
        """Get stats for a user's vault."""
        paths = self.get_paths(user_id)

        def _get_stats():
            total_bytes = 0
            file_count = 0

            for file_version, _ in self.bucket.ls(paths.prefix, recursive=True):
                if not file_version.file_name.endswith("/.keep"):
                    total_bytes += file_version.size
                    file_count += 1

            return {
                "total_bytes": total_bytes,
                "file_count": file_count,
                "prefix": paths.prefix
            }

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _get_stats)


# =============================================================================
# SINGLETON
# =============================================================================

_vault_service: Optional[VaultService] = None


def get_vault_service(config: dict) -> VaultService:
    """Get or create the vault service singleton."""
    global _vault_service
    if _vault_service is None:
        _vault_service = VaultService(config)
    return _vault_service
