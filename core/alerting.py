"""
Alert Engine - Threshold monitoring and notifications

Evaluates alert rules against metrics and sends notifications.

Usage:
    from core.alerting import alert_engine

    # Start the alert evaluation loop
    await alert_engine.start()

    # Stop on shutdown
    await alert_engine.stop()
"""

import asyncio
import logging
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    """Alert rule definition."""
    id: str
    name: str
    description: Optional[str]
    metric_type: str
    condition: str
    threshold: float
    window_minutes: int
    custom_sql: Optional[str]
    severity: str
    notification_channels: List[str]
    cooldown_minutes: int
    enabled: bool
    last_triggered_at: Optional[datetime]


@dataclass
class AlertInstance:
    """A fired alert instance."""
    rule_id: str
    rule_name: str
    severity: str
    metric_value: float
    threshold_value: float
    message: str


class AlertEngine:
    """
    Evaluates alert rules and sends notifications.

    Runs as a background task, checking rules every 60 seconds.
    """

    _instance: Optional['AlertEngine'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._db_pool = None
        self._eval_task: Optional[asyncio.Task] = None
        self._running = False

        # Notification config from environment
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        self.smtp_host = os.getenv('SMTP_HOST')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.alert_email_from = os.getenv('ALERT_EMAIL_FROM', 'alerts@cogtwin.local')
        self.alert_email_to = os.getenv('ALERT_EMAIL_TO', '').split(',')

        logger.info("[AlertEngine] Initialized")

    def set_db_pool(self, pool):
        """Set the database connection pool."""
        self._db_pool = pool

    async def start(self):
        """Start the alert evaluation loop."""
        if self._eval_task is not None:
            return

        self._running = True
        self._eval_task = asyncio.create_task(self._evaluation_loop())
        logger.info("[AlertEngine] Started evaluation loop")

    async def stop(self):
        """Stop the alert evaluation loop."""
        self._running = False
        if self._eval_task:
            self._eval_task.cancel()
            try:
                await self._eval_task
            except asyncio.CancelledError:
                pass
            self._eval_task = None
        logger.info("[AlertEngine] Stopped")

    async def _evaluation_loop(self):
        """Main evaluation loop."""
        while self._running:
            try:
                await self._evaluate_all_rules()
            except Exception as e:
                logger.error(f"[AlertEngine] Evaluation error: {e}")

            await asyncio.sleep(60)  # Evaluate every 60 seconds

    async def _evaluate_all_rules(self):
        """Evaluate all enabled alert rules."""
        if not self._db_pool:
            return

        async with self._db_pool.acquire() as conn:
            # Load enabled rules
            rows = await conn.fetch("""
                SELECT id, name, description, metric_type, condition, threshold,
                       window_minutes, custom_sql, severity, notification_channels,
                       cooldown_minutes, enabled, last_triggered_at
                FROM enterprise.alert_rules
                WHERE enabled = TRUE
            """)

            rules = [AlertRule(
                id=str(r['id']),
                name=r['name'],
                description=r['description'],
                metric_type=r['metric_type'],
                condition=r['condition'],
                threshold=r['threshold'],
                window_minutes=r['window_minutes'],
                custom_sql=r['custom_sql'],
                severity=r['severity'],
                notification_channels=r['notification_channels'] if isinstance(r['notification_channels'], list) else [],
                cooldown_minutes=r['cooldown_minutes'],
                enabled=r['enabled'],
                last_triggered_at=r['last_triggered_at'],
            ) for r in rows]

        for rule in rules:
            await self._evaluate_rule(rule)

    async def _evaluate_rule(self, rule: AlertRule):
        """Evaluate a single alert rule."""
        # Check cooldown
        if rule.last_triggered_at:
            cooldown_until = rule.last_triggered_at + timedelta(minutes=rule.cooldown_minutes)
            if datetime.utcnow() < cooldown_until:
                return  # Still in cooldown

        # Get metric value
        metric_value = await self._get_metric_value(rule)
        if metric_value is None:
            return

        # Check condition
        triggered = self._check_condition(metric_value, rule.condition, rule.threshold)

        if triggered:
            await self._fire_alert(rule, metric_value)

    async def _get_metric_value(self, rule: AlertRule) -> Optional[float]:
        """Get the current metric value for a rule."""
        if not self._db_pool:
            return None

        try:
            async with self._db_pool.acquire() as conn:
                if rule.metric_type == 'error_count':
                    result = await conn.fetchval("""
                        SELECT COUNT(*) FROM enterprise.structured_logs
                        WHERE level = 'ERROR'
                          AND timestamp > NOW() - INTERVAL '1 minute' * $1
                    """, rule.window_minutes)

                elif rule.metric_type == 'rag_latency_p95':
                    result = await conn.fetchval("""
                        SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_ms)
                        FROM enterprise.rag_metrics
                        WHERE timestamp > NOW() - INTERVAL '1 minute' * $1
                    """, rule.window_minutes)

                elif rule.metric_type == 'llm_cost_hourly':
                    result = await conn.fetchval("""
                        SELECT COALESCE(SUM(cost_usd), 0)
                        FROM enterprise.llm_call_metrics
                        WHERE timestamp > NOW() - INTERVAL '1 minute' * $1
                    """, rule.window_minutes)

                elif rule.metric_type == 'cache_hit_rate':
                    from core.metrics_collector import metrics_collector
                    total = metrics_collector.cache_hits + metrics_collector.cache_misses
                    result = (metrics_collector.cache_hits / total * 100) if total > 0 else 100

                elif rule.metric_type == 'memory_percent':
                    from core.metrics_collector import metrics_collector
                    system = metrics_collector.get_system_metrics()
                    result = system.get('memory_percent', 0)

                elif rule.metric_type == 'custom_sql' and rule.custom_sql:
                    result = await conn.fetchval(rule.custom_sql)

                else:
                    logger.warning(f"[AlertEngine] Unknown metric type: {rule.metric_type}")
                    return None

                return float(result) if result is not None else None

        except Exception as e:
            logger.error(f"[AlertEngine] Metric fetch error for {rule.name}: {e}")
            return None

    def _check_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Check if the condition is met."""
        if condition == 'gt':
            return value > threshold
        elif condition == 'gte':
            return value >= threshold
        elif condition == 'lt':
            return value < threshold
        elif condition == 'lte':
            return value <= threshold
        elif condition == 'eq':
            return value == threshold
        elif condition == 'neq':
            return value != threshold
        return False

    async def _fire_alert(self, rule: AlertRule, metric_value: float):
        """Fire an alert and send notifications."""
        logger.warning(f"[AlertEngine] ALERT FIRED: {rule.name} (value={metric_value}, threshold={rule.threshold})")

        alert = AlertInstance(
            rule_id=rule.id,
            rule_name=rule.name,
            severity=rule.severity,
            metric_value=metric_value,
            threshold_value=rule.threshold,
            message=f"{rule.name}: {rule.metric_type} is {metric_value} (threshold: {rule.threshold})"
        )

        # Record alert instance
        await self._record_alert_instance(alert)

        # Update last_triggered_at
        await self._update_rule_triggered(rule.id)

        # Send notifications
        notifications_sent = []

        if 'slack' in rule.notification_channels:
            success = await self._send_slack_notification(alert)
            notifications_sent.append({'channel': 'slack', 'success': success})

        if 'email' in rule.notification_channels:
            success = await self._send_email_notification(alert)
            notifications_sent.append({'channel': 'email', 'success': success})

        # Update notification status
        await self._update_alert_notifications(alert.rule_id, notifications_sent)

    async def _record_alert_instance(self, alert: AlertInstance):
        """Record a fired alert in the database."""
        if not self._db_pool:
            return

        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO enterprise.alert_instances
                    (rule_id, metric_value, threshold_value, message, context)
                    VALUES ($1, $2, $3, $4, $5)
                """, alert.rule_id, alert.metric_value, alert.threshold_value,
                     alert.message, '{}')
        except Exception as e:
            logger.error(f"[AlertEngine] Record alert error: {e}")

    async def _update_rule_triggered(self, rule_id: str):
        """Update last_triggered_at for a rule."""
        if not self._db_pool:
            return

        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE enterprise.alert_rules
                    SET last_triggered_at = NOW(), last_evaluated_at = NOW()
                    WHERE id = $1
                """, rule_id)
        except Exception as e:
            logger.error(f"[AlertEngine] Update rule error: {e}")

    async def _update_alert_notifications(self, rule_id: str, notifications: List[Dict]):
        """Update notifications_sent for the most recent alert."""
        if not self._db_pool:
            return

        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE enterprise.alert_instances
                    SET notifications_sent = $2
                    WHERE rule_id = $1
                    ORDER BY triggered_at DESC
                    LIMIT 1
                """, rule_id, str(notifications))
        except Exception as e:
            logger.error(f"[AlertEngine] Update notifications error: {e}")

    async def _send_slack_notification(self, alert: AlertInstance) -> bool:
        """Send alert to Slack webhook."""
        if not self.slack_webhook_url:
            logger.warning("[AlertEngine] Slack webhook URL not configured")
            return False

        try:
            # Severity emoji
            emoji = {
                'info': 'ℹ️',
                'warning': '⚠️',
                'critical': '🚨'
            }.get(alert.severity, '⚠️')

            payload = {
                'text': f"{emoji} *{alert.rule_name}*",
                'attachments': [{
                    'color': {
                        'info': '#36a64f',
                        'warning': '#ffcc00',
                        'critical': '#ff0000'
                    }.get(alert.severity, '#ffcc00'),
                    'fields': [
                        {'title': 'Severity', 'value': alert.severity.upper(), 'short': True},
                        {'title': 'Value', 'value': str(round(alert.metric_value, 2)), 'short': True},
                        {'title': 'Threshold', 'value': str(alert.threshold_value), 'short': True},
                    ],
                    'text': alert.message,
                    'footer': 'CogTwin Alert Engine',
                    'ts': int(datetime.utcnow().timestamp())
                }]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.slack_webhook_url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info(f"[AlertEngine] Slack notification sent for {alert.rule_name}")
                        return True
                    else:
                        logger.error(f"[AlertEngine] Slack webhook failed: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"[AlertEngine] Slack notification error: {e}")
            return False

    async def _send_email_notification(self, alert: AlertInstance) -> bool:
        """Send alert via email."""
        if not self.smtp_host or not self.alert_email_to:
            logger.warning("[AlertEngine] Email not configured")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert.severity.upper()}] {alert.rule_name}"
            msg['From'] = self.alert_email_from
            msg['To'] = ', '.join(self.alert_email_to)

            # Plain text version
            text = f"""
Alert: {alert.rule_name}
Severity: {alert.severity.upper()}
Value: {alert.metric_value}
Threshold: {alert.threshold_value}

{alert.message}

---
CogTwin Alert Engine
"""

            # HTML version
            html = f"""
<html>
<body>
<h2 style="color: {'red' if alert.severity == 'critical' else 'orange'}">
    {alert.rule_name}
</h2>
<table>
    <tr><td><strong>Severity:</strong></td><td>{alert.severity.upper()}</td></tr>
    <tr><td><strong>Value:</strong></td><td>{alert.metric_value}</td></tr>
    <tr><td><strong>Threshold:</strong></td><td>{alert.threshold_value}</td></tr>
</table>
<p>{alert.message}</p>
<hr>
<small>CogTwin Alert Engine</small>
</body>
</html>
"""

            msg.attach(MIMEText(text, 'plain'))
            msg.attach(MIMEText(html, 'html'))

            # Send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"[AlertEngine] Email notification sent for {alert.rule_name}")
            return True

        except Exception as e:
            logger.error(f"[AlertEngine] Email notification error: {e}")
            return False


# Global instance
alert_engine = AlertEngine()
