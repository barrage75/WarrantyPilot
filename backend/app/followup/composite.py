from typing import Any

from app.contracts.enums import Channel
from app.contracts.interfaces import FollowUpChecker
from app.contracts.models import Case
from app.followup.portal import ACTIVE_STATUSES


def effective_channel(case: Case) -> Channel:
    return (case.verdict.channel if case.verdict else None) or case.channel


class CompositeFollowUp:
    def __init__(self, email: FollowUpChecker, portal: FollowUpChecker) -> None:
        self.email, self.portal = email, portal

    def check(self, case: Case) -> list[dict[str, Any]]:
        if case.status not in ACTIVE_STATUSES:
            return []
        channel = effective_channel(case)
        if channel in {
            Channel.EMAIL_RESELLER,
            Channel.EMAIL_MANUFACTURER_SUPPORT,
            Channel.EMAIL_LESSOR,
        }:
            return self.email.check(case)
        if channel == Channel.BROWSER_PORTAL:
            return self.portal.check(case)
        return []
