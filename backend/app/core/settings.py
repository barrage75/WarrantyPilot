from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_DEMO_PASSWORD = "appelia-demo"
DEFAULT_ANCHOR_KEYS = frozenset(
    {"local-dev-only-change-me", "not-a-real-key-change-before-use", ""}
)


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
    smtp_port: int = Field(default=2525, ge=1, le=65535)
    maildir_path: Path = Path("runtime/mail")
    email_sent_ledger_path: Path = Path("runtime/email_sent.jsonl")
    email_sender: str = "warrantypilot@appelia.example"
    email_ai_disclosure: bool = True
    followup_interval_s: float = Field(default=0, ge=0)
    followup_outbox_path: Path = Path("runtime/followup.sqlite3")
    gmail_client_id: SecretStr | None = None
    gmail_client_secret: SecretStr | None = None
    gmail_refresh_token: SecretStr | None = None
    gmail_label_id: str | None = None
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    trusted_hosts: list[str] = Field(
        default_factory=lambda: ["127.0.0.1", "localhost", "testserver"]
    )
    demo_mode: bool = True
    demo_today: date = date(2026, 11, 20)
    demo_password: SecretStr | None = None
    demo_any_password: bool = True
    session_ttl_hours: int = Field(default=8, ge=1, le=24)
    max_auto_threshold_eur: Decimal = Field(default=Decimal("1000"), ge=0)
    journal_archive_dir: Path = Path("runtime/journal-archive")
    auto_anchor_every: int = Field(default=20, ge=1)

    def active_demo_password(self) -> str:
        if self.demo_password is not None and self.demo_password.get_secret_value():
            return self.demo_password.get_secret_value()
        if self.environment == "dev":
            return DEV_DEMO_PASSWORD
        raise InsecureConfigurationError("WP_DEMO_PASSWORD is required outside env=dev")


class InsecureConfigurationError(RuntimeError):
    pass


def assert_secure_configuration(settings: AppSettings) -> None:
    if settings.environment == "dev":
        return
    if settings.journal_anchor_key.get_secret_value() in DEFAULT_ANCHOR_KEYS:
        raise InsecureConfigurationError(
            "WP_JOURNAL_ANCHOR_KEY uses a public default value outside env=dev"
        )
    settings.active_demo_password()


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
