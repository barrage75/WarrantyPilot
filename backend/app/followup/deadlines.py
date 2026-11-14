from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from app.contracts.enums import CaseStatus
from app.contracts.models import Case, DataChecklist
from app.followup.clock import Clock, FollowUpClock, utc_now


@dataclass(frozen=True)
class ReturnRequirement:
    case_id: UUID
    manufacturer: str
    requested_on: date
    within_days: int
    source: str
    is_pc: bool = False
    received_on: date | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.within_days, bool)
            or not isinstance(self.within_days, int)
            or self.within_days < 1
        ):
            raise ValueError("Un délai de retour explicite et positif est requis")
        if not self.source.strip():
            raise ValueError("La source du délai de retour est requise")
        if not self.manufacturer.strip():
            raise ValueError("Le fabricant est requis")

    @property
    def due_on(self) -> date:
        return self.requested_on + timedelta(days=self.within_days)


class ReturnDeadlineChecker:
    def __init__(self, *, clock: Clock = utc_now, demo_today: date | None = None) -> None:
        self.clock = FollowUpClock(clock, demo_today)

    def check(
        self, case: Case, requirement: ReturnRequirement, checklist: DataChecklist | None = None
    ) -> list[dict[str, Any]]:
        if requirement.case_id != case.id:
            raise ValueError("Le retour doit appartenir au dossier")
        if case.status == CaseStatus.CANCELLED or requirement.received_on is not None:
            return []
        today = self.clock.now().date()
        days_left = (requirement.due_on - today).days
        manufacturer = requirement.manufacturer.strip().casefold()
        requires_checklist = requirement.is_pc or manufacturer == "dell"
        data_ready = bool(checklist and checklist.case_id == case.id and checklist.complete())
        alert = "overdue" if days_left < 0 else "due_soon" if days_left <= 3 else None
        return [
            {
                "kind": "return_deadline",
                "case_id": str(case.id),
                "manufacturer": requirement.manufacturer,
                "source": requirement.source,
                "due_on": requirement.due_on.isoformat(),
                "alert_on": (requirement.due_on - timedelta(days=3)).isoformat(),
                "days_left": days_left,
                "alert": alert,
                "observed_on": today.isoformat(),
                "requires_data_checklist": requires_checklist,
                "return_blocked": requires_checklist and not data_ready,
                "blocking_prerequisite": "pc_data_protection_checklist"
                if requires_checklist and not data_ready
                else None,
                "replacement_blocked_until_return_received": manufacturer == "jabra",
                "executed": False,
            }
        ]
