"""Configuration management for Claude SDK Toolkit."""

import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass
class ClaudeConfig:
    """Configuration for Claude SDK."""

    api_key: str
    model: str = "claude-sonnet-4-5"
    max_tokens: int = 8192
    temperature: float = 1.0

    @classmethod
    def from_env(cls) -> "ClaudeConfig":
        """Load configuration from environment variables."""
        load_dotenv()
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        return cls(
            api_key=api_key,
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
            max_tokens=int(os.getenv("CLAUDE_MAX_TOKENS", "8192")),
            temperature=float(os.getenv("CLAUDE_TEMPERATURE", "1.0")),
        )


@dataclass
class DatabaseConfig:
    """Configuration for database tools."""

    host: str
    database: str
    user: str
    password: str
    port: int = 5432
    sslmode: str = "require"

    @classmethod
    def from_env(cls) -> Optional["DatabaseConfig"]:
        """Load database configuration from environment variables."""
        load_dotenv()

        host = os.getenv("AZURE_PG_HOST") or os.getenv("DB_HOST")
        database = os.getenv("AZURE_PG_DATABASE") or os.getenv("DB_NAME")
        user = os.getenv("AZURE_PG_USER") or os.getenv("DB_USER")
        password = os.getenv("AZURE_PG_PASSWORD") or os.getenv("DB_PASSWORD")

        if not all([host, database, user, password]):
            return None

        return cls(
            host=host,
            database=database,
            user=user,
            password=password,
            port=int(os.getenv("DB_PORT", "5432")),
            sslmode=os.getenv("DB_SSLMODE", "require"),
        )

    @property
    def connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        return (
            f"host={self.host} "
            f"dbname={self.database} "
            f"user={self.user} "
            f"password={self.password} "
            f"port={self.port} "
            f"sslmode={self.sslmode}"
        )


@dataclass
class ToolkitConfig:
    """Main configuration for the toolkit."""

    claude: ClaudeConfig
    database: Optional[DatabaseConfig] = None
    skills_dir: Path = field(default_factory=lambda: Path.cwd() / "skills_data" / "skills")
    working_dir: Path = field(default_factory=Path.cwd)
    max_context_size: int = 50000

    # CLI settings
    input_timeout: Optional[float] = None
    history_file: Optional[Path] = None

    # Tool settings
    enabled_tools: list[str] = field(default_factory=lambda: [
        "Read", "Write", "Edit", "Bash",
        "Glob", "Grep", "Task"
    ])

    @classmethod
    def from_env(cls) -> "ToolkitConfig":
        """Load full configuration from environment."""
        load_dotenv()

        claude_config = ClaudeConfig.from_env()
        database_config = DatabaseConfig.from_env()

        skills_dir = Path(os.getenv("SKILLS_DIR", "skills_data/skills"))
        if not skills_dir.is_absolute():
            skills_dir = Path.cwd() / skills_dir

        working_dir = Path(os.getenv("WORKING_DIR", Path.cwd()))

        history_file = os.getenv("HISTORY_FILE")
        if history_file:
            history_file = Path(history_file)

        return cls(
            claude=claude_config,
            database=database_config,
            skills_dir=skills_dir,
            working_dir=working_dir,
            max_context_size=int(os.getenv("MAX_CONTEXT_SIZE", "50000")),
            input_timeout=_parse_timeout(os.getenv("INPUT_TIMEOUT")),
            history_file=history_file,
        )


def _parse_timeout(value: Optional[str]) -> Optional[float]:
    """Parse timeout value from environment variable."""
    if not value or value.lower() in ("off", "none", ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None
