"""Guarded Playwright session: allowlist enforcement, captures and confirmation reading.

Playwright is imported lazily so the backend runs without it; a missing
installation is reported as ``browser_unavailable``.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.actions.browser.drivers.base import CONFIRMATION_MARKER, PortalJob, PortalSubmission
from app.actions.browser.errors import PortalError, PortalErrorCode

# Defence in depth: Chromium cannot resolve any host except the loopback ones.
HOST_RESOLVER_RULES = "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1"
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 900
CASE_NUMBER_RE = re.compile(r"^[A-Za-z0-9-]{4,40}$")


def token_init_script(token: str) -> str:
    """Pin the hidden ``requestToken`` so every engine submits the idempotent token."""
    return (
        "(() => { const token = " + json.dumps(token) + ";"
        " const pin = () => document.querySelectorAll('input[name=\"requestToken\"]')"
        ".forEach((el) => { el.value = token; });"
        " document.addEventListener('DOMContentLoaded', pin);"
        " document.addEventListener('submit', pin, true); })();"
    )


def is_timeout(exc: BaseException) -> bool:
    return type(exc).__name__ == "TimeoutError"


class GuardedBrowser:
    def __init__(self, job: PortalJob, context: Any) -> None:
        self.job = job
        self.context = context
        self.page: Any = None
        self.violation: str | None = None
        self._shots = 0

    # --- allowlist guard -------------------------------------------------
    def _flag(self, url: str) -> None:
        if self.violation is None:
            self.violation = url

    def check(self) -> None:
        if self.violation is not None:
            raise PortalError(PortalErrorCode.URL_NOT_ALLOWED, self.violation)

    async def on_route(self, route: Any) -> None:
        request = route.request
        url = str(request.url)
        if self.job.allowlist.allows_navigation(url) or url.startswith(("data:", "blob:")):
            await route.continue_()
            return
        if request.is_navigation_request():
            self._flag(url)
        await route.abort("blockedbyclient")

    def on_request(self, request: Any) -> None:
        url = str(request.url)
        if (
            request.is_navigation_request()
            and url.startswith(("http:", "https:", "ftp:", "ws:", "wss:"))
            and not self.job.allowlist.allows(url)
        ):
            self._flag(url)

    def watch_page(self, page: Any) -> None:
        def on_frame(frame: Any) -> None:
            url = str(frame.url)
            if (
                frame == page.main_frame
                and not self.job.allowlist.allows_navigation(url)
                and not url.startswith(("chrome-error:", "data:"))
            ):
                self._flag(url)

        page.on("framenavigated", on_frame)

    # --- navigation helpers ----------------------------------------------
    def current_url(self) -> str:
        return str(self.page.url)

    def fail_from(self, exc: BaseException, what: str) -> PortalError:
        """Map a Playwright exception; an allowlist violation always wins."""
        if isinstance(exc, PortalError):
            return exc
        if self.violation is not None:
            return PortalError(PortalErrorCode.URL_NOT_ALLOWED, self.violation)
        if is_timeout(exc):
            return PortalError(PortalErrorCode.PORTAL_TIMEOUT, what)
        return PortalError(PortalErrorCode.PORTAL_ERROR, f"{what}: {exc}")

    async def goto(self, url: str) -> Any:
        self.job.allowlist.require(url)
        try:
            response = await self.page.goto(
                url, wait_until="domcontentloaded", timeout=self.job.navigation_timeout_ms
            )
        except Exception as exc:
            raise self.fail_from(exc, f"navigation to {url}") from exc
        self.check()
        return response

    async def screenshot(self, label: str) -> Path:
        self.check()
        self._shots += 1
        self.job.screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.job.screenshot_dir / f"{self._shots:02d}-{label}.png"
        await self.page.screenshot(path=str(path), full_page=True)
        return path

    async def screenshot_bytes(self) -> bytes:
        self.check()
        data = await self.page.screenshot(full_page=False)
        return bytes(data)

    async def step(self, text: str, label: str) -> Path:
        path = await self.screenshot(label)
        await self.job.reporter.step(text, path)
        return path

    async def read_confirmation(self) -> PortalSubmission:
        """Read the case number from the portal page itself, never from an agent's claim."""
        self.check()
        url = self.current_url()
        if CONFIRMATION_MARKER not in url or not self.job.allowlist.allows(url):
            raise PortalError(PortalErrorCode.CASE_NUMBER_MISSING, f"not a confirmation: {url}")
        locator = self.page.locator("#case-number")
        if await locator.count() == 0:
            raise PortalError(PortalErrorCode.CASE_NUMBER_MISSING, "no #case-number element")
        number = str(await locator.first.get_attribute("data-case-number") or "").strip()
        if not CASE_NUMBER_RE.match(number) or not url.rstrip("/").endswith(number):
            raise PortalError(PortalErrorCode.CASE_NUMBER_MISSING, f"unexpected number {number!r}")
        path = await self.step(f"Dossier Dell créé : {number}", "confirmation")
        return PortalSubmission(case_number=number, url=url, screenshot_path=path)


@asynccontextmanager
async def guarded_browser(
    job: PortalJob, *, cdp_port: int | None = None
) -> AsyncIterator[GuardedBrowser]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise PortalError(PortalErrorCode.BROWSER_UNAVAILABLE, "playwright missing") from exc

    args = [HOST_RESOLVER_RULES]
    if cdp_port is not None:
        args.append(f"--remote-debugging-port={cdp_port}")
    with TemporaryDirectory(prefix="wp-browser-") as profile:
        async with async_playwright() as pw:
            try:
                context = await pw.chromium.launch_persistent_context(
                    profile,
                    headless=job.settings.headless,
                    args=args,
                    viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                    accept_downloads=False,
                    service_workers="block",
                )
            except Exception as exc:
                raise PortalError(PortalErrorCode.BROWSER_UNAVAILABLE, str(exc)) from exc
            guard = GuardedBrowser(job, context)
            try:
                await context.add_init_script(token_init_script(job.request_token))
                await context.route("**/*", guard.on_route)
                context.on("request", guard.on_request)
                context.on("page", guard.watch_page)
                guard.page = context.pages[0] if context.pages else await context.new_page()
                guard.watch_page(guard.page)
                guard.page.set_default_timeout(job.navigation_timeout_ms)
                yield guard
            finally:
                await context.close()
