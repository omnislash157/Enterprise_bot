# VAULT INGESTION BUILD: Personal Memory Vaults

**Priority:** P0  
**Estimated Complexity:** High (multi-phase)  
**Dependencies:** personal_auth (COMPLETE), B2 credentials (IN .env)

---

## OVERVIEW

### User Story
> As a Cogzy personal tier user, I want to upload my Anthropic/OpenAI chat exports so that my AI has persistent memory of everything I've discussed.

### Architecture Summary
```
User Signup → Eager Vault Provisioning (B2)
     ↓
Upload Button → Stream to B2 → Queue Job
     ↓
Pipeline: Parse → Dedupe → Embed (GPU parallel) → Cluster → Save to Vault
     ↓
Memory retrieval scoped to user's vault only
```

### Acceptance Criteria
- [ ] User signup creates B2 vault prefix automatically
- [ ] Upload endpoint accepts conversations.json / .zip files
- [ ] Pipeline processes uploads into user's vault (not global ./data)
- [ ] Free tier: 20 messages/day, upload enabled (the hook)
- [ ] Premium tier: unlimited messages, full memory features
- [ ] Dedupe prevents re-processing same conversations
- [ ] Progress tracking for upload processing

---

## DEPENDENCY GRAPH

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: FOUNDATION                          │
│                    (Must complete first)                        │
├─────────────────────────────────────────────────────────────────┤
│  TASK 1A: Database Migration (personal.vaults, vault_uploads)   │
│  TASK 1B: Config Updates (tiers, feature flags)                 │
│                                                                 │
│  These can run in PARALLEL                                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 2: CORE SERVICES                       │
│                    (Depends on Phase 1)                         │
├─────────────────────────────────────────────────────────────────┤
│  TASK 2A: Vault Service (B2 integration)                        │
│  TASK 2B: Tier Service (free/premium logic)                     │
│                                                                 │
│  These can run in PARALLEL                                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 3: INTEGRATION                         │
│                    (Depends on Phase 2)                         │
├─────────────────────────────────────────────────────────────────┤
│  TASK 3A: Upload Endpoint (routes + job queue)                  │
│  TASK 3B: Pipeline Modification (B2 paths + user scoping)       │
│                                                                 │
│  These can run in PARALLEL                                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 4: WIRING                              │
│                    (Depends on Phase 3)                         │
├─────────────────────────────────────────────────────────────────┤
│  TASK 4A: Wire vault creation into signup flow                  │
│  TASK 4B: Wire tier checks into chat endpoint                   │
│  TASK 4C: Frontend upload component                             │
│                                                                 │
│  4A and 4B can run in PARALLEL, 4C depends on API ready         │
└─────────────────────────────────────────────────────────────────┘
```

---

## PHASE 1: FOUNDATION

### TASK 1A: Database Migration

**File:** `migrations/007_personal_vaults.sql`

```sql
-- Personal Vaults - Per-user cloud storage for memory
-- Part of Cogzy personal tier

BEGIN;

-- Vault metadata
CREATE TABLE personal.vaults (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES personal.users(id) ON DELETE CASCADE,
    
    -- B2 location
    bucket TEXT NOT NULL DEFAULT 'cogzy-vaults',
    prefix TEXT NOT NULL,  -- users/{user_uuid}
    
    -- Stats (updated by pipeline)
    node_count INTEGER DEFAULT 0,
    total_bytes BIGINT DEFAULT 0,
    last_sync_at TIMESTAMPTZ,
    
    -- State machine
    status TEXT NOT NULL DEFAULT 'empty' 
        CHECK (status IN ('empty', 'syncing', 'ready', 'error')),
    error_message TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_user_vault UNIQUE(user_id)
);

-- Upload tracking
CREATE TABLE personal.vault_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vault_id UUID NOT NULL REFERENCES personal.vaults(id) ON DELETE CASCADE,
    
    -- Source identification
    source_type TEXT NOT NULL 
        CHECK (source_type IN ('anthropic', 'openai', 'grok', 'gemini', 'unknown')),
    original_filename TEXT,
    uploaded_bytes BIGINT,
    
    -- Processing state
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'complete', 'failed')),
    progress_pct INTEGER DEFAULT 0,
    
    -- Results
    nodes_created INTEGER DEFAULT 0,
    nodes_deduplicated INTEGER DEFAULT 0,
    error_message TEXT,
    
    -- Timing
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ
);

-- User tier tracking (for rate limiting)
CREATE TABLE personal.user_tiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES personal.users(id) ON DELETE CASCADE,
    
    tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'premium')),
    
    -- Usage tracking (reset daily)
    messages_today INTEGER DEFAULT 0,
    messages_reset_at DATE DEFAULT CURRENT_DATE,
    
    -- Subscription info (for premium)
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    subscription_status TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_user_tier UNIQUE(user_id)
);

-- Indexes
CREATE INDEX idx_vaults_user ON personal.vaults(user_id);
CREATE INDEX idx_vaults_status ON personal.vaults(status);
CREATE INDEX idx_uploads_vault ON personal.vault_uploads(vault_id);
CREATE INDEX idx_uploads_status ON personal.vault_uploads(status);
CREATE INDEX idx_tiers_user ON personal.user_tiers(user_id);

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER vaults_updated_at
    BEFORE UPDATE ON personal.vaults
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tiers_updated_at
    BEFORE UPDATE ON personal.user_tiers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMIT;
```

**Verification:**
```sql
\dt personal.*
-- Should show: users, vaults, vault_uploads, user_tiers

SELECT column_name, data_type FROM information_schema.columns 
WHERE table_schema = 'personal' AND table_name = 'vaults';
```

---

### TASK 1B: Config Updates

**File:** `config.yaml` - Add tier configuration

Find the `features:` section and add after it:

```yaml
# =============================================================================
# USER TIERS (Personal SaaS)
# =============================================================================
tiers:
  free:
    messages_per_day: 20
    upload_enabled: true        # The hook - let them taste memory
    max_vault_size_mb: 100      # ~10k conversations
    features:
      - basic_chat
      - memory_upload
      - context_window_1m       # Use Grok's context
  
  premium:
    messages_per_day: -1        # Unlimited (-1)
    upload_enabled: true
    max_vault_size_mb: 10000    # 10GB - years of conversation
    features:
      - basic_chat
      - memory_upload
      - context_window_2m
      - memory_search
      - metacognitive_mirror
      - voice_mode
    price_monthly_usd: 20

# =============================================================================
# VAULT STORAGE (B2)
# =============================================================================
vault:
  provider: b2
  bucket: ${B2_BUCKET_NAME}          # From .env
  key_id: ${B2_APPLICATION_KEY_ID}   # From .env  
  app_key: ${B2_APPLICATION_KEY}     # From .env
  base_prefix: users                 # users/{user_uuid}/...
  
  # Subdirectories created per user
  structure:
    uploads: uploads      # Raw chat exports
    corpus: corpus        # Processed nodes.json
    vectors: vectors      # Embeddings .npy files
    indexes: indexes      # FAISS, clusters

# =============================================================================
# INGESTION PIPELINE (Personal tier)
# =============================================================================
ingestion:
  enabled: true
  
  # Embedding acceleration
  embedder:
    provider: deepinfra
    model: BAAI/bge-m3
    max_concurrent: 200           # DeepInfra limit - redline it
    batch_size: 32
    
  # Job queue (Redis)
  queue:
    redis_key_prefix: cogzy:jobs
    max_retries: 3
    job_timeout_seconds: 3600     # 1 hour max per upload
    
  # Deduplication
  dedup:
    enabled: true
    hash_fields:                  # Fields used for content hash
      - human_content
      - assistant_content
      - conversation_id
```

**File:** `config.yaml` - Update paths section

Replace the existing `paths:` section:

```yaml
# =============================================================================
# PATHS
# =============================================================================
paths:
  # Local paths (enterprise mode / dev fallback)
  data_dir: ./data
  manuals_root: ./manuals
  
  # Personal tier uses vault paths instead
  # Resolved at runtime: vault.base_prefix/{user_id}/corpus/nodes.json
```

**Verification:**
```bash
python -c "from config_loader import load_config; c = load_config(); print(c.get('tiers', {}).get('free', {}))"
# Should print: {'messages_per_day': 20, 'upload_enabled': True, ...}
```

---

## PHASE 2: CORE SERVICES

### TASK 2A: Vault Service

**File:** `core/vault_service.py`

```python
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

from b2sdk.v2 import B2Api, InMemoryAccountInfo

logger = logging.getLogger(__name__)

# Thread pool for blocking B2 operations
_executor = ThreadPoolExecutor(max_workers=4)


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
        
        self.bucket_name = vault_config.get("bucket") or os.getenv("B2_BUCKET_NAME")
        key_id = vault_config.get("key_id") or os.getenv("B2_APPLICATION_KEY_ID")
        app_key = vault_config.get("app_key") or os.getenv("B2_APPLICATION_KEY")
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
            downloaded = self.bucket.download_file_by_name(file_path)
            return downloaded.read()
        
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
```

**Verification:**
```python
# Test B2 connection
python -c "
from core.vault_service import VaultService
from config_loader import load_config
vs = VaultService(load_config())
print(f'Connected to bucket: {vs.bucket_name}')
"
```

---

### TASK 2B: Tier Service

**File:** `core/tier_service.py`

```python
"""
Tier Service - Free/Premium usage management

Handles:
- Message rate limiting (20/day free, unlimited premium)
- Feature gating
- Usage tracking
- Tier upgrades (Stripe integration placeholder)

Version: 1.0.0
"""

import logging
from datetime import date
from typing import Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Tier(Enum):
    FREE = "free"
    PREMIUM = "premium"


@dataclass
class TierLimits:
    """Limits for a tier."""
    messages_per_day: int  # -1 = unlimited
    upload_enabled: bool
    max_vault_size_mb: int
    features: list[str]


@dataclass
class UsageStatus:
    """Current usage status for a user."""
    tier: Tier
    messages_today: int
    messages_limit: int  # -1 = unlimited
    messages_remaining: int  # -1 = unlimited
    can_send_message: bool
    upload_enabled: bool
    features: list[str]


class TierService:
    """
    Manages user tiers and rate limiting.
    
    Usage:
        tier_service = TierService(config, db_pool)
        
        # Check before processing message
        status = await tier_service.get_usage_status(user_id)
        if not status.can_send_message:
            return "Daily limit reached. Upgrade to premium!"
        
        # After successful message
        await tier_service.increment_usage(user_id)
    """
    
    def __init__(self, config: dict, db_pool):
        """
        Args:
            config: Full config with 'tiers' section
            db_pool: asyncpg connection pool
        """
        self.db = db_pool
        
        # Load tier configs
        tiers_config = config.get("tiers", {})
        
        self.tier_limits = {
            Tier.FREE: TierLimits(
                messages_per_day=tiers_config.get("free", {}).get("messages_per_day", 20),
                upload_enabled=tiers_config.get("free", {}).get("upload_enabled", True),
                max_vault_size_mb=tiers_config.get("free", {}).get("max_vault_size_mb", 100),
                features=tiers_config.get("free", {}).get("features", ["basic_chat"])
            ),
            Tier.PREMIUM: TierLimits(
                messages_per_day=tiers_config.get("premium", {}).get("messages_per_day", -1),
                upload_enabled=tiers_config.get("premium", {}).get("upload_enabled", True),
                max_vault_size_mb=tiers_config.get("premium", {}).get("max_vault_size_mb", 10000),
                features=tiers_config.get("premium", {}).get("features", [
                    "basic_chat", "memory_upload", "memory_search", 
                    "metacognitive_mirror", "voice_mode"
                ])
            )
        }
        
        logger.info(f"TierService initialized: free={self.tier_limits[Tier.FREE].messages_per_day}/day")
    
    async def ensure_tier_record(self, user_id: str) -> None:
        """Create tier record if not exists (called on signup)."""
        async with self.db.acquire() as conn:
            await conn.execute("""
                INSERT INTO personal.user_tiers (user_id, tier)
                VALUES ($1, 'free')
                ON CONFLICT (user_id) DO NOTHING
            """, user_id)
    
    async def get_user_tier(self, user_id: str) -> Tier:
        """Get user's current tier."""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT tier FROM personal.user_tiers WHERE user_id = $1",
                user_id
            )
            if not row:
                # Auto-create free tier
                await self.ensure_tier_record(user_id)
                return Tier.FREE
            return Tier(row["tier"])
    
    async def get_usage_status(self, user_id: str) -> UsageStatus:
        """
        Get full usage status for a user.
        
        Handles daily reset automatically.
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT tier, messages_today, messages_reset_at
                FROM personal.user_tiers
                WHERE user_id = $1
            """, user_id)
            
            if not row:
                await self.ensure_tier_record(user_id)
                tier = Tier.FREE
                messages_today = 0
            else:
                tier = Tier(row["tier"])
                messages_today = row["messages_today"]
                reset_date = row["messages_reset_at"]
                
                # Check if we need to reset (new day)
                if reset_date < date.today():
                    await conn.execute("""
                        UPDATE personal.user_tiers
                        SET messages_today = 0, messages_reset_at = CURRENT_DATE
                        WHERE user_id = $1
                    """, user_id)
                    messages_today = 0
            
            limits = self.tier_limits[tier]
            
            # Calculate remaining
            if limits.messages_per_day == -1:
                messages_remaining = -1
                can_send = True
            else:
                messages_remaining = max(0, limits.messages_per_day - messages_today)
                can_send = messages_remaining > 0
            
            return UsageStatus(
                tier=tier,
                messages_today=messages_today,
                messages_limit=limits.messages_per_day,
                messages_remaining=messages_remaining,
                can_send_message=can_send,
                upload_enabled=limits.upload_enabled,
                features=limits.features
            )
    
    async def increment_usage(self, user_id: str) -> int:
        """
        Increment message count for today.
        
        Returns new count.
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE personal.user_tiers
                SET messages_today = messages_today + 1
                WHERE user_id = $1
                RETURNING messages_today
            """, user_id)
            
            if not row:
                await self.ensure_tier_record(user_id)
                return 1
            
            return row["messages_today"]
    
    async def upgrade_to_premium(
        self, 
        user_id: str,
        stripe_customer_id: str,
        stripe_subscription_id: str
    ) -> bool:
        """
        Upgrade user to premium tier.
        
        Called after successful Stripe payment.
        """
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE personal.user_tiers
                SET tier = 'premium',
                    stripe_customer_id = $2,
                    stripe_subscription_id = $3,
                    subscription_status = 'active'
                WHERE user_id = $1
            """, user_id, stripe_customer_id, stripe_subscription_id)
            
            logger.info(f"Upgraded user {user_id} to premium")
            return True
    
    async def downgrade_to_free(self, user_id: str) -> bool:
        """
        Downgrade user to free tier.
        
        Called on subscription cancellation.
        """
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE personal.user_tiers
                SET tier = 'free',
                    subscription_status = 'cancelled'
                WHERE user_id = $1
            """, user_id)
            
            logger.info(f"Downgraded user {user_id} to free")
            return True
    
    def has_feature(self, status: UsageStatus, feature: str) -> bool:
        """Check if user has access to a feature."""
        return feature in status.features


# =============================================================================
# SINGLETON
# =============================================================================

_tier_service: Optional[TierService] = None


async def get_tier_service(config: dict, db_pool) -> TierService:
    """Get or create the tier service singleton."""
    global _tier_service
    if _tier_service is None:
        _tier_service = TierService(config, db_pool)
    return _tier_service
```

**Verification:**
```python
# Test tier logic
python -c "
from core.tier_service import TierService, Tier

# Mock config
config = {
    'tiers': {
        'free': {'messages_per_day': 20},
        'premium': {'messages_per_day': -1}
    }
}

# Can't fully test without DB, but verify class loads
ts = TierService(config, None)
print(f'Free limit: {ts.tier_limits[Tier.FREE].messages_per_day}')
print(f'Premium limit: {ts.tier_limits[Tier.PREMIUM].messages_per_day}')
"
```

---

## PHASE 3: INTEGRATION

### TASK 3A: Upload Endpoint

**File:** `routes/personal_vault.py`

```python
"""
Personal Vault Routes - Upload and status endpoints

Endpoints:
- POST /api/personal/vault/upload - Upload chat export
- GET /api/personal/vault/status - Get vault status
- GET /api/personal/vault/upload/{upload_id} - Get upload progress

Version: 1.0.0
"""

import logging
import json
from uuid import UUID
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel

from auth.personal_auth import get_current_user, SessionData
from core.vault_service import get_vault_service, VaultService
from core.tier_service import get_tier_service, TierService
from config_loader import load_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/personal/vault", tags=["personal-vault"])

# Response models
class UploadResponse(BaseModel):
    upload_id: str
    status: str
    message: str

class VaultStatus(BaseModel):
    node_count: int
    total_bytes: int
    status: str
    last_sync_at: Optional[datetime]
    uploads: list[dict]

class UploadProgress(BaseModel):
    upload_id: str
    status: str
    progress_pct: int
    nodes_created: int
    nodes_deduplicated: int
    error_message: Optional[str]


def detect_source_type(filename: str, content_sample: bytes) -> str:
    """Detect the source type from filename or content."""
    filename_lower = filename.lower()
    
    if "anthropic" in filename_lower or "claude" in filename_lower:
        return "anthropic"
    elif "openai" in filename_lower or "chatgpt" in filename_lower:
        return "openai"
    elif "grok" in filename_lower:
        return "grok"
    elif "gemini" in filename_lower:
        return "gemini"
    
    # Try to detect from content structure
    try:
        data = json.loads(content_sample[:10000].decode('utf-8', errors='ignore'))
        
        # Anthropic format has specific structure
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if "uuid" in first and "chat_messages" in first:
                return "anthropic"
            elif "mapping" in first:
                return "openai"
    except:
        pass
    
    return "unknown"


async def process_upload_job(
    upload_id: str,
    user_id: str,
    source_type: str,
    file_path: str,
    db_pool,
    config: dict
):
    """
    Background job to process an upload.
    
    1. Download from B2 (or use local temp)
    2. Run through ingestion pipeline
    3. Update upload status
    """
    from memory.ingest.pipeline import run_pipeline_for_user
    
    logger.info(f"Starting upload processing: {upload_id}")
    
    async with db_pool.acquire() as conn:
        # Mark as processing
        await conn.execute("""
            UPDATE personal.vault_uploads
            SET status = 'processing', processing_started_at = NOW()
            WHERE id = $1
        """, upload_id)
    
    try:
        # Run pipeline
        result = await run_pipeline_for_user(
            user_id=user_id,
            source_type=source_type,
            upload_id=upload_id,
            config=config
        )
        
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE personal.vault_uploads
                SET status = 'complete',
                    progress_pct = 100,
                    nodes_created = $2,
                    nodes_deduplicated = $3,
                    processing_completed_at = NOW()
                WHERE id = $1
            """, upload_id, result["nodes_created"], result["nodes_deduplicated"])
            
            # Update vault stats
            await conn.execute("""
                UPDATE personal.vaults
                SET node_count = node_count + $2,
                    status = 'ready',
                    last_sync_at = NOW()
                WHERE user_id = $1
            """, user_id, result["nodes_created"])
        
        logger.info(f"Upload {upload_id} complete: {result['nodes_created']} nodes")
        
    except Exception as e:
        logger.exception(f"Upload {upload_id} failed: {e}")
        
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE personal.vault_uploads
                SET status = 'failed', error_message = $2
                WHERE id = $1
            """, upload_id, str(e))


@router.post("/upload", response_model=UploadResponse)
async def upload_chat_export(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: SessionData = Depends(get_current_user),
    vault_service: VaultService = Depends(lambda: get_vault_service(load_config())),
    tier_service: TierService = Depends(lambda: get_tier_service(load_config(), None)),  # TODO: wire db_pool
):
    """
    Upload a chat export file for processing.
    
    Accepts:
    - Anthropic conversations.json
    - OpenAI export .zip or conversations.json
    - Grok/Gemini exports
    
    Returns upload_id for progress tracking.
    """
    user_id = session.user_id
    
    # Check tier allows upload
    # TODO: Get actual status when db is wired
    # status = await tier_service.get_usage_status(user_id)
    # if not status.upload_enabled:
    #     raise HTTPException(403, "Upload not available on your tier")
    
    # Read file content
    content = await file.read()
    
    if len(content) == 0:
        raise HTTPException(400, "Empty file")
    
    # Detect source type
    source_type = detect_source_type(file.filename, content)
    
    # Upload to B2
    from io import BytesIO
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_filename = f"{timestamp}_{file.filename}"
    
    await vault_service.upload_file(
        user_id=user_id,
        source_type=source_type,
        filename=dest_filename,
        file_data=BytesIO(content),
        content_type=file.content_type or "application/json"
    )
    
    # Create upload record
    # TODO: Wire actual db_pool
    config = load_config()
    
    # For now, generate upload_id (will come from DB insert)
    import uuid
    upload_id = str(uuid.uuid4())
    
    # Queue background job
    background_tasks.add_task(
        process_upload_job,
        upload_id=upload_id,
        user_id=user_id,
        source_type=source_type,
        file_path=f"users/{user_id}/uploads/{source_type}/{dest_filename}",
        db_pool=None,  # TODO: Wire
        config=config
    )
    
    logger.info(f"Queued upload {upload_id} for user {user_id}: {source_type}")
    
    return UploadResponse(
        upload_id=upload_id,
        status="processing",
        message=f"Upload received. Processing {source_type} export..."
    )


@router.get("/status", response_model=VaultStatus)
async def get_vault_status(
    session: SessionData = Depends(get_current_user),
):
    """Get current vault status and recent uploads."""
    user_id = session.user_id
    
    # TODO: Query actual database
    # For now return placeholder
    return VaultStatus(
        node_count=0,
        total_bytes=0,
        status="empty",
        last_sync_at=None,
        uploads=[]
    )


@router.get("/upload/{upload_id}", response_model=UploadProgress)
async def get_upload_progress(
    upload_id: str,
    session: SessionData = Depends(get_current_user),
):
    """Get progress of a specific upload."""
    # TODO: Query actual database
    return UploadProgress(
        upload_id=upload_id,
        status="processing",
        progress_pct=50,
        nodes_created=0,
        nodes_deduplicated=0,
        error_message=None
    )
```

**Wire into main.py:**
```python
# Add import (near other route imports)
from routes.personal_vault import router as personal_vault_router

# Add router (in startup section)
app.include_router(personal_vault_router)
logger.info("[STARTUP] Personal vault routes loaded at /api/personal/vault")
```

**Verification:**
```bash
# After server running
curl -X POST http://localhost:8000/api/personal/vault/upload \
  -H "Cookie: session_id=xxx" \
  -F "file=@conversations.json"
```

---

### TASK 3B: Pipeline Modification

**File:** `memory/ingest/pipeline.py` - Add user-scoped entry point

Add this function to the existing pipeline.py (don't replace, append):

```python
# =============================================================================
# USER-SCOPED PIPELINE ENTRY POINT
# =============================================================================

async def run_pipeline_for_user(
    user_id: str,
    source_type: str,
    upload_id: str,
    config: dict,
) -> dict:
    """
    Run ingestion pipeline for a specific user's upload.
    
    Reads from user's B2 vault, processes, writes back to vault.
    
    Args:
        user_id: User UUID
        source_type: anthropic, openai, grok, gemini
        upload_id: UUID of the vault_uploads record
        config: Full config dict
        
    Returns:
        dict with nodes_created, nodes_deduplicated counts
    """
    from core.vault_service import get_vault_service
    
    vault = get_vault_service(config)
    paths = vault.get_paths(user_id)
    
    logger.info(f"Running pipeline for user {user_id}, upload {upload_id}")
    
    # 1. List files in uploads/{source_type}/
    upload_prefix = f"{paths.uploads}/{source_type}/"
    upload_files = await vault.list_files(upload_prefix)
    
    if not upload_files:
        raise ValueError(f"No files found in {upload_prefix}")
    
    # 2. Download and parse each file
    all_exchanges = []
    for file_path in upload_files:
        if file_path.endswith("/.keep"):
            continue
            
        content = await vault.download_file(file_path)
        
        # Use existing chat parser
        from memory.ingest.chat_parser import parse_chat_export
        exchanges = parse_chat_export(content, source_type)
        all_exchanges.extend(exchanges)
    
    logger.info(f"Parsed {len(all_exchanges)} exchanges from {len(upload_files)} files")
    
    # 3. Load existing nodes for dedup
    existing_nodes = []
    try:
        existing_content = await vault.download_file(paths.nodes_json())
        existing_data = json.loads(existing_content)
        existing_nodes = [MemoryNode.from_dict(d) for d in existing_data]
    except:
        pass  # No existing nodes yet
    
    # 4. Deduplicate
    from memory.ingest.dedup import deduplicate_exchanges
    new_exchanges, dedup_count = deduplicate_exchanges(
        all_exchanges, 
        existing_nodes
    )
    
    logger.info(f"After dedup: {len(new_exchanges)} new, {dedup_count} duplicates skipped")
    
    if not new_exchanges:
        return {"nodes_created": 0, "nodes_deduplicated": dedup_count}
    
    # 5. Convert to nodes
    nodes = [exchange_to_node(ex, user_id=user_id) for ex in new_exchanges]
    
    # 6. Embed (GPU parallel)
    from embedder import get_embedder
    embedder = get_embedder(config)
    
    texts = [f"{n.human_content} {n.assistant_content}" for n in nodes]
    embeddings = await embedder.embed_batch(texts, show_progress=True)
    
    # 7. Cluster (optional, can skip for now)
    # from streaming_cluster import StreamingClusterEngine
    # ...
    
    # 8. Save to vault
    # Merge with existing
    all_nodes = existing_nodes + nodes
    nodes_json = json.dumps([n.to_dict() for n in all_nodes], default=str)
    await vault.upload_bytes(user_id, "corpus/nodes.json", nodes_json.encode())
    
    # Save embeddings
    import numpy as np
    if existing_nodes:
        # Load existing embeddings
        try:
            existing_emb_bytes = await vault.download_file(paths.embeddings_npy())
            existing_emb = np.load(BytesIO(existing_emb_bytes))
            all_embeddings = np.vstack([existing_emb, np.array(embeddings)])
        except:
            all_embeddings = np.array(embeddings)
    else:
        all_embeddings = np.array(embeddings)
    
    emb_buffer = BytesIO()
    np.save(emb_buffer, all_embeddings)
    await vault.upload_bytes(user_id, "vectors/nodes.npy", emb_buffer.getvalue())
    
    logger.info(f"Saved {len(nodes)} new nodes to vault ({len(all_nodes)} total)")
    
    return {
        "nodes_created": len(nodes),
        "nodes_deduplicated": dedup_count
    }


def exchange_to_node(exchange: dict, user_id: str) -> MemoryNode:
    """Convert a parsed exchange to a MemoryNode with user scoping."""
    from core.schemas import MemoryNode, Source
    
    return MemoryNode(
        id=exchange.get("id") or hashlib.sha256(
            f"{exchange['human'][:100]}{exchange['assistant'][:100]}".encode()
        ).hexdigest()[:16],
        source=Source(exchange.get("source", "unknown")),
        conversation_id=exchange.get("conversation_id", "import"),
        sequence_index=exchange.get("sequence_index", 0),
        created_at=exchange.get("timestamp") or datetime.now(),
        human_content=exchange["human"],
        assistant_content=exchange["assistant"],
        user_id=user_id,  # CRITICAL: Scope to user
        tenant_id=None,   # Personal tier, no tenant
    )
```

---

## PHASE 4: WIRING

### TASK 4A: Wire Vault Creation into Signup

**File:** `auth/personal_auth.py` - Modify `register_email` and `google_auth`

In `register_email`, after the user INSERT succeeds, add:

```python
# After: return AuthResult(success=True, user_id=str(user["id"]), ...)

# Add vault provisioning
from core.vault_service import get_vault_service
from config_loader import load_config

try:
    vault_service = get_vault_service(load_config())
    await vault_service.create_vault(str(user["id"]))
    
    # Create vault record in DB
    await conn.execute("""
        INSERT INTO personal.vaults (user_id, prefix, status)
        VALUES ($1, $2, 'empty')
    """, user["id"], f"users/{user['id']}")
    
    # Create tier record
    await conn.execute("""
        INSERT INTO personal.user_tiers (user_id, tier)
        VALUES ($1, 'free')
    """, user["id"])
    
    logger.info(f"Provisioned vault for new user: {user['email']}")
except Exception as e:
    logger.error(f"Vault provisioning failed for {user['email']}: {e}")
    # Don't fail registration - vault can be created later
```

Same pattern in `google_auth` after new user creation.

---

### TASK 4B: Wire Tier Checks into Chat

**File:** `main.py` - In the chat endpoint, add tier check

Find the chat/message handler and add before processing:

```python
# Add import at top
from core.tier_service import get_tier_service

# In chat handler, before processing message:
tier_service = await get_tier_service(config, db_pool)
usage_status = await tier_service.get_usage_status(user_id)

if not usage_status.can_send_message:
    return {
        "error": "daily_limit",
        "message": f"You've used all {usage_status.messages_limit} messages for today. Upgrade to premium for unlimited messages!",
        "messages_used": usage_status.messages_today,
        "resets_at": "midnight UTC"
    }

# After successful response:
await tier_service.increment_usage(user_id)
```

---

### TASK 4C: Frontend Upload Component

**File:** `frontend-cogzy/src/lib/components/VaultUpload.svelte`

```svelte
<script lang="ts">
    import { onMount } from 'svelte';
    
    let files: FileList | null = null;
    let uploading = false;
    let uploadStatus: string | null = null;
    let uploadId: string | null = null;
    let progress = 0;
    let error: string | null = null;
    
    const API_URL = import.meta.env.VITE_API_URL || '';
    
    async function handleUpload() {
        if (!files || files.length === 0) return;
        
        uploading = true;
        error = null;
        uploadStatus = 'Uploading...';
        
        const formData = new FormData();
        formData.append('file', files[0]);
        
        try {
            const res = await fetch(`${API_URL}/api/personal/vault/upload`, {
                method: 'POST',
                body: formData,
                credentials: 'include'
            });
            
            if (!res.ok) {
                throw new Error(await res.text());
            }
            
            const data = await res.json();
            uploadId = data.upload_id;
            uploadStatus = data.message;
            
            // Poll for progress
            pollProgress();
            
        } catch (e) {
            error = e.message;
            uploading = false;
        }
    }
    
    async function pollProgress() {
        if (!uploadId) return;
        
        const interval = setInterval(async () => {
            try {
                const res = await fetch(
                    `${API_URL}/api/personal/vault/upload/${uploadId}`,
                    { credentials: 'include' }
                );
                const data = await res.json();
                
                progress = data.progress_pct;
                uploadStatus = `Processing: ${progress}% (${data.nodes_created} memories found)`;
                
                if (data.status === 'complete') {
                    clearInterval(interval);
                    uploading = false;
                    uploadStatus = `Done! Added ${data.nodes_created} memories to your vault.`;
                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    uploading = false;
                    error = data.error_message;
                }
            } catch (e) {
                clearInterval(interval);
                error = e.message;
                uploading = false;
            }
        }, 2000);
    }
</script>

<div class="vault-upload">
    <h3>Import Your Chat History</h3>
    <p class="subtitle">Upload your Anthropic or OpenAI export to give me memory of our past conversations.</p>
    
    <div class="upload-zone" class:dragging={false}>
        <input 
            type="file" 
            accept=".json,.zip"
            bind:files
            disabled={uploading}
        />
        
        {#if files && files.length > 0}
            <p class="selected">{files[0].name}</p>
        {:else}
            <p>Drop conversations.json here or click to browse</p>
        {/if}
    </div>
    
    <button 
        on:click={handleUpload}
        disabled={uploading || !files}
        class="upload-btn"
    >
        {uploading ? 'Processing...' : 'Upload & Process'}
    </button>
    
    {#if uploadStatus}
        <div class="status">
            {#if uploading}
                <div class="progress-bar">
                    <div class="fill" style="width: {progress}%"></div>
                </div>
            {/if}
            <p>{uploadStatus}</p>
        </div>
    {/if}
    
    {#if error}
        <div class="error">
            <p>{error}</p>
        </div>
    {/if}
</div>

<style>
    .vault-upload {
        padding: 1.5rem;
        border: 1px solid var(--border-color, #333);
        border-radius: 8px;
        background: var(--bg-secondary, #1a1a1a);
    }
    
    h3 {
        margin: 0 0 0.5rem 0;
        color: var(--text-primary, #fff);
    }
    
    .subtitle {
        color: var(--text-secondary, #888);
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }
    
    .upload-zone {
        border: 2px dashed var(--border-color, #444);
        border-radius: 8px;
        padding: 2rem;
        text-align: center;
        cursor: pointer;
        transition: border-color 0.2s;
    }
    
    .upload-zone:hover {
        border-color: var(--accent, #0f0);
    }
    
    .upload-zone input {
        display: none;
    }
    
    .upload-btn {
        width: 100%;
        margin-top: 1rem;
        padding: 0.75rem;
        background: var(--accent, #0f0);
        color: #000;
        border: none;
        border-radius: 4px;
        font-weight: bold;
        cursor: pointer;
    }
    
    .upload-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
    
    .progress-bar {
        height: 4px;
        background: var(--bg-tertiary, #333);
        border-radius: 2px;
        margin-bottom: 0.5rem;
        overflow: hidden;
    }
    
    .progress-bar .fill {
        height: 100%;
        background: var(--accent, #0f0);
        transition: width 0.3s;
    }
    
    .status {
        margin-top: 1rem;
        padding: 0.75rem;
        background: var(--bg-tertiary, #222);
        border-radius: 4px;
    }
    
    .error {
        margin-top: 1rem;
        padding: 0.75rem;
        background: rgba(255, 0, 0, 0.1);
        border: 1px solid rgba(255, 0, 0, 0.3);
        border-radius: 4px;
        color: #ff6b6b;
    }
</style>
```

**Wire into settings or dashboard page** - wherever makes sense in the UI.

---

## VERIFICATION CHECKPOINTS

### After Phase 1
```sql
-- Verify tables exist
\dt personal.*
-- Should show: users, vaults, vault_uploads, user_tiers

-- Verify config loads
python -c "from config_loader import load_config; print(load_config()['tiers'])"
```

### After Phase 2
```bash
# Test B2 connection
python -c "
from core.vault_service import get_vault_service
from config_loader import load_config
vs = get_vault_service(load_config())
print('B2 connected:', vs.bucket_name)
"

# Test tier service
python -c "
from core.tier_service import TierService, Tier
ts = TierService({'tiers': {'free': {'messages_per_day': 20}}}, None)
print('Free limit:', ts.tier_limits[Tier.FREE].messages_per_day)
"
```

### After Phase 3
```bash
# Start server
uvicorn main:app --reload

# Test upload endpoint (need valid session)
curl -X POST http://localhost:8000/api/personal/vault/upload \
  -H "Cookie: session_id=TEST" \
  -F "file=@test_conversations.json"
```

### After Phase 4
```bash
# Full flow test
1. Sign up new user (Google OAuth)
2. Check B2 for vault creation
3. Upload conversations.json
4. Check vault status endpoint
5. Send chat message, verify tier limit
```

---

## SDK AGENT EXECUTION PLAN

```
SPAWN STRATEGY:

PHASE 1 (Foundation) - 2 parallel agents:
  Agent 1A: Run migration 007_personal_vaults.sql
  Agent 1B: Update config.yaml with tiers + vault sections

CHECKPOINT: Verify both complete

PHASE 2 (Core Services) - 2 parallel agents:
  Agent 2A: Create core/vault_service.py
  Agent 2B: Create core/tier_service.py

CHECKPOINT: Verify imports work

PHASE 3 (Integration) - 2 parallel agents:
  Agent 3A: Create routes/personal_vault.py + wire to main.py
  Agent 3B: Add run_pipeline_for_user to memory/ingest/pipeline.py

CHECKPOINT: Server starts, endpoints respond

PHASE 4 (Wiring) - 3 parallel agents:
  Agent 4A: Modify personal_auth.py signup flows
  Agent 4B: Add tier checks to chat endpoint in main.py
  Agent 4C: Create frontend VaultUpload.svelte

FINAL VERIFICATION: Full signup → upload → chat flow
```

---

## ROLLBACK PLAN

```sql
-- Database rollback
DROP TABLE IF EXISTS personal.vault_uploads;
DROP TABLE IF EXISTS personal.vaults;
DROP TABLE IF EXISTS personal.user_tiers;
```

```bash
# Git rollback
git revert HEAD~N  # N = number of commits
```

---

## FILES CREATED/MODIFIED

| File | Action | Phase |
|------|--------|-------|
| migrations/007_personal_vaults.sql | CREATE | 1A |
| config.yaml | MODIFY | 1B |
| core/vault_service.py | CREATE | 2A |
| core/tier_service.py | CREATE | 2B |
| routes/personal_vault.py | CREATE | 3A |
| memory/ingest/pipeline.py | MODIFY | 3B |
| auth/personal_auth.py | MODIFY | 4A |
| main.py | MODIFY | 4B |
| frontend-cogzy/src/lib/components/VaultUpload.svelte | CREATE | 4C |
