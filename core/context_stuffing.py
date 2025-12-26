"""
Context Stuffing - Direct Manual Injection for Grok 2M Context

Replaces RAG retrieval with full document context stuffing.
Simpler, faster, no chunking or embedding required.

Access Control:
- Purchasing users (or super_users) see ALL manuals
- Everyone else sees sales + warehouse only (no purchasing/costs)

Usage:
    from core.context_stuffing import get_context_stuffer, is_context_stuffing_enabled

    stuffer = get_context_stuffer(config)
    docs = stuffer.get_docs_for_user(user_email)

Version: 1.0.0
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Set

logger = logging.getLogger(__name__)


class ContextStuffer:
    """
    Manages document loading and user-based access control.

    Caches documents in memory for fast retrieval.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.stuffing_config = config.get("features", {}).get("context_stuffing", {})

        # Paths - use docs.stuffing config if available, else defaults
        docs_config = config.get("docs", {}).get("stuffing", {})
        base_path = config.get("docs", {}).get("docs_dir", "./docs/driscoll")

        self.doc_path = Path(self.stuffing_config.get("doc_path", base_path))
        self.full_access_file = self.stuffing_config.get("full_access_file", "all_manuals.txt")
        self.restricted_file = self.stuffing_config.get("restricted_file", "sales_warehouse.txt")

        # Access control - departments that see EVERYTHING (including purchasing)
        self.full_access_depts: Set[str] = set(
            self.stuffing_config.get("full_access_departments", ["purchasing"])
        )

        # Document cache
        self._full_docs: Optional[str] = None
        self._restricted_docs: Optional[str] = None

        # Pre-load if configured
        if self.stuffing_config.get("cache_on_startup", True):
            self._load_docs()

        logger.info(
            f"[ContextStuffer] Initialized: path={self.doc_path}, "
            f"full_access_depts={self.full_access_depts}"
        )

    def _load_docs(self) -> None:
        """Load document files into memory."""
        full_path = self.doc_path / self.full_access_file
        restricted_path = self.doc_path / self.restricted_file

        # Load full docs (includes purchasing)
        if full_path.exists():
            self._full_docs = full_path.read_text(encoding='utf-8')
            tokens_est = len(self._full_docs) // 4
            logger.info(f"[ContextStuffer] Loaded {full_path}: {len(self._full_docs):,} chars (~{tokens_est:,} tokens)")
        else:
            logger.warning(f"[ContextStuffer] Full docs not found: {full_path}")
            self._full_docs = ""

        # Load restricted docs (sales + warehouse only)
        if restricted_path.exists():
            self._restricted_docs = restricted_path.read_text(encoding='utf-8')
            tokens_est = len(self._restricted_docs) // 4
            logger.info(f"[ContextStuffer] Loaded {restricted_path}: {len(self._restricted_docs):,} chars (~{tokens_est:,} tokens)")
        else:
            logger.warning(f"[ContextStuffer] Restricted docs not found: {restricted_path}")
            self._restricted_docs = ""

    def _user_has_full_access(self, user_email: str, department: str = None) -> bool:
        """
        Check if user should see all documents (including purchasing).

        Returns True if:
        - User is super_user (checked via auth service if available)
        - User's department is in full_access_departments
        - department param explicitly in full_access_departments
        """
        if not user_email:
            return False

        # Check department param directly (fast path)
        if department and department.lower() in {d.lower() for d in self.full_access_depts}:
            logger.debug(f"[ContextStuffer] {user_email} dept={department} -> full access")
            return True

        # Try auth service for super_user and department_access check
        try:
            from auth.auth_service import get_auth_service
            auth = get_auth_service()
            user = auth.get_user_by_email(user_email)

            if not user:
                logger.debug(f"[ContextStuffer] User not found: {user_email}")
                return False

            # Super users see everything
            if getattr(user, 'is_super_user', False):
                logger.debug(f"[ContextStuffer] {user_email} is super_user -> full access")
                return True

            # Check department_access list
            user_depts = set(getattr(user, 'department_access', []) or [])
            user_depts_lower = {d.lower() for d in user_depts}
            full_access_lower = {d.lower() for d in self.full_access_depts}

            if user_depts_lower.intersection(full_access_lower):
                logger.debug(f"[ContextStuffer] {user_email} has {user_depts & self.full_access_depts} -> full access")
                return True

            return False

        except ImportError:
            # No auth service - fall back to department param only
            logger.debug("[ContextStuffer] No auth_service available, using department param only")
            return False
        except Exception as e:
            logger.error(f"[ContextStuffer] Error checking user access: {e}")
            return False

    def get_docs_for_user(self, user_email: str, department: str = None) -> str:
        """
        Get appropriate document set for user.

        Returns full docs for purchasing/super_user, restricted for others.
        """
        # Lazy load if not cached
        if self._full_docs is None:
            self._load_docs()

        if self._user_has_full_access(user_email, department):
            logger.info(f"[ContextStuffer] {user_email} -> full docs ({len(self._full_docs):,} chars)")
            return self._full_docs or ""
        else:
            logger.info(f"[ContextStuffer] {user_email} -> restricted docs ({len(self._restricted_docs):,} chars)")
            return self._restricted_docs or ""

    def get_docs_for_department(self, department: str) -> str:
        """
        Get docs based on department only (no user lookup).

        Faster path when we just have department info.
        """
        if self._full_docs is None:
            self._load_docs()

        if department and department.lower() in {d.lower() for d in self.full_access_depts}:
            return self._full_docs or ""
        return self._restricted_docs or ""

    def reload_docs(self) -> None:
        """Force reload of document files (call after manual updates)."""
        self._full_docs = None
        self._restricted_docs = None
        self._load_docs()
        logger.info("[ContextStuffer] Documents reloaded")

    @property
    def is_enabled(self) -> bool:
        """Check if context stuffing is enabled in config."""
        return self.stuffing_config.get("enabled", False)

    @property
    def full_docs_size(self) -> int:
        """Return size of full docs in chars."""
        return len(self._full_docs or "")

    @property
    def restricted_docs_size(self) -> int:
        """Return size of restricted docs in chars."""
        return len(self._restricted_docs or "")


# =============================================================================
# SINGLETON & CONVENIENCE FUNCTIONS
# =============================================================================

_stuffer: Optional[ContextStuffer] = None


def get_context_stuffer(config: Dict[str, Any] = None) -> ContextStuffer:
    """Get or create the context stuffer singleton."""
    global _stuffer
    if _stuffer is None:
        if config is None:
            raise RuntimeError("ContextStuffer not initialized - pass config on first call")
        _stuffer = ContextStuffer(config)
    return _stuffer


def reset_context_stuffer() -> None:
    """Reset the singleton (for testing)."""
    global _stuffer
    _stuffer = None


def get_context_for_user(user_email: str, department: str = None, config: Dict[str, Any] = None) -> str:
    """
    Convenience function to get docs for a user.

    Usage:
        docs = get_context_for_user("alice@driscollfoods.com", "sales", config)
    """
    stuffer = get_context_stuffer(config)
    return stuffer.get_docs_for_user(user_email, department)


def is_context_stuffing_enabled(config: Dict[str, Any]) -> bool:
    """Check if context stuffing is enabled."""
    return config.get("features", {}).get("context_stuffing", {}).get("enabled", False)


def is_rag_enabled(config: Dict[str, Any]) -> bool:
    """Check if RAG is enabled."""
    return config.get("features", {}).get("enterprise_rag", {}).get("enabled", True)


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import yaml

    print("Context Stuffing Module Test")
    print("=" * 50)

    # Load config
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text())
    else:
        # Test config
        config = {
            "docs": {
                "docs_dir": "./docs/driscoll"
            },
            "features": {
                "context_stuffing": {
                    "enabled": True,
                    "doc_path": "./docs/driscoll",
                    "full_access_file": "all_manuals.txt",
                    "restricted_file": "sales_warehouse.txt",
                    "full_access_departments": ["purchasing"],
                    "cache_on_startup": True,
                }
            }
        }

    print(f"\n[CONFIG] context_stuffing.enabled = {is_context_stuffing_enabled(config)}")
    print(f"[CONFIG] enterprise_rag.enabled = {is_rag_enabled(config)}")

    # Test stuffer initialization
    try:
        reset_context_stuffer()
        stuffer = ContextStuffer(config)
        print(f"\n[OK] ContextStuffer initialized")
        print(f"  Full docs: {stuffer.full_docs_size:,} chars (~{stuffer.full_docs_size//4:,} tokens)")
        print(f"  Restricted docs: {stuffer.restricted_docs_size:,} chars (~{stuffer.restricted_docs_size//4:,} tokens)")

        # Test access control
        print(f"\n[TEST] Access control:")
        print(f"  purchasing dept -> full: {stuffer._user_has_full_access('test@driscollfoods.com', 'purchasing')}")
        print(f"  sales dept -> full: {stuffer._user_has_full_access('test@driscollfoods.com', 'sales')}")
        print(f"  warehouse dept -> full: {stuffer._user_has_full_access('test@driscollfoods.com', 'warehouse')}")

    except Exception as e:
        print(f"\n[ERROR] ContextStuffer init failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 50)
    print("Module loaded successfully")
