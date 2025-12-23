"""
Security Logger - Standardized security event logging

Ensures consistent log format for security watcher alert rules.
All security events use specific prefixes that alert rules match against.

Usage:
    from core.security_logger import security_log
    
    security_log.auth_failure(email, reason, session_id)
    security_log.honeypot_access(email, division, session_id)
    security_log.rate_limited(session_id, email)
    security_log.division_denied(email, division, session_id)
    security_log.prompt_injection(email, pattern, session_id)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SecurityLogger:
    """
    Standardized security event logger.
    
    Log messages use specific patterns matched by alert rules in
    enterprise.alert_rules (see migration 011_security_alert_rules.sql).
    """
    
    def auth_failure(
        self, 
        email: str, 
        reason: str, 
        session_id: Optional[str] = None,
        ip: Optional[str] = None
    ):
        """Log authentication failure - matched by 'Auth Failure Cluster' rule."""
        logger.warning(
            f"[SECURITY] Auth failure: email={email}, reason={reason}",
            extra={
                'user_email': email,
                'session_id': session_id,
                'security_event': 'auth_failure',
                'ip': ip
            }
        )
    
    def honeypot_access(
        self,
        email: str,
        division: str,
        session_id: Optional[str] = None
    ):
        """Log honeypot access attempt - matched by 'Honeypot Access Attempt' rule."""
        logger.critical(
            f"[HONEYPOT] User {email} attempted access to {division}",
            extra={
                'user_email': email,
                'session_id': session_id,
                'security_event': 'honeypot_access',
                'target_division': division
            }
        )
    
    def rate_limited(
        self,
        session_id: str,
        email: Optional[str] = None
    ):
        """Log rate limit hit - matched by 'Rate Limit Storm' rule."""
        logger.warning(
            f"[SECURITY] Rate limit exceeded: session={session_id}, email={email}",
            extra={
                'user_email': email,
                'session_id': session_id,
                'security_event': 'rate_limited'
            }
        )
    
    def division_denied(
        self,
        email: str,
        division: str,
        session_id: Optional[str] = None
    ):
        """Log division access denied - matched by 'Division Escalation Attempts' rule."""
        logger.warning(
            f"[SECURITY] Division access denied: {email} attempted {division}",
            extra={
                'user_email': email,
                'session_id': session_id,
                'security_event': 'division_denied',
                'target_division': division
            }
        )
    
    def division_blocked(
        self,
        email: str,
        division: str,
        session_id: Optional[str] = None
    ):
        """Log division change blocked - matched by 'Division Escalation Attempts' rule."""
        logger.warning(
            f"[SECURITY] Division change blocked: {email} attempted {division}",
            extra={
                'user_email': email,
                'session_id': session_id,
                'security_event': 'division_blocked',
                'target_division': division
            }
        )
    
    def prompt_injection(
        self,
        email: str,
        pattern: str,
        content_preview: str,
        session_id: Optional[str] = None
    ):
        """Log prompt injection attempt - matched by 'Prompt Injection Attempt' rule."""
        logger.warning(
            f"[SECURITY] Prompt injection detected: pattern={pattern}, user={email}",
            extra={
                'user_email': email,
                'session_id': session_id,
                'security_event': 'prompt_injection',
                'pattern': pattern,
                'content_preview': content_preview[:100]  # First 100 chars only
            }
        )
    
    def session_created(
        self,
        session_id: str,
        email: Optional[str] = None
    ):
        """Log session creation - used by 'Session Flood' rule aggregation."""
        logger.info(
            f"[SESSION] New session: {session_id}, email={email}",
            extra={
                'user_email': email,
                'session_id': session_id,
                'security_event': 'session_created'
            }
        )
    
    def suspicious_activity(
        self,
        email: str,
        activity: str,
        details: str,
        session_id: Optional[str] = None
    ):
        """Log generic suspicious activity."""
        logger.warning(
            f"[SECURITY] Suspicious activity: {activity} by {email} - {details}",
            extra={
                'user_email': email,
                'session_id': session_id,
                'security_event': 'suspicious',
                'activity': activity
            }
        )


# Singleton instance
security_log = SecurityLogger()


# =====================================================
# PROMPT INJECTION DETECTOR
# =====================================================

# Common prompt injection patterns
INJECTION_PATTERNS = [
    ('ignore_instructions', r'ignore (all )?(previous |prior |above )?instructions'),
    ('system_prompt', r'(show|print|output|reveal|display) (your |the )?(system )?prompt'),
    ('dan_jailbreak', r'you are (now )?DAN'),
    ('developer_mode', r'(developer|dev|debug) mode'),
    ('roleplay_override', r'pretend (you are|to be) '),
    ('base64_injection', r'decode (this )?base64'),
    ('instruction_override', r'new instructions:'),
]

import re

def check_prompt_injection(content: str) -> Optional[str]:
    """
    Check content for common prompt injection patterns.
    
    Returns pattern name if detected, None otherwise.
    """
    content_lower = content.lower()
    
    for pattern_name, pattern_regex in INJECTION_PATTERNS:
        if re.search(pattern_regex, content_lower):
            return pattern_name
    
    return None


def detect_and_log_injection(
    content: str,
    email: str,
    session_id: Optional[str] = None
) -> bool:
    """
    Check for prompt injection and log if detected.
    
    Returns True if injection detected.
    """
    pattern = check_prompt_injection(content)
    if pattern:
        security_log.prompt_injection(
            email=email,
            pattern=pattern,
            content_preview=content,
            session_id=session_id
        )
        return True
    return False
