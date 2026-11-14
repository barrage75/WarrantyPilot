"""Browser Use driver (open-source 1.0, https://docs.browser-use.com/open-source).

The agent drives our guarded Chromium through its CDP endpoint, with
``allowed_domains`` restricted to the reproduction. Success is never taken
from the agent's verdict: the case number is read from the confirmation page.
"""

from __future__ import annotations

import socket
from typing import Any

from app.actions.browser.drivers._session import GuardedBrowser, guarded_browser
from app.actions.browser.drivers.base import CONFIRMATION_MARKER, PortalJob, PortalSubmission
from app.actions.browser.drivers.hcompany import build_task
from app.actions.browser.errors import PortalError, PortalErrorCode


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class BrowserUseDriver:
    name = "browser_use"

    def build_llm(self, job: PortalJob) -> Any:
        try:
            from browser_use import ChatOpenAI
        except ImportError as exc:
            raise PortalError(PortalErrorCode.ENGINE_UNAVAILABLE, "browser-use missing") from exc
        settings = job.settings
        model = settings.browser_use_model
        if model.startswith("bu-"):
            if settings.browser_use_api_key is None:
                raise PortalError(PortalErrorCode.ENGINE_UNAVAILABLE, "BROWSER_USE_API_KEY not set")
            # A 'bu-*' string is documented as ChatBrowserUse, keyed by BROWSER_USE_API_KEY.
            return model
        if settings.openai_api_key is None:
            raise PortalError(PortalErrorCode.ENGINE_UNAVAILABLE, "OPENAI_API_KEY not set")
        return ChatOpenAI(
            model,
            api_key=settings.openai_api_key.get_secret_value(),
            base_url=settings.browser_use_openai_base_url,
        )

    async def submit(self, job: PortalJob) -> PortalSubmission:
        llm = self.build_llm(job)
        from browser_use import Agent, Browser

        port = free_port()
        async with guarded_browser(job, cdp_port=port) as browser:
            await browser.goto(job.form_url)
            await browser.step("Agent Browser Use démarré sur la reproduction Dell", "agent-start")
            agent = Agent(
                build_task(job) + f"\nThe form is already open at {job.form_url}.",
                llm=llm,
                browser=Browser(
                    cdp_url=f"http://127.0.0.1:{port}",
                    allowed_domains=job.allowlist.browser_use_domains(),
                ),
            )
            try:
                result = await agent.run(
                    max_steps=job.settings.agent_max_steps,
                    timeout=job.settings.action_timeout_seconds,
                )
            except Exception as exc:
                raise browser.fail_from(exc, "browser-use run") from exc
            browser.check()
            if getattr(result, "status", None) != "completed":
                status = getattr(result, "status", None)
                error = getattr(result, "error", None)
                raise PortalError(PortalErrorCode.AGENT_FAILED, f"status={status} error={error}")
            self._focus_confirmation(browser)
            return await browser.read_confirmation()

    @staticmethod
    def _focus_confirmation(browser: GuardedBrowser) -> None:
        for page in browser.context.pages:
            if CONFIRMATION_MARKER in str(page.url):
                browser.page = page
                return
