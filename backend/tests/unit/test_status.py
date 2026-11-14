from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.contracts.enums import ActionResultStatus, CaseStatus, RealityBadge
from app.contracts.models import ActionResult
from app.core.status import TRANSITIONS, InvalidTransition, transition


def _success() -> ActionResult:
    return ActionResult(
        action_id=uuid4(),
        status=ActionResultStatus.SUCCESS,
        proof="ticket-123",
        badge=RealityBadge.SIMULATED,
    )


def test_every_declared_transition_is_accepted() -> None:
    for current, targets in TRANSITIONS.items():
        for target in targets:
            kwargs = {"action_result": _success()} if target == CaseStatus.SENT else {}
            assert transition(current, target, **kwargs) == target


def test_every_undeclared_transition_is_rejected() -> None:
    for current in CaseStatus:
        for target in CaseStatus:
            if target not in TRANSITIONS[current]:
                with pytest.raises(InvalidTransition):
                    transition(current, target, action_result=_success())


def test_sent_requires_successful_result_with_proof() -> None:
    failure = ActionResult(
        action_id=uuid4(),
        status=ActionResultStatus.FAILURE,
        error="not delivered",
        badge=RealityBadge.SIMULATED,
    )
    with pytest.raises(InvalidTransition, match="successful ActionResult"):
        transition(CaseStatus.SENDING, CaseStatus.SENT, action_result=failure)
    with pytest.raises(ValidationError):
        ActionResult(
            action_id=uuid4(),
            status=ActionResultStatus.SUCCESS,
            proof=" ",
            badge=RealityBadge.SIMULATED,
        )
    with pytest.raises(InvalidTransition):
        transition(CaseStatus.PREPARED, CaseStatus.SENT, action_result=_success())


def test_failed_retry_is_limited_to_two_attempts() -> None:
    assert transition(CaseStatus.FAILED, CaseStatus.SENDING, attempts=0)
    assert transition(CaseStatus.FAILED, CaseStatus.SENDING, attempts=1)
    with pytest.raises(InvalidTransition, match="at most twice"):
        transition(CaseStatus.FAILED, CaseStatus.SENDING, attempts=2)
