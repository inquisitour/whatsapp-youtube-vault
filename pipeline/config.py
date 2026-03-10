"""Application settings loaded from environment / .env file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (one level up from pipeline/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Settings:
    """Central configuration read from environment variables."""

    def __init__(self) -> None:
        self.anthropic_api_key: str = self._require("ANTHROPIC_API_KEY")
        self.claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

        self.vault_dir: Path = Path(os.getenv("VAULT_DIR", str(_PROJECT_ROOT / "vault")))
        self.data_dir: Path = Path(os.getenv("DATA_DIR", str(_PROJECT_ROOT / "data")))
        self.links_file: Path = Path(
            os.getenv("LINKS_FILE", str(self.data_dir / "links.jsonl"))
        )
        self.db_path: Path = Path(
            os.getenv("DB_PATH", str(self.vault_dir / "vault.db"))
        )
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @staticmethod
    def _require(key: str) -> str:
        """Return the value of an env var or raise."""
        value = os.getenv(key)
        if not value:
            raise EnvironmentError(f"Required environment variable {key} is not set")
        return value


def get_settings() -> Settings:
    """Return a ``Settings`` instance (created fresh each call)."""
    return Settings()
