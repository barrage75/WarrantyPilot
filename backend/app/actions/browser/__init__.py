"""Browser portal adapter (lot L4b): files repair requests on the local Dell reproduction."""

from app.actions.browser.adapter import BrowserPortalAdapter
from app.actions.browser.allowlist import UrlAllowlist
from app.actions.browser.drivers.base import BrowserDriver, PortalJob, PortalSubmission
from app.actions.browser.drivers.browser_use import BrowserUseDriver
from app.actions.browser.drivers.hcompany import HCompanyDriver
from app.actions.browser.drivers.scripted import ScriptedPlaywrightDriver
from app.actions.browser.errors import PortalError, PortalErrorCode
from app.actions.browser.settings import BrowserEngine, BrowserSettings

__all__ = [
    "BrowserDriver",
    "BrowserEngine",
    "BrowserPortalAdapter",
    "BrowserSettings",
    "BrowserUseDriver",
    "HCompanyDriver",
    "PortalError",
    "PortalErrorCode",
    "PortalJob",
    "PortalSubmission",
    "ScriptedPlaywrightDriver",
    "UrlAllowlist",
]
