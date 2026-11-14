"""The ``BrowserDriver`` interface shared by the scripted and AI engines."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.parse import quote
from uuid import UUID

from app.actions.browser.allowlist import UrlAllowlist
from app.actions.browser.claim import PortalClaim
from app.actions.browser.settings import BrowserSettings

logger = logging.getLogger(__name__)

HOME_PATH = "/support/home/fr-fr"
SERVICE_PATH = "/support/incidents-online/fr-fr/servicerequest"
SIGNIN_PATH = "/myaccount/fr-fr/signin"
CONFIRMATION_MARKER = SERVICE_PATH + "/confirmation/"

StepCallback = Callable[[str, str | None], Awaitable[None] | None]


class StepReporter:
    """Forwards progress to ``on_step(text, screenshot_path)`` without ever failing the action."""

    def __init__(self, on_step: StepCallback | None, engine: str) -> None:
        self._on_step = on_step
        self.engine = engine

    async def step(self, text: str, screenshot_path: Path | str | None = None) -> None:
        path = str(screenshot_path) if screenshot_path is not None else None
        logger.info("browser_portal[%s] %s", self.engine, text)
        if self._on_step is None:
            return
        try:
            outcome = self._on_step(f"[{self.engine}] {text}", path)
            if inspect.isawaitable(outcome):
                await outcome
        except Exception:
            logger.exception("browser_portal on_step callback failed")


@dataclass(frozen=True)
class PortalJob:
    action_id: UUID
    claim: PortalClaim
    portal_url: str
    request_token: str
    email: str
    password: str
    screenshot_dir: Path
    allowlist: UrlAllowlist
    settings: BrowserSettings
    reporter: StepReporter

    @property
    def form_url(self) -> str:
        url = f"{self.portal_url}{SERVICE_PATH}?servicetag={quote(self.claim.service_tag)}"
        if self.claim.repro_fail_mode:
            url += f"&__fail={self.claim.repro_fail_mode}"
        return url

    @property
    def navigation_timeout_ms(self) -> float:
        return self.settings.navigation_timeout_seconds * 1000


@dataclass(frozen=True)
class PortalSubmission:
    case_number: str
    url: str
    screenshot_path: Path


@runtime_checkable
class BrowserDriver(Protocol):
    name: str

    async def submit(self, job: PortalJob) -> PortalSubmission:
        """Open the portal, file the repair request and return the portal case number."""
        ...
