"""Settings of the browser portal adapter (local to lot L4b)."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PORTAL_URL = "http://127.0.0.1:8100"
DEMO_EMAIL = "demo.appelia@reproduction.local"
DEMO_PASSWORD = "demo-only"  # Public demo password of repro/dell, not a secret.


class BrowserEngine(StrEnum):
    SCRIPTED = "scripted"
    HCOMPANY = "hcompany"
    BROWSER_USE = "browser_use"


class BrowserSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WP_BROWSER_", extra="ignore", populate_by_name=True
    )

    browser_engine: BrowserEngine = Field(
        default=BrowserEngine.SCRIPTED,
        validation_alias=AliasChoices("browser_engine", "WP_BROWSER_ENGINE", "BROWSER_ENGINE"),
    )
    fallback_to_scripted: bool = True
    portal_url: str = DEFAULT_PORTAL_URL
    headless: bool = True
    navigation_timeout_seconds: float = Field(default=15.0, gt=0)
    action_timeout_seconds: float = Field(default=180.0, gt=0)
    runtime_dir: Path = Path("runtime/browser")
    demo_email: str = DEMO_EMAIL
    demo_password: SecretStr = SecretStr(DEMO_PASSWORD)
    test_mode: bool = False
    test_origins: list[str] = Field(default_factory=list)
    agent_max_steps: int = Field(default=40, gt=0)

    hcompany_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "hcompany_api_key", "WP_BROWSER_HCOMPANY_API_KEY", "HCOMPANY_API_KEY"
        ),
    )
    hcompany_base_url: str = "https://api.hcompany.ai/v1"
    hcompany_model: str = "holo4-27b"

    browser_use_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "browser_use_api_key", "WP_BROWSER_BROWSER_USE_API_KEY", "BROWSER_USE_API_KEY"
        ),
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "openai_api_key", "WP_BROWSER_OPENAI_API_KEY", "OPENAI_API_KEY"
        ),
    )
    browser_use_model: str = "bu-fast"
    browser_use_openai_base_url: str | None = None

    @classmethod
    def from_env(cls) -> Self:
        return cls()

    @property
    def screenshot_dir(self) -> Path:
        return self.runtime_dir / "screenshots"

    @property
    def store_path(self) -> Path:
        return self.runtime_dir / "idempotency.sqlite3"
