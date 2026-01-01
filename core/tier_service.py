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
