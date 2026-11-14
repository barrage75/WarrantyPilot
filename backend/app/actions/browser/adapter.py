"""``ActionAdapter`` for ``Channel.BROWSER_PORTAL`` on the local Dell reproduction."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from urllib.parse import urlsplit

from app.actions.browser.allowlist import UrlAllowlist, origin_of
from app.actions.browser.claim import parse_claim
from app.actions.browser.drivers.base import (
    BrowserDriver,
    PortalJob,
    PortalSubmission,
    StepCallback,
    StepReporter,
)
from app.actions.browser.drivers.browser_use import BrowserUseDriver
from app.actions.browser.drivers.hcompany import HCompanyDriver
from app.actions.browser.drivers.scripted import ScriptedPlaywrightDriver
from app.actions.browser.errors import PortalError, PortalErrorCode
from app.actions.browser.proof import PortalProof
from app.actions.browser.settings import BrowserEngine, BrowserSettings
from app.actions.browser.store import IdempotencyStore, request_token_for
from app.contracts.enums import ActionResultStatus, Channel, RealityBadge
from app.contracts.models import Action, ActionResult

logger = logging.getLogger(__name__)

DEMO_EMAIL_SUFFIX = "@reproduction.local"


def default_drivers() -> dict[BrowserEngine, BrowserDriver]:
    return {
        BrowserEngine.SCRIPTED: ScriptedPlaywrightDriver(),
        BrowserEngine.HCOMPANY: HCompanyDriver(),
        BrowserEngine.BROWSER_USE: BrowserUseDriver(),
    }


class BrowserPortalAdapter:
    channel: Channel = Channel.BROWSER_PORTAL
    badge: RealityBadge = RealityBadge.REPRODUCTION

    def __init__(
        self,
        settings: BrowserSettings | None = None,
        *,
        on_step: StepCallback | None = None,
        drivers: Mapping[BrowserEngine, BrowserDriver] | None = None,
        store: IdempotencyStore | None = None,
    ) -> None:
        self.settings = settings or BrowserSettings()
        self.allowlist = UrlAllowlist(
            test_origins=self.settings.test_origins, test_mode=self.settings.test_mode
        )
        self.on_step = on_step
        self.drivers: dict[BrowserEngine, BrowserDriver] = {**default_drivers(), **(drivers or {})}
        self.store = store or IdempotencyStore(self.settings.store_path)
        self._locks: dict[str, asyncio.Lock] = {}

    def _failure(self, action: Action, error: str) -> ActionResult:
        return ActionResult(
            action_id=action.id, status=ActionResultStatus.FAILURE, error=error, badge=self.badge
        )

    def _portal_origin(self, action: Action) -> str:
        target = str(action.payload.get("url") or self.settings.portal_url)
        self.allowlist.require(target)
        self.allowlist.require(self.settings.portal_url)
        parts = urlsplit(target)
        if origin_of(target) is None:
            raise PortalError(PortalErrorCode.URL_NOT_ALLOWED, target)
        return f"{parts.scheme}://{parts.netloc}"

    def _check_demo_credentials(self) -> None:
        if not self.settings.demo_email.lower().endswith(DEMO_EMAIL_SUFFIX):
            raise PortalError(
                PortalErrorCode.DEMO_CREDENTIALS_REQUIRED,
                "only reproduction demo accounts may be used",
            )

    async def execute(self, action: Action) -> ActionResult:
        if action.channel != Channel.BROWSER_PORTAL:
            return self._failure(action, "unsupported_channel")
        reporter = StepReporter(self.on_step, self.settings.browser_engine.value)
        try:
            origin = self._portal_origin(action)
            claim = parse_claim(action.payload)
            self._check_demo_credentials()
        except PortalError as exc:
            logger.warning("browser_portal action %s refused: %s", action.id, exc)
            await reporter.step(f"Action refusée : {exc}")
            return self._failure(action, exc.code.value)

        token = request_token_for(action.case_id)
        lock = self._locks.setdefault(token, asyncio.Lock())
        async with lock:
            prior = self.store.reserve(action.idempotency_key, action.case_id, token)
            if prior is not None and prior.proof:
                replay = PortalProof.model_validate_json(prior.proof).model_copy(
                    update={"replayed": True}
                )
                await reporter.step(
                    f"Dossier déjà créé ({replay.case_number}) : aucune nouvelle soumission",
                    replay.screenshot_path,
                )
                return ActionResult(
                    action_id=action.id,
                    status=ActionResultStatus.SUCCESS,
                    proof=replay.to_json(),
                    badge=self.badge,
                )
            job = PortalJob(
                action_id=action.id,
                claim=claim,
                portal_url=origin,
                request_token=token,
                email=self.settings.demo_email,
                password=self.settings.demo_password.get_secret_value(),
                screenshot_dir=self.settings.screenshot_dir / str(action.id),
                allowlist=self.allowlist,
                settings=self.settings,
                reporter=reporter,
            )
            try:
                engine, submission = await asyncio.wait_for(
                    self._run_engines(job), timeout=self.settings.action_timeout_seconds
                )
            except TimeoutError:
                await reporter.step("Délai global dépassé : action arrêtée")
                return self._failure(action, PortalErrorCode.PORTAL_TIMEOUT.value)
            except PortalError as exc:
                logger.warning("browser_portal action %s failed: %s", action.id, exc)
                await reporter.step(f"Échec : {exc}")
                return self._failure(action, exc.code.value)

            proof = PortalProof(
                case_number=submission.case_number,
                url=submission.url,
                screenshot_path=str(submission.screenshot_path),
                engine=engine.value,
                request_token=token,
            )
            self.store.complete(action.idempotency_key, proof.to_json())
            return ActionResult(
                action_id=action.id,
                status=ActionResultStatus.SUCCESS,
                proof=proof.to_json(),
                badge=self.badge,
            )

    async def _run_engines(self, job: PortalJob) -> tuple[BrowserEngine, PortalSubmission]:
        engine = self.settings.browser_engine
        try:
            return engine, await self._run(engine, job)
        except PortalError as exc:
            can_fall_back = (
                engine != BrowserEngine.SCRIPTED
                and self.settings.fallback_to_scripted
                and exc.fallback_allowed
            )
            if not can_fall_back:
                raise
            logger.warning(
                "browser_portal engine %s failed (%s); falling back to scripted", engine, exc
            )
            await job.reporter.step(
                f"Échec du moteur {engine.value} ({exc.code.value}) : bascule sur le moteur scripté"
            )
        scripted_job = PortalJob(
            **{**job.__dict__, "reporter": StepReporter(self.on_step, BrowserEngine.SCRIPTED.value)}
        )
        return BrowserEngine.SCRIPTED, await self._run(BrowserEngine.SCRIPTED, scripted_job)

    async def _run(self, engine: BrowserEngine, job: PortalJob) -> PortalSubmission:
        driver = self.drivers[engine]
        try:
            return await driver.submit(job)
        except PortalError:
            raise
        except Exception as exc:
            logger.exception("browser_portal driver %s crashed", engine)
            code = (
                PortalErrorCode.PORTAL_ERROR
                if engine == BrowserEngine.SCRIPTED
                else PortalErrorCode.AGENT_FAILED
            )
            raise PortalError(code, f"{type(exc).__name__}: {exc}") from exc
