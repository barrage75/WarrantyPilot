"""Shared fixtures-as-functions for the browser portal adapter tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.actions.browser import (
    BrowserPortalAdapter,
    BrowserSettings,
    PortalError,
    PortalErrorCode,
    PortalJob,
    PortalSubmission,
)
from app.actions.browser.drivers.base import CONFIRMATION_MARKER
from app.actions.browser.settings import BrowserEngine
from app.contracts.enums import Channel, RealityBadge
from app.contracts.models import Action

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def claim_payload(**overrides: Any) -> dict[str, Any]:
    claim: dict[str, Any] = {
        "service_tag": "7XK4L93",
        "problem_category": "Écran",
        "problem_description": "L'écran reste noir après l'ouverture du couvercle (fictif).",
        "contact_first_name": "Camille",
        "contact_last_name": "Martin",
        "contact_email": "camille.martin@appelia.example",
        "contact_phone": "0102030405",
        "company_name": "Appelia (fictif)",
        "address_line1": "12 rue de la Démo",
        "postal_code": "75011",
        "city": "Paris",
        "availability_date": "2026-11-20",
        "availability_slot": "Matin 8h–12h",
    }
    claim.update(overrides)
    return claim


def make_action(
    *,
    url: str = "http://127.0.0.1:8100",
    case_id: UUID | None = None,
    key: str | None = None,
    claim: dict[str, Any] | None = None,
) -> Action:
    case = case_id or uuid4()
    return Action(
        case_id=case,
        channel=Channel.BROWSER_PORTAL,
        kind="portal_claim",
        idempotency_key=key or f"case:{case}:execute:1",
        payload={"url": url, "portal_claim": claim if claim is not None else claim_payload()},
        badge=RealityBadge.REPRODUCTION,
    )


class FakeDriver:
    """Driver double: records jobs, then fails or returns a fake confirmation."""

    def __init__(
        self,
        name: str,
        *,
        error: PortalErrorCode | None = None,
        crash: bool = False,
        delay: float = 0.0,
    ) -> None:
        self.name = name
        self.error = error
        self.crash = crash
        self.delay = delay
        self.jobs: list[PortalJob] = []

    async def submit(self, job: PortalJob) -> PortalSubmission:
        self.jobs.append(job)
        await job.reporter.step(f"{self.name} started")
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.crash:
            raise RuntimeError("driver exploded")
        if self.error is not None:
            raise PortalError(self.error, "fake")
        job.screenshot_dir.mkdir(parents=True, exist_ok=True)
        shot = job.screenshot_dir / "01-confirmation.png"
        shot.write_bytes(PNG_MAGIC)
        number = f"FAKE{len(self.jobs):04d}"
        return PortalSubmission(
            case_number=number,
            url=f"{job.portal_url}{CONFIRMATION_MARKER}{number}",
            screenshot_path=shot,
        )


def make_settings(tmp_path: Path, **overrides: Any) -> BrowserSettings:
    values: dict[str, Any] = {"runtime_dir": tmp_path / "runtime", "action_timeout_seconds": 30}
    values.update(overrides)
    return BrowserSettings(**values)


def make_adapter(
    tmp_path: Path,
    *,
    scripted: FakeDriver | None = None,
    hcompany: FakeDriver | None = None,
    steps: list[tuple[str, str | None]] | None = None,
    **settings: Any,
) -> BrowserPortalAdapter:
    drivers: dict[BrowserEngine, Any] = {}
    if scripted is not None:
        drivers[BrowserEngine.SCRIPTED] = scripted
    if hcompany is not None:
        drivers[BrowserEngine.HCOMPANY] = hcompany

    def on_step(text: str, path: str | None) -> None:
        if steps is not None:
            steps.append((text, path))

    return BrowserPortalAdapter(
        make_settings(tmp_path, **settings), on_step=on_step, drivers=drivers
    )
