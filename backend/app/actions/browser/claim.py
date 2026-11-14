"""Form data for the Dell repair request, read only from ``Action.payload``."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.actions.browser.errors import PortalError, PortalErrorCode
from app.contracts.models import BrowserPortalClaim

PortalClaim = BrowserPortalClaim


def parse_claim(payload: dict[str, Any]) -> PortalClaim:
    raw = payload.get("portal_claim")
    if not isinstance(raw, dict):
        raise PortalError(PortalErrorCode.INVALID_PAYLOAD, "payload.portal_claim is missing")
    try:
        return PortalClaim.model_validate(raw)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in err["loc"]) for err in exc.errors()})
        raise PortalError(PortalErrorCode.INVALID_PAYLOAD, ", ".join(fields)) from exc
