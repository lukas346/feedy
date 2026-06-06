"""Application configuration from environment variables."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Default fetch interval for new websites (24 hours)
DEFAULT_FETCH_INTERVAL_MINUTES: int = 1440

# Pagination constants (universal for all "load more" sections)
DEFAULT_PAGE_SIZE: int = 10
DEFAULT_LOAD_MORE_SIZE: int = 10


def get_git_commit() -> str:
    """Get the short git commit hash from file or git command."""
    # Try reading from file (Docker build)
    commit_file = Path(__file__).parent.parent / "GIT_COMMIT"
    if commit_file.exists():
        content = commit_file.read_text().strip()
        if content and content != "unknown":
            return content

    # Fallback to git command (local development)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return "unknown"


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    database_url: str
    worker_interval_minutes: int
    base_url: str | None

    def __init__(self) -> None:
        """Load settings from environment variables with defaults."""
        data_dir = Path(__file__).parent.parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        default_db_url = f"sqlite:///{data_dir / 'reader.db'}"

        self.database_url = os.environ.get("DATABASE_URL", default_db_url)
        self.worker_interval_minutes = int(
            os.environ.get("WORKER_INTERVAL_MINUTES", "15")
        )
        # Base URL for external links (bookmarklet, etc.). If not set, uses request URL.
        base_url = os.environ.get("BASE_URL", "").strip().rstrip("/")
        self.base_url = base_url if base_url else None


settings = Settings()
