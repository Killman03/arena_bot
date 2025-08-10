from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")

    # Notion
    notion_api_key: str = Field(alias="NOTION_API_KEY")
    notion_database_goals: str = Field(alias="NOTION_DB_GOALS")
    notion_database_tasks: str = Field(alias="NOTION_DB_TASKS")

    # DeepSeek (LLM) API
    deepseek_api_key: str = Field(alias="DEEPSEEK_API_KEY")

    # Others
    default_timezone: str = Field(default="UTC", alias="DEFAULT_TIMEZONE")
    daily_principle_reminder_hour: int = Field(default=7, alias="DAILY_PRINCIPLE_REMINDER_HOUR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


settings = Settings()  # type: ignore[arg-type]


