from __future__ import annotations

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    BOT_TOKEN: str
    DATABASE_URL: str

    # DeepSeek (LLM) API
    DEEPSEEK_API_KEY: str

    # Others
    DEFAULT_TIMEZONE: str = "UTC"
    DAILY_PRINCIPLE_REMINDER_HOUR: int = 7
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",  # Явный путь
        env_file_encoding="utf-8", 
        case_sensitive=True  # Лучше использовать True для consistency
    )


# Отладочная информация после создания settings
settings = Settings()