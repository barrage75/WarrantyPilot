from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="dev", validation_alias="WP_ENV")
    database_url: str = "sqlite:///runtime/warrantypilot.db"
    journal_anchor_key: SecretStr = SecretStr("local-dev-only-change-me")
    anchor_file: Path = Path("runtime/anchors/anchors.jsonl")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    demo_mode: bool = True
    demo_today: date = date(2026, 11, 20)


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
