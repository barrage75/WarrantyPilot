from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.contracts.enums import CaseStatus
from app.contracts.models import Case, ChecklistStep, DataChecklist
from app.followup import ReturnDeadlineChecker, ReturnRequirement


def setup_return(manufacturer="Jabra", **kwargs):
    case = Case(incident_id=uuid4(), status=CaseStatus.TRACKED)
    requirement = ReturnRequirement(
        case_id=case.id,
        manufacturer=manufacturer,
        requested_on=date(2026, 11, 1),
        within_days=14,
        source="Consigne de retour fictive RMA-001, délai de démonstration",
        **kwargs,
    )
    return case, requirement


@pytest.mark.parametrize(
    "day,alert", [(11, None), (12, "due_soon"), (15, "due_soon"), (16, "overdue")]
)
def test_calculated_deadline_and_three_day_alert(day, alert):
    case, requirement = setup_return()
    event = ReturnDeadlineChecker(demo_today=date(2026, 11, day)).check(case, requirement)[0]
    assert event["due_on"] == "2026-11-15"
    assert event["alert_on"] == "2026-11-12"
    assert event["alert"] == alert
    assert event["replacement_blocked_until_return_received"] is True
    assert event["return_blocked"] is False
    assert event["executed"] is False


def test_dell_deadline_does_not_bypass_pc_checklist():
    case, requirement = setup_return("Dell")
    checker = ReturnDeadlineChecker(demo_today=date(2026, 11, 12))
    incomplete = DataChecklist(case_id=case.id)
    result = checker.check(case, requirement, incomplete)[0]
    assert result["alert"] == "due_soon"
    assert result["return_blocked"] is True
    assert result["blocking_prerequisite"] == "pc_data_protection_checklist"
    at = datetime(2026, 11, 1, tzinfo=UTC)
    complete = DataChecklist(
        case_id=case.id,
        steps={
            name: ChecklistStep(done=True, at=at, by_person_id=uuid4()) for name in incomplete.steps
        },
    )
    assert checker.check(case, requirement, complete)[0]["return_blocked"] is False
    other = complete.model_copy(update={"case_id": uuid4()})
    assert checker.check(case, requirement, other)[0]["return_blocked"] is True
    assert not any(step.done for step in incomplete.steps.values())


def test_return_received_cancelled_and_resolved():
    case, requirement = setup_return()
    checker = ReturnDeadlineChecker(demo_today=date(2026, 11, 12))
    case.status = CaseStatus.RESOLVED
    assert checker.check(case, requirement)  # Le retour peut rester dû après résolution.
    case.status = CaseStatus.CANCELLED
    assert checker.check(case, requirement) == []
    case, requirement = setup_return(received_on=date(2026, 11, 5))
    assert checker.check(case, requirement) == []


def test_source_and_case_link_are_required():
    case, requirement = setup_return()
    with pytest.raises(ValueError):
        ReturnDeadlineChecker().check(Case(incident_id=uuid4()), requirement)
    with pytest.raises(ValueError):
        ReturnRequirement(case.id, "Jabra", date(2026, 11, 1), 0, "test")
    with pytest.raises(ValueError):
        ReturnRequirement(case.id, "Jabra", date(2026, 11, 1), 14, "")
