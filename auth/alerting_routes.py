"""
Alerting API Routes - Alert management and viewing

Provides endpoints for alert rules CRUD and instance viewing.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

alerting_router = APIRouter()


class AlertRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    metric_type: str
    condition: str
    threshold: float
    window_minutes: int = 5
    custom_sql: Optional[str] = None
    severity: str = 'warning'
    notification_channels: List[str] = ['slack']
    cooldown_minutes: int = 15
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    threshold: Optional[float] = None
    window_minutes: Optional[int] = None
    severity: Optional[str] = None
    notification_channels: Optional[List[str]] = None
    cooldown_minutes: Optional[int] = None
    enabled: Optional[bool] = None


@alerting_router.get("/rules")
async def list_alert_rules():
    """List all alert rules."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, name, description, metric_type, condition, threshold,
                       window_minutes, severity, notification_channels, cooldown_minutes,
                       enabled, last_evaluated_at, last_triggered_at, created_at
                FROM enterprise.alert_rules
                ORDER BY created_at DESC
            """)

        return {'rules': [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"[Alerting] List rules error: {e}")
        return {'rules': [], 'error': str(e)}


@alerting_router.post("/rules")
async def create_alert_rule(rule: AlertRuleCreate):
    """Create a new alert rule."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO enterprise.alert_rules
                (name, description, metric_type, condition, threshold, window_minutes,
                 custom_sql, severity, notification_channels, cooldown_minutes, enabled)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id
            """, rule.name, rule.description, rule.metric_type, rule.condition,
                 rule.threshold, rule.window_minutes, rule.custom_sql, rule.severity,
                 rule.notification_channels, rule.cooldown_minutes, rule.enabled)

        return {'id': str(row['id']), 'message': 'Rule created'}
    except Exception as e:
        logger.error(f"[Alerting] Create rule error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alerting_router.put("/rules/{rule_id}")
async def update_alert_rule(rule_id: str, update: AlertRuleUpdate):
    """Update an alert rule."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()

        # Build dynamic update query
        updates = []
        params = []
        param_idx = 1

        for field, value in update.dict(exclude_unset=True).items():
            if value is not None:
                updates.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not updates:
            return {'message': 'No updates provided'}

        params.append(rule_id)
        query = f"""
            UPDATE enterprise.alert_rules
            SET {', '.join(updates)}, updated_at = NOW()
            WHERE id = ${param_idx}
        """

        async with pool.acquire() as conn:
            await conn.execute(query, *params)

        return {'message': 'Rule updated'}
    except Exception as e:
        logger.error(f"[Alerting] Update rule error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alerting_router.delete("/rules/{rule_id}")
async def delete_alert_rule(rule_id: str):
    """Delete an alert rule."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM enterprise.alert_rules WHERE id = $1
            """, rule_id)

        return {'message': 'Rule deleted'}
    except Exception as e:
        logger.error(f"[Alerting] Delete rule error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alerting_router.get("/instances")
async def list_alert_instances(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    rule_id: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
):
    """List fired alert instances."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()

        query = """
            SELECT ai.id, ai.rule_id, ar.name as rule_name, ar.severity,
                   ai.triggered_at, ai.resolved_at, ai.status,
                   ai.acknowledged_by, ai.acknowledged_at,
                   ai.metric_value, ai.threshold_value, ai.message
            FROM enterprise.alert_instances ai
            JOIN enterprise.alert_rules ar ON ai.rule_id = ar.id
            WHERE ai.triggered_at > NOW() - INTERVAL '1 hour' * $1
        """
        params = [hours]
        param_idx = 2

        if status:
            query += f" AND ai.status = ${param_idx}"
            params.append(status)
            param_idx += 1

        if rule_id:
            query += f" AND ai.rule_id = ${param_idx}"
            params.append(rule_id)
            param_idx += 1

        query += f" ORDER BY ai.triggered_at DESC LIMIT ${param_idx}"
        params.append(limit)

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return {'instances': [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"[Alerting] List instances error: {e}")
        return {'instances': [], 'error': str(e)}


@alerting_router.post("/instances/{instance_id}/acknowledge")
async def acknowledge_alert(instance_id: str, user_email: str = Query(...)):
    """Acknowledge an alert instance."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE enterprise.alert_instances
                SET status = 'acknowledged',
                    acknowledged_by = $2,
                    acknowledged_at = NOW()
                WHERE id = $1
            """, instance_id, user_email)

        return {'message': 'Alert acknowledged'}
    except Exception as e:
        logger.error(f"[Alerting] Acknowledge error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alerting_router.post("/instances/{instance_id}/resolve")
async def resolve_alert(instance_id: str):
    """Mark an alert as resolved."""
    try:
        from core.database import get_db_pool
        pool = await get_db_pool()

        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE enterprise.alert_instances
                SET status = 'resolved', resolved_at = NOW()
                WHERE id = $1
            """, instance_id)

        return {'message': 'Alert resolved'}
    except Exception as e:
        logger.error(f"[Alerting] Resolve error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
