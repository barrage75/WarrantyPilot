"""Typed failures raised by browser drivers and mapped to ``ActionResult.error``."""

from __future__ import annotations

from enum import StrEnum


class PortalErrorCode(StrEnum):
    URL_NOT_ALLOWED = "url_not_allowed"
    INVALID_PAYLOAD = "invalid_payload"
    DEMO_CREDENTIALS_REQUIRED = "demo_credentials_required"
    BROWSER_UNAVAILABLE = "browser_unavailable"
    ENGINE_UNAVAILABLE = "engine_unavailable"
    AGENT_FAILED = "agent_failed"
    PORTAL_TIMEOUT = "portal_timeout"
    PORTAL_ERROR = "portal_error"
    PORTAL_VALIDATION_ERROR = "portal_validation_error"
    LOGIN_FAILED = "login_failed"
    UNKNOWN_SERVICE_TAG = "unknown_service_tag"
    WARRANTY_EXPIRED = "warranty_expired"
    CASE_NUMBER_MISSING = "case_number_missing"


ENGINE_SIDE_ERRORS = frozenset(
    {
        PortalErrorCode.ENGINE_UNAVAILABLE,
        PortalErrorCode.AGENT_FAILED,
        PortalErrorCode.CASE_NUMBER_MISSING,
        PortalErrorCode.PORTAL_VALIDATION_ERROR,
        PortalErrorCode.LOGIN_FAILED,
    }
)
"""Failures caused by the driver itself; another engine may succeed where it failed."""


class PortalError(Exception):
    def __init__(self, code: PortalErrorCode, detail: str = "") -> None:
        super().__init__(f"{code.value}: {detail}" if detail else code.value)
        self.code = code
        self.detail = detail

    @property
    def fallback_allowed(self) -> bool:
        return self.code in ENGINE_SIDE_ERRORS
