"""Deterministic selector-based driver: the always-available engine used in CI."""

from __future__ import annotations

from typing import Any

from app.actions.browser.drivers._session import GuardedBrowser, guarded_browser
from app.actions.browser.drivers.base import SIGNIN_PATH, PortalJob, PortalSubmission
from app.actions.browser.errors import PortalError, PortalErrorCode


def status_error(response: Any, what: str) -> PortalError | None:
    status = int(response.status) if response is not None else 0
    if status == 0:
        return PortalError(PortalErrorCode.PORTAL_ERROR, f"{what}: no response")
    if status < 400:
        return None
    mapping = {
        404: PortalErrorCode.UNKNOWN_SERVICE_TAG,
        403: PortalErrorCode.WARRANTY_EXPIRED,
        422: PortalErrorCode.PORTAL_VALIDATION_ERROR,
        504: PortalErrorCode.PORTAL_TIMEOUT,
    }
    return PortalError(mapping.get(status, PortalErrorCode.PORTAL_ERROR), f"{what}: HTTP {status}")


class ScriptedPlaywrightDriver:
    name = "scripted"

    async def submit(self, job: PortalJob) -> PortalSubmission:
        async with guarded_browser(job) as browser:
            return await self.run(browser)

    async def _click_and_wait(self, browser: GuardedBrowser, selector: str, what: str) -> Any:
        page = browser.page
        try:
            async with page.expect_navigation(
                wait_until="domcontentloaded", timeout=browser.job.navigation_timeout_ms
            ) as navigation:
                await page.click(selector)
            response = await navigation.value
        except Exception as exc:
            raise browser.fail_from(exc, what) from exc
        browser.check()
        return response

    async def sign_in(self, browser: GuardedBrowser) -> Any:
        job = browser.job
        page = browser.page
        await browser.step("Connexion au compte de démonstration de la reproduction", "signin")
        await page.fill('[name="SignInModel.EmailAddress"]', job.email)
        await self._click_and_wait(browser, "#btnSSoContinue", "sign-in email step")
        if await page.locator("#userPwd_UserInputSecret").count() == 0:
            raise PortalError(PortalErrorCode.LOGIN_FAILED, "password step not shown")
        await page.fill("#userPwd_UserInputSecret", job.password)
        response = await self._click_and_wait(browser, "#btnSignIn", "sign-in password step")
        if SIGNIN_PATH in browser.current_url():
            raise PortalError(PortalErrorCode.LOGIN_FAILED, "demo credentials rejected")
        return response

    async def run(self, browser: GuardedBrowser) -> PortalSubmission:
        job = browser.job
        claim = job.claim
        page = browser.page
        response = await browser.goto(job.form_url)
        if SIGNIN_PATH in browser.current_url():
            response = await self.sign_in(browser)
            if job.claim.repro_fail_mode:
                # The sign-in redirect drops extra query parameters such as ``__fail``.
                response = await browser.goto(job.form_url)
        if error := status_error(response, "repair form"):
            await browser.step(f"Formulaire indisponible ({error.code.value})", "form-error")
            raise error
        await browser.step(f"Formulaire de réparation ouvert pour {claim.service_tag}", "form")

        await page.select_option("#problemCategory", label=claim.problem_category)
        for field_id, value in claim.form_values().items():
            await page.fill(f"#{field_id}", value)
        await page.select_option("#availabilitySlot", label=claim.availability_slot)
        if claim.attachment_path is not None:
            await page.set_input_files("#attachment", str(claim.attachment_path))
        await page.check("#consent")
        await browser.step("Formulaire rempli avec les données de l'action", "filled")

        response = await self._click_and_wait(browser, "#btnSubmitRequest", "submission")
        if error := status_error(response, "submission"):
            if error.code == PortalErrorCode.PORTAL_VALIDATION_ERROR:
                messages = await page.locator("p.error[role=alert]").all_inner_texts()
                error = PortalError(error.code, "; ".join(m.strip() for m in messages))
            await browser.step(f"Soumission refusée ({error.code.value})", "submit-error")
            raise error
        return await browser.read_confirmation()
