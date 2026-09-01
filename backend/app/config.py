
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from the backend root (next to config.py → ../../)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)


@dataclass
class Settings:
    # ── App ──
    app_name: str = "auto-release-notes"
    version: str = "0.1.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    )

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./data/app.db",
    )

    # Redis (queue / cache)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # GitHub OAuth
    github_client_id: Optional[str] = os.getenv("GITHUB_CLIENT_ID")
    github_client_secret: Optional[str] = os.getenv("GITHUB_CLIENT_SECRET")
    github_app_id: Optional[str] = os.getenv("GITHUB_APP_ID")
    github_app_private_key: Optional[str] = os.getenv("GITHUB_APP_PRIVATE_KEY")
    github_webhook_secret: Optional[str] = os.getenv("GITHUB_WEBHOOK_SECRET")

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24h

    # Encryption (for user API keys at rest)
    encryption_key: str = os.getenv("ENCRYPTION_KEY", "")

    # Storage
    data_dir: str = os.getenv("DATA_DIR", "./data")
    clone_work_dir: str = os.getenv("CLONE_WORK_DIR", "./data/repos")

    # Default LLM
    default_llm_provider: str = "commit"

    # Webhook server
    webhook_port: int = int(os.getenv("WEBHOOK_PORT", "9876"))
    webhook_path: str = os.getenv("WEBHOOK_PATH", "/webhook")
    webhook_base_url: Optional[str] = os.getenv("WEBHOOK_BASE_URL")


settings = Settings()